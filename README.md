# Grant Front Office

Shared private-use acquisition and control infrastructure for Grant Baseball Operations (GBO) and Grant Football Operations (GFO).

## Layout

- `gbo/` — canonical GBO/CBS acquisition, ingest, reconciliation and compact current-state projection code.
- `gfo/` — canonical GFO/Sleeper acquisition, normalization, validation, provenance and transaction-lineage code.
- `.github/workflows/` — thin orchestration only.
- `gbo-launcher.js` — stable GBO browser-loader layer, intentionally kept at a fixed root path because the permanent browser bookmarklet resolves it through immutable repository ID `1337389940`.
- `bookmarklet.txt` — permanent GBO Refresh bookmarklet.
- `manifest.json` — GBO launcher/collector contract and migration state.
- `ARTIFACT_REGISTRY.md` — mandatory supersession/quarantine registry for durable Front Office artifacts.

## GBO

`gbo/collector.js` is the canonical CBS collector. It runs only inside Grant's already-authenticated CBS Fantasy Baseball browser session and downloads a sanitized JSON snapshot locally. The permanent bookmarklet resolves the root launcher by immutable repository ID, so repository renames do not require replacing the browser button. The launcher provides visible progress feedback, prevents duplicate simultaneous runs and warns when transaction history is incomplete.

Validated snapshots are reconciled and promoted under `gbo/current/`; compact front-office projections are the preferred routine retrieval interface, while the full snapshot remains available for deeper evidence.

## GFO

- `gfo/collector.py` — canonical Sleeper normalization, validation, transaction-provenance and snapshot-diff collector.
- `gfo/transaction_lineage.py` — canonical human-readable Grant transaction lineage built from Sleeper IDs and transaction evidence.
- `.github/workflows/gfo-refresh.yml` — scheduled/dispatch orchestration layer.
- Successful production refreshes publish retrievable canonical GREEN state on branch `gfo-green` under `gfo/current/`.

## Shared authority contract

Authority is domain-specific rather than one universal ranking.

- For platform-recorded facts — ownership, roster placement, completed transactions, FAAB/budget, salaries/cap where supplied, and draft-pick movement — the newest successful authoritative platform-derived state controls for the effective time it actually describes.
- Grant's direct statements are authoritative for intent, strategy, preferences, decision rationale, corrections to non-platform context, and facts the platform cannot encode. They always outrank assistant prose.
- Prior assistant prose is analysis/history-of-conversation only; it can identify something to verify but cannot authenticate a roster or transaction fact by repetition.
- When sources appear to conflict, align their temporal and semantic scope before calling them contradictory. A later transaction cannot retroactively change what was true earlier, and a correction aimed at an invented historical claim must not be broadened into a denial of a later real event.
- When authoritative sources truly conflict after scope alignment, quarantine and reconcile the conflict. Do not silently overwrite one source with another.
- Persistence, freshness, authority and temporal scope are separate properties. A durable file can be stale; a live platform state can be current without preserving rationale; conversational context can be useful without being evidence.

## Temporal-scope contract

Interpret every stateful/historical claim as: **fact + provenance/authority + effective timestamp or interval + semantic context**. Reconciliation should compare like periods with like periods rather than flattening history into a timeless yes/no assertion.

This rule is shared across sports. In GFO, a player added later in the day cannot prove he was already rostered earlier. In GBO, a later add/drop/IL/activation cannot be used to rewrite the roster state that existed before that transaction. Direct corrections must be attached to the historical claim they actually correct.

## Artifact supersession contract

`ARTIFACT_REGISTRY.md` must be checked before a versioned durable workbook/control artifact is used as institutional evidence. A later version explicitly supersedes an earlier version for current doctrine and corrections. Superseded artifacts remain historical records only and cannot reintroduce a quarantined error merely because file search retrieves them.

Known critical quarantine: `Grant_Front_Office_OS_v1_2.xlsx` and `GFO_Control_Center_2026-08-18_v1_2.xlsx` contain the erroneous interpretation that Grant misremembered the Hibner history. That interpretation is false and permanently superseded. The corrected chronology in v1.3+ and the GFO README controls.

## Architecture contracts

- Protect requirements, not implementations.
- One owner per responsibility.
- Prefer consolidation over accretion.
- Treat live authoritative platform evidence as current-state authority; durable databases are organizational history.
- Consume compact published canonical state for routine reconciliation; use raw snapshots/workflow diagnostics only when deeper evidence or failure diagnosis is needed.
- Check artifact supersession/quarantine before using durable institutional files.
- A replacement must meet or exceed the known-good system for correctness, completeness, provenance, continuity, reliability and recoverability before promotion.
- Keep rollback paths during migration, then retire them after successful validation rather than retaining permanent duplicate implementations.
- After a material refactor reaches GREEN, prefer stability and normal-run evidence over further churn.
- Generalizable process improvements should propagate between GBO and GFO, while sport/platform-specific state and mechanics remain isolated.

## Security

Collectors are read-only. CBS credentials remain inside the authenticated browser session and are not persisted. Repository artifacts must not contain source-platform passwords, session cookies, access tokens, or private snapshot data.
