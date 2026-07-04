from unittest.mock import MagicMock, patch

import pytest

from app.indexing.jina_embeddings import JinaEmbeddingClient


def test_embed_query_uses_retrieval_query_task():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    with patch("app.indexing.jina_embeddings.default_settings") as mock_settings:
        mock_settings.JINA_API_KEY = "test-key"
        mock_settings.JINA_API_BASE_URL = "https://api.jina.ai/v1"
        mock_settings.JINA_EMBEDDING_MODEL = "jina-embeddings-v5-text-small"
        mock_settings.JINA_QUERY_TASK = "retrieval.query"
        mock_settings.JINA_DOCUMENT_TASK = "retrieval.passage"
        mock_settings.JINA_EMBED_NORMALIZED = True
        mock_settings.JINA_EMBED_OUTPUT_DIMENSION = None
        mock_settings.JINA_EMBED_MAX_CHARS = 12000
        mock_settings.JINA_EMBED_BATCH_SIZE = 16
        mock_settings.QDRANT_EMBEDDING_DIM = None

        embedder = JinaEmbeddingClient(mock_settings)
        embedder._client = mock_client

        vec = embedder.embed_query("auth middleware")

    assert vec == [0.1, 0.2, 0.3]
    body = mock_client.post.call_args[1]["json"]
    assert body["task"] == "retrieval.query"
    assert body["normalized"] is True
    assert body["input"] == ["auth middleware"]
    assert "dimensions" not in body


def test_embed_document_uses_retrieval_passage_and_title():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": [1.0, 2.0]}]}

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    with patch("app.indexing.jina_embeddings.default_settings") as mock_settings:
        mock_settings.JINA_API_KEY = "test-key"
        mock_settings.JINA_API_BASE_URL = "https://api.jina.ai/v1"
        mock_settings.JINA_EMBEDDING_MODEL = "jina-embeddings-v5-text-small"
        mock_settings.JINA_QUERY_TASK = "retrieval.query"
        mock_settings.JINA_DOCUMENT_TASK = "retrieval.passage"
        mock_settings.JINA_EMBED_NORMALIZED = True
        mock_settings.JINA_EMBED_OUTPUT_DIMENSION = None
        mock_settings.JINA_EMBED_MAX_CHARS = 12000
        mock_settings.JINA_EMBED_BATCH_SIZE = 16
        mock_settings.QDRANT_EMBEDDING_DIM = 2

        embedder = JinaEmbeddingClient(mock_settings)
        embedder._client = mock_client

        vec = embedder.embed_document("class User:", title="models/user.py")

    assert vec == [1.0, 2.0]
    body = mock_client.post.call_args[1]["json"]
    assert body["task"] == "retrieval.passage"
    assert body["input"] == ["models/user.py\nclass User:"]


def test_create_embedding_client_jina():
    from app.indexing.embedding_client import create_embedding_client

    with patch("app.indexing.embedding_client.JinaEmbeddingClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        with patch("app.indexing.embedding_client.default_settings") as mock_settings:
            mock_settings.EMBEDDING_PROVIDER = "jina"
            client = create_embedding_client(mock_settings)
            mock_cls.assert_called_once_with(mock_settings)
            assert client is mock_cls.return_value


def test_missing_jina_api_key_raises():
    with patch("app.indexing.jina_embeddings.default_settings") as mock_settings:
        mock_settings.JINA_API_KEY = ""
        with pytest.raises(ValueError, match="JINA_API_KEY"):
            JinaEmbeddingClient(mock_settings)
