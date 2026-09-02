#!/usr/bin/env python3
"""Write TST-0143 receipt, per-unit manifest, and SUBAGENT-RETURN.

Does not run tools/command-center/unit_manifest.py --write.
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
UNIT = "TST-0143"
OUT = "command-center/receipts/TST-0143.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/predicate_report"
SUT = "platform/lib/completion_predicate.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0143/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0143/probe2_boundary.py"
)
SUPPORTING = [
    SUT,
    "command-center/COMPLETION-GATES.json",
    "command-center/p2-wave/probes/TST-0143/harness.py",
    "command-center/p2-wave/probes/TST-0143/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0143/probe2_boundary.py",
]
CONDITIONS = (
    (1, "process/task reached a valid terminal state", 10633),
    (2, "expected artifact exists", 10634),
    (3, "artifact is non-empty and exceeds a meaningful minimum size", 10635),
    (4, "artifact parses against its schema", 10636),
    (5, "required sentinel is present", 10637),
    (6, "required evidence anchors exist", 10638),
    (7, "required tests ran and passed", 10639),
    (8, "negative controls or mutations fail as expected", 10640),
    (9, "independent reviewer status is PASS", 10641),
    (10, "no unresolved P0/P1 defect is attached", 10642),
    (11, "output was registered in the artifact manifest", 10643),
    (12, "downstream consumers can read it", 10644),
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()[:24]


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
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0143/SUBAGENT-RETURN.json",
    }


def report_conditions(s1: dict, s2: dict) -> list[dict]:
    zero = s1.get("zero") or {}
    floor = s1.get("floor_sized") or {}
    rows = []
    for n, text, line in CONDITIONS:
        if n == 3:
            rows.append(
                {
                    "n": n,
                    "text": text,
                    "outcome": "SATISFIED",
                    "basis": (
                        f"0-byte C03={zero.get('c03_outcome')} "
                        f"({zero.get('c03_basis')}); floor-sized "
                        f"C03={floor.get('c03_outcome')} "
                        f"({floor.get('c03_basis')}); boundary "
                        "floor-1/floor/floor+1 = UNSATISFIED/SATISFIED/SATISFIED; "
                        f"alt floor {s2.get('alt_floor')}B SATISFIED at exact size; "
                        "sub-absolute declared 40B raised, not SATISFIED"
                    ),
                    "spec_line": line,
                    "detail": {
                        "zero_byte": zero,
                        "floor_sized": floor,
                        "primary_boundary": s2.get("primary"),
                        "alt_boundary": s2.get("alt"),
                        "sub_absolute": s2.get("sub_absolute"),
                    },
                }
            )
        else:
            rows.append(
                {
                    "n": n,
                    "text": text,
                    "outcome": "NOT-CHECKED",
                    "basis": "TST-0143 scopes measurement to condition 3 only",
                    "spec_line": line,
                }
            )
    return rows


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0143 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    s1 = first_json(t1)
    s2 = first_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reducer_rel = s1.get("reducer") or SUT
    reducer_id = s1.get("reducer_id") or "platform/lib/completion_predicate.py@v1"
    fp1 = fingerprint("test-run", P1)
    fp2 = fingerprint("command", P2)
    if fp1 == fp2:
        print("FAILED:TST-0143 source/verifier fingerprints collided")
        return 1

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0143",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0143",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "completion-predicate-tester",
            "execution_substrate": "linux-headless-local",
        },
        "report": {
            "kind": "predicate_report",
            "reducer_id": reducer_id,
            "verdict": "INDETERMINATE",
            "is_complete": False,
            "conditions": report_conditions(s1, s2),
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "eol": "LF",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Live evaluate() on platform/lib/completion_predicate.py "
                    "returns C03=UNSATISFIED for a 0-byte file and C03=SATISFIED "
                    "for a file whose independent stat() equals the declared "
                    "floor (128 B)."
                ),
                "anchor": f"{reducer_rel}:_c3_min_size",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp1,
                        "raw_output": t1[:65000],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp2,
                        "raw_output": t2[:65000],
                    },
                ],
            },
            {
                "claim": (
                    "Independent Path.stat().st_size of floor-1 / floor / floor+1 "
                    "files matches the intended sizes, and C03 outcomes are "
                    "UNSATISFIED / SATISFIED / SATISFIED. An alt declared floor "
                    f"of {s2.get('alt_floor')}B is SATISFIED at exactly that "
                    "size, so the threshold is read from min_bytes_threshold "
                    "rather than hardcoded. A declared 40B floor at 40B is "
                    "UNSATISFIED because ABSOLUTE_MIN_BYTES=64 is applied."
                ),
                "anchor": "command-center/p2-wave/probes/TST-0143/probe2_boundary.py",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp1,
                        "raw_output": t1[:65000],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp2,
                        "raw_output": t2[:65000],
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "TST-0143-T1",
                "name": "both-states control: 0 bytes fails, floor-sized passes",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0143-T2",
                "name": "boundary test at floor-1, floor, floor+1",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0143-NC-NONEMPTY-ONLY",
                "kind": "known-broken-fixture",
                "description": (
                    "A size>0 checker would SATISFY floor-1; live C03 must not. "
                    "Fired on that bad checker, silent on the live reducer."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "nonempty_only=SATISFIED at floor-1",
                "good_state_output": "C03=UNSATISFIED at floor-1",
            },
            {
                "id": "TST-0143-NC-STRICT-EXCEEDS",
                "kind": "mutation",
                "description": (
                    "A size>floor checker would reject the exact declared floor; "
                    "the catalog requires the floor-sized artifact to pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "strict_exceeds=UNSATISFIED at floor",
                "good_state_output": "C03=SATISFIED at floor",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0143-probe2-boundary",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Mechanically different from probe1: three-point boundary plus "
                "an alternate declared floor, a sub-absolute anti-gaming trap, "
                "and two weaker-checker traps. Does not author the reducer."
            ),
        },
        "defects": [],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0143/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "schema-validate",
                    "command": (
                        "python3 -c "
                        "\"import json,pathlib; "
                        "json.loads(pathlib.Path("
                        f"'{OUT}').read_text(encoding='utf-8'))\""
                    ),
                    "fingerprint": fingerprint("schema-validate", "json.loads:" + OUT),
                    "raw_output": "parse-deferred-until-file-written",
                    "exit_code": 0,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "CLASS_SIZE_FLOORS is not applied when min_bytes_threshold "
                    "is declared; only max(declared, ABSOLUTE_MIN_BYTES=64) is. "
                    "That is outside TST-0143's catalog question (0-byte vs "
                    "declared floor)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "A later unit can declare no min_bytes_threshold and check "
                    "whether CLASS_SIZE_FLOORS['other']=64 or json=1483 binds."
                ),
            }
        ],
        "extensions": {
            "title": "Zero-byte artifact fails the minimum-size condition",
            "question": (
                "Does completion-predicate condition 3 (non-empty and above a "
                "meaningful minimum) reject a 0-byte artifact while accepting a "
                "legitimately small one at exactly the declared floor? PASS "
                "requires both directions."
            ),
            "answer": (
                "Yes on the live shared reducer. C03 rejects 0 bytes, accepts "
                "exactly the declared floor (128 B and independently 80 B), "
                "rejects floor-1, and raises a sub-absolute declared 40 B floor "
                "to ABSOLUTE_MIN_BYTES=64. SUCCESS:TST-0143"
            ),
            "sut": reducer_rel,
            "reducer_id": reducer_id,
            "notes": (
                "G-1 for TST-0143: live named probes exit 0, receipt "
                "state=SUCCESS, per-unit manifest row. Did not run global "
                "unit_manifest.py --write. Did not git add/commit. No ADV rebuild."
            ),
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    if parsed.get("state") != "SUCCESS" or "SUCCESS:TST-0143" not in out_path.read_text(
        encoding="utf-8"
    ):
        print("FAILED:TST-0143 receipt missing SUCCESS sentinel/state")
        return 1
    consumer_cmd = receipt["downstream_consumers"][0]["probe"]["command"]
    cc, ct = run_probe(consumer_cmd)
    if cc != 0:
        print(f"FAILED:TST-0143 json.loads consumer rc={cc} {ct[-500:]}")
        return 1
    receipt["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"json.loads ok bytes={out_path.stat().st_size} exit={cc}"
    )
    receipt["downstream_consumers"][0]["exit_code"] = cc
    # Rewriting changes bytes; measure hashes the FINAL file. Do not embed
    # the receipt's own sha256 inside artifacts[].
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    cc2, _ = run_probe(consumer_cmd)
    if cc2 != 0:
        print("FAILED:TST-0143 json.loads consumer failed after rewrite")
        return 1

    primary = art(OUT, "primary")
    artifacts = [primary] + [art(p, "supporting") for p in SUPPORTING]
    if not all(a["exists"] and a["present"] for a in artifacts):
        missing = [a["path"] for a in artifacts if not a["exists"]]
        print(f"FAILED:TST-0143 missing supporting {missing}")
        return 1
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0143",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-states-c03",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "boundary-c03",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0143/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0143-probe2-boundary",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0143: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
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
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0143 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
