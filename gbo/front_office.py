#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

GRANT_TEAM_ID = "3"
PLAYER_KEYS = ("pro_team", "pro_team_abbrev", "team", "position", "positions", "eligible_positions", "status", "injury_status", "free_agent", "on_waivers")
ROSTER_PLAYER_KEYS = ("roster_status", "salary", "contract", "keeper_status", "position", "positions", "eligible_positions")
TEAM_KEYS = ("long_abbr", "short_name", "abbr", "active_roster_salary", "total_roster_salary")
SHARD_SIZE = 250

def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def name(p):
    for k in ("fullname", "full_name", "name"):
        if p.get(k): return str(p[k])
    return " ".join(str(x) for x in (p.get("firstname"), p.get("lastname")) if x) or str(p.get("id") or "UNKNOWN")
def pick(d, keys): return {k: d.get(k) for k in keys if d.get(k) is not None}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--snapshot", required=True); ap.add_argument("--manifest", required=True); ap.add_argument("--output-dir", required=True)
    args = ap.parse_args(); s = load(args.snapshot); manifest = load(args.manifest); outdir = Path(args.output_dir)
    if outdir.exists(): shutil.rmtree(outdir)
    outdir.mkdir(parents=True)
    sources = s.get("sources") or {}
    teams = (((sources.get("rosters") or {}).get("data") or {}).get("body") or {}).get("rosters", {}).get("teams", []) or []
    players = (((sources.get("players") or {}).get("data") or {}).get("body") or {}).get("players", []) or []
    pmap = {str(p.get("id")): p for p in players if p.get("id") is not None}
    ownership, roster_teams = {}, []
    for t in teams:
        tid = str(t.get("id")); tc = pick(t, TEAM_KEYS); tc["team_id"] = tid; tc["players"] = []
        for rp in t.get("players") or []:
            pid = str(rp.get("id")); base = pmap.get(pid) or rp
            item = pick(rp, ROSTER_PLAYER_KEYS); item.update({"player_id": pid, "name": name(base)})
            tc["players"].append(item); ownership[pid] = {"team_id": tid, "name": item["name"], "roster_status": rp.get("roster_status")}
        roster_teams.append(tc)
    available = []
    for p in players:
        if int(p.get("in_player_pool") or 0) != 1: continue
        if int(p.get("free_agent") or 0) != 1 and int(p.get("on_waivers") or 0) != 1: continue
        item = pick(p, PLAYER_KEYS); item.update({"player_id": str(p.get("id")), "name": name(p)}); available.append(item)
    available.sort(key=lambda x: (x.get("name") or "", x["player_id"]))
    shards = []
    for i in range(0, len(available), SHARD_SIZE):
        filename = f"available_{i // SHARD_SIZE:02d}.json"; rows = available[i:i + SHARD_SIZE]
        save(outdir / filename, {"schema": "gbo.available.v1", "snapshot_hash": manifest.get("snapshot_hash"), "count": len(rows), "players": rows}); shards.append(filename)
    tx = sources.get("transactions") or {}; ref = sources.get("reference") or {}
    provenance = {"snapshot_hash": manifest.get("snapshot_hash"), "snapshot_generated_at": manifest.get("snapshot_generated_at"), "ingested_at": manifest.get("ingested_at"), "collector": manifest.get("collector"), "core_status": manifest.get("core_status"), "validation_issues": manifest.get("validation_issues") or [], "transaction_rows": manifest.get("transaction_rows")}
    core = {"schema": "gbo.front_office.v2", "provenance": provenance, "source_health": s.get("source_health") or {}, "validation": s.get("validation") or {}, "grant": {"team_id": GRANT_TEAM_ID, "cbs_state": s.get("my_cbs_state") or {}, "roster_summary": s.get("my_roster_summary") or {}}, "league": {"teams": roster_teams, "ownership": ownership}, "available_pool": {"count": len(available), "shards": shards, "shard_size": SHARD_SIZE}, "transactions": {"headers": tx.get("headers") or [], "row_count": tx.get("unique_transaction_rows"), "recent_rows": (tx.get("rows") or [])[:90]}}
    core["projection_hash"] = digest(core); save(outdir / "core.json", core)
    save(outdir / "standings.json", {"schema": "gbo.reference.v1", "snapshot_hash": manifest.get("snapshot_hash"), "data": ref.get("standings") or {}})
    save(outdir / "waiver_report.json", {"schema": "gbo.reference.v1", "snapshot_hash": manifest.get("snapshot_hash"), "data": ref.get("waiver_report") or {}})
    save(outdir / "league_details.json", {"schema": "gbo.reference.v1", "snapshot_hash": manifest.get("snapshot_hash"), "data": ref.get("league_details") or {}})
    print(json.dumps({"schema": core["schema"], "available": len(available), "owned": len(ownership), "shards": len(shards), "snapshot_hash": manifest.get("snapshot_hash")}, indent=2))

if __name__ == "__main__": main()
# v2 sharded projection production trigger
