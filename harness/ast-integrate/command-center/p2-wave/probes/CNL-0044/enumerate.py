"""Enumerate TRADECRAFT family members from on-tree signals.

Library file 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is searched, never invented.
Member ids are read from WORK-UNIT-CATALOG.json with two independent parsers.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FAMILY = "TRADECRAFT"
FAMILY_UNIT = "CNL-0044"
EXPECTED_N = 7
LIBRARY_NAME = "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
FAMILY_UNITS = {
    "CNL-0038": "DELIBERATIVE",
    "CNL-0039": "ADVERSARIAL",
    "CNL-0040": "JUDICIAL",
    "CNL-0041": "ANONYMOUS",
    "CNL-0042": "GENERATIVE",
    "CNL-0043": "FORECASTING",
    "CNL-0044": "TRADECRAFT",
    "CNL-0045": "ENGINEERING-REVIEW",
    "CNL-0046": "META-COMPOSITION",
}

# First parser: comma-separated P-id list inside the naming parenthesis.
LIST_RE = re.compile(
    r"named so no member can fall through a family mis-assignment \((P\d+ .+)\)\s*:",
    re.I | re.S,
)
ITEM_RE = re.compile(r"P(\d+)\s+([^,]+?)(?=, P\d+|$)", re.I)
# Second parser: P-ids only, no names — independent of comma-splitting names.
PID_ONLY_RE = re.compile(r"\bP(\d{2})\b")
EVIDENCE_N_RE = re.compile(
    r"family=TRADECRAFT,\s*expected n=(\d+)", re.I
)


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def catalog_unit(uid: str, data: dict | None = None) -> dict:
    data = data if data is not None else load_catalog()
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def parse_named_list(question: str) -> list[dict]:
    m = LIST_RE.search(question or "")
    if not m:
        return []
    blob = m.group(1)
    out = []
    for num, name in ITEM_RE.findall(blob):
        out.append(
            {
                "id": f"P{int(num)}",
                "name": name.strip(),
                "pid_num": int(num),
            }
        )
    return out


def parse_pids_only(question: str) -> list[str]:
    """Independent of name-splitting: every Pxx token in the naming clause."""
    m = LIST_RE.search(question or "")
    blob = m.group(1) if m else (question or "")
    return [f"P{int(n)}" for n in PID_ONLY_RE.findall(blob)]


def library_candidates() -> list[Path]:
    return [
        Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806") / LIBRARY_NAME,
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806") / LIBRARY_NAME,
        Path.home() / ".claude/harness-restore-20260806" / LIBRARY_NAME,
        REPO / LIBRARY_NAME,
        REPO / "command-center" / LIBRARY_NAME,
        REPO / "command-center" / "sources" / LIBRARY_NAME,
        REPO / "command-center" / "design" / "council" / LIBRARY_NAME,
        Path("/opt/p2") / LIBRARY_NAME,
    ]


def find_library() -> dict:
    tried = []
    found = None
    for path in library_candidates():
        present = path.is_file()
        tried.append({"path": str(path), "present": present})
        if present and found is None:
            found = path
    extra = []
    src = REPO / "command-center" / "sources"
    if src.is_dir():
        extra = [p for p in src.glob(LIBRARY_NAME)]
    for p in extra:
        rec = {"path": str(p), "present": p.is_file()}
        if rec not in tried:
            tried.append(rec)
        if p.is_file() and found is None:
            found = p
    return {
        "filename": LIBRARY_NAME,
        "present": found is not None,
        "path": str(found) if found else None,
        "tried": tried,
        "note": (
            "Library bodies were not read because the file is absent on this "
            "worktree. Enumeration of TRADECRAFT P-ids uses catalog-named "
            "records (CNL-0038..CNL-0046 question_or_target lists), not an "
            "invented protocol catalogue."
            if found is None
            else "Library file present; family members should be counted from it."
        ),
    }


def enumerate_family() -> dict:
    data = load_catalog()
    unit = catalog_unit(FAMILY_UNIT, data)
    question = str(unit.get("question_or_target") or "")
    evidence = str(unit.get("evidence_requirement") or "")

    signal1 = parse_named_list(question)
    signal1_ids = [r["id"] for r in signal1]

    # Independent: P-id tokens only, no name field.
    signal2_ids = parse_pids_only(question)

    ev = EVIDENCE_N_RE.search(evidence)
    signal_ev = {
        "family": FAMILY,
        "expected_n": int(ev.group(1)) if ev else None,
        "source": (
            "command-center/WORK-UNIT-CATALOG.json "
            "work_units[id=CNL-0044].evidence_requirement"
        ),
    }

    # Independent: union of all family-unit naming lists, then filter TRADECRAFT unit.
    by_family: dict[str, list[dict]] = {}
    for uid, fam in FAMILY_UNITS.items():
        q = str(catalog_unit(uid, data).get("question_or_target") or "")
        by_family[fam] = parse_named_list(q)

    tradecraft_from_all = by_family.get(FAMILY) or []
    signal3_ids = [r["id"] for r in tradecraft_from_all]

    # Confirm no other family claims P38-P44.
    claimed_elsewhere = []
    tradecraft_nums = {r["pid_num"] for r in signal1}
    for fam, recs in by_family.items():
        if fam == FAMILY:
            continue
        for r in recs:
            if r["pid_num"] in tradecraft_nums or 38 <= r["pid_num"] <= 44:
                claimed_elsewhere.append(
                    {"id": r["id"], "name": r["name"], "family": fam}
                )

    n1, n2, n3 = len(signal1_ids), len(signal2_ids), len(signal3_ids)
    ids_agree = signal1_ids == signal2_ids == signal3_ids
    n_agree = n1 == n2 == n3 == EXPECTED_N and signal_ev["expected_n"] == EXPECTED_N

    lib = find_library()
    library_n = None
    library_ids = None
    if lib["present"] and lib["path"]:
        raw = json.loads(Path(lib["path"]).read_text(encoding="utf-8"))
        recs = []
        if isinstance(raw, dict):
            for key in ("protocols", "records", "items"):
                if isinstance(raw.get(key), list):
                    recs = raw[key]
                    break
            if not recs:
                recs = raw.get("protocol_records") or []
        elif isinstance(raw, list):
            recs = raw
        matched = []
        for rec in recs:
            if not isinstance(rec, dict):
                continue
            fam = str(rec.get("family") or rec.get("Family") or "")
            if fam.upper() != FAMILY:
                continue
            rid = rec.get("id") or rec.get("record_id") or rec.get("pid")
            matched.append(str(rid))
        library_n = len(matched)
        library_ids = matched

    return {
        "family": FAMILY,
        "expected_n": EXPECTED_N,
        "library": lib,
        "library_family_n": library_n,
        "library_family_ids": library_ids,
        "records": signal1,
        "ids": signal1_ids,
        "measured_n": n1,
        "claimed_elsewhere": claimed_elsewhere,
        "agreement": bool(ids_agree and n_agree and not claimed_elsewhere),
        "signals": [
            {
                "id": "catalog-question-named-list",
                "source": (
                    "command-center/WORK-UNIT-CATALOG.json "
                    "work_units[id=CNL-0044].question_or_target"
                ),
                "mechanism": "regex split of the naming parenthesis on ', P'",
                "ids": signal1_ids,
                "n": n1,
            },
            {
                "id": "catalog-question-pid-tokens",
                "source": (
                    "command-center/WORK-UNIT-CATALOG.json "
                    "work_units[id=CNL-0044].question_or_target"
                ),
                "mechanism": "findall Pxx tokens inside the naming parenthesis (no names)",
                "ids": signal2_ids,
                "n": n2,
            },
            {
                "id": "all-family-units-then-filter-TRADECRAFT",
                "source": (
                    "command-center/WORK-UNIT-CATALOG.json "
                    "work_units[id=CNL-0038..CNL-0046].question_or_target"
                ),
                "mechanism": "parse every family unit list, keep FAMILY=TRADECRAFT",
                "ids": signal3_ids,
                "n": n3,
            },
            {
                "id": "evidence-requirement-expected-n",
                "source": signal_ev["source"],
                "mechanism": "regex family=TRADECRAFT, expected n=N",
                "expected_n": signal_ev["expected_n"],
            },
        ],
        "other_families": {
            fam: [{"id": r["id"], "name": r["name"]} for r in recs]
            for fam, recs in by_family.items()
            if fam != FAMILY
        },
        "question": question,
        "unit": {
            "id": FAMILY_UNIT,
            "output_path": unit.get("output_path"),
            "output_schema": unit.get("output_schema"),
            "completion_sentinel": unit.get("completion_sentinel"),
            "title": unit.get("title"),
        },
    }
