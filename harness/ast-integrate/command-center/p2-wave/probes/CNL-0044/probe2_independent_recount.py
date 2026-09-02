#!/usr/bin/env python3
"""Probe 2: independent recount / re-tabulation (reviewer).

Does not read the design-note argument. Re-parses the catalog with a different
extractor, re-runs fixtures, re-computes the duplicate pair, then checks that
the author's NUMBERS match.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
NOTE = REPO / (
    "command-center/design/council/"
    "CNL-0044-executable-runtime-semantics-for-the-7-tradecraft-protocol.md"
)
sys.path.insert(0, str(HERE))
import semantics as S  # noqa: E402

# Different extractor from enumerate.parse_named_list: pull P38..P44 in order
# from the whole CNL-0044 question string without using the naming-parenthesis regex.
RANGE_RE = re.compile(r"\bP(3[8-9]|4[0-4])\b")
EV_RE = re.compile(r"family=TRADECRAFT,\s*expected n=(\d+)")
CROSS_RE = re.compile(
    r"\bP(0[1-9]|[1-4]\d|5[0-8])\s+([a-z0-9-]+(?:\s*\([^)]+\))?)",
    re.I,
)


def load_unit(uid: str) -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def recount_tradecraft() -> list[str]:
    q = str(load_unit("CNL-0044").get("question_or_target") or "")
    seen = []
    for m in RANGE_RE.finditer(q):
        pid = f"P{m.group(1)}"
        if pid not in seen:
            seen.append(pid)
    return seen


def recount_expected_n() -> int | None:
    ev = str(load_unit("CNL-0044").get("evidence_requirement") or "")
    m = EV_RE.search(ev)
    return int(m.group(1)) if m else None


def recount_p48() -> dict | None:
    """Find P48 from CNL-0045, not from CNL-0044's duplicate list."""
    q = str(load_unit("CNL-0045").get("question_or_target") or "")
    for pid, name in CROSS_RE.findall(q):
        if f"P{int(pid)}" == "P48" or pid == "48":
            return {"id": "P48", "name": name.strip()}
    # Fallback: search the P48 token nearby
    m = re.search(r"P48\s+([^,:]+)", q)
    if m:
        return {"id": "P48", "name": m.group(1).strip()}
    return None


def main() -> int:
    ids = recount_tradecraft()
    expected = recount_expected_n()
    if expected != 7 or ids != ["P38", "P39", "P40", "P41", "P42", "P43", "P44"]:
        print(f"FAILED:CNL-0044-probe2 independent recount ids={ids} expected_n={expected}")
        return 1

    verdicts = S.run_all()
    executable = [v["record_id"] for v in verdicts if v["executability"] == "EXECUTABLE"]
    if executable != ids:
        print("FAILED:CNL-0044-probe2 executable set", executable)
        return 1

    p48 = recount_p48()
    if not p48:
        print("FAILED:CNL-0044-probe2 P48 not found in CNL-0045 question")
        return 1
    others = {"ENGINEERING-REVIEW": [p48]}
    # Include every other family record name parsed from CNL-0038..CNL-0046 except TRADECRAFT.
    family_units = {
        "CNL-0038": "DELIBERATIVE",
        "CNL-0039": "ADVERSARIAL",
        "CNL-0040": "JUDICIAL",
        "CNL-0041": "ANONYMOUS",
        "CNL-0042": "GENERATIVE",
        "CNL-0043": "FORECASTING",
        "CNL-0045": "ENGINEERING-REVIEW",
        "CNL-0046": "META-COMPOSITION",
    }
    parsed_others: dict[str, list] = {}
    for uid, fam in family_units.items():
        q = str(load_unit(uid).get("question_or_target") or "")
        recs = []
        for pid, name in CROSS_RE.findall(q):
            recs.append({"id": f"P{int(pid)}", "name": name.strip()})
        parsed_others[fam] = recs
    tradecraft_records = [
        {"id": pid, "name": name}
        for pid, name in zip(
            ids,
            [
                "analysis-of-competing-hypotheses",
                "key-assumptions-check",
                "quality-of-information-check",
                "deception-detection",
                "argument-mapping",
                "premortem",
                "postmortem-5whys-causal",
            ],
        )
    ]
    # Names above are the catalog tokens; duplicate detector uses P43's designed
    # operator vs sibling aliases, so names of P38-P42/P44 are unused for collision.
    dups = S.find_duplicates(tradecraft_records, parsed_others)
    if len(dups) != 1 or dups[0]["tradecraft_id"] != "P43" or dups[0]["other_id"] != "P48":
        print("FAILED:CNL-0044-probe2 independent duplicate set", dups)
        return 1

    if not NOTE.is_file():
        print("FAILED:CNL-0044-probe2 design note absent")
        return 1
    note = json.loads(NOTE.read_text(encoding="utf-8"))
    # Numbers only — not the author's prose.
    n_note = int(note.get("enumeration", {}).get("measured_n") or -1)
    exec_note = [
        p["record_id"]
        for p in (note.get("protocols") or [])
        if p.get("executability") == "EXECUTABLE"
    ]
    dup_note = [
        (d.get("tradecraft_id"), d.get("other_id"))
        for d in (note.get("duplicates") or [])
    ]
    if n_note != 7:
        print("FAILED:CNL-0044-probe2 note measured_n disagreement", n_note)
        return 1
    if exec_note != ids:
        print("FAILED:CNL-0044-probe2 note executable disagreement", exec_note)
        return 1
    if dup_note != [("P43", "P48")]:
        print("FAILED:CNL-0044-probe2 note duplicate disagreement", dup_note)
        return 1
    if str(note.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0044-probe2 note self-declared", note.get("state"))
        return 1

    print(
        f"recount_n={len(ids)} expected_n={expected} executable={len(executable)} "
        f"duplicates={dup_note} p48_name={p48['name']!r} note_n={n_note}"
    )
    print("SUCCESS:CNL-0044-probe2 independent recount reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
