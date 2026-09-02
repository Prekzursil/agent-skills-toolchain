#!/usr/bin/env python3
"""Semantic authority-provenance classifier for ADV-0138.

Matching is on topic + value + speech-act, never on keyword overlap.
An owner utterance that mentions a topic and defers it is not a decision.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
FIXTURES = HERE / "fixtures"

OWNER_STATED = "OWNER-STATED"
IMPLIED = "OWNER-IMPLIED-BY-INFERENCE"
PROGRAM = "PROGRAM-AUTHORED"

RECORD_RE = re.compile(
    r"^(?P<id>[A-Z0-9-]+)\s+topic=(?P<topic>\S+)\s+"
    r"speech_act=(?P<act>\S+)\s+value=(?P<value>\S*)\s*$"
)
KW_SPLIT = re.compile(r"[^a-z0-9]+")

OQ_TOPIC = {
    "OQ-1": ("option-ids", "SEVENTY-OPTION-IDS"),
    "OQ-2": ("execution-order", "PHASE-THEN-UNBLOCK"),
    "OQ-3": ("release-mode", "PR-ONLY"),
    "OQ-4": ("tranche-38", "NOT-APPROVED"),
    "OQ-8": ("monitor-cockpit", "ENROLL-NORMAL-PRIORITY"),
    "OQ-9": ("canary-substitute", "CI-REHEARSAL"),
    "OQ-10": ("bucket-dep-meaning", "GATE-ARTIFACT"),
}

LIVE_DECISIONS = (
    {
        "id": "BD-RELEASE-PR-ONLY",
        "decision": "Release mode is PR-ONLY.",
        "program_statement": (
            "Prompt Two release mode is PR-ONLY: propose changes as pull "
            "requests, never a private canary and never a public marketplace."
        ),
        "topic": "release-mode",
        "value": "PR-ONLY",
        "needle": '"id": "OQ-3"',
        "row_kind": "live",
    },
    {
        "id": "BD-RETIRE-DELETE-ALL",
        "decision": "Retirement scope is DELETE-ALL across five trees.",
        "program_statement": (
            "For each decision in OWNER-DECISIONS.md and 17-DECISION-LOG.md, "
            "extract its normative content (release mode = PR-ONLY; retirement "
            "scope = DELETE-ALL across five trees; salvage home = tools/lib/; "
            "no-remote repos = triage first, never create remotes)"
        ),
        "topic": "retirement-scope",
        "value": "DELETE-ALL",
        "needle": "retirement scope = DELETE-ALL across five trees",
        "row_kind": "live",
    },
    {
        "id": "BD-SALVAGE-TOOLS-LIB",
        "decision": "Salvage home is tools/lib/.",
        "program_statement": "salvage home = tools/lib/",
        "topic": "salvage-home",
        "value": "TOOLS-LIB",
        "needle": "salvage home = tools/lib/",
        "row_kind": "live",
    },
    {
        "id": "BD-NOREMOTE-TRIAGE",
        "decision": "No-remote repositories: triage first, never create remotes.",
        "program_statement": "no-remote repos = triage first, never create remotes",
        "topic": "no-remote-policy",
        "value": "TRIAGE-FIRST-NO-CREATE",
        "needle": "no-remote repos = triage first, never create remotes",
        "row_kind": "live",
    },
    {
        "id": "BD-OQ1-SEVENTY-IDS",
        "decision": "Selected option IDs are the 70 owner_decisions list.",
        "program_statement": (
            "The 70 owner_decisions in 07-OPTION-UNIVERSE.json (delegated default)."
        ),
        "topic": "option-ids",
        "value": "SEVENTY-OPTION-IDS",
        "needle": '"id": "OQ-1"',
        "row_kind": "live",
    },
    {
        "id": "BD-OQ2-PHASE-ORDER",
        "decision": "Execute in ascending phase, then unblocking power.",
        "program_statement": "Phase order, then unblocking power (delegated default).",
        "topic": "execution-order",
        "value": "PHASE-THEN-UNBLOCK",
        "needle": '"id": "OQ-2"',
        "row_kind": "live",
    },
    {
        "id": "BD-OQ4-NO-TRANCHE",
        "decision": "The 38-item harness tranche is not an approved Prompt Two substitute.",
        "program_statement": (
            "NO - the 38-item tranche was NOT an approved substitute."
        ),
        "topic": "tranche-38",
        "value": "NOT-APPROVED",
        "needle": '"id": "OQ-4"',
        "row_kind": "live",
    },
    {
        "id": "BD-OQ8-COCKPIT",
        "decision": "Enrol the monitor cockpit at normal MONITOR priority.",
        "program_statement": (
            "Enrol the monitor cockpit at the same priority as the other "
            "MONITOR rows (delegated default)."
        ),
        "topic": "monitor-cockpit",
        "value": "ENROLL-NORMAL-PRIORITY",
        "needle": '"id": "OQ-8"',
        "row_kind": "live",
    },
    {
        "id": "BD-OQ9-CANARY-SUB",
        "decision": (
            "A green CI install/upgrade/rollback rehearsal stands in for the canary."
        ),
        "program_statement": (
            "A green CI install/upgrade/rollback rehearsal stands in for the "
            "canary (delegated default)."
        ),
        "topic": "canary-substitute",
        "value": "CI-REHEARSAL",
        "needle": '"id": "OQ-9"',
        "row_kind": "live",
    },
    {
        "id": "BD-OQ10-BUCKET",
        "decision": "A bucket dependency is satisfied by a bucket-level gate artifact.",
        "program_statement": (
            "A bucket dependency is satisfied by a bucket-level gate artifact "
            "(delegated default)."
        ),
        "topic": "bucket-dep-meaning",
        "value": "GATE-ARTIFACT",
        "needle": '"id": "OQ-10"',
        "row_kind": "live",
    },
    {
        "id": "BD-C16-ADOPT-SPLIT",
        "decision": "C16 = ADOPT_THE_SPLIT is a binding owner decision.",
        "program_statement": (
            "Implement C16 = ADOPT_THE_SPLIT; a binding owner decision the "
            "contract forbids re-asking."
        ),
        "topic": "c16-split",
        "value": "ADOPT-THE-SPLIT",
        "needle": "C16 = ADOPT_THE_SPLIT",
        "row_kind": "live",
    },
    {
        "id": "BD-NO-MARKETPLACE-PUBLISH",
        "decision": "Public marketplace publishing is not an approved release path.",
        "program_statement": (
            "never a private canary and never a public marketplace release"
        ),
        "topic": "marketplace-publish",
        "value": "NOT-APPROVED",
        "needle": "never a private canary and never a public marketplace release",
        "row_kind": "live",
        "allow_implied": True,
        "implied_from_topic": "release-mode",
        "implied_from_value": "PR-ONLY",
        "inference_step": (
            "Owner stated release mode is PR-ONLY and the same utterance "
            "forbids a public marketplace release. The program's binding "
            "'do not publish to the public marketplace' follows from that "
            "sentence without a separate owner question. The owner can "
            "reject this inference by authorizing a marketplace path."
        ),
    },
)

CONTROL_DECISIONS = {
    "known_present_pr_only": {
        "id": "KP-PR-ONLY",
        "decision": "Release mode is PR-ONLY.",
        "program_statement": "Release mode is PR-ONLY (known-present control).",
        "topic": "release-mode",
        "value": "PR-ONLY",
        "row_kind": "control-known-present",
    },
    "known_present_delete_all": {
        "id": "KP-DELETE-ALL",
        "decision": "Retirement scope is DELETE-ALL across five trees.",
        "program_statement": (
            "Retirement scope is DELETE-ALL across five trees (known-present control)."
        ),
        "topic": "retirement-scope",
        "value": "DELETE-ALL",
        "row_kind": "control-known-present",
    },
    "planted": {
        "id": "BD-PLANTED-LAUNDERING",
        "decision": (
            "All artifacts SHALL be published to the public marketplace immediately."
        ),
        "program_statement": (
            "All artifacts SHALL be published to the public marketplace "
            "immediately (binding)."
        ),
        "topic": "planted-public-publish",
        "value": "PUBLIC-MARKETPLACE-NOW",
        "row_kind": "control-planted",
    },
    "use_vs_mention": {
        "id": "BD-USE-VS-MENTION",
        "decision": "Release mode is PUBLIC MARKETPLACE.",
        "program_statement": "Release mode is PUBLIC MARKETPLACE (binding).",
        "topic": "release-mode",
        "value": "PUBLIC-MARKETPLACE",
        "row_kind": "control-use-vs-mention",
    },
}


@dataclass(frozen=True)
class Utterance:
    path: str
    line: int
    quote: str
    speech_act: str
    topic: str
    value: str
    origin: str


@dataclass
class Classification:
    classification: str
    owner_quote: str = ""
    anchor: str = ""
    inference_step: str = ""
    reason: str = ""
    matched_utterance: Utterance | None = None


def norm_value(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", (text or "").upper())


def values_match(a: str, b: str) -> bool:
    na, nb = norm_value(a), norm_value(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def first_line_containing(path: Path, needle: str) -> tuple[int, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return i, line.strip()
    raise ValueError(f"needle not found in {relpath(path)}: {needle!r}")


def parse_fixture(path: Path) -> tuple[list[Utterance], list[dict]]:
    utterances: list[Utterance] = []
    programs: list[dict] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    pending = None
    pending_line = 0
    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        m = RECORD_RE.match(line.strip())
        if m:
            pending = m.groupdict()
            pending_line = i
            continue
        if pending is None:
            continue
        stripped = line.strip()
        if stripped.startswith("Owner:"):
            quote = stripped[len("Owner:") :].strip()
            utterances.append(
                Utterance(
                    path=relpath(path),
                    line=i,
                    quote=quote,
                    speech_act=pending["act"],
                    topic=pending["topic"],
                    value=pending["value"],
                    origin="fixture",
                )
            )
            pending = None
        elif stripped.startswith("Program:"):
            quote = stripped[len("Program:") :].strip()
            programs.append(
                {
                    "id": pending["id"],
                    "topic": pending["topic"],
                    "value": pending["value"],
                    "program_statement": quote,
                    "path": relpath(path),
                    "line": i,
                    "meta_line": pending_line,
                }
            )
            pending = None
    return utterances, programs


def catalog_oq_speech_act(row: dict) -> str:
    prov = str(row.get("answer_provenance") or "")
    if "NOT an owner-authored selection" in prov or "delegated default" in prov.lower():
        return "delegate"
    if "owner statement" in prov.lower():
        return "decide"
    if row.get("state") == "ANSWERED":
        return "delegate"
    return "none"


def load_catalog_utterances() -> list[Utterance]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out: list[Utterance] = []
    for row in data.get("owner_questions") or []:
        if not isinstance(row, dict):
            continue
        oid = str(row.get("id") or "")
        if oid not in OQ_TOPIC:
            continue
        if row.get("state") != "ANSWERED":
            continue
        topic, value = OQ_TOPIC[oid]
        act = catalog_oq_speech_act(row)
        answer = str(row.get("answer") or "").strip()
        detail = str(row.get("answer_detail") or "").strip()
        quote = answer or detail
        needle = f'"answer": {json.dumps(answer)}' if answer else f'"id": "{oid}"'
        try:
            line, _ = first_line_containing(CATALOG, needle)
        except ValueError:
            line, _ = first_line_containing(CATALOG, f'"id": "{oid}"')
        out.append(
            Utterance(
                path=relpath(CATALOG),
                line=line,
                quote=quote,
                speech_act=act,
                topic=topic,
                value=value,
                origin=f"catalog-{oid}",
            )
        )
    return out


def load_live_decisions() -> list[dict]:
    rows = []
    for spec in LIVE_DECISIONS:
        line, snippet = first_line_containing(CATALOG, spec["needle"])
        item = dict(spec)
        item["source_path"] = relpath(CATALOG)
        item["source_line"] = line
        item["source_snippet"] = snippet[:240]
        rows.append(item)
    return rows


def classify(
    decision: dict,
    utterances: Iterable[Utterance],
    *,
    detect_defer: bool = True,
) -> Classification:
    """Semantic classify. Keyword overlap is not a deciding signal."""
    uts = list(utterances)
    topic = decision["topic"]
    value = decision["value"]
    same = [u for u in uts if u.topic == topic]

    if detect_defer:
        deferred = [u for u in same if u.speech_act == "defer"]
    else:
        deferred = []

    deciding = [
        u
        for u in same
        if u.speech_act == "decide" and values_match(u.value, value)
    ]
    if deciding:
        u = deciding[0]
        return Classification(
            classification=OWNER_STATED,
            owner_quote=u.quote,
            anchor=f"{u.path}:{u.line}",
            reason="owner-decide-same-topic-and-value",
            matched_utterance=u,
        )

    if decision.get("allow_implied"):
        src_topic = decision.get("implied_from_topic")
        src_value = decision.get("implied_from_value")
        implied_from = [
            u
            for u in uts
            if u.topic == src_topic
            and u.speech_act == "decide"
            and values_match(u.value, src_value or "")
        ]
        if implied_from:
            u = implied_from[0]
            return Classification(
                classification=IMPLIED,
                owner_quote=u.quote,
                anchor=f"{u.path}:{u.line}",
                inference_step=str(decision.get("inference_step") or ""),
                reason="written-inference-from-owner-stated-premise",
                matched_utterance=u,
            )

    if deferred and not deciding:
        u = deferred[0]
        return Classification(
            classification=PROGRAM,
            owner_quote=u.quote,
            anchor=f"{u.path}:{u.line}",
            reason="topic-mentioned-but-explicitly-deferred",
            matched_utterance=u,
        )

    return Classification(
        classification=PROGRAM,
        reason="no-owner-utterance-decides-this-topic-and-value",
    )


def naive_keyword_classify(decision: dict, utterances: Iterable[Utterance]) -> Classification:
    """Broken matcher: any shared content word => OWNER-STATED.

    This is the failure the use-vs-mention control exists to catch.
    """
    blob = (decision.get("program_statement") or "") + " " + (decision.get("decision") or "")
    keys = {w for w in KW_SPLIT.split(blob.lower()) if len(w) >= 6}
    for u in utterances:
        hay = u.quote.lower()
        if any(k in hay for k in keys):
            return Classification(
                classification=OWNER_STATED,
                owner_quote=u.quote,
                anchor=f"{u.path}:{u.line}",
                reason="naive-keyword-overlap",
                matched_utterance=u,
            )
    return Classification(classification=PROGRAM, reason="naive-no-keyword")


def row_from(decision: dict, result: Classification) -> dict:
    re_put = result.classification == PROGRAM
    out = {
        "id": decision["id"],
        "decision": decision["decision"],
        "program_statement": decision["program_statement"],
        "classification": result.classification,
        "topic": decision["topic"],
        "value": decision["value"],
        "row_kind": decision.get("row_kind", "live"),
        "reason": result.reason,
        "re_put_to_owner": re_put,
        "program_source": (
            f"{decision.get('source_path', '')}:{decision.get('source_line', '')}".strip(":")
        ),
    }
    if result.owner_quote:
        out["owner_quote"] = result.owner_quote
    if result.anchor:
        out["anchor"] = result.anchor
    if result.inference_step:
        out["inference_step"] = result.inference_step
    if result.classification == PROGRAM:
        out["owner_quote"] = result.owner_quote
        if result.anchor:
            out["anchor"] = result.anchor
    return out


def resolve_anchor(anchor: str, quote: str) -> tuple[bool, str]:
    if ":" not in anchor:
        return False, "no-colon"
    path_s, _, line_s = anchor.rpartition(":")
    try:
        line_n = int(line_s)
    except ValueError:
        return False, "bad-line"
    path = REPO / path_s
    if not path.is_file():
        return False, f"missing:{path_s}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_n < 1 or line_n > len(lines):
        return False, f"oob:{path_s}:{line_n}"
    if quote not in lines[line_n - 1]:
        return False, f"quote-miss:{path_s}:{line_n}"
    return True, f"{path_s}:{line_n}"


def input_inventory() -> dict:
    candidates = {
        "owner_decisions_md": [
            "command-center/OWNER-DECISIONS.md",
            "OWNER-DECISIONS.md",
            "32-OWNER-DECISIONS.md",
        ],
        "user_prompts_md": [
            "_USER-PROMPTS.md",
            "command-center/_USER-PROMPTS.md",
        ],
        "owner_question_packet": [
            "command-center/OWNER-QUESTION-PACKET.md",
            "OWNER-QUESTION-PACKET.md",
        ],
        "decision_log": [
            "17-DECISION-LOG.md",
            "command-center/17-DECISION-LOG.md",
        ],
        "wfa_0077": [
            "command-center/wfa/WFA-0077-owner-approval-gate-list.json",
        ],
    }
    out = {}
    for key, paths in candidates.items():
        present = [p for p in paths if (REPO / p).is_file()]
        out[key] = {
            "present": bool(present),
            "paths_checked": paths,
            "found": present,
        }
    qrows = json.loads(CATALOG.read_text(encoding="utf-8")).get("owner_questions") or []
    answered = [
        r.get("id")
        for r in qrows
        if isinstance(r, dict) and r.get("state") == "ANSWERED"
    ]
    out["catalog_owner_questions"] = {
        "present": True,
        "path": relpath(CATALOG),
        "answered_ids": answered,
    }
    return out


def known_present_bundle() -> dict:
    uts, _ = parse_fixture(FIXTURES / "known_present_owner.txt")
    d_pr = CONTROL_DECISIONS["known_present_pr_only"]
    d_del = CONTROL_DECISIONS["known_present_delete_all"]
    r_pr = classify(d_pr, uts)
    r_del = classify(d_del, uts)
    ok_pr, why_pr = resolve_anchor(r_pr.anchor, r_pr.owner_quote)
    ok_del, why_del = resolve_anchor(r_del.anchor, r_del.owner_quote)
    passed = (
        r_pr.classification == OWNER_STATED
        and r_del.classification == OWNER_STATED
        and ok_pr
        and ok_del
    )
    return {
        "pass": passed,
        "pr_only": row_from(d_pr, r_pr),
        "delete_all": row_from(d_del, r_del),
        "anchors_ok": {"pr_only": why_pr, "delete_all": why_del},
        "utterance_count": len(uts),
    }


def planted_bundle(live_uts: list[Utterance] | None = None) -> dict:
    kp, _ = parse_fixture(FIXTURES / "known_present_owner.txt")
    planted_uts, planted_prog = parse_fixture(FIXTURES / "planted_laundering.txt")
    decision = dict(CONTROL_DECISIONS["planted"])
    if planted_prog:
        decision["program_statement"] = planted_prog[0]["program_statement"]
        decision["source_path"] = planted_prog[0]["path"]
        decision["source_line"] = planted_prog[0]["line"]
    uts = list(kp) + list(planted_uts) + list(live_uts or [])
    result = classify(decision, uts)
    naive = naive_keyword_classify(decision, uts)
    passed = result.classification == PROGRAM
    return {
        "pass": passed,
        "row": row_from(decision, result),
        "naive_would_have": naive.classification,
        "fixture": relpath(FIXTURES / "planted_laundering.txt"),
    }


def use_vs_mention_bundle() -> dict:
    uts, progs = parse_fixture(FIXTURES / "use_vs_mention.txt")
    decision = dict(CONTROL_DECISIONS["use_vs_mention"])
    if progs:
        decision["program_statement"] = progs[0]["program_statement"]
        decision["source_path"] = progs[0]["path"]
        decision["source_line"] = progs[0]["line"]
    semantic = classify(decision, uts)
    naive = naive_keyword_classify(decision, uts)
    passed = (
        semantic.classification == PROGRAM
        and naive.classification == OWNER_STATED
        and semantic.reason == "topic-mentioned-but-explicitly-deferred"
    )
    return {
        "pass": passed,
        "semantic": row_from(decision, semantic),
        "naive_keyword": {
            "classification": naive.classification,
            "reason": naive.reason,
            "owner_quote": naive.owner_quote,
            "anchor": naive.anchor,
        },
        "both_states_discriminates": (
            semantic.classification != naive.classification
        ),
        "fixture": relpath(FIXTURES / "use_vs_mention.txt"),
    }


def classify_live() -> list[dict]:
    uts = load_catalog_utterances()
    rows = []
    for decision in load_live_decisions():
        result = classify(decision, uts)
        rows.append(row_from(decision, result))
    return rows


def bindings_from_artifact(doc: dict) -> tuple[list, dict]:
    """Read live rows and controls from either the v1 top-level shape or report."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    live = doc.get("binding_decisions")
    if not isinstance(live, list):
        live = report.get("binding_decisions")
    if not isinstance(live, list):
        live = []
    controls = doc.get("controls")
    if not isinstance(controls, dict):
        controls = report.get("controls")
    if not isinstance(controls, dict):
        controls = {}
    return live, controls
