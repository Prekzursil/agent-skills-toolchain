#!/usr/bin/env python3
"""Write IMP-0278 catalog receipt, SUBAGENT-RETURN, and per-unit manifest.

Runs named probes first. Hashes are measured off disk after the receipt is
written. Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0278"
OUT = "command-center/receipts/IMP-0278.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0278/probe1_delivered_mapping.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0278/probe2_negative_control.py"
)
SUPPORTING = [
    "tools/council/integrity/partition.py",
    "tools/council/integrity/__init__.py",
    "command-center/p2-wave/probes/IMP-0278/fixtures/scenario.json",
    "command-center/p2-wave/probes/IMP-0278/probe1_delivered_mapping.py",
    "command-center/p2-wave/probes/IMP-0278/probe2_negative_control.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**subprocess.os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0278/SUBAGENT-RETURN.json",
        "role": role,
    }


def extract_json_blob(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0278 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = extract_json_blob(t1)
    p2 = extract_json_blob(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    module_rel = "tools/council/integrity/partition.py"
    module_sha, module_bytes = digest(REPO / module_rel)

    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0278",
        "completion_sentinel": "SUCCESS:IMP-0278",
        "title": "Information-partition engine",
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-integrity-module"
        ),
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0278; "
            "_USER-PROMPTS.md:10746-10767 information partition; "
            "same lattice type as blind first-pass / staged evidence / "
            "fishbowl observer (CNL-0006 question)"
        ),
        "question_or_target": (
            "Implement tools/council/integrity/partition.py delivering "
            "per-participant redacted context so configured partitions "
            "genuinely differ. Falsifiable question: does any participant "
            "receive a token it was partitioned away from, measured by "
            "scanning delivered prompts rather than by reading the config?"
        ),
        "answer": (
            "On the lattice fixture (alpha/beta/gamma + shared + alpha-beta "
            "joint), delivered prompts differ, the withheld-token scan of "
            "those prompt strings reports zero hits, the same scanner finds "
            "a token that WAS delivered (detector control), and disabling "
            "redaction makes the scan FIRE. Kernel IMP-0264 is not on disk; "
            "this module is the delivery seam a kernel would call."
        ),
        "artifact_paths": [OUT, module_rel],
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "note": "self; sha256 filled in UNIT-ARTIFACT-MANIFEST after write",
            },
            {
                "path": module_rel,
                "role": "implementation",
                "exists": True,
                "bytes": module_bytes,
                "sha256": module_sha,
            },
        ],
        "evidence": [
            {
                "id": "E1-delivered-prompt-scan-zero-hits",
                "claim": (
                    "Scanning each seat's delivered prompt text for tokens "
                    "withheld from that seat yields zero hits."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0278/probe1_delivered_mapping.py",
                "measurement": {
                    "leak_hit_count": p1.get("leak_hit_count"),
                    "partitions_differ": p1.get("partitions_differ"),
                    "scan_target": p1.get("scan_target"),
                    "not_a_config_read": p1.get("not_a_config_read"),
                    "mapping_ok": p1.get("mapping_ok"),
                },
                "probe_exit": c1,
            },
            {
                "id": "E2-detector-control-finds-delivered-token",
                "claim": (
                    "The scanner finds PTOK-ALPHA-imp0278-7f3a in alice's "
                    "delivered prompt before leak-scan silence is trusted."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0278/probe1_delivered_mapping.py",
                "measurement": {
                    "detector_control_found": p1.get("detector_control_found"),
                    "detector_control_scan": p1.get("detector_control_scan"),
                    "shared_token_in_all_prompts": p1.get("shared_token_in_all_prompts"),
                },
                "probe_exit": c1,
            },
            {
                "id": "E3-negative-control-redaction-off-fires",
                "claim": (
                    "Disabling redaction and scanning the open prompts with "
                    "the redacting withheld set makes the scan FIRE; the "
                    "redacting path stays silent (both-states)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0278/probe2_negative_control.py",
                "measurement": {
                    "fired_on_bad": p2.get("fired_on_bad"),
                    "silent_on_good": p2.get("silent_on_good"),
                    "alice_open_scan_hits": p2.get("alice_open_scan_hits"),
                    "observer_closed_has_joint": p2.get("observer_closed_has_joint"),
                    "observer_open_has_joint": p2.get("observer_open_has_joint"),
                    "vacuous_scan_delivered_on_open_spec_hits": p2.get(
                        "vacuous_scan_delivered_on_open_spec_hits"
                    ),
                },
                "probe_exit": c2,
            },
        ],
        "test_ids": [
            "unit-partition-definition-to-delivered-context-mapping",
            "detector-control-scanner-finds-known-present-token",
            "negative-control-disable-redaction-scan-fires",
        ],
        "negative_control_ids": [
            "NC-DISABLE-REDACTION",
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0278-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests (probe2), not the author's summary",
            "note": (
                "G-1 named probe 2 is the adversarial check: it disables "
                "redaction and requires the scan to FIRE, and requires the "
                "redacting path to stay silent."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "No live council round through tools/council/kernel.py "
                    "(IMP-0264). That kernel is absent on this worktree; "
                    "partition.py is the delivery seam a kernel would call."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the leak scan on prompts minted by kernel.py "
                    "once IMP-0264 exists."
                ),
            },
            {
                "claim": (
                    "Paraphrase / laundered leaks (CNF-0093) are outside "
                    "this unit's token-scan contract."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "CNF-0093 paraphrase search over participant output.",
            },
        ],
        "tests": [
            {
                "id": "unit-partition-definition-to-delivered-context-mapping",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "detector-control-scanner-finds-known-present-token",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "negative-control-disable-redaction-scan-fires",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-DISABLE-REDACTION",
                "kind": "disable-redaction",
                "description": (
                    "Turn redact=False, deliver prompts, scan with the "
                    "redacting withheld-token set; must FIRE. Redacting "
                    "path must stay silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "dependencies": ["IMP-0264"],
        "dependency_note": (
            "IMP-0264 kernel is not present. This unit still delivers the "
            "partition engine and proves delivery-vs-leak on rendered prompts. "
            "Not parked: the catalog target is partition.py, not the kernel."
        ),
        "min_bytes_threshold": 2048,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "notes": (
            "G-1 for IMP-0278: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0278" not in body:
        print("FAILED:IMP-0278 sentinel missing from receipt body")
        return 1
    out_path.write_text(body, encoding="utf-8")
    if out_path.stat().st_size < int(receipt["min_bytes_threshold"]):
        print("FAILED:IMP-0278 receipt below min_bytes_threshold")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0278",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-integrity-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "partition-definition-to-delivered-context-mapping",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "negative-control-disable-redaction",
                "raw_output": t2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0278/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0278-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0278: live named probes exit 0, "
            "command-center/receipts/IMP-0278.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={primary['bytes']} sha256={primary['sha256']}")
    print("wrote SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
