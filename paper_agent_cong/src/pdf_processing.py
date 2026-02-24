import io
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover
    PdfReader = None

from .models import Paper


def download_pdf_bytes(url: str, user_agent: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/pdf"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def _drop_appendix(text: str) -> str:
    patterns = [
        r"(?im)^\s*appendix(?:\s+[a-z0-9].*)?$",
        r"(?im)^\s*appendices(?:\s*[:\-].*)?$",
        r"(?im)^\s*references\s*$",
        r"(?im)^\s*bibliography\s*$",
    ]
    cut = len(text)
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            cut = min(cut, m.start())
    return text[:cut].strip()


def _default_external_extractor_cmd() -> Optional[str]:
    if shutil.which("pdftotext"):
        return "pdftotext -layout -nopgbrk {pdf} -"
    return None


def _extract_main_text_with_external(pdf_bytes: bytes, cmd_template: str) -> str:
    with tempfile.TemporaryDirectory(prefix="paper_extract_") as tmpdir:
        tmp_pdf = Path(tmpdir) / "paper.pdf"
        tmp_pdf.write_bytes(pdf_bytes)
        cmd_text = cmd_template.replace("{pdf}", str(tmp_pdf))
        if "{pdf}" not in cmd_template:
            cmd_text = f"{cmd_text} {str(tmp_pdf)}"
        proc = subprocess.run(shlex.split(cmd_text), check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"external extractor failed (exit {proc.returncode})")
        output = proc.stdout.strip()
        if output:
            return output
        md_path = tmp_pdf.with_suffix(".md")
        if md_path.exists():
            return md_path.read_text(encoding="utf-8", errors="replace")
        return ""


def _extract_main_text_with_pypdf(pdf_bytes: bytes) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    chunks: List[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        if t:
            chunks.append(t)
    return "\n\n".join(chunks).strip()


def extract_main_text_from_pdf(pdf_bytes: bytes, progress_cb=None) -> str:
    extractor = os.getenv("PAPER_TEXT_EXTRACTOR", "auto").strip().lower()
    cmd_template = os.getenv("PAPER_TEXT_EXTRACTOR_CMD", "").strip()
    if extractor == "auto" and not cmd_template:
        auto_cmd = _default_external_extractor_cmd()
        if auto_cmd:
            cmd_template = auto_cmd
    if extractor in {"external", "auto"} and cmd_template:
        try:
            text = _extract_main_text_with_external(pdf_bytes, cmd_template)
            if text:
                return _drop_appendix(text)
        except Exception as e:
            if progress_cb:
                progress_cb(f"External extractor failed; falling back to pypdf ({type(e).__name__})")
    elif extractor == "external" and not cmd_template:
        raise RuntimeError("PAPER_TEXT_EXTRACTOR=external requires PAPER_TEXT_EXTRACTOR_CMD")
    return _drop_appendix(_extract_main_text_with_pypdf(pdf_bytes))


def _safe_filename(text: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    return out[:120] if out else "paper"


def download_pdfs_for_papers(
    papers: List[Paper],
    date_str: str,
    user_agent: str,
    build_dir: Path,
    arxiv_pdf_lookup: Callable[[str, str, int], Optional[str]],
    progress_cb=None,
) -> Dict[str, int]:
    out_dir = build_dir / date_str / "pdfs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    skipped = 0
    failed = 0
    arxiv_retry_hits = 0
    for idx, p in enumerate(papers, start=1):
        pdf_url = p.pdf_link or (f"https://arxiv.org/pdf/{p.paper_id}.pdf" if p.source == "arxiv" else None)
        if not pdf_url:
            skipped += 1
            continue
        if progress_cb:
            progress_cb(f"PDF {idx}/{len(papers)}: {p.paper_id}")
        dest = out_dir / f"{_safe_filename(p.paper_id)}.pdf"
        try:
            data = download_pdf_bytes(pdf_url, user_agent)
            if not data:
                raise RuntimeError("empty PDF response body")
            dest.write_bytes(data)
            ok += 1
        except Exception:
            alt_pdf_url = arxiv_pdf_lookup(p.title, user_agent, 3)
            if alt_pdf_url and alt_pdf_url != pdf_url:
                try:
                    data2 = download_pdf_bytes(alt_pdf_url, user_agent)
                    if data2:
                        dest.write_bytes(data2)
                        ok += 1
                        arxiv_retry_hits += 1
                        continue
                except Exception:
                    pass
            failed += 1
    return {
        "downloaded": ok,
        "skipped": skipped,
        "failed": failed,
        "arxiv_retry_hits": arxiv_retry_hits,
        "output_dir": str(out_dir),
    }
