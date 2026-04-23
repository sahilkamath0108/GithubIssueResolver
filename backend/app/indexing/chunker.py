from __future__ import annotations

import ast
import logging
from app.core.settings import Settings, settings as default_settings
from app.indexing.schemas import TextChunk

logger = logging.getLogger(__name__)


class CodeChunker:
    """
    Splits source files into chunks suitable for embedding.
    Python: prefers top-level functions/classes (AST); falls back to line windows.
    Other languages: line-based windows with configurable max lines.
    """

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or default_settings

    def chunk_file(self, path: str, content: str) -> list[TextChunk]:
        if not content.strip():
            return []
        lower = path.lower()
        if lower.endswith(".py"):
            chunks = self._chunk_python(path, content)
            if chunks:
                return chunks
        return self._chunk_by_lines(path, content)

    def _chunk_python(self, path: str, content: str) -> list[TextChunk]:
        lines = content.splitlines(keepends=True)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            logger.debug("Python parse failed; using line chunks", extra={"path": path})
            return []

        max_lines = max(1, self._settings.INDEX_CHUNK_MAX_LINES)
        spans: list[tuple[str, int, int]] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", None) or 1
                end = getattr(node, "end_lineno", None) or start
                name = node.name
                kind = type(node).__name__.replace("Def", "").lower()
                chunk_id = f"{kind}:{name}:L{start}-L{end}"
                spans.append((chunk_id, start, end))
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue
            elif isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.AugAssign)):
                start = getattr(node, "lineno", None) or 1
                end = getattr(node, "end_lineno", None) or start
                spans.append((f"stmt:L{start}-L{end}", start, end))

        if not spans:
            return []

        chunks: list[TextChunk] = []
        for chunk_id, start, end in spans:
            segment = self._slice_lines(lines, start, end)
            if not segment.strip():
                continue
            seg_lines = segment.count("\n") + (0 if segment.endswith("\n") else 1)
            if seg_lines > max_lines:
                sub = self._chunk_by_lines(path, segment, start_line=start)
                for c in sub:
                    chunks.append(
                        TextChunk(
                            chunk_id=f"{chunk_id}>{c.chunk_id}",
                            text=c.text,
                            start_line=c.start_line,
                            end_line=c.end_line,
                        )
                    )
            else:
                chunks.append(TextChunk(chunk_id=chunk_id, text=segment, start_line=start, end_line=end))
        return chunks

    def _slice_lines(self, lines: list[str], start_line: int, end_line: int) -> str:
        # ast line numbers are 1-based inclusive
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        return "".join(lines[start_idx:end_idx])

    def _chunk_by_lines(
        self,
        path: str,
        content: str,
        *,
        start_line: int = 1,
    ) -> list[TextChunk]:
        lines = content.splitlines(keepends=True)
        max_lines = max(1, self._settings.INDEX_CHUNK_MAX_LINES)
        overlap = max(0, min(self._settings.INDEX_CHUNK_OVERLAP_LINES, max_lines - 1))
        stride = max(1, max_lines - overlap)
        chunks: list[TextChunk] = []
        i = 0
        line_no = start_line
        while i < len(lines):
            window = lines[i : i + max_lines]
            if not window:
                break
            text = "".join(window)
            end_line = line_no + len(window) - 1
            chunk_id = f"lines:L{line_no}-L{end_line}"
            chunks.append(TextChunk(chunk_id=chunk_id, text=text, start_line=line_no, end_line=end_line))
            line_no += stride
            i += stride
        return chunks
