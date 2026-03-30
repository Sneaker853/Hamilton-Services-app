from pathlib import Path
import logging

from db import get_cursor

logger = logging.getLogger(__name__)
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

MIGRATION_LOCK_ID = 820305  # Arbitrary advisory lock ID for migrations


def run_migrations() -> None:
    with get_cursor() as (conn, cur):
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()

        # Acquire advisory lock to prevent concurrent migration runs
        cur.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
        try:
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

            migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            for migration_file in migration_files:
                filename = migration_file.name
                if filename in applied:
                    continue

                sql = migration_file.read_text(encoding="utf-8")
                try:
                    cur.execute(sql)
                    cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (filename,))
                    conn.commit()
                    logger.info("Applied migration: %s", filename)
                except Exception:
                    conn.rollback()
                    logger.exception("Migration failed: %s", filename)
                    raise
        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,))
            conn.commit()
