from contextlib import contextmanager
from typing import Generator
import logging

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL, DB_POOL_MIN, DB_POOL_MAX

logger = logging.getLogger(__name__)

_db_pool: ThreadedConnectionPool | None = None


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

    conn = _db_pool.getconn()
    try:
        yield conn
    finally:
        _db_pool.putconn(conn)


@contextmanager
def get_cursor(dict_cursor: bool = False) -> Generator:
    with get_db_connection() as conn:
        if dict_cursor:
            cur = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cur = conn.cursor()

        try:
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
