#!/usr/bin/env python3
"""Executable go/no-go over the 21 program stopping conditions.

GO only when every condition is TRUE. NOT-CHECKED blocks as hard as FALSE.
Condition 13 reads REL-0003's recorded ruling; it never hardcodes canary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from conditions import (  # noqa: E402
    CONDITIONS,
    EVIDENCE_SCHEMA,
    PACKET_SCHEMA,
    REL0003,
)

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
VERDICTS = ("TRUE", "FALSE", "NOT-CHECKED")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return exc


def _row(cond: dict, verdict: str, reason: str, **extra: Any) -> dict:
    if verdict not in VERDICTS:
        raise ValueError(verdict)
    out = {
        "id": cond["id"],
        "spec_line": cond["spec_line"],
        "text": cond["text"],
        "text_provenance": cond["text_provenance"],
        "catalog_anchor": cond["catalog_anchor"],
        "verdict": verdict,
        "anchor": extra.pop("anchor", cond["evidence_path"]),
        "evaluation_kind": extra.pop("evaluation_kind", "file-read"),
        "reason": reason,
        "evidence_path": cond["evidence_path"],
        "schema_ok": extra.pop("schema_ok", False),
    }
    out.update(extra)
    return out


def _evidence_schema_ok(doc: Any, condition_id: int) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, f"not-an-object:{type(doc).__name__}"
    if doc.get("schema") != EVIDENCE_SCHEMA:
        return False, "wrong-schema-id"
    cid = doc.get("condition_id")
    if cid != condition_id:
        return False, f"condition-id-mismatch:{cid!r}"
    verdict = doc.get("verdict")
    if verdict not in VERDICTS:
        return False, f"verdict-not-in-enum:{verdict!r}"
    anchor = doc.get("anchor")
    if not isinstance(anchor, str) or len(anchor) < 3:
        return False, "anchor-missing"
    return True, "ok"


def _packet_schema_ok(doc: Any) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, f"not-an-object:{type(doc).__name__}"
    if doc.get("schema") != PACKET_SCHEMA:
        return False, "wrong-schema-id"
    if doc.get("unit_id") != "REL-0003":
        return False, "unit-id-mismatch"
    for key in ("question", "recommendation", "default_if_unanswered"):
        val = doc.get(key)
        if not isinstance(val, str) or len(val) < 8:
            return False, f"missing-field:{key}"
    return True, "ok"


def _named_receipt_ok(root: Path, rel: str) -> tuple[str, str]:
    path = root / rel
    if not path.is_file():
        return "NOT-CHECKED", f"named-receipt-absent:{rel}"
    doc = load_json(path)
    if not isinstance(doc, dict):
        return "FALSE", f"named-receipt-unparseable:{rel}"
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return "FALSE", f"named-receipt-self-declared:{rel}:{state}"
    sentinel = str(doc.get("sentinel") or "")
    if not sentinel.startswith("SUCCESS:"):
        return "FALSE", f"named-receipt-sentinel:{rel}"
    unit_id = str(doc.get("unit_id") or "")
    expected = Path(rel).stem
    if unit_id and unit_id != expected:
        return "FALSE", f"named-receipt-unit-mismatch:{rel}:{unit_id}"
    return "TRUE", f"named-receipt-ok:{rel}"


def evaluate_condition_13(root: Path, cond: dict) -> dict:
    """Read REL-0003's ruling. Never interpret canary without that file."""
    path = root / REL0003
    extras = {
        "hardcoded_canary": False,
        "ruling_source": REL0003,
        "ruling_present": path.is_file(),
        "named_receipts": [],
    }
    if not path.is_file():
        return _row(
            cond,
            "NOT-CHECKED",
            "REL-0003 receipt absent; owner ruling unread",
            schema_ok=False,
            **extras,
        )
    doc = load_json(path)
    if not isinstance(doc, dict):
        return _row(
            cond,
            "FALSE",
            f"REL-0003 unparseable:{type(doc).__name__}",
            schema_ok=False,
            **extras,
        )
    ok, why = _packet_schema_ok(doc)
    extras["schema_ok"] = ok
    if not ok:
        return _row(
            cond,
            "FALSE",
            f"REL-0003 schema-invalid:{why}",
            **extras,
        )
    ruling = doc.get("ruling")
    if not isinstance(ruling, dict) or not ruling.get("recorded"):
        return _row(
            cond,
            "NOT-CHECKED",
            "REL-0003 packet has no recorded ruling",
            **extras,
        )
    receipts = ruling.get("evidence_receipts")
    if not isinstance(receipts, list) or not receipts:
        return _row(
            cond,
            "NOT-CHECKED",
            "ruling recorded but names no evidence receipts",
            **extras,
        )
    named: list[dict] = []
    worst = "TRUE"
    reasons: list[str] = []
    for rel in receipts:
        if not isinstance(rel, str) or not rel.strip():
            worst = "FALSE"
            reasons.append("non-string-receipt-path")
            continue
        verdict, reason = _named_receipt_ok(root, rel.replace("\\", "/"))
        named.append({"path": rel, "verdict": verdict, "reason": reason})
        reasons.append(reason)
        if verdict == "FALSE":
            worst = "FALSE"
        elif verdict == "NOT-CHECKED" and worst != "FALSE":
            worst = "NOT-CHECKED"
    extras["named_receipts"] = named
    extras["ruling_equivalent"] = ruling.get("condition_13_equivalent")
    return _row(
        cond,
        worst,
        "; ".join(reasons),
        **extras,
    )


def evaluate_standard(root: Path, cond: dict) -> dict:
    rel = cond["evidence_path"]
    path = root / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return _row(
            cond,
            "NOT-CHECKED",
            "evidence file absent",
            schema_ok=False,
        )
    doc = load_json(path)
    if not isinstance(doc, dict):
        return _row(
            cond,
            "FALSE",
            f"unparseable:{type(doc).__name__}",
            schema_ok=False,
        )
    ok, why = _evidence_schema_ok(doc, cond["id"])
    if not ok:
        return _row(
            cond,
            "FALSE",
            f"schema-invalid:{why}",
            schema_ok=False,
            observed_keys=sorted(str(k) for k in doc.keys()),
        )
    verdict = str(doc["verdict"])
    return _row(
        cond,
        verdict,
        "schema-valid evidence file read",
        schema_ok=True,
        evidence_anchor=doc.get("anchor"),
        evidence_probe=doc.get("probe"),
    )


def evaluate(root: Path | None = None) -> dict:
    root = Path(root) if root is not None else REPO
    rows: list[dict] = []
    for cond in CONDITIONS:
        if cond.get("special") == "rel-0003-ruling":
            rows.append(evaluate_condition_13(root, cond))
        else:
            rows.append(evaluate_standard(root, cond))
    counts = {
        "TRUE": sum(1 for r in rows if r["verdict"] == "TRUE"),
        "FALSE": sum(1 for r in rows if r["verdict"] == "FALSE"),
        "NOT-CHECKED": sum(1 for r in rows if r["verdict"] == "NOT-CHECKED"),
    }
    counts["blocking"] = counts["FALSE"] + counts["NOT-CHECKED"]
    decision = "GO" if counts["TRUE"] == 21 and counts["blocking"] == 0 else "NO-GO"
    c13 = next(r for r in rows if r["id"] == 13)
    spec_path = root / "_USER-PROMPTS.md"
    return {
        "decision": decision,
        "aggregate_rule": (
            "GO only when every one of the 21 conditions is TRUE; "
            "NOT-CHECKED blocks precisely as hard as FALSE."
        ),
        "conditions": rows,
        "counts": counts,
        "condition_13": {
            "ruling_source": REL0003,
            "hardcoded_canary": False,
            "verdict": c13["verdict"],
            "reason": c13["reason"],
            "ruling_present": c13.get("ruling_present"),
        },
        "spec_file": {
            "path": "_USER-PROMPTS.md",
            "present": spec_path.is_file(),
            "note": (
                "verbatim spec lines 11376-11398 were not readable on this tree; "
                "condition TEXT is catalog-pinned, verdicts are file reads"
                if not spec_path.is_file()
                else "spec file present"
            ),
        },
        "evaluator": "command-center/p2-wave/probes/REL-0018/evaluator.py",
        "root": str(root),
    }


def fingerprint(report: dict) -> tuple:
    return tuple(
        (r["id"], r["verdict"], r["reason"], r["evaluation_kind"])
        for r in report["conditions"]
    )


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO
    report = evaluate(root)
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"SUCCESS:REL-0018-eval decision={report['decision']} "
        f"TRUE={report['counts']['TRUE']} "
        f"FALSE={report['counts']['FALSE']} "
        f"NOT-CHECKED={report['counts']['NOT-CHECKED']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
