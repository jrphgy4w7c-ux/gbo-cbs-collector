#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def health(snapshot):
    issues = []
    meta = snapshot.get("meta") or {}
    source = snapshot.get("source_health") or {}
    validation = snapshot.get("validation") or {}

    if not str(meta.get("collector") or "").startswith("GBO-CBS-"):
        issues.append({"code": "COLLECTOR_ID"})
    if not meta.get("generated_at"):
        issues.append({"code": "MISSING_GENERATED_AT"})

    for key in ("rosters_api", "players_api", "stats_api"):
        if not (source.get(key) or {}).get("ok"):
            issues.append({"code": "CORE_SOURCE_FAILED", "source": key})

    tx = source.get("transactions") or {}
    if not tx.get("ok"):
        issues.append({"code": "TRANSACTIONS_FAILED"})
    if not tx.get("complete"):
        issues.append({"code": "TRANSACTIONS_INCOMPLETE", "pages_read": tx.get("pages_read"), "pages_expected": tx.get("pages_expected")})

    if int(validation.get("roster_team_count") or 0) <= 0:
        issues.append({"code": "EMPTY_ROSTER_SET"})
    if int(validation.get("player_record_count") or 0) <= 0:
        issues.append({"code": "EMPTY_PLAYER_POOL"})

    return {"status": "GREEN" if not issues else "PARTIAL", "issues": issues}


def player_name(player):
    for key in ("fullname", "full_name", "name"):
        if player.get(key):
            return str(player[key])
    parts = [player.get("firstname") or player.get("first_name"), player.get("lastname") or player.get("last_name")]
    text = " ".join(str(x) for x in parts if x)
    return text or str(player.get("id") or "UNKNOWN")


def roster_state(snapshot):
    teams = (((snapshot.get("sources") or {}).get("rosters") or {}).get("data") or {}).get("body", {}).get("rosters", {}).get("teams", []) or []
    players = (((snapshot.get("sources") or {}).get("players") or {}).get("data") or {}).get("body", {}).get("players", []) or []
    names = {str(p.get("id")): player_name(p) for p in players if p.get("id") is not None}
    owned = {}
    for team in teams:
        tid = str(team.get("id"))
        for p in team.get("players") or []:
            pid = str(p.get("id"))
            owned[pid] = {
                "team_id": tid,
                "name": names.get(pid, player_name(p)),
                "roster_status": p.get("roster_status"),
            }
    return owned


def reconcile(previous, current):
    if not previous:
        return {"baseline": True, "ownership_changes": [], "grant": {"changed": False}, "transactions_added": []}

    before = roster_state(previous)
    after = roster_state(current)
    changes = []
    for pid in sorted(set(before) | set(after)):
        a, b = before.get(pid), after.get(pid)
        if a == b:
            continue
        changes.append({
            "player_id": pid,
            "name": (b or a or {}).get("name"),
            "from_team_id": a.get("team_id") if a else None,
            "to_team_id": b.get("team_id") if b else None,
            "from_status": a.get("roster_status") if a else None,
            "to_status": b.get("roster_status") if b else None,
        })

    grant_id = "3"
    grant_changes = [c for c in changes if c.get("from_team_id") == grant_id or c.get("to_team_id") == grant_id]
    prev_cbs = previous.get("my_cbs_state") or {}
    cur_cbs = current.get("my_cbs_state") or {}
    prev_sum = previous.get("my_roster_summary") or {}
    cur_sum = current.get("my_roster_summary") or {}

    def tx_rows(s):
        return (((s.get("sources") or {}).get("transactions") or {}).get("rows") or [])

    old_tx = {json.dumps(row, sort_keys=True) for row in tx_rows(previous)}
    added_tx = [row for row in tx_rows(current) if json.dumps(row, sort_keys=True) not in old_tx]

    return {
        "baseline": False,
        "ownership_changes": changes,
        "grant": {
            "changed": bool(grant_changes),
            "player_changes": grant_changes,
            "fab_remaining": {"from": prev_cbs.get("fab_remaining"), "to": cur_cbs.get("fab_remaining")},
            "waiver_position": {"from": prev_cbs.get("waiver_position"), "to": cur_cbs.get("waiver_position")},
            "active_roster_salary": {"from": prev_sum.get("active_roster_salary"), "to": cur_sum.get("active_roster_salary")},
            "total_roster_salary": {"from": prev_sum.get("total_roster_salary"), "to": cur_sum.get("total_roster_salary")},
        },
        "transactions_added": added_tx,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inbox", required=True)
    p.add_argument("--previous")
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()

    current = load(args.inbox)
    previous = load(args.previous) if args.previous and Path(args.previous).exists() else None
    result = health(current)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema": "gbo.ingest.v1",
        "ingested_at": now(),
        "snapshot_generated_at": (current.get("meta") or {}).get("generated_at"),
        "collector": (current.get("meta") or {}).get("collector"),
        "core_status": result["status"],
        "validation_issues": result["issues"],
        "snapshot_hash": digest(current),
        "transaction_rows": ((current.get("source_health") or {}).get("transactions") or {}).get("unique_rows"),
    }
    save(out / "latest_manifest.json", manifest)

    if result["status"] != "GREEN":
        save(out / "reconciliation.json", {"status": "PARTIAL", "issues": result["issues"]})
        print(json.dumps(manifest, indent=2))
        return 2

    save(out / "latest_snapshot.json", current)
    rec = reconcile(previous, current)
    rec["status"] = "GREEN"
    rec["snapshot_hash"] = manifest["snapshot_hash"]
    save(out / "reconciliation.json", rec)
    print(json.dumps({"manifest": manifest, "reconciliation": rec}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
