# Grant Front Office

Shared private-use acquisition and control infrastructure for Grant Baseball Operations (GBO) and Grant Football Operations (GFO).

## Shared operating system

The organizational doctrine now has one canonical home on `main`:

- `front_office/core.json` — universal evidence, continuity, evaluation, writeback and architecture controls.
- `front_office/adapters/gbo.json` and `front_office/adapters/gfo.json` — sport-specific translations with no cross-sport state.
- `front_office/sync_manifest.json` — version alignment and GREEN/YELLOW/RED propagation status.
- `front_office/change_log.jsonl` — append-only organizational refinement history.
- `front_office/validate.py` — propagation gate requiring the core and both adapters to remain version-aligned and complete.

Workbooks are human-readable projections of this shared doctrine plus sport-specific history. They are not independent doctrine sources and do not override newer valid platform state.

## Layout

- `front_office/` — canonical shared Grant Front Office OS and sport adapters.
- `gbo/` — canonical GBO/CBS acquisition, ingest, reconciliation and compact current-state projection code.
- `gfo/` — canonical GFO/Sleeper acquisition, normalization, validation, provenance and transaction-lineage code.
- `.github/workflows/` — thin orchestration only.
- `gbo-launcher.js` — stable GBO browser-loader layer, intentionally kept at a fixed root path because the permanent browser bookmarklet resolves it through immutable repository ID `1337389940`.
- `bookmarklet.txt` — permanent GBO Refresh bookmarklet.
- `manifest.json` — GBO launcher/collector contract and migration state.

## Operator phrases

- **GBO Refresh** — process the newest authenticated CBS browser capture and reconcile GBO. If no sufficiently fresh capture exists for the decision at hand, say so rather than pretending CBS was refreshed.
- **GFO Refresh** — collect and reconcile current Sleeper state through the canonical GFO pipeline.
- **Front Office Full Check** — refresh both sports as far as current platform access allows, reconcile both, then audit the shared architecture and report material state changes, risks or improvements. It must preserve the distinction between a fresh platform capture and reconciliation against the newest previously validated state.

## GBO

`gbo/collector.js` is the canonical CBS collector. It runs only inside Grant's already-authenticated CBS Fantasy Baseball browser session and downloads a sanitized JSON snapshot locally. The permanent bookmarklet resolves the root launcher by immutable repository ID, so repository renames do not require replacing the browser button. The launcher provides visible progress feedback, prevents duplicate simultaneous runs and warns when transaction history is incomplete.

Validated snapshots are reconciled and promoted under `gbo/current/`; compact front-office projections are the preferred routine retrieval interface, while the full snapshot remains available for deeper evidence.

## GFO

- `gfo/collector.py` — canonical Sleeper normalization, validation, transaction-provenance and snapshot-diff collector.
- `gfo/transaction_lineage.py` — canonical human-readable Grant transaction lineage built from Sleeper IDs and transaction evidence.
- `.github/workflows/gfo-refresh.yml` — scheduled/dispatch orchestration layer.
- Successful production refreshes publish retrievable canonical GREEN state on branch `gfo-green` under `gfo/current/`.

## Shared authority contract

- Platform-derived evidence controls platform-recorded facts for the time period it actually describes.
- Grant's direct statements control intent, strategy, preferences, rationale and context not encoded by the platform, and always outrank assistant prose.
- Prior assistant prose is never transaction/ownership evidence by itself.
- Apparent conflicts must be checked for temporal/contextual scope before being treated as real contradictions. A later transaction cannot rewrite what was true earlier.
- Persistence, freshness and authority are separate properties.
- An ad hoc web retrieval is not presumed fresher than a timestamped canonical snapshot unless its retrieval freshness is actually established; cached or transient platform responses do not override later validated state.

## Version rule

When durable institutional artifacts are versioned, use the latest valid version for current doctrine and corrections. Older versions are historical only when a newer version supersedes them.

## Architecture contracts

- Protect requirements, not implementations.
- One owner per responsibility.
- Prefer consolidation over accretion.
- Treat live authoritative platform evidence as current-state authority; durable databases are organizational history.
- Consume compact published canonical state for routine reconciliation; use raw snapshots/workflow diagnostics only when deeper evidence or failure diagnosis is needed.
- A replacement must meet or exceed the known-good system for correctness, completeness, provenance, continuity, reliability and recoverability before promotion.
- Keep rollback paths during migration, then retire them after successful validation rather than retaining permanent duplicate implementations.
- After a material refactor reaches GREEN, prefer stability and normal-run evidence over further churn.
- Generalizable process improvements should propagate between GBO and GFO, while sport/platform-specific state and mechanics remain isolated.

## Security

Collectors are read-only. CBS credentials remain inside the authenticated browser session and are not persisted. Repository artifacts must not contain source-platform passwords, session cookies, access tokens, or private snapshot data.
