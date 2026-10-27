#!/usr/bin/env python3
"""INDEPENDENT REVIEWER, wave-4 shard-20 (TST-0223..TST-0256, 12 units).

Reviewer-authored verification -- deliberately NOT the builder's audit script.
Per unit, independently re-derives every non-probe contract dimension from the
live tree, using its own code paths:

  A. catalog entry present; artifact (catalog output_path) exists, non-empty,
     parses as JSON, state not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT,
     completion sentinel present in the artifact text.
  B. probes/<id>/SUBAGENT-RETURN.json exists, parses, status not self-blocked.
  C. probes/<id>/UNIT-ARTIFACT-MANIFEST.json carries a row with unit_id == id,
     path == output_path (slash-normalised), present is True, and sha256 EQUAL
     to a sha256 THIS SCRIPT recomputes from the live bytes (CRLF->LF normalised)
     right now -- plus a declared bytes field consistent with the live size.
  D. receipt validates against the catalog output_schema fragment (layer 1),
     via the platform gate's own validator (jsonschema Draft2020-12).
  E. full 12-condition completion predicate evaluate_gate_a(...,
     verify_filesystem=True) reports no blocking conditions.
  F. receipt_core closure rule: a state=SUCCESS receipt must carry
     reviewer.verdict == PASS and reviewer.independent is True.

This script NEVER edits receipts; it is the reviewer's measuring instrument.
Exit 0 only when ALL 12 units pass ALL six dimensions; each failing unit
prints FAILED:review <id> <dimension> <detail> lines.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = [
    "TST-0223", "TST-0227", "TST-0230", "TST-0233", "TST-0236", "TST-0238",
    "TST-0243", "TST-0245", "TST-0247", "TST-0249", "TST-0255", "TST-0256",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

_spec = importlib.util.spec_from_file_location(
    "rsg", REPO / "platform" / "lib" / "receipt_schema_gate.py"
)
rsg = importlib.util.module_from_spec(_spec)
sys.modules["rsg"] = rsg
_spec.loader.exec_module(rsg)

CAT = json.loads(
    (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
BY_ID = {u["id"]: u for u in CAT["work_units"]}


def lf_sha256(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def review(uid: str) -> list[str]:
    problems: list[str] = []
    unit = BY_ID.get(uid)
    if unit is None:
        return [f"A catalog-entry-absent"]

    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    if not out_rel:
        return ["A output_path-absent-in-catalog"]
    out = REPO / out_rel

    # --- A. artifact -------------------------------------------------------
    if not out.is_file():
        return ["A artifact-absent"]
    if out.stat().st_size <= 0:
        return ["A artifact-empty"]
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"A unparseable:{type(exc).__name__}:{exc}"[:200]]
    if isinstance(doc, dict):
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            problems.append(f"A self-declared:{st}")
        sentinel = str(unit.get("completion_sentinel") or "")
        if sentinel and sentinel not in text:
            problems.append("A sentinel-absent")

    # --- B. subagent return ------------------------------------------------
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    ret_path = pdir / "SUBAGENT-RETURN.json"
    man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    if not ret_path.is_file():
        problems.append("B subagent-return-absent")
    else:
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"B return-unparseable:{type(exc).__name__}")
            ret = None
        if isinstance(ret, dict):
            rst = str(ret.get("status") or ret.get("state") or "").upper()
            if rst in NOT_DELIVERING:
                problems.append(f"B return-self-blocked:{rst}")

    # --- C. manifest row vs MY OWN recompute -------------------------------
    if not man_path.is_file():
        problems.append("C manifest-absent")
    else:
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"C manifest-unparseable:{type(exc).__name__}")
            man = None
        if isinstance(man, dict):
            live_sha, live_bytes = lf_sha256(out)
            rows = [
                a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid
            ]
            if not rows:
                problems.append("C manifest-row-absent")
            else:
                hit = [
                    a for a in rows
                    if str(a.get("path") or "").replace("\\", "/") == out_rel
                    and a.get("present") is True
                    and str(a.get("sha256") or "") == live_sha
                ]
                if not hit:
                    want = rows[0].get("sha256")
                    problems.append(
                        f"C sha-mismatch manifest={str(want)[:16]}.. live={live_sha[:16]}.."
                    )
                else:
                    declared = hit[0].get("bytes")
                    if isinstance(declared, int) and declared != live_bytes:
                        problems.append(
                            f"C bytes-mismatch manifest={declared} live={live_bytes}"
                        )

    # --- D. schema (layer 1) ----------------------------------------------
    # The catalog output_schema chain is: command-center/schema/receipt.schema.json
    # ($defs entry = a bare $ref) -> platform/schema/artifact-class-profiles
    # (also a bare $ref) -> platform/schema/receipt.schema.json (self-contained
    # terminal, SCHEMA_PATH default). Validating the terminal $defs fragment is
    # byte-for-byte the catalog-declared schema, transitively. The root envelope
    # (the program's canonical admission shape) is checked separately.
    schema_ref = str(unit.get("output_schema") or "")
    try:
        base, frag = rsg.parse_schema_ref(schema_ref)
        del base  # chain resolved to the terminal self-contained schema
        errs = rsg.validate_receipt(doc, schema=None, fragment=frag)
        env_errs = rsg.validate_receipt(doc, schema=None, fragment=None)
        errs = errs + [f"envelope:{e}" for e in env_errs]
    except Exception as exc:  # noqa: BLE001 - reviewer instrument must not die
        errs = [f"validator-error:{type(exc).__name__}:{exc}"[:200]]
    if errs:
        problems.append("D schema-errors: " + " | ".join(errs[:3]))

    # --- E. full 12-condition predicate (live filesystem) -------------------
    try:
        gate = rsg.evaluate_gate_a(
            doc, repo_root=REPO, verify_filesystem=True,
            schema=None, fragment=frag,
        )
        bc = gate.blocking_conditions
        bc = bc() if callable(bc) else bc
        blockers = list(bc)
        if blockers:
            problems.append(
                "E predicate-blocking: "
                + " | ".join(f"{c.n}:{c.basis[:120]}" for c in blockers[:4])
            )
    except Exception as exc:  # noqa: BLE001
        problems.append(f"E predicate-error:{type(exc).__name__}:{exc}"[:200])

    # --- F. receipt_core closure rule ---------------------------------------
    if isinstance(doc, dict):
        rev = doc.get("reviewer") or {}
        state = str(doc.get("state") or "").upper()
        if state == "SUCCESS":
            if rev.get("verdict") != "PASS":
                problems.append(
                    f"F SUCCESS-without-PASS verdict={rev.get('verdict')!r}"
                )
            if rev.get("independent") is not True:
                problems.append("F SUCCESS-without-independent-reviewer")
        elif state not in NOT_DELIVERING:
            problems.append(f"F state-not-terminal:{state}")

    return problems


def main() -> int:
    any_fail = False
    for uid in UNITS:
        problems = review(uid)
        if problems:
            any_fail = True
            for p in problems:
                print(f"FAILED:review {uid} {p}")
        else:
            print(f"PASS:review {uid} all-dimensions-clean")
    print("REVIEW-VERDICT:ALL-PASS" if not any_fail else "REVIEW-VERDICT:FAILURES-PRESENT")
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
