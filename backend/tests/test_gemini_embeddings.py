from unittest.mock import MagicMock, patch

import pytest

from app.indexing.gemini_embeddings import (
    GeminiEmbeddingClient,
    format_code_retrieval_query,
    format_retrieval_document,
)


def test_format_code_retrieval_query():
    assert format_code_retrieval_query("auth middleware") == (
        "task: code retrieval | query: auth middleware"
    )


def test_format_retrieval_document_with_title():
    assert format_retrieval_document("def foo(): pass", title="src/app.py") == (
        "title: src/app.py | text: def foo(): pass"
    )


def test_format_retrieval_document_without_title():
    assert format_retrieval_document("hello") == "title: none | text: hello"


def test_embed_query_parses_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"embedding": {"values": [0.1, 0.2, 0.3]}}

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    with patch("app.indexing.gemini_embeddings.default_settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "test-key"
        mock_settings.GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
        mock_settings.GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
        mock_settings.GEMINI_EMBED_OUTPUT_DIMENSION = None
        mock_settings.GEMINI_EMBED_MAX_CHARS = 12000

        embedder = GeminiEmbeddingClient(mock_settings)
        embedder._client = mock_client

        vec = embedder.embed_query("login handler")

    assert vec == [0.1, 0.2, 0.3]
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/models/gemini-embedding-2:embedContent"
    body = call_args[1]["json"]
    assert "output_dimensionality" not in body
    assert body["content"]["parts"][0]["text"] == format_code_retrieval_query("login handler")


def test_embed_document_uses_file_title():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"embedding": {"values": [1.0, 2.0]}}

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    with patch("app.indexing.gemini_embeddings.default_settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "test-key"
        mock_settings.GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
        mock_settings.GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
        mock_settings.GEMINI_EMBED_OUTPUT_DIMENSION = None
        mock_settings.GEMINI_EMBED_MAX_CHARS = 12000

        embedder = GeminiEmbeddingClient(mock_settings)
        embedder._client = mock_client

        vec = embedder.embed_document("class User:", title="models/user.py")

    assert vec == [1.0, 2.0]
    body = mock_client.post.call_args[1]["json"]
    assert body["content"]["parts"][0]["text"] == format_retrieval_document(
        "class User:", title="models/user.py"
    )


def test_missing_api_key_raises():
    with patch("app.indexing.gemini_embeddings.default_settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = ""
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiEmbeddingClient(mock_settings)
