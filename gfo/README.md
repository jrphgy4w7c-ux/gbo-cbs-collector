# GFO Refresh

Canonical live-state/provenance layer for Grant Football Operations.

## One owner per responsibility

- `gfo/collector.py` — fetches Sleeper, normalizes current state, validates invariants, reconstructs future picks, sweeps/deduplicates transactions, diffs against the prior successful snapshot, and checks provenance.
- `gfo/availability.py` — derives the canonical ownership view from current Sleeper rosters. A resolved player present in that view is `ROSTERED`; a resolved player absent from it is `AVAILABLE`. It keeps platform IDs as internal identity plumbing and preserves owner/team metadata for useful human output.
- `gfo/transaction_lineage.py` — resolves canonical Sleeper transaction evidence into a compact human-readable Grant ledger using authoritative Sleeper player/user identity maps; it preserves raw IDs, reconstructs FAAB running balances, and validates transaction-derived FAAB against current Sleeper state.
- `.github/workflows/gfo-refresh.yml` — scheduling/orchestration only. It runs regression tests, restores prior canonical state, runs collector-side validation/projection, builds the ownership view, and publishes the new GREEN state.
- `front_office/runtime_contract.json` — shared GBO/GFO runtime bootstrap and evolution-loop contract. Chats are workstations, not institutional brains.
- ChatGPT Front Office Architecture Audit — checks whether this control plane is healthy, lean, current, and improvable.
- ChatGPT Front Office Reconciliation — interprets the newest authoritative GBO/GFO state; it does not reimplement collector logic or guess player identities from prose.
- Durable GFO databases/context — organizational history, not a substitute for live Sleeper state.
- Football analysis — injuries, practice, depth charts, usage, news, scouting and dynasty evaluation; intentionally separate from platform-state collection.

## GREEN contract

A production GFO Refresh is fully GREEN only when:

1. the latest `main` workflow run succeeds;
2. collector, ownership and transaction-lineage regression tests pass;
3. `core_status` is `GREEN`;
4. `provenance_status` is `GREEN`;
5. validation issues are empty;
6. provenance exceptions are empty;
7. transaction lineage resolves all involved Grant player IDs to authoritative Sleeper identities;
8. transaction-derived FAAB reconciles exactly to Sleeper's current FAAB state;
9. `latest_ownership.json` is generated from the same canonical roster snapshot.

## Published-state retrieval

Successful production runs publish the newest canonical GREEN state to branch `gfo-green`. Routine reconciliation should read:

1. `gfo/current/latest_manifest.json`
2. `gfo/current/latest_ownership.json`
3. `gfo/current/latest_diff.json`
4. `gfo/current/latest_snapshot.json`
5. `gfo/current/latest_transaction_lineage.json`

Workflow-run inspection is diagnostic when published state is stale, missing or PARTIAL.

## Player-status contract

Before substantive add, stash or waiver analysis, resolve current ownership from the canonical ownership view or fresher live Sleeper state.

- Player present on a current league roster: `ROSTERED`.
- Player absent from every current league roster: `AVAILABLE`.
- Waiver status changes acquisition timing, not availability. Include a clear time when authoritative evidence supports it; never guess.
- Default user-facing output is the human conclusion (`AVAILABLE` or `ROSTERED`, optionally owner/team and useful waiver timing). Sleeper IDs and API plumbing stay internal unless Grant asks.
- If current ownership cannot be verified, say `availability unconfirmed` and do not recommend the add.

## Runtime continuity

Every GFO chat is a workstation in one continuous front office. Before substantive analysis, the runtime sequence is shared core → GFO adapter → newest valid canonical state needed for the question → relevant durable institutional context → analysis. HQ is headquarters, not the brain.

When a material error repeats or a better durable workflow is discovered, the fix is not complete when it is merely remembered. Classify it, assign it to the responsible layer, encode it, add or strengthen a regression check, propagate shared lessons where applicable, version/log it, and verify the relevant gate is GREEN.

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
