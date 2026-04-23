from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TreeBlobFile:
    """A single blob (file) entry from a git tree."""

    path: str
    blob_sha: str
    size: int


@dataclass(frozen=True)
class TextChunk:
    """A chunk of source ready for embedding."""

    chunk_id: str
    text: str
    start_line: int
    end_line: int


@dataclass
class IndexRunResult:
    """Summary returned by indexing operations."""

    repo: str
    mode: Literal["full", "incremental", "skipped"]
    commit_sha: str
    files_indexed: int = 0
    chunks_written: int = 0
    files_deleted: int = 0
    files_skipped_unchanged: int = 0
    message: str = ""
