"""
CLI for repository indexing (GitHub API → Gemini → Qdrant).

Uses :meth:`RepoIndexer.sync_repo` so first run is a full index, later runs are incremental
unless you pass ``--force-full``.

From the ``backend`` directory (with env vars set, same as the API), for example::

    python scripts/index_repo.py owner/repo
    python scripts/index_repo.py owner/repo --force-full
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Sync a GitHub repo into Qdrant (auto full vs incremental from stored commit).",
    )
    parser.add_argument("repo", help='Repository as "owner/name"')
    parser.add_argument(
        "--force-full",
        action="store_true",
        help="Clear all vectors for this repo in Qdrant and reindex every file.",
    )
    args = parser.parse_args()

    from app.db.session import SessionLocal
    from app.indexing import RepoIndexer

    with SessionLocal() as db:
        indexer = RepoIndexer(db)
        try:
            result = indexer.sync_repo(args.repo, force_full=args.force_full)
        finally:
            indexer.close()

    print(result)


if __name__ == "__main__":
    main()
