# Grant Front Office collector infrastructure

Private-use data-acquisition infrastructure for Grant Baseball Operations (GBO) and Grant Football Operations (GFO). The repository is being evolved toward a sport-neutral front-office layout while preserving the currently working production paths until migration is validated.

## GBO CBS collector

- `collector.js` — current production CBS collector.
- `gbo-launcher.js` — stable loader layer. It resolves repository files through immutable GitHub repository ID `1337389940`, so repository renames do not require changing the browser bookmarklet.
- `bookmarklet.txt` — permanent GBO Refresh bookmarklet. It loads only `gbo-launcher.js`; future collector-path changes are absorbed by the launcher.
- `manifest.json` — launcher/collector contract and current versions.

The GBO collector runs only inside Grant's already-authenticated CBS Fantasy Baseball browser session and downloads a sanitized JSON snapshot locally. This repository contains no CBS username, password, session cookie, access token, league password, or snapshot data.

## GFO

- `gfo/collector.py` — canonical Sleeper normalization, validation, transaction-provenance and snapshot-diff collector.
- `.github/workflows/gfo-refresh.yml` — thin scheduled orchestration layer.

## Architecture rule

Protect working behavior during refactors. Proposed replacements must meet or exceed the existing system's correctness, completeness, provenance, continuity, reliability and recoverability before the older path is retired.

## Security

Collectors are read-only. Credentials remain inside the authenticated source-platform session where applicable and are not persisted in repository artifacts.
