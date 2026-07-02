import json
import hashlib
import redis as redis_lib
import logging
import sys
import contextvars
from groq import Groq
from app.core.settings import settings

# Redis cache client for LLM response caching
_cache = redis_lib.Redis.from_url(settings.REDIS_URL, decode_responses=True)
_CACHE_TTL = 60 * 60 * 24  # 24 hours

# Groq client for chat LLM
# NOTE: Groq's Python SDK expects the base host URL (e.g. https://api.groq.com)
# and it will append its own API path. If you set a base_url that already includes
# `/openai/v1`, you will get doubled paths like `/openai/v1/openai/v1/...`.
_groq = Groq(
    api_key=(settings.GROQ_API_KEY or None),
    base_url=settings.GROQ_BASE_URL,
)

logger = logging.getLogger(__name__)

# Stores the most recent raw LLM content in the current context (request/task)
_last_llm_raw: contextvars.ContextVar[str | None] = contextvars.ContextVar("last_llm_raw", default=None)

def get_last_llm_raw() -> str | None:
    return _last_llm_raw.get()

def _parse_ollama_stream_text(raw_text: str) -> str:
    """
    Ollama can return NDJSON (one JSON object per line) even when stream=false,
    depending on proxying / server version. This extracts and concatenates the
    incremental tokens into a single text response.
    """
    out_parts: list[str] = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        # /api/chat stream chunks
        msg = obj.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            out_parts.append(msg["content"])
            continue
        # /api/generate stream chunks
        if isinstance(obj.get("response"), str):
            out_parts.append(obj["response"])
            continue
    return "".join(out_parts).strip()


def _cache_key(prompt: str) -> str:
    return f"llm:cache:{hashlib.sha256(prompt.encode()).hexdigest()}"


def _get_cached(prompt: str) -> dict | None:
    raw = _cache.get(_cache_key(prompt))
    return json.loads(raw) if raw else None


def _set_cached(prompt: str, response: dict) -> None:
    _cache.setex(_cache_key(prompt), _CACHE_TTL, json.dumps(response))


def call_llm(prompt: str, use_cache: bool = True) -> str:
    """
    Call Groq chat LLM with optional Redis caching.
    Cache hit = zero LLM cost for repeated identical prompts.
    """
    if use_cache:
        cached = _get_cached(prompt)
        if cached:
            text = cached["text"]
            _last_llm_raw.set(text)
            return text

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to `.env`.")

    completion = _groq.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    text = ""
    if completion.choices:
        msg = completion.choices[0].message
        if msg and getattr(msg, "content", None):
            text = msg.content or ""

    if not isinstance(text, str) or not text.strip():
        # Provide a helpful error payload for debugging.
        try:
            payload = completion.model_dump()
        except Exception:
            payload = {"has_choices": bool(getattr(completion, "choices", None)), "model": getattr(completion, "model", None)}
        logger.error("Groq returned empty content. Response payload: %s", payload)
        raise RuntimeError(
            "Groq returned an empty response. "
            "This often happens when using a non-chat model ID with the chat endpoint. "
            "Set GROQ_MODEL to a chat-completions model like `llama-3.3-70b-versatile`."
        )

    if use_cache:
        _set_cached(prompt, {"text": text})

    _last_llm_raw.set(text)
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

    def _strict_parse(s: str) -> dict:
        obj = json.loads(s)
        if not isinstance(obj, dict):
            raise ValueError("Expected a JSON object at top-level.")
        return obj

    # First attempt: strict JSON parse
    try:
        return _strict_parse(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Second attempt: extract the first JSON object/array substring.
    # Many models preface or suffix the JSON with explanations despite instructions.
    start_obj = cleaned.find("{")
    start_arr = cleaned.find("[")
    candidates = [i for i in (start_obj, start_arr) if i != -1]
    if not candidates:
        logger.error("LLM JSON parse failed: no JSON start token. Raw (truncated): %s", cleaned[:2000])
        print("[llm_service] JSON parse failed: no JSON start token. Raw (truncated):", cleaned[:2000], file=sys.stderr)
        raise ValueError("LLM response did not contain a JSON object/array start token.")
    start = min(candidates)

    end_obj = cleaned.rfind("}")
    end_arr = cleaned.rfind("]")
    end_candidates = [i for i in (end_obj, end_arr) if i != -1]
    end = max(end_candidates) if end_candidates else -1
    if end <= start:
        logger.error("LLM JSON parse failed: no JSON end token. Raw (truncated): %s", cleaned[:2000])
        print("[llm_service] JSON parse failed: no JSON end token. Raw (truncated):", cleaned[:2000], file=sys.stderr)
        raise ValueError("LLM response did not contain a complete JSON object/array.")

    snippet = cleaned[start : end + 1].strip()
    try:
        return _strict_parse(snippet)
    except (json.JSONDecodeError, ValueError):
        # Final attempt: ask the model to repair the JSON.
        repair_prompt = (
            "You will be given a response that was supposed to be a single JSON object.\n"
            "Fix it into VALID JSON (RFC 8259). Return ONLY the JSON object, no commentary.\n\n"
            f"Broken response:\n{cleaned}\n"
        )
        repaired = call_llm(repair_prompt, use_cache=False).strip()
        if repaired.startswith("```"):
            repaired = repaired.split("\n", 1)[-1]
            repaired = repaired.rsplit("```", 1)[0].strip()
        # Try parse repaired (and if it still contains extra text, extract braces)
        try:
            return _strict_parse(repaired)
        except (json.JSONDecodeError, ValueError):
            s2 = repaired
            s2_start = min([i for i in (s2.find("{"), s2.find("[")) if i != -1], default=-1)
            s2_end = max([i for i in (s2.rfind("}"), s2.rfind("]")) if i != -1], default=-1)
            if s2_start != -1 and s2_end > s2_start:
                try:
                    return _strict_parse(s2[s2_start : s2_end + 1].strip())
                except (json.JSONDecodeError, ValueError):
                    pass

            # Always surface the actual raw output for debugging.
            raw_trunc = cleaned[:2000]
            repaired_trunc = repaired[:2000]
            logger.error("LLM JSON parse failed after repair. Raw (truncated): %s", raw_trunc)
            logger.error("LLM JSON repair output (truncated): %s", repaired_trunc)
            print("[llm_service] JSON parse failed. Raw (truncated):", raw_trunc, file=sys.stderr)
            print("[llm_service] JSON repair output (truncated):", repaired_trunc, file=sys.stderr)
            raise ValueError(
                "LLM returned invalid JSON even after repair attempt. "
                "See logs for raw/repaired output."
            )
