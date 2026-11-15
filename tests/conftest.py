"""Each test owns a schema and lock key in a disposable PostgreSQL database."""

import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest


@pytest.fixture
def database():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.fail("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    schema = "fencing_" + uuid4().hex
    lock_key = uuid4().int % (2**63 - 1)

    @contextmanager
    def connect():
        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            conn.execute("SET statement_timeout = '10s'")
            conn.execute("SET lock_timeout = '5s'")
            yield conn

    with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            with connect() as conn:
                conn.execute(
                    (Path(__file__).parents[1] / "schema.sql").read_text()
                )
            yield connect, lock_key
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
