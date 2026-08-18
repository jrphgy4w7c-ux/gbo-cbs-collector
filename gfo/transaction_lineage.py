#!/usr/bin/env python3
"""Build a compact, human-readable Grant transaction ledger from canonical Sleeper evidence.

Raw transaction IDs/player IDs remain authoritative evidence. This projection resolves
those IDs through Sleeper's player and league user maps so Front Office reconciliation
can consume settled transaction history without guessing identities from chat context.
"""
from __future__ import annotations
import argparse, json, time, urllib.request
from pathlib import Path

SCHEMA = "gfo.transaction-lineage.v1"
BASE = "https://api.sleeper.app/v1"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_json(url, attempts=4, timeout=30):
    err = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GFO-Transaction-Lineage/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            err = e
            if i + 1 < attempts:
                time.sleep(1.2 * 2**i)
    raise RuntimeError(f"failed to retrieve {url}: {type(err).__name__}: {err}")


def player_identity(player_id, players):
    pid = str(player_id)
    p = players.get(pid) or {}
    name = p.get("full_name") or " ".join(x for x in [p.get("first_name"), p.get("last_name")] if x) or None
    return {
        "player_id": pid,
        "name": name,
        "position": p.get("position"),
        "team": p.get("team"),
        "resolved": bool(name),
    }


def roster_labels(league_id):
    users = get_json(f"{BASE}/league/{league_id}/users")
    rosters = get_json(f"{BASE}/league/{league_id}/rosters")
    by_user = {str(u.get("user_id")): u for u in users}
    out = {}
    for r in rosters:
        rid = int(r["roster_id"])
        uid = str(r.get("owner_id"))
        u = by_user.get(uid) or {}
        meta = u.get("metadata") or {}
        out[rid] = {
            "roster_id": rid,
            "owner_id": uid,
            "display_name": u.get("display_name"),
            "team_name": meta.get("team_name") or u.get("display_name"),
        }
    return out


def normalize_pick(p):
    return {
        "season": str(p.get("season")),
        "round": int(p.get("round")),
        "original_roster_id": int(p.get("roster_id")),
        "from_roster_id": int(p.get("previous_owner_id")) if p.get("previous_owner_id") is not None else None,
        "to_roster_id": int(p.get("owner_id")) if p.get("owner_id") is not None else None,
    }


def build(snapshot, txs, players, labels):
    league_id = str(snapshot["league_id"])
    grant_id = int(snapshot["grant_roster_id"])
    starting_budget = int(snapshot["league"]["settings"].get("waiver_budget") or 0)
    grant = snapshot["rosters"][str(grant_id)]
    balance = starting_budget
    paid_claim_spend = 0
    transfer_in = 0
    transfer_out = 0
    unresolved = set()
    ledger = []
    paid_claims = []

    for t in sorted(txs, key=lambda x: (int(x.get("status_updated") or x.get("created") or 0), str(x.get("transaction_id")))):
        if t.get("status") != "complete":
            continue
        roster_ids = [int(x) for x in (t.get("roster_ids") or [])]
        adds_raw = t.get("adds") or {}
        drops_raw = t.get("drops") or {}
        grant_add_ids = [str(pid) for pid, rid in adds_raw.items() if int(rid) == grant_id]
        grant_drop_ids = [str(pid) for pid, rid in drops_raw.items() if int(rid) == grant_id]
        pick_rows = [normalize_pick(p) for p in (t.get("draft_picks") or [])]
        transfer_rows = []
        grant_transfer_delta = 0
        for w in t.get("waiver_budget") or []:
            sender, receiver, amount = int(w["sender"]), int(w["receiver"]), int(w["amount"])
            row = {"sender_roster_id": sender, "receiver_roster_id": receiver, "amount": amount}
            transfer_rows.append(row)
            if sender == grant_id:
                transfer_out += amount
                grant_transfer_delta -= amount
            if receiver == grant_id:
                transfer_in += amount
                grant_transfer_delta += amount

        grant_involved = grant_id in roster_ids or bool(grant_add_ids) or bool(grant_drop_ids) or any(
            grant_id in (p["from_roster_id"], p["to_roster_id"]) for p in pick_rows
        ) or grant_transfer_delta != 0
        if not grant_involved:
            continue

        settings = t.get("settings") or {}
        bid = settings.get("waiver_bid")
        spend = int(bid) if bid is not None and grant_id in roster_ids else 0
        paid_claim_spend += spend
        balance -= spend
        balance += grant_transfer_delta

        adds = [player_identity(pid, players) for pid in grant_add_ids]
        drops = [player_identity(pid, players) for pid in grant_drop_ids]
        for row in adds + drops:
            if not row["resolved"]:
                unresolved.add(row["player_id"])

        if spend > 0:
            paid_claims.append({
                "transaction_id": str(t.get("transaction_id")),
                "effective_at_ms": int(t.get("status_updated") or t.get("created") or 0),
                "amount": spend,
                "adds": adds,
                "drops": drops,
                "faab_balance_after": balance,
            })

        # Also resolve every player moved in a Grant trade, not just Grant's side, so the
        # transaction remains understandable without reopening the raw league ledger.
        all_moves = []
        for pid, rid in sorted(adds_raw.items()):
            ident = player_identity(pid, players)
            if not ident["resolved"]:
                unresolved.add(ident["player_id"])
            all_moves.append({"direction":"to","roster_id":int(rid),"player":ident})
        for pid, rid in sorted(drops_raw.items()):
            ident = player_identity(pid, players)
            if not ident["resolved"]:
                unresolved.add(ident["player_id"])
            all_moves.append({"direction":"from","roster_id":int(rid),"player":ident})

        ledger.append({
            "transaction_id": str(t.get("transaction_id")),
            "type": t.get("type"),
            "effective_at_ms": int(t.get("status_updated") or t.get("created") or 0),
            "roster_ids": roster_ids,
            "rosters": [labels.get(r, {"roster_id":r}) for r in roster_ids],
            "grant_adds": adds,
            "grant_drops": drops,
            "player_moves": all_moves,
            "draft_picks": pick_rows,
            "faab_spend": spend,
            "faab_transfers": transfer_rows,
            "grant_faab_delta": -spend + grant_transfer_delta,
            "grant_faab_balance_after": balance,
        })

    expected_used = paid_claim_spend + transfer_out - transfer_in
    state_used = int(grant["faab_used"])
    state_remaining = int(grant["faab_remaining"])
    issues = []
    if unresolved:
        issues.append({"code":"UNRESOLVED_PLAYER_IDS","player_ids":sorted(unresolved)})
    if expected_used != state_used or balance != state_remaining:
        issues.append({
            "code":"FAAB_LINEAGE_MISMATCH",
            "expected_used":expected_used,
            "sleeper_faab_used":state_used,
            "computed_remaining":balance,
            "sleeper_faab_remaining":state_remaining,
            "paid_claim_spend":paid_claim_spend,
            "transfer_in":transfer_in,
            "transfer_out":transfer_out,
        })
    status = "GREEN" if not issues else "PARTIAL"
    return {
        "schema": SCHEMA,
        "collected_at": snapshot["collected_at"],
        "league_id": league_id,
        "grant_roster": labels.get(grant_id, {"roster_id":grant_id}),
        "starting_faab": starting_budget,
        "paid_claim_spend": paid_claim_spend,
        "paid_claims": paid_claims,
        "faab_transfer_in": transfer_in,
        "faab_transfer_out": transfer_out,
        "sleeper_faab_used": state_used,
        "sleeper_faab_remaining": state_remaining,
        "transaction_count": len(ledger),
        "transactions": ledger,
        "status": status,
        "issues": issues,
    }


def self_test():
    snapshot = {"collected_at":"2026-08-18T00:00:00Z","league_id":"L","grant_roster_id":3,
                "league":{"settings":{"waiver_budget":200}},
                "rosters":{"3":{"faab_used":17,"faab_remaining":183}}}
    txs = [{"transaction_id":"x","status":"complete","created":1,"status_updated":2,"type":"waiver",
            "roster_ids":[3],"settings":{"waiver_bid":17},"adds":{"10":3},"drops":{"11":3},
            "draft_picks":[],"waiver_budget":[]}]
    players = {"10":{"full_name":"Added Player","position":"WR","team":"AAA"},
               "11":{"full_name":"Dropped Player","position":"RB","team":"BBB"}}
    labels = {3:{"roster_id":3,"team_name":"Big Nasty","display_name":"Grant"}}
    out = build(snapshot, txs, players, labels)
    assert out["status"] == "GREEN"
    assert out["transactions"][0]["grant_adds"][0]["name"] == "Added Player"
    assert out["transactions"][0]["grant_drops"][0]["name"] == "Dropped Player"
    assert out["transactions"][0]["grant_faab_balance_after"] == 183
    assert out["paid_claims"][0]["adds"][0]["name"] == "Added Player"
    print("PASS transaction_lineage")
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
    snapshot = load(a.snapshot)
    players = get_json(f"{BASE}/players/nfl")
    labels = roster_labels(snapshot["league_id"])
    out = build(snapshot, load(a.transactions), players, labels)
    save(a.output, out)
    print(json.dumps({
        "transaction_lineage_status":out["status"],
        "transactions":out["transaction_count"],
        "paid_claim_spend":out["paid_claim_spend"],
        "paid_claims":len(out["paid_claims"]),
        "sleeper_faab_used":out["sleeper_faab_used"],
        "issues":out["issues"],
    }, indent=2))
    return 3 if a.require_green and out["status"] != "GREEN" else 0

if __name__ == "__main__":
    raise SystemExit(main())
