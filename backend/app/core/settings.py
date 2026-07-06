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
    GROQ_MAX_OUTPUT_TOKENS: int = 4096

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

    # Embeddings (indexing + Qdrant search) — provider: jina | gemini
    EMBEDDING_PROVIDER: str = "jina"

    # Jina (https://jina.ai/api-dashboard/embedding)
    JINA_API_KEY: str = ""
    JINA_API_BASE_URL: str = "https://api.jina.ai/v1"
    JINA_EMBEDDING_MODEL: str = "jina-embeddings-v5-text-small"
    JINA_QUERY_TASK: str = "retrieval.query"
    JINA_DOCUMENT_TASK: str = "retrieval.passage"
    JINA_EMBED_NORMALIZED: bool = True
    JINA_EMBED_OUTPUT_DIMENSION: int | None = 1024  # v5-text-small native dim
    JINA_EMBED_MAX_CHARS: int = 12000
    JINA_EMBED_BATCH_SIZE: int = 16

    # Gemini (optional provider)
    GEMINI_API_KEY: str = ""
    GEMINI_API_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"
    GEMINI_EMBED_OUTPUT_DIMENSION: int = 768
    GEMINI_EMBED_MAX_CHARS: int = 12000

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

    CONTEXT_SEARCH_TOP_K: int = 24
    CONTEXT_SEARCH_TOP_K_PER_QUERY: int = 12
    CONTEXT_SEARCH_MAX_QUERIES: int = 4
    CONTEXT_TARGET_MAX_FILES: int = 8
    CONTEXT_VECTOR_FETCH_TOP_FILES: int = 5
    CONTEXT_ALLOWLIST_MAX_FILES: int = 16
    ENTRYPOINT_SCORE_BOOST: float = 0.08
    ENTRYPOINT_MAX_INJECT: int = 4
    SEARCH_QUERY_MAX: int = 500
    PLANNER_REPO_TREE_MAX_PATHS: int = 500
    PLANNER_REPO_TREE_MAX_CHARS: int = 8000

    # Agent limits
    MAX_RETRIES: int = 2
    MAX_AGENT_STEPS: int = 5
    MAX_CONTEXT_TOKENS: int = 8000
    CODE_WRITER_MAX_FILES_PER_CALL: int = 1
    PLAN_HINTS_MAX_EXTRA_FILES: int = 2
    WORKFLOW_SKIP_TESTS: bool = False

    # Isolated sandbox runner (only service that should mount Docker socket)
    SANDBOX_RUNNER_URL: str = "http://sandbox:8090"
    SANDBOX_RUNNER_SECRET: str = ""

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
    def embedding_model_id(self) -> str:
        if self.EMBEDDING_PROVIDER.strip().lower() == "jina":
            return self.JINA_EMBEDDING_MODEL
        return self.GEMINI_EMBEDDING_MODEL

    @property
    def provider_embedding_dim(self) -> int | None:
        """Output dimension configured for the active embedding provider."""
        if self.EMBEDDING_PROVIDER.strip().lower() == "jina":
            return self.JINA_EMBED_OUTPUT_DIMENSION
        return self.GEMINI_EMBED_OUTPUT_DIMENSION

    @property
    def effective_embedding_dim(self) -> int | None:
        """Provider output dim, else explicit Qdrant dim, else inferred on first embed."""
        return self.provider_embedding_dim or self.QDRANT_EMBEDDING_DIM

    @property
    def groq_model_output_limit(self) -> int:
        """Groq per-model max completion tokens (request values above this are clamped)."""
        model = self.GROQ_MODEL.lower()
        if "llama-4-scout" in model:
            return 8192
        if "llama-3.3-70b" in model:
            return 32768
        if "llama-3.1" in model:
            return 8192
        return 8192

    @property
    def effective_groq_max_output_tokens(self) -> int:
        return min(self.GROQ_MAX_OUTPUT_TOKENS, self.groq_model_output_limit)

    @property
    def oauth_enabled(self) -> bool:
        return bool(
            self.GITHUB_OAUTH_CLIENT_ID
            and self.GITHUB_OAUTH_CLIENT_SECRET
            and self.GITHUB_OAUTH_CALLBACK_URL
            and self.JWT_SECRET
        )


settings = Settings()
