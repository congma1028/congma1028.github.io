import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional

from .models import Paper

_RETRY_MAX_ATTEMPTS = 5


def _parse_retry_after_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    raw = value.strip()
    if raw.isdigit():
        return float(raw)
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        delta = (parsed - dt.datetime.now(dt.timezone.utc)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


def _json_extract(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _extract_retry_seconds_from_error_text(text: str) -> Optional[float]:
    match = re.search(r"retry in\\s+([0-9]+(?:\\.[0-9]+)?)s", text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _empty_usage() -> Dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _llm_retry_attempts() -> int:
    return _RETRY_MAX_ATTEMPTS


def configure_retry_max_attempts(value: int) -> None:
    global _RETRY_MAX_ATTEMPTS
    _RETRY_MAX_ATTEMPTS = max(1, min(10, int(value)))


def _heuristic_eval() -> Dict[str, Any]:
    return {
        "include": False,
        "score": 0,
        "confidence": "low",
        "reasons": ["LLM evaluation unavailable"],
        "tags": [],
        "summary": "Evaluation unavailable because LLM call failed.",
    }


def _failed_eval(error: str) -> Dict[str, Any]:
    out = _heuristic_eval()
    out["_error"] = error
    return out


def _normalize_eval_payload(parsed: Dict[str, Any], usage: Dict[str, int]) -> Dict[str, Any]:
    reasons = parsed.get("reasons", [])
    tags = parsed.get("tags", [])
    parsed["reasons"] = reasons[:3] if isinstance(reasons, list) else []
    parsed["tags"] = tags[:6] if isinstance(tags, list) else []
    parsed["score"] = int(parsed.get("score", 0))
    parsed["score"] = max(0, min(100, parsed["score"]))
    if parsed.get("confidence") not in {"low", "medium", "high"}:
        parsed["confidence"] = "low"
    parsed["include"] = bool(parsed.get("include", False))
    if not isinstance(parsed.get("summary"), str):
        parsed["summary"] = ""
    parsed["usage"] = usage
    return parsed


def normalize_usage(eval_data: Dict[str, Any]) -> Dict[str, int]:
    usage = eval_data.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    return {
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
    }


def resolve_llm_provider_model() -> tuple[str, str]:
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider == "openai":
        default_model = "gpt-4o-mini"
    elif provider == "ollama":
        default_model = "llama3.1:8b"
    elif provider == "openai_compatible":
        default_model = "llama3.1"
    else:
        default_model = "gemini-2.5-flash"
    model = os.getenv("LLM_MODEL", default_model).strip()
    if not model:
        raise RuntimeError("LLM_MODEL cannot be empty")
    return provider, model


def _http_json_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body) if body else {}


def preflight_llm_credentials_and_model(provider: str, model: str) -> None:
    provider_norm = provider.strip().lower()
    if provider_norm == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY or LLM_API_KEY is not set")
        model_name = model if model.startswith("models/") else f"models/{model}"
        model_path = urllib.parse.quote(model_name, safe="/-._")
        _http_json_get(f"https://generativelanguage.googleapis.com/v1beta/{model_path}?key={api_key}")
        return
    if provider_norm == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY or LLM_API_KEY is not set")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
        _http_json_get(
            f"{base_url}/v1/models/{urllib.parse.quote(model, safe='-._')}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        return
    if provider_norm == "openai_compatible":
        base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
        api_key = os.getenv("LLM_API_KEY", "").strip()
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        _http_json_get(f"{base_url}/models", headers=headers, timeout=20)
        return
    if provider_norm == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        _http_json_get(f"{base_url}/api/tags", timeout=20)
        return
    raise RuntimeError("Unsupported LLM_PROVIDER")


def _call_gemini(prompt: str, model: str, temperature: float) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return {"_error": "GEMINI_API_KEY or LLM_API_KEY is not set", "usage": _empty_usage()}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    model_path = urllib.parse.quote(model, safe="-._")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_path}:generateContent?key={api_key}"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    max_attempts = _llm_retry_attempts()
    raw = None
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < max_attempts:
                retry_secs = _extract_retry_seconds_from_error_text(body)
                time.sleep(max(1.0, retry_secs if retry_secs is not None else 10.0 * attempt))
                continue
            return {"_error": f"Gemini HTTP {e.code}: {body[:600]}", "usage": _empty_usage()}
        except Exception as e:
            if attempt < max_attempts:
                time.sleep(2.0 * attempt)
                continue
            return {"_error": f"Gemini request failed: {type(e).__name__}: {e}", "usage": _empty_usage()}
    if raw is None:
        return {"_error": "Gemini request failed after retries", "usage": _empty_usage()}
    usage_obj = raw.get("usageMetadata", {})
    usage = {
        "input_tokens": int(usage_obj.get("promptTokenCount", 0) or 0),
        "output_tokens": int(usage_obj.get("candidatesTokenCount", 0) or 0),
        "total_tokens": int(usage_obj.get("totalTokenCount", 0) or 0),
    }
    text = "\n".join(
        part.get("text", "")
        for cand in raw.get("candidates", [])
        for part in cand.get("content", {}).get("parts", [])
        if isinstance(part.get("text"), str)
    ).strip()
    try:
        parsed = json.loads(_json_extract(text))
        parsed["usage"] = usage
        return parsed
    except Exception:
        return {"_error": "Could not parse JSON output from Gemini", "usage": usage}


def _call_openai_like(prompt: str, model: str, temperature: float, base_url: str, api_key: str, label: str) -> Dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return JSON only. No markdown or extra text."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    max_attempts = _llm_retry_attempts()
    raw = None
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < max_attempts:
                retry_after = _parse_retry_after_seconds(e.headers.get("Retry-After"))
                time.sleep(max(1.0, retry_after if retry_after is not None else 10.0 * attempt))
                continue
            return {"_error": f"{label} HTTP {e.code}: {body[:600]}", "usage": _empty_usage()}
        except Exception as e:
            if attempt < max_attempts:
                time.sleep(2.0 * attempt)
                continue
            return {"_error": f"{label} request failed: {type(e).__name__}: {e}", "usage": _empty_usage()}
    if raw is None:
        return {"_error": f"{label} request failed after retries", "usage": _empty_usage()}
    usage_obj = raw.get("usage", {})
    usage = {
        "input_tokens": int(usage_obj.get("prompt_tokens", 0) or 0),
        "output_tokens": int(usage_obj.get("completion_tokens", 0) or 0),
        "total_tokens": int(usage_obj.get("total_tokens", 0) or 0),
    }
    content = ""
    choices = raw.get("choices", [])
    if choices and isinstance(choices[0], dict):
        content = str(choices[0].get("message", {}).get("content", "") or "")
    try:
        parsed = json.loads(_json_extract(content))
        parsed["usage"] = usage
        return parsed
    except Exception:
        return {"_error": f"Could not parse JSON output from {label}", "usage": usage}


def _call_ollama(prompt: str, model: str, temperature: float, base_url: str) -> Dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/api/generate"
    payload = {"model": model, "prompt": prompt, "format": "json", "stream": False, "options": {"temperature": temperature}}
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"_error": f"Ollama request failed: {type(e).__name__}: {e}", "usage": _empty_usage()}
    usage = {
        "input_tokens": int(raw.get("prompt_eval_count", 0) or 0),
        "output_tokens": int(raw.get("eval_count", 0) or 0),
        "total_tokens": int((raw.get("prompt_eval_count", 0) or 0) + (raw.get("eval_count", 0) or 0)),
    }
    text = str(raw.get("response", "") or "")
    try:
        parsed = json.loads(_json_extract(text))
        parsed["usage"] = usage
        return parsed
    except Exception:
        return {"_error": "Could not parse JSON output from Ollama", "usage": usage}


def call_llm_json_prompt(prompt: str, provider: str, model: str, temperature: float = 0.1) -> Dict[str, Any]:
    p = provider.strip().lower()
    if p == "gemini":
        return _call_gemini(prompt, model, temperature)
    if p == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            return {"_error": "OPENAI_API_KEY or LLM_API_KEY is not set", "usage": _empty_usage()}
        return _call_openai_like(prompt, model, temperature, os.getenv("OPENAI_BASE_URL", "https://api.openai.com"), api_key, "OpenAI")
    if p == "openai_compatible":
        return _call_openai_like(prompt, model, temperature, os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"), os.getenv("LLM_API_KEY", ""), "OpenAI-compatible")
    if p == "ollama":
        return _call_ollama(prompt, model, temperature, os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    return {"_error": "Unsupported LLM provider", "usage": _empty_usage()}


def call_llm_eval(
    paper: Paper,
    prompt: str,
    provider: str,
    model: str,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    out = call_llm_json_prompt(prompt, provider, model, temperature)
    if out.get("_error"):
        return _failed_eval(str(out["_error"]))
    return _normalize_eval_payload(out, normalize_usage(out))
