# GFO Refresh

Canonical live-state/provenance layer for Grant Football Operations.

## One owner per responsibility

- `gfo/collector.py` — fetches Sleeper, normalizes current state, validates invariants, reconstructs future picks, sweeps/deduplicates transactions, diffs against the prior successful snapshot, and checks provenance.
- `gfo/faab_lineage.py` — collector-side deterministic projection of already-collected transaction evidence into a compact FAAB ledger; it validates transaction-derived spend against Sleeper current state and never guesses missing provenance.
- `.github/workflows/gfo-refresh.yml` — scheduling/orchestration only. It runs regression tests, restores the prior artifact, runs collector-side validation, and publishes the new canonical artifact/state.
- ChatGPT Front Office Architecture Audit — checks whether this control plane is healthy, lean, current, and improvable.
- ChatGPT Front Office Reconciliation — interprets the newest authoritative GBO/GFO state; it does not reimplement collector logic.
- Durable GFO databases/context — organizational history, not a substitute for live Sleeper state.
- Football analysis — injuries, practice, depth charts, usage, news, scouting and dynasty evaluation; intentionally separate from platform-state collection.

## GREEN contract

A production GFO Refresh is fully GREEN only when:

1. the latest `main` workflow run succeeds;
2. collector regression tests pass;
3. `core_status` is `GREEN`;
4. `provenance_status` is `GREEN`;
5. validation issues are empty;
6. provenance exceptions are empty;
7. deterministic FAAB lineage reconciles to Sleeper's current `waiver_budget_used` state.

The collector currently sweeps Sleeper transaction rounds 0–18 and uses the prior successful canonical snapshot when available. A GREEN run also publishes `latest_faab_lineage.json` so settled FAAB history remains directly retrievable instead of being rediscovered from prose or a large raw transaction file.

## State-lineage invariant

Current state and its settled provenance are different responsibilities and both must survive reconciliation. Superseded values remain historical evidence but must not re-enter the active issue list unless newer authoritative evidence contradicts the settled state. For deterministic counters such as FAAB, preserve the compact event ledger and validate it against current platform state on every production refresh.

## Design rule

Prefer consolidation over accretion. Put logic in executable code/tests when possible; keep workflow YAML thin; keep ChatGPT automation prompts focused on contracts and decisions rather than duplicating implementation details. A helper is justified only when it produces a distinct durable projection from canonical evidence; if lineage projections multiply, consolidate them back into the collector rather than accumulating parallel mechanisms.
