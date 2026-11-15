# Test-first execution evidence

This is a newly written public demonstration, not a historical client incident.

## Environment

- Local verification: Python 3.12.3, PostgreSQL 16.15, psycopg 3.2.10, pytest 8.4.2.
- GitHub Actions uses Python 3.12 and a real PostgreSQL 16 service.
- Tests create isolated schemas in a disposable database.
- No sleeps, stress-loop repetitions, production secrets, or private source code.

## Commit order

1. Baseline on main: `cb41823cb499566e2ad182f311d90cc977f434bc`.
   Three smoke tests passed; the database function intentionally did not fence writes.
2. First PR commit: `ca58c9abb259ff3f64ae5070b225a9d8194da588`.
   Changes only test files. Five new regression cases failed, while the three smoke tests passed.
3. Second PR commit: adds the leader-row lock and epoch rejection to the database function.
   The unchanged test suite passes all eight cases.

[Verified failing GitHub Actions run for the first PR commit](https://github.com/engbakrmostafa/pg-fencing-demo/actions/runs/43682157907)

The PR's Checks tab records the fixed commit's GitHub Actions result.

## Observed failure

Command: `python3 -m pytest -q --tb=short`

```text
test_stale_worker_cannot_write_after_handover[insert]
  ('accepted', (1, 'obsolete')) != ('rejected', None)
test_stale_worker_cannot_write_after_handover[update]
  ('accepted', (1, 'obsolete')) != ('rejected', (2, 'current'))
test_guard_locks_leader_row_until_the_write_transaction_commits
  DID NOT RAISE LockNotAvailable
test_missing_leader_metadata_fails_closed
  DID NOT RAISE StaleLeader
test_stale_error_escaping_outer_transaction_rolls_back_earlier_work
  DID NOT RAISE StaleLeader
5 failed, 3 passed
```

The GitHub failure log independently reports the same five assertion failures; this is not a dependency-install or collection failure.

## Observed fixed result

Command: `python3 -m pytest -q`

```text
........                                                                 [100%]
8 passed
```

## What makes the tests deterministic

The old job captures epoch 1 and opens its own business connection, then signals readiness and waits on an Event. The test closes the old advisory-lock session, obtains and releases a transaction advisory lock as a server-side cleanup acknowledgement, activates epoch 2, and writes a current result. Only then does it release the old worker.

The lock-lifetime test keeps the write transaction open and requests `FOR NO KEY UPDATE NOWAIT` from another connection. This requests the same conflicting lock mode needed by an epoch update and immediately proves whether the write retained its fence; it does not infer blocking from elapsed time.

Event and database timeouts bound broken tests. They do not determine the tested interleaving. The worker's release event is also set in `finally`, and its Future is read so failures are not lost in a background thread.

## Guarantee boundary

The database guard prevents old-epoch inserts and updates through the demonstrated function after the successor's epoch has committed. It fails closed on missing metadata, and a stale error escaping an outer transaction rolls back earlier writes in that transaction.

This sample does not claim instantaneous revocation at session loss, role-based protection from arbitrary owner-role SQL, or exactly-once external effects. A job already authorized under the leader-row lock is ordered before takeover; the successor must wait for that transaction.
