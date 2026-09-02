#!/usr/bin/env python3
"""Write command-center/research/RES-0112.json (research claim record)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/research/RES-0112.json"

SENTINEL = (
    "SUCCESS:RES-0112 in the receipt AND a property gap table citing "
    "existing gates at file:line with at least one already-satisfied row"
)

RECORD = {
    "unit_id": "RES-0112",
    "id": "RES-0112",
    "state": "SUCCESS",
    "status": "DELIVERED",
    "report_kind": "research-claim-record",
    "schema_version": 1,
    "declared_schema": "command-center/schema/research-claim-record.schema.json",
    "schema_on_disk": True,
    "schema_note": (
        "command-center/schema/research-claim-record.schema.json is a generated "
        "shim that $ref's platform/schema/artifact-class-profiles.schema.json"
        "#/$defs/research-claim-record. G-1 does not load it. This record is "
        "still a typed claim file: unit_id, state, sentinel, mechanisms with "
        "DOI+section+effect+baseline, and a property gap table with file:line "
        "cites."
    ),
    "sentinel": SENTINEL,
    "receipt": {
        "unit_id": "RES-0112",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": (
            "What does the safety-critical checklist literature say about WHY "
            "checklists work (killer items, read-do versus do-confirm, pause "
            "points), and which of those properties do this program's gates "
            "currently lack?"
        ),
        "answer": (
            "Checklists work when they (1) isolate killer items so one miss "
            "stops the procedure, (2) pick one method — read-do (do-list) or "
            "do-confirm (challenge-response) — and do not silently mix them, "
            "and (3) halt at named pause points at natural breaks. On this "
            "worktree, G-1 already has (1) and a do-confirm analog; it lacks "
            "named pause points and an explicit read-do versus do-confirm split."
        ),
    },
    "title": "Transfer checklist and crew-resource-management discipline to agent gates",
    "question_or_target": (
        "What does the safety-critical checklist literature say about WHY "
        "checklists work (killer items, read-do versus do-confirm, pause "
        "points), and which of those properties do this program's gates "
        "currently lack?"
    ),
    "fetched_on": "2026-08-25",
    "sources": [
        {
            "id": "Haynes-2009",
            "doi": "10.1056/NEJMsa0810119",
            "title": "A Surgical Safety Checklist to Reduce Morbidity and Mortality in a Global Population",
            "authors": "Haynes AB, Weiser TG, Berry WR, et al.",
            "venue": "N Engl J Med 2009;360:491-499",
            "fetch": "https://www.nejm.org/doi/pdf/10.1056/NEJMsa0810119",
            "evidence_tier": "E1",
        },
        {
            "id": "Arriaga-2013",
            "doi": "10.1056/NEJMsa1204720",
            "title": "Simulation-Based Trial of Surgical-Crisis Checklists",
            "authors": "Arriaga AF, Bader AM, Wong JM, et al.",
            "venue": "N Engl J Med 2013;368:246-253",
            "fetch": "https://doi.org/10.1056/nejmsa1204720",
            "evidence_tier": "E1",
        },
        {
            "id": "Urbach-2014",
            "doi": "10.1056/NEJMsa1308261",
            "title": "Introduction of Surgical Safety Checklists in Ontario, Canada",
            "authors": "Urbach DR, Govindarajan A, Saskin R, Wilton AS, Baxter NN",
            "venue": "N Engl J Med 2014;370:1029-1038",
            "fetch": "https://www.nejm.org/doi/full/10.1056/NEJMsa1308261",
            "evidence_tier": "E1",
            "role": "negative-control / overclaim brake",
        },
        {
            "id": "Degani-Wiener-1990-CR",
            "report": "NASA-CR-177549",
            "title": "Human Factors of Flight-Deck Checklists: The Normal Checklist",
            "authors": "Degani A, Wiener EL",
            "year": 1990,
            "fetch": "https://www.faa.gov/sites/faa.gov/files/2022-11/NASA%20Ames%20Rpt%20CR%20177549%20.pdf",
            "evidence_tier": "E1-for-text-E3-for-promotion",
            "note": "Design distinction and the phrase killer items; no trial effect size vs baseline in this CR.",
        },
        {
            "id": "Degani-Wiener-1993",
            "doi": "10.1177/001872089303500209",
            "title": "Cockpit Checklists: Concepts, Design, and Use",
            "authors": "Degani A, Wiener EL",
            "venue": "Human Factors 1993;35(2):345-359",
            "evidence_tier": "E2",
            "note": "Journal form of the NASA CR field study. Still no RCT effect size for killer-item placement.",
        },
    ],
    "mechanisms": [
        {
            "id": "M-pause-points",
            "name": "Named pause points at natural workflow breaks",
            "promoted": True,
            "evidence_tier": "E1",
            "why_checklists_work": (
                "Haynes implements the 19-item WHO list at three critical "
                "junctures, forcing a spoken halt before anaesthesia, before "
                "incision, and before leaving the room. That is the pause-point "
                "property, not a longer to-do list."
            ),
            "doi": "10.1056/NEJMsa0810119",
            "section_or_figure": (
                "Intervention: 'three critical junctures in care: before "
                "anesthesia is administered, immediately before incision, and "
                "before the patient is taken out of the operating room'; "
                "Results / Table 5"
            ),
            "baseline": (
                "3733 patients before the checklist: in-hospital death 1.5%; "
                "any complication 11.0% (Table 5 totals)"
            ),
            "effect_size": (
                "3955 patients after: death 0.8% (P=0.003 vs 1.5% baseline); "
                "any complication 7.0% (P<0.001 vs 11.0% baseline)"
            ),
            "strongest_caveat": (
                "Before-after, not a randomized trial. Haynes Discussion treats "
                "the mechanism as multifactorial (antibiotics, pulse oximetry, "
                "team brief). Pause points are what the intervention installed; "
                "they are not isolated as the proven causal kernel of the 1.5% "
                "to 0.8% drop. Urbach 2014 (doi:10.1056/NEJMsa1308261, Abstract) "
                "measured a mandated checklist at population scale: adjusted "
                "death 0.71% (95% CI 0.66-0.76) before vs 0.65% (0.60-0.70) "
                "after, OR 0.91 (0.80-1.03), P=0.13 — a headline 'checklists "
                "cut deaths' without that baseline is E3 and cannot promote."
            ),
        },
        {
            "id": "M-read-do-crisis",
            "name": "Read-do (do-list) for time-critical abnormal work",
            "promoted": True,
            "evidence_tier": "E1",
            "why_checklists_work": (
                "Crisis checklists lead the operator through steps during the "
                "event (call-do-response / read-do), rather than verifying a "
                "configuration already done from memory. That is Degani's "
                "do-list method, tested as a crisis aid."
            ),
            "doi": "10.1056/NEJMsa1204720",
            "section_or_figure": "Results; Figure 1",
            "baseline": (
                "Without checklist (memory only): 89 of 379 critical steps "
                "missed (23%)"
            ),
            "effect_size": (
                "With crisis checklists available: 24 of 371 steps missed (6%), "
                "P<0.001 vs 23% baseline; adjusted RR 0.28 (95% CI 0.18-0.42)"
            ),
            "strongest_caveat": (
                "High-fidelity simulation, not live operating-room mortality. "
                "Does not show that read-do reduces deaths; it shows missed "
                "critical steps fall from 23% to 6% when the list is in hand "
                "during the crisis."
            ),
        },
        {
            "id": "M-do-confirm",
            "name": "Do-confirm / challenge-response for normal work",
            "promoted": False,
            "evidence_tier": "E3",
            "cannot_promote_reason": (
                "Degani & Wiener NASA-CR-177549 §3.1.4 distinguishes "
                "challenge-response (verify after configuring from memory) from "
                "do-list (the list leads the action). No trial in the fetched "
                "CR or 1993 Human Factors paper reports an effect size against "
                "a baseline for choosing one method over the other. A headline "
                "without baseline is E3 and cannot promote this mechanism. "
                "The local G-1 live probe re-run is still measured as a "
                "do-confirm analog in the gap table."
            ),
            "doi": "10.1177/001872089303500209",
            "report": "NASA-CR-177549",
            "section_or_figure": "NASA-CR-177549 §3.1.4 The Method (challenge-response vs do-list)",
            "baseline": None,
            "effect_size": None,
            "strongest_caveat": "Design distinction only; not promoted.",
        },
        {
            "id": "M-killer-items",
            "name": "Killer items as independently fatal, listed first",
            "promoted": False,
            "evidence_tier": "E3",
            "cannot_promote_reason": (
                "NASA-CR-177549 §3.1.6 uses the crews' phrase 'killer items' "
                "for the subset operators will still run when they shed a long "
                "list; guideline (10) says put the most critical items at the "
                "start of the task-checklist; guideline (15) says inspectors "
                "must not compromise on critical killer items. No effect size "
                "versus a baseline is reported. Cannot promote."
            ),
            "doi": "10.1177/001872089303500209",
            "report": "NASA-CR-177549",
            "section_or_figure": (
                "NASA-CR-177549 §3.1.6 ('killer items'); Design guideline (10) "
                "critical items at the beginning; guideline (15) no compromise "
                "on critical killer items"
            ),
            "baseline": None,
            "effect_size": None,
            "strongest_caveat": "Guideline, not a measured effect. Not promoted.",
        },
    ],
    "e3_headlines_rejected": [
        {
            "headline": "Checklists cut surgical deaths by 47%",
            "missing": "baseline 1.5% death (Haynes Table 5) omitted",
            "evidence_tier": "E3",
            "promoted": False,
        },
        {
            "headline": "Crisis checklists reduce missed steps 75%",
            "missing": "baseline 23% missed steps (89/379) omitted",
            "evidence_tier": "E3",
            "promoted": False,
        },
    ],
    "property_gap_table": [
        {
            "property_id": "killer-items",
            "literature_name": "killer items",
            "literature_source": "NASA-CR-177549 §3.1.6; guideline (10), (15)",
            "status": "already-satisfied",
            "control_row": True,
            "program_reading": (
                "G-1 and ready_units treat self-declared BLOCKED/FAILED/"
                "SEVERED/TIMEOUT as a single item that independently fails "
                "the whole check, regardless of other greens. That is the "
                "killer-item analog: one miss stops the procedure."
            ),
            "gate_citations": [
                {
                    "path": "command-center/p2-wave/_measure_one_delivered.py",
                    "line": 23,
                    "snippet": 'NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})',
                },
                {
                    "path": "command-center/p2-wave/_measure_one_delivered.py",
                    "line": 133,
                    "snippet": "if st in NOT_DELIVERING:",
                },
                {
                    "path": "command-center/p2-wave/_measure_one_delivered.py",
                    "line": 134,
                    "snippet": 'return fail(uid, f"self-declared:{st}")',
                },
                {
                    "path": "command-center/ready_units.py",
                    "line": 44,
                    "snippet": 'NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})',
                },
                {
                    "path": "command-center/ready_units.py",
                    "line": 376,
                    "snippet": "if isinstance(st, str) and st.upper() in NOT_DELIVERING:",
                },
                {
                    "path": "command-center/ready_units.py",
                    "line": 377,
                    "snippet": 'return False, f"self-declared:{st.upper()}"',
                },
            ],
        },
        {
            "property_id": "do-confirm",
            "literature_name": "do-confirm / challenge-response",
            "literature_source": "NASA-CR-177549 §3.1.4 challenge-response",
            "status": "already-satisfied",
            "control_row": True,
            "program_reading": (
                "G-1 re-runs named probes live (run_cmd) instead of trusting "
                "exit codes stored in the receipt. Claimed delivery is "
                "challenged and independently confirmed. That is do-confirm."
            ),
            "gate_citations": [
                {
                    "path": "command-center/p2-wave/_measure_one_delivered.py",
                    "line": 90,
                    "snippet": "def run_cmd(cmd: str) -> tuple[int, str]:",
                },
                {
                    "path": "command-center/p2-wave/_measure_one_delivered.py",
                    "line": 151,
                    "snippet": "for i, cmd in enumerate(cmds, 1):",
                },
                {
                    "path": "command-center/p2-wave/_measure_one_delivered.py",
                    "line": 152,
                    "snippet": "code, tail = run_cmd(cmd)",
                },
            ],
        },
        {
            "property_id": "pause-points",
            "literature_name": "pause points",
            "literature_source": (
                "Haynes 2009 Intervention: three critical junctures in care"
            ),
            "status": "absent",
            "control_row": False,
            "program_reading": (
                "G-1 main() is one linear pass: parse artifact, re-run probes, "
                "check manifest digest. There is no named halt at a workflow "
                "break (no Sign-In / Time-Out / Sign-Out analog) between those "
                "stages. Absence is read from the gate file, not assumed."
            ),
            "gate_citations": [
                {
                    "path": "command-center/p2-wave/_measure_one_delivered.py",
                    "line": 109,
                    "end_line": 181,
                    "snippet": "def main() -> int:",
                    "absence_check": "no_named_pause_in_range",
                },
                {
                    "path": "command-center/p2-wave/_measure_one_delivered.py",
                    "line": 151,
                    "end_line": 178,
                    "snippet": "for i, cmd in enumerate(cmds, 1):",
                    "absence_check": "probes_then_manifest_same_function",
                },
            ],
            "contrast_not_this_gate": {
                "path": "tools/marketplace/revocation_list/install_gate.py",
                "line": 7,
                "snippet": "on ``REFUSE`` places **nothing** - not even the package directory",
                "note": (
                    "The install-time revocation gate (IMP-0079) does refuse "
                    "before any payload write. That is one "
                    "pause-before-irreversible-action on package install, not a "
                    "Haynes pause-point set on the unit-delivery gate. "
                    "tools/plugin/install_gate.py (IMP-0008) is not on this tree, "
                    "so the contrast cites the gate that is."
                ),
            },
        },
        {
            "property_id": "read-do-versus-do-confirm",
            "literature_name": "read-do versus do-confirm",
            "literature_source": "NASA-CR-177549 §3.1.4; Arriaga 2013 crisis do-list",
            "status": "absent",
            "control_row": False,
            "program_reading": (
                "G-1 has a single undifferentiated live-exec path. The source "
                "does not name read-do vs do-confirm, does not label items as "
                "do-list vs challenge-response, and has no separate crisis "
                "read-do checklist. Degani: mixing methods without naming them "
                "is the operational failure mode."
            ),
            "gate_citations": [
                {
                    "path": "command-center/p2-wave/_measure_one_delivered.py",
                    "line": 90,
                    "end_line": 158,
                    "snippet": "def run_cmd(cmd: str) -> tuple[int, str]:",
                    "absence_check": "no_method_split_named",
                }
            ],
        },
    ],
    "already_satisfied_count": 2,
    "absent_count": 2,
    "tests_required": [
        {
            "id": "cite-file-line-when-absent",
            "requirement": "cite this program's gates at file:line when claiming a property is absent",
            "how_met": "pause-points and read-do-versus-do-confirm rows cite _measure_one_delivered.py line ranges; probes re-open those lines.",
        },
        {
            "id": "control-already-satisfied",
            "requirement": "control: identify at least one property the existing gates already have",
            "how_met": "killer-items and do-confirm rows are status=already-satisfied with live snippets.",
        },
    ],
    "reviewer": {
        "reviewer_id": "RES-0112-adversarial-refuter",
        "independent": True,
        "fresh_context": True,
        "default_when_insufficient": "REFUTED",
        "verdict": "PASS-WITH-CAVEATS",
        "refuted_promotions": [
            "M-do-confirm as a literature mechanism (E3, no effect+baseline)",
            "M-killer-items as a literature mechanism (E3, no effect+baseline)",
            "Haynes 47% relative death reduction stated without 1.5% baseline (E3)",
        ],
        "surviving_claims_strongest_caveat": (
            "Pause points and read-do crisis lists are evidenced as installed "
            "properties with effect+baseline (Haynes Table 5; Arriaga Figure 1). "
            "They are not proven, in isolation, to be why any specific death "
            "was avoided. G-1 already implements killer-item and do-confirm "
            "analogs; it lacks named pause points and a named method split. "
            "Urbach 2014 is the overclaim brake: a checklist mandate can move "
            "death from 0.71% to 0.65% and not be significant."
        ),
    },
    "residual_unknowns": [
        "The catalog schema shim does not model property_gap_table; G-1 probes enforce that shape instead of jsonschema.",
        "RES-0108 (declared dependency) is not delivered here; this unit measures gates and literature, not the gem rubric.",
    ],
}


def find_line(rel: str, snippet: str) -> int:
    fp = REPO / rel
    if not fp.is_file():
        raise SystemExit(f"FAILED:emit missing {rel}")
    text = fp.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:emit snippet missing in {rel}: {snippet[:80]!r}")
    return text[:idx].count("\n") + 1


def bind_live_lines(record: dict) -> None:
    """Re-anchor every in-tree gate citation to the line its snippet lives on now.

    The gate files are live code (``_measure_one_delivered.py`` moved on 02.09),
    so a hard-coded ``line`` rots; the snippet is the stable identity. A window
    (``end_line``) keeps its span so a def-block citation still covers the body.
    """
    for row in record.get("property_gap_table") or []:
        for cite in row.get("gate_citations") or []:
            rel = str(cite.get("path") or "")
            snip = str(cite.get("snippet") or "")
            if not rel or not snip or rel.startswith(("http://", "https://")):
                continue
            old = cite.get("line")
            new = find_line(rel, snip)
            end = cite.get("end_line")
            if isinstance(end, int) and isinstance(old, int) and end >= old:
                cite["end_line"] = new + (end - old)
            cite["line"] = new
        contrast = row.get("contrast_not_this_gate")
        if isinstance(contrast, dict) and contrast.get("path") and contrast.get("snippet"):
            contrast["line"] = find_line(str(contrast["path"]), str(contrast["snippet"]))


def main() -> int:
    bind_live_lines(RECORD)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(RECORD, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
