from app.core.settings import Settings


def test_scout_clamps_output_tokens():
    s = Settings(
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        GROQ_MODEL="meta-llama/llama-4-scout-17b-16e-instruct",
        GROQ_MAX_OUTPUT_TOKENS=16384,
    )
    assert s.groq_model_output_limit == 8192
    assert s.effective_groq_max_output_tokens == 8192


def test_llama33_allows_higher_output():
    s = Settings(
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        GROQ_MODEL="llama-3.3-70b-versatile",
        GROQ_MAX_OUTPUT_TOKENS=4096,
    )
    assert s.groq_model_output_limit == 32768
    assert s.effective_groq_max_output_tokens == 4096
