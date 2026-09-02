#!/usr/bin/env python3
"""Probe 1: blinding/contamination + corpus differential + 12-condition coverage."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from clean_room import evaluate, spec_bytes  # noqa: E402
from differ import differ  # noqa: E402
from observe import all_cases, ensure_fixtures  # noqa: E402
from shipped_adapter import evaluate_observation as shipped_eval  # noqa: E402
from shipped_adapter import shipped_path  # noqa: E402

REPO = HERE.parents[3]


def _fail(msg: str) -> int:
    print(f"FAILED:CNF-0170-probe1 {msg}")
    return 1


def blinding_attestation() -> dict:
    payload = spec_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    src = (HERE / "clean_room.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    forbidden = [
        name
        for name in imports
        if "completion_predicate" in name or name in {"shipped_adapter", "platform"}
    ]
    banned_tokens = (
        "completion_predicate",
        "shipped_adapter",
        "platform.lib",
        "platform/lib",
    )
    token_hits = [t for t in banned_tokens if t in src]
    shipped = shipped_path()
    shipped_in_payload = False
    if shipped is not None:
        shipped_in_payload = shipped.read_bytes() in payload
    return {
        "payload_files": ["SPEC-FRAGMENT.txt"],
        "payload_sha256": digest,
        "payload_bytes": len(payload),
        "clean_room_imports": imports,
        "forbidden_imports": forbidden,
        "banned_token_hits": token_hits,
        "shipped_present": shipped is not None,
        "shipped_path": None if shipped is None else shipped.relative_to(REPO).as_posix(),
        "shipped_bytes_in_payload": shipped_in_payload,
        "ok": not forbidden and not token_hits and not shipped_in_payload,
    }


def coverage(rows: list[dict]) -> dict:
    exercised = {n: [] for n in range(1, 13)}
    not_checked = []
    for row in rows:
        cr = row["clean_room"]
        for cond in cr.get("conditions") or []:
            n = int(cond["n"])
            if cond["outcome"] != "UNKNOWN":
                exercised[n].append(
                    {"case": row["id"], "outcome": cond["outcome"], "basis": cond["basis"]}
                )
    for n in range(1, 13):
        if not exercised[n]:
            not_checked.append(n)
    return {
        "exercised": {str(n): v[:3] for n, v in exercised.items()},
        "not_checked": not_checked,
        "all_twelve_exercised": not not_checked,
    }


def maybe_check_receipt() -> dict | None:
    path = REPO / "command-center/receipts/CNF-0170.json"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    issues = []
    if "SUCCESS:CNF-0170" not in text:
        issues.append("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        issues.append(f"self-declared:{doc.get('state')}")
    verdict = str((doc.get("confirmation") or doc).get("verdict") or "").upper()
    if verdict in {"CONFIRMED", "REFUTED"}:
        src = (doc.get("confirmation") or doc).get("source_probe")
        if not src:
            issues.append("unsourced-CONFIRMED-or-REFUTED")
    return {"present": True, "issues": issues, "verdict": verdict}


def main() -> int:
    ensure_fixtures()
    blind = blinding_attestation()
    if not blind["ok"]:
        print(json.dumps(blind, indent=2, sort_keys=True))
        return _fail("contamination: clean-room payload not blinded from shipped reducer")

    cases = all_cases()
    table = []
    for obs in cases:
        cr = evaluate(obs)
        sh = shipped_eval(obs)
        diff = differ(cr, sh)
        table.append(
            {
                "id": obs["id"],
                "live": bool(obs.get("live")),
                "target_unsatisfied": obs.get("target_unsatisfied"),
                "clean_room": cr,
                "shipped": {
                    "verdict": sh.get("verdict"),
                    "shipped_present": sh.get("shipped_present"),
                    "conditions": sh.get("conditions"),
                },
                "differ": {
                    "disagreement_count": diff["disagreement_count"],
                    "agreement_count": diff["agreement_count"],
                    "verdicts_match": diff["verdicts_match"],
                    "disagreements": diff["disagreements"],
                },
            }
        )

    # Targeted mutants must fail the named condition in the clean-room.
    mutant_misses = []
    for row in table:
        n = row.get("target_unsatisfied")
        if not n:
            continue
        conds = {int(c["n"]): c for c in row["clean_room"]["conditions"]}
        if conds.get(int(n), {}).get("outcome") != "UNSATISFIED":
            mutant_misses.append(
                {
                    "id": row["id"],
                    "n": n,
                    "got": conds.get(int(n), {}).get("outcome"),
                    "basis": conds.get(int(n), {}).get("basis"),
                }
            )
    if mutant_misses:
        print(json.dumps({"mutant_misses": mutant_misses}, indent=2))
        return _fail("targeted mutant did not unsatisfy the named condition")

    cov = coverage(table)
    if not cov["all_twelve_exercised"]:
        print(json.dumps(cov, indent=2))
        return _fail(f"conditions NOT-CHECKED: {cov['not_checked']}")

    healthy = next(r for r in table if r["id"] == "FIX-HEALTHY")
    if healthy["clean_room"]["verdict"] != "COMPLETE":
        print(json.dumps(healthy["clean_room"], indent=2)[:4000])
        return _fail("healthy fixture was not COMPLETE in clean-room")

    receipt = maybe_check_receipt()
    if receipt and receipt["issues"]:
        print(json.dumps(receipt, indent=2))
        return _fail("receipt structural issues " + ",".join(receipt["issues"]))

    disagreement_rows = sum(1 for r in table if r["differ"]["disagreement_count"])
    summary = {
        "probe": "probe1-contamination-corpus",
        "blinding": blind,
        "cases": len(table),
        "synthetic": sum(1 for r in table if not r["live"]),
        "live": sum(1 for r in table if r["live"]),
        "cases_with_disagreement": disagreement_rows,
        "zero_disagreement_suspicious": disagreement_rows == 0,
        "coverage": {"not_checked": cov["not_checked"], "all_twelve": cov["all_twelve_exercised"]},
        "healthy_clean_room": healthy["clean_room"]["verdict"],
        "shipped_present": healthy["shipped"]["shipped_present"],
        "receipt": receipt,
        "disagreement_table_head": [
            {
                "id": r["id"],
                "cr": r["clean_room"]["verdict"],
                "sh": r["shipped"]["verdict"],
                "n_disagree": r["differ"]["disagreement_count"],
            }
            for r in table
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        f"blinding_ok={blind['ok']} cases={len(table)} "
        f"disagree_rows={disagreement_rows} coverage12={cov['all_twelve_exercised']}"
    )
    print("SUCCESS:CNF-0170-probe1 contamination, corpus differ, 12-condition coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
