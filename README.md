# Grant Front Office

Shared private-use acquisition infrastructure for Grant Baseball Operations (GBO) and Grant Football Operations (GFO).

## Layout

- `gbo/` — canonical GBO/CBS acquisition code.
- `gfo/` — canonical GFO/Sleeper acquisition, normalization, validation and provenance code.
- `.github/workflows/` — thin orchestration only.
- `gbo-launcher.js` — stable GBO browser-loader layer, intentionally kept at a fixed root path because the permanent browser bookmarklet resolves it through immutable repository ID `1337389940`.
- `bookmarklet.txt` — permanent GBO Refresh bookmarklet.
- `manifest.json` — GBO launcher/collector contract and migration state.

## GBO

`gbo/collector.js` is the canonical CBS collector. It runs only inside Grant's already-authenticated CBS Fantasy Baseball browser session and downloads a sanitized JSON snapshot locally. The permanent bookmarklet resolves the root launcher by immutable repository ID, so repository renames do not require replacing the browser button. The launcher provides visible progress feedback, prevents duplicate simultaneous runs and warns when transaction history is incomplete.

## GFO

- `gfo/collector.py` — canonical Sleeper normalization, validation, transaction-provenance and snapshot-diff collector.
- `.github/workflows/gfo-refresh.yml` — scheduled/dispatch orchestration layer.

## Architecture contracts

- Protect requirements, not implementations.
- One owner per responsibility.
- Prefer consolidation over accretion.
- Treat live authoritative platform evidence as current-state authority; durable databases are organizational history.
- A replacement must meet or exceed the known-good system for correctness, completeness, provenance, continuity, reliability and recoverability before promotion.
- Keep rollback paths during migration, then retire them after successful validation rather than retaining permanent duplicate implementations.
- After a material refactor reaches GREEN, prefer stability and normal-run evidence over further churn.

## Security

Collectors are read-only. CBS credentials remain inside the authenticated browser session and are not persisted. Repository artifacts must not contain source-platform passwords, session cookies, access tokens, or private snapshot data.
