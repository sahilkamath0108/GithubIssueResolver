from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    REDIS_URL: str

    # Environment: "development" | "production"
    ENVIRONMENT: str = "development"
    SQL_ECHO: bool = False

    # Groq (chat LLM for workflow plan/write/fix) via OpenAI-compatible API
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # GitHub — server PAT for webhooks/background jobs when OAuth is enabled
    GITHUB_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    REQUIRE_WEBHOOK_SECRET: bool = False  # if true, reject webhooks when secret unset

    # GitHub OAuth (user login — per-user repo access for submit/index)
    GITHUB_OAUTH_CLIENT_ID: str = ""
    GITHUB_OAUTH_CLIENT_SECRET: str = ""
    GITHUB_OAUTH_CALLBACK_URL: str = ""
    JWT_SECRET: str = ""
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    AUTH_COOKIE_NAME: str = "session"
    AUTH_COOKIE_SECURE: bool = False  # set true in production behind HTTPS

    # Comma-separated owner/name repos allowed for workflow + indexing (empty = all)
    REPO_ALLOWLIST: str = ""

    # Qdrant (repo code indexing)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "repo_code_chunks"
    QDRANT_TIMEOUT: int = 120
    QDRANT_API_KEY: str = ""
    QDRANT_EMBEDDING_DIM: int | None = None

    # Ollama embeddings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"

    # GitHub indexing / resilience
    GITHUB_API_MAX_RETRIES: int = 5
    GITHUB_API_RETRY_MIN_WAIT: float = 1.0
    GITHUB_API_RETRY_MAX_WAIT: float = 30.0
    INDEX_MAX_FILE_BYTES: int = 1_048_576
    INDEX_BLOB_FETCH_WORKERS: int = 8
    INDEX_CHUNK_MIN_LINES: int = 1
    INDEX_CHUNK_MAX_LINES: int = 400
    INDEX_CHUNK_OVERLAP_LINES: int = 0
    INDEX_FILE_EXTENSIONS: str = (
        ".py,.js,.ts,.tsx,.jsx,.mjs,.cjs,"
        ".go,.rs,.java,.kt,.cs,.rb,.php,.swift,.scala,"
        ".c,.h,.cpp,.hpp,.cc,.hh,"
        ".html,.htm,.css,.scss,.sass,.less,"
        ".vue,.svelte,.astro,"
        ".json,.yaml,.yml,.toml,.ini,"
        ".dockerfile,.tf,.tfvars,"
        ".sh,.bash,.zsh,.ps1,"
        ".sql,"
        ".md,.mdx,.txt"
    )
    INDEX_UPSERT_BATCH_SIZE: int = 64

    CONTEXT_SEARCH_TOP_K: int = 12

    # Agent limits
    MAX_RETRIES: int = 2
    MAX_AGENT_STEPS: int = 5
    MAX_CONTEXT_TOKENS: int = 6000
    WORKFLOW_SKIP_TESTS: bool = False

    # API security
    API_KEY: str = ""
    FRONTEND_ORIGIN: str = ""
    EXPOSE_DOCS: bool = True
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 30

    # Pagination
    TASK_LIST_DEFAULT_LIMIT: int = 50
    TASK_LIST_MAX_LIMIT: int = 200

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def index_file_extensions(self) -> tuple[str, ...]:
        parts = [p.strip().lower() for p in self.INDEX_FILE_EXTENSIONS.split(",")]
        return tuple(p for p in parts if p)

    @property
    def repo_allowlist_raw(self) -> tuple[str, ...]:
        parts = [p.strip() for p in self.REPO_ALLOWLIST.split(",") if p.strip()]
        return tuple(parts)

    @property
    def repo_allowlist(self) -> frozenset[str]:
        return frozenset(p.lower() for p in self.repo_allowlist_raw)

    @property
    def oauth_enabled(self) -> bool:
        return bool(
            self.GITHUB_OAUTH_CLIENT_ID
            and self.GITHUB_OAUTH_CLIENT_SECRET
            and self.GITHUB_OAUTH_CALLBACK_URL
            and self.JWT_SECRET
        )


settings = Settings()
