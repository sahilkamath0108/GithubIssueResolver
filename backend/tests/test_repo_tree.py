from app.domain.agents.prompt_guard import wrap_repo_tree_for_planner
from app.services.repo_tree import format_path_list_for_planner, should_skip_tree_path


def test_should_skip_tree_path_ignores_vendor_dirs():
    assert should_skip_tree_path("node_modules/react/index.js")
    assert should_skip_tree_path("frontend/node_modules/lodash.js")
    assert not should_skip_tree_path("src/components/Counter.tsx")
    assert not should_skip_tree_path(".github/workflows/ci.yml")


def test_format_path_list_for_planner_includes_header():
    text = format_path_list_for_planner(
        ["src/app.py", "tests/test_app.py"],
        repo_full_name="owner/repo",
        branch="main",
        max_chars=8000,
    )
    assert "owner/repo" in text
    assert "src/app.py" in text
    assert "tests/test_app.py" in text


def test_wrap_repo_tree_for_planner_delimits_content():
    wrapped = wrap_repo_tree_for_planner("src/main.py\nsrc/util.py")
    assert "REPOSITORY FILE TREE" in wrapped
    assert "END REPOSITORY FILE TREE" in wrapped
    assert "src/main.py" in wrapped
