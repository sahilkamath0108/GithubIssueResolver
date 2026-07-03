import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.settings import settings


def _fernet() -> Fernet:
    secret = settings.JWT_SECRET or settings.GITHUB_OAUTH_CLIENT_SECRET
    if not secret:
        raise RuntimeError("JWT_SECRET is required to encrypt OAuth tokens.")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_token(cipher: str) -> str:
    try:
        return _fernet().decrypt(cipher.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored OAuth token could not be decrypted.") from exc
