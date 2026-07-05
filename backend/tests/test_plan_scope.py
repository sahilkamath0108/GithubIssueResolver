from app.services.code_context_service import assign_target_files
from app.services.plan_scope import (
    extract_paths_from_plan,
    infer_scope_from_issue,
    is_backend_path,
    is_frontend_path,
    merge_plan_constraints,
    resolve_scope,
)


def test_infer_frontend_scope_from_issue():
    assert infer_scope_from_issue("My Registrations page", "No backend changes required.") == "frontend"


def test_extract_paths_from_plan_changes():
    plan = {
        "changes": [
            "Add frontend/app/my-registrations/page.tsx",
            "Update frontend/components/navbar.tsx to add link",
            "Use frontend/utils/apis/ordersAPI.ts or similar",
        ]
    }
    paths = extract_paths_from_plan(plan)
    assert "frontend/app/my-registrations/page.tsx" in paths
    assert "frontend/components/navbar.tsx" in paths
    assert "frontend/utils/apis/ordersAPI.ts" in paths


def test_assign_target_files_prefers_plan_paths_over_backend_vector_hits():
    plan = {
        "scope": "frontend",
        "constraints": ["No backend changes"],
        "changes": [
            "Add frontend/app/my-registrations/page.tsx",
            "Update frontend/components/navbar.tsx",
        ],
        "search_query": "registrations orders navbar",
    }
    repo_paths = [
        "frontend/components/navbar.tsx",
        "frontend/utils/apis/ordersAPI.ts",
        "frontend/app/order-confirmation/page.tsx",
        "server/controllers/ordersController.js",
        "server/app.js",
    ]
    vector_chunks = [
        {"path": "server/controllers/ordersController.js", "chunk": "x", "score": 0.99},
        {"path": "server/routes/ordersRoutes.js", "chunk": "y", "score": 0.95},
        {"path": "frontend/utils/apis/ordersAPI.ts", "chunk": "z", "score": 0.5},
    ]
    issue = {"title": "Registrations", "body": "No backend changes required."}
    out = assign_target_files(plan, vector_chunks, repo_paths=repo_paths, issue=issue, max_files=5)
    targets = out["files_to_modify"]
    assert targets[0] == "frontend/app/my-registrations/page.tsx"
    assert "frontend/components/navbar.tsx" in targets
    assert not any(is_backend_path(p) for p in targets)
    assert "frontend/app/my-registrations/page.tsx" in out["_files_to_create"]


def test_merge_constraints_from_issue():
    issue = {"title": "UI", "body": "No backend changes required."}
    plan = {"scope": "fullstack", "constraints": []}
    merged = merge_plan_constraints(plan, issue)
    assert "No backend changes" in merged
    assert resolve_scope(plan, issue) == "frontend"


def test_frontend_path_detection():
    assert is_frontend_path("frontend/app/foo/page.tsx")
    assert is_backend_path("server/controllers/ordersController.js")
    assert not is_frontend_path("server/app.js")
