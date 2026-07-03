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
