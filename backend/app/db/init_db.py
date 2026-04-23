from sqlalchemy import text
from app.db.session import engine, Base
import app.models  


def create_partitions(conn):
    """
    Create monthly partitions for task_logs.
    SQLAlchemy ORM cannot declare PARTITION BY — must be done via raw SQL.
    Add more partitions as needed or automate via a scheduled job.
    """
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'task_logs_2026_01'
            ) THEN
                CREATE TABLE task_logs_2026_01 PARTITION OF task_logs
                FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'task_logs_2026_02'
            ) THEN
                CREATE TABLE task_logs_2026_02 PARTITION OF task_logs
                FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'task_logs_2026_03'
            ) THEN
                CREATE TABLE task_logs_2026_03 PARTITION OF task_logs
                FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'task_logs_2026_04'
            ) THEN
                CREATE TABLE task_logs_2026_04 PARTITION OF task_logs
                FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
            END IF;
        END
        $$;
    """))


def init():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        create_partitions(conn)
        conn.commit()


if __name__ == "__main__":
    init()
