import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

from ..models import Paper
from .base import BaseProvider


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _crossref_date_from_item(item: Dict[str, object]) -> str:
    for key in ["published-print", "published-online", "issued", "created"]:
        date_obj = item.get(key, {})
        if not isinstance(date_obj, dict):
            continue
        parts = date_obj.get("date-parts", [])
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            y = int(parts[0][0])
            m = int(parts[0][1]) if len(parts[0]) > 1 else 1
            d = int(parts[0][2]) if len(parts[0]) > 2 else 1
            return f"{y:04d}-{m:02d}-{d:02d}"
    return ""


class CrossrefProvider(BaseProvider):
    def __init__(
        self,
        journals: List[str],
        max_results_per_journal: int,
        from_days: int,
        request_delay_seconds: float = 1.0,
        user_agent: str = "paper-agent/1.0",
        arxiv_pdf_fallback: bool = True,
        arxiv_lookup_fn: Optional[Callable[[str], Optional[str]]] = None,
        progress_cb=None,
    ) -> None:
        self.journals = journals
        self.max_results_per_journal = max_results_per_journal
        self.from_days = from_days
        self.request_delay_seconds = request_delay_seconds
        self.user_agent = user_agent
        self.arxiv_pdf_fallback = arxiv_pdf_fallback
        self.arxiv_lookup_fn = arxiv_lookup_fn
        self.progress_cb = progress_cb

    @property
    def name(self) -> str:
        return "crossref"

    def _progress(self, msg: str) -> None:
        if self.progress_cb:
            self.progress_cb(msg)

    def fetch(self) -> List[Paper]:
        if not self.journals:
            return []
        self._progress(f"Fetch 2/2: Crossref journals ({len(self.journals)})")
        all_papers: List[Paper] = []
        since_date = (dt.date.today() - dt.timedelta(days=self.from_days)).isoformat()
        arxiv_hits = 0

        for idx, journal in enumerate(self.journals, start=1):
            self._progress(f"Crossref {idx}/{len(self.journals)}: {journal}")
            params = urllib.parse.urlencode(
                {
                    "filter": f"from-pub-date:{since_date},container-title:{journal}",
                    "sort": "published",
                    "order": "desc",
                    "rows": str(self.max_results_per_journal),
                    "select": "DOI,title,author,abstract,URL,container-title,published-print,published-online,issued,link",
                }
            )
            url = f"https://api.crossref.org/works?{params}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
            except Exception:
                time.sleep(self.request_delay_seconds)
                continue

            items = raw.get("message", {}).get("items", [])
            if not isinstance(items, list):
                items = []
            added = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                doi = str(item.get("DOI", "")).strip()
                if not doi:
                    continue
                title_list = item.get("title", [])
                title = str(title_list[0]).strip() if isinstance(title_list, list) and title_list else ""
                if not title:
                    continue
                abstract = str(item.get("abstract", "") or "")
                abstract = _normalize_ws(re.sub(r"<[^>]+>", " ", abstract))
                authors: List[str] = []
                for a in item.get("author", []) or []:
                    if not isinstance(a, dict):
                        continue
                    given = str(a.get("given", "")).strip()
                    family = str(a.get("family", "")).strip()
                    full = (given + " " + family).strip()
                    if full:
                        authors.append(full)
                link = str(item.get("URL", "")).strip() or f"https://doi.org/{doi}"
                pdf_link = None
                for lnk in item.get("link", []) or []:
                    if not isinstance(lnk, dict):
                        continue
                    ctype = str(lnk.get("content-type", "")).lower()
                    href = str(lnk.get("URL", "")).strip()
                    if href and "pdf" in ctype:
                        pdf_link = href
                        break
                journal_names = item.get("container-title", []) or []
                journal_name = (
                    str(journal_names[0]).strip()
                    if isinstance(journal_names, list) and journal_names
                    else journal
                )
                paper = Paper(
                    paper_id=f"doi:{doi.lower()}",
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    date=_crossref_date_from_item(item),
                    link=link,
                    pdf_link=pdf_link,
                    source="crossref",
                    doi=doi.lower(),
                    journal=journal_name,
                )
                if self.arxiv_pdf_fallback and not paper.pdf_link and self.arxiv_lookup_fn:
                    alt = self.arxiv_lookup_fn(paper.title)
                    if alt:
                        paper.pdf_link = alt
                        arxiv_hits += 1
                    time.sleep(max(0.0, self.request_delay_seconds))
                all_papers.append(paper)
                added += 1
            self._progress(f"Completed {journal}: +{added} papers")
            time.sleep(self.request_delay_seconds)

        if self.arxiv_pdf_fallback:
            self._progress(f"Crossref arXiv-PDF fallback attached PDFs for {arxiv_hits} papers")
        return all_papers
