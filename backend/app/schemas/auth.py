from pydantic import BaseModel


class AuthStatusResponse(BaseModel):
    oauth_enabled: bool
    authenticated: bool = False


class UserProfile(BaseModel):
    id: int
    github_id: int
    login: str
    avatar_url: str | None = None


class GitHubRepoSummary(BaseModel):
    full_name: str
    private: bool
    html_url: str
    default_branch: str
    permissions_push: bool


class ProviderKeysStatus(BaseModel):
    user_keys_required: bool
    embedding_provider: str
    groq_configured: bool
    jina_configured: bool
    groq_user_configured: bool
    jina_user_configured: bool


class ProviderKeysUpdate(BaseModel):
    groq_api_key: str | None = None
    jina_api_key: str | None = None
