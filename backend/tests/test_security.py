import pytest

from app.core.security import (
    assert_repo_allowed,
    parse_github_issue_url,
    parse_github_repo_url,
    sanitize_repo_path,
    verify_api_key,
)


class TestGitHubUrlValidation:
    def test_valid_repo_url(self):
        assert parse_github_repo_url("https://github.com/octocat/Hello-World") == "octocat/Hello-World"

    def test_rejects_non_github_host(self):
        with pytest.raises(ValueError, match="github.com"):
            parse_github_repo_url("https://evil.example.com/octocat/Hello-World")

    def test_valid_issue_url(self):
        slug, num = parse_github_issue_url("https://github.com/octocat/Hello-World/issues/42")
        assert slug == "octocat/Hello-World"
        assert num == 42

    def test_rejects_invalid_issue_url(self):
        with pytest.raises(ValueError):
            parse_github_issue_url("https://github.com/octocat/Hello-World/pull/1")


class TestPathSanitization:
    def test_accepts_normal_path(self):
        assert sanitize_repo_path("src/main.py") == "src/main.py"

    def test_rejects_traversal(self):
        with pytest.raises(ValueError):
            sanitize_repo_path("../secret.env")

    def test_rejects_absolute(self):
        with pytest.raises(ValueError):
            sanitize_repo_path("/etc/passwd")


class TestRepoAllowlist:
    def test_allowlist_empty_allows_all(self, monkeypatch):
        monkeypatch.setattr("app.core.security.settings.REPO_ALLOWLIST", "")
        assert_repo_allowed("any/one")

    def test_allowlist_blocks_unknown(self, monkeypatch):
        monkeypatch.setattr("app.core.security.settings.REPO_ALLOWLIST", "allowed/repo")
        with pytest.raises(ValueError, match="REPO_ALLOWLIST"):
            assert_repo_allowed("other/repo")

    def test_allowlist_allows_listed(self, monkeypatch):
        monkeypatch.setattr("app.core.security.settings.REPO_ALLOWLIST", "allowed/repo")
        assert_repo_allowed("allowed/repo")


class TestApiKey:
    def test_empty_key_allows_all(self, monkeypatch):
        monkeypatch.setattr("app.core.security.settings.API_KEY", "")
        assert verify_api_key(None) is True
        assert verify_api_key("anything") is True

    def test_timing_safe_compare(self, monkeypatch):
        monkeypatch.setattr("app.core.security.settings.API_KEY", "secret-key")
        assert verify_api_key("secret-key") is True
        assert verify_api_key("wrong") is False
