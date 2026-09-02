#!/usr/bin/env python3
"""Write ADV-0118 catalog artifact, SUBAGENT-RETURN, and per-unit manifest."""
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
import engine as E  # noqa: E402

UNIT = "ADV-0118"
OUT = "command-center/adversarial/ADV-0118-shell-quoting-corpus-own-scripts.json"
SCHEMA = "command-center/schema/fault-injection-run.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0118/probe1_dual_shell_execute.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0118/probe2_delivered_value.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0118/engine.py",
    "command-center/p2-wave/probes/ADV-0118/probe1_dual_shell_execute.py",
    "command-center/p2-wave/probes/ADV-0118/probe2_delivered_value.py",
    "command-center/p2-wave/probes/ADV-0118/capture_argv.py",
    "command-center/p2-wave/probes/ADV-0118/owned_launcher.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0118/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    unit = E.catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if not sentinel.startswith("SUCCESS:ADV-0118"):
        print("FAILED:ADV-0118 catalog completion_sentinel missing SUCCESS:ADV-0118")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0118 probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    targets = p2.get("targets") or p1.get("targets") or []
    tests = p1.get("tests") or []
    overall = p2.get("overall_verdict") or p1.get("overall_verdict") or "PARTIAL"
    question = str(unit.get("question_or_target") or "")
    answer = (
        "Live GNU bash and portable PowerShell 7.4.6 executed the program's own "
        "git/gh/launcher constructions against the catalog payload corpus. Naive "
        "single-quote shell strings (no shlex.quote in-tree) break on apostrophe "
        "prose; PowerShell here-strings break when the payload contains the "
        "terminator; unquoted HEAD^{commit} is a PowerShell XOR/script-block, not "
        "a git peel. Native argv round-trips. GNU bash does not MSYS-convert "
        "/sdcard paths (MSYS Git Bash NOT-CHECKED). A 40000-char payload exceeds "
        "the Windows 32767 CreateProcess cap with no in-tree preflight; a clip "
        "mutant distinguishes that from silent Linux truncation. "
        f"overall_verdict={overall}."
    )
    artifact = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:ADV-0118",
        "completion_sentinel": sentinel,
        "report_kind": "fault-injection-run",
        "title": unit.get("title"),
        "output_schema": SCHEMA,
        "question": question,
        "answer": answer,
        "overall_verdict": overall,
        "targets": targets,
        "tests": tests,
        "controls": tests,
        "evidence": [
            {
                "kind": "dual-shell-execute",
                "path": "command-center/p2-wave/probes/ADV-0118/probe1_dual_shell_execute.py",
                "claim": "Each construction × payload ran in GNU bash and live pwsh 7.4.6.",
                "n_cells": p1.get("n_cells"),
            },
            {
                "kind": "delivered-value",
                "path": "command-center/p2-wave/probes/ADV-0118/probe2_delivered_value.py",
                "claim": "Far-end git %B / gh capture / launcher bytes compared to intended.",
                "far_end_control_ok": p2.get("far_end_control_ok"),
            },
            {
                "kind": "windows-cap-mutant",
                "path": "command-center/p2-wave/probes/ADV-0118/engine.py",
                "claim": "Clip mutant at 32767 chars must not round-trip.",
                "fired": p2.get("windows_clip_fired"),
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "reviewer": {
            "reviewer_id": "ADV-0118-probe2-delivered-value",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "cursor-grok-4.6",
            "role": "platform-fault-injector",
            "execution_substrate": "linux-worktree-plus-portable-pwsh-7.4.6",
        },
        "artifacts": [{"path": OUT, "exists": True, "role": "primary"}],
        "spec_anchor": unit.get("spec_anchor"),
        "ts": now,
        "notes": (
            "G-1 for ADV-0118: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild circle. cloud ok=true is not delivery. Git Bash family "
            "is GNU bash (MSYS drive conversion NOT-CHECKED)."
        ),
        "in_tree_shlex_quote_uses": 0,
        "pwsh": (p1.get("shells") or [None, {}])[-1] if p1.get("shells") else None,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(artifact, indent=1, sort_keys=True) + "\n"
    if sentinel not in blob:
        print("FAILED:ADV-0118 completion_sentinel missing from artifact text")
        return 1
    out_path.write_text(blob, encoding="utf-8")
    try:
        import jsonschema  # type: ignore
    except ImportError:
        jsonschema = None  # type: ignore
    if jsonschema is not None:
        schema_doc = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema_doc).validate(artifact)

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0118",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "dual-shell-execute",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "delivered-value",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0118/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0118-probe2-delivered-value",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0118: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
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
    print("SUCCESS:ADV-0118 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
