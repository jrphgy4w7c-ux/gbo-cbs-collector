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
    runtime = load_json("runtime_contract.json")
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

    runtime_spec = manifest.get("runtime_contract") or {}
    if runtime_spec.get("path") != "front_office/runtime_contract.json":
        issues.append("sync manifest does not point to the canonical runtime contract")
    if runtime_spec.get("runtime_version") != runtime.get("runtime_version"):
        issues.append("runtime contract version does not match sync manifest")
    if runtime_spec.get("status") != "GREEN":
        issues.append("runtime contract is not GREEN")
    if (runtime.get("chat_model") or {}).get("role") != "workstation":
        issues.append("runtime contract must define chats as workstations")
    if len(runtime.get("bootstrap_sequence") or []) < 5:
        issues.append("runtime bootstrap sequence is incomplete")
    gate_ids = {gate.get("id") for gate in runtime.get("hard_gates") or []}
    for required in (
        "availability_before_acquisition_analysis",
        "deterministic_state_not_memory",
        "identity_internal_presentation_external",
    ):
        if required not in gate_ids:
            issues.append(f"runtime contract missing hard gate: {required}")
    evolution = runtime.get("evolution_loop") or {}
    if "memory alone" not in (evolution.get("rule") or ""):
        issues.append("runtime evolution loop does not prohibit memory-only fixes")
    if len(evolution.get("steps") or []) < 6:
        issues.append("runtime evolution loop is incomplete")

    for name, adapter in adapters.items():
        if adapter.get("front_office") != name:
            issues.append(f"{name} adapter identity mismatch")
        if adapter.get("doctrine_version") != version:
            issues.append(f"{name} doctrine version does not match core")
        if adapter.get("runtime_contract") != "front_office/runtime_contract.json":
            issues.append(f"{name} adapter is not wired to the runtime contract")
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
        if spec.get("adapter_version") != adapter.get("adapter_version"):
            issues.append(f"{name} adapter version does not match sync manifest")

    gfo = adapters.get("GFO") or {}
    if (gfo.get("canonical_state") or {}).get("ownership") != "gfo/current/latest_ownership.json":
        issues.append("GFO canonical state does not publish latest_ownership.json")
    contract = gfo.get("player_status_contract") or {}
    if contract.get("labels") != ["AVAILABLE", "ROSTERED"]:
        issues.append("GFO player-status labels must be exactly AVAILABLE and ROSTERED")
    if not contract.get("ownership_gate"):
        issues.append("GFO player-status contract is missing the pre-analysis ownership gate")
    if "absent from every current Sleeper roster" not in (contract.get("availability_rule") or ""):
        issues.append("GFO availability rule is not roster-derived")
    if "Keep Sleeper player IDs" not in (contract.get("presentation") or ""):
        issues.append("GFO presentation contract does not keep Sleeper IDs internal")
    if not contract.get("waiver_rule"):
        issues.append("GFO player-status contract is missing the waiver rule")

    runtime_gfo = ((runtime.get("sport_requirements") or {}).get("GFO") or {})
    if runtime_gfo.get("ownership_view") != "gfo/current/latest_ownership.json":
        issues.append("runtime GFO requirement does not point to latest_ownership.json")
    if runtime_gfo.get("status_labels") != ["AVAILABLE", "ROSTERED"]:
        issues.append("runtime GFO status labels are not aligned")

    for name, projection in (manifest.get("workbook_projection") or {}).items():
        if projection.get("doctrine_version") != version or projection.get("status") != "GREEN":
            issues.append(f"{name} workbook projection is not aligned and GREEN")

    controls = manifest.get("runtime_controls") or {}
    for name in ("skill", "architecture_audit", "pull_request_gate"):
        if (controls.get(name) or {}).get("status") != "GREEN":
            issues.append(f"runtime control {name} is not GREEN")

    events = [json.loads(line) for line in (ROOT / "change_log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if not events or events[-1].get("doctrine_version") != version:
        issues.append("change log does not end on the current doctrine version")

    if issues:
        print("Front Office OS: RED")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(
        f"Front Office OS: GREEN — doctrine {version}; runtime {runtime['runtime_version']}; "
        f"{len(control_ids)} shared controls; GBO/GFO/workbooks/runtime aligned; GFO ownership gate enforced"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
