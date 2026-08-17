# GFO Refresh

Canonical live-state/provenance layer for Grant Football Operations.

## One owner per responsibility

- `gfo/collector.py` — fetches Sleeper, normalizes current state, validates invariants, reconstructs future picks, sweeps/deduplicates transactions, diffs against the prior successful snapshot, and checks provenance.
- `.github/workflows/gfo-refresh.yml` — scheduling/orchestration only. It runs regression tests, restores the prior artifact, runs the collector, and uploads the new canonical artifact.
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
6. provenance exceptions are empty.

The collector currently sweeps Sleeper transaction rounds 0–18 and uses the prior successful canonical snapshot when available.

## Design rule

Prefer consolidation over accretion. Put logic in executable code/tests when possible; keep workflow YAML thin; keep ChatGPT automation prompts focused on contracts and decisions rather than duplicating implementation details.
