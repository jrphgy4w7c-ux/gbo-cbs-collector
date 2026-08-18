# Grant Baseball Operations collector

Canonical CBS acquisition, ingest, reconciliation and current-state projection layer for Grant Baseball Operations.

## One owner per responsibility

- `gbo/collector.js` — canonical production CBS collector. It runs inside Grant's authenticated CBS browser session and produces the sanitized source snapshot.
- `gbo/ingest.py` — validates an uploaded snapshot, reconciles it against the prior canonical state and promotes only GREEN state.
- `gbo/front_office.py` — builds compact retrievable projections for routine front-office use without requiring repeated parsing of the full raw snapshot.
- `.github/workflows/gbo-ingest.yml` — orchestration only: validate, reconcile, project, promote GREEN state and retain evidence.
- ChatGPT Front Office Reconciliation — interprets the newest canonical state; it does not recreate collector/ingest logic.
- Durable GBO databases/context — institutional history and analytical context, not a substitute for newer CBS state.

## Browser acquisition

The permanent browser bookmarklet resolves the stable root `gbo-launcher.js` through immutable repository ID `1337389940`; the launcher resolves `gbo/collector.js`. Repository renames therefore do not require replacing the bookmarklet.

The legacy root collector has been retired after successful production validation. Git history is the rollback path; there is no active duplicate collector fallback.

## Published-state retrieval

For routine reconciliation, prefer the compact promoted state on `main`:

1. `gbo/current/latest_manifest.json` — freshness, collector version and GREEN/validation status.
2. `gbo/current/latest_reconciliation.json` — delta against the prior promoted state.
3. `gbo/current/front_office/core.json` — compact league/Grant/source-health summary.
4. `gbo/current/front_office/grant_roster.json`, `ownership.json`, `league_rosters.json` and the available-pool shards as the question requires.

Use the full `gbo/current/latest_snapshot.json` only when deeper source evidence is needed. A persistent file is not automatically current; the manifest timestamp and health contract determine freshness.
