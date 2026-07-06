from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.provider_key_service import (
    assert_provider_keys_for_user,
    provider_keys_status,
    user_must_supply_provider_keys,
)


def test_user_must_supply_when_oauth_and_no_env_keys():
    with patch("app.services.provider_key_service.settings") as mock_settings:
        mock_settings.oauth_enabled = True
        mock_settings.GROQ_API_KEY = ""
        mock_settings.JINA_API_KEY = ""
        mock_settings.EMBEDDING_PROVIDER = "jina"
        assert user_must_supply_provider_keys() is True


def test_user_not_required_when_env_keys_set():
    with patch("app.services.provider_key_service.settings") as mock_settings:
        mock_settings.oauth_enabled = True
        mock_settings.GROQ_API_KEY = "gsk-test"
        mock_settings.JINA_API_KEY = "jina-test"
        mock_settings.EMBEDDING_PROVIDER = "jina"
        assert user_must_supply_provider_keys() is False


def test_assert_provider_keys_raises_when_missing():
    db = MagicMock()
    with patch("app.services.provider_key_service.settings") as mock_settings:
        mock_settings.oauth_enabled = True
        mock_settings.GROQ_API_KEY = ""
        mock_settings.JINA_API_KEY = ""
        mock_settings.EMBEDDING_PROVIDER = "jina"
        with patch("app.services.provider_key_service.GitHubUserRepository") as repo_cls:
            repo_cls.return_value.get_groq_api_key.return_value = None
            repo_cls.return_value.get_jina_api_key.return_value = None
            with pytest.raises(HTTPException) as exc:
                assert_provider_keys_for_user(db, 1)
            assert exc.value.status_code == 400
            assert "Groq" in exc.value.detail


def test_provider_keys_status_marks_user_keys():
    db = MagicMock()
    with patch("app.services.provider_key_service.settings") as mock_settings:
        mock_settings.oauth_enabled = True
        mock_settings.GROQ_API_KEY = ""
        mock_settings.JINA_API_KEY = ""
        mock_settings.EMBEDDING_PROVIDER = "jina"
        with patch("app.services.provider_key_service.GitHubUserRepository") as repo_cls:
            repo_cls.return_value.get_groq_api_key.return_value = "gsk-user"
            repo_cls.return_value.get_jina_api_key.return_value = None
            status = provider_keys_status(db, 7)
            assert status["groq_configured"] is True
            assert status["groq_user_configured"] is True
            assert status["jina_configured"] is False
