from contextlib import contextmanager
from typing import Generator
import logging

import psycopg2
import psycopg2.pool
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL, DB_POOL_MIN, DB_POOL_MAX

logger = logging.getLogger(__name__)

_db_pool: ThreadedConnectionPool | None = None

DB_QUERY_TIMEOUT_MS = 30_000  # 30 seconds default statement timeout


def init_db_pool() -> None:
    global _db_pool
    if _db_pool is None:
        _db_pool = ThreadedConnectionPool(DB_POOL_MIN, DB_POOL_MAX, dsn=DATABASE_URL)
        logger.info("Database pool initialized (min=%s, max=%s)", DB_POOL_MIN, DB_POOL_MAX)


def close_db_pool() -> None:
    global _db_pool
    if _db_pool is not None:
        _db_pool.closeall()
        _db_pool = None
        logger.info("Database pool closed")


@contextmanager
def get_db_connection() -> Generator:
    if _db_pool is None:
        raise RuntimeError("Database pool is not initialized")

    conn = None
    try:
        conn = _db_pool.getconn()
    except psycopg2.pool.PoolError:
        logger.error("Database connection pool exhausted")
        raise RuntimeError("Database connection pool exhausted — try again shortly")

    try:
        yield conn
    finally:
        if conn:
            _db_pool.putconn(conn)


@contextmanager
def get_cursor(dict_cursor: bool = False, timeout_ms: int = DB_QUERY_TIMEOUT_MS) -> Generator:
    with get_db_connection() as conn:
        if dict_cursor:
            cur = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cur = conn.cursor()

        try:
            cur.execute("SET LOCAL statement_timeout = %s", (timeout_ms,))
            yield conn, cur
        finally:
            cur.close()


def check_db_health() -> bool:
    try:
        with get_cursor() as (_, cur):
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False
