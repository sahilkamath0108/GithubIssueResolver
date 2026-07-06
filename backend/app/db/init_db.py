from sqlalchemy import text
from app.db.session import engine, Base
from app.db.task_log_partitions import ensure_task_log_partitions
import app.models


def ensure_enums(conn):
    """Create PostgreSQL ENUM types if missing (idempotent for Supabase reruns)."""
    conn.execute(text("""
        DO $$ BEGIN
            CREATE TYPE taskstatus AS ENUM ('queued', 'running', 'success', 'failed', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """))


def ensure_schema_compat(conn):
    """
    Small forward-only schema fixes for local/dev environments.
    `create_all` won't alter existing columns, so we do lightweight ALTERs here.
    """
    # dlq_tasks.original_task_id used to be UUID; now stored as TEXT.
    # Safe for existing UUID values and for integer ids stored as strings.
    conn.execute(text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'dlq_tasks'
                  AND column_name = 'original_task_id'
                  AND data_type = 'uuid'
            ) THEN
                ALTER TABLE dlq_tasks
                ALTER COLUMN original_task_id TYPE TEXT
                USING original_task_id::text;
            END IF;
        END
        $$;
    """))
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tasks' AND column_name = 'github_user_id'
            ) THEN
                ALTER TABLE tasks ADD COLUMN github_user_id BIGINT NULL;
                CREATE INDEX IF NOT EXISTS ix_tasks_github_user_id ON tasks (github_user_id);
            END IF;
        END
        $$;
    """))
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tasks' AND column_name = 'celery_task_id'
            ) THEN
                ALTER TABLE tasks ADD COLUMN celery_task_id VARCHAR(255) NULL;
            END IF;
        END
        $$;
    """))
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'taskstatus' AND e.enumlabel = 'cancelled'
            ) THEN
                ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'cancelled';
            END IF;
        END
        $$;
    """))
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'github_users' AND column_name = 'groq_api_key_encrypted'
            ) THEN
                ALTER TABLE github_users ADD COLUMN groq_api_key_encrypted TEXT NULL;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'github_users' AND column_name = 'jina_api_key_encrypted'
            ) THEN
                ALTER TABLE github_users ADD COLUMN jina_api_key_encrypted TEXT NULL;
            END IF;
        END
        $$;
    """))
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'repo_index_state' AND column_name = 'embedding_model'
            ) THEN
                ALTER TABLE repo_index_state ADD COLUMN embedding_model VARCHAR(128) NULL;
            END IF;
        END
        $$;
    """))


def init():
    with engine.connect() as conn:
        ensure_enums(conn)
        conn.commit()
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        ensure_task_log_partitions(conn)
        ensure_schema_compat(conn)
        conn.commit()


if __name__ == "__main__":
    init()
