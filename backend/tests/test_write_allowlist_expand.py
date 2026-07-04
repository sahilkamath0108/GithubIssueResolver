from unittest.mock import patch

import pytest

from app.services.code_context_service import expand_write_allowlist


def test_expand_write_allowlist_merges_and_fetches():
    plan = {"files_to_modify": ["server/app.js"]}
    repo_files = [{"path": "server/app.js", "content": "app"}]

    with patch("app.services.github_service.get_file_contents") as mock_fetch:
        mock_fetch.return_value = [{"path": "server/redis/config.js", "content": "redis cfg"}]
        new_plan, new_files, planned = expand_write_allowlist(
            plan,
            repo_files,
            ["server/redis/config.js"],
            repo_url="https://github.com/o/r",
        )

    assert "server/redis/config.js" in new_plan["files_to_modify"]
    assert new_plan["_allowlist_expanded"] is True
    assert any(f["path"] == "server/redis/config.js" for f in new_files)
    mock_fetch.assert_called_once()
    assert "server/redis/config.js" in planned


def test_expand_write_allowlist_rejects_only_invalid_paths():
    plan = {"files_to_modify": ["a.js"]}
    with patch("app.services.github_service.get_file_contents") as mock_fetch:
        with pytest.raises(ValueError, match="No valid extra paths"):
            expand_write_allowlist(
                plan,
                [],
                ["../evil.js"],
                repo_url="https://github.com/o/r",
            )
    mock_fetch.assert_not_called()
