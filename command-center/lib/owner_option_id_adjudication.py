#!/usr/bin/env python3
"""CC-0023 owner adjudication for algorithmically unresolvable M-NN refs.

Honesty rules (load-bearing):
  * Never invent an owner answer or timestamp.
  * Inferred / majority / most-likely / LLM classification is NOT evidence.
  * Unanswered refs MUST end as DEFERRED with an impact statement.
  * Do not silently rewrite ambiguous M-NN tokens in source docs.

Linux Cloud / single-checkout: Prompt-One Windows trees and _optid_* intermediates
are unmounted. The 58 refs are enumerated from OPTION-ID-RESOLUTION census
buckets (counts CONFIRMED); per-token line IDs are not fabricated.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

CENSUS_PATH = REPO / "command-center/option-id/CC-0023-UNRESOLVED-REFS.json"
LEDGER_PATH = REPO / "command-center/option-id/OWNER-ADJUDICATION-LEDGER.json"
PACKET_PATH = REPO / "command-center/option-id/OWNER-ADJUDICATION-PACKET.md"
OWNER_DECISIONS = REPO / "command-center/OWNER-DECISIONS.md"
OWNER_QUESTION_PACKET = REPO / "command-center/OWNER-QUESTION-PACKET.md"
RESOLUTION_JSON = REPO / "command-center/OPTION-ID-RESOLUTION.json"

CC23_SECTION_MARKER = "## CC-0023 — option-id namespace adjudication (58 refs)"

# Foundation questions that batch the 58 refs (~7 ref-bearing + 5 session policies).
QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "OQ-CC23-01",
        "title": "Leave F-B-02 mention tokens in 17-DECISION-LOG.md untouched?",
        "covers_buckets": ["doc17-mentions"],
        "recommendation": (
            "(a) Leave all 10 mention tokens verbatim; append-only REMEDIATED row "
            "(already done by CC-0022 for tense/namespace). Never blind-rewrite."
        ),
        "strongest_tradeoff": (
            "Rewriting mention tokens destroys the historical evidence of the "
            "collision claim itself."
        ),
        "default_if_unanswered": "DEFERRED: leave mentions untouched; no rewrite.",
        "impact_if_deferred": (
            "10 mention tokens stay ambiguous-looking to naive greps; CC-0021 "
            "use-vs-mention gate already excludes 17-DECISION-LOG paths."
        ),
    },
    {
        "id": "OQ-CC23-02",
        "title": "How should the 16 unsettled refs in 16-GRILL-QUEUE-PHASE2.md resolve?",
        "covers_buckets": ["doc16-unsettled"],
        "recommendation": (
            "(b) Author of doc 16 maps each operational cite to option-universe-M "
            "or architecture-mech; finding-write-up mentions stay as mentions."
        ),
        "strongest_tradeoff": (
            "Batching saves owner time but a wrong namespace on an operational "
            "cite is silent data loss (LLM classifier: 86% accurate, 100% of "
            "errors = data loss)."
        ),
        "default_if_unanswered": "DEFERRED: no rewrite of any doc-16 M-NN token.",
        "impact_if_deferred": (
            "16 refs remain algorithmically unresolved; downstream rewrite "
            "lanes must not touch doc 16."
        ),
    },
    {
        "id": "OQ-CC23-03",
        "title": "Which namespace do the 11 unsettled BLOCKS: fields in doc 18 mean?",
        "covers_buckets": ["doc18-blocks-unsettled"],
        "recommendation": (
            "(b) Author of 18-OPEN-UNKNOWNS-AND-PROBES.md answers one BLOCKS: "
            "field at a time; do not infer from adjacent settled MECH-16/17."
        ),
        "strongest_tradeoff": (
            "Adjacency inference (M-16 settled MECH ⇒ nearby M-18 is MECH-18) "
            "is exactly the near-collision trap called out in OPTION-ID-RESOLUTION §7c."
        ),
        "default_if_unanswered": "DEFERRED: BLOCKS: fields stay bare M-NN.",
        "impact_if_deferred": (
            "11 blocker edges stay namespace-ambiguous; executors must not "
            "treat them as selected option IDs or MECH IDs."
        ),
    },
    {
        "id": "OQ-CC23-04",
        "title": "Which namespace for the 5 unsettled refs in 19-SUBSTANCE-AUDIT-OPTIONS.md?",
        "covers_buckets": ["doc19-unsettled"],
        "recommendation": (
            "(b) Author of doc 19 maps each unsettled cite; apply only after "
            "timestamped answer."
        ),
        "strongest_tradeoff": (
            "Substance-audit prose mixes option and mechanism vocabulary; a "
            "wrong rewrite flips audit conclusions."
        ),
        "default_if_unanswered": "DEFERRED: no rewrite in doc 19 unsettled cites.",
        "impact_if_deferred": (
            "5 refs stay unresolved; substance-audit consumers must treat bare "
            "M-NN as ambiguous."
        ),
    },
    {
        "id": "OQ-CC23-05",
        "title": "Resolve the 2 unsettled refs in diagrams/07-option-dependency-map.md?",
        "covers_buckets": ["diagrams-unsettled"],
        "recommendation": "(a) Prefer option-universe-M when the diagram edge is an option dependency.",
        "strongest_tradeoff": "Diagram edges look option-like but may cite mechanisms.",
        "default_if_unanswered": "DEFERRED: diagram tokens unchanged.",
        "impact_if_deferred": "2 diagram refs remain ambiguous.",
    },
    {
        "id": "OQ-CC23-06",
        "title": "Are wave1 REGISTER.md M-1/M-3 a fourth namespace (mission grades)?",
        "covers_buckets": ["wave1-mission-grades"],
        "recommendation": (
            "(a) Yes — declare MG-1/MG-3 (or keep single-digit M-N as mission "
            "grades) distinct from family-M and MECH-."
        ),
        "strongest_tradeoff": (
            "Collapsing mission grades into family-M invents option cards that "
            "do not exist."
        ),
        "default_if_unanswered": "DEFERRED: leave M-1/M-3; do not rewrite to M-01/MECH-01.",
        "impact_if_deferred": (
            "Fourth namespace stays undeclared in live prose; CC-0021 registry "
            "already declares MG-N provisionally from census."
        ),
    },
    {
        "id": "OQ-CC23-07",
        "title": "Confirm scratch _sa_*/_verify_*/_p1floor_* refs are out of scope?",
        "covers_buckets": ["scratch-tooling"],
        "recommendation": "(a) Out of scope — do not adjudicate scratch tooling tokens.",
        "strongest_tradeoff": "Ignoring scratch refs risks a later false 'fully resolved' claim.",
        "default_if_unanswered": "DEFERRED: scratch tooling remains out of rewrite scope.",
        "impact_if_deferred": "12 scratch refs stay unresolved and explicitly non-blocking.",
    },
    {
        "id": "OQ-CC23-08",
        "title": "Standing rule for the M-18 near-collision (benchmark vs certification)?",
        "covers_buckets": [],
        "recommendation": (
            "(c) Never auto-resolve M-18; require an explicit author answer naming "
            "option M-18 (benchmark harness) or MECH-18 (certification harness)."
        ),
        "strongest_tradeoff": (
            "Both readings are plausible in almost any sentence — mis-resolution "
            "produces no visible error."
        ),
        "default_if_unanswered": "DEFERRED: M-18 stays unresolved wherever bare.",
        "impact_if_deferred": "Near-collision remains the highest-risk ambiguous token.",
    },
    {
        "id": "OQ-CC23-09",
        "title": "Default when the owner never answers a foundation question?",
        "covers_buckets": [],
        "recommendation": (
            "(a) Record DEFERRED + impact; continue independent work; never LLM-guess."
        ),
        "strongest_tradeoff": "Deferred ambiguity slows executors vs inventing a wrong namespace.",
        "default_if_unanswered": "DEFERRED applies to every unanswered ref (this question's own default).",
        "impact_if_deferred": "All unanswered refs stay DEFERRED — the honest blocked state.",
    },
    {
        "id": "OQ-CC23-10",
        "title": "Ban LLM / majority / most-likely classification as settlement evidence?",
        "covers_buckets": [],
        "recommendation": "(a) Ban. Only timestamped owner/author answers count.",
        "strongest_tradeoff": "Slower closure vs measured 86%-accurate classifier with 100% lossful errors.",
        "default_if_unanswered": "Ban stands (catalog evidence_requirement).",
        "impact_if_deferred": "No classifier settlement path; packet stays owner-gated.",
    },
    {
        "id": "OQ-CC23-11",
        "title": "Authorize any silent rewrite of ambiguous M-NN tokens without an answer?",
        "covers_buckets": [],
        "recommendation": "(a) No. Zero unattributed id changes.",
        "strongest_tradeoff": "Cleaner docs vs irreversible namespace corruption.",
        "default_if_unanswered": "No silent rewrites authorized.",
        "impact_if_deferred": "Source docs 16/18/19 keep bare tokens until answered.",
    },
    {
        "id": "OQ-CC23-12",
        "title": "Where must every recorded answer be durable?",
        "covers_buckets": [],
        "recommendation": (
            "(a) OWNER-DECISIONS.md CC-0023 section + option-id/OWNER-ADJUDICATION-LEDGER.json."
        ),
        "strongest_tradeoff": "Dual write vs single generated OWNER-DECISIONS overwrite risk.",
        "default_if_unanswered": "Ledger + OWNER-DECISIONS section remain the durability targets.",
        "impact_if_deferred": "Durability paths stay declared; answers still absent.",
    },
]


@dataclass
class ControlResult:
    name: str
    passed: bool
    detail: dict[str, Any]


def load_census(path: Path | None = None) -> dict[str, Any]:
    p = path or CENSUS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def load_ledger(path: Path | None = None) -> dict[str, Any]:
    p = path or LEDGER_PATH
    if not p.is_file():
        return {
            "schema_version": 1,
            "unit": "CC-0023",
            "answers": {},
            "ref_states": {},
            "recorded_owner_answers": [],
        }
    return json.loads(p.read_text(encoding="utf-8"))


def census_arithmetic_ok(census: dict[str, Any] | None = None) -> ControlResult:
    c = census or load_census()
    bucket_sum = sum(b["count"] for b in c["buckets"])
    n_refs = len(c["refs"])
    ok = (
        bucket_sum == 58
        and n_refs == 58
        and c.get("requires_author_adjudication") == 58
        and {r["ref_id"] for r in c["refs"]} == {f"REF-{i:03d}" for i in range(1, 59)}
    )
    # Cross-check published resolution totals when present.
    res_ok = True
    res_detail: dict[str, Any] = {}
    if RESOLUTION_JSON.is_file():
        res = json.loads(RESOLUTION_JSON.read_text(encoding="utf-8"))
        totals = res.get("10_rewrite_cost_if_proposal_applied", {}).get("totals", {})
        res_detail = totals
        res_ok = totals.get("requires_author_adjudication") == 58
        ok = ok and res_ok
    return ControlResult(
        "census-arithmetic-58",
        ok,
        {
            "bucket_sum": bucket_sum,
            "n_refs": n_refs,
            "resolution_totals": res_detail,
        },
    )


def grouping_control(census: dict[str, Any] | None = None) -> ControlResult:
    """Refs that share a bucket share one question; question count << 58."""
    c = census or load_census()
    q_for_ref = {r["ref_id"]: r["question_id"] for r in c["refs"]}
    questions_used = sorted(set(q_for_ref.values()))
    # Every ref maps to a declared question.
    declared = {q["id"] for q in QUESTIONS}
    mapped_ok = set(questions_used) <= declared
    # Batching: one question per bucket for ref-bearing questions.
    by_q: dict[str, set[str]] = {}
    for r in c["refs"]:
        by_q.setdefault(r["question_id"], set()).add(r["bucket_id"])
    one_bucket_per_q = all(len(v) == 1 for v in by_q.values())
    n_q = len(QUESTIONS)
    ok = (
        mapped_ok
        and one_bucket_per_q
        and len(c["refs"]) == 58
        and n_q <= 12
        and len(questions_used) < 58
        and len(questions_used) <= 12
    )
    return ControlResult(
        "grouping-shared-decisions-batched",
        ok,
        {
            "n_questions_declared": n_q,
            "n_questions_used_by_refs": len(questions_used),
            "questions_used": questions_used,
            "one_bucket_per_question": one_bucket_per_q,
        },
    )


def apply_owner_silence(
    census: dict[str, Any] | None = None,
    ledger: dict[str, Any] | None = None,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Mark every unanswered ref DEFERRED. Never fabricates owner answers.

    `now` stamps when DEFERRED was *recorded by the implementer*, not an owner
    answer timestamp. Owner answer fields stay null.
    """
    c = census or load_census()
    led = ledger or load_ledger()
    answers = dict(led.get("answers") or {})
    stamp = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    q_by_id = {q["id"]: q for q in QUESTIONS}
    ref_states: dict[str, Any] = {}
    deferred = 0
    answered = 0
    for r in c["refs"]:
        qid = r["question_id"]
        q = q_by_id[qid]
        ans = answers.get(qid)
        if (
            isinstance(ans, dict)
            and ans.get("owner_answer")
            and ans.get("answered_at")
            and ans.get("provenance") == "owner"
        ):
            # Only accept explicitly provenance=owner answers with timestamps.
            ref_states[r["ref_id"]] = {
                "state": "OWNER_ANSWERED",
                "question_id": qid,
                "owner_answer": ans["owner_answer"],
                "answered_at": ans["answered_at"],
                "provenance": "owner",
            }
            answered += 1
        else:
            ref_states[r["ref_id"]] = {
                "state": "DEFERRED",
                "question_id": qid,
                "owner_answer": None,
                "answered_at": None,
                "deferred_recorded_at": stamp,
                "impact": q["impact_if_deferred"],
                "default_if_unanswered": q["default_if_unanswered"],
                "provenance": "implementer-deferred-no-owner-session",
            }
            deferred += 1
    out = {
        "schema_version": 1,
        "unit": "CC-0023",
        "updated_at": stamp,
        "answers": answers,
        "ref_states": ref_states,
        "counts": {
            "total_refs": 58,
            "deferred": deferred,
            "owner_answered": answered,
        },
        "recorded_owner_answers": [
            {
                "question_id": qid,
                "owner_answer": a["owner_answer"],
                "answered_at": a["answered_at"],
            }
            for qid, a in answers.items()
            if isinstance(a, dict)
            and a.get("provenance") == "owner"
            and a.get("owner_answer")
            and a.get("answered_at")
        ],
        "honesty": {
            "invented_owner_answers": False,
            "llm_classification_used": False,
            "silent_rewrites_authorized": False,
        },
    }
    return out


def deferred_coverage_control(ledger: dict[str, Any] | None = None) -> ControlResult:
    led = ledger or load_ledger()
    states = led.get("ref_states") or {}
    if len(states) != 58:
        return ControlResult(
            "deferred-or-answered-coverage",
            False,
            {"n_states": len(states), "expected": 58},
        )
    bad = []
    for rid, st in states.items():
        if st.get("state") == "OWNER_ANSWERED":
            if not st.get("owner_answer") or not st.get("answered_at"):
                bad.append(rid)
        elif st.get("state") == "DEFERRED":
            if not st.get("impact"):
                bad.append(rid)
        else:
            bad.append(rid)
    return ControlResult(
        "deferred-or-answered-coverage",
        len(bad) == 0,
        {
            "deferred": sum(1 for s in states.values() if s["state"] == "DEFERRED"),
            "owner_answered": sum(
                1 for s in states.values() if s["state"] == "OWNER_ANSWERED"
            ),
            "bad": bad,
        },
    )


def silent_rewrite_control(
    *,
    before_text: str,
    after_text: str,
    attributed_spans: list[tuple[str, str]] | None = None,
) -> ControlResult:
    """Diff control: bare M-NN token changes must be attributed to an owner answer.

    attributed_spans: list of (old_token, new_token) pairs authorized by owner.
    """
    bare = re.compile(r"(?<![A-Za-z0-9_-])M-(\d{1,3})(?![0-9A-Za-z])")
    before_ids = bare.findall(before_text)
    after_ids = bare.findall(after_text)
    # Also detect MECH- insertions that replace bare M-
    mech = re.compile(r"MECH-(\d{1,3})")
    before_mech = set(mech.findall(before_text))
    after_mech = set(mech.findall(after_text))
    new_mech = after_mech - before_mech

    attributed = {(a, b) for a, b in (attributed_spans or [])}
    unattributed: list[str] = []

    # Token multiset change on bare M-
    if before_ids != after_ids:
        # Allow only if every removed bare id has an attributed rewrite.
        from collections import Counter

        b, a = Counter(before_ids), Counter(after_ids)
        removed = list((b - a).elements())
        for num in removed:
            old = f"M-{int(num):02d}" if len(num) <= 2 else f"M-{num}"
            # normalize: census uses unpadded sometimes; accept both
            candidates = [f"M-{num}", f"M-{int(num):02d}", f"MECH-{num}", f"MECH-{int(num):02d}"]
            ok_one = any((f"M-{num}", c) in attributed or (old, c) in attributed for c in candidates)
            if not ok_one:
                unattributed.append(f"removed-bare-M-{num}")

    for num in sorted(new_mech):
        # New MECH without attributed pair is unattributed if bare count also dropped.
        pair_ok = any(
            (f"M-{num}", f"MECH-{num}") in attributed
            or (f"M-{int(num):02d}", f"MECH-{int(num):02d}") in attributed
            for _ in [0]
        )
        if not pair_ok and before_ids != after_ids:
            # only flag if bare side changed
            if num in before_ids or f"{int(num)}" in before_ids:
                if f"removed-bare-M-{num}" not in unattributed:
                    unattributed.append(f"new-MECH-{num}-unattributed")

    # Strict: any bare-token sequence change with empty attribution fails.
    if before_ids != after_ids and not attributed:
        unattributed.append("bare-token-sequence-changed-without-attribution")

    ok = len(unattributed) == 0
    return ControlResult(
        "zero-silent-rewrites",
        ok,
        {
            "before_bare": before_ids,
            "after_bare": after_ids,
            "unattributed": unattributed,
        },
    )


_ANSWER_LINE_RE = re.compile(
    r"^\| (?P<qid>OQ-CC23-\d{2}) \| (?P<state>DEFERRED|OWNER_ANSWERED|OPEN) \| "
    r"(?P<answer>[^|]*) \| (?P<at>[^|]*) \|",
    re.MULTILINE,
)


def render_owner_decisions_section(ledger: dict[str, Any]) -> str:
    """Markdown section appended/replaced in OWNER-DECISIONS.md."""
    lines = [
        CC23_SECTION_MARKER,
        "",
        "Durable record for the 58 algorithmically unresolvable option-id references",
        "(CC-0023). **Only rows with state=OWNER_ANSWERED and a non-empty timestamp",
        "are owner evidence.** DEFERRED rows are implementer recordings of silence —",
        "not invented answers.",
        "",
        f"Machine ledger: `{LEDGER_PATH.relative_to(REPO).as_posix()}`",
        f"Question packet: `{PACKET_PATH.relative_to(REPO).as_posix()}`",
        f"Census: `{CENSUS_PATH.relative_to(REPO).as_posix()}`",
        "",
        "| question | state | answer | answered_at |",
        "|---|---|---|---|",
    ]
    ref_states = ledger.get("ref_states") or {}
    # Aggregate by question.
    for q in QUESTIONS:
        qid = q["id"]
        ans = (ledger.get("answers") or {}).get(qid)
        if (
            isinstance(ans, dict)
            and ans.get("provenance") == "owner"
            and ans.get("owner_answer")
            and ans.get("answered_at")
        ):
            state = "OWNER_ANSWERED"
            answer = str(ans["owner_answer"]).replace("|", "/")
            at = str(ans["answered_at"])
        else:
            # If any covered ref is DEFERRED, question is DEFERRED.
            covered = [
                s
                for s in ref_states.values()
                if s.get("question_id") == qid
            ]
            if covered and all(s.get("state") == "OWNER_ANSWERED" for s in covered):
                state = "OWNER_ANSWERED"
                answer = "(see ledger)"
                at = covered[0].get("answered_at") or "—"
            else:
                state = "DEFERRED"
                answer = q["default_if_unanswered"].replace("|", "/")
                at = "—"
        lines.append(f"| {qid} | {state} | {answer} | {at} |")
    lines.extend(
        [
            "",
            "### Recorded owner answers (re-read target)",
            "",
        ]
    )
    recorded = ledger.get("recorded_owner_answers") or []
    if not recorded:
        lines.append(
            "_None. Owner session unavailable on Linux Cloud; zero invented answers._"
        )
    else:
        for row in recorded:
            lines.append(
                f"- **{row['question_id']}** ({row['answered_at']}): {row['owner_answer']}"
            )
    lines.append("")
    return "\n".join(lines)


def upsert_owner_decisions_section(ledger: dict[str, Any], path: Path | None = None) -> str:
    target = path or OWNER_DECISIONS
    section = render_owner_decisions_section(ledger)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    if CC23_SECTION_MARKER in existing:
        pre, _rest = existing.split(CC23_SECTION_MARKER, 1)
        # Drop old section through EOF (CC-0023 section is terminal append).
        new_text = pre.rstrip() + "\n\n" + section
    else:
        new_text = existing.rstrip() + "\n\n" + section
    target.write_text(new_text, encoding="utf-8")
    return section


def durability_roundtrip(
    ledger: dict[str, Any] | None = None,
    decisions_path: Path | None = None,
) -> ControlResult:
    """Re-read OWNER-DECISIONS.md and recover every recorded owner answer."""
    led = ledger or load_ledger()
    path = decisions_path or OWNER_DECISIONS
    text = path.read_text(encoding="utf-8")
    if CC23_SECTION_MARKER not in text:
        return ControlResult(
            "durability-owner-decisions-roundtrip",
            False,
            {"error": "CC-0023 section missing"},
        )
    found = {
        m.group("qid"): {
            "state": m.group("state").strip(),
            "answer": m.group("answer").strip(),
            "answered_at": m.group("at").strip(),
        }
        for m in _ANSWER_LINE_RE.finditer(text)
    }
    expected = led.get("recorded_owner_answers") or []
    missing = []
    for row in expected:
        qid = row["question_id"]
        got = found.get(qid)
        if not got or got["state"] != "OWNER_ANSWERED":
            missing.append(qid)
            continue
        if row["owner_answer"] not in got["answer"] and got["answer"] != row["owner_answer"]:
            # allow truncated table cells
            if row["answered_at"] not in got["answered_at"]:
                missing.append(qid)
    # Also: every DEFERRED question row must be present when no owner answers.
    deferred_qs = [
        q["id"]
        for q in QUESTIONS
        if not any(
            a.get("question_id") == q["id"] for a in expected
        )
    ]
    missing_deferred = [qid for qid in deferred_qs if qid not in found]
    ok = len(missing) == 0 and len(missing_deferred) == 0 and len(found) == len(QUESTIONS)
    return ControlResult(
        "durability-owner-decisions-roundtrip",
        ok,
        {
            "found_questions": sorted(found),
            "expected_owner_answers": len(expected),
            "missing_owner_rows": missing,
            "missing_deferred_rows": missing_deferred,
        },
    )


def render_packet() -> str:
    parts = [
        "# OWNER-ADJUDICATION-PACKET — CC-0023",
        "",
        "**Built for CC-0023** · 58 algorithmically unresolvable option-id references",
        "batched into 12 foundation questions (7 ref-bearing + 5 session policies).",
        "",
        "Rules (from catalog + `_USER-PROMPTS.md` owner interaction):",
        "- Ask **one foundation-level question at a time**.",
        "- Each question carries recommendation, strongest tradeoff, default if unanswered.",
        "- **Only a recorded owner answer with a timestamp counts as evidence.**",
        "- Inferred / majority / most-likely / LLM classification → **DEFERRED + impact**.",
        "- Do **not** silently rewrite ambiguous `M-NN` tokens.",
        "",
        f"Census: `{CENSUS_PATH.relative_to(REPO).as_posix()}`",
        f"Ledger: `{LEDGER_PATH.relative_to(REPO).as_posix()}`",
        "",
        "---",
        "",
    ]
    for i, q in enumerate(QUESTIONS, 1):
        covered = list(q["covers_buckets"])
        if covered:
            census = load_census()
            n_refs = sum(1 for r in census["refs"] if r["question_id"] == q["id"])
            covers_line = f"**Covers:** {', '.join(covered)} ({n_refs} refs)"
        else:
            covers_line = "**Covers:** session policy (0 direct refs)"
        parts.extend(
            [
                f"## {i}. {q['id']} — {q['title']}",
                "",
                covers_line,
                "",
                f"**Recommendation:** {q['recommendation']}",
                "",
                f"**Strongest tradeoff:** {q['strongest_tradeoff']}",
                "",
                f"**Default if unanswered:** {q['default_if_unanswered']}",
                "",
                f"**Impact if DEFERRED:** {q['impact_if_deferred']}",
                "",
                "---",
                "",
            ]
        )
    parts.extend(
        [
            "## Answer sheet (empty until owner speaks)",
            "",
            "| question | owner answer | answered_at |",
            "|---|---|---|",
        ]
    )
    for q in QUESTIONS:
        parts.append(f"| {q['id']} | — | — |")
    parts.append("")
    return "\n".join(parts)


def write_packet(path: Path | None = None) -> Path:
    target = path or PACKET_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_packet(), encoding="utf-8")
    return target


def sync_owner_question_packet_pointer() -> None:
    """Append a short pointer into the live OWNER-QUESTION-PACKET.md if missing."""
    marker = "## CC-0023 — 58 unresolvable option-id refs"
    pointer = (
        f"{marker}\n\n"
        "Owner adjudication for the 58 algorithmically unresolvable `M-NN` references "
        "lives in:\n\n"
        f"- `{PACKET_PATH.relative_to(REPO).as_posix()}` (one foundation question at a time)\n"
        f"- `{LEDGER_PATH.relative_to(REPO).as_posix()}` (machine ledger)\n"
        f"- `{OWNER_DECISIONS.relative_to(REPO).as_posix()}` section "
        "`CC-0023 — option-id namespace adjudication`\n\n"
        "Do not invent answers. Unanswered → DEFERRED + impact.\n"
    )
    if not OWNER_QUESTION_PACKET.is_file():
        OWNER_QUESTION_PACKET.write_text(pointer, encoding="utf-8")
        return
    text = OWNER_QUESTION_PACKET.read_text(encoding="utf-8")
    if marker in text:
        return
    OWNER_QUESTION_PACKET.write_text(text.rstrip() + "\n\n" + pointer, encoding="utf-8")


def run_all_controls(
    *,
    ledger: dict[str, Any] | None = None,
    rewrite_before: str = "See M-16 and M-18 in the BLOCKS field.",
    rewrite_after: str | None = None,
) -> dict[str, Any]:
    led = ledger or load_ledger()
    after = rewrite_after if rewrite_after is not None else rewrite_before
    controls = [
        census_arithmetic_ok(),
        grouping_control(),
        deferred_coverage_control(led),
        silent_rewrite_control(before_text=rewrite_before, after_text=after),
        durability_roundtrip(led),
    ]
    return {
        "ok": all(c.passed for c in controls),
        "controls": {c.name: {"pass": c.passed, "detail": c.detail} for c in controls},
    }


def materialize(*, defer_stamp: str | None = None) -> dict[str, Any]:
    """Write packet, ledger (all DEFERRED), OWNER-DECISIONS section, pointer."""
    write_packet()
    sync_owner_question_packet_pointer()
    led = apply_owner_silence(now=defer_stamp)
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(
        json.dumps(led, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    upsert_owner_decisions_section(led)
    return led


if __name__ == "__main__":
    import sys

    led = materialize()
    report = run_all_controls(ledger=led)
    print(json.dumps({"counts": led["counts"], "controls": report}, indent=2))
    sys.exit(0 if report["ok"] else 1)
