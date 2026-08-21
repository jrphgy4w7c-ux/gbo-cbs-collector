#!/usr/bin/env python3
"""Build GFO's deterministic Sleeper ownership/availability view.

A resolved Sleeper player ID present in the ownership index is ROSTERED.
A resolved Sleeper player ID absent from the ownership index is AVAILABLE.
Player IDs are internal identity plumbing; user-facing responses should prefer
the human status conclusion and owner/team when useful.
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

BASE = "https://api.sleeper.app/v1"
SCHEMA = "gfo.ownership.v1"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch_users(league_id, timeout=25):
    req = urllib.request.Request(
        f"{BASE}/league/{league_id}/users",
        headers={"User-Agent": "GFO-Ownership/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def user_map(users):
    out = {}
    for user in users or []:
        uid = str(user.get("user_id"))
        metadata = user.get("metadata") or {}
        out[uid] = {
            "display_name": user.get("display_name"),
            "team_name": metadata.get("team_name"),
        }
    return out


def build_ownership(snapshot, users=None):
    users_by_id = user_map(users)
    index = {}
    for rid, roster in (snapshot.get("rosters") or {}).items():
        owner_id = str(roster.get("owner_id"))
        owner = users_by_id.get(owner_id) or {}
        reserve = set(str(x) for x in (roster.get("reserve") or []))
        taxi = set(str(x) for x in (roster.get("taxi") or []))
        starters = set(str(x) for x in (roster.get("starters") or []))
        for raw_pid in roster.get("players") or []:
            pid = str(raw_pid)
            if pid in taxi:
                placement = "TAXI"
            elif pid in reserve:
                placement = "RESERVE"
            elif pid in starters:
                placement = "STARTER"
            else:
                placement = "ROSTER"
            if pid in index:
                raise ValueError(f"duplicate ownership for player {pid}")
            index[pid] = {
                "status": "ROSTERED",
                "roster_id": int(rid),
                "owner_id": owner_id,
                "owner_name": owner.get("display_name"),
                "team_name": owner.get("team_name"),
                "placement": placement,
            }

    return {
        "schema": SCHEMA,
        "collected_at": snapshot.get("collected_at"),
        "league_id": str(snapshot.get("league_id")),
        "availability_rule": "resolved player absent from ownership_index => AVAILABLE; present => ROSTERED",
        "labels": ["AVAILABLE", "ROSTERED"],
        "presentation_rule": "Keep Sleeper IDs and API mechanics internal unless Grant asks; default to AVAILABLE or ROSTERED, with owner/team and waiver-clear timing when useful.",
        "ownership_index": dict(sorted(index.items())),
        "owned_player_count": len(index),
    }


def player_status(ownership, player_id):
    row = (ownership.get("ownership_index") or {}).get(str(player_id))
    if row:
        return row
    return {"status": "AVAILABLE"}


def self_test():
    snapshot = {
        "collected_at": "2026-08-21T12:00:00Z",
        "league_id": "league",
        "rosters": {
            "1": {
                "owner_id": "u1",
                "players": ["A", "B", "C"],
                "reserve": ["B"],
                "taxi": ["C"],
                "starters": ["A"],
            },
            "2": {
                "owner_id": "u2",
                "players": ["D"],
                "reserve": [],
                "taxi": [],
                "starters": [],
            },
        },
    }
    users = [
        {"user_id": "u1", "display_name": "Grant", "metadata": {"team_name": "Big Nasty"}},
        {"user_id": "u2", "display_name": "Other", "metadata": {"team_name": "Other Team"}},
    ]
    ownership = build_ownership(snapshot, users)
    assert ownership["owned_player_count"] == 4
    assert player_status(ownership, "A")["status"] == "ROSTERED"
    assert player_status(ownership, "A")["placement"] == "STARTER"
    assert player_status(ownership, "B")["placement"] == "RESERVE"
    assert player_status(ownership, "C")["placement"] == "TAXI"
    assert player_status(ownership, "Z") == {"status": "AVAILABLE"}
    assert player_status(ownership, "A")["team_name"] == "Big Nasty"

    duplicate = json.loads(json.dumps(snapshot))
    duplicate["rosters"]["2"]["players"].append("A")
    try:
        build_ownership(duplicate, users)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate ownership must fail")

    print("GFO ownership regression tests: PASS")
    return 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot")
    parser.add_argument("--users")
    parser.add_argument("--output")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.self_test:
        return self_test()
    if not args.snapshot or not args.output:
        raise SystemExit("--snapshot and --output are required unless --self-test is used")
    snapshot = load(args.snapshot)
    users = load(args.users) if args.users else fetch_users(snapshot["league_id"])
    save(args.output, build_ownership(snapshot, users))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
