"""Probe: does each design card's declared seat count equal the sum of its own role list?

Mechanical, not judgement: parse the 16 design cards in this slice (C-D33..C-D45, C-X46..C-X48)
out of 12-COUNCIL-PROTOCOLS-AND-PRESETS.md, expand every role multiplier, and compare.

The claim this settles (asserted in C-X46's metadata.notes): C-X46 is the ONLY card in the slice
whose 'seats:' number disagrees with its own role list.

DETECTOR CONTROL: the parser is first run against synthetic rows with known answers, including a
known-BROKEN row, so a zero-mismatch result cannot be a silent parser failure.

Run from the repo root:  python platform/council/presets/_probe_seat_arithmetic.py
"""

from __future__ import annotations

import os
import re

DESIGN_DOC = os.path.join(
    os.path.expanduser("~"),
    ".claude",
    "harness-restore-20260806",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
)

SLICE_IDS = [f"C-D{n}" for n in range(33, 46)] + ["C-X46", "C-X47", "C-X48"]

_CARD_RE = re.compile(r"^####\s+(C-[A-Z]\d+)\s+`([^`]+)`", re.MULTILINE)
_SEATS_RE = re.compile(r"\*\*seats:\*\*\s*(\d+)")
_ROLES_RE = re.compile(r"\*\*roles:\*\*\s*(.+?)\s*\|\s*\*\*rounds")
_PAREN_RE = re.compile(r"\([^)]*\)")
_N_OF_M_RE = re.compile(r"^(\d+)\s+[a-z_]+\s*x\s*(\d+)$")
_SUFFIX_RE = re.compile(r"_x(\d+)$")


def expand_roles(roles_text: str) -> int:
    """Sum a design card's role list, expanding every multiplier form it uses."""
    cleaned = _PAREN_RE.sub("", roles_text)
    total = 0
    for raw in cleaned.split(","):
        token = raw.strip()
        if not token:
            continue
        m = _N_OF_M_RE.match(token)
        if m:
            total += int(m.group(1)) * int(m.group(2))
            continue
        m = _SUFFIX_RE.search(token)
        total += int(m.group(1)) if m else 1
    return total


def _detector_control() -> list[str]:
    """Prove the parser computes known answers, INCLUDING a known-broken row."""
    cases = [
        ("evidence_clerk,implementer,red_x2", 4),
        ("meta_chair,4 subcouncils x3,dissent_guardian,scribe", 15),
        ("writer_x36 (6 groups of 6)", 36),
        ("juror_x12,judge", 13),
        ("lens_seat_x40,ground_agent,synthesiser_x2", 43),
        ("solo", 1),
    ]
    failures = []
    for text, want in cases:
        got = expand_roles(text)
        status = "ok " if got == want else "FAIL"
        print(f"  [{status}] expand_roles({text!r}) = {got} (want {want})")
        if got != want:
            failures.append(f"parser control failed on {text!r}: {got} != {want}")
    # a deliberately-broken row: declared 40 vs a role list of 43 MUST be seen as a mismatch
    if expand_roles("lens_seat_x40,ground_agent,synthesiser_x2") == 40:
        failures.append(
            "parser cannot distinguish 40 from 43; the mismatch detector is blind"
        )
    return failures


def main() -> int:
    print("DETECTOR CONTROL (synthetic rows with known answers):")
    failures = _detector_control()
    print()

    if not os.path.isfile(DESIGN_DOC):
        print(f"FAILED:seat-arithmetic design doc not found: {DESIGN_DOC}")
        return 1

    with open(DESIGN_DOC, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    cards = list(_CARD_RE.finditer(text))
    bounds = {}
    for i, m in enumerate(cards):
        end = cards[i + 1].start() if i + 1 < len(cards) else len(text)
        bounds[m.group(1)] = (m.group(2), text[m.start() : end])

    mismatches, parsed = [], 0
    for design_id in SLICE_IDS:
        if design_id not in bounds:
            failures.append(f"{design_id}: card not found in the design doc")
            continue
        name, body = bounds[design_id]
        sm, rm = _SEATS_RE.search(body), _ROLES_RE.search(body)
        if not sm or not rm:
            failures.append(f"{design_id}: could not parse seats/roles")
            continue
        parsed += 1
        declared, computed = int(sm.group(1)), expand_roles(rm.group(1))
        flag = "MISMATCH" if declared != computed else "ok      "
        print(f"  [{flag}] {design_id} {name}: seats={declared} role_sum={computed}")
        if declared != computed:
            mismatches.append((design_id, name, declared, computed, rm.group(1)))

    print()
    if parsed != len(SLICE_IDS):
        failures.append(f"parsed only {parsed} of {len(SLICE_IDS)} cards")

    expected = {"C-X46"}
    found = {m[0] for m in mismatches}
    if found != expected:
        failures.append(
            f"mismatch set is {sorted(found)}, expected {sorted(expected)}; the claim that C-X46 "
            "is the only arithmetic defect in this slice does not hold as stated"
        )

    for design_id, name, declared, computed, roles in mismatches:
        print(
            f"DEFECT {design_id} `{name}`: card says seats={declared}, its own role list "
            f"({roles}) sums to {computed}"
        )

    if failures:
        print()
        for f in failures:
            print(f"  - {f}")
        print(f"FAILED:seat-arithmetic {len(failures)} problem(s)")
        return 1
    print(
        f"SUCCESS:seat-arithmetic {parsed}/{len(SLICE_IDS)} cards parsed; "
        f"{len(mismatches)} mismatch (C-X46: 40 declared vs 43 roles, corroborated by that "
        "card's own note 'measured 43 agents'); 15 cards agree"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
