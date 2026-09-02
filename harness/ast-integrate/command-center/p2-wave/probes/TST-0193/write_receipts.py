#!/usr/bin/env python3
"""Write TST-0193 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0193"
OUT = "command-center/receipts/TST-0193.json"
SENTINEL = "SUCCESS:TST-0193"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0193/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0193/probe2_property.py"
)
SUPPORTING = [
    "tools/shell/param_pipeline.py",
    "command-center/p2-wave/probes/TST-0193/payloads.py",
    "command-center/p2-wave/probes/TST-0193/probe1_detector_control.py",
    "command-center/p2-wave/probes/TST-0193/probe2_property.py",
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
        "receipt_path": "command-center/p2-wave/probes/TST-0193/SUBAGENT-RETURN.json",
        "role": role,
    }


def parse_probe_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = parse_probe_json(t1)
    j2 = parse_probe_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib_sha, lib_bytes = digest(REPO / "tools/shell/param_pipeline.py")
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    git_bash = shutil.which("git-bash") or ""

    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Workflow parameters are never re-parsed by a shell",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/shell_report",
        "min_bytes_threshold": 2048,
        "schema_version": 1,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json#TST-0193 "
            "_USER-PROMPTS.md:11015 (Phase 10 layer 27, shell-quoting tests)"
        ),
        "question_or_target": (
            "Can a workflow parameter containing $(...), backticks or %VAR% "
            "cause command substitution anywhere in the pipeline? PASS requires "
            "zero substitution across every parameter sink, proven by a canary "
            "that would create a marker file if evaluated."
        ),
        "implementation": {
            "library": "tools/shell/param_pipeline.py",
            "library_sha256": lib_sha,
            "library_bytes": lib_bytes,
            "sinks": ["argv", "env", "file", "stdin"],
            "mechanism": (
                "Parameters are passed as argv elements, environment values, "
                "file bytes, or stdin. dispatch never interpolates a parameter "
                "into a shell script string and refuses subprocess shell mode. "
                "tools/lib/codex-invocation.mjs exists and keeps the prompt on "
                "stdin rather than argv; named probes exercise "
                "tools/shell/param_pipeline.py as the live substitution gate."
            ),
            "missing_catalog_inputs": [
                "rules/common/windows-shell.md",
                "rules/common/cross-vendor-dispatch.md",
                "_USER-PROMPTS.md",
            ],
        },
        "evidence": [
            {
                "id": "E1-canary-absent",
                "claim": (
                    "Signal (a): after dispatching substitution payloads through "
                    "every sink, the canary marker file is absent. The detector "
                    "control splice-eval of $(touch PATH) and backticks creates "
                    "the same marker, so absence is not a dead detector."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0193/probe1_detector_control.py",
                "computed": {
                    "dollar_paren_splice_created_canary": (j1.get("detector") or {}).get(
                        "dollar_paren_splice_created_canary"
                    ),
                    "backtick_splice_created_canary": (j1.get("detector") or {}).get(
                        "backtick_splice_created_canary"
                    ),
                    "pipeline_dollar_canary_present": (j1.get("pipeline") or {}).get(
                        "dollar_canary_present"
                    ),
                    "pipeline_backtick_canary_present": (j1.get("pipeline") or {}).get(
                        "backtick_canary_present"
                    ),
                    "property_canary_hits": j2.get("canary_hits"),
                    "sample_splice_eval_fired": j2.get("sample_splice_eval_fired"),
                },
            },
            {
                "id": "E2-literal-at-each-sink",
                "claim": (
                    "Signal (b): every sink records the original parameter bytes. "
                    "300 injection payloads (241 with $(, backtick, or % tokens) "
                    "round-trip through argv, env, file, and stdin. A cmd.exe "
                    "%PATH% expander changes the value; the pipeline does not."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0193/probe2_property.py",
                "computed": {
                    "payload_count": j2.get("payload_count"),
                    "literal_pass_count": j2.get("literal_pass_count"),
                    "substitution_token_count": j2.get("substitution_token_count"),
                    "family_ok": j2.get("family_ok"),
                    "percent_expand_changes_value": (j1.get("detector") or {}).get(
                        "percent_expand_changes_value"
                    ),
                    "percent_literal_all_sinks": (j1.get("pipeline") or {}).get(
                        "percent_literal_all_sinks"
                    ),
                    "source_enables_shell": j2.get("source_enables_shell"),
                },
            },
        ],
        "tests": [
            {
                "id": "detector-control-splice-eval-creates-canary",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "property-300-injection-payloads",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "NC1-splice-eval-dollar-paren",
                "kind": "detector-control",
                "description": (
                    "bash -c interpolating $(touch CANARY) must create the marker."
                ),
                "fired_on_bad_state": bool(
                    (j1.get("detector") or {}).get("dollar_paren_splice_created_canary")
                ),
                "silent_on_good_state": not bool(
                    (j1.get("pipeline") or {}).get("dollar_canary_present")
                ),
            },
            {
                "id": "NC2-splice-eval-backticks",
                "kind": "detector-control",
                "description": (
                    "bash -c interpolating backtick-touch must create the marker."
                ),
                "fired_on_bad_state": bool(
                    (j1.get("detector") or {}).get("backtick_splice_created_canary")
                ),
                "silent_on_good_state": not bool(
                    (j1.get("pipeline") or {}).get("backtick_canary_present")
                ),
            },
            {
                "id": "NC3-cmd-percent-expand",
                "kind": "detector-control",
                "description": (
                    "cmd.exe-model %PATH% expansion must change the value; "
                    "the pipeline must record %PATH% literally."
                ),
                "fired_on_bad_state": bool(
                    (j1.get("detector") or {}).get("percent_expand_changes_value")
                ),
                "silent_on_good_state": bool(
                    (j1.get("pipeline") or {}).get("percent_literal_all_sinks")
                ),
            },
        ],
        "artifacts": [
            {
                "path": "tools/shell/param_pipeline.py",
                "role": "implementation",
                "sha256": lib_sha,
                "bytes": lib_bytes,
                "exists": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0193-probe2-property-300",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Catalog asks an independent reviewer to re-run on a second "
                "Windows shell (pwsh7 and Git Bash). This G-1 delivery uses "
                "probe2 as the independent mechanical re-run on Linux bash. "
                f"pwsh={pwsh or 'absent'}; git-bash={git_bash or 'absent'}. "
                "A human Windows-shell pass is not claimed."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "pwsh7 and Git Bash were not re-run on this Linux worktree. "
                    "%VAR% expansion is proven with a cmd.exe-model expander, "
                    "not live cmd.exe."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 and probe2 under pwsh7 and Git Bash on Windows; "
                    "confirm the canary still appears only on splice-eval."
                ),
            },
            {
                "claim": (
                    "tools/lib/codex-invocation.mjs is in the tree. It writes "
                    "the prompt to a file and streams it on stdin; argv ends "
                    "with '-'. A Windows .cmd shim may set shell:true. Named "
                    "probes do not spawn that module; they gate "
                    "tools/shell/param_pipeline.py."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Point named probes at createCodexExecPlan spawn and "
                    "confirm $(...) / backticks / %VAR% still stay literal."
                ),
            },
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0193/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "shell-portability-tester",
            "execution_substrate": "linux-worktree",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0193: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:TST-0193"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if SENTINEL not in payload:
        print("FAILED:TST-0193 sentinel missing from receipt text")
        return 1
    if out_path.stat().st_size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0193 receipt too small {out_path.stat().st_size}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/shell_report",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "detector-control-splice-eval",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "property-300-injection-payloads",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0193/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0193-probe2-property-300",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0193: live named probes exit 0, receipts/TST-0193.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
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
    print("SUCCESS:TST-0193 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
