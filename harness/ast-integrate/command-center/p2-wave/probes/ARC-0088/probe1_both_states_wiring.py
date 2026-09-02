#!/usr/bin/env python3
"""Probe 1: both-states wiring proof.

Unregister (file still on disk) => wiring proof fails.
Re-register and live-invoke => both signals fire and proof passes.
Manifest/file presence alone is rejected as proof.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import dispatch as D  # noqa: E402
import harness as H  # noqa: E402

OUT = HERE / "probe1-both-states-wiring.raw.json"
CONTRACT = REPO / "command-center/phase4/contracts/ARC-0088.json"


def load_contract() -> dict | None:
    if not CONTRACT.is_file() or CONTRACT.stat().st_size <= 0:
        return None
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def check_contract(doc: dict) -> list[str]:
    errs: list[str] = []
    if doc.get("unit_id") != "ARC-0088":
        errs.append("unit-id")
    if "SUCCESS:ARC-0088" not in json.dumps(doc):
        errs.append("sentinel")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"state={st}")
    proof = doc.get("wiring_proof") or {}
    if proof.get("manifest_file_is_not_proof") is not True:
        errs.append("manifest-treated-as-proof")
    signals = list(proof.get("required_signals") or [])
    if signals != ["dispatcher_record", "side_effect"]:
        errs.append(f"signals={signals}")
    events = list(doc.get("event_types") or [])
    if list(D.EVENT_TYPES) != events:
        errs.append("event-types-diverge-from-dispatcher")
    stdin_fields = list((doc.get("stdin_json_shape") or {}).get("required_fields") or [])
    if stdin_fields != list(D.STDIN_REQUIRED_FIELDS):
        errs.append("stdin-fields-diverge")
    return errs


def run_both_states() -> dict:
    with tempfile.TemporaryDirectory(prefix="arc0088-p1-") as tmp:
        root = Path(tmp)
        script = H.write_script(root / "hooks" / "marker.py", H.MARKER_HOOK)
        spec = H.spec_for("hook.marker", "PreToolUse", script)
        manifest = H.write_manifest(root / "manifest.json", [spec])
        payload = D.default_stdin("PreToolUse", str(root), {"tool_name": "Bash", "tool_input": {}})

        live_dir = root / "live"
        live = D.fire_event(manifest, payload, live_dir, "hook.marker")

        unreg_manifest = H.write_manifest(root / "manifest-unregistered.json", [])
        # File remains on disk; only the registration row is gone.
        unreg_dir = root / "unreg"
        unreg = D.fire_event(unreg_manifest, payload, unreg_dir, "hook.marker")

        file_only_claimed = D.wiring_proof(
            manifest_present=True,
            file_present=True,
            dispatcher_record_observed=False,
            side_effect_observed=False,
        )
        return {
            "registered": live,
            "unregistered": unreg,
            "file_only_claimed_wired": file_only_claimed["wired"],
            "file_still_present_when_unregistered": script.is_file(),
        }


def main() -> int:
    run = run_both_states()
    live = run["registered"]
    unreg = run["unregistered"]
    errs: list[str] = []

    if unreg["wiring"]["wired"] is not False:
        errs.append("unregistered-still-wired")
    if unreg["wiring"]["dispatcher_record_observed"] or unreg["wiring"]["side_effect_observed"]:
        errs.append("unregistered-emitted-signal")
    if not run["file_still_present_when_unregistered"]:
        errs.append("unregistered-deleted-file-instead-of-unregister")
    if live["wiring"]["wired"] is not True:
        errs.append("registered-not-wired")
    if not live["wiring"]["dispatcher_record_observed"]:
        errs.append("missing-dispatcher-record")
    if not live["wiring"]["side_effect_observed"]:
        errs.append("missing-side-effect")
    if live["process_exit"] != 0 or live["session_continue"] is not True:
        errs.append("registered-did-not-continue")
    if run["file_only_claimed_wired"] is not False:
        errs.append("file-presence-accepted-as-wiring")

    doc = load_contract()
    contract_checked = False
    if doc is not None:
        contract_checked = True
        errs.extend(check_contract(doc))

    payload = {
        "probe": "probe1-both-states-wiring",
        "unit_id": "ARC-0088",
        "registered_wired": live["wiring"]["wired"],
        "unregistered_wired": unreg["wiring"]["wired"],
        "file_only_claimed_wired": run["file_only_claimed_wired"],
        "dispatcher_record_observed": live["wiring"]["dispatcher_record_observed"],
        "side_effect_observed": live["wiring"]["side_effect_observed"],
        "contract_checked": contract_checked,
        "errors": errs,
        "pass": not errs,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"registered_wired={live['wiring']['wired']} "
        f"unregistered_wired={unreg['wiring']['wired']} "
        f"file_only={run['file_only_claimed_wired']} "
        f"signals=dispatcher:{live['wiring']['dispatcher_record_observed']}"
        f"+side:{live['wiring']['side_effect_observed']} "
        f"contract_checked={contract_checked}"
    )
    if errs:
        print("FAILED:ARC-0088-probe1 " + "; ".join(errs[:8]))
        return 1
    print("SUCCESS:ARC-0088-probe1 both-states wiring proof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
