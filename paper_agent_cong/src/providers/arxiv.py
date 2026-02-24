import datetime as dt
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from ..models import Paper
from .base import BaseProvider


def _strip_arxiv_version(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_title_for_match(text: str) -> str:
    return re.sub(r"\W+", "", text.lower())


def _parse_retry_after_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    raw = value.strip()
    if raw.isdigit():
        return float(raw)
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            import datetime as dt

            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        import datetime as dt

        delta = (parsed - dt.datetime.now(dt.timezone.utc)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


def _parse_arxiv_datetime(value: str) -> Optional[dt.datetime]:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _submission_window_bounds_utc(
    lookback_hours: int,
    align_to_submission_deadline: bool,
) -> tuple[dt.datetime, dt.datetime]:
    now_utc = dt.datetime.now(dt.timezone.utc)
    hours = max(1, int(lookback_hours))
    if not align_to_submission_deadline:
        return now_utc - dt.timedelta(hours=hours), now_utc

    now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
    cutoff_et = now_et.replace(hour=14, minute=0, second=0, microsecond=0)
    if now_et < cutoff_et:
        cutoff_et -= dt.timedelta(days=1)
    window_end_et = cutoff_et
    window_start_et = window_end_et - dt.timedelta(hours=hours)
    return (
        window_start_et.astimezone(dt.timezone.utc),
        window_end_et.astimezone(dt.timezone.utc),
    )


def find_arxiv_pdf_for_title(title: str, user_agent: str, retries: int = 3) -> Optional[str]:
    if not title.strip():
        return None
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    search_title = _normalize_ws(title)
    query = urllib.parse.urlencode(
        {
            "search_query": f'ti:"{search_title}"',
            "start": 0,
            "max_results": 5,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
    )
    url = f"https://export.arxiv.org/api/query?{query}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "application/atom+xml"},
    )
    raw = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(8.0 * attempt)
                continue
            return None
        except Exception:
            if attempt < retries:
                time.sleep(2.0 * attempt)
                continue
            return None
    if raw is None:
        return None
    try:
        root = ET.fromstring(raw)
    except Exception:
        return None

    wanted = _normalize_title_for_match(title)
    for entry in root.findall("atom:entry", ns):
        arxiv_title = _normalize_ws(entry.findtext("atom:title", default="", namespaces=ns))
        cand = _normalize_title_for_match(arxiv_title)
        if not cand:
            continue
        if cand == wanted or wanted in cand or cand in wanted:
            id_text = entry.findtext("atom:id", default="", namespaces=ns)
            if not id_text:
                continue
            arxiv_id = _strip_arxiv_version(id_text.rsplit("/", 1)[-1])
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    return None


class ArxivProvider(BaseProvider):
    def __init__(
        self,
        categories: List[str],
        per_category_max_results: int,
        retries: int = 5,
        request_delay_seconds: float = 4.0,
        user_agent: str = "paper-agent/1.0",
        lookback_hours: int = 24,
        align_to_submission_deadline: bool = True,
        progress_cb=None,
    ) -> None:
        self.categories = categories
        self.per_category_max_results = per_category_max_results
        self.retries = retries
        self.request_delay_seconds = request_delay_seconds
        self.user_agent = user_agent
        self.lookback_hours = max(1, int(lookback_hours))
        self.align_to_submission_deadline = bool(align_to_submission_deadline)
        self.progress_cb = progress_cb

    @property
    def name(self) -> str:
        return "arxiv"

    def _progress(self, msg: str) -> None:
        if self.progress_cb:
            self.progress_cb(msg)

    def fetch(self) -> List[Paper]:
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        all_by_id: Dict[str, Paper] = {}
        combined_query = "(" + " OR ".join(f"cat:{c}" for c in self.categories) + ")"
        total_target = self.per_category_max_results * len(self.categories)
        page_size = min(100, total_target)
        pages = (total_target + page_size - 1) // page_size
        window_start_utc, window_end_utc = _submission_window_bounds_utc(
            self.lookback_hours,
            self.align_to_submission_deadline,
        )

        self._progress(f"Fetch 1/1: arXiv combined query {combined_query}")
        self._progress(
            "arXiv submission window (UTC): "
            f"{window_start_utc.isoformat()} to {window_end_utc.isoformat()}"
        )

        for page_idx in range(pages):
            start = page_idx * page_size
            this_max = min(page_size, total_target - start)
            self._progress(f"arXiv page {page_idx + 1}/{pages}: start={start}, max_results={this_max}")

            raw = None
            for attempt in range(1, self.retries + 1):
                try:
                    query = urllib.parse.urlencode(
                        {
                            "search_query": combined_query,
                            "sortBy": "submittedDate",
                            "sortOrder": "descending",
                            "start": start,
                            "max_results": this_max,
                        }
                    )
                    url = f"https://export.arxiv.org/api/query?{query}"
                    req = urllib.request.Request(
                        url,
                        headers={
                            "User-Agent": self.user_agent,
                            "Accept": "application/atom+xml",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        raw = resp.read()
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 429 and attempt < self.retries:
                        retry_after = _parse_retry_after_seconds(e.headers.get("Retry-After"))
                        wait_secs = max(20.0 * attempt, retry_after or 0.0)
                        self._progress(
                            f"arXiv page {page_idx + 1} attempt {attempt}/{self.retries} got HTTP 429; "
                            f"backing off {wait_secs:.1f}s"
                        )
                        time.sleep(wait_secs)
                        continue
                    if attempt < self.retries:
                        wait_secs = min(30.0, 3.0 * attempt)
                        self._progress(
                            f"arXiv page {page_idx + 1} attempt {attempt}/{self.retries} failed "
                            f"(HTTP {e.code}); retrying in {wait_secs:.0f}s"
                        )
                        time.sleep(wait_secs)
                        continue
                except Exception as e:
                    if attempt < self.retries:
                        wait_secs = min(30.0, 3.0 * attempt)
                        self._progress(
                            f"arXiv page {page_idx + 1} attempt {attempt}/{self.retries} failed "
                            f"({type(e).__name__}); retrying in {wait_secs:.0f}s"
                        )
                        time.sleep(wait_secs)
                        continue

            if raw is None:
                continue

            before_count = len(all_by_id)
            root = ET.fromstring(raw)
            page_has_older_entries = False
            for entry in root.findall("atom:entry", ns):
                id_text = entry.findtext("atom:id", default="", namespaces=ns)
                if not id_text:
                    continue
                arxiv_id = _strip_arxiv_version(id_text.rsplit("/", 1)[-1])
                title = _normalize_ws(entry.findtext("atom:title", default="", namespaces=ns))
                abstract = _normalize_ws(entry.findtext("atom:summary", default="", namespaces=ns))
                published = entry.findtext("atom:published", default="", namespaces=ns)
                submitted_dt = _parse_arxiv_datetime(published)
                if submitted_dt is not None:
                    if submitted_dt < window_start_utc:
                        page_has_older_entries = True
                        continue
                    if submitted_dt > window_end_utc:
                        continue
                date = published[:10] if published else ""

                authors: List[str] = []
                for author in entry.findall("atom:author", ns):
                    name = _normalize_ws(author.findtext("atom:name", default="", namespaces=ns))
                    if name:
                        authors.append(name)

                link = id_text
                pdf_link = None
                for lnk in entry.findall("atom:link", ns):
                    rel = lnk.attrib.get("rel", "")
                    href = lnk.attrib.get("href", "")
                    typ = lnk.attrib.get("type", "")
                    title_attr = lnk.attrib.get("title", "")
                    if rel == "alternate" and href:
                        link = href
                    if title_attr == "pdf" or typ == "application/pdf":
                        pdf_link = href
                if not pdf_link:
                    pdf_link = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                all_by_id[arxiv_id] = Paper(
                    paper_id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    date=date,
                    link=link,
                    pdf_link=pdf_link,
                    source="arxiv",
                )
            fetched = len(all_by_id) - before_count
            self._progress(f"Completed page {page_idx + 1}: +{fetched} unique papers (total unique: {len(all_by_id)})")
            if page_has_older_entries:
                self._progress("Reached entries older than submission window; stopping pagination")
                break
            time.sleep(self.request_delay_seconds)

        return list(all_by_id.values())
