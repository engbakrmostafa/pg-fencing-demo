# PostgreSQL Fencing Demo Implementation Plan

> For agentic workers: execute the authorized small demonstration in order, retaining separate failing-test and fix commits.

**Goal:** Show a reproducible stale-leader defect and its transactionally correct fix in a public PR.
**Architecture:** Dedicated session advisory lock; persistent increasing epoch; protected database function; real PostgreSQL integration tests.
**Tech Stack:** Python 3.12, psycopg 3, pytest, PostgreSQL 16, GitHub Actions.
**Spec:** docs/design.md

## Constraints and review focus

Use newly written public sample code only. No production credentials or deployment.
No sleeps or repeated race attempts. Event timeouts only bound a hung test.
Check stale inserts, stale updates, missing epoch metadata, transaction rollback, and handover serialization.
The sample does not provide crash-proof external delivery or a complete heartbeat lease.

## Task 1: Seed the honest baseline

Files: fencing.py, schema.sql, tests/conftest.py, tests/test_baseline.py, README.md, compose.yaml, requirements.txt, pytest.ini, .github/workflows/tests.yml.
- [ ] Define the minimal interfaces: try_acquire(connection, lock_key) -> int | None; write_result(connection, epoch, job_id, value) -> None.
- [ ] Run the baseline against PostgreSQL 16 and commit it on main.
- [ ] Create the public repository.

## Task 2: Test-first fencing PR

Files: tests/test_fencing.py, schema.sql.
- [ ] Use Events to pause a worker with epoch 1, close its leader session, activate epoch 2, then release the stale write. Assert StaleLeader and unchanged result rows.
- [ ] Assert store_result holds the leader-row lock until transaction end with FOR UPDATE NOWAIT on another connection.
- [ ] Assert missing metadata fails closed and stale errors roll back earlier changes in the same transaction.
- [ ] Run tests and record assertion failures; commit and push tests only.
- [ ] Add SELECT FOR UPDATE and epoch validation inside store_result before its upsert.
- [ ] Run unchanged suite, record success, and commit the fix separately.
- [ ] Review, push, open PR, and verify PostgreSQL CI.
