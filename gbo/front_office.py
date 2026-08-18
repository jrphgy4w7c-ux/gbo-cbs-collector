#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path
GRANT_TEAM_ID="3"; SHARD_SIZE=250
PLAYER_KEYS=("pro_team","pro_team_abbrev","team","position","positions","eligible_positions","status","injury_status","free_agent","on_waivers")
ROSTER_KEYS=("roster_status","salary","contract","keeper_status","position","positions","eligible_positions")
TEAM_KEYS=("long_abbr","short_name","abbr","active_roster_salary","total_roster_salary")
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def save(p,v): p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def name(p):
    for k in ("fullname","full_name","name"):
        if p.get(k): return str(p[k])
    return " ".join(str(x) for x in (p.get("firstname"),p.get("lastname")) if x) or str(p.get("id") or "UNKNOWN")
def pick(d,ks): return {k:d.get(k) for k in ks if d.get(k) is not None}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--snapshot",required=True); ap.add_argument("--manifest",required=True); ap.add_argument("--output-dir",required=True); a=ap.parse_args()
    s=load(a.snapshot); m=load(a.manifest); out=Path(a.output_dir)
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True); src=s.get("sources") or {}
    teams=(((src.get("rosters") or {}).get("data") or {}).get("body") or {}).get("rosters",{}).get("teams",[]) or []
    players=(((src.get("players") or {}).get("data") or {}).get("body") or {}).get("players",[]) or []; pmap={str(p.get("id")):p for p in players if p.get("id") is not None}
    ownership={}; roster_teams=[]; grant_team=None
    for t in teams:
        tid=str(t.get("id")); tc=pick(t,TEAM_KEYS); tc["team_id"]=tid; tc["players"]=[]
        for rp in t.get("players") or []:
            pid=str(rp.get("id")); item=pick(rp,ROSTER_KEYS); item.update({"player_id":pid,"name":name(pmap.get(pid) or rp)}); tc["players"].append(item); ownership[pid]={"team_id":tid,"name":item["name"],"roster_status":rp.get("roster_status")}
        roster_teams.append(tc)
        if tid==GRANT_TEAM_ID: grant_team=tc
    available=[]
    for p in players:
        if int(p.get("in_player_pool") or 0)!=1 or (int(p.get("free_agent") or 0)!=1 and int(p.get("on_waivers") or 0)!=1): continue
        x=pick(p,PLAYER_KEYS); x.update({"player_id":str(p.get("id")),"name":name(p)}); available.append(x)
    available.sort(key=lambda x:(x.get("name") or "",x["player_id"])); shards=[]
    for i in range(0,len(available),SHARD_SIZE):
        fn=f"available_{i//SHARD_SIZE:02d}.json"; rows=available[i:i+SHARD_SIZE]; save(out/fn,{"schema":"gbo.available.v1","snapshot_hash":m.get("snapshot_hash"),"count":len(rows),"players":rows}); shards.append(fn)
    tx=src.get("transactions") or {}; ref=src.get("reference") or {}; prov={"snapshot_hash":m.get("snapshot_hash"),"snapshot_generated_at":m.get("snapshot_generated_at"),"ingested_at":m.get("ingested_at"),"collector":m.get("collector"),"core_status":m.get("core_status"),"validation_issues":m.get("validation_issues") or [],"transaction_rows":m.get("transaction_rows")}
    core={"schema":"gbo.front_office.v3","provenance":prov,"source_health":s.get("source_health") or {},"validation":s.get("validation") or {},"grant":{"team_id":GRANT_TEAM_ID,"cbs_state":s.get("my_cbs_state") or {},"roster_summary":s.get("my_roster_summary") or {}},"available_pool":{"count":len(available),"shards":shards,"shard_size":SHARD_SIZE},"league":{"team_count":len(roster_teams),"owned_player_count":len(ownership)},"transactions":{"row_count":tx.get("unique_transaction_rows"),"recent_rows":(tx.get("rows") or [])[:30]}}
    core["projection_hash"]=digest(core); save(out/"core.json",core)
    save(out/"grant_roster.json",{"schema":"gbo.grant_roster.v1","snapshot_hash":m.get("snapshot_hash"),"team":grant_team or {}})
    save(out/"league_rosters.json",{"schema":"gbo.league_rosters.v1","snapshot_hash":m.get("snapshot_hash"),"teams":roster_teams})
    save(out/"ownership.json",{"schema":"gbo.ownership.v1","snapshot_hash":m.get("snapshot_hash"),"ownership":ownership})
    for fn,key in (("standings.json","standings"),("waiver_report.json","waiver_report"),("league_details.json","league_details")): save(out/fn,{"schema":"gbo.reference.v1","snapshot_hash":m.get("snapshot_hash"),"data":ref.get(key) or {}})
    print(json.dumps({"schema":core["schema"],"available":len(available),"owned":len(ownership),"shards":len(shards),"snapshot_hash":m.get("snapshot_hash")},indent=2))
if __name__=="__main__": main()
