from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    REDIS_URL: str

    # Ollama (LLM for workflow + embeddings for indexing/search)
    OLLAMA_CHAT_MODEL: str = "gemma2:9b"

    # GitHub
    GITHUB_TOKEN: str
    GITHUB_WEBHOOK_SECRET: str = ""  # set to verify webhook signatures (recommended)

    # Qdrant (repo code indexing)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "repo_code_chunks"
    QDRANT_TIMEOUT: int = 120
    QDRANT_API_KEY: str = ""  # set for Qdrant Cloud / secured deployments
    QDRANT_EMBEDDING_DIM: int | None = None  # if unset, inferred from first Ollama embedding

    # Ollama embeddings (indexing). Override model to match your local pull, e.g. nomic-embed-text
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"

    # GitHub indexing / resilience
    GITHUB_API_MAX_RETRIES: int = 5
    GITHUB_API_RETRY_MIN_WAIT: float = 1.0
    GITHUB_API_RETRY_MAX_WAIT: float = 30.0
    INDEX_MAX_FILE_BYTES: int = 1_048_576  # 1 MiB per file
    INDEX_BLOB_FETCH_WORKERS: int = 8
    INDEX_CHUNK_MIN_LINES: int = 1
    INDEX_CHUNK_MAX_LINES: int = 400
    INDEX_CHUNK_OVERLAP_LINES: int = 0
    INDEX_FILE_EXTENSIONS: str = (
    # Backend / General Programming
    ".py,.js,.ts,.tsx,.jsx,.mjs,.cjs,"
    ".go,.rs,.java,.kt,.cs,.rb,.php,.swift,.scala,"
    ".c,.h,.cpp,.hpp,.cc,.hh,"

    # Frontend
    ".html,.htm,.css,.scss,.sass,.less,"
    ".vue,.svelte,.astro,"

    # Config / Infra / DevOps
    ".json,.yaml,.yml,.toml,.ini,.env,"
    ".dockerfile,.tf,.tfvars,"

    # Shell / Scripts
    ".sh,.bash,.zsh,.ps1,"

    # Database
    ".sql,"

    # Docs (useful for context)
    ".md,.mdx,.txt"
)
    INDEX_UPSERT_BATCH_SIZE: int = 64

    # Agent limits
    MAX_RETRIES: int = 2
    MAX_AGENT_STEPS: int = 5
    MAX_CONTEXT_TOKENS: int = 6000

    # API security
    API_KEY: str = ""  # set in .env

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def index_file_extensions(self) -> tuple[str, ...]:
        parts = [p.strip().lower() for p in self.INDEX_FILE_EXTENSIONS.split(",")]
        return tuple(p for p in parts if p)


settings = Settings()
