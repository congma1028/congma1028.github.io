from src.models import Paper
from src import pipeline_engine as pe


def _mk_ranked(pid: str):
    return {
        "paper": Paper(
            paper_id=pid,
            title=f"title-{pid}",
            authors=["A B"],
            abstract="abstract",
            date="2026-02-23",
            link=f"https://example.org/{pid}",
            pdf_link=f"https://example.org/{pid}.pdf",
            source="arxiv",
            doi=None,
            journal="arXiv",
        ),
        "eval": {
            "score": 90,
            "include": True,
            "confidence": "high",
            "reasons": ["r"],
            "tags": ["t"],
            "summary": "s0",
        },
    }


def test_second_pass_limit_applies_top_k(monkeypatch):
    monkeypatch.setattr(pe, "_load_json_map", lambda path: {})
    monkeypatch.setattr(pe, "_save_json_map", lambda path, data: None)
    monkeypatch.setattr(pe, "_download_pdf_bytes", lambda url, ua: b"%PDF")
    monkeypatch.setattr(pe, "_extract_main_text_from_pdf", lambda b: "paper text")
    monkeypatch.setattr(
        pe,
        "call_llm_json_prompt",
        lambda prompt, provider, model, temperature=0.1: {
            "summary": "s1",
            "reasons": ["rr"],
            "tags": ["tt"],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        },
    )
    monkeypatch.setattr(pe, "_append_llm_error_log", lambda *args, **kwargs: None)

    ranked = [_mk_ranked("p1"), _mk_ranked("p2"), _mk_ranked("p3")]
    out = pe.second_pass_enrich_papers(
        ranked=ranked,
        interests_text="- x",
        date_str="2026-02-23",
        provider="gemini",
        model="gemini-2.5-flash",
        user_agent="ua",
        runtime_cfg={
            "second_pass_limit": 1,
            "report_max_concurrency": 1,
            "second_pass_temperature": 0.1,
        },
    )
    assert len(out) == 1
    assert out[0]["paper"].paper_id == "p1"
    assert out[0]["eval"]["summary"] == "s1"


def test_second_pass_limit_zero_means_all(monkeypatch):
    monkeypatch.setattr(pe, "_load_json_map", lambda path: {})
    monkeypatch.setattr(pe, "_save_json_map", lambda path, data: None)
    monkeypatch.setattr(pe, "_download_pdf_bytes", lambda url, ua: b"%PDF")
    monkeypatch.setattr(pe, "_extract_main_text_from_pdf", lambda b: "paper text")
    monkeypatch.setattr(
        pe,
        "call_llm_json_prompt",
        lambda prompt, provider, model, temperature=0.1: {
            "summary": "s_all",
            "reasons": ["rr"],
            "tags": ["tt"],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        },
    )
    monkeypatch.setattr(pe, "_append_llm_error_log", lambda *args, **kwargs: None)

    ranked = [_mk_ranked("p1"), _mk_ranked("p2")]
    out = pe.second_pass_enrich_papers(
        ranked=ranked,
        interests_text="- x",
        date_str="2026-02-23",
        provider="gemini",
        model="gemini-2.5-flash",
        user_agent="ua",
        runtime_cfg={
            "second_pass_limit": 0,
            "report_max_concurrency": 1,
            "second_pass_temperature": 0.1,
        },
    )
    assert len(out) == 2
