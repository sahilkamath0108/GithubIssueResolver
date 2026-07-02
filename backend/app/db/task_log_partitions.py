"""Monthly RANGE partitions for task_logs (PostgreSQL)."""
from __future__ import annotations

from datetime import date
from threading import Lock

from sqlalchemy import text
from sqlalchemy.engine import Connection

_partition_lock = Lock()
_ensured_months: set[tuple[int, int]] = set()


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def ensure_task_log_partitions(
    conn: Connection,
    *,
    anchor: date | None = None,
    months_back: int = 2,
    months_forward: int = 12,
) -> None:
    """
    Create missing monthly partitions for task_logs.
    Safe to call repeatedly (uses CREATE TABLE IF NOT EXISTS).
    """
    anchor = anchor or date.today()
    start = _add_months(_month_start(anchor), -months_back)
    end = _add_months(_month_start(anchor), months_forward + 1)

    cur = start
    while cur < end:
        nxt = _add_months(cur, 1)
        part_name = f"task_logs_{cur.year}_{cur.month:02d}"
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {part_name} PARTITION OF task_logs
                FOR VALUES FROM (:from_d) TO (:to_d)
                """
            ),
            {"from_d": cur.isoformat(), "to_d": nxt.isoformat()},
        )
        cur = nxt


def ensure_task_log_partition_cached(for_day: date | None = None) -> None:
    """Ensure the partition for for_day exists (once per month per process)."""
    day = for_day or date.today()
    key = (day.year, day.month)
    if key in _ensured_months:
        return
    with _partition_lock:
        if key in _ensured_months:
            return
        from app.db.session import engine

        with engine.connect() as conn:
            ensure_task_log_partitions(conn, anchor=day, months_back=0, months_forward=0)
            conn.commit()
        _ensured_months.add(key)
