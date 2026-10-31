"""Probe: are these presets actually EDITABLE, or just valid?

"Editable" is a claim, so it gets a probe. For each of the 17 lane-2 files:

1. DOCUMENTED: metadata.notes exists, is non-trivial, and contains an
   "EDITABLE DIALS" section naming at least two JSON pointers. A file whose only
   documentation is its field names is an opaque blob.
2. LIVE DIAL: turn a real dial (raise the seat count coherently) and confirm the
   edited file STILL validates - a dial that cannot move is decorative.
3. GUARDED DIAL: turn the same dial INCOHERENTLY (seats up, roster not) and
   confirm the validator REJECTS it. Without this, (2) proves only that the
   validator is asleep.
4. PURE JSON: the file parses with no build step and round-trips byte-identically
   through json.loads/json.dumps at the same indent, i.e. nothing in it depends
   on the generator.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "platform" / "lib"))

import jsonschema  # noqa: E402
from councilspec import semantics  # noqa: E402

SCHEMA = json.loads(
    (REPO / "platform" / "schema" / "councilspec.schema.json").read_text(
        encoding="utf-8"
    )
)
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)

LANE_FILES = [
    "c-s17-red-blue-4",
    "c-s18-oxford-4-plus-judge",
    "c-s19-socratic-chair-plus-4",
    "c-s20-charrette-5-design",
    "c-s21-six-hats-6",
    "c-s22-nominal-group-6",
    "c-s23-delphi-5-anon-3rounds",
    "c-s24-ach-5-hypotheses",
    "c-s25-war-room-5-incident",
    "c-s26-postmortem-5-blameless",
    "c-s27-kill-the-company-5",
    "c-s28-stakeholder-negotiation-5",
    "c-s29-two-key-authorization",
    "c-s30-rfc-last-call-open",
    "c-d31-deep-architecture-12",
    "c-d32-deep-security-threat-model-10",
    "g-up01-stakeholder-user-panel",
]


def accepted(spec: Dict[str, Any]) -> bool:
    if list(VALIDATOR.iter_errors(spec)):
        return False
    return not [f for f in semantics.check(spec) if f.severity == "ERROR"]


def add_seat(spec: Dict[str, Any], coherent: bool) -> Dict[str, Any]:
    s = copy.deepcopy(spec)
    count = s["participants"]["count"]
    if count.get("mode") != "exact":
        # elastic/range councils widen differently
        count["max"] = (count.get("max") or 9) + 2
        return s
    count["exact_n"] += 1
    if count.get("min") is not None:
        count["min"] += 1
    if count.get("max") is not None:
        count["max"] += 1
    if coherent:
        seed = copy.deepcopy(s["participants"]["roster"][0])
        seed["participant_id"] = "extra-seat-1"
        seed["display_name"] = "Added by the editability probe"
        s["participants"]["roster"].append(seed)
    return s


def main() -> int:
    rows: List[Dict[str, Any]] = []
    bad = 0
    for stem in LANE_FILES:
        path = HERE / f"{stem}.councilspec.json"
        raw = path.read_text(encoding="utf-8")
        spec = json.loads(raw)

        notes = (spec.get("metadata") or {}).get("notes") or ""
        pointers = notes.count("$.")
        documented = ("EDITABLE DIALS" in notes) and pointers >= 2 and len(notes) >= 400

        base_ok = accepted(spec)
        live_ok = accepted(add_seat(spec, coherent=True))
        guard_rejects = not accepted(add_seat(spec, coherent=False))
        roundtrip = json.dumps(spec, indent=2, ensure_ascii=True) + "\n" == raw

        ok = documented and base_ok and live_ok and guard_rejects and roundtrip
        bad += 0 if ok else 1
        rows.append(
            {
                "file": path.name,
                "documented": documented,
                "dial_pointers_in_notes": pointers,
                "notes_chars": len(notes),
                "base_valid": base_ok,
                "live_dial_accepted": live_ok,
                "incoherent_edit_rejected": guard_rejects,
                "pure_json_roundtrip": roundtrip,
                "verdict": "PASS" if ok else "FAIL",
            }
        )
        print(
            f"[{'ok  ' if ok else 'FAIL'}] {path.name:<48} notes={len(notes):>4}c "
            f"pointers={pointers:>2} base={base_ok} dial_moves={live_ok} "
            f"guard_fires={guard_rejects} pure_json={roundtrip}"
        )

    (HERE / "_lane2_probe_editable_out.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"\nfiles={len(rows)} pass={len(rows) - bad} fail={bad}")
    if bad:
        print(f"FAILED:editability {bad} file(s) are not demonstrably editable")
        return 1
    print(
        "SUCCESS:editability all 17 files are documented, their dials move and still validate, "
        "an incoherent edit is rejected, and each is pure JSON with no build step"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
