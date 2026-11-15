# Fencing demonstration design

Goal: provide a public, reproducible test-first work sample without using any private repository.

Choice: Python plus real PostgreSQL 16. An in-memory receipt race would be smaller, but PostgreSQL directly exercises the client's deploy-overlap problem. A complete FastAPI server would add unrelated setup; the sample isolates its storage contract.

Acceptance:
1. Main contains a clearly labeled, synthetic, unfenced baseline with passing smoke tests.
2. The PR's first commit adds deterministic failures: stale insert/update after a session handover, missing leader metadata, and absence of a transaction-scoped leader-row lock.
3. The next commit adds the minimal database guard and passes the unchanged tests.
4. Record local red/green runs, open a real public PR, and verify GitHub Actions against PostgreSQL.
5. Leave the PR open for review; do not merge or deploy.

The committed epoch increment activates leadership. A transaction that already owns the fence row finishes before a successor can activate. Each old job keeps its original epoch.
