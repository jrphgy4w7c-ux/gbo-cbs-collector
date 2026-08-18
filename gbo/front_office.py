#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

GRANT_TEAM_ID = "3"
PLAYER_KEYS = (
    "id", "fullname", "full_name", "name", "firstname", "lastname",
    "pro_team", "pro_team_abbrev", "team", "position", "positions",
    "eligible_positions", "status", "injury_status", "in_player_pool",
    "free_agent", "on_waivers"
)
ROSTER_PLAYER_KEYS = (
    "id", "roster_status", "salary", "contract", "keeper_status",
    "position", "positions", "eligible_positions"
)
TEAM_KEYS = (
    "id", "long_abbr", "short_name", "abbr", "active_roster_salary",
    "total_roster_salary"
)

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

def name(p):
    for k in ("fullname", "full_name", "name"):
        if p.get(k): return str(p[k])
    return " ".join(str(x) for x in (p.get("firstname"), p.get("lastname")) if x) or str(p.get("id") or "UNKNOWN")

def pick(d, keys):
    return {k: d.get(k) for k in keys if k in d and d.get(k) is not None}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--snapshot", required=True); ap.add_argument("--manifest", required=True); ap.add_argument("--output", required=True)
    args = ap.parse_args(); s = load(args.snapshot); manifest = load(args.manifest)
    sources = s.get("sources") or {}
    teams = (((sources.get("rosters") or {}).get("data") or {}).get("body") or {}).get("rosters", {}).get("teams", []) or []
    players = (((sources.get("players") or {}).get("data") or {}).get("body") or {}).get("players", []) or []
    pmap = {str(p.get("id")): p for p in players if p.get("id") is not None}
    ownership = {}; roster_teams = []
    for t in teams:
        tc = pick(t, TEAM_KEYS); tc["team_id"] = str(t.get("id")); tc["players"] = []
        for rp in t.get("players") or []:
            pid = str(rp.get("id")); base = pmap.get(pid) or {}
            item = pick(rp, ROSTER_PLAYER_KEYS); item["player_id"] = pid; item["name"] = name(base or rp)
            tc["players"].append(item)
            ownership[pid] = {"team_id": tc["team_id"], "name": item["name"], "roster_status": rp.get("roster_status")}
        roster_teams.append(tc)
    available = []
    for p in players:
        if int(p.get("in_player_pool") or 0) != 1: continue
        if int(p.get("free_agent") or 0) != 1 and int(p.get("on_waivers") or 0) != 1: continue
        item = pick(p, PLAYER_KEYS); item["player_id"] = str(p.get("id")); item["name"] = name(p); available.append(item)
    tx = sources.get("transactions") or {}
    reference = sources.get("reference") or {}
    out = {
        "schema": "gbo.front_office.v1",
        "provenance": {
            "snapshot_hash": manifest.get("snapshot_hash"), "snapshot_generated_at": manifest.get("snapshot_generated_at"),
            "ingested_at": manifest.get("ingested_at"), "collector": manifest.get("collector"), "core_status": manifest.get("core_status"),
            "validation_issues": manifest.get("validation_issues") or [], "transaction_rows": manifest.get("transaction_rows")
        },
        "source_health": s.get("source_health") or {}, "validation": s.get("validation") or {},
        "grant": {"cbs_state": s.get("my_cbs_state") or {}, "roster_summary": s.get("my_roster_summary") or {}, "team_id": GRANT_TEAM_ID},
        "league": {"teams": roster_teams, "ownership": ownership},
        "available_pool": {"count": len(available), "players": available},
        "transactions": {"headers": tx.get("headers") or [], "row_count": tx.get("unique_transaction_rows"), "recent_rows": (tx.get("rows") or [])[:90]},
        "reference": {"standings": reference.get("standings") or {}, "league_details": reference.get("league_details") or {}, "waiver_report": reference.get("waiver_report") or {}}
    }
    out["projection_hash"] = digest(out)
    save(args.output, out)
    print(json.dumps({"schema": out["schema"], "available": len(available), "owned": len(ownership), "snapshot_hash": manifest.get("snapshot_hash")}, indent=2))

if __name__ == "__main__": main()
