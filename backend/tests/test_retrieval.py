from app.services.retrieval import (
    apply_entrypoint_boost,
    build_search_queries,
    detect_entrypoint_paths,
    merge_search_hits,
    rank_retrieval_hits,
)


def test_build_search_queries_includes_primary_and_changes():
    plan = {
        "search_query": "counter increment onClick useState",
        "changes": ["Fix counter button handler", "Fix counter button handler"],
    }
    queries = build_search_queries(plan)
    assert queries[0] == "counter increment onClick useState"
    assert "Fix counter button handler" in queries
    assert len(queries) == 2


def test_merge_search_hits_keeps_best_score():
    merged = merge_search_hits(
        [
            [{"path": "src/a.py", "chunk": "alpha", "score": 0.7}],
            [{"path": "src/a.py", "chunk": "alpha", "score": 0.9}],
        ]
    )
    assert len(merged) == 1
    assert merged[0]["score"] == 0.9


def test_detect_entrypoint_paths_prefers_shallow_main_files():
    paths = [
        "src/components/Counter.tsx",
        "server/app.js",
        "server/redis/config.js",
        "src/deep/nested/main.py",
    ]
    detected = detect_entrypoint_paths(paths, max_paths=2)
    assert "server/app.js" in detected


def test_apply_entrypoint_boost_raises_entrypoint_score():
    hits = [
        {"path": "src/util.py", "chunk": "x", "score": 0.5},
        {"path": "server/app.js", "chunk": "y", "score": 0.5},
    ]
    boosted = apply_entrypoint_boost(hits)
    by_path = {h["path"]: h["score"] for h in boosted}
    assert by_path["server/app.js"] > by_path["src/util.py"]


def test_rank_retrieval_injects_missing_frontend_entrypoint():
    hits = [{"path": "frontend/components/Counter.tsx", "chunk": "jsx", "score": 0.8}]
    repo_paths = [
        "frontend/components/Counter.tsx",
        "frontend/components/navbar.tsx",
        "server/app.js",
    ]
    ranked = rank_retrieval_hits(hits, repo_paths=repo_paths, scope="frontend")
    paths = [h["path"] for h in ranked]
    assert "frontend/components/navbar.tsx" in paths
    assert "server/app.js" not in paths
