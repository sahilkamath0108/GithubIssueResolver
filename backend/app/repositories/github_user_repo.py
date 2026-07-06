from typing import Optional

from sqlalchemy.orm import Session

from app.core.token_crypto import decrypt_token, encrypt_token
from app.models.github_user import GitHubUser


class GitHubUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[GitHubUser]:
        return self.db.query(GitHubUser).filter(GitHubUser.id == user_id).first()

    def get_by_github_id(self, github_id: int) -> Optional[GitHubUser]:
        return self.db.query(GitHubUser).filter(GitHubUser.github_id == github_id).first()

    def upsert_oauth_user(
        self,
        *,
        github_id: int,
        login: str,
        avatar_url: str | None,
        access_token: str,
        token_scope: str | None,
    ) -> GitHubUser:
        encrypted = encrypt_token(access_token)
        user = self.get_by_github_id(github_id)
        if user:
            user.login = login
            user.avatar_url = avatar_url
            user.access_token_encrypted = encrypted
            user.token_scope = token_scope
        else:
            user = GitHubUser(
                github_id=github_id,
                login=login,
                avatar_url=avatar_url,
                access_token_encrypted=encrypted,
                token_scope=token_scope,
            )
            self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_access_token(self, user_id: int) -> str | None:
        user = self.get_by_id(user_id)
        if not user or not user.access_token_encrypted:
            return None
        return decrypt_token(user.access_token_encrypted)

    def clear_access_token(self, user_id: int) -> None:
        user = self.get_by_id(user_id)
        if not user:
            return
        user.access_token_encrypted = ""
        user.token_scope = None
        user.groq_api_key_encrypted = None
        user.jina_api_key_encrypted = None
        self.db.commit()

    def get_groq_api_key(self, user_id: int) -> str | None:
        user = self.get_by_id(user_id)
        if not user or not user.groq_api_key_encrypted:
            return None
        return decrypt_token(user.groq_api_key_encrypted)

    def get_jina_api_key(self, user_id: int) -> str | None:
        user = self.get_by_id(user_id)
        if not user or not user.jina_api_key_encrypted:
            return None
        return decrypt_token(user.jina_api_key_encrypted)

    def set_provider_keys(
        self,
        user_id: int,
        *,
        groq_api_key: str | None = None,
        jina_api_key: str | None = None,
    ) -> GitHubUser:
        user = self.get_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        if groq_api_key is not None:
            user.groq_api_key_encrypted = encrypt_token(groq_api_key) if groq_api_key else None
        if jina_api_key is not None:
            user.jina_api_key_encrypted = encrypt_token(jina_api_key) if jina_api_key else None
        self.db.commit()
        self.db.refresh(user)
        return user
