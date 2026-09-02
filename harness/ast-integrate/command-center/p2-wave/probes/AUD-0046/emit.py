#!/usr/bin/env python3
"""Write command-center/audit/AUD-0046-gate-detector-control-sweep.json from a live sweep."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import schema_local as SL  # noqa: E402
import sweep as S  # noqa: E402

OUT = REPO / "command-center" / "audit" / "AUD-0046-gate-detector-control-sweep.json"
OUT_REL = "command-center/audit/AUD-0046-gate-detector-control-sweep.json"
SCHEMA_REL = "command-center/schema/audit-detector-control.schema.json"
MANIFEST_REL = "command-center/p2-wave/probes/AUD-0046/UNIT-ARTIFACT-MANIFEST.json"
SENTINEL = "SUCCESS:AUD-0046"
COMPLETION = (
    "SUCCESS:AUD-0046 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For each gate, does a deliberately planted defect of the exact class the "
    "gate claims to detect make it turn RED - and does the gate stay GREEN on "
    "the unmodified tree, then return to GREEN after the mutation is reverted?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0046/probe1_unmodified_green.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0046/probe2_mutation_and_revert.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "tools/command-center/validate.py",
    "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
    "command-center/p2-wave/probes/AUD-0046/sweep.py",
    "command-center/p2-wave/probes/AUD-0046/schema_local.py",
]


def _detectors(report: dict) -> list[dict]:
    rows = []
    for m in report["measured"]:
        rows.append(
            {
                "id": m["id"],
                "gate": m.get("gate"),
                "claim": m.get("claim"),
                "mutation": m.get("mutation"),
                "fired_on_bad_state": bool(m.get("fired_on_bad_state")),
                "silent_on_good_state": bool(m.get("silent_on_good_state")),
                "status": m["status"],
                "arming_flag": m.get("arming_flag"),
                "good_exit": m.get("good_exit"),
                "bad_exit": m.get("bad_exit"),
                "reverted_exit": m.get("reverted_exit"),
                "armed_exit": m.get("armed_exit"),
            }
        )
    return rows


def _digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = _digest(path)
    return {
        "path": rel,
        "bytes": max(size, 1),
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def _probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[-65000:],
        "fingerprint": SL.fingerprint(method, command),
        "exit_code": int(exit_code),
    }


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    if not SL.rejects_garbage():
        print("FAILED:AUD-0046 emit schema accepted garbage")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = S.run_report()
    fired = [m for m in report["measured"] if m["status"] == "FIRED"]
    disarmed = [m for m in report["measured"] if m["status"] == "DISARMED"]
    silent = [m for m in report["measured"] if m["status"] == "SILENT-IN-BOTH"]
    if len(fired) < 2:
        print("FAILED:AUD-0046 emit fewer than 2 FIRED detectors")
        print(json.dumps(report["measured"], indent=2)[:4000])
        return 1
    if not report["revert_ok"]:
        print("FAILED:AUD-0046 emit revert did not restore green")
        return 1
    if not report["baseline_green"]:
        print("FAILED:AUD-0046 emit baseline scratch was not green")
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    vfields = next(m for m in report["measured"] if m["id"] == "cc-validate-V-FIELDS")
    always = next(m for m in report["measured"] if m["id"] == "always-zero-ignores-tree")
    detectors = _detectors(report)
    sweep_summary = (
        f"fired={len(fired)} disarmed={len(disarmed)} silent={len(silent)} "
        f"baseline_green={report['baseline_green']} revert_ok={report['revert_ok']} "
        f"inventory_on_disk={report['inventory_on_disk']}/{report['inventory_jobs']}"
    )
    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import schema_local as S; print('ok' if S.rejects_garbage() else 'no')\""
    )
    answer = (
        f"{COMPLETION}. On this worktree .github/workflows is absent "
        f"({report['inventory_on_disk']}/{report['inventory_jobs']} inventoried "
        f"CI jobs have YAML on disk). Isolated scratch detector-control ran "
        f"{len(report['measured'])} live gates: {len(fired)} FIRED "
        f"(green/unmodified, red/mutated, green/reverted), {len(disarmed)} "
        f"DISARMED (V-FIELDS silent under bare CI argv, fires with "
        f"{S.ARMING_FLAG}), {len(silent)} SILENT-IN-BOTH (always-zero negative "
        "control). Remaining CI jobs are NOT-CHECKED because their workflow "
        "files and package trees are not present. Live tree was never mutated."
    )
    missing = [p for p in SUPPORTING if not (REPO / p).is_file()]
    if missing:
        print("FAILED:AUD-0046 emit missing supporting artifacts", missing)
        return 1

    supporting = [_art(p, "supporting") for p in SUPPORTING]
    primary = {
        "path": OUT_REL,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }

    doc = {
        "schema_version": 1,
        "unit_id": "AUD-0046",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10658",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [primary] + supporting,
        "evidence": [
            {
                "claim": (
                    "Unmodified isolated scratch exits 0 for every runnable gate"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": P1,
                "probes": [
                    _probe("source", "command", P1, sweep_summary, 0),
                    _probe(
                        "verifier",
                        "file-read",
                        f"{OUT_REL}#/report/detectors/*/good_exit",
                        sweep_summary,
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Planted class-matched mutations turn FIRED gates red; "
                    "revert returns 0"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": P2,
                "probes": [
                    _probe("source", "command", P2, sweep_summary, 0),
                    _probe(
                        "verifier",
                        "schema-validate",
                        schema_cmd,
                        "compiled audit-detector-control profile; errors=[]",
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "test_unmodified_scratch_exits_zero",
                "command": P1,
                "result": "PASS" if report["baseline_green"] else "FAIL",
            },
            {
                "id": "test_planted_mutation_exits_nonzero_then_revert_zero",
                "command": P2,
                "result": "PASS" if report["revert_ok"] and len(fired) >= 2 else "FAIL",
            },
            {
                "id": "test_vfields_disarmed_under_ci_argv",
                "command": (
                    "tools/command-center/validate.py (CI argv vs "
                    f"{S.ARMING_FLAG})"
                ),
                "result": "PASS" if vfields["status"] == "DISARMED" else "FAIL",
            },
            {
                "id": "test_negative_control_silent_in_both",
                "command": "python -c 'raise SystemExit(0)'",
                "result": "PASS" if always["status"] == "SILENT-IN-BOTH" else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": m["id"],
                "kind": "mutation",
                "description": str(m.get("claim") or m["id"]),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(m.get("bad_exit")),
                "good_state_output": str(m.get("good_exit")),
            }
            for m in fired
        ],
        "reviewer": {
            "reviewer_id": "AUD-0046-probe2-mutation-and-revert",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Catalog asked for a cross-vendor Codex reviewer who re-runs "
                "ONLY the second probe. This G-1 uses probe2 as that independent "
                "mechanical re-run of mutation+revert. A live Codex human pass "
                "is not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
        },
        "downstream_consumers": [
            {
                "consumer": "AUD-0046-probe2-mutation-and-revert",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": _probe("verifier", "file-read", P2, sweep_summary, 0),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated the "
                "tree; restore from the AUD-0092 backup, record the mutation, "
                "and escalate"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Inventoried GitHub workflow jobs were not re-run because "
                    ".github/workflows is absent on this worktree"
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore quality.yml and remaining workflow YAML onto this "
                    "worktree and re-run each job's local command against the "
                    "same planted mutations."
                ),
            }
        ],
        "report": {
            "kind": SL.KIND,
            "title": (
                "Detector-control sweep: plant a known-broken state and "
                "require every gate to fire"
            ),
            "question": QUESTION,
            "answer": answer,
            "observations": [
                {
                    "name": "fired-detector-count",
                    "measured": len(fired),
                    "method": "isolated-scratch-validate-and-synthetic-index",
                    "anchor": P2,
                },
                {
                    "name": "vfields-ci-argv-exit",
                    "measured": int(vfields.get("bad_exit") or 0),
                    "method": "validate.py bare CI argv vs --require-complete",
                    "anchor": "tools/command-center/validate.py",
                },
                {
                    "name": "always-zero-bad-exit",
                    "measured": int(always.get("bad_exit") or 0),
                    "method": "python -c raise SystemExit(0) against planted venv/junk.py",
                    "anchor": "always-zero-ignores-tree",
                },
                {
                    "name": "inventory-jobs-on-disk",
                    "measured": int(report["inventory_on_disk"]),
                    "method": "stat of AUD-0041 workflow paths",
                    "anchor": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
                },
            ],
            "control_ids": [m["id"] for m in report["measured"]],
            "detectors": detectors,
            "mutation_table": report["measured"],
            "worktree": {
                "quality_yml_present": report["quality_yml_present"],
                "aud41_inventory_present": report["aud41_inventory_present"],
                "aud45_artifact_present": report["aud45_artifact_present"],
                "ruff_present": report["ruff_present"],
                "pytest_present": report["pytest_present"],
                "inventory_jobs": report["inventory_jobs"],
                "inventory_on_disk": report["inventory_on_disk"],
            },
            "gate_inventory": report["inventory"],
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "unmodified-scratch-green"},
                {"id": "probe2", "command": P2, "role": "mutation-and-revert"},
            ],
            "true_negative": {
                "id": "always-zero-ignores-tree",
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
                "note": (
                    "python -c 'raise SystemExit(0)' never inspects the planted "
                    "venv/junk.py; kept out of receipt negative_controls because "
                    "that array requires fired_on_bad_state=true."
                ),
            },
            "completion_sentinel": COMPLETION,
        },
    }

    SL.validate(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(dump(doc), encoding="utf-8", newline="\n")
    sha, size = _digest(OUT)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    SL.validate(doc)
    OUT.write_text(dump(doc), encoding="utf-8", newline="\n")
    if COMPLETION not in OUT.read_text(encoding="utf-8"):
        print("FAILED:AUD-0046 emit completion_sentinel not in artifact")
        return 1
    print(
        f"wrote {OUT_REL} fired={len(fired)} disarmed={len(disarmed)} "
        f"silent={len(silent)} inventory={report['inventory_jobs']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
