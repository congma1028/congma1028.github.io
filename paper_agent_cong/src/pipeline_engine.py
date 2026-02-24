import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config_sources
from . import digest as digest_mod
from . import first_pass
from . import llm_client
from . import pdf_processing
from . import second_pass
from . import source_fetch
from . import zotero_sync
from .core import database as db
from .models import Paper
from .providers import ArxivProvider, CrossrefProvider


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DIGEST_DIR = ROOT / "digests"
BUILD_DIR = ROOT / "build"
LOG_DIR = ROOT / "logs"
LLM_REPORT_CACHE_PATH = LOG_DIR / "llm_report_cache.json"
DB_PATH = ROOT / "data" / "paper_agent.db"


class ConfigError(RuntimeError):
    pass


def _progress(message: str) -> None:
    ts = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def ensure_dirs() -> None:
    for path in [DIGEST_DIR, BUILD_DIR, LOG_DIR, DB_PATH.parent]:
        path.mkdir(parents=True, exist_ok=True)
    db.init_db(DB_PATH)


def load_yaml(path: Path) -> Dict[str, Any]:
    return config_sources.load_yaml(path, error_cls=ConfigError)


def load_interests() -> str:
    return config_sources.load_interests(CONFIG_DIR, error_cls=ConfigError)


def load_arxiv_source_config() -> Dict[str, Any]:
    return config_sources.load_arxiv_source_config(CONFIG_DIR, error_cls=ConfigError)


def load_crossref_source_config() -> Dict[str, Any]:
    return config_sources.load_crossref_source_config(CONFIG_DIR, error_cls=ConfigError)


def load_interest_exclusions() -> List[str]:
    return config_sources.load_interest_exclusions(CONFIG_DIR, error_cls=ConfigError)


def load_runtime_config() -> Dict[str, Any]:
    return config_sources.load_runtime_config(CONFIG_DIR, error_cls=ConfigError)


def _find_arxiv_pdf_for_title(title: str, user_agent: str, retries: int = 3) -> Optional[str]:
    return source_fetch.find_arxiv_pdf_for_title_with_retries(title, user_agent, retries)


def fetch_arxiv_recent(
    categories: List[str],
    per_category_max_results: int,
    retries: int = 5,
    request_delay_seconds: float = 4.0,
    user_agent: str = "paper-agent/1.0",
    lookback_hours: int = 24,
    align_to_submission_deadline: bool = True,
) -> List[Paper]:
    return source_fetch.fetch_arxiv_recent(
        categories=categories,
        per_category_max_results=per_category_max_results,
        retries=retries,
        request_delay_seconds=request_delay_seconds,
        user_agent=user_agent,
        lookback_hours=lookback_hours,
        align_to_submission_deadline=align_to_submission_deadline,
        arxiv_provider_cls=ArxivProvider,
        progress_cb=_progress,
    )


def fetch_crossref_recent(
    journals: List[str],
    max_results_per_journal: int,
    from_days: int,
    request_delay_seconds: float = 1.0,
    user_agent: str = "paper-agent/1.0",
    arxiv_pdf_fallback: int = 1,
) -> List[Paper]:
    return source_fetch.fetch_crossref_recent(
        journals=journals,
        max_results_per_journal=max_results_per_journal,
        from_days=from_days,
        request_delay_seconds=request_delay_seconds,
        user_agent=user_agent,
        arxiv_pdf_fallback=arxiv_pdf_fallback,
        crossref_provider_cls=CrossrefProvider,
        progress_cb=_progress,
        arxiv_pdf_lookup_fn=_find_arxiv_pdf_for_title,
    )


def _paper_dedupe_key(p: Paper) -> str:
    return source_fetch.paper_dedupe_key(p)


def fetch_all_sources(arxiv_cfg: Dict[str, Any], crossref_cfg: Dict[str, Any]) -> List[Paper]:
    return source_fetch.fetch_all_sources(
        arxiv_cfg=arxiv_cfg,
        crossref_cfg=crossref_cfg,
        arxiv_provider_cls=ArxivProvider,
        crossref_provider_cls=CrossrefProvider,
        progress_cb=_progress,
        arxiv_pdf_lookup_fn=_find_arxiv_pdf_for_title,
    )


def download_pdfs_for_papers(papers: List[Paper], date_str: str, user_agent: str) -> Dict[str, int]:
    return pdf_processing.download_pdfs_for_papers(
        papers=papers,
        date_str=date_str,
        user_agent=user_agent,
        build_dir=BUILD_DIR,
        arxiv_pdf_lookup=_find_arxiv_pdf_for_title,
        progress_cb=_progress,
    )


def _tokenize_for_match(text: str) -> List[str]:
    return first_pass.tokenize_for_match(text)


def prefilter_papers_for_eval(
    papers: List[Paper], interests_text: str, candidate_limit: int
) -> List[Paper]:
    return first_pass.prefilter_papers_for_eval(papers, interests_text, candidate_limit)


def load_cache(interests_hash: str) -> Dict[str, Any]:
    return db.get_eval_cache(interests_hash=interests_hash, db_path=DB_PATH)


def save_cache(data: Dict[str, Any], interests_hash: str) -> None:
    db.upsert_eval_cache_entries(data, interests_hash=interests_hash, db_path=DB_PATH)


def _load_json_map(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_json_map(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clear_run_logs() -> None:
    patterns = [
        "first_pass_token_usage_*.json",
        "second_pass_token_usage_*.json",
        "llm_api_errors_*.log",
        "fetched_papers_with_abstracts_*.json",
        # Legacy log names kept for cleanup compatibility.
        "llm_usage_*.json",
        "llm_report_usage_*.json",
        "llm_errors_*.log",
        "gemini_usage_*.json",
        "gemini_errors_*.log",
        "gpt_usage_*.json",
        "gpt_errors_*.log",
    ]
    removed = 0
    for pattern in patterns:
        for path in LOG_DIR.glob(pattern):
            try:
                path.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        _progress(f"Cleared {removed} previous log file(s) in {LOG_DIR}")


def clear_eval_caches(clear_db_cache_on_run: bool = False) -> None:
    if clear_db_cache_on_run:
        try:
            if DB_PATH.exists():
                DB_PATH.unlink()
                _progress(f"Cleared SQLite cache DB at {DB_PATH}")
            db.init_db(DB_PATH)
        except Exception:
            pass

    removed = 0
    if LLM_REPORT_CACHE_PATH.exists():
        try:
            LLM_REPORT_CACHE_PATH.unlink()
            removed += 1
        except Exception:
            pass
    if removed:
        _progress(f"Cleared {removed} evaluation cache file(s) in {LOG_DIR}")


def _eval_prompt_for_paper(paper: Paper, interests_text: str) -> str:
    return first_pass.eval_prompt_for_paper(paper, interests_text)


def resolve_llm_provider_model() -> tuple[str, str]:
    try:
        return llm_client.resolve_llm_provider_model()
    except Exception as e:
        raise ConfigError(str(e)) from None


def preflight_llm_credentials_and_model(provider: str, model: str) -> None:
    try:
        llm_client.preflight_llm_credentials_and_model(provider, model)
    except Exception as e:
        raise ConfigError(str(e)) from None


def call_llm_eval(
    paper: Paper,
    interests_text: str,
    provider: str,
    model: str,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    prompt = _eval_prompt_for_paper(paper, interests_text)
    return llm_client.call_llm_eval(paper, prompt, provider, model, temperature)


def call_llm_json_prompt(
    prompt: str,
    provider: str,
    model: str,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    return llm_client.call_llm_json_prompt(prompt, provider, model, temperature)


def _normalize_usage(eval_data: Dict[str, Any]) -> Dict[str, int]:
    return llm_client.normalize_usage(eval_data)


def _append_llm_error_log(date_str: str, paper_id: str, provider: str, model: str, error: str) -> None:
    log_path = LOG_DIR / f"llm_api_errors_{date_str}.log"
    ts = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{ts} provider={provider} model={model} paper_id={paper_id} error={error}\n")


def _write_fetched_papers_log(date_str: str, papers: List[Paper]) -> Path:
    out_path = LOG_DIR / f"fetched_papers_with_abstracts_{date_str}.json"
    payload = {
        "date": date_str,
        "count": len(papers),
        "papers": [
            {
                "paper_id": p.paper_id,
                "source": p.source,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "date": p.date,
                "link": p.link,
                "pdf_link": p.pdf_link,
                "doi": p.doi,
                "journal": p.journal,
            }
            for p in papers
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def _apply_topic_exclusions(
    papers: List[Paper],
    exclude_topics: List[str],
) -> tuple[List[Paper], int]:
    tokens = [t.lower() for t in exclude_topics if t.strip()]
    if not tokens:
        return papers, 0
    kept: List[Paper] = []
    skipped = 0
    for p in papers:
        hay = f"{p.title} {p.abstract}".lower()
        if any(tok in hay for tok in tokens):
            skipped += 1
            continue
        kept.append(p)
    return kept, skipped


def evaluate_papers(
    papers: List[Paper],
    interests_text: str,
    date_str: str,
    provider: str,
    model: str,
    runtime_cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    cfg = runtime_cfg or load_runtime_config()
    usage_log, results = first_pass.evaluate_papers(
        papers=papers,
        interests_text=interests_text,
        date_str=date_str,
        provider=provider,
        model=model,
        load_cache_fn=load_cache,
        save_cache_fn=save_cache,
        call_llm_eval_fn=call_llm_eval,
        normalize_usage_fn=_normalize_usage,
        append_llm_error_log_fn=_append_llm_error_log,
        progress_cb=_progress,
        eval_workers=int(cfg["llm_max_concurrency"]),
        first_pass_limit=int(cfg["first_pass_limit"]),
        first_pass_temperature=float(cfg["first_pass_temperature"]),
    )
    usage_path = LOG_DIR / f"first_pass_token_usage_{date_str}.json"
    included = first_pass.sort_included_results(usage_log, results, str(usage_path))
    _progress(f"Evaluation complete: included {len(included)} papers")
    return included


def _download_pdf_bytes(url: str, user_agent: str) -> bytes:
    return pdf_processing.download_pdf_bytes(url, user_agent)


def _extract_main_text_from_pdf(pdf_bytes: bytes) -> str:
    return pdf_processing.extract_main_text_from_pdf(pdf_bytes, progress_cb=_progress)


def _second_pass_prompt_for_paper(paper: Paper, interests_text: str, paper_text: str) -> str:
    return second_pass.second_pass_prompt_for_paper(paper, interests_text, paper_text)


def second_pass_enrich_papers(
    ranked: List[Dict[str, Any]],
    interests_text: str,
    date_str: str,
    provider: str,
    model: str,
    user_agent: str,
    runtime_cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    cfg = runtime_cfg or load_runtime_config()
    return second_pass.second_pass_enrich_papers(
        ranked=ranked,
        interests_text=interests_text,
        date_str=date_str,
        provider=provider,
        model=model,
        user_agent=user_agent,
        llm_report_cache_path=LLM_REPORT_CACHE_PATH,
        log_dir=LOG_DIR,
        report_usage_log_path=(LOG_DIR / f"second_pass_token_usage_{date_str}.json"),
        load_json_map_fn=_load_json_map,
        save_json_map_fn=_save_json_map,
        download_pdf_bytes_fn=_download_pdf_bytes,
        extract_main_text_from_pdf_fn=_extract_main_text_from_pdf,
        second_pass_prompt_fn=_second_pass_prompt_for_paper,
        call_llm_json_prompt_fn=call_llm_json_prompt,
        normalize_usage_fn=_normalize_usage,
        append_llm_error_log_fn=_append_llm_error_log,
        progress_cb=_progress,
        second_pass_limit=int(cfg["second_pass_limit"]),
        report_workers=int(cfg["report_max_concurrency"]),
        second_pass_temperature=float(cfg["second_pass_temperature"]),
    )


def latex_escape(text: str) -> str:
    return digest_mod.latex_escape(text)


def render_tex(date_str: str, ranked: List[Dict[str, Any]]) -> str:
    return digest_mod.render_tex(date_str, ranked)


def write_digest_tex(date_str: str, content: str) -> Path:
    return digest_mod.write_digest_tex(date_str, content, DIGEST_DIR)


def compile_pdf(date_str: str, tex_path: Path) -> Path:
    return digest_mod.compile_pdf(date_str, tex_path, DIGEST_DIR, BUILD_DIR, progress_cb=_progress)


def run_pipeline(force: bool = False) -> int:
    ensure_dirs()
    date_str = dt.date.today().isoformat()
    existing_pdf = DIGEST_DIR / f"{date_str}.pdf"
    if existing_pdf.exists() and not force:
        _progress(f"Skipping run: digest already exists for today at {existing_pdf}")
        print(f"Already generated today: {existing_pdf}")
        print("Use 'python -m src.papers run --force' to rerun.")
        return 0

    provider, model = resolve_llm_provider_model()
    _progress(f"Preflight: validating {provider} model '{model}' and API key")
    preflight_llm_credentials_and_model(provider, model)
    _progress("Preflight passed")

    clear_run_logs()
    runtime_cfg = load_runtime_config()
    clear_eval_caches(clear_db_cache_on_run=bool(runtime_cfg["clear_db_cache_on_run"]))
    llm_client.configure_retry_max_attempts(int(runtime_cfg["llm_retry_max_attempts"]))
    interests_text = load_interests()
    arxiv_cfg = load_arxiv_source_config()
    crossref_cfg = load_crossref_source_config()

    _progress("Step 1/5: Fetching papers from enabled sources")
    papers = fetch_all_sources(arxiv_cfg=arxiv_cfg, crossref_cfg=crossref_cfg)
    fetched_log_path = _write_fetched_papers_log(date_str, papers)
    _progress(f"Wrote fetched-papers log: {fetched_log_path}")
    db.upsert_papers(papers, db_path=DB_PATH)
    if not papers:
        _progress("No papers fetched from enabled sources")
        return 0

    zot_client = zotero_sync.build_client()
    if zot_client is None:
        _progress("Zotero client not configured; skipping Zotero DOI pre-filter and sync")
    else:
        papers, skipped_zot = zotero_sync.filter_existing_doi_items(zot_client, papers)
        if skipped_zot:
            _progress(f"Skipped {skipped_zot} papers already present in Zotero by DOI")
        if not papers:
            _progress("No new papers to process after Zotero DOI filtering")
            return 0
    exclude_topics = list(runtime_cfg.get("exclude_topics", [])) + load_interest_exclusions()
    # Preserve order while deduplicating.
    dedup_exclusions = list(dict.fromkeys([x for x in exclude_topics if str(x).strip()]))
    papers, excluded_topic_count = _apply_topic_exclusions(
        papers,
        exclude_topics=dedup_exclusions,
    )
    if excluded_topic_count:
        _progress(f"Excluded {excluded_topic_count} papers by configured topic exclusions")
    if not papers:
        _progress("No papers left after topic exclusions")
        return 0

    _progress("Step 2/5: First-pass filtering and ranking (title + abstract)")
    _progress(
        "Limits: "
        f"FIRST_PASS_LIMIT={runtime_cfg['first_pass_limit']}, "
        f"SECOND_PASS_LIMIT={runtime_cfg['second_pass_limit']}"
    )
    ranked = evaluate_papers(
        papers,
        interests_text,
        date_str,
        provider,
        model,
        runtime_cfg=runtime_cfg,
    )
    ranked_ids = [item["paper"].paper_id for item in ranked]
    db.set_paper_status(ranked_ids, "shortlisted", db_path=DB_PATH)
    ranked_id_set = set(ranked_ids)
    rejected_ids = [p.paper_id for p in papers if p.paper_id not in ranked_id_set]
    db.set_paper_status(rejected_ids, "rejected", db_path=DB_PATH)

    _progress("Step 3/5: Second-pass report generation (full paper text, no appendix)")
    ranked = second_pass_enrich_papers(
        ranked=ranked,
        interests_text=interests_text,
        date_str=date_str,
        provider=provider,
        model=model,
        user_agent=arxiv_cfg["user_agent"],
        runtime_cfg=runtime_cfg,
    )

    zotero_score_threshold = int(runtime_cfg["zotero_sync_score_threshold"])
    zotero_synced = 0
    if zot_client is not None:
        _progress(
            f"Syncing high-score papers to Zotero (score > {zotero_score_threshold})"
        )
        for item in ranked:
            ev = item.get("eval", {})
            score = int(ev.get("score", 0) or 0)
            if score <= zotero_score_threshold:
                item["zotero_synced"] = False
                continue
            p = item.get("paper")
            if not isinstance(p, Paper):
                item["zotero_synced"] = False
                continue
            ok, zot_url, err = zotero_sync.push_to_zotero(
                zot_client,
                p,
                score=score,
                tags=ev.get("tags", []) if isinstance(ev.get("tags", []), list) else [],
                reasons=ev.get("reasons", []) if isinstance(ev.get("reasons", []), list) else [],
            )
            item["zotero_synced"] = bool(ok)
            item["zotero_url"] = zot_url
            if ok:
                zotero_synced += 1
            elif err:
                _append_llm_error_log(date_str, p.paper_id, provider, model, f"zotero_sync: {err}")
    else:
        for item in ranked:
            item["zotero_synced"] = False

    _progress("Step 4/5: Rendering LaTeX digest")
    tex_content = render_tex(date_str, ranked)
    tex_path = write_digest_tex(date_str, tex_content)
    _progress("Step 5/5: Compiling PDF digest")
    pdf_path = compile_pdf(date_str, tex_path)
    db.set_paper_status([item["paper"].paper_id for item in ranked], "digested", db_path=DB_PATH)

    print(f"Fetched papers: {len(papers)}")
    print(f"Included top papers: {len(ranked)}")
    print(f"Synced to Zotero (score>{zotero_score_threshold}): {zotero_synced}")
    print(f"Wrote TeX: {tex_path}")
    print(f"Wrote PDF: {pdf_path}")
    print(f"Wrote fetched papers log: {LOG_DIR / f'fetched_papers_with_abstracts_{date_str}.json'}")
    print(f"Wrote first-pass token log: {LOG_DIR / f'first_pass_token_usage_{date_str}.json'}")
    print(f"Wrote second-pass token log: {LOG_DIR / f'second_pass_token_usage_{date_str}.json'}")
    print(f"Wrote LLM API error log: {LOG_DIR / f'llm_api_errors_{date_str}.log'}")
    print(f"SQLite DB: {DB_PATH}")
    return 0


def run_fetch_stage_download_pdfs(force: bool = False) -> int:
    ensure_dirs()
    date_str = dt.date.today().isoformat()
    out_dir = BUILD_DIR / date_str / "pdfs"
    if out_dir.exists() and not force:
        _progress(f"Skipping fetch-pdfs: output already exists at {out_dir}")
        print(f"Already downloaded today: {out_dir}")
        print("Use 'python -m src.papers fetch-pdfs --force' to rerun.")
        return 0

    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)

    arxiv_cfg = load_arxiv_source_config()
    crossref_cfg = load_crossref_source_config()
    _progress("Stage-1 test: fetching papers only (no LLM calls)")
    papers = fetch_all_sources(arxiv_cfg=arxiv_cfg, crossref_cfg=crossref_cfg)
    _progress(f"Fetched {len(papers)} papers across enabled sources")
    fetched_log_path = _write_fetched_papers_log(date_str, papers)
    _progress(f"Wrote fetched-papers log: {fetched_log_path}")
    stats = download_pdfs_for_papers(papers=papers, date_str=date_str, user_agent=arxiv_cfg["user_agent"])

    print(f"Fetched papers: {len(papers)}")
    print(f"Wrote fetched papers log: {fetched_log_path}")
    print(f"Downloaded PDFs: {stats['downloaded']}")
    print(f"Recovered via arXiv fallback: {stats['arxiv_retry_hits']}")
    print(f"Skipped (no PDF link): {stats['skipped']}")
    print(f"Failed downloads: {stats['failed']}")
    print(f"PDF output dir: {stats['output_dir']}")
    return 0


def run_zotero_test(doi: str, push: bool = False) -> int:
    from . import pipeline_cli

    return pipeline_cli.run_zotero_test(doi=doi, push=push)


def build_parser():
    from . import pipeline_cli

    return pipeline_cli.build_parser()


def main(argv: Optional[List[str]] = None) -> int:
    from . import pipeline_cli

    return pipeline_cli.main(argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
