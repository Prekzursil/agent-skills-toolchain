"""Council-output vs the 12-condition predicate: one row per condition.

can_satisfy means a well-formed council *result envelope* can present the
evidence the shared reducer already knows how to score. cannot means the
council's own internals are the wrong kind of evidence; a council-specific
discharge is required. NOT-APPLICABLE is unused: marking C9/C12 N/A would
let a council complete without independent review or a real consumer.
"""
from __future__ import annotations

from conditions import ANTI_PATTERNS, CONDITIONS, SPEC_CAPTURE, SPEC_LOCUS

QUESTION = (
    "Which of the 12 completion conditions can a council output actually satisfy, "
    "and for each one it cannot (independent reviewer PASS, downstream consumers "
    "can read it), what is the council-specific discharge?"
)

ROWS: list[dict] = [
    {
        "n": 1,
        "spec_verbatim": CONDITIONS[0][1],
        "spec_cite": f"{SPEC_LOCUS} condition 1",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "Council-as-workflow (CNL-0124) records envelope.state. SUCCESS is "
            "the only completion terminal. BLOCKED/FAILED/TIMEOUT/SEVERED are "
            "terminal but not complete. Process exit 0 with state missing or "
            "RUNNING does not satisfy C1."
        ),
        "discharge": (
            "Same reducer as every other unit: state in {SUCCESS} SATISFIES; "
            "other terminals UNSATISFY C1 rather than converting to PASS."
        ),
    },
    {
        "n": 2,
        "spec_verbatim": CONDITIONS[1][1],
        "spec_cite": f"{SPEC_LOCUS} condition 2",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "The council result file must exist on disk at output_path. A path "
            "printed in the transcript is not existence (anti-pattern 3)."
        ),
        "discharge": "stat the declared path; missing file => C2 UNSATISFIED.",
    },
    {
        "n": 3,
        "spec_verbatim": CONDITIONS[2][1],
        "spec_cite": f"{SPEC_LOCUS} condition 3",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "Council JSON must exceed a meaningful floor (128 B here) and the "
            "declared byte count must match bytes on disk."
        ),
        "discharge": "re-measure bytes; empty or undersize => C3 UNSATISFIED.",
    },
    {
        "n": 4,
        "spec_verbatim": CONDITIONS[3][1],
        "spec_cite": f"{SPEC_LOCUS} condition 4",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "Council result must parse as JSON against the declared council "
            "result / design-note schema. Markdown-only transcript fails C4."
        ),
        "discharge": "json.loads + schema validate; parse error => C4 UNSATISFIED.",
    },
    {
        "n": 5,
        "spec_verbatim": CONDITIONS[4][1],
        "spec_cite": f"{SPEC_LOCUS} condition 5",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "The catalog sentinel (SUCCESS:<id> or the council unit sentinel) "
            "must be present in the result. Missing sentinel MUST fail even "
            "when exit_code is 0 — that is the live-wiring proof."
        ),
        "discharge": (
            "Strip sentinel, keep exit 0 / existing file / schema-valid: "
            "predicate.complete must be false with C5 UNSATISFIED."
        ),
    },
    {
        "n": 6,
        "spec_verbatim": CONDITIONS[5][1],
        "spec_cite": f"{SPEC_LOCUS} condition 6",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "CNL-0075 lineage: idea -> option card -> claim -> argument -> "
            "vote -> decision -> action plan. A recommendation with no "
            "anchors fails C6."
        ),
        "discharge": "require >=2 evidence_anchors pointing at ledger ids.",
    },
    {
        "n": 7,
        "spec_verbatim": CONDITIONS[6][1],
        "spec_cite": f"{SPEC_LOCUS} condition 7",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "tests_required on the council *unit* must have run and passed. "
            "Seated votes are not tests. simulate.py exit 0 is not C7."
        ),
        "discharge": "non-empty tests[] all PASS; empty or FAIL => C7 UNSATISFIED.",
    },
    {
        "n": 8,
        "spec_verbatim": CONDITIONS[7][1],
        "spec_cite": f"{SPEC_LOCUS} condition 8",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "Council anti-failure controls must FIRE on a planted-bad fixture "
            "and stay SILENT on known-good. A control that is always-red or "
            "always-green measures nothing."
        ),
        "discharge": "at least one control with fired_on_bad and silent_on_good.",
    },
    {
        "n": 9,
        "spec_verbatim": CONDITIONS[8][1],
        "spec_cite": f"{SPEC_LOCUS} condition 9",
        "can_satisfy": False,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "A council output cannot satisfy C9 from its own internals. The "
            "council is the producing body. Treating 'the council voted PASS' "
            "as independent review of the council unit is circular (CNL-0026: "
            "judge/juror fusion is the named SPOF). Internal judge/juror "
            "separation is C8-class protocol hygiene, not C9 of the council unit."
        ),
        "discharge": (
            "Council-specific: attach an external_reviewer whose reviewer_id "
            "is not in seated_participants and whose verdict is PASS. When "
            "this council is the review of a *different* unit, its verdict "
            "discharges C9 of that reviewed unit only — never C9 of itself. "
            "Not NOT-APPLICABLE: an N/A here would let a council complete "
            "without independent review."
        ),
    },
    {
        "n": 10,
        "spec_verbatim": CONDITIONS[9][1],
        "spec_cite": f"{SPEC_LOCUS} condition 10",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "Open P0/P1 defects attached to the council run block completion "
            "the same way they block any other unit."
        ),
        "discharge": "zero open P0/P1 on the council run record.",
    },
    {
        "n": 11,
        "spec_verbatim": CONDITIONS[10][1],
        "spec_cite": f"{SPEC_LOCUS} condition 11",
        "can_satisfy": True,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "The council result must be a row in the unit artifact manifest "
            "with sha256 matching bytes on disk. A plausible digest with no "
            "file is not a receipt (anti-pattern 2)."
        ),
        "discharge": "manifest.registered and sha256_matches against disk bytes.",
    },
    {
        "n": 12,
        "spec_verbatim": CONDITIONS[11][1],
        "spec_cite": f"{SPEC_LOCUS} condition 12",
        "can_satisfy": False,
        "applicability": "APPLICABLE",
        "how_or_why_not": (
            "A council output cannot satisfy C12 by 'participants can read "
            "the transcript' or by schema-valid existence. ADV-0001: a "
            "passing-but-unusable artifact is the named attack. Existence "
            "is not readability (CC-0009)."
        ),
        "discharge": (
            "Council-specific: a named downstream consumer — the parent "
            "workflow fan-in / synthesis reader — must open, parse, and "
            "extract sentinel, recommendation, lineage_root, and dissent. "
            "Schema-valid JSON missing a consumer field => C12 UNSATISFIED. "
            "Not NOT-APPLICABLE: N/A would make C12 decorative."
        ),
    },
]


def counts() -> dict:
    if len(ROWS) != 12:
        raise SystemExit(f"table length {len(ROWS)} != 12")
    for i, row in enumerate(ROWS, 1):
        if row["n"] != i:
            raise SystemExit(f"row n drift {row['n']} != {i}")
        if row["spec_verbatim"] != CONDITIONS[i - 1][1]:
            raise SystemExit(f"verbatim drift at C{i}")
        if row["applicability"] == "NOT-APPLICABLE":
            raise SystemExit(f"C{i} marked N/A; this mapping forbids N/A-as-pass")
        if not str(row.get("discharge") or "").strip():
            raise SystemExit(f"C{i} missing discharge")
    can = [r["n"] for r in ROWS if r["can_satisfy"]]
    cannot = [r["n"] for r in ROWS if not r["can_satisfy"]]
    return {
        "n": 12,
        "can_satisfy": can,
        "cannot_satisfy": cannot,
        "n_can": len(can),
        "n_cannot": len(cannot),
        "anti_patterns": ANTI_PATTERNS,
        "spec_locus": SPEC_LOCUS,
        "spec_capture": SPEC_CAPTURE,
        "named_cannot": [9, 12],
    }
