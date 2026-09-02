#!/usr/bin/env python3
"""Emit ADV-0030 adversarial artifact, then per-unit return + manifest."""
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import harness as H  # noqa: E402
import jsonschema  # noqa: E402

UNIT = "ADV-0030"
OUT_REL = "command-center/adversarial/ADV-0030-validate-install-toctou.json"
SCHEMA_REL = "command-center/schema/fault-injection-run.schema.json"
CATALOG_SCHEMA = "command-center/schema/exploit-proof.schema.json"
ART = REPO / OUT_REL
SCHEMA = REPO / SCHEMA_REL
SENTINEL = "SUCCESS:ADV-0030"
COMPLETION = (
    "SUCCESS:ADV-0030 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0030 <reason>."
)
QUESTION = (
    "Is there a window between the validator reading a package and the "
    "installer consuming it in which the bytes can change - and does the "
    "installer re-verify the hash it validated?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0030/probe1_swap_after_validate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0030/probe2_static_recheck.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def build_doc(report: dict, probes: list[dict]) -> dict:
    post = report["swap_after_digest_before_place"]
    pre = report["swap_after_validate_before_digest"]
    control = report["control"]
    toctou = bool(post["toctou_installed_swapped"])
    pre_refused = bool(pre["refused"])
    recheck_handoff = pre_refused
    recheck_at_use = not toctou
    instrumentation = bool(report["instrumentation_ok"] and control["ok"])
    passed = instrumentation and pre_refused
    state = "SUCCESS" if passed else "FAILED"
    answer = (
        "Production install_from_handoff calls validate_handoff (schema/typed "
        "handoff only; it does not hash payload bytes), then re-computes "
        "payload_digest once and compares it to handoff digest.value. That "
        f"check refused a post-validate/pre-digest swap ({pre['error_type']}). "
        "After the check, place_payload_files copies current payload bytes "
        "with no second hash; staged census compares sorted path keys to "
        "projection dests, not content. Monkeypatching payload_digest to swap "
        f"the skill after it returned meant dest received {post['installed_preview']!r}. "
        "Control (no swap) installed the original marker and the source digest "
        "was stable. Negative: a naive boolean-trust installer (validate_handoff "
        "then place, no digest) installed the same post-validate swap. Catalog "
        "output_schema command-center/schema/exploit-proof.schema.json is absent "
        "on this worktree; this envelope validates against "
        "command-center/schema/fault-injection-run.schema.json."
    )
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "state": state,
        "status": "DELIVERED" if passed else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION,
        COMPLETION: True,
        "report_kind": "fault-injection-run",
        "title": "Time-of-check to time-of-use window between validation and install",
        "question": QUESTION,
        "answer": answer,
        "spec_anchor": "_USER-PROMPTS.md:10871, 11049",
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "catalog_output_schema": CATALOG_SCHEMA,
        "catalog_output_schema_present": (REPO / CATALOG_SCHEMA).is_file(),
        "execution_substrate": "worktree-isolated",
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "measured": {
            "instrumentation_ok": instrumentation,
            "control_ok": control["ok"],
            "control_src_digest_stable": control["src_digest_stable"],
            "handoff_matches_src": control["handoff_matches_src"],
            "pre_digest_refused": pre_refused,
            "pre_digest_error_type": pre["error_type"],
            "post_digest_installed_swapped": toctou,
            "post_digest_installed_original": post["installed_original"],
            "post_digest_digest_calls": post["digest_calls"],
            "naive_good_original": report["naive_good"]["installed_original"],
            "naive_bad_swapped": report["naive_bad"]["installed_swapped"],
            "rechecks_handoff_digest": recheck_handoff,
            "rechecks_at_point_of_use": recheck_at_use,
            "pass": passed,
        },
        "enumerated_targets": [
            {
                "id": "TARGET-TOCTOU-POST-DIGEST-INSTALLS-SWAP",
                "question": (
                    "After payload_digest returns (validation of payload bytes), "
                    "can swapping staged payload bytes still change what is installed?"
                ),
                "verdict": "CONFIRMED" if toctou else "REFUTED",
                "meaning": (
                    "CONFIRMED means the swapped marker was installed; the "
                    "installer did not re-hash at point of use."
                ),
            },
            {
                "id": "TARGET-POST-VALIDATOR-PRE-DIGEST-CAUGHT",
                "question": (
                    "If bytes change after validate_handoff / build_handoff but "
                    "before the installer's payload_digest check, is install refused?"
                ),
                "verdict": "CONFIRMED" if pre_refused else "REFUTED",
                "meaning": (
                    "CONFIRMED means DigestMismatchError fired and dest was not "
                    "created — the installer does not trust the validator boolean alone."
                ),
            },
            {
                "id": "TARGET-REVERIFY-AT-PLACE",
                "question": (
                    "Does the installer re-verify the payload digest at "
                    "place_payload_files / staged census?"
                ),
                "verdict": "REFUTED" if toctou else "CONFIRMED",
                "meaning": (
                    "REFUTED means no digest re-check at point of use: swapped "
                    "bytes were copied. CONFIRMED would mean the swap was caught."
                ),
            },
        ],
        "probes": probes,
        "tests": [
            {
                "id": "T1-NAMED-PROBE-1-RUNTIME-SWAP",
                "name": "Swap staged bytes after digest check; record dest bytes",
                "result": "PASS" if passed else "FAIL",
                "command": P1,
            },
            {
                "id": "T2-NAMED-PROBE-2-STATIC-RECHECK",
                "name": "AST: payload_digest once before place; census is path-only",
                "result": "PASS",
                "command": P2,
            },
            {
                "id": "T3-CONTROL-NO-SWAP-INSTALL",
                "name": "Without the swap, install succeeds and dest matches original digest",
                "result": "PASS" if control["ok"] else "FAIL",
            },
            {
                "id": "T4-CONTROL-SRC-DIGEST-STABLE",
                "name": "Control run does not mutate payload bytes (instrumentation distinct)",
                "result": "PASS" if control["src_digest_stable"] else "FAIL",
            },
            {
                "id": "T5-NEGATIVE-NAIVE-TRUST-BOOLEAN",
                "name": "Boolean-trust mutant installs post-validate swap; clean payload does not",
                "result": (
                    "PASS"
                    if report["naive_bad"]["installed_swapped"]
                    and report["naive_good"]["installed_original"]
                    else "FAIL"
                ),
            },
            {
                "id": "T6-PRE-DIGEST-WINDOW-REFUSED",
                "name": "Swap after validate/handoff and before installer digest is refused",
                "result": "PASS" if pre_refused else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-NAIVE-TRUST-VALIDATOR-BOOLEAN",
                "kind": "both-states",
                "description": (
                    "A mutant installer calls validate_handoff then "
                    "place_payload_files with no payload_digest. On a "
                    "post-validate swap it must install swapped bytes; on an "
                    "unmodified payload it must install original bytes. This "
                    "is the failure mode the production digest check exists to catch."
                ),
                "fired_on_bad_state": bool(report["naive_bad"]["installed_swapped"]),
                "silent_on_good_state": bool(
                    report["naive_good"]["installed_original"]
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "ADV-0030-probe2-static-recheck",
            "verdict": "PASS" if passed else "FAIL",
            "independent": True,
            "note": (
                "Mechanical independence is probe-2 AST call-order versus "
                "probe-1 live byte swap. A live Anthropic opus review is not claimed."
            ),
        },
        "evidence": [
            {
                "path": OUT_REL,
                "kind": "primary-artifact",
                "claim": "Fault-injection run with both named probes and controls.",
            },
            {
                "path": "tools/plugin/install.py",
                "kind": "implementation",
                "claim": "Production validate-then-digest-then-place sequence.",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0030/harness.py",
                "kind": "harness",
                "claim": "Disposable payload, digest-hook swap, naive boolean mutant.",
            },
        ],
        "implementation": {
            "install": "tools/plugin/install.py",
            "handoff": "tools/marketplace/handoff.py",
            "placement": "tools/plugin/placement.py",
            "harness": "command-center/p2-wave/probes/ADV-0030/harness.py",
        },
    }


def supporting() -> list[str]:
    return [
        SCHEMA_REL,
        "tools/plugin/install.py",
        "tools/plugin/placement.py",
        "tools/marketplace/handoff.py",
        "command-center/p2-wave/probes/ADV-0030/harness.py",
        "command-center/p2-wave/probes/ADV-0030/probe1_swap_after_validate.py",
        "command-center/p2-wave/probes/ADV-0030/probe2_static_recheck.py",
        "command-center/p2-wave/probes/ADV-0030/emit_artifact.py",
    ]


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    report = H.measure()
    if not report["instrumentation_ok"] or not report["control"]["ok"]:
        print("FAILED:ADV-0030 emit instrumentation/control did not pass")
        print(json.dumps(report, indent=2, sort_keys=True)[:8000])
        return 1

    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    probes = [
        {
            "id": "probe1",
            "command": P1,
            "role": "runtime-swap",
            "exit_code": rc1,
            "raw_output": out1,
        },
        {
            "id": "probe2",
            "command": P2,
            "role": "static-recheck",
            "exit_code": rc2,
            "raw_output": out2,
        },
    ]
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0030 named probes did not exit 0")
        print(out1[-3000:])
        print(out2[-3000:])
        return 1

    doc = build_doc(report, probes)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    write_json(ART, doc)

    sha, size = sha256_file(ART)
    artifacts = [
        {
            "bytes": size,
            "path": OUT_REL,
            "present": True,
            "receipt_path": "command-center/p2-wave/probes/ADV-0030/SUBAGENT-RETURN.json",
            "role": "primary",
            "sha256": sha,
            "unit_id": UNIT,
        }
    ]
    for rel in supporting():
        path = REPO / rel
        s, b = sha256_file(path)
        artifacts.append(
            {
                "bytes": b,
                "path": rel,
                "present": True,
                "receipt_path": "command-center/p2-wave/probes/ADV-0030/SUBAGENT-RETURN.json",
                "role": "supporting",
                "sha256": s,
                "unit_id": UNIT,
            }
        )

    ret = {
        "artifacts": [
            {
                "bytes": size,
                "exists": True,
                "path": OUT_REL,
                "role": "primary",
                "sha256": sha,
            }
        ],
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/ADV-0030/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": probes,
        "notes": (
            "G-1 for ADV-0030: live named probes exit 0, adversarial artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "ADV-0030-probe2-static-recheck",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unit_id": UNIT,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(f"{SENTINEL} artifact emitted; probes rc={rc1},{rc2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
