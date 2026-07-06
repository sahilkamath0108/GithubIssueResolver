#!/usr/bin/env python3
"""
Truncate workflow-related tables for a fresh start.
Keeps github_users (OAuth sessions) and repo_index_state by default.

Usage (from repo root):
  docker compose exec backend python scripts/reset_workflow_data.py
  docker compose exec backend python scripts/reset_workflow_data.py --include-index-state
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/reset_workflow_data.py` from repo root or /app in Docker.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db.session import engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear workflow task data from PostgreSQL.")
    parser.add_argument(
        "--include-index-state",
        action="store_true",
        help="Also truncate repo_index_state (local index metadata; Qdrant vectors are separate).",
    )
    args = parser.parse_args()

    tables = [
        "task_logs",
        "task_steps",
        "task_results",
        "workflow_states",
        "dlq_tasks",
        "tasks",
    ]
    if args.include_index_state:
        tables.append("repo_index_state")

    sql = f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print(f"Cleared tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()
