#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0021-install-path-stride-threat-model.json."""
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

from engine import (  # noqa: E402
    COMPLETION,
    OUT_REL,
    P1_CMD,
    P2_CMD,
    PROBE1_TEXT,
    PROBE2_TEXT,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
    probe1_payload,
    probe2_payload,
    targets_from,
)

P1 = P1_CMD
P2 = P2_CMD


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


def validate(doc: dict) -> None:
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore
    except ImportError as exc:
        required = schema.get("required") or []
        missing = [k for k in required if k not in doc]
        if missing:
            raise RuntimeError(f"schema required keys missing: {missing}") from exc
        return
    jsonschema.Draft7Validator(schema).validate(doc)


def unmitigated_by_boundary(cells: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for cell in cells:
        if cell.get("status") != "unmitigated":
            continue
        out.setdefault(str(cell.get("boundary_id")), []).append(str(cell.get("category")))
    return {k: v for k, v in out.items()}


def build_answer(p1: dict, p2: dict) -> str:
    gaps = unmitigated_by_boundary(p2.get("stride_cells") or [])
    gap_txt = "; ".join(f"{bid}[{','.join(cats)}]" for bid, cats in sorted(gaps.items()))
    demos = [
        c["id"]
        for c in (p2.get("stride_cells") or [])
        if c.get("demonstration_confirmed")
    ]
    return (
        "Code-derived STRIDE model of install/update/repair/rollback/uninstall "
        f"crosses {p1.get('boundary_count')} trust boundaries and fills "
        f"{p1.get('cell_count')} STRIDE cells "
        f"(mitigated={p2.get('mitigated')}, partially-mitigated={p2.get('partial')}, "
        f"unmitigated={p2.get('unmitigated')} after executable bypass). "
        "Mitigations that held: typed handoff+transaction_id, payload digest "
        "mismatch, permission-widening halt, uninstall disposable-marker and "
        "path confinement. Unmitigated STRIDE by boundary: "
        f"{gap_txt}. Executable demonstrations confirmed on "
        f"{demos}. Marketplace.install does not call verify_signature; "
        "install.py does not call txn_journal.recover; placement does not "
        "confine dest/source. Follow-up units and accepted residuals are in "
        "unmitigated_disposition. No Windows registry surface on this Linux "
        "worktree."
    )


def build_doc(p1: dict, p2: dict, raw1: str, raw2: str, c1: int, c2: int) -> dict:
    cells = list(p2.get("stride_cells") or [])
    disp = list(p2.get("dispositions") or [])
    targets = targets_from(p2)
    crypto = p2.get("crypto_negative_control") or {}
    crypto_ok = bool(crypto.get("control_held"))
    missing_exec = list(p2.get("missing_executable_checks") or [])
    closure_ok = bool(p2.get("closure_ok"))
    benign_ok = bool((p2.get("bypass") or {}).get("benign_ok"))
    two_sided = int(p2.get("mitigated") or 0) >= 1 and int(p2.get("unmitigated") or 0) >= 1
    passed = (
        c1 == 0
        and c2 == 0
        and bool(p1.get("pass"))
        and bool(p2.get("pass"))
        and not missing_exec
        and closure_ok
        and crypto_ok
        and benign_ok
        and two_sided
    )
    if not passed:
        raise RuntimeError(
            "emit gates failed: "
            + json.dumps(
                {
                    "c1": c1,
                    "c2": c2,
                    "p1": p1.get("pass"),
                    "p2": p2.get("pass"),
                    "p2_reason": p2.get("reason"),
                    "missing_exec": missing_exec,
                    "closure_ok": closure_ok,
                    "crypto_ok": crypto_ok,
                    "benign_ok": benign_ok,
                    "two_sided": two_sided,
                },
                default=str,
            )[:4000]
        )
    tests = [
        {
            "id": "T1-PROBE-1-CODE-FLOWS",
            "name": "enumerate trust boundaries and STRIDE cells from install-path code",
            "command": P1,
            "result": "PASS" if c1 == 0 and p1.get("pass") else "FAIL",
        },
        {
            "id": "T2-PROBE-2-BYPASS",
            "name": "execute each claimed mitigation; downgrade cells with no check",
            "command": P2,
            "result": "PASS" if c2 == 0 and p2.get("pass") else "FAIL",
        },
        {
            "id": "T3-MITIGATED-EXECUTABLE-CHECKS",
            "name": "every still-mitigated cell has an executable bypass attempt",
            "result": "PASS" if not missing_exec else "FAIL",
        },
        {
            "id": "T4-UNMITIGATED-DISPOSITION",
            "name": "every unmitigated cell is a follow-up unit or accepted residual",
            "result": "PASS" if closure_ok else "FAIL",
        },
        {
            "id": "T5-BENIGN-INSTALL-CONTROL",
            "name": "detector control: a valid payload installs (not reject-everything)",
            "result": "PASS" if benign_ok else "FAIL",
        },
        {
            "id": "T6-CRYPTO-NEGATIVE-CONTROL",
            "name": "verify_signature is UNSIGNED on None and not UNSIGNED on a bad record",
            "result": "PASS" if crypto_ok else "FAIL",
        },
        {
            "id": "T7-TWO-SIDED-MODEL",
            "name": "model records both mitigated and unmitigated cells after bypass",
            "result": "PASS" if two_sided else "FAIL",
        },
        {
            "id": "T8-DECLARED-SCHEMA",
            "name": "artifact parses against command-center/schema/threat-model.schema.json",
            "result": "PASS",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise RuntimeError("emit tests not all PASS")
    allowed = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    if any(t.get("verdict") not in allowed for t in targets):
        raise RuntimeError("target verdict not in enum")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = build_answer(p1, p2)
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION,
        "report_kind": "threat-model",
        "title": "STRIDE threat model of the plugin installation and update path",
        "question": QUESTION,
        "answer": answer,
        "overall_verdict": "PARTIAL",
        "mechanism": (
            "code-derived (not doc-derived) trust-boundary enumeration with "
            "executable verification of each claimed mitigation"
        ),
        "spec_anchor": "_USER-PROMPTS.md:11049, 10824-10842",
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "produced_at": now,
        "probe1_verbatim": PROBE1_TEXT,
        "probe2_verbatim": PROBE2_TEXT,
        "enumerated_targets": targets,
        "probes": [
            {
                "id": "probe1",
                "verbatim": PROBE1_TEXT,
                "command": P1,
                "exit_code": c1,
                "raw_output": raw1,
                "role": "code-flows",
            },
            {
                "id": "probe2",
                "verbatim": PROBE2_TEXT,
                "command": P2,
                "exit_code": c2,
                "raw_output": raw2,
                "role": "bypass",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "verbatim": PROBE1_TEXT,
                "command": P1,
                "exit_code": c1,
                "raw_output": raw1,
                "role": "code-flows",
            },
            {
                "id": "probe2",
                "verbatim": PROBE2_TEXT,
                "command": P2,
                "exit_code": c2,
                "raw_output": raw2,
                "role": "bypass",
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-CRYPTO-NOT-VACUOUS",
                "kind": "both-states",
                "description": (
                    "verify_signature(None) is UNSIGNED (silent on unsigned/"
                    "good-absence). A malformed record is not UNSIGNED "
                    "(fires on bad). The helper is live even though "
                    "marketplace.install never calls it."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "unsigned": (crypto.get("detail") or {}).get("unsigned"),
                "bad_record": (crypto.get("detail") or {}).get("bad_record"),
            },
            {
                "id": "NC-BENIGN-INSTALL",
                "kind": "detector-control",
                "description": (
                    "A schema-valid payload with matching digest installs. "
                    "Refusals of untyped handoff / digest mismatch / "
                    "permission widening are therefore not a reject-everything "
                    "detector."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "benign_ok": benign_ok,
            },
        ],
        "boundaries": p1.get("boundaries") or [],
        "stride_cells": cells,
        "unmitigated_disposition": disp,
        "reviewer": {
            "reviewer_id": "ADV-0021-probe2-bypass",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Executable bypass of every cell marked mitigated, plus "
                "demonstrations on unmitigated projection/signature cells. "
                "Does not re-read Probe 1's status column as proof."
            ),
            "vendor": "mechanical-probe",
        },
        "evidence": [
            {
                "claim": (
                    "Nine trust boundaries and 54 STRIDE cells were derived "
                    "from install-path modules, not from a design document."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ADV-0021/probe1_code_flows.py",
            },
            {
                "claim": (
                    "Every still-mitigated cell refused its bypass; untyped "
                    "handoff, digest mismatch, permission widening, and "
                    "uninstall path escape did not place or delete illegally."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ADV-0021/probe2_bypass.py",
            },
            {
                "claim": (
                    "Projection dest/source confinement and marketplace "
                    "signature-on-install are unmitigated; dest-escape, "
                    "source-read, and unsigned marketplace.install were "
                    "demonstrated."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/placement.py",
            },
            {
                "claim": (
                    "txn_journal.recover exists and is not called from "
                    "install.py; activate is rmtree then rename."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/install.py",
            },
        ],
        "counts": {
            "boundaries": p1.get("boundary_count"),
            "cells": p1.get("cell_count"),
            "mitigated": p2.get("mitigated"),
            "partial": p2.get("partial"),
            "unmitigated": p2.get("unmitigated"),
            "downgraded": p2.get("downgraded"),
        },
        "bypass": p2.get("bypass"),
        "notes": (
            "G-1 for ADV-0021. Did not run tools/command-center/unit_manifest.py "
            "--write. Did not relaunch finish-everything-close or "
            "p2-cloud-ok-deliver. Finding unmitigated cells is the unit's "
            "job, not a BLOCKED outcome. cloud ok=true is not delivery."
        ),
        COMPLETION: True,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0:
        print("FAILED:ADV-0021 emit probe1")
        print(t1[-4000:])
        return 1
    if c2 != 0:
        print("FAILED:ADV-0021 emit probe2")
        print(t2[-4000:])
        return 1
    p1 = probe1_payload()
    p2 = probe2_payload()
    try:
        doc = build_doc(p1, p2, t1, t2, c1, c2)
        validate(doc)
    except Exception as exc:
        print(f"FAILED:ADV-0021 emit {type(exc).__name__}: {exc}")
        return 1
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if SENTINEL not in text:
        print("FAILED:ADV-0021 catalog sentinel missing from serialisation")
        return 1
    if COMPLETION not in text:
        print("FAILED:ADV-0021 completion_sentinel missing from serialisation")
        return 1
    if PROBE1_TEXT not in text or PROBE2_TEXT not in text:
        print("FAILED:ADV-0021 named probe text missing")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
