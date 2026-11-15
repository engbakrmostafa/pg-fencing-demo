"""Deterministic regressions for a stale scheduler and transactional fencing."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import psycopg
import pytest

from fencing import StaleLeader, try_acquire, write_result


def acknowledge_lock_release(connection, key):
    # A close() is not a server acknowledgement. Block on the actual PG lock
    # once, then commit its release before the next pg_try_advisory_lock.
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (key,))


@pytest.mark.parametrize("existing_result", [False, True], ids=["insert", "update"])
def test_stale_worker_cannot_write_after_handover(database, existing_result):
    connect, key = database
    worker_ready = Event()
    allow_late_write = Event()

    with connect() as old_leader, connect() as new_leader:
        old_epoch = try_acquire(old_leader, key)
        assert old_epoch == 1

        def old_worker():
            # A separate pooled connection survives the leadership session.
            with connect() as writer:
                worker_ready.set()
                assert allow_late_write.wait(5), "handover did not finish"
                try:
                    write_result(writer, old_epoch, "scan-1", "obsolete")
                except StaleLeader:
                    return "rejected"
                return "accepted"

        with ThreadPoolExecutor(max_workers=1) as executor:
            late_write = executor.submit(old_worker)
            try:
                assert worker_ready.wait(5), "old worker did not start"
                old_leader.close()
                acknowledge_lock_release(new_leader, key)
                assert try_acquire(new_leader, key) == 2

                with connect() as writer:
                    current_job = "scan-1" if existing_result else "other-scan"
                    write_result(writer, 2, current_job, "current")

                allow_late_write.set()
                verdict = late_write.result(timeout=10)
            finally:
                # Also release the worker if an assertion or DB call failed.
                allow_late_write.set()

        with connect() as observer:
            stored = observer.execute(
                "SELECT epoch, value FROM scheduler_result "
                "WHERE job_id = 'scan-1'"
            ).fetchone()

        expected = (2, "current") if existing_result else None
        assert (verdict, stored) == ("rejected", expected)


def test_guard_locks_leader_row_until_the_write_transaction_commits(database):
    connect, key = database
    with connect() as leader, connect() as writer, connect() as probe:
        assert try_acquire(leader, key) == 1

        with writer.transaction():
            write_result(writer, 1, "scan-1", "current")
            # This conflicts with the epoch UPDATE used during takeover.
            # NOWAIT gives an immediate deterministic answer, not a timed guess.
            with pytest.raises(psycopg.errors.LockNotAvailable):
                with probe.transaction():
                    probe.execute(
                        "SELECT epoch FROM scheduler_leader "
                        "WHERE name = 'scheduler' FOR NO KEY UPDATE NOWAIT"
                    )

        # The fence is transaction scoped, not leaked past the commit.
        with probe.transaction():
            assert probe.execute(
                "SELECT epoch FROM scheduler_leader "
                "WHERE name = 'scheduler' FOR NO KEY UPDATE NOWAIT"
            ).fetchone() == (1,)


def test_missing_leader_metadata_fails_closed(database):
    connect, key = database
    with connect() as leader, connect() as writer:
        assert try_acquire(leader, key) == 1
        writer.execute("DELETE FROM scheduler_leader")

        with pytest.raises(StaleLeader):
            write_result(writer, 1, "scan-1", "unowned")

        assert writer.execute(
            "SELECT count(*) FROM scheduler_result"
        ).fetchone() == (0,)


def test_stale_error_escaping_outer_transaction_rolls_back_earlier_work(database):
    connect, key = database
    with connect() as old_leader:
        assert try_acquire(old_leader, key) == 1

    with connect() as new_leader, connect() as writer:
        acknowledge_lock_release(new_leader, key)
        assert try_acquire(new_leader, key) == 2

        # Catch outside the outer context: a nested transaction is a savepoint,
        # and swallowing its error inside the outer context would allow commit.
        with pytest.raises(StaleLeader):
            with writer.transaction():
                write_result(writer, 2, "valid-but-uncommitted", "current")
                write_result(writer, 1, "late", "obsolete")

        assert writer.execute(
            "SELECT count(*) FROM scheduler_result"
        ).fetchone() == (0,)
