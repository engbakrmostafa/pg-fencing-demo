"""A deliberately small PostgreSQL scheduler leadership example."""

from __future__ import annotations

import psycopg
from psycopg.pq import TransactionStatus


class StaleLeader(RuntimeError):
    """The database refused a job's obsolete or invalid fencing token."""


def try_acquire(connection: psycopg.Connection, lock_key: int) -> int | None:
    """Acquire once on a fresh, dedicated autocommit connection.

    Keep the connection open while scheduling. Closing it releases leadership.
    The returned epoch is usable only after its increment commits.
    """
    if not connection.autocommit:
        raise ValueError("leadership requires an autocommit connection")
    if connection.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("leadership requires an idle connection")

    acquired = connection.execute(
        "SELECT pg_try_advisory_lock(%s)", (lock_key,)
    ).fetchone()[0]
    if not acquired:
        return None

    try:
        with connection.transaction():
            row = connection.execute(
                "UPDATE scheduler_leader SET epoch = epoch + 1 "
                "WHERE name = 'scheduler' RETURNING epoch"
            ).fetchone()
            if row is None:
                raise RuntimeError("permanent scheduler leader row is missing")
        return row[0]
    except BaseException:
        # A failed acquisition must not leave a live session owning the lock.
        connection.close()
        raise


def write_result(
    connection: psycopg.Connection, epoch: int, job_id: str, value: str
) -> None:
    """Persist a result via the database's sole demonstrated write operation."""
    try:
        with connection.transaction():
            connection.execute(
                "SELECT store_result(%s, %s, %s)", (epoch, job_id, value)
            )
    except psycopg.errors.RaiseException as error:
        raise StaleLeader("database rejected the scheduler epoch") from error
