#!/usr/bin/env python3
"""Derive durable FAAB lineage from canonical Sleeper transactions.

This is a collector-side helper: it does not fetch or interpret fantasy value. It
turns already-collected transaction evidence into a compact, auditable ledger and
checks that transaction-derived spend reconciles to Sleeper's current roster state.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

SCHEMA = "gfo.faab-lineage.v1"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def derive(snapshot, txs):
    budget = int(snapshot["league"]["settings"].get("waiver_budget") or 0)
    roster_id = int(snapshot["grant_roster_id"])
    roster = snapshot["rosters"][str(roster_id)]
    claims = []
    transfers = []

    for t in txs:
        if t.get("status") != "complete":
            continue
        settings = t.get("settings") or {}
        bid = settings.get("waiver_bid")
        roster_ids = [int(x) for x in (t.get("roster_ids") or [])]
        if bid is not None and roster_id in roster_ids:
            adds = [str(pid) for pid, rid in (t.get("adds") or {}).items() if int(rid) == roster_id]
            drops = [str(pid) for pid, rid in (t.get("drops") or {}).items() if int(rid) == roster_id]
            claims.append({
                "transaction_id": str(t.get("transaction_id")),
                "effective_at_ms": int(t.get("status_updated") or t.get("created") or 0),
                "amount": int(bid),
                "adds": sorted(adds),
                "drops": sorted(drops),
            })
        for w in t.get("waiver_budget") or []:
            sender, receiver, amount = int(w["sender"]), int(w["receiver"]), int(w["amount"])
            if roster_id in (sender, receiver):
                transfers.append({
                    "transaction_id": str(t.get("transaction_id")),
                    "effective_at_ms": int(t.get("status_updated") or t.get("created") or 0),
                    "sender": sender, "receiver": receiver, "amount": amount,
                })

    claims.sort(key=lambda x: (x["effective_at_ms"], x["transaction_id"]))
    transfers.sort(key=lambda x: (x["effective_at_ms"], x["transaction_id"]))
    claim_spend = sum(x["amount"] for x in claims)
    transfer_out = sum(x["amount"] for x in transfers if x["sender"] == roster_id)
    transfer_in = sum(x["amount"] for x in transfers if x["receiver"] == roster_id)
    # Sleeper's waiver_budget_used is authoritative current state. Claims are the
    # deterministic spend ledger; transfers are preserved separately because their
    # treatment can vary by league/platform semantics and must never be guessed.
    state_used = int(roster["faab_used"])
    state_remaining = int(roster["faab_remaining"])
    status = "GREEN" if claim_spend == state_used else "PARTIAL"
    issues = [] if status == "GREEN" else [{
        "code": "FAAB_LINEAGE_MISMATCH",
        "transaction_claim_spend": claim_spend,
        "sleeper_faab_used": state_used,
        "difference": state_used - claim_spend,
        "transfer_in": transfer_in,
        "transfer_out": transfer_out,
    }]
    return {
        "schema": SCHEMA,
        "collected_at": snapshot["collected_at"],
        "league_id": snapshot["league_id"],
        "roster_id": roster_id,
        "starting_budget": budget,
        "claims": claims,
        "claim_spend": claim_spend,
        "transfers": transfers,
        "transfer_in": transfer_in,
        "transfer_out": transfer_out,
        "sleeper_faab_used": state_used,
        "sleeper_faab_remaining": state_remaining,
        "status": status,
        "issues": issues,
    }


def self_test():
    snapshot = {"collected_at":"2026-08-18T00:00:00Z","league_id":"L","grant_roster_id":3,
                "league":{"settings":{"waiver_budget":200}},
                "rosters":{"3":{"faab_used":66,"faab_remaining":134}}}
    txs = [
        {"transaction_id":"a","status":"complete","created":1,"roster_ids":[3],"settings":{"waiver_bid":5},"adds":{"P1":3}},
        {"transaction_id":"b","status":"complete","created":2,"roster_ids":[3],"settings":{"waiver_bid":44},"adds":{"P2":3}},
        {"transaction_id":"c","status":"complete","created":3,"roster_ids":[3],"settings":{"waiver_bid":17},"adds":{"P3":3}},
        {"transaction_id":"failed","status":"failed","created":4,"roster_ids":[3],"settings":{"waiver_bid":99},"adds":{"P4":3}},
    ]
    out = derive(snapshot, txs)
    assert out["status"] == "GREEN" and out["claim_spend"] == 66 and len(out["claims"]) == 3
    bad = json.loads(json.dumps(snapshot)); bad["rosters"]["3"]["faab_used"] = 67
    assert derive(bad, txs)["status"] == "PARTIAL"
    print("PASS faab_lineage")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot")
    p.add_argument("--transactions")
    p.add_argument("--output")
    p.add_argument("--require-green", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        return self_test()
    if not all((a.snapshot, a.transactions, a.output)):
        p.error("--snapshot, --transactions and --output are required")
    out = derive(load(a.snapshot), load(a.transactions))
    save(a.output, out)
    print(json.dumps({"faab_lineage_status":out["status"],"claim_spend":out["claim_spend"],"sleeper_faab_used":out["sleeper_faab_used"],"claims":len(out["claims"]),"issues":out["issues"]}, indent=2))
    return 3 if a.require_green and out["status"] != "GREEN" else 0

if __name__ == "__main__":
    raise SystemExit(main())
