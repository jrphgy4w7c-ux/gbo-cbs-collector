# GFO Refresh

Canonical live-state/provenance layer for Grant Football Operations.

## One owner per responsibility

- `gfo/collector.py` — fetches Sleeper, normalizes current state, validates invariants, reconstructs future picks, sweeps/deduplicates transactions, diffs against the prior successful snapshot, and checks provenance.
- `gfo/transaction_lineage.py` — resolves canonical Sleeper transaction evidence into a compact human-readable Grant ledger using authoritative Sleeper player/user identity maps; it preserves raw IDs, reconstructs FAAB running balances, and validates transaction-derived FAAB against current Sleeper state.
- `.github/workflows/gfo-refresh.yml` — scheduling/orchestration only. It runs regression tests, restores prior canonical state, runs collector-side validation/projection, and publishes the new GREEN state.
- ChatGPT Front Office Architecture Audit — checks whether this control plane is healthy, lean, current, and improvable.
- ChatGPT Front Office Reconciliation — interprets the newest authoritative GBO/GFO state; it does not reimplement collector logic or guess player identities from prose.
- Durable GFO databases/context — organizational history, not a substitute for live Sleeper state.
- Football analysis — injuries, practice, depth charts, usage, news, scouting and dynasty evaluation; intentionally separate from platform-state collection.

## GREEN contract

A production GFO Refresh is fully GREEN only when:

1. the latest `main` workflow run succeeds;
2. collector and transaction-lineage regression tests pass;
3. `core_status` is `GREEN`;
4. `provenance_status` is `GREEN`;
5. validation issues are empty;
6. provenance exceptions are empty;
7. transaction lineage resolves all involved Grant player IDs to authoritative Sleeper identities;
8. transaction-derived FAAB reconciles exactly to Sleeper's current FAAB state.

## Published-state retrieval

Successful production runs publish the newest canonical GREEN state to branch `gfo-green`. Routine reconciliation should read:

1. `gfo/current/latest_manifest.json`
2. `gfo/current/latest_diff.json`
3. `gfo/current/latest_snapshot.json`
4. `gfo/current/latest_transaction_lineage.json`

Workflow-run inspection is diagnostic when published state is stale, missing or PARTIAL.

## Authority and temporal-scope invariant

- Platform evidence controls platform-recorded facts for the effective time it actually describes.
- Grant's direct statements control intent, strategy, preferences, rationale and non-platform context, and always outrank assistant prose.
- Prior assistant prose is never transaction/ownership evidence by itself.
- Before treating two claims as contradictory, align their time period and semantic target. A later transaction cannot retroactively make an earlier ownership claim true.
- Current roster state controls present ownership at its timestamp; transaction lineage explains historical changes at their effective times.

## Identity invariant

Front Office reconciliation must never infer a transaction's player identity from memory or surrounding prose when Sleeper supplies an authoritative player ID.

## Design rule

Prefer consolidation over accretion. Put logic in executable code/tests when possible; keep workflow YAML thin; keep prompts focused on contracts and decisions rather than duplicating implementation details. Git history is the rollback path.
