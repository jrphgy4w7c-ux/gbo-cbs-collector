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
8. transaction-derived FAAB (claims plus transfers) reconciles exactly to Sleeper's current FAAB state.

The collector currently sweeps Sleeper transaction rounds 0–18 and uses the prior successful canonical snapshot when available. A GREEN run publishes `latest_transaction_lineage.json` so settled transaction history is directly retrievable with player names, raw IDs, roster identities, adds/drops, trades/picks, FAAB spend/transfers, and running balance.

## State-lineage invariant

Current state and its settled provenance are different responsibilities and both must survive reconciliation. Superseded values remain historical evidence but must not re-enter the active issue list unless newer authoritative evidence contradicts the settled state. Deterministic counters such as FAAB must be reconstructable from a compact event ledger and checked against current platform state on every production refresh.

## Identity invariant

Front Office reconciliation must never infer a transaction's player identity from memory or surrounding prose when the platform supplies an authoritative player ID. Raw Sleeper IDs remain provenance; the normalized ledger resolves them through Sleeper's player map before the transaction is treated as human-readable settled history.

## Design rule

Prefer consolidation over accretion. Put logic in executable code/tests when possible; keep workflow YAML thin; keep ChatGPT prompts focused on contracts and decisions rather than duplicating implementation details. The earlier standalone FAAB helper was retained only for shadow parity testing, then retired after the generalized transaction lineage matched it in production with no regression. Git history remains the rollback path.
