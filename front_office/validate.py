#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> int:
    core = load_json("core.json")
    manifest = load_json("sync_manifest.json")
    adapters = {
        name: load_json(spec["path"].removeprefix("front_office/"))
        for name, spec in manifest["adapters"].items()
    }
    version = core["doctrine_version"]
    control_ids = [control["id"] for control in core["controls"]]
    issues = []

    if len(control_ids) != len(set(control_ids)):
        issues.append("core control IDs are not unique")
    if manifest.get("doctrine_version") != version:
        issues.append("sync manifest doctrine version does not match core")
    if manifest.get("status") != "GREEN":
        issues.append("sync manifest is not GREEN")

    for name, adapter in adapters.items():
        if adapter.get("front_office") != name:
            issues.append(f"{name} adapter identity mismatch")
        if adapter.get("doctrine_version") != version:
            issues.append(f"{name} doctrine version does not match core")
        translated = set((adapter.get("translations") or {}).keys())
        missing = sorted(set(control_ids) - translated)
        extra = sorted(translated - set(control_ids))
        if missing:
            issues.append(f"{name} missing translations: {', '.join(missing)}")
        if extra:
            issues.append(f"{name} has unknown translations: {', '.join(extra)}")
        spec = manifest["adapters"][name]
        if spec.get("doctrine_version") != version or spec.get("status") != "GREEN":
            issues.append(f"{name} sync-manifest entry is not aligned and GREEN")

    for name, projection in (manifest.get("workbook_projection") or {}).items():
        if projection.get("doctrine_version") != version or projection.get("status") != "GREEN":
            issues.append(f"{name} workbook projection is not aligned and GREEN")

    runtime = manifest.get("runtime_controls") or {}
    for name in ("skill", "architecture_audit", "pull_request_gate"):
        if (runtime.get(name) or {}).get("status") != "GREEN":
            issues.append(f"runtime control {name} is not GREEN")

    events = [json.loads(line) for line in (ROOT / "change_log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if not events or events[-1].get("doctrine_version") != version:
        issues.append("change log does not end on the current doctrine version")

    if issues:
        print("Front Office OS: RED")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(f"Front Office OS: GREEN — doctrine {version}; {len(control_ids)} shared controls; GBO/GFO/workbooks/runtime aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
