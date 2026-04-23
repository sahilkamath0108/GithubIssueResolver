import json
import hashlib
import redis as redis_lib
import httpx
from app.core.settings import settings

# Redis cache client for LLM response caching
_cache = redis_lib.Redis.from_url(settings.REDIS_URL, decode_responses=True)
_CACHE_TTL = 60 * 60 * 24  # 24 hours

_client = httpx.Client(
    base_url=settings.OLLAMA_BASE_URL.rstrip("/"),
    timeout=httpx.Timeout(120.0, connect=10.0),
)


def _cache_key(prompt: str) -> str:
    return f"llm:cache:{hashlib.sha256(prompt.encode()).hexdigest()}"


def _get_cached(prompt: str) -> dict | None:
    raw = _cache.get(_cache_key(prompt))
    return json.loads(raw) if raw else None


def _set_cached(prompt: str, response: dict) -> None:
    _cache.setex(_cache_key(prompt), _CACHE_TTL, json.dumps(response))


def call_llm(prompt: str, use_cache: bool = True) -> str:
    """
    Call Ollama LLM with optional Redis caching.
    Cache hit = zero LLM cost for repeated identical prompts.
    """
    if use_cache:
        cached = _get_cached(prompt)
        if cached:
            return cached["text"]

    # Prefer /api/chat (newer Ollama). Fallback to /api/generate.
    body = {
        "model": settings.OLLAMA_CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    r = _client.post("/api/chat", json=body)
    if r.status_code == 404:
        r = _client.post(
            "/api/generate",
            json={"model": settings.OLLAMA_CHAT_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}},
        )
        r.raise_for_status()
        data = r.json()
        text = data.get("response") or ""
    else:
        r.raise_for_status()
        data = r.json()
        msg = data.get("message") or {}
        text = msg.get("content") or ""

    if use_cache:
        _set_cached(prompt, {"text": text})

    return text


def call_llm_json(prompt: str, use_cache: bool = True) -> dict:
    """
    Call LLM and parse JSON response. Raises ValueError if not valid JSON.
    """
    raw = call_llm(prompt, use_cache=use_cache)
    cleaned = raw.strip()

    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    # First attempt: strict JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Second attempt: extract the first JSON object/array substring.
    # Many models preface or suffix the JSON with explanations despite instructions.
    start_obj = cleaned.find("{")
    start_arr = cleaned.find("[")
    candidates = [i for i in (start_obj, start_arr) if i != -1]
    if not candidates:
        raise
    start = min(candidates)

    end_obj = cleaned.rfind("}")
    end_arr = cleaned.rfind("]")
    end_candidates = [i for i in (end_obj, end_arr) if i != -1]
    end = max(end_candidates) if end_candidates else -1
    if end <= start:
        raise

    snippet = cleaned[start : end + 1].strip()
    return json.loads(snippet)
