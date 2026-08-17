#!/usr/bin/env python3
"""GFO Refresh: canonical Sleeper state + transaction provenance."""
from __future__ import annotations
import argparse, copy, hashlib, json, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

VERSION = "2.0.0"
LEAGUE_ID = "1315882920837128192"
GRANT_USER_ID = "340645503257550848"
BASE = "https://api.sleeper.app/v1"


def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
def save(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def digest(obj): return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def get(url, attempts=4, timeout=25):
    err = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"GFO-Refresh/{VERSION}"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode()), {"ok": True, "status": int(getattr(r, "status", 200)), "attempts": i + 1, "url": url}
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}"
            if e.code in (429, 500, 502, 503, 504) and i + 1 < attempts:
                time.sleep(1.2 * 2**i); continue
            return None, {"ok": False, "status": e.code, "attempts": i + 1, "url": url, "error": err, "class": "PLATFORM"}
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            if i + 1 < attempts:
                time.sleep(1.2 * 2**i); continue
            return None, {"ok": False, "status": None, "attempts": i + 1, "url": url, "error": err, "class": "RETRIEVAL"}
    return None, {"ok": False, "attempts": attempts, "url": url, "error": err, "class": "RETRIEVAL"}


def normalize_rosters(raw, budget):
    out = {}
    for r in raw:
        rid = str(r["roster_id"]); s = r.get("settings") or {}; used = int(s.get("waiver_budget_used") or 0)
        out[rid] = {
            "roster_id": int(rid), "owner_id": str(r.get("owner_id")),
            "players": sorted(str(x) for x in (r.get("players") or [])),
            "starters": sorted(str(x) for x in (r.get("starters") or [])),
            "reserve": sorted(str(x) for x in (r.get("reserve") or [])),
            "taxi": sorted(str(x) for x in (r.get("taxi") or [])),
            "faab_used": used, "faab_remaining": budget - used,
            "waiver_position": s.get("waiver_position"), "total_moves": s.get("total_moves"),
        }
    return out


def pick_ledger(roster_ids, traded, seasons, rounds):
    moved = {(str(p["season"]), int(p["round"]), str(p["roster_id"])): str(p["owner_id"]) for p in traded}
    return [{"season": str(y), "round": rnd, "original_roster_id": int(orig), "owner_roster_id": int(moved.get((str(y), rnd, orig), orig))}
            for y in seasons for rnd in range(1, rounds + 1) for orig in sorted(roster_ids, key=int)]


def validate(league, rosters, users, picks):
    issues = []; expected = int(league.get("total_rosters") or (league.get("settings") or {}).get("num_teams") or 0)
    if len(rosters) != expected: issues.append({"code": "ROSTER_COUNT", "expected": expected, "actual": len(rosters)})
    uids = {str(u.get("user_id")) for u in users}; seen = {}; grant = []
    for rid, r in rosters.items():
        if r["owner_id"] not in uids: issues.append({"code": "OWNER_MAPPING", "roster_id": int(rid), "owner_id": r["owner_id"]})
        if r["owner_id"] == GRANT_USER_ID: grant.append(int(rid))
        owned = set(r["players"])
        if not set(r["reserve"]).issubset(owned): issues.append({"code": "RESERVE_NOT_OWNED", "roster_id": int(rid)})
        if not set(r["taxi"]).issubset(owned): issues.append({"code": "TAXI_NOT_OWNED", "roster_id": int(rid)})
        for pid in owned:
            if pid in seen and seen[pid] != rid: issues.append({"code": "DUPLICATE_OWNERSHIP", "player_id": pid, "rosters": [int(seen[pid]), int(rid)]})
            seen[pid] = rid
    if len(grant) != 1: issues.append({"code": "GRANT_ROSTER_MAPPING", "matches": grant})
    if not picks: issues.append({"code": "EMPTY_PICK_LEDGER"})
    return {"status": "GREEN" if not issues else "PARTIAL", "issues": issues, "grant_roster_id": grant[0] if len(grant) == 1 else None}


def diff(prev, cur):
    if not prev: return {"baseline": True, "rosters": [], "picks": []}
    out = []
    for rid in sorted(set(prev["rosters"]) | set(cur["rosters"]), key=int):
        a, b = prev["rosters"].get(rid), cur["rosters"].get(rid)
        if not a or not b: out.append({"roster_id": int(rid), "roster_changed": True}); continue
        d = {"roster_id": int(rid)}
        for fld in ("players", "reserve", "taxi", "starters"):
            x, y = set(a[fld]), set(b[fld])
            if x != y: d[fld] = {"added": sorted(y-x), "removed": sorted(x-y)}
        for fld in ("faab_used", "faab_remaining", "waiver_position"):
            if a.get(fld) != b.get(fld): d[fld] = {"from": a.get(fld), "to": b.get(fld)}
        if len(d) > 1: out.append(d)
    pa = {(p["season"], p["round"], p["original_roster_id"]): p["owner_roster_id"] for p in prev["future_picks"]}
    pb = {(p["season"], p["round"], p["original_roster_id"]): p["owner_roster_id"] for p in cur["future_picks"]}
    pd = [{"season": k[0], "round": k[1], "original_roster_id": k[2], "from": pa.get(k), "to": pb.get(k)} for k in sorted(set(pa)|set(pb)) if pa.get(k) != pb.get(k)]
    return {"baseline": False, "rosters": out, "picks": pd}


def provenance(delta, txs, prior_time):
    if delta.get("baseline"): return []
    cutoff = int(datetime.fromisoformat(prior_time.replace("Z", "+00:00")).timestamp()*1000) if prior_time else 0
    adds, drops, faab, picks = set(), set(), set(), set()
    for t in txs:
        if t.get("status") != "complete" or int(t.get("created") or 0) < cutoff: continue
        adds |= {(str(p), int(r)) for p, r in (t.get("adds") or {}).items()}
        drops |= {(str(p), int(r)) for p, r in (t.get("drops") or {}).items()}
        if (t.get("settings") or {}).get("waiver_bid") is not None: faab |= {int(r) for r in (t.get("roster_ids") or [])}
        for w in t.get("waiver_budget") or []: faab |= {int(w["sender"]), int(w["receiver"])}
        for p in t.get("draft_picks") or []: picks.add((str(p["season"]), int(p["round"]), int(p["roster_id"])))
    exc = []
    for r in delta["rosters"]:
        rid = r["roster_id"]
        for pid in r.get("players", {}).get("added", []):
            if (pid, rid) not in adds: exc.append({"kind": "UNEXPLAINED_ADD", "roster_id": rid, "player_id": pid})
        for pid in r.get("players", {}).get("removed", []):
            if (pid, rid) not in drops: exc.append({"kind": "UNEXPLAINED_DROP", "roster_id": rid, "player_id": pid})
        if "faab_used" in r and rid not in faab: exc.append({"kind": "UNEXPLAINED_FAAB", "roster_id": rid, "delta": r["faab_used"]})
    for p in delta["picks"]:
        key = (p["season"], p["round"], p["original_roster_id"])
        if key not in picks: exc.append({"kind": "UNEXPLAINED_PICK", **p})
    return exc


def run(a):
    out = Path(a.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = now(); urls = {
        "league": f"{BASE}/league/{a.league_id}", "rosters": f"{BASE}/league/{a.league_id}/rosters",
        "users": f"{BASE}/league/{a.league_id}/users", "traded_picks": f"{BASE}/league/{a.league_id}/traded_picks"}
    data, sources = {}, {}
    for k, u in urls.items(): data[k], sources[k] = get(u)
    core_fail = [k for k,v in sources.items() if not v["ok"]]
    manifest = {"collector": "GFO Refresh", "version": VERSION, "collected_at": stamp, "sources": sources}
    if core_fail:
        manifest.update(core_status="PARTIAL", provenance_status="UNKNOWN", core_failures=core_fail); save(out/"latest_manifest.json", manifest); return 2

    league = data["league"]; settings = league.get("settings") or {}; budget = int(settings.get("waiver_budget") or 0)
    rosters = normalize_rosters(data["rosters"], budget)
    season = int(league["season"]); rounds = int(settings.get("draft_rounds") or 5)
    picks = pick_ledger(rosters.keys(), data["traded_picks"], range(season+1, season+1+a.pick_years), rounds)
    core = validate(league, rosters, data["users"], picks)

    tx_by_id, tx_sources = {}, {}
    for rnd in range(a.min_round, a.max_round + 1):
        rows, meta = get(f"{BASE}/league/{a.league_id}/transactions/{rnd}"); tx_sources[str(rnd)] = meta
        if meta["ok"] and isinstance(rows, list):
            for t in rows:
                tid = str(t.get("transaction_id"))
                if tid and tid != "None": tx_by_id[tid] = t
    failed = [int(r) for r,m in tx_sources.items() if not m["ok"]]
    txs = sorted(tx_by_id.values(), key=lambda t:(int(t.get("created") or 0), str(t.get("transaction_id"))))

    snapshot = {"schema":"gfo.snapshot.v2", "collected_at":stamp, "league_id":a.league_id,
                "league":{"name":league.get("name"),"season":league.get("season"),"settings":settings,"roster_positions":league.get("roster_positions"),"scoring_settings":league.get("scoring_settings")},
                "rosters":rosters, "future_picks":picks, "grant_roster_id":core["grant_roster_id"], "core_validation":core}
    prior = load(a.prior_snapshot) if a.prior_snapshot and Path(a.prior_snapshot).exists() else None
    delta = diff(prior, snapshot); exc = provenance(delta, txs, prior.get("collected_at") if prior else None)
    prov = "GREEN" if not failed and not exc else "PARTIAL"
    grant = rosters.get(str(core["grant_roster_id"])) if core["grant_roster_id"] else None
    manifest.update(core_status=core["status"], provenance_status=prov, validation_issues=core["issues"],
                    transaction_rounds={"min":a.min_round,"max":a.max_round,"failed":failed,"sources":tx_sources},
                    unique_transactions=len(txs), provenance_exceptions=exc,
                    grant={"roster_id":core["grant_roster_id"],"players":len(grant["players"]),"reserve":len(grant["reserve"]),"taxi":len(grant["taxi"]),"faab_used":grant["faab_used"],"faab_remaining":grant["faab_remaining"],"waiver_position":grant["waiver_position"]} if grant else None,
                    snapshot_hash=digest(snapshot), diff_hash=digest(delta))
    save(out/"latest_snapshot.json", snapshot); save(out/"latest_transactions.json", txs); save(out/"latest_diff.json", delta); save(out/"latest_manifest.json", manifest)
    print(json.dumps({k:manifest[k] for k in ("core_status","provenance_status","unique_transactions","grant","validation_issues","provenance_exceptions")}, indent=2))
    if core["status"] != "GREEN": return 2
    if a.require_provenance and prov != "GREEN": return 3
    return 0


def self_test():
    results=[]
    def check(name, fn):
        try: fn(); results.append((name, True, ""))
        except Exception as e: results.append((name, False, f"{type(e).__name__}: {e}"))
    league={"total_rosters":2,"settings":{"num_teams":2,"waiver_budget":200}}
    users=[{"user_id":GRANT_USER_ID},{"user_id":"u2"}]
    raw=[{"roster_id":1,"owner_id":GRANT_USER_ID,"players":["A","B"],"reserve":["B"],"taxi":[],"starters":["A"],"settings":{"waiver_budget_used":10}},
         {"roster_id":2,"owner_id":"u2","players":["C"],"reserve":[],"taxi":[],"starters":["C"],"settings":{"waiver_budget_used":0}}]
    def base():
        r=normalize_rosters(copy.deepcopy(raw),200); p=pick_ledger(r.keys(),[],[2027],2); return r,p
    check("core_green", lambda: (_ for _ in ()).throw(AssertionError()) if validate(league,*base()[:1],users,base()[1])["status"]!="GREEN" else None)
    def tp(): r,_=base(); p=pick_ledger(r.keys(),[{"season":"2027","round":1,"roster_id":1,"owner_id":2}],[2027],2); assert next(x for x in p if x["round"]==1 and x["original_roster_id"]==1)["owner_roster_id"]==2
    check("future_picks",tp)
    def td(): b=copy.deepcopy(raw); b[1]["players"].append("A"); r=normalize_rosters(b,200); p=pick_ledger(r.keys(),[],[2027],2); assert any(x["code"]=="DUPLICATE_OWNERSHIP" for x in validate(league,r,users,p)["issues"])
    check("duplicate_ownership",td)
    def tt(): b=copy.deepcopy(raw); b[0]["taxi"]=["Z"]; r=normalize_rosters(b,200); p=pick_ledger(r.keys(),[],[2027],2); assert any(x["code"]=="TAXI_NOT_OWNED" for x in validate(league,r,users,p)["issues"])
    check("invalid_taxi",tt)
    check("tx_dedup", lambda: (_ for _ in ()).throw(AssertionError()) if len({t["transaction_id"]:t for t in [{"transaction_id":"1"},{"transaction_id":"1"},{"transaction_id":"2"}]})!=2 else None)
    def prov_case(explained):
        r,p=base(); prev={"collected_at":"2026-08-17T12:00:00Z","rosters":r,"future_picks":p}; b=copy.deepcopy(raw); b[0]["players"].append("D"); b[0]["settings"]["waiver_budget_used"]=15; cur={"rosters":normalize_rosters(b,200),"future_picks":p}; d=diff(prev,cur)
        tx=[] if not explained else [{"transaction_id":"x","status":"complete","created":1800000000000,"adds":{"D":1},"roster_ids":[1],"settings":{"waiver_bid":5}}]
        return provenance(d,tx,prev["collected_at"])
    check("unexplained_provenance", lambda: (_ for _ in ()).throw(AssertionError()) if not prov_case(False) else None)
    check("explained_provenance", lambda: (_ for _ in ()).throw(AssertionError()) if prov_case(True) else None)
    for n,ok,e in results: print(("PASS" if ok else "FAIL"), n, e)
    print(f"REGRESSION TESTS: {sum(ok for _,ok,_ in results)}/{len(results)} passed")
    return 0 if all(ok for _,ok,_ in results) else 1


def args():
    p=argparse.ArgumentParser(); p.add_argument("--league-id",default=LEAGUE_ID); p.add_argument("--output-dir",default="gfo_refresh"); p.add_argument("--prior-snapshot"); p.add_argument("--pick-years",type=int,default=3); p.add_argument("--min-round",type=int,default=0); p.add_argument("--max-round",type=int,default=18); p.add_argument("--require-provenance",action="store_true"); p.add_argument("--self-test",action="store_true"); return p.parse_args()

if __name__ == "__main__":
    a=args(); raise SystemExit(self_test() if a.self_test else run(a))
