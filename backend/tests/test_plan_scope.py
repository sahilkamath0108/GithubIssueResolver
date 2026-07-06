from app.services.plan_scope import (
    collect_plan_target_paths,
    extract_paths_from_plan,
    filter_related_extra_paths,
    infer_scope_from_issue,
    is_backend_path,
    is_extra_path_related_to_targets,
    is_frontend_path,
    is_infra_path,
    merge_plan_constraints,
    resolve_scope,
)
from app.services.code_context_service import assign_target_files, _top_vector_paths


def test_infer_devops_scope_is_fullstack():
    body = (
        "Prometheus is configured to scrape host.docker.internal:5500, but lumina-api "
        "runs on the same Docker network as Prometheus."
    )
    assert infer_scope_from_issue("lumina-api target DOWN", body) == "fullstack"


def test_infra_path_detection():
    assert is_infra_path("docker-compose.yml")
    assert is_infra_path("monitoring/prometheus.yml")
    assert is_backend_path("monitoring/prometheus.yml")
    assert is_backend_path("docker-compose.yml")


def test_extract_paths_includes_yaml_configs():
    plan = {
        "changes": [
            "Update monitoring/prometheus.yml scrape target to lumina-api:5500",
            "Adjust docker-compose.yml network aliases",
        ]
    }
    paths = extract_paths_from_plan(plan)
    assert "monitoring/prometheus.yml" in paths
    assert "docker-compose.yml" in paths


def test_assign_target_files_keeps_prometheus_paths_when_scope_backend():
    plan = {
        "scope": "backend",
        "files_to_modify": ["monitoring/prometheus.yml", "docker-compose.yml"],
        "changes": ["Point Prometheus at lumina-api:5500 on the compose network"],
        "search_query": "prometheus scrape_configs lumina-api host.docker.internal",
    }
    out = assign_target_files(
        plan,
        [{"path": "monitoring/prometheus.yml", "chunk": "scrape_configs", "score": 0.9}],
        repo_paths=["monitoring/prometheus.yml", "docker-compose.yml"],
        max_files=8,
    )
    assert "monitoring/prometheus.yml" in out["files_to_modify"]
    assert "docker-compose.yml" in out["files_to_modify"]


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


def test_related_extra_path_same_api_folder():
    targets = ["frontend/utils/apis/eventsAPI.ts"]
    assert is_extra_path_related_to_targets("frontend/utils/apis/fetchWithAuth.ts", targets)
    assert not is_extra_path_related_to_targets("frontend/app/session/[sessionId]/page.tsx", targets)


def test_filter_related_extra_paths_caps_count():
    targets = ["frontend/utils/apis/eventsAPI.ts"]
    extras = [
        "frontend/utils/apis/fetchWithAuth.ts",
        "frontend/utils/apis/cartAPI.ts",
        "frontend/app/home/page.tsx",
    ]
    related, unrelated = filter_related_extra_paths(extras, targets, max_extra=1)
    assert len(related) == 1
    assert "frontend/app/home/page.tsx" in unrelated


def test_collect_plan_target_paths_merges_explicit_list_and_changes():
    plan = {
        "files_to_modify": ["src/App.jsx"],
        "changes": ["Also update src/components/List.tsx for keys"],
    }
    paths = collect_plan_target_paths(plan)
    assert paths == ["src/App.jsx", "src/components/List.tsx"]


def test_assign_target_files_uses_planner_files_to_modify():
    plan = {
        "scope": "frontend",
        "files_to_modify": ["src/App.jsx"],
        "changes": ["Add unique keys in src/App.jsx"],
        "search_query": "React key prop list children",
    }
    out = assign_target_files(plan, [], repo_paths=["src/App.jsx"], max_files=8)
    assert out["files_to_modify"] == ["src/App.jsx"]


def test_top_vector_paths_caps_at_five():
    chunks = [
        {"path": f"frontend/f{i}.ts", "chunk": "x", "score": 1.0 - i * 0.1}
        for i in range(8)
    ]
    paths = _top_vector_paths(chunks, "frontend", limit=5)
    assert len(paths) == 5
    assert paths[0] == "frontend/f0.ts"


def test_assign_target_files_merges_planner_with_top_vector_for_modify_and_fetch():
    plan = {
        "scope": "frontend",
        "files_to_modify": ["frontend/utils/apis/eventsAPI.ts"],
        "changes": ["Update frontend/utils/apis/eventsAPI.ts to propagate errors"],
        "search_query": "React Query error eventsAPI",
    }
    repo_paths = [
        "frontend/utils/apis/eventsAPI.ts",
        "frontend/utils/apis/cartAPI.ts",
        "frontend/utils/providers/queryProvider.tsx",
    ]
    vector_chunks = [
        {"path": "frontend/utils/apis/cartAPI.ts", "chunk": "x", "score": 0.99},
        {"path": "frontend/utils/providers/queryProvider.tsx", "chunk": "y", "score": 0.95},
    ]
    out = assign_target_files(plan, vector_chunks, repo_paths=repo_paths, max_files=8)
    assert out["files_to_modify"] == [
        "frontend/utils/apis/eventsAPI.ts",
        "frontend/utils/apis/cartAPI.ts",
        "frontend/utils/providers/queryProvider.tsx",
    ]
    assert out["files_to_fetch"] == out["files_to_modify"]
    assert out["_vector_modify_paths"] == [
        "frontend/utils/apis/cartAPI.ts",
        "frontend/utils/providers/queryProvider.tsx",
    ]
    assert out["_vector_context_paths"] == []


def test_assign_target_files_prefers_plan_paths_over_backend_vector_hits():
    plan = {
        "scope": "frontend",
        "constraints": ["No backend changes"],
        "files_to_modify": [
            "frontend/app/my-registrations/page.tsx",
            "frontend/components/navbar.tsx",
        ],
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
    assert len(targets) == 3
    assert targets[0] == "frontend/app/my-registrations/page.tsx"
    assert "frontend/components/navbar.tsx" in targets
    assert "frontend/utils/apis/ordersAPI.ts" in targets
    assert not any(is_backend_path(p) for p in targets)
    assert out["files_to_fetch"] == targets
    assert "frontend/app/my-registrations/page.tsx" in out["_files_to_create"]


def test_merge_constraints_from_issue():
    issue = {"title": "UI", "body": "No backend changes required."}
    plan = {"scope": "fullstack", "constraints": []}
    merged = merge_plan_constraints(plan, issue)
    assert "No backend changes" in merged
    assert resolve_scope(plan, issue) == "frontend"


def test_frontend_path_uses_backend_denylist_not_allowlist():
    assert is_frontend_path("frontend/app/foo/page.tsx")
    assert is_frontend_path("src/App.jsx")
    assert is_frontend_path("src/components/Counter.tsx")
    assert is_frontend_path("client/src/pages/Home.tsx")
    assert is_frontend_path("src/main.py")
    assert is_backend_path("server/controllers/ordersController.js")
    assert not is_frontend_path("server/app.js")
