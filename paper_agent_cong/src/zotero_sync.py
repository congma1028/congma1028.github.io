import datetime as dt
import os
from typing import Any, Dict, List, Optional, Tuple

from .models import Paper

try:
    from pyzotero import zotero  # type: ignore
except Exception:  # pragma: no cover
    zotero = None


def is_enabled() -> bool:
    return os.getenv("ZOTERO_SYNC_ENABLED", "1").strip().lower() not in {"0", "false", "no"}


def build_client() -> Optional[Any]:
    if zotero is None:
        return None
    if not is_enabled():
        return None
    library_id = os.getenv("ZOTERO_LIBRARY_ID", "").strip()
    library_type = os.getenv("ZOTERO_LIBRARY_TYPE", "user").strip() or "user"
    api_key = os.getenv("ZOTERO_API_KEY", "").strip()
    if not library_id:
        return None
    return zotero.Zotero(library_id, library_type, api_key or None)


def doi_in_zotero(client: Any, doi: str) -> bool:
    doi_norm = (doi or "").strip().lower()
    if not doi_norm:
        return False
    try:
        items = client.items(q=doi_norm)
    except Exception:
        return False
    for item in items or []:
        data = item.get("data", {}) if isinstance(item, dict) else {}
        item_doi = str(data.get("DOI", "")).strip().lower()
        if item_doi == doi_norm:
            return True
    return False


def filter_existing_doi_items(client: Any, papers: List[Paper]) -> Tuple[List[Paper], int]:
    if client is None:
        return papers, 0
    kept: List[Paper] = []
    skipped = 0
    for p in papers:
        if p.doi and doi_in_zotero(client, p.doi):
            skipped += 1
            continue
        kept.append(p)
    return kept, skipped


def _paper_to_zotero_item(
    paper: Paper, score: int, tags: List[str], reasons: List[str]
) -> Dict[str, Any]:
    creators = []
    for name in paper.authors:
        bits = [x for x in name.strip().split(" ") if x]
        if not bits:
            continue
        if len(bits) == 1:
            creators.append({"creatorType": "author", "name": bits[0]})
        else:
            creators.append(
                {
                    "creatorType": "author",
                    "firstName": " ".join(bits[:-1]),
                    "lastName": bits[-1],
                }
            )
    note_lines = [f"Score: {score}"]
    if reasons:
        note_lines.append("Reasons:")
        for r in reasons[:3]:
            note_lines.append(f"- {r}")
    is_preprint = paper.source == "arxiv"
    item = {
        "itemType": "preprint" if is_preprint else "journalArticle",
        "title": paper.title,
        "creators": creators,
        "abstractNote": paper.abstract or "",
        "date": paper.date or "",
        "url": paper.link,
        "DOI": paper.doi or "",
        "extra": "\n".join(note_lines),
        "tags": [{"tag": t} for t in (tags or [])[:6]],
        "accessDate": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
    }
    if is_preprint:
        # Zotero preprint does not accept publicationTitle.
        item["archive"] = paper.journal or "arXiv"
        if paper.paper_id:
            item["archiveLocation"] = paper.paper_id
    else:
        item["publicationTitle"] = paper.journal or ""
    return item


def push_to_zotero(
    client: Any,
    paper: Paper,
    score: int,
    tags: List[str],
    reasons: List[str],
) -> Tuple[bool, Optional[str], Optional[str]]:
    if client is None:
        return False, None, "Zotero client not configured"
    payload = _paper_to_zotero_item(paper, score, tags, reasons)
    try:
        out = client.create_items([payload])
    except Exception as e:
        return False, None, f"create_items failed: {type(e).__name__}: {e}"

    success = out.get("successful", {}) if isinstance(out, dict) else {}
    if not success:
        failed = out.get("failed", {}) if isinstance(out, dict) else {}
        if isinstance(failed, dict) and failed:
            first_failed = next(iter(failed.values()))
            if isinstance(first_failed, dict):
                code = first_failed.get("code")
                msg = first_failed.get("message")
                return False, None, f"create_items failed ({code}): {msg}"
        return False, None, f"create_items response missing success: {out}"
    first = next(iter(success.values()))
    key = first.get("key") if isinstance(first, dict) else None
    if not key:
        return True, None, None

    library_id = os.getenv("ZOTERO_LIBRARY_ID", "").strip()
    library_type = os.getenv("ZOTERO_LIBRARY_TYPE", "user").strip() or "user"
    if library_id:
        lib_path = "groups" if library_type == "group" else "users"
        url = f"https://www.zotero.org/{lib_path}/{library_id}/items/{key}"
        return True, url, None
    return True, None, None
