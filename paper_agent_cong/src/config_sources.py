import os
from pathlib import Path
from typing import Any, Dict, Type

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def load_yaml(path: Path, error_cls: Type[Exception] = RuntimeError) -> Dict[str, Any]:
    if not path.exists():
        raise error_cls(f"Missing config file: {path}")
    if yaml is None:
        raise error_cls("PyYAML is required. Install with: pip install pyyaml")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise error_cls(f"Config must be a YAML mapping: {path}")
    return data


def _to_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def load_interests(config_dir: Path, error_cls: Type[Exception] = RuntimeError) -> str:
    data = load_yaml(config_dir / "interests.yaml", error_cls=error_cls)
    interests = data.get("interests")
    if isinstance(interests, list):
        items = [str(x).strip() for x in interests if str(x).strip()]
        if not items:
            raise error_cls("config/interests.yaml has empty 'interests' list")
        return "\n".join(f"- {item}" for item in items)
    if isinstance(interests, str) and interests.strip():
        return interests.strip()
    research_profile = data.get("research_profile")
    if isinstance(research_profile, str) and research_profile.strip():
        return research_profile.strip()
    raise error_cls("config/interests.yaml must define 'interests' as list or string")


def load_interest_exclusions(config_dir: Path, error_cls: Type[Exception] = RuntimeError) -> list[str]:
    data = load_yaml(config_dir / "interests.yaml", error_cls=error_cls)
    raw = data.get("exclude_topics", [])
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def load_arxiv_source_config(config_dir: Path, error_cls: Type[Exception] = RuntimeError) -> Dict[str, Any]:
    data = load_yaml(config_dir / "sources.yaml", error_cls=error_cls)

    arxiv = None
    if isinstance(data.get("arxiv"), dict):
        arxiv = data["arxiv"]
    elif isinstance(data.get("sources"), list):
        for src in data["sources"]:
            if isinstance(src, dict) and str(src.get("name", "")).lower() == "arxiv":
                arxiv = src
                break

    if not isinstance(arxiv, dict):
        raise error_cls("config/sources.yaml must include an arXiv source config")

    categories = arxiv.get("categories", [])
    if not isinstance(categories, list):
        raise error_cls("arXiv 'categories' must be a list when provided")

    clean_categories = [str(c).strip() for c in categories if str(c).strip()]
    if not clean_categories:
        raise error_cls("arXiv source must provide a non-empty 'categories' list")

    per_category_max = int(arxiv.get("per_category_max_results", arxiv.get("max_results", 30)))
    if per_category_max <= 0:
        per_category_max = 30

    retries = int(arxiv.get("retries", 5))
    retries = max(1, min(5, retries))

    request_delay_seconds = float(arxiv.get("request_delay_seconds", 4.0))
    if request_delay_seconds < 0:
        request_delay_seconds = 0.0

    lookback_hours = int(arxiv.get("lookback_hours", 24))
    lookback_hours = max(1, min(168, lookback_hours))

    align_to_submission_deadline = _to_bool(
        arxiv.get("align_to_submission_deadline", True),
        default=True,
    )

    user_agent = str(arxiv.get("user_agent", os.getenv("ARXIV_USER_AGENT", "").strip())).strip()
    if not user_agent:
        contact_email = os.getenv("ARXIV_CONTACT_EMAIL", "").strip()
        if contact_email:
            user_agent = f"paper-agent-daily-digest/1.0 (+mailto:{contact_email})"
        else:
            user_agent = "paper-agent-daily-digest/1.0"

    return {
        "enabled": bool(arxiv.get("enabled", True)),
        "categories": clean_categories,
        "per_category_max_results": per_category_max,
        "retries": retries,
        "request_delay_seconds": request_delay_seconds,
        "lookback_hours": lookback_hours,
        "align_to_submission_deadline": align_to_submission_deadline,
        "user_agent": user_agent,
    }


def load_crossref_source_config(config_dir: Path, error_cls: Type[Exception] = RuntimeError) -> Dict[str, Any]:
    data = load_yaml(config_dir / "sources.yaml", error_cls=error_cls)
    crossref = data.get("crossref")
    if not isinstance(crossref, dict):
        return {
            "enabled": False,
            "journals": [],
            "max_results_per_journal": 20,
            "from_days": 7,
            "request_delay_seconds": 1.0,
            "user_agent": "paper-agent-daily-digest/1.0",
            "arxiv_pdf_fallback": 1,
        }

    journals = crossref.get("journals", [])
    if not isinstance(journals, list):
        raise error_cls("crossref 'journals' must be a list when provided")
    clean_journals = [str(j).strip() for j in journals if str(j).strip()]

    max_results = int(crossref.get("max_results_per_journal", 20))
    max_results = max(1, min(200, max_results))
    from_days = int(crossref.get("from_days", 7))
    from_days = max(1, min(60, from_days))

    request_delay_seconds = float(crossref.get("request_delay_seconds", 1.0))
    if request_delay_seconds < 0:
        request_delay_seconds = 0.0

    user_agent = str(crossref.get("user_agent", os.getenv("CROSSREF_USER_AGENT", "").strip())).strip()
    if not user_agent:
        user_agent = "paper-agent-daily-digest/1.0"

    arxiv_pdf_fallback = int(crossref.get("arxiv_pdf_fallback", 1))
    return {
        "enabled": bool(crossref.get("enabled", True)),
        "journals": clean_journals,
        "max_results_per_journal": max_results,
        "from_days": from_days,
        "request_delay_seconds": request_delay_seconds,
        "user_agent": user_agent,
        "arxiv_pdf_fallback": 1 if arxiv_pdf_fallback != 0 else 0,
    }


def load_runtime_config(config_dir: Path, error_cls: Type[Exception] = RuntimeError) -> Dict[str, Any]:
    default_cfg: Dict[str, Any] = {
        "first_pass_limit": 12,
        "second_pass_limit": 20,
        "llm_max_concurrency": 1,
        "report_max_concurrency": 1,
        "first_pass_temperature": 0.1,
        "second_pass_temperature": 0.1,
        "llm_retry_max_attempts": 5,
        "zotero_sync_score_threshold": 85,
        "clear_db_cache_on_run": False,
        "exclude_topics": [],
    }
    path = config_dir / "runtime.yaml"
    if not path.exists():
        return default_cfg

    data = load_yaml(path, error_cls=error_cls)
    out = dict(default_cfg)

    out["first_pass_limit"] = int(data.get("first_pass_limit", out["first_pass_limit"]))
    out["second_pass_limit"] = int(data.get("second_pass_limit", out["second_pass_limit"]))
    out["llm_max_concurrency"] = max(1, int(data.get("llm_max_concurrency", out["llm_max_concurrency"])))
    out["report_max_concurrency"] = max(1, int(data.get("report_max_concurrency", out["report_max_concurrency"])))
    out["first_pass_temperature"] = float(data.get("first_pass_temperature", out["first_pass_temperature"]))
    out["second_pass_temperature"] = float(data.get("second_pass_temperature", out["second_pass_temperature"]))
    out["llm_retry_max_attempts"] = max(1, min(10, int(data.get("llm_retry_max_attempts", out["llm_retry_max_attempts"]))))
    out["zotero_sync_score_threshold"] = int(data.get("zotero_sync_score_threshold", out["zotero_sync_score_threshold"]))
    out["clear_db_cache_on_run"] = _to_bool(data.get("clear_db_cache_on_run", out["clear_db_cache_on_run"]), default=False)
    raw_exclude = data.get("exclude_topics", [])
    if isinstance(raw_exclude, list):
        out["exclude_topics"] = [str(x).strip() for x in raw_exclude if str(x).strip()]
    elif isinstance(raw_exclude, str) and raw_exclude.strip():
        out["exclude_topics"] = [raw_exclude.strip()]
    else:
        out["exclude_topics"] = []
    return out
