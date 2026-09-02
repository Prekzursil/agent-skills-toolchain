#!/usr/bin/env python3
"""Probe 2: independent recount from fixtures; disagreement in a number blocks.

Does not import tally.py. Signal 1 is integer field recount. Signal 2 is a
regex count of yes-choice tokens in the fixture bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recount as R  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md"
)
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
FIX = HERE / "fixtures"
TALLY_PY = HERE / "tally.py"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0058-probe2 {msg}")
    return 1


def needle_line(path: Path, needle: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, ln in enumerate(lines, 1) if needle in ln]
    if len(hits) != 1:
        raise ValueError(f"{path.name} needle {needle!r} hits={hits}")
    return hits[0]


def main() -> int:
    if not ART.is_file():
        return fail("design note missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CNL-0058" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")

    mutant = dict(doc)
    mutant.pop("reviewer", None)
    if not list(validator.iter_errors(mutant)):
        return fail("schema accepted artifact with reviewer stripped")

    measured = (doc.get("measured") or {}).get("supermajority") or {}
    names = ("planted-bad", "known-good", "quorum-void", "death-unreplaced")
    for name in names:
        path = FIX / f"{name}.json"
        profile = R.load(path)
        live = R.recount(profile)
        text_yes = R.text_yes_count(path.read_text(encoding="utf-8"))
        print(
            f"recount[{name}] yes={live['yes']} freeze_n={live['freeze_n']} "
            f"shrunk_n={live['shrunk_n']} detector={live['detector']} "
            f"outcome={live['outcome']} text_yes={text_yes}"
        )
        if text_yes != live["yes"]:
            return fail(f"{name} text-yes {text_yes} != field-yes {live['yes']}")
        row = measured.get(name) or {}
        for field in ("yes", "freeze_n", "shrunk_n", "detector", "outcome"):
            if row.get(field) != live[field if field != "detector" else "detector"]:
                if field == "detector":
                    want = live["detector"]
                else:
                    want = live[field]
                if row.get(field) != want:
                    return fail(
                        f"disagreement {name}.{field} artifact={row.get(field)!r} "
                        f"recount={want!r}"
                    )

    death = R.load(FIX / "death-unreplaced.json")
    death_live = R.recount(death)
    if death_live["freeze_n"] != 6 or death_live["yes"] != 3:
        return fail("death-unreplaced recount unexpected")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("verdict") != "PASS":
        return fail("reviewer did not independently PASS")
    recount_blob = str(rev.get("method") or rev.get("notes") or "")
    if "recount" not in recount_blob.lower():
        return fail("reviewer method is not a recount")

    for claim in doc.get("claims") or []:
        anchor = str(claim.get("anchor") or "")
        if ":" not in anchor:
            return fail(f"claim {claim.get('id')} anchor not file:line")
        rel, _, line_s = anchor.partition(":")
        rel = rel.replace("\\", "/")
        try:
            line = int(line_s)
        except ValueError:
            return fail(f"claim {claim.get('id')} bad line {line_s}")
        path = REPO / rel
        if not path.is_file():
            return fail(f"claim {claim.get('id')} missing {rel}")
        lines = path.read_text(encoding="utf-8").splitlines()
        if line < 1 or line > len(lines):
            return fail(f"claim {claim.get('id')} line oob")
        print(f"anchor {claim.get('id')} {rel}:{line} ok")

    freeze_line = needle_line(TALLY_PY, "FREEZE-N: len(freeze_set)")
    det_line = needle_line(TALLY_PY, "DETECTOR: FIRE iff")
    super_line = needle_line(TALLY_PY, "SUPERMAJORITY: m * yes")
    print(f"tally_markers freeze={freeze_line} super={super_line} detector={det_line}")

    print("SUCCESS:CNL-0058-probe2 independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
