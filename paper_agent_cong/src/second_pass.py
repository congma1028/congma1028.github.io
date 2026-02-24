import concurrent.futures
import datetime as dt
import hashlib
import json
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List

from .models import Paper


def second_pass_prompt_for_paper(
    paper: Paper, interests_text: str, paper_text: str
) -> str:
    return textwrap.dedent(
        f"""
        You generate digest notes for a research paper.
        Output JSON only, no markdown, no code fences, no extra text.

        Research interests:
        {interests_text}

        Paper title: {paper.title}
        Paper abstract: {paper.abstract}

        Full paper text (appendix removed):
        {paper_text}

        Return a JSON object with fields:
        - summary: 2-3 sentence concise summary grounded in the paper
        - reasons: array of 1-3 short bullets for why this paper is relevant
        - tags: array of 3-6 keyword strings
        """
    ).strip()


def second_pass_enrich_papers(
    ranked: List[Dict[str, Any]],
    interests_text: str,
    date_str: str,
    provider: str,
    model: str,
    user_agent: str,
    llm_report_cache_path: Path,
    log_dir: Path,
    report_usage_log_path: Path,
    load_json_map_fn: Callable[[Path], Dict[str, Any]],
    save_json_map_fn: Callable[[Path, Dict[str, Any]], None],
    download_pdf_bytes_fn: Callable[[str, str], bytes],
    extract_main_text_from_pdf_fn: Callable[[bytes], str],
    second_pass_prompt_fn: Callable[[Paper, str, str], str],
    call_llm_json_prompt_fn: Callable[[str, str, str, float], Dict[str, Any]],
    normalize_usage_fn: Callable[[Dict[str, Any]], Dict[str, int]],
    append_llm_error_log_fn: Callable[[str, str, str, str, str], None],
    progress_cb: Callable[[str], None],
    second_pass_limit: int,
    report_workers: int,
    second_pass_temperature: float,
) -> List[Dict[str, Any]]:
    if not ranked:
        return ranked

    if int(second_pass_limit) <= 0:
        target = ranked
    else:
        target = ranked[: int(second_pass_limit)]

    report_cache = load_json_map_fn(llm_report_cache_path)
    interests_hash = hashlib.sha256(interests_text.encode("utf-8")).hexdigest()[:16]
    usage_entries: List[Dict[str, Any]] = []
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    report_workers = max(1, int(report_workers))

    progress_cb(
        f"Second pass on {len(target)}/{len(ranked)} papers using full text (excluding appendix), "
        f"provider={provider}, model={model}, concurrency={report_workers}"
    )

    def _enrich_one(item: Dict[str, Any]) -> Dict[str, Any]:
        paper: Paper = item["paper"]
        cache_key = paper.paper_id
        cached = report_cache.get(cache_key)
        if isinstance(cached, dict) and cached.get("interests_hash") == interests_hash:
            report = cached.get("report", {})
            return {"item": item, "report": report, "cached": True, "error": ""}
        try:
            pdf_url = paper.pdf_link or f"https://arxiv.org/pdf/{paper.paper_id}.pdf"
            pdf_bytes = download_pdf_bytes_fn(pdf_url, user_agent)
            paper_text = extract_main_text_from_pdf_fn(pdf_bytes)
            if not paper_text:
                return {
                    "item": item,
                    "report": {},
                    "cached": False,
                    "error": "empty extracted paper text",
                }
            prompt = second_pass_prompt_fn(paper, interests_text, paper_text)
            out = call_llm_json_prompt_fn(
                prompt,
                provider,
                model,
                temperature=second_pass_temperature,
            )
            error_text = str(out.get("_error", "")).strip()
            if error_text:
                return {
                    "item": item,
                    "report": out,
                    "cached": False,
                    "error": error_text,
                }
            report = {
                "summary": str(out.get("summary", "")).strip(),
                "reasons": out.get("reasons", [])
                if isinstance(out.get("reasons", []), list)
                else [],
                "tags": out.get("tags", [])
                if isinstance(out.get("tags", []), list)
                else [],
                "usage": normalize_usage_fn(out),
            }
            report["reasons"] = report["reasons"][:3]
            report["tags"] = report["tags"][:6]
            report_cache[cache_key] = {
                "paper_id": paper.paper_id,
                "interests_hash": interests_hash,
                "updated_at": dt.datetime.now(dt.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "report": report,
            }
            return {"item": item, "report": report, "cached": False, "error": ""}
        except Exception as e:
            return {
                "item": item,
                "report": {},
                "cached": False,
                "error": f"{type(e).__name__}: {e}",
            }

    enriched_by_id: Dict[str, Dict[str, Any]] = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=report_workers) as executor:
        futures = [executor.submit(_enrich_one, item) for item in target]
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            item = res["item"]
            report = res["report"]
            error_text = str(res["error"]).strip()
            if error_text:
                append_llm_error_log_fn(
                    date_str,
                    item["paper"].paper_id,
                    provider,
                    model,
                    f"second_pass: {error_text}",
                )
            else:
                if isinstance(report.get("summary"), str) and report.get("summary"):
                    item["eval"]["summary"] = report["summary"]
                if isinstance(report.get("reasons"), list) and report.get("reasons"):
                    item["eval"]["reasons"] = report["reasons"][:3]
                if isinstance(report.get("tags"), list) and report.get("tags"):
                    item["eval"]["tags"] = report["tags"][:6]

            usage = normalize_usage_fn(report if isinstance(report, dict) else {})
            usage_totals["input_tokens"] += usage["input_tokens"]
            usage_totals["output_tokens"] += usage["output_tokens"]
            usage_totals["total_tokens"] += usage["total_tokens"]
            usage_entries.append(
                {
                    "paper_id": item["paper"].paper_id,
                    "cached": bool(res["cached"]),
                    "error": error_text if error_text else None,
                    "usage": usage,
                }
            )
            enriched_by_id[item["paper"].paper_id] = item
            done += 1
            if done == len(target) or done % 5 == 0:
                progress_cb(f"Second-pass progress: {done}/{len(target)}")

    save_json_map_fn(llm_report_cache_path, report_cache)
    report_usage_log = {
        "date": date_str,
        "provider": provider,
        "model": model,
        "papers_second_pass": len(ranked),
        "totals": usage_totals,
        "entries": usage_entries,
    }
    report_usage_log_path.write_text(
        json.dumps(report_usage_log, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return [enriched_by_id.get(item["paper"].paper_id, item) for item in target]
