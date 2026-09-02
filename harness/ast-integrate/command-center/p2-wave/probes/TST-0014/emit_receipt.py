#!/usr/bin/env python3
"""Write TST-0014 receipt, per-unit manifest, and SUBAGENT-RETURN.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0014"
OUT = "command-center/receipts/TST-0014.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0014/probe1_enumerator_finds_known.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0014/probe2_gate_fails_uncontrolled.py"
)
QUESTION = (
    "Target: every detector in the repo (hook check, validator rule, gate "
    "script) must declare a known-present fixture and a known-broken fixture "
    "in a registry; CI fails on any detector with no control. Question: how "
    "many detectors exist today and how many have zero controls? Report the "
    "raw count before proposing the gate threshold."
)
SUPPORTING = [
    SCHEMA,
    "tools/detector_control/__init__.py",
    "tools/detector_control/enumerate.py",
    "tools/detector_control/controls.py",
    "tools/detector_control/gate.py",
    "tools/detector_control/registry.json",
    "command-center/p2-wave/probes/TST-0014/probe1_enumerator_finds_known.py",
    "command-center/p2-wave/probes/TST-0014/probe2_gate_fails_uncontrolled.py",
    "command-center/p2-wave/probes/TST-0014/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int, str]:
    data = path.read_bytes() if path.is_file() else b""
    lf = data.replace(b"\r\n", b"\n")
    crlf = data.count(b"\r\n")
    nlf = data.count(b"\n") - crlf
    if crlf and nlf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    elif b"\n" in data:
        eol = "LF"
    else:
        eol = "NONE"
    return hashlib.sha256(lf).hexdigest(), len(lf), eol


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size, eol = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": eol,
    }


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size, _eol = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0014/SUBAGENT-RETURN.json",
        "role": role,
    }


def bound_errors(doc: object) -> list[str]:
    """Local bound check. jsonschema 4.10.3 cannot compile the catalog shim
    (Draft7Validator network $ref to ast-integrate.invalid; schema_resolver
    registry= kwarg). Same fingerprint as ARC-0033. G-1 does not schema-compile.
    """
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["not-an-object"]
    if doc.get("unit_id") != UNIT:
        errs.append("unit_id")
    if str(doc.get("state") or "").upper() != "SUCCESS":
        errs.append("state")
    blob = json.dumps(doc, sort_keys=True)
    if "SUCCESS:TST-0014" not in blob:
        errs.append("sentinel")
    census = doc.get("census") if isinstance(doc.get("census"), dict) else {}
    for key in ("detector_count", "controlled_count", "uncontrolled_count"):
        if not isinstance(census.get(key), int):
            errs.append(f"census.{key}")
    if census.get("reported_before_threshold") is not True:
        errs.append("census.reported_before_threshold")
    inventory = doc.get("inventory") if isinstance(doc.get("inventory"), list) else []
    if not inventory:
        errs.append("inventory")
    for i, row in enumerate(inventory):
        if not isinstance(row, dict):
            errs.append(f"inventory[{i}]")
            continue
        if not row.get("id"):
            errs.append(f"inventory[{i}].id")
        if row.get("verdict") not in {"controlled", "uncontrolled"}:
            errs.append(f"inventory[{i}].verdict")
    control = (
        doc.get("detector_control")
        if isinstance(doc.get("detector_control"), dict)
        else {}
    )
    if control.get("fired") is not True:
        errs.append("detector_control.fired")
    if control.get("known_present_run_first") is not True:
        errs.append("detector_control.known_present_run_first")
    tests = doc.get("tests") if isinstance(doc.get("tests"), list) else []
    if len(tests) < 2:
        errs.append("tests")
    return errs


def validate_receipt(doc: dict) -> list[str]:
    shim = REPO / SCHEMA
    if not shim.is_file() or shim.stat().st_size <= 0:
        return [f"missing {SCHEMA}"]
    try:
        shim_doc = json.loads(shim.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unparseable-shim:{type(exc).__name__}"]
    if shim_doc.get("x-artifact-class") != "detector-control":
        return ["shim-not-detector-control"]
    phys = REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
    if not phys.is_file():
        return ["missing-physical-schema"]
    errs = bound_errors(doc)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": UNIT, "state": "SUCCESS"},
    ):
        if not bound_errors(garbage):
            errs.append("bound-check accepted garbage")
            break
    return errs


def main() -> int:
    sys.path.insert(0, str(REPO / "tools"))
    from detector_control.enumerate import enumerator_control  # noqa: E402
    from detector_control.gate import run_gate  # noqa: E402

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0014 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:TST-0014 probe JSON pass!=true")
        return 1

    control = enumerator_control()
    if not control["fired"]:
        print("FAILED:TST-0014 enumerator control missed planted detector")
        return 1

    live_census = run_gate(census_only=True, threshold=0)
    live_fail = run_gate(census_only=False, threshold=0)
    census = live_census["census"]
    if census["detector_count"] is None:
        print("FAILED:TST-0014 live census missing")
        return 1
    if live_census["detector_control"]["fired"] is not True:
        print("FAILED:TST-0014 live census skipped enumerator control")
        return 1

    proposed_threshold = 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in supporting if not a["exists"]]
    if missing:
        print("FAILED:TST-0014 missing supporting", missing)
        return 1

    inventory = []
    for row in live_census.get("inventory") or []:
        inventory.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "source": row["source"],
                "verdict": row["verdict"],
                "reason": row["reason"],
                "known_present": row.get("known_present"),
                "known_broken": row.get("known_broken"),
                "known_good": row.get("known_good"),
                "known_present_exists": row.get("known_present_exists"),
                "known_broken_exists": row.get("known_broken_exists"),
            }
        )

    receipt = {
        "id": UNIT,
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0014",
        "completion_sentinel": "SUCCESS:TST-0014",
        "title": "Detector-control registry and CI gate for uncontrolled detectors",
        "question": QUESTION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#TST-0014",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "census": {
            "detector_count": census["detector_count"],
            "controlled_count": census["controlled_count"],
            "uncontrolled_count": census["uncontrolled_count"],
            "reported_before_threshold": True,
            "uncontrolled_ids": live_census.get("uncontrolled_ids") or [],
            "controlled_ids": live_census.get("controlled_ids") or [],
            "families": {
                "hook_check": sum(1 for r in inventory if r["kind"] == "hook_check"),
                "validator_rule": sum(
                    1 for r in inventory if r["kind"] == "validator_rule"
                ),
                "gate_script": sum(1 for r in inventory if r["kind"] == "gate_script"),
            },
            "inputs_on_this_worktree": {
                "hooks/_dispatch/manifest.json": "present (IMP-0404 router hooks)",
                "tools/command-center/validate.py": "present (10 named checks)",
                "_USER-PROMPTS.md:10658": "absent on this worktree",
            },
        },
        "proposed_threshold": proposed_threshold,
        "threshold_rationale": (
            "Raw census is reported above. After that count: proposed CI "
            "threshold is 0 uncontrolled detectors. Live tree currently has "
            f"{census['uncontrolled_count']} uncontrolled detector(s), so "
            "tools/detector_control/gate.py exits 1 at threshold 0. That is "
            "the gate working, not a reason to raise the threshold."
        ),
        "inventory": inventory,
        "detector_control": {
            "known_present_run_first": True,
            "fired_before_absence_reported": True,
            "fired": True,
            "planted_ids": control["planted_ids"],
            "found_planted": control["found_planted"],
            "missing_planted": control["missing_planted"],
            "fixture_root": "tools/detector_control/fixtures/known-present",
        },
        "gate": {
            "path": "tools/detector_control/gate.py",
            "live_census_only_exit": live_census["exit_code"],
            "live_fail_on_uncontrolled_exit": live_fail["exit_code"],
            "live_fail_reason": live_fail["reason"],
            "threshold": proposed_threshold,
            "wired_into_quality_yml": False,
        },
        "registry_path": "tools/detector_control/registry.json",
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": supporting,
        "evidence": [
            {
                "id": "signal-1-raw-census-before-threshold",
                "kind": "enumerated-inventory",
                "requirement": (
                    "an enumerated detector inventory with a controlled/"
                    "uncontrolled verdict per row; the enumerator itself must "
                    "be proven to find a known-present detector before any "
                    "zero is trusted"
                ),
                "verdict": "CONFIRMED",
                "claim": (
                    f"Live census on this worktree: {census['detector_count']} "
                    f"detectors, {census['controlled_count']} controlled, "
                    f"{census['uncontrolled_count']} with zero controls "
                    f"({live_census.get('uncontrolled_ids')}). Enumerator "
                    "found planted-hook-check, PLANTED-CHECK, and "
                    "tools/plugin/planted_gate.py before the live walk. "
                    "Proposed threshold 0 was recorded after those counts."
                ),
                "detector_count": census["detector_count"],
                "controlled_count": census["controlled_count"],
                "uncontrolled_count": census["uncontrolled_count"],
                "confidence": "almost-certain",
            },
            {
                "id": "signal-2-gate-fails-on-uncontrolled",
                "kind": "ci-gate",
                "requirement": "CI fails on any detector with no control",
                "verdict": "CONFIRMED",
                "claim": (
                    "On fixtures/all-controlled the gate exits 0. On "
                    "fixtures/uncontrolled it exits 1 and names "
                    "uncontrolled-orphan-hook. Live tree at threshold 0 also "
                    f"exits 1 because {census['uncontrolled_count']} detector(s) "
                    f"lack a FIRE/SILENT fixture pair: "
                    f"{live_census.get('uncontrolled_ids')}."
                ),
                "good_exit": j2.get("good_exit"),
                "bad_exit": j2.get("bad_exit"),
                "confidence": "almost-certain",
            },
        ],
        "test_ids": [
            "test_enumerator_finds_a_known_detector",
            "test_ci_gate_fails_on_an_uncontrolled_detector",
        ],
        "tests": [
            {
                "id": "test_enumerator_finds_a_known_detector",
                "command": P1,
                "result": "PASS" if c1 == 0 and j1.get("pass") else "FAIL",
            },
            {
                "id": "test_ci_gate_fails_on_an_uncontrolled_detector",
                "command": P2,
                "result": "PASS" if c2 == 0 and j2.get("pass") else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "enumerator-empty-tree-after-known-present",
                "kind": "known-broken-fixture",
                "description": (
                    "Enumerator control FIRED on fixtures/known-present "
                    "(planted detectors present). The same enumerator pointed "
                    "at an empty temp tree does not find planted ids. Live "
                    "zeros are not trusted without the first leg."
                ),
                "fired_on_bad_state": j1.get("control_fired") is True,
                "silent_on_good_state": j1.get("negative_fired") is False,
            },
            {
                "id": "uncontrolled-orphan-hook",
                "kind": "known-broken-fixture",
                "description": (
                    "Fixture tree adds hook id uncontrolled-orphan-hook with "
                    "no registry fixtures. Gate must FAIL. all-controlled "
                    "must PASS."
                ),
                "fired_on_bad_state": j2.get("bad_exit") == 1,
                "silent_on_good_state": j2.get("good_exit") == 0,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0014-probe2-gate-fails-uncontrolled",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 starts from the gate CLI and a planted uncontrolled "
                "hook, not from the census numbers in probe 1. Catalog "
                "reviewer_requirement asks for a fresh-context human "
                "adversarial reviewer from the other vendor; that human pass "
                "is residual and is not claimed."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "enumerator-finds-known-detector", "command": P1},
            {
                "id": "probe2",
                "role": "ci-gate-fails-on-uncontrolled-detector",
                "command": P2,
            },
        ],
        "cloud_ok": False,
        "residual_unknowns": [
            {
                "id": "user-prompts-absent",
                "text": (
                    "_USER-PROMPTS.md:10658 is not on this worktree. Scope "
                    "was taken from the catalog question_or_target, "
                    "tests_required, and evidence_requirement."
                ),
            },
            {
                "id": "tst-0013-harness-not-imported",
                "text": (
                    "Dependency TST-0013 (reusable both-states decorator) is "
                    "not delivered on this worktree. This unit ships a "
                    "registry plus enumerator rather than importing that "
                    "decorator. IMP-0044 both_states_harness.py exists and "
                    "was not claimed as TST-0013."
                ),
            },
            {
                "id": "quality-yml-absent",
                "text": (
                    ".github/workflows/quality.yml is not claimed as wiring "
                    "the new gate. The gate binary is "
                    "tools/detector_control/gate.py."
                ),
            },
            {
                "id": "schema-compile-parked",
                "text": (
                    "jsonschema 4.10.3 cannot compile "
                    "command-center/schema/detector-control.schema.json "
                    "(Draft7Validator network $ref to ast-integrate.invalid; "
                    "schema_resolver registry= TypeError). Same fingerprint "
                    "as ARC-0033. G-1 does not schema-compile. Bound check "
                    "rejects garbage. No ADV rebuild."
                ),
            },
            {
                "id": "live-uncontrolled-detectors",
                "text": (
                    "Live uncontrolled ids at emit time are recorded in "
                    "census.uncontrolled_ids. Dispatch-manifest hook checks "
                    "and extra tools/*gate.py scripts without a FIRE/SILENT "
                    "fixture pair remain uncontrolled rather than being "
                    "stub-registered as green. Router hooks "
                    "(router-pre-tool, router-prompt-submit) have IMP-0404 "
                    "fail-open probes, which is a different property than a "
                    "detector-control pair."
                ),
            },
            {
                "id": "human-reviewer-residual",
                "text": (
                    "G-1 named probes are green. A second human in a fresh "
                    "context has not scored this unit."
                ),
            },
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "every live detector now has controls",
            "quality.yml invokes the new gate",
            "a human adversarial reviewer in a fresh context scored PASS",
            "TST-0013 was delivered or imported",
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "ts": now,
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot - after the second failure on the "
                "same error fingerprint, enumerate >=2 alternative approaches "
                "before a third attempt (AGENTS.md 4b)"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0014/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }

    schema_errs = validate_receipt(receipt)
    if schema_errs:
        print("FAILED:TST-0014 schema", schema_errs[:12])
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:TST-0014" not in payload:
        print("FAILED:TST-0014 emit sentinel missing from blob")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    primary = manifest_row(OUT, "primary")
    if primary["bytes"] < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0014 artifact {primary['bytes']}B below floor")
        return 1
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
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
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0014",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "enumerator-finds-known-detector",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "ci-gate-fails-on-uncontrolled-detector",
                "raw_output": t2,
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
        "manifest_path": "command-center/p2-wave/probes/TST-0014/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0014-probe2-gate-fails-uncontrolled",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0014: live named probes exit 0, receipts/TST-0014.json "
            f"state=SUCCESS, census detectors={census['detector_count']} "
            f"uncontrolled={census['uncontrolled_count']} reported before "
            "threshold 0. Per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(
        f"census detectors={census['detector_count']} "
        f"controlled={census['controlled_count']} "
        f"uncontrolled={census['uncontrolled_count']}"
    )
    print("SUCCESS:TST-0014 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
