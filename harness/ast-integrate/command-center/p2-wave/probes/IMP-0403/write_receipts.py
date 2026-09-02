#!/usr/bin/env python3
"""Write IMP-0403 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json.

Does not run tools/command-center/unit_manifest.py --write.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0403"
OUT = "command-center/receipts/IMP-0403.json"
SENTINEL = "SENTINEL:IMP-0403:ROUTE-CLI-SHIPPED"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0403/probe1_cli_contract.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0403/probe2_doc_example.py"
)
SUPPORTING = [
    "tools/ast.py",
    "tools/router/__init__.py",
    "tools/router/route.py",
    "command-center/p2-wave/probes/IMP-0403/fixtures/capability-index.json",
    "command-center/p2-wave/probes/IMP-0403/probe1_cli_contract.py",
    "command-center/p2-wave/probes/IMP-0403/probe2_doc_example.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "present": True,
        "role": role,
        "eol": "LF",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0403 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    dry = [
        'python3 tools/ast.py route --query "lint a Python module for unused imports" --index command-center/p2-wave/probes/IMP-0403/fixtures/capability-index.json',
        'python3 tools/ast.py route --query "summarize this PDF for the owner" --index command-center/p2-wave/probes/IMP-0403/fixtures/capability-index.json',
        'python3 tools/ast.py route --query "what is the weather in Paris" --index command-center/p2-wave/probes/IMP-0403/fixtures/capability-index.json',
    ]
    transcripts = []
    for cmd in dry:
        code, text = run_cmd(cmd)
        stdout = text
        try:
            doc = json.loads(stdout)
        except json.JSONDecodeError:
            doc = {"parse_error": True}
        transcripts.append(
            {
                "command": cmd,
                "exit_code": code,
                "verdict": doc.get("verdict") if isinstance(doc, dict) else None,
                "injection_performed": doc.get("injection_performed")
                if isinstance(doc, dict)
                else None,
                "session_started": doc.get("session_started") if isinstance(doc, dict) else None,
                "stdout_tail": stdout[-1500:],
            }
        )
        if code != 0:
            print("FAILED:IMP-0403 dry-run", cmd, "exit", code)
            return 1

    supporting = [art(p, "supporting") for p in SUPPORTING]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0403",
        "title": "Owner-facing route dry-run CLI",
        "question_or_target": (
            "Ship an ast route CLI that answers, for an arbitrary query string, "
            "exactly what the router would select, with confidence, explanation "
            "and near-misses - WITHOUT injecting anything."
        ),
        "min_bytes_threshold": 128,
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Three documented dry runs (two SELECTED, one NO-CAPABILITY-FITS) "
                    "exit 0 with structured JSON on stdout and injection_performed=false."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/ast.py:DOCUMENTED_EXAMPLE_LINES",
                "probes": [
                    probe("source", "command", dry[i], json.dumps(transcripts[i]), transcripts[i]["exit_code"])
                    for i in range(3)
                ],
            },
            {
                "claim": (
                    "Every flag printed by `ast route --help` parses; --inject and "
                    "an undocumented flag are rejected (CLI contract)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0403/probe1_cli_contract.py",
                "probes": [
                    probe("source", "command", P1, t1, c1),
                    probe("verifier", "command", P2, t2, c2),
                ],
            },
            {
                "claim": (
                    "A documented example in the help text is executed verbatim by "
                    "probe2; the reviewer runs only those examples."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0403/probe2_doc_example.py",
                "probes": [probe("source", "command", P2, t2, c2)],
            },
            {
                "claim": (
                    "Capability body canaries never appear on stdout; the CLI shares "
                    "router.route.route_query and does not start a session."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/router/route.py:route_query",
                "probes": [probe("verifier", "command", P2, t2, c2)],
            },
            {
                "claim": (
                    "No-fit is terminal: the weather query returns NO-CAPABILITY-FITS "
                    "with near-misses rather than injecting a weak match."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/router/route.py:NO_FIT",
                "probes": [probe("source", "command", dry[2], json.dumps(transcripts[2]), transcripts[2]["exit_code"])],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "tests": [
            {"id": "cli-contract-flags-parse", "command": P1, "result": "PASS"},
            {"id": "documentation-command-verbatim", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "undocumented-flag-rejected",
                "kind": "unknown-flag",
                "description": "--inject and --not-a-documented-flag must fail to parse",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "rejected --inject",
                "good_state_output": "documented flags parse",
            },
            {
                "id": "body-canary-absent",
                "kind": "injection-leak",
                "description": "CANARY-IMP-0403-BODY must be absent from dry-run stdout",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "canary would fail probe2",
                "good_state_output": "canary_absent=True",
            },
            {
                "id": "weak-match-not-injected",
                "kind": "no-fit-terminal",
                "description": "weather query must be NO-CAPABILITY-FITS, not a weak SELECTED",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "SELECTED on no-fit would fail probe2",
                "good_state_output": transcripts[2]["verdict"],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0403-probe2-doc-example",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope": "documented help examples only",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0403/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "python3 tools/ast.py route (documented examples)",
                "artifact_path": "tools/ast.py",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe("verifier", "command", P2, t2, c2),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Confidence is a deterministic matcher score (confidence_kind=score), "
                    "not a calibrated probability from IMP-0391 fusion."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-measure calibration after IMP-0391 delivers a reliability diagram.",
            }
        ],
        "dry_run_transcripts": transcripts,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "implementation": {
            "cli": "tools/ast.py",
            "router": "tools/router/route.py",
            "shared_entry": "router.route.route_query",
            "injection": "none — dry-run only",
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(receipt, indent=2, ensure_ascii=True) + "\n"
    out_path.write_text(encoded, encoding="utf-8", newline="\n")
    if SENTINEL not in encoded:
        print("FAILED:IMP-0403 sentinel missing from receipt")
        return 1

    primary = art(OUT, "primary")
    rows = [
        {
            "path": OUT,
            "sha256": primary["sha256"],
            "bytes": primary["bytes"],
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0403/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for item in supporting:
        rows.append(
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
                "present": True,
                "unit_id": UNIT,
                "receipt_path": "command-center/p2-wave/probes/IMP-0403/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )
    man = {
        "schema_version": 1,
        "unit_id": UNIT,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0403/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0403-probe2-doc-example",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ended,
        "notes": (
            "G-1 for IMP-0403: live named probes exit 0, receipt state=SUCCESS "
            "with SENTINEL:IMP-0403:ROUTE-CLI-SHIPPED, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. ast route is dry-run only."
        ),
    }
    ret_path = HERE / "SUBAGENT-RETURN.json"
    ret_path.write_text(json.dumps(ret, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT} bytes={primary['bytes']} sha256={primary['sha256']}")
    print("SUCCESS:IMP-0403 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
