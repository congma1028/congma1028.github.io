import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import textwrap
from typing import Any, Callable, Dict, List

from .models import Paper


def tokenize_for_match(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def prefilter_papers_for_eval(
    papers: List[Paper], interests_text: str, candidate_limit: int
) -> List[Paper]:
    if candidate_limit <= 0 or len(papers) <= candidate_limit:
        return papers

    interest_terms = {
        tok for tok in tokenize_for_match(interests_text) if len(tok) >= 4
    }
    scored: List[tuple[int, Paper]] = []
    for paper in papers:
        text = f"{paper.title} {paper.abstract}"
        paper_terms = set(tokenize_for_match(text))
        overlap = len(interest_terms & paper_terms)
        scored.append((overlap, paper))

    # Keep strongest lexical matches first. Stable sort keeps recent ordering ties.
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:candidate_limit]]


def heuristic_eval() -> Dict[str, Any]:
    return {
        "include": False,
        "score": 0,
        "confidence": "low",
        "reasons": ["LLM evaluation unavailable"],
        "tags": [],
        "summary": "Evaluation unavailable because LLM call failed.",
    }


def eval_prompt_for_paper(paper: Paper, interests_text: str) -> str:
    return textwrap.dedent(
        f"""
        You evaluate research-paper relevance.
        Output JSON only, no markdown, no code fences, no extra text.

        Research interests:
        {interests_text}

        Evaluate this paper using only title and abstract.

        Paper title: {paper.title}
        Paper abstract: {paper.abstract}

        Return a JSON object with fields:
        - include: boolean
        - score: integer 0-100
        - confidence: one of [low, medium, high]
        - reasons: array of 1-3 short bullet strings
        - tags: array of 3-6 keyword strings
        - summary: 2-3 sentence concise summary
        """
    ).strip()


def evaluate_papers(
    papers: List[Paper],
    interests_text: str,
    date_str: str,
    provider: str,
    model: str,
    load_cache_fn: Callable[[str], Dict[str, Any]],
    save_cache_fn: Callable[[Dict[str, Any], str], None],
    call_llm_eval_fn: Callable[[Paper, str, str, str, float], Dict[str, Any]],
    normalize_usage_fn: Callable[[Dict[str, Any]], Dict[str, int]],
    append_llm_error_log_fn: Callable[[str, str, str, str, str], None],
    progress_cb: Callable[[str], None],
    eval_workers: int,
    first_pass_limit: int,
    first_pass_temperature: float,
) -> List[Dict[str, Any]]:
    eval_workers = max(1, int(eval_workers))

    interests_hash = hashlib.sha256(interests_text.encode("utf-8")).hexdigest()[:16]
    cache = load_cache_fn(interests_hash)
    usage_entries: List[Dict[str, Any]] = []
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    cache_hits = 0
    api_calls = 0
    eval_papers = prefilter_papers_for_eval(
        papers=papers,
        interests_text=interests_text,
        candidate_limit=first_pass_limit,
    )
    total_papers = len(eval_papers)
    skipped_prefilter = max(0, len(papers) - len(eval_papers))
    progress_cb(
        f"Evaluating {total_papers}/{len(papers)} papers with {provider} model {model} "
        f"(prefilter skipped: {skipped_prefilter})"
    )

    results: List[Dict[str, Any]] = []
    uncached_papers: List[Paper] = []
    for paper in eval_papers:
        cache_key = paper.paper_id
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and cached.get("interests_hash") == interests_hash:
            eval_data = cached.get("eval", heuristic_eval())
            cache_hits += 1
            usage = normalize_usage_fn(eval_data)
            usage_totals["input_tokens"] += usage["input_tokens"]
            usage_totals["output_tokens"] += usage["output_tokens"]
            usage_totals["total_tokens"] += usage["total_tokens"]
            usage_entries.append(
                {
                    "paper_id": paper.paper_id,
                    "score": int(eval_data.get("score", 0) or 0),
                    "include": bool(eval_data.get("include", False)),
                    "cached": True,
                    "usage": usage,
                }
            )
            results.append({"paper": paper, "eval": eval_data})
        else:
            uncached_papers.append(paper)

    if uncached_papers:
        progress_cb(
            f"Submitting {len(uncached_papers)} uncached papers to {provider} "
            f"with concurrency {eval_workers}"
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=eval_workers) as executor:
            future_to_paper = {
                executor.submit(
                    call_llm_eval_fn,
                    paper,
                    interests_text,
                    provider,
                    model,
                    first_pass_temperature,
                ): paper
                for paper in uncached_papers
            }
            for future in concurrent.futures.as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    eval_data = future.result()
                except Exception:
                    eval_data = heuristic_eval()

                api_calls += 1
                error_text = str(eval_data.get("_error", "")).strip()
                if error_text:
                    append_llm_error_log_fn(
                        date_str,
                        paper.paper_id,
                        provider,
                        model,
                        error_text,
                    )
                else:
                    cache[paper.paper_id] = {
                        "paper_id": paper.paper_id,
                        "interests_hash": interests_hash,
                        "updated_at": dt.datetime.now(dt.timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "eval": eval_data,
                    }

                usage = normalize_usage_fn(eval_data)
                usage_totals["input_tokens"] += usage["input_tokens"]
                usage_totals["output_tokens"] += usage["output_tokens"]
                usage_totals["total_tokens"] += usage["total_tokens"]
                usage_entries.append(
                    {
                        "paper_id": paper.paper_id,
                        "score": int(eval_data.get("score", 0) or 0),
                        "include": bool(eval_data.get("include", False)),
                        "cached": False,
                        "error": error_text if error_text else None,
                        "usage": usage,
                    }
                )
                results.append({"paper": paper, "eval": eval_data})

                completed = cache_hits + api_calls
                if completed == total_papers or completed % 10 == 0:
                    progress_cb(
                        f"Evaluation progress: {completed}/{total_papers} "
                        f"(cache hits: {cache_hits}, API calls: {api_calls})"
                    )
    elif total_papers > 0:
        progress_cb(
            f"Evaluation progress: {total_papers}/{total_papers} "
            f"(cache hits: {cache_hits}, API calls: {api_calls})"
        )

    save_cache_fn(cache, interests_hash)
    usage_log = {
        "date": date_str,
        "provider": provider,
        "model": model,
        "papers_evaluated": len(eval_papers),
        "papers_fetched": len(papers),
        "papers_skipped_prefilter": skipped_prefilter,
        "totals": usage_totals,
        "entries": usage_entries,
    }
    return usage_log, results


def sort_included_results(
    usage_log: Dict[str, Any],
    results: List[Dict[str, Any]],
    usage_log_path: str,
) -> List[Dict[str, Any]]:
    with open(usage_log_path, "w", encoding="utf-8") as f:
        json.dump(usage_log, f, indent=2, ensure_ascii=False)

    included = [r for r in results if r["eval"].get("include")]
    included.sort(key=lambda x: x["eval"].get("score", 0), reverse=True)
    return included
