#!/usr/bin/env python3
"""Extract binding owner constraints from live files on this worktree.

Named catalog inputs that are missing, or present-but-wrong-document, are
recorded as such. Bytes are not invented. ANSWERED catalog owner_questions
are the live quoteable decision record when OWNER-DECISIONS.md does not
carry those rulings.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OWNER_REL = "command-center/OWNER-DECISIONS.md"
DECISION_LOG_REL = "17-DECISION-LOG.md"
OPTION_UNIVERSE_CANDIDATES = (
    "07-OPTION-UNIVERSE.json",
    "command-center/07-OPTION-UNIVERSE.json",
    "07-OPTION-UNIVERSE.md",
)
FAMILY_M_SLICE = "command-center/option-id/07-OPTION-UNIVERSE.family-M-slice.md"
PHASE3_LOG = "command-center/phase3/DECISION-LOG.md"
PROBE2 = "command-center/p2-wave/probes/RES-0183/probe2_quote_lineage.py"
NEGATION = re.compile(
    r"(?i)\b(never|not|no|reject(?:ed)?|must\s+not|do\s+not|don't|without|missing)\b"
)
PADDING_RULING = re.compile(
    r"^Owner ruling \d+: keep workflow catalog entry WF-\d+ as the published path"
)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def file_lineage(rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "present": False,
            "resolved_url": None,
            "fetch_timestamp": now_utc(),
            "sha256": None,
            "bytes": 0,
        }
    raw = path.read_bytes()
    return {
        "path": rel,
        "present": True,
        "resolved_url": path.resolve().as_uri(),
        "fetch_timestamp": now_utc(),
        "sha256": sha256_bytes(raw),
        "bytes": len(raw.replace(b"\r\n", b"\n")),
    }


def first_present(rels: tuple[str, ...]) -> str | None:
    for rel in rels:
        if (REPO / rel).is_file():
            return rel
    return None


def find_snippet_line(rel: str, snippet: str) -> tuple[int, str]:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if snippet in line:
            return i + 1, line.strip()[:400]
    raise KeyError(f"{snippet!r} not in {rel}")


def verify_quote(rel: str, line_no: int, quote: str, slop: int = 2) -> bool:
    path = REPO / rel
    if not path.is_file() or not quote:
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_no < 1 or line_no > len(lines):
        return False
    lo = max(0, line_no - 1 - slop)
    hi = min(len(lines), line_no + slop)
    return quote in "\n".join(lines[lo:hi])


def load_catalog() -> dict:
    return json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))


def answered_owner_questions() -> list[dict]:
    out = []
    for row in load_catalog().get("owner_questions") or []:
        if isinstance(row, dict) and str(row.get("state") or "").upper() == "ANSWERED":
            out.append(row)
    return out


def oq_anchor(qid: str, needle: str) -> tuple[str, int, str]:
    lines = (REPO / CATALOG_REL).read_text(encoding="utf-8").splitlines()
    start = None
    token = f'"id": "{qid}"'
    for i, line in enumerate(lines):
        if token in line:
            start = i
            break
    if start is None:
        raise KeyError(qid)
    for j in range(start, min(len(lines), start + 20)):
        if needle in lines[j]:
            return CATALOG_REL, j + 1, lines[j].strip()[:400]
    raise KeyError(f"{qid} needle {needle!r}")


def negation_before(text: str, start: int, window: int = 50) -> bool:
    prefix = text[max(0, start - window) : start]
    return bool(NEGATION.search(prefix))


def make_constraint(
    *,
    cid: str,
    kind: str,
    binding: bool,
    authority: str,
    owner_confirmation_required: bool,
    title: str,
    normative_text: str,
    quote: str,
    rel: str,
    line: int,
    confidence_band: str,
    forbidden_release_modes: list[str] | None = None,
    forbidden_patterns: list[dict] | None = None,
    notes: str = "",
) -> dict:
    return {
        "id": cid,
        "kind": kind,
        "binding": binding,
        "authority": authority,
        "owner_confirmation_required": owner_confirmation_required,
        "title": title,
        "normative_text": normative_text,
        "quote": quote,
        "anchor": f"{rel}:{line}",
        "path": rel,
        "line": line,
        "source_lineage": file_lineage(rel),
        "confidence_band": confidence_band,
        "settling_probe": PROBE2,
        "forbidden_release_modes": forbidden_release_modes or [],
        "forbidden_patterns": forbidden_patterns or [],
        "notes": notes,
    }


def parse_decision_log_current() -> dict[str, Any]:
    rel = DECISION_LOG_REL
    path = REPO / rel
    if not path.is_file():
        return {
            "present": False,
            "current_real": [],
            "padding_current": 0,
            "superseded": 0,
        }
    text = path.read_text(encoding="utf-8")
    chunks = re.split(r"(?m)^## ", text)
    current_real = []
    padding_current = 0
    superseded = 0
    for chunk in chunks[1:]:
        heading = chunk.splitlines()[0].strip()
        body = chunk
        status_m = re.search(r"(?m)^status:\s*(\S+)", body)
        status = (status_m.group(1) if status_m else "").upper()
        if status == "SUPERSEDED":
            superseded += 1
            continue
        if status != "CURRENT":
            continue
        body_lines = [
            ln
            for ln in body.splitlines()
            if ln.strip()
            and not ln.startswith("date:")
            and not ln.startswith("status:")
            and not ln.startswith("valid_as_of:")
            and not ln.startswith("supersedes:")
            and not ln.startswith("##")
            and not ln.startswith("probe-assert:")
        ]
        prose = " ".join(body_lines)
        if PADDING_RULING.search(prose):
            padding_current += 1
            continue
        line, snip = find_snippet_line(rel, heading)
        current_real.append(
            {
                "id": heading.split()[0],
                "heading": heading,
                "line": line,
                "snippet": snip,
                "prose": prose[:500],
            }
        )
    return {
        "present": True,
        "current_real": current_real,
        "padding_current": padding_current,
        "superseded": superseded,
    }


def build_constraints() -> dict[str, Any]:
    stated: list[dict] = []
    inferred: list[dict] = []
    observations: list[dict] = []
    coverage: list[dict] = []

    owner_lin = file_lineage(OWNER_REL)
    coverage.append(
        {
            "source": "OWNER-DECISIONS.md",
            "path": OWNER_REL,
            "present": owner_lin["present"],
            "role": "named-primary",
            "note": (
                "Live file holds ARC-0077 only: unsigned DEFAULT-APPLIED OVERRIDE, "
                "lock_in_force=false. It does not currently record PR-ONLY."
            ),
            "lineage": owner_lin,
        }
    )

    log_meta = parse_decision_log_current()
    log_lin = file_lineage(DECISION_LOG_REL)
    coverage.append(
        {
            "source": "17-DECISION-LOG",
            "path": DECISION_LOG_REL,
            "present": log_meta["present"],
            "role": "named-primary-reconstructed",
            "note": (
                "File is present as a CC-0022 reconstruction of the option-id "
                "collision log. CURRENT real entries are the family-M census and "
                "the closed collision. Padding keep-WF-NNNN rulings are "
                "reconstruction filler and are not treated as owner constraints. "
                "The file does not contain PR-ONLY / DELETE-ALL / salvage-home / "
                "no-remote text."
            ),
            "current_real_ids": [e["id"] for e in log_meta.get("current_real") or []],
            "padding_current": log_meta.get("padding_current"),
            "lineage": log_lin,
        }
    )

    opt_rel = first_present(OPTION_UNIVERSE_CANDIDATES)
    coverage.append(
        {
            "source": "07-OPTION-UNIVERSE",
            "path": opt_rel or "07-OPTION-UNIVERSE.json",
            "present": bool(opt_rel),
            "role": "named-primary",
            "note": (
                "ABSENT. OQ-1 accepts 70 owner_decisions from that file; without "
                "the file the 70-id membership list cannot be checked. The family-M "
                "slice is an option-id collision fixture, not the 70-id list."
            ),
            "lineage": file_lineage(opt_rel)
            if opt_rel
            else file_lineage("07-OPTION-UNIVERSE.json"),
        }
    )
    slice_lin = file_lineage(FAMILY_M_SLICE)
    coverage.append(
        {
            "source": "07-OPTION-UNIVERSE.family-M-slice",
            "path": FAMILY_M_SLICE,
            "present": slice_lin["present"],
            "role": "wrong-document-control",
            "note": (
                "Present CC-0022 slice of family M option cards. Not the OQ-1 "
                "owner_decisions list."
            ),
            "lineage": slice_lin,
        }
    )
    p3 = file_lineage(PHASE3_LOG)
    coverage.append(
        {
            "source": "phase3/DECISION-LOG.md",
            "path": PHASE3_LOG,
            "present": p3["present"],
            "role": "wrong-document-control",
            "note": "ARC-0077 packet pointer only; not 17-DECISION-LOG.md.",
            "lineage": p3,
        }
    )
    cat_lin = file_lineage(CATALOG_REL)
    coverage.append(
        {
            "source": "catalog-owner_questions",
            "path": CATALOG_REL,
            "present": True,
            "role": "live-stand-in",
            "note": (
                "ANSWERED owner_questions are the live, quoteable owner-decision "
                "record on this sparse tree."
            ),
            "lineage": cat_lin,
        }
    )

    oqs = {row["id"]: row for row in answered_owner_questions()}

    rel, line, snip = oq_anchor("OQ-3", '"answer": "PR-ONLY."')
    stated.append(
        make_constraint(
            cid="BC-OQ-3-PR-ONLY",
            kind="STATED",
            binding=True,
            authority="OWNER-STATED",
            owner_confirmation_required=False,
            title="Release mode is PR-ONLY",
            normative_text=(
                "Recommendations must propose pull requests only. A private canary "
                "and a public marketplace release are ruled out. Phase 15 branches "
                "on this decision."
            ),
            quote="PR-ONLY",
            rel=rel,
            line=line,
            confidence_band="almost-certain",
            forbidden_release_modes=[
                "PUBLIC-CANARY",
                "PRIVATE-CANARY",
                "PUBLIC-MARKETPLACE",
                "MARKETPLACE",
            ],
            forbidden_patterns=[
                {"id": "public-canary", "regex": r"(?i)public\s+canary"},
                {"id": "private-canary", "regex": r"(?i)private\s+canary"},
                {
                    "id": "canary-channel",
                    "regex": r"(?i)canary\s+(channel|path|release|deployment|track)",
                },
                {
                    "id": "marketplace-publish",
                    "regex": r"(?i)(public\s+marketplace|marketplace\s+(publish|release))",
                },
            ],
            notes=snip,
        )
    )

    rel, line, snip = oq_anchor(
        "OQ-9", "No deployment target is created, consistent with OQ-3 = PR-ONLY."
    )
    stated.append(
        make_constraint(
            cid="BC-OQ-9-CANARY-SUBSTITUTE",
            kind="STATED",
            binding=True,
            authority="DELEGATED-DEFAULT",
            owner_confirmation_required=False,
            title="Canary substitute is a PR-head CI rehearsal, not a deployment",
            normative_text=(
                "Under PR-ONLY, the canary gate is replaced by a green CI run on "
                "the PR head exercising install -> upgrade -> rollback against a "
                "throwaway prefix, plus the documented rollback procedure. No "
                "deployment target is created."
            ),
            quote="No deployment target is created, consistent with OQ-3 = PR-ONLY.",
            rel=rel,
            line=line,
            confidence_band="likely",
            forbidden_patterns=[
                {
                    "id": "canary-deployment-target",
                    "regex": (
                        r"(?i)(deployment\s+target).{0,80}canary|"
                        r"canary.{0,80}(deployment\s+target)"
                    ),
                }
            ],
            notes=snip,
        )
    )

    rel, line, snip = oq_anchor(
        "OQ-4", "NO - the 38-item tranche was NOT an approved substitute."
    )
    stated.append(
        make_constraint(
            cid="BC-OQ-4-NO-38-TRANCHE",
            kind="STATED",
            binding=True,
            authority="OWNER-STATED",
            owner_confirmation_required=False,
            title="38-item harness tranche is not Prompt Two",
            normative_text=(
                "Do not recommend treating the 38-item harness tranche as an "
                "approved substitute for Prompt Two. The owner selected the full "
                ">=2,048-unit Prompt Two."
            ),
            quote="the 38-item tranche was NOT an approved substitute",
            rel=rel,
            line=line,
            confidence_band="almost-certain",
            forbidden_patterns=[
                {
                    "id": "38-as-prompt-two",
                    "regex": (
                        r"(?i)38[- ]item\s+tranche.{0,80}"
                        r"(prompt\s+two|approved substitute)"
                    ),
                }
            ],
            notes=snip,
        )
    )

    rel, line, snip = oq_anchor(
        "OQ-1",
        "The 70 `owner_decisions` in 07-OPTION-UNIVERSE.json (delegated default).",
    )
    stated.append(
        make_constraint(
            cid="BC-OQ-1-SEVENTY-IDS",
            kind="STATED",
            binding=True,
            authority="DELEGATED-DEFAULT",
            owner_confirmation_required=False,
            title="Selected option IDs are the 70 owner_decisions (file absent)",
            normative_text=(
                "OQ-1 accepts the 70 owner_decisions in 07-OPTION-UNIVERSE.json "
                "verbatim. Partial ids quoted in the catalog: A-01, A-03, A-12, "
                "A-13, A-17, A-18. The full membership list is NOT-CHECKED because "
                "07-OPTION-UNIVERSE.json is absent. A recommendation that discards "
                "that list is non-compliant; a recommendation that invents the "
                "missing 70 ids is overclaim."
            ),
            quote="Accept the existing list verbatim (A-01, A-03, A-12, A-13, A-17, A-18",
            rel=rel,
            line=line,
            confidence_band="likely",
            forbidden_patterns=[
                {
                    "id": "discard-oq1",
                    "regex": r"(?i)(replace|reject|discard).{0,60}(70\s+`?owner_decisions|OQ-1)",
                }
            ],
            notes=snip,
        )
    )

    rel, line, snip = oq_anchor(
        "OQ-2", "Phase order, then unblocking power (delegated default)."
    )
    stated.append(
        make_constraint(
            cid="BC-OQ-2-PHASE-THEN-UNBLOCK",
            kind="STATED",
            binding=True,
            authority="DELEGATED-DEFAULT",
            owner_confirmation_required=False,
            title="Execute in ascending phase, then unblocking power",
            normative_text=(
                "Within the program, execute in ascending phase (0 -> 16); within "
                "a phase take the unit that unblocks the most downstream units first."
            ),
            quote="Execute in ascending phase (0 -> 16, letter sub-phases in place)",
            rel=rel,
            line=line,
            confidence_band="likely",
            forbidden_patterns=[
                {
                    "id": "reverse-phase-order",
                    "regex": (
                        r"(?i)(execute|schedule|prioritise|prioritize)"
                        r".{0,40}(descending phase|phase 16.*first)"
                    ),
                }
            ],
            notes=snip,
        )
    )

    rel, line, snip = oq_anchor(
        "OQ-8",
        "Enrol the monitor cockpit at the same priority as the other MONITOR rows",
    )
    stated.append(
        make_constraint(
            cid="BC-OQ-8-COCKPIT-MONITOR-PRIORITY",
            kind="STATED",
            binding=True,
            authority="DELEGATED-DEFAULT",
            owner_confirmation_required=False,
            title="Monitor cockpit enrols at ordinary MONITOR priority",
            normative_text=(
                "Enrol the monitor cockpit into the unified contract at the same "
                "priority as other MONITOR rows; do not privilege it over remaining "
                "R-M rows."
            ),
            quote="same priority as the other MONITOR rows",
            rel=rel,
            line=line,
            confidence_band="likely",
            forbidden_patterns=[
                {
                    "id": "cockpit-outranks",
                    "regex": r"(?i)(cockpit).{0,40}(outrank|higher priority than|privilege)",
                }
            ],
            notes=snip,
        )
    )

    rel, line, snip = oq_anchor(
        "OQ-10",
        "A bucket dependency is satisfied by a bucket-level gate artifact",
    )
    stated.append(
        make_constraint(
            cid="BC-OQ-10-BUCKET-GATE",
            kind="STATED",
            binding=True,
            authority="DELEGATED-DEFAULT",
            owner_confirmation_required=False,
            title="Bucket dependencies are bucket-level gates, not all-members-done",
            normative_text=(
                "A B\\d+ bucket dependency is satisfied by a bucket-level gate "
                "artifact. The rejected alternative 'all members done' leaves the "
                "edges unsatisfiable."
            ),
            quote="Rejected alternative: 'all members done'",
            rel=rel,
            line=line,
            confidence_band="likely",
            forbidden_patterns=[
                {
                    "id": "all-members-done",
                    "regex": r"(?i)bucket.{0,40}(all members done|every member complete)",
                }
            ],
            notes=snip,
        )
    )

    if log_meta["present"]:
        for entry in log_meta["current_real"]:
            if entry["id"] == "DL-0042-R1":
                q = "Literal shared-id count is 0. P2-09 applied."
                qline, _ = find_snippet_line(DECISION_LOG_REL, q)
                stated.append(
                    make_constraint(
                        cid="BC-DL-0042-R1-COLLISION-CLOSED",
                        kind="STATED",
                        binding=True,
                        authority="DECISION-LOG-CURRENT",
                        owner_confirmation_required=False,
                        title="Option-id collision is closed; do not treat it as live",
                        normative_text=(
                            "DL-0042-R1 records the 31-way option-id collision as "
                            "closed by MECH-NN re-prefix. A research recommendation "
                            "that treats the collision as still live contradicts the "
                            "current log. SUPERSEDED DL-0042 wording is retained but "
                            "is not current."
                        ),
                        quote=q,
                        rel=DECISION_LOG_REL,
                        line=qline,
                        confidence_band="almost-certain",
                        forbidden_patterns=[
                            {
                                "id": "collision-still-live",
                                "regex": r"(?i)31-way option-id collision.{0,60}\bis live\b",
                            }
                        ],
                        notes=entry["snippet"],
                    )
                )
            elif entry["id"] == "DL-0001":
                q = "07-OPTION-UNIVERSE family M holds 33 ids"
                qline, _ = find_snippet_line(DECISION_LOG_REL, q)
                stated.append(
                    make_constraint(
                        cid="BC-DL-0001-FAMILY-M-CENSUS",
                        kind="STATED",
                        binding=True,
                        authority="DECISION-LOG-CURRENT",
                        owner_confirmation_required=False,
                        title="Family M census is 33 ids as of 2026-08-07",
                        normative_text=(
                            "DL-0001 records 07-OPTION-UNIVERSE family M as 33 ids. "
                            "A recommendation that asserts a different live census "
                            "without a new measurement contradicts the current log."
                        ),
                        quote=q,
                        rel=DECISION_LOG_REL,
                        line=qline,
                        confidence_band="likely",
                        notes=entry["snippet"],
                    )
                )

    if (REPO / OWNER_REL).is_file():
        unsigned_needle = "delegated default, NOT an owner-authored"
        line, snip = find_snippet_line(OWNER_REL, unsigned_needle)
        observations.append(
            make_constraint(
                cid="OBS-ARC-0077-UNSIGNED-OVERRIDE",
                kind="STATED",
                binding=False,
                authority="UNSIGNED-DEFAULT",
                owner_confirmation_required=True,
                title="ARC-0077 OVERRIDE is not an owner signature",
                normative_text=(
                    "OWNER-DECISIONS records delegated defaults that are not "
                    "owner-authored selections. Research must not treat a "
                    "delegated-default row as an owner ruling that A2 is forbidden."
                ),
                quote=unsigned_needle,
                rel=OWNER_REL,
                line=line,
                confidence_band="almost-certain",
                notes=snip,
            )
        )

    prose_needle = (
        "release mode = PR-ONLY; retirement scope = DELETE-ALL across five trees"
    )
    prose_line, prose_snip = find_snippet_line(CATALOG_REL, prose_needle)
    inferred.append(
        make_constraint(
            cid="INF-RETIRE-DELETE-ALL",
            kind="INFERRED",
            binding=False,
            authority="CATALOG-PROSE",
            owner_confirmation_required=True,
            title="Retirement scope DELETE-ALL across five trees (inferred)",
            normative_text=(
                "BLD-0014's question names retirement scope = DELETE-ALL across "
                "five trees as normative content of OWNER-DECISIONS.md / "
                "17-DECISION-LOG.md. Those files do not currently hold that text "
                "on this worktree, so the constraint is INFERRED and not binding "
                "until an owner-signed source quotes it."
            ),
            quote="retirement scope = DELETE-ALL across five trees",
            rel=CATALOG_REL,
            line=prose_line,
            confidence_band="roughly-even",
            notes=prose_snip,
        )
    )
    inferred.append(
        make_constraint(
            cid="INF-SALVAGE-TOOLS-LIB",
            kind="INFERRED",
            binding=False,
            authority="CATALOG-PROSE",
            owner_confirmation_required=True,
            title="Salvage home tools/lib/ (inferred)",
            normative_text=(
                "Catalog prose names salvage home = tools/lib/. Not quoted from "
                "OWNER-DECISIONS.md or 17-DECISION-LOG.md on this tree."
            ),
            quote="salvage home = tools/lib/",
            rel=CATALOG_REL,
            line=prose_line,
            confidence_band="roughly-even",
            notes=prose_snip,
        )
    )
    inferred.append(
        make_constraint(
            cid="INF-NO-REMOTE-TRIAGE",
            kind="INFERRED",
            binding=False,
            authority="CATALOG-PROSE",
            owner_confirmation_required=True,
            title="No-remote repos: triage first, never create remotes (inferred)",
            normative_text=(
                "Catalog prose names no-remote repos = triage first, never create "
                "remotes. Not quoted from OWNER-DECISIONS.md or 17-DECISION-LOG.md "
                "on this tree."
            ),
            quote="no-remote repos = triage first, never create remotes",
            rel=CATALOG_REL,
            line=prose_line,
            confidence_band="roughly-even",
            notes=prose_snip,
        )
    )

    inputs_needle = "_USER-PROMPTS.md:10526 (do not re-ask answered questions)"
    try:
        in_line, in_snip = find_snippet_line(CATALOG_REL, inputs_needle)
        inferred.append(
            make_constraint(
                cid="INF-DO-NOT-REASK",
                kind="INFERRED",
                binding=False,
                authority="CATALOG-INPUT-CITATION",
                owner_confirmation_required=True,
                title="Do not re-ask answered questions (spec file absent)",
                normative_text=(
                    "RES-0183 inputs cite _USER-PROMPTS.md:10526. That file is "
                    "absent here; the rule is recorded as INFERRED from the catalog "
                    "citation, not from the spec bytes."
                ),
                quote="do not re-ask answered questions",
                rel=CATALOG_REL,
                line=in_line,
                confidence_band="likely",
                notes=in_snip,
            )
        )
    except KeyError:
        pass

    return {
        "stated": stated,
        "inferred": inferred,
        "observations": observations,
        "coverage": coverage,
        "answered_oq_ids": sorted(oqs.keys()),
        "oq_count_json": len(oqs),
        "distinct_from_res_0127": (
            "RES-0127 asks which research artifacts exist only in one of two "
            "corpus trees. This unit extracts binding owner constraints and a "
            "checker. It does not emit a two-tree union manifest."
        ),
    }
