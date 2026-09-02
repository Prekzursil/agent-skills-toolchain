#!/usr/bin/env python3
"""RES-0086 mechanism table, rail integrity, and hard-gate checker.

Classification is about whether omitting the minority position from a named
artifact field would fail a mechanical check (structurally-enforced) or
whether survival depends on people following instructions (norm-dependent).
Only structurally-enforced preservation mechanisms may be recommended as gates.
"""
from __future__ import annotations

import copy
import hashlib
import json
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAP = HERE / "captures"
INDEX_PATH = CAP / "INDEX.json"
LOCAL_PATH = CAP / "LOCAL.json"

ENFORCEMENT = ("structurally-enforced", "norm-dependent")
NONE_FIELDS = frozenset({"", "none", "n/a", "-", "null", "None"})
HARD_GATE_FIELD = "minority_reports"
HARD_GATE_ITEM_KEYS = ("author_id", "rationale", "claim_ids", "sha256")

# Needles that must occur in the frozen capture (prevents citing WAF interstitials).
NEEDLES: dict[str, tuple[bytes, ...]] = {
    "w3c-process-html": (
        b"Formal Objection",
        b"publicly available",
        b"Call for Review",
    ),
    "w3c-council-guide": (
        b"Publishing Formal Objections",
        b"must be made publicly available",
    ),
    "ieee-opman-sect5": (
        b"verbatim text of each comment",
        b"Do Not Approve",
    ),
    "ieee-recirc-faq": (b"unresolved negative comments",),
    "fomc-minutes-20260729": (b"Voting against this action",),
    "stlouisfed-fomc-dissents": (
        b"reasons given by any members who dissent",
    ),
    "fomc-statement-20260729": (b"Voting against",),
    "rfc7282-txt": (
        b"important minority views to get lost in the noise",
        b"reasoned explanation",
    ),
    "rfc7282-datatracker-html": (b"minority views",),
    "govinfo-21-14-60-xml": (
        b"may not refer to members by name",
        b"complete and accurate description",
    ),
    "cornell-21-14-60": (b"may not refer to members by name",),
    "frcp-31-cornell": (b"The verdict must be unanimous",),
    "ca3-frcp-31-chapter9": (b"Rule 31", b"unanimous"),
    "icj-statute": (
        b"any judge shall be entitled to deliver a separate opinion",
    ),
    "icj-spender-art57": (b"Article 57", b"separate opinion"),
}


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def pdf_inflated(raw: bytes) -> bytes:
    """Concatenate FlateDecode PDF streams so needle search is possible."""
    out = bytearray()
    i = 0
    while True:
        j = raw.find(b"stream", i)
        if j < 0:
            break
        k = raw.find(b"endstream", j)
        if k < 0:
            break
        chunk = raw[j + 6 : k]
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        elif chunk.startswith(b"\n"):
            chunk = chunk[1:]
        elif chunk.startswith(b"\r"):
            chunk = chunk[1:]
        try:
            out.extend(zlib.decompress(chunk))
        except zlib.error:
            pass
        i = k + 9
    return bytes(out)


def pdf_literal_text(inflated: bytes) -> bytes:
    """Join PDF literal strings so kerned TJ arrays become searchable text."""
    import re

    parts = re.findall(rb"\((?:\\.|[^\\)])*\)", inflated)
    return b"".join(p[1:-1] for p in parts)


def haystack(raw: bytes) -> bytes:
    if raw.startswith(b"%PDF"):
        inflated = pdf_inflated(raw)
        if not inflated:
            return raw
        literals = pdf_literal_text(inflated)
        return literals if literals else inflated
    return raw


def load_index() -> list[dict]:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


LOCAL_SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "command-center/WORK-UNIT-CATALOG.json",
        "catalog-res-0086-row",
        "structured-catalog-json",
    ),
    (
        "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md",
        "prompt-two-slice-dissent-lines",
        "prose-named-failure-class",
    ),
)


def build_local_rows(now: str | None = None) -> list[dict]:
    """Derive the two local (non-network) rails straight from the tree.

    The catalog row and the CC-0024 fixture live in this repository, so their
    lineage never needs a fetch: it is rebuilt from bytes on disk. ``capture.py``
    freezes the same rows into ``captures/LOCAL.json``; ``load_local`` falls back
    to this builder when that frozen file is absent from a capture.
    """
    from datetime import datetime, timezone

    stamp = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for rel, lid, kind in LOCAL_SOURCES:
        path = REPO / rel
        present = path.is_file()
        raw = path.read_bytes() if present else b""
        rows.append(
            {
                "id": lid,
                "kind": kind,
                "path": rel if present else str(path),
                "present": present,
                "bytes": len(raw),
                "sha256": digest_bytes(raw) if raw else "",
                "http_status": 200 if present else 0,
                "fetched_at": stamp,
                "permalink": rel if present else "",
            }
        )
    return rows


def load_local() -> list[dict]:
    if LOCAL_PATH.is_file():
        return json.loads(LOCAL_PATH.read_text(encoding="utf-8"))
    return build_local_rows()


def index_by_id() -> dict[str, dict]:
    return {row["id"]: row for row in load_index()}


def capture_bytes(capture_id: str) -> bytes:
    row = index_by_id()[capture_id]
    path = REPO / row["capture_path"]
    return path.read_bytes()


def rail_record(capture_id: str, kind: str) -> dict:
    row = index_by_id()[capture_id]
    rec = {
        "id": row["id"],
        "kind": kind,
        "permalink": row["permalink"],
        "fetched_at": row["fetched_at"],
        "http_status": row["http_status"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
        "capture_path": row["capture_path"],
    }
    if row.get("canonical_permalink"):
        rec["canonical_permalink"] = row["canonical_permalink"]
    if row.get("note"):
        rec["note"] = row["note"]
    if row.get("final_url"):
        rec["final_url"] = row["final_url"]
    return rec


def local_rail(local_id: str, kind: str) -> dict:
    row = next(r for r in load_local() if r["id"] == local_id)
    return {
        "id": row["id"],
        "kind": kind,
        "permalink": row["permalink"],
        "fetched_at": row["fetched_at"],
        "http_status": row["http_status"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
        "capture_path": row["path"],
        "binding_full_file_hash": local_id != "catalog-res-0086-row",
        "note": (
            "Full-catalog sha256 is informational; probe binds on the RES-0086 "
            "unit object, not the 5MB catalog file, because sibling units may "
            "touch other keys."
            if local_id == "catalog-res-0086-row"
            else "Fixture hash is binding."
        ),
    }


def snippet(capture_id: str, needle: bytes, window: int = 200) -> str:
    raw = haystack(capture_bytes(capture_id))
    i = raw.lower().find(needle.lower())
    if i < 0:
        return ""
    start = max(0, i - 40)
    frag = raw[start : i + window]
    return frag.decode("utf-8", "replace").replace("\n", " ").replace("\r", " ")


def verify_captures() -> dict:
    idx = load_index()
    failures = []
    rows = []
    for row in idx:
        cid = row["id"]
        path = REPO / row["capture_path"]
        if not path.is_file():
            failures.append(f"missing:{cid}")
            continue
        raw = path.read_bytes()
        live_sha = digest_bytes(raw)
        if live_sha != row.get("sha256"):
            failures.append(f"sha-mismatch:{cid}")
        if row.get("http_status") != 200:
            failures.append(f"http:{cid}:{row.get('http_status')}")
        if not row.get("permalink") or not row.get("fetched_at"):
            failures.append(f"lineage-incomplete:{cid}")
        hay = haystack(raw)
        for needle in NEEDLES.get(cid, ()):
            if needle.lower() not in hay.lower():
                failures.append(f"needle-miss:{cid}:{needle.decode()}")
        rows.append(cid)
    return {
        "ok": not failures,
        "failures": failures,
        "n": len(rows),
        "ids": rows,
    }


def mechanisms() -> list[dict]:
    """Canonical eight-row table. Mutants copy this."""
    return [
        {
            "id": "M1-w3c-formal-objection",
            "institution_class": "standards-body",
            "institution": "W3C",
            "mechanism": (
                "Formal Objection public record: the objection MUST include "
                "issue, decision, and rationale; a record MUST be made "
                "publicly available; a Call for Review MUST identify related "
                "Formal Objections."
            ),
            "enforcement_classification": "structurally-enforced",
            "preserves_minority": True,
            "checkable_artifact_field": "formal_objections",
            "gate_predicate": (
                "formal_objections is a required array. Each item has "
                "objector_id, issue_summary, decision_appealed, rationale. "
                "If any FO was filed, omitting its row fails the gate. "
                "call_for_review.identified_formal_objection_ids must list "
                "those ids."
            ),
            "recommended_as_gate": True,
            "strongest_caveat": (
                "W3C waives the public-record requirement if the objector is "
                "satisfied before confidentiality is changed. The gate must "
                "still record the FO and the resolution, not drop the row."
            ),
            "claim_id": "C1",
            "rail_ids": ["w3c-process-html", "w3c-council-guide"],
        },
        {
            "id": "M2-ieee-recirculation",
            "institution_class": "standards-body",
            "institution": "IEEE-SA",
            "mechanism": (
                "Recirculation ballot package MUST include the verbatim text "
                "of each unresolved Do Not Approve comment, the voter name, "
                "and the comment-resolution response; unresolved negatives "
                "are submitted to RevCom with those reasons."
            ),
            "enforcement_classification": "structurally-enforced",
            "preserves_minority": True,
            "checkable_artifact_field": "unresolved_negative_comments",
            "gate_predicate": (
                "unresolved_negative_comments[].comment_verbatim, "
                "voter_name, and disposition_response are required. A "
                "disposition of reject without rationale fails. Recirculation "
                "cannot close while an unresolved DNA vote lacks this triple."
            ),
            "recommended_as_gate": True,
            "strongest_caveat": (
                "Live IEEE OM HTML returned HTTP 403; this row is grounded in "
                "the 2024 Wayback snapshot of the same URL plus the IEEE FAQ "
                "snapshot. Recirculation preserves comments into the ballot "
                "package, not necessarily into the published standard text."
            ),
            "claim_id": "C2",
            "rail_ids": ["ieee-opman-sect5", "ieee-recirc-faq"],
        },
        {
            "id": "M3-fomc-vote-against",
            "institution_class": "regulatory-advisory-panel",
            "institution": "FOMC",
            "mechanism": (
                "FOMC minutes (and the policy statement) contain a named "
                "'Voting against this action' line listing dissenting members "
                "and a one-line preference."
            ),
            "enforcement_classification": "structurally-enforced",
            "preserves_minority": True,
            "checkable_artifact_field": "vote.against",
            "gate_predicate": (
                "vote.against is a required array (may be empty). Each item "
                "has member_id and preferred_action. Dropping a known "
                "dissenting member_id fails."
            ),
            "recommended_as_gate": True,
            "strongest_caveat": (
                "This structurally preserves identity and a one-line "
                "preference, not a full minority report. St. Louis Fed notes "
                "that fuller reasons often appear in speeches, which are "
                "norm-dependent add-ons."
            ),
            "claim_id": "C3",
            "rail_ids": ["fomc-minutes-20260729", "stlouisfed-fomc-dissents"],
        },
        {
            "id": "M4-icj-article-57",
            "institution_class": "judicial-analog",
            "institution": "International Court of Justice",
            "mechanism": (
                "ICJ Statute Article 57: if the judgment is not unanimous in "
                "whole or in part, any judge shall be entitled to deliver a "
                "separate opinion, published with the judgment."
            ),
            "enforcement_classification": "structurally-enforced",
            "preserves_minority": True,
            "checkable_artifact_field": "dissenting_opinions",
            "gate_predicate": (
                "dissenting_opinions is a required array. If vote.against is "
                "non-empty, each dissenting judge is either an author of a "
                "dissenting_opinions row or has declined_to_file=true. "
                "Dropping a filed separate opinion fails."
            ),
            "recommended_as_gate": True,
            "strongest_caveat": (
                "'Entitled' is a right, not a duty: a dissenting judge may "
                "decline to file. The gate therefore requires the array key "
                "and identity coverage, not a forced essay."
            ),
            "claim_id": "C4",
            "rail_ids": ["icj-statute", "icj-spender-art57"],
        },
        {
            "id": "M5-fda-14-60-minutes",
            "institution_class": "regulatory-advisory-panel",
            "institution": "FDA advisory committees (21 CFR 14.60)",
            "mechanism": (
                "Minutes MUST describe matters discussed and conclusions, but "
                "closed deliberative minutes may not refer to members by name "
                "except on request, so attributed minority positions are not "
                "a required field."
            ),
            "enforcement_classification": "norm-dependent",
            "preserves_minority": False,
            "checkable_artifact_field": "none",
            "gate_predicate": (
                "Minutes existence is structural; attributed dissent is not. "
                "No named field a hard gate can check for minority survival."
            ),
            "recommended_as_gate": False,
            "strongest_caveat": (
                "A committee could still write named dissents into open "
                "minutes. That is optional practice, not a checkable field."
            ),
            "claim_id": "C5",
            "rail_ids": ["govinfo-21-14-60-xml", "cornell-21-14-60"],
        },
        {
            "id": "M6-ietf-rough-consensus",
            "institution_class": "standards-body",
            "institution": "IETF",
            "mechanism": (
                "RFC 7282: chairs should give a reasoned explanation to "
                "unaccommodated objectors; counting heads can lose minority "
                "views. The RFC publication artifact has no required dissent "
                "section, so the duty is a chair instruction."
            ),
            "enforcement_classification": "norm-dependent",
            "preserves_minority": False,
            "checkable_artifact_field": "none",
            "gate_predicate": "No RFC-level field a hard gate can check.",
            "recommended_as_gate": False,
            "strongest_caveat": (
                "Mailing-list archives exist, but RFC publication does not "
                "fail closed if a dissent section is absent. Treating IETF "
                "rough consensus as a gate would be an instruction the "
                "synthesizer may ignore."
            ),
            "claim_id": "C6",
            "rail_ids": ["rfc7282-txt", "rfc7282-datatracker-html"],
        },
        {
            "id": "M7-frcp-31-jury-verdict",
            "institution_class": "jury",
            "institution": "US federal criminal jury (FRCP 31)",
            "mechanism": (
                "The verdict MUST be unanimous. A poll that reveals dissent "
                "leads to further deliberation or mistrial. Minority "
                "reasoning never becomes a field on the verdict form."
            ),
            "enforcement_classification": "norm-dependent",
            "preserves_minority": False,
            "checkable_artifact_field": "none",
            "gate_predicate": (
                "The verdict artifact is structurally silent on minority "
                "reasoning. Preservation, when it happens, is extra-record "
                "interview practice."
            ),
            "recommended_as_gate": False,
            "strongest_caveat": (
                "Unanimity is itself structural, but it structurally erases "
                "rather than preserves minority positions. Classified "
                "norm-dependent as a *preservation* mechanism because no "
                "checkable field goes red when minority reasoning is absent."
            ),
            "claim_id": "C7",
            "rail_ids": ["frcp-31-cornell", "ca3-frcp-31-chapter9"],
        },
        {
            "id": "M8-synthesizer-instruction",
            "institution_class": "anti-pattern",
            "institution": "Council synthesizer prompt",
            "mechanism": (
                "An instruction that the synthesizer 'include the minority "
                "report' or that omitted dissent is a named failure class, "
                "without a schema field a checker can fail."
            ),
            "enforcement_classification": "norm-dependent",
            "preserves_minority": False,
            "checkable_artifact_field": "none",
            "gate_predicate": "Prompt text is not a hard gate.",
            "recommended_as_gate": False,
            "strongest_caveat": (
                "Catalog RES-0086 itself forbids recommending this class as "
                "a gate. The named failure class at _USER-PROMPTS.md:11340 "
                "is the harm this unit's field is meant to catch."
            ),
            "claim_id": "C8",
            "rail_ids": [
                "catalog-res-0086-row",
                "prompt-two-slice-dissent-lines",
            ],
        },
    ]


def attach_rails(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        rec = copy.deepcopy(row)
        rails = []
        for rid in rec["rail_ids"]:
            if rid in ("catalog-res-0086-row", "prompt-two-slice-dissent-lines"):
                kind = (
                    "structured-api-probe"
                    if rid == "catalog-res-0086-row"
                    else "prose-source"
                )
                rails.append(local_rail(rid, kind))
            else:
                idx = index_by_id()[rid]
                kind = (
                    "structured-api-probe"
                    if idx.get("rail") == "R1"
                    else "prose-source"
                )
                rails.append(rail_record(rid, kind))
        rec["rails"] = rails
        out.append(rec)
    return out


def field_named(value: object) -> bool:
    return str(value or "").strip() not in NONE_FIELDS


def table_violations(rows: list[dict]) -> list[str]:
    """Return reasons the table is not gate-legal. Empty => silent/good."""
    v: list[str] = []
    classes = set()
    for row in rows:
        eid = row.get("id") or "?"
        klass = row.get("enforcement_classification")
        classes.add(klass)
        if klass not in ENFORCEMENT:
            v.append(f"{eid}:bad-class:{klass}")
        rec = bool(row.get("recommended_as_gate"))
        field = row.get("checkable_artifact_field")
        preserves = row.get("preserves_minority")
        if rec:
            if klass != "structurally-enforced":
                v.append(f"{eid}:norm-dependent-recommended-as-gate")
            if not field_named(field):
                v.append(f"{eid}:recommended-without-checkable-field")
            if preserves is not True:
                v.append(f"{eid}:non-preserving-recommended-as-gate")
        if klass == "structurally-enforced" and preserves is True:
            if not field_named(field):
                v.append(f"{eid}:structural-preservation-missing-field")
        if klass == "norm-dependent" and field_named(field):
            v.append(f"{eid}:norm-dependent-claimed-checkable-field")
    if "structurally-enforced" not in classes:
        v.append("table:no-structurally-enforced-row")
    if "norm-dependent" not in classes:
        v.append("table:no-norm-dependent-row")
    if not any(r.get("recommended_as_gate") for r in rows):
        v.append("table:no-recommended-gate")
    rec_fields = {
        r.get("checkable_artifact_field")
        for r in rows
        if r.get("recommended_as_gate")
    }
    if HARD_GATE_FIELD not in rec_fields and not any(
        field_named(r.get("checkable_artifact_field"))
        for r in rows
        if r.get("recommended_as_gate")
    ):
        v.append("table:no-named-hard-gate-field")
    return v


def evaluate_table(rows: list[dict]) -> dict:
    viol = table_violations(rows)
    return {
        "silent": not viol,
        "fired": bool(viol),
        "violations": viol,
        "n": len(rows),
        "n_structural": sum(
            1
            for r in rows
            if r.get("enforcement_classification") == "structurally-enforced"
        ),
        "n_norm": sum(
            1
            for r in rows
            if r.get("enforcement_classification") == "norm-dependent"
        ),
        "recommended_fields": [
            r.get("checkable_artifact_field")
            for r in rows
            if r.get("recommended_as_gate")
        ],
    }


def mutant_norm_as_gate() -> list[dict]:
    rows = copy.deepcopy(mechanisms())
    for row in rows:
        if row["id"] == "M6-ietf-rough-consensus":
            row["recommended_as_gate"] = True
            row["checkable_artifact_field"] = "please_include_dissent"
    return rows


def mutant_empty_field() -> list[dict]:
    rows = copy.deepcopy(mechanisms())
    for row in rows:
        if row["id"] == "M1-w3c-formal-objection":
            row["checkable_artifact_field"] = ""
    return rows


def both_states() -> dict:
    good = evaluate_table(mechanisms())
    bad_norm = evaluate_table(mutant_norm_as_gate())
    bad_field = evaluate_table(mutant_empty_field())
    fired_on_bad = bad_norm["fired"] and bad_field["fired"]
    silent_on_good = good["silent"]
    return {
        "check": "hard-gate-only-structurally-enforced-with-named-field",
        "good": good,
        "mutant_norm_as_gate": bad_norm,
        "mutant_empty_field": bad_field,
        "fired_on_bad": fired_on_bad,
        "silent_on_good": silent_on_good,
        "discriminates": fired_on_bad and silent_on_good,
        "negative_control": {
            "rejects": (
                "A table that recommends IETF rough consensus (norm-dependent) "
                "as a gate, and a table that recommends W3C FO as a gate but "
                "leaves checkable_artifact_field empty."
            ),
            "on_that_state": (
                "mutant_norm_as_gate.fired and mutant_empty_field.fired"
            ),
            "bad_state_output": {
                "norm_as_gate_violations": bad_norm["violations"],
                "empty_field_violations": bad_field["violations"],
            },
            "good_state_output": {"violations": good["violations"]},
        },
        "hard_gate_field": HARD_GATE_FIELD,
        "hard_gate_item_keys": list(HARD_GATE_ITEM_KEYS),
    }


def catalog_res0086() -> dict:
    catalog = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(
            encoding="utf-8"
        )
    )
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "RES-0086":
            return unit
    return {}


def fixture_dissent_line_present() -> bool:
    path = (
        REPO
        / "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
    )
    text = path.read_text(encoding="utf-8")
    return "dissent/minority report is dropped" in text


def claims() -> list[dict]:
    table = attach_rails(mechanisms())
    out = []
    for row in table:
        out.append(
            {
                "id": row["claim_id"],
                "mechanism_id": row["id"],
                "claim": row["mechanism"],
                "enforcement_classification": row["enforcement_classification"],
                "evidence_tier": "E2",
                "verdict": "CONFIRMED",
                "strongest_caveat": row["strongest_caveat"],
                "rails": row["rails"],
                "checkable_artifact_field": row["checkable_artifact_field"],
                "recommended_as_gate": row["recommended_as_gate"],
            }
        )
    return out


def hard_gate() -> dict:
    return {
        "artifact_field": HARD_GATE_FIELD,
        "required_item_keys": list(HARD_GATE_ITEM_KEYS),
        "supporting_fields": [
            "formal_objections",
            "unresolved_negative_comments",
            "vote.against",
            "dissenting_opinions",
        ],
        "predicate": (
            "The key minority_reports MUST be present even when empty. "
            "Each item requires author_id, rationale, claim_ids, sha256. "
            "For every member_id in vote.against, a matching minority_reports "
            "row exists OR declined_to_file is true. Synthesis MUST NOT drop "
            "an existing row. Only mechanisms classified "
            "structurally-enforced may be wired to this gate. A prompt "
            "instruction without this field is not a gate."
        ),
        "derived_from": [
            "M1-w3c-formal-objection",
            "M2-ieee-recirculation",
            "M3-fomc-vote-against",
            "M4-icj-article-57",
        ],
    }
