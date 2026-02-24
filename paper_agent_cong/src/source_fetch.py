import os
import re
from typing import Any, Callable, Dict, List, Optional, Type

from .models import Paper
from .providers import BaseProvider, find_arxiv_pdf_for_title


def find_arxiv_pdf_for_title_with_retries(
    title: str,
    user_agent: str,
    retries: int = 3,
) -> Optional[str]:
    return find_arxiv_pdf_for_title(title=title, user_agent=user_agent, retries=retries)


def fetch_arxiv_recent(
    categories: List[str],
    per_category_max_results: int,
    arxiv_provider_cls: Type[BaseProvider],
    progress_cb: Callable[[str], None],
    retries: int = 5,
    request_delay_seconds: float = 4.0,
    user_agent: str = "paper-agent/1.0",
    lookback_hours: int = 24,
    align_to_submission_deadline: bool = True,
) -> List[Paper]:
    provider = arxiv_provider_cls(
        categories=categories,
        per_category_max_results=per_category_max_results,
        retries=retries,
        request_delay_seconds=request_delay_seconds,
        user_agent=user_agent,
        lookback_hours=lookback_hours,
        align_to_submission_deadline=align_to_submission_deadline,
        progress_cb=progress_cb,
    )
    return provider.fetch()


def fetch_crossref_recent(
    journals: List[str],
    max_results_per_journal: int,
    from_days: int,
    crossref_provider_cls: Type[BaseProvider],
    progress_cb: Callable[[str], None],
    arxiv_pdf_lookup_fn: Callable[[str, str, int], Optional[str]],
    request_delay_seconds: float = 1.0,
    user_agent: str = "paper-agent/1.0",
    arxiv_pdf_fallback: int = 1,
) -> List[Paper]:
    env_fallback = os.getenv("CROSSREF_ARXIV_PDF_FALLBACK", "").strip()
    fallback_raw = env_fallback if env_fallback else str(arxiv_pdf_fallback)
    enable_arxiv_fallback = fallback_raw.lower() not in {"0", "false", "no"}
    provider = crossref_provider_cls(
        journals=journals,
        max_results_per_journal=max_results_per_journal,
        from_days=from_days,
        request_delay_seconds=request_delay_seconds,
        user_agent=user_agent,
        arxiv_pdf_fallback=enable_arxiv_fallback,
        arxiv_lookup_fn=(lambda title: arxiv_pdf_lookup_fn(title, user_agent, 3))
        if enable_arxiv_fallback
        else None,
        progress_cb=progress_cb,
    )
    return provider.fetch()


def paper_dedupe_key(p: Paper) -> str:
    if p.doi:
        return f"doi:{p.doi.lower()}"
    if p.source == "arxiv":
        return f"arxiv:{p.paper_id.lower()}"
    title_key = re.sub(r"\W+", "", p.title.lower())
    return f"title:{title_key}"


def fetch_all_sources(
    arxiv_cfg: Dict[str, Any],
    crossref_cfg: Dict[str, Any],
    arxiv_provider_cls: Type[BaseProvider],
    crossref_provider_cls: Type[BaseProvider],
    progress_cb: Callable[[str], None],
    arxiv_pdf_lookup_fn: Callable[[str, str, int], Optional[str]],
) -> List[Paper]:
    providers: List[BaseProvider] = []

    if arxiv_cfg.get("enabled", True):
        providers.append(
            arxiv_provider_cls(
                categories=arxiv_cfg["categories"],
                per_category_max_results=arxiv_cfg["per_category_max_results"],
                retries=arxiv_cfg["retries"],
                request_delay_seconds=arxiv_cfg["request_delay_seconds"],
                user_agent=arxiv_cfg["user_agent"],
                lookback_hours=int(arxiv_cfg.get("lookback_hours", 24)),
                align_to_submission_deadline=bool(
                    arxiv_cfg.get("align_to_submission_deadline", True)
                ),
                progress_cb=progress_cb,
            )
        )

    if crossref_cfg.get("enabled", False):
        env_fallback = os.getenv("CROSSREF_ARXIV_PDF_FALLBACK", "").strip()
        fallback_raw = env_fallback if env_fallback else str(crossref_cfg["arxiv_pdf_fallback"])
        enable_arxiv_fallback = fallback_raw.lower() not in {"0", "false", "no"}
        providers.append(
            crossref_provider_cls(
                journals=crossref_cfg["journals"],
                max_results_per_journal=crossref_cfg["max_results_per_journal"],
                from_days=crossref_cfg["from_days"],
                request_delay_seconds=crossref_cfg["request_delay_seconds"],
                user_agent=crossref_cfg["user_agent"],
                arxiv_pdf_fallback=enable_arxiv_fallback,
                arxiv_lookup_fn=(
                    lambda title: arxiv_pdf_lookup_fn(title, arxiv_cfg["user_agent"], 3)
                )
                if enable_arxiv_fallback
                else None,
                progress_cb=progress_cb,
            )
        )

    papers: List[Paper] = []
    for provider in providers:
        papers.extend(provider.fetch())

    deduped: Dict[str, Paper] = {}
    for p in papers:
        key = paper_dedupe_key(p)
        if key not in deduped:
            deduped[key] = p
    return list(deduped.values())
