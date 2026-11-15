# PostgreSQL fencing demo

A small Python 3.12 / PostgreSQL 16 work sample showing why leader election alone does not fence writes from an old scheduler.

This repository was created as a fresh, synthetic demonstration. It is not a historical production incident or copied client code. The main branch is an intentionally incomplete baseline: it elects one advisory-lock owner and allocates epochs, but does not enforce epochs when storing results. The accompanying pull request adds deterministic regression tests first and the database guard second.

## Evidence

See [the recorded red/green results](docs/evidence.md) on the PR branch.

## Run

Use a disposable PostgreSQL database; tests create and remove their own randomly named schemas.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
docker compose up -d --wait
export TEST_DATABASE_URL=postgresql://postgres:demo-only@127.0.0.1:55439/fencing_demo
pytest -q
docker compose down -v
```

The Compose password is a published disposable test value, not a production credential. PostgreSQL is bound to localhost. Tests require PostgreSQL and do not silently substitute SQLite.

## Contract

- A dedicated connection acquires a session advisory lock; each acquisition increments the permanent leader row's epoch in a committed transaction.
- Each job retains the epoch under which it started. A fresh connection must be used for each acquisition attempt; do not re-enter a session lock.
- Results are persisted through `store_result`, called by `write_result`.
- The fixed implementation locks the leader row, rejects a missing or stale epoch with a database exception, and writes in the same transaction.
- The epoch increment and protected writes contend on the same row. A protected transaction authorized before takeover can finish; takeover becomes active only when its new epoch commits.
- Tests use `threading.Event` and PostgreSQL `NOWAIT`, not timing sleeps or statistical repetitions.

## Scope

This is a database correctness example, not a complete scheduler or security boundary. The test database role owns the schema; production must restrict direct DML and route all protected writes through guarded functions or equivalent triggers. A TTL/heartbeat lease, connection supervision, external-effect idempotency, authentication, and a web API are outside this sample.

The permanent epoch must never reset during normal deployments. Keep protected transactions short, acquire the leader-row lock before business-row locks, and treat serialization errors as failed writes. No broker connection, trading, production deployment, or private code is involved.

## Sources

- [PostgreSQL 16 advisory and row locks](https://www.postgresql.org/docs/16/explicit-locking.html)
- [PostgreSQL 16 transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html)
- [Psycopg transaction contexts](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
