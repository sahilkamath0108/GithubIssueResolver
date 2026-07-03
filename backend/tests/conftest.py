import os

# Minimal env for importing app modules in tests
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("API_KEY", "test-api-key")
