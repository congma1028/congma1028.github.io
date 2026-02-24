import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .models import Paper


def latex_escape(text: str) -> str:
    unicode_replacements = {
        "α": r"$\alpha$",
        "β": r"$\beta$",
        "γ": r"$\gamma$",
        "δ": r"$\delta$",
        "ε": r"$\epsilon$",
        "θ": r"$\theta$",
        "λ": r"$\lambda$",
        "μ": r"$\mu$",
        "π": r"$\pi$",
        "σ": r"$\sigma$",
        "τ": r"$\tau$",
        "φ": r"$\phi$",
        "ω": r"$\omega$",
        "Δ": r"$\Delta$",
        "Σ": r"$\Sigma$",
        "Ω": r"$\Omega$",
        "≤": r"$\leq$",
        "≥": r"$\geq$",
        "≠": r"$\neq$",
        "≈": r"$\approx$",
        "→": r"$\rightarrow$",
        "←": r"$\leftarrow$",
        "∞": r"$\infty$",
        "×": r"$\times$",
        "–": "-",
        "—": "--",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
    }
    for src, dst in unicode_replacements.items():
        text = text.replace(src, dst)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def render_tex(date_str: str, ranked: List[Dict[str, object]]) -> str:
    parts = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{hyperref}",
        r"\usepackage{enumitem}",
        r"\usepackage{microtype}",
        r"\setlist[itemize]{noitemsep,topsep=2pt,leftmargin=1.25em}",
        r"\title{Daily Paper Digest --- " + latex_escape(date_str) + r"}",
        r"\date{}",
        r"\begin{document}",
        r"\maketitle",
        r"\section*{Top Papers}",
    ]
    if not ranked:
        parts.append(r"No papers passed filtering today.")
    for item in ranked:
        p: Paper = item["paper"]  # type: ignore[index]
        ev: Dict[str, object] = item["eval"]  # type: ignore[index]
        zot_synced = bool(item.get("zotero_synced", False))
        zot_url = str(item.get("zotero_url", "") or "")
        authors = ", ".join(p.authors) if p.authors else "Unknown"
        tags = ev.get("tags", [])
        tag_text = ", ".join(str(t) for t in tags) if isinstance(tags, list) and tags else "-"
        summary = str(ev.get("summary", "") or "")
        reasons = ev.get("reasons", [])
        section_title = latex_escape(p.title)
        if zot_synced:
            if zot_url:
                section_title += r" \href{" + zot_url + r"}{[Zotero]}"
            else:
                section_title += r" [Zotero]"
        parts.extend(
            [
                r"\subsection*{" + section_title + r"}",
                r"\textbf{Authors:} " + latex_escape(authors) + r"\\",
                r"\textbf{Date:} " + latex_escape(p.date) + r"\\",
                r"\textbf{Link:} \href{" + p.link + r"}{" + latex_escape(p.link) + r"}\\",
                r"\textbf{PDF:} \href{" + (p.pdf_link or p.link) + r"}{PDF}\\",
                r"\textbf{Score:} " + latex_escape(str(ev.get("score", 0))) + r"\\",
                r"\textbf{Tags:} " + latex_escape(tag_text),
                "",
                latex_escape(summary),
                "",
                r"\textbf{Why relevant:}",
                r"\begin{itemize}",
            ]
        )
        if isinstance(reasons, list):
            for reason in reasons[:3]:
                parts.append(r"\item " + latex_escape(str(reason)))
        parts.extend([r"\end{itemize}", ""])
    parts.append(r"\end{document}")
    return "\n".join(parts) + "\n"


def write_digest_tex(date_str: str, content: str, digest_dir: Path) -> Path:
    path = digest_dir / f"{date_str}.tex"
    path.write_text(content, encoding="utf-8")
    return path


def _run(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def _find_cmd(name: str) -> Optional[str]:
    return shutil.which(name)


def compile_pdf(date_str: str, tex_path: Path, digest_dir: Path, build_dir: Path, progress_cb=None) -> Path:
    out_pdf = digest_dir / f"{date_str}.pdf"
    tectonic = _find_cmd("tectonic")
    if tectonic:
        if progress_cb:
            progress_cb("Compiling PDF with tectonic")
        proc = _run([tectonic, "--outdir", str(digest_dir), str(tex_path)])
        if proc.returncode == 0 and out_pdf.exists():
            return out_pdf
        raise RuntimeError(f"tectonic failed:\n{proc.stdout}")

    pdflatex = _find_cmd("pdflatex")
    if not pdflatex:
        raise RuntimeError("No LaTeX compiler found. Install 'tectonic' or 'pdflatex'.")
    build_day_dir = build_dir / date_str
    if build_day_dir.exists():
        shutil.rmtree(build_day_dir)
    build_day_dir.mkdir(parents=True, exist_ok=True)
    temp_tex = build_day_dir / tex_path.name
    shutil.copy2(tex_path, temp_tex)
    try:
        for pass_idx in range(2):
            if progress_cb:
                progress_cb(f"Compiling PDF with pdflatex (pass {pass_idx + 1}/2)")
            proc = _run([pdflatex, "-interaction=nonstopmode", "-halt-on-error", temp_tex.name], cwd=build_day_dir)
            if proc.returncode != 0:
                raise RuntimeError(f"pdflatex failed:\n{proc.stdout}")
        built_pdf = build_day_dir / f"{date_str}.pdf"
        if not built_pdf.exists():
            raise RuntimeError("pdflatex did not produce expected PDF output")
        shutil.copy2(built_pdf, out_pdf)
        return out_pdf
    finally:
        shutil.rmtree(build_day_dir, ignore_errors=True)
