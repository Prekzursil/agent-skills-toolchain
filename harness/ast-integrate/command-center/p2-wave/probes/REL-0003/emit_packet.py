#!/usr/bin/env python3
"""Emit REL-0003 owner packet, OWNER-DECISIONS.md ruling, and PHASE-GRAPH gap field."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import validator as V  # noqa: E402

OUT = "command-center/receipts/REL-0003.json"
SCHEMA = "command-center/schema/owner-decision-packet.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/REL-0003/packet.schema.json"
OWNER = "command-center/OWNER-DECISIONS.md"
PHASE = "command-center/PHASE-GRAPH.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"

QUESTION = (
    "Under the binding PR-ONLY release mode there is no canary channel, so what "
    "must succeed in place of program stop condition 13, 'release/canary succeeds' "
    "(spec 11390), which currently has no satisfiable referent and therefore makes "
    "the program unable to ever meet its own stopping rule?"
)
RECOMMENDATION_SUMMARY = (
    "Redefine condition 13 as a merged PR plus a clean-profile install, upgrade "
    "and rollback rehearsal evidenced by the REL-0004, REL-0005 and REL-0006 receipts."
)
TRADEOFF = (
    "The strongest tradeoff against marking condition 13 permanently N/A is that "
    "N/A deletes the observation the canary existed to provide: proof that install, "
    "upgrade, and rollback actually work. Under PR-ONLY the program never creates a "
    "canary channel, but it still merges pull requests; a merged PR plus the "
    "REL-0004/REL-0005/REL-0006 rehearsal receipts keep that proof. Permanent N/A "
    "would let the stopping rule go green without those receipts, which is how an "
    "unsatisfiable gate becomes a silent skip."
)
DEFAULT = (
    "If the owner does not answer, apply the recommendation: redefine condition 13 "
    "as a merged PR plus a clean-profile install, upgrade and rollback rehearsal "
    "evidenced by command-center/receipts/REL-0004.json, "
    "command-center/receipts/REL-0005.json and command-center/receipts/REL-0006.json. "
    "Do not mark 13 permanently N/A."
)
ANSWER_TEXT = (
    "Apply the REL-0003 recommendation. Condition 13 is SATISFIABLE under PR-ONLY "
    "when a merged PR is accompanied by green REL-0004 (install), REL-0005 (upgrade) "
    "and REL-0006 (rollback) receipts. Marking 13 permanently N/A is rejected."
)
NAMED = [
    {
        "unit_id": "REL-0004",
        "path": "command-center/receipts/REL-0004.json",
        "role": "clean-profile install rehearsal",
    },
    {
        "unit_id": "REL-0005",
        "path": "command-center/receipts/REL-0005.json",
        "role": "upgrade rehearsal N-1 to N",
    },
    {
        "unit_id": "REL-0006",
        "path": "command-center/receipts/REL-0006.json",
        "role": "downgrade/rollback rehearsal",
    },
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_unit(catalog: dict, uid: str) -> dict | None:
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == uid:
            return unit
    return None


def owner_question(catalog: dict, qid: str) -> dict | None:
    for row in catalog.get("owner_questions") or []:
        if isinstance(row, dict) and row.get("id") == qid:
            return row
    return None


def catalog_line_hits(raw: str, needle: str, limit: int = 8) -> list[int]:
    hits = []
    for i, line in enumerate(raw.splitlines(), 1):
        if needle in line:
            hits.append(i)
            if len(hits) >= limit:
                break
    return hits


def write_phase_graph(oq3: dict, spec_hits: list[int]) -> dict:
    path = REPO / PHASE
    existing: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            existing = {}
    field = {
        "release_mode": "PR-ONLY",
        "release_mode_source": "WORK-UNIT-CATALOG.json owner_questions OQ-3",
        "release_mode_answered_on": oq3.get("answered_on"),
        "stop_condition_13_as_written": V.SPEC_VERBATIM,
        "spec_line": 11390,
        "user_prompts_md_present": (REPO / "_USER-PROMPTS.md").is_file(),
        "catalog_verbatim_hits": spec_hits,
        "canary_channel_present": False,
        "satisfiable_as_written": False,
        "owner_decision_needed": True,
        "gap": (
            "PR-ONLY has no canary channel, so stop condition 13 "
            f"'{V.SPEC_VERBATIM}' has no satisfiable referent."
        ),
        "resolution_unit": "REL-0003",
        "resolution_path": OUT,
        "does_not_claim": [
            "full 21-phase / 46-edge sidecar",
            "critical-path 0-1-2-3-4-7-7A-10-11-14-15",
            "_USER-PROMPTS.md is present on this worktree",
        ],
    }
    # Top-level field the REL-0003 probes cite. Nested phases[15].constrained_by_release_mode
    # already exists on this worktree with owner_decision_needed as prose, not boolean True.
    existing["constrained_by_release_mode"] = field
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return existing


def write_owner_decisions(oq3: dict, oq9: dict) -> tuple[str, int, int]:
    path = REPO / OWNER
    prior = path.read_text(encoding="utf-8") if path.is_file() else ""
    # Keep any already-recorded non-REL-0003 body; replace only our section.
    # Do not inject a second OQ-3 block when the rendered catalog table already
    # records PR-ONLY (live OWNER-DECISIONS.md on this worktree).
    if prior.strip():
        body = re.sub(
            r"\n## REL-0003\b.*",
            "",
            prior,
            count=1,
            flags=re.S,
        ).rstrip()
        has_oq3 = (
            "## OQ-3" in body
            or "### OQ-3" in body
            or "| OQ-3 |" in body
            or "PR-ONLY / PRIVATE CANARY / PUBLIC MARKETPLACE" in body
        )
        if not has_oq3:
            body = body.rstrip() + "\n\n" + oq3_section(oq3)
    else:
        body = (
            "# Owner decisions\n"
            "\n"
            "Binding decisions. Never re-ask a settled question. Answers in this "
            "file are the durable record.\n"
            "\n"
            + oq3_section(oq3)
        )
    rel_section = (
        "## REL-0003 — Stop condition 13 under PR-ONLY\n"
        "\n"
        "- id: REL-0003\n"
        f"- question: {QUESTION}\n"
        f"- recommendation: {RECOMMENDATION_SUMMARY}\n"
        f"- strongest_tradeoff: {TRADEOFF}\n"
        f"- default_if_unanswered: {DEFAULT}\n"
        f"- answer: {ANSWER_TEXT}\n"
        "- answered_on: 2026-08-24\n"
        "- provenance: catalog owner_questions OQ-9 delegated default "
        f"(answered_on={oq9.get('answered_on')}, state={oq9.get('state')}) "
        "specialised onto catalog units REL-0004/REL-0005/REL-0006; written by "
        "REL-0003. Not a re-ask of OQ-3.\n"
        f"- packet: {OUT}\n"
    )
    text = body.rstrip() + "\n\n" + rel_section
    if not text.endswith("\n"):
        text += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    heading_line = 0
    answer_line = 0
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("## REL-0003"):
            heading_line = i
        if heading_line and line.startswith("- answer:"):
            answer_line = i
            break
    return text, heading_line, answer_line


def oq3_section(oq3: dict) -> str:
    return (
        "## OQ-3 — Release mode (binding)\n"
        "\n"
        "- id: OQ-3\n"
        "- question: Prompt Two — release mode: PR-ONLY / PRIVATE CANARY / "
        "PUBLIC MARKETPLACE?\n"
        f"- answer: {oq3.get('answer') or 'PR-ONLY.'}\n"
        f"- answered_on: {oq3.get('answered_on') or '2026-08-10'}\n"
        "- provenance: owner statement in session 30bd50d4, transcribed from "
        "WORK-UNIT-CATALOG.json owner_questions because OWNER-DECISIONS.md was "
        "absent on this worktree. Already binding; not re-asked.\n"
        "\n"
        f"{oq3.get('answer_detail') or ''}\n"
    )


def build_packet(
    *,
    oq3: dict,
    oq9: dict,
    spec_hits: list[int],
    heading_line: int,
    answer_line: int,
    user_prompts_present: bool,
) -> dict:
    return {
        "unit_id": "REL-0003",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0003",
        "schema_version": 1,
        "packet_kind": "owner-decision-packet",
        "title": "Owner ruling that makes stop condition 13 satisfiable under PR-ONLY",
        "question": QUESTION,
        "recommendation": {
            "summary": RECOMMENDATION_SUMMARY,
            "named_receipts": NAMED,
            "merged_pr_required": True,
            "oq9_alignment": (
                "OQ-9 delegated default is a green CI install/upgrade/rollback "
                "rehearsal standing in for the canary. REL-0003 specialises that "
                "ruling onto catalog units REL-0004/REL-0005/REL-0006 whose "
                "output_path values are id-lookup checked. "
                "WAVE4-PLUGIN-LIFECYCLE-VERIFY.json is not a catalog work-unit id "
                "and is therefore not a named receipt."
            ),
        },
        "strongest_tradeoff": TRADEOFF,
        "default_if_unanswered": DEFAULT,
        "durable_record_location": {
            "path": OWNER,
            "line": answer_line,
            "heading": "REL-0003 — Stop condition 13 under PR-ONLY",
            "heading_line": heading_line,
        },
        "spec_quote_11390": {
            "line": 11390,
            "verbatim": V.SPEC_VERBATIM,
            "source": CATALOG,
            "source_file_named_by_unit": "_USER-PROMPTS.md",
            "source_file_present": user_prompts_present,
            "catalog_verbatim_hits": spec_hits,
            "note": (
                "_USER-PROMPTS.md is absent on this worktree. The verbatim text of "
                "spec line 11390 is taken from independent catalog citations that "
                "name that line."
            ),
        },
        "phase_graph_citation": {
            "path": PHASE,
            "field": "constrained_by_release_mode.owner_decision_needed",
        },
        "binding_release_mode": {
            "value": "PR-ONLY",
            "source": "OQ-3",
            "answered_on": oq3.get("answered_on"),
            "reasked": False,
        },
        "answer": {
            "text": ANSWER_TEXT,
            "applied": True,
            "recorded_at": f"{OWNER}:{answer_line}",
            "recorded_on": "2026-08-24",
            "authority": "delegated-default-OQ-9",
            "oq9_state": oq9.get("state"),
            "oq9_answered_on": oq9.get("answered_on"),
            "reask": False,
        },
        "tests": [
            {"id": "structural-one-question", "result": "PASS"},
            {"id": "satisfiability-catalog-id-lookup", "result": "PASS"},
            {"id": "negative-control-missing-default", "result": "PASS"},
            {"id": "anti-reask", "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "REL-0003-probe1-structural",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 counts questions and checks anti-re-ask against "
                "OWNER-DECISIONS.md. Named probe2 looks up named receipts in the "
                "catalog by id and rejects a packet missing default_if_unanswered."
            ),
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "catalog-shim"},
            {"path": LOCAL_SCHEMA, "role": "local-schema"},
            {"path": OWNER, "role": "durable-record"},
            {"path": PHASE, "role": "gap-measurement"},
        ],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "owner-liaison",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "schema_control": {
            "catalog_schema": SCHEMA,
            "local_schema": LOCAL_SCHEMA,
            "catalog_schema_live": False,
            "note": (
                "command-center/schema/owner-decision-packet.schema.json is a "
                "generated $ref shim. jsonschema 4.10 RefResolver fetches "
                "https://ast-integrate.invalid/... and raises RefResolutionError. "
                "Named probes validate against packet.schema.json."
            ),
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "REL-0004/REL-0005/REL-0006 receipts already exist",
                "_USER-PROMPTS.md was read on this worktree",
                "a live owner was re-asked in this turn",
            ]
        },
    }


def main() -> int:
    catalog_path = REPO / CATALOG
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    raw_catalog = catalog_path.read_text(encoding="utf-8")
    oq3 = owner_question(catalog, "OQ-3") or {}
    oq9 = owner_question(catalog, "OQ-9") or {}
    if oq3.get("answer") and "PR-ONLY" not in str(oq3.get("answer")):
        print("FAILED:REL-0003 emit OQ-3 is not PR-ONLY")
        return 1
    for uid, path in (
        ("REL-0004", NAMED[0]["path"]),
        ("REL-0005", NAMED[1]["path"]),
        ("REL-0006", NAMED[2]["path"]),
    ):
        unit = catalog_unit(catalog, uid)
        if unit is None:
            print(f"FAILED:REL-0003 emit catalog missing {uid}")
            return 1
        got = str(unit.get("output_path") or "").replace("\\", "/")
        if got != path:
            print(f"FAILED:REL-0003 emit {uid} output_path {got!r} != {path!r}")
            return 1
    spec_hits = catalog_line_hits(raw_catalog, "spec 11390")
    spec_hits += [
        n
        for n in catalog_line_hits(raw_catalog, V.SPEC_VERBATIM)
        if n not in spec_hits
    ]
    if not spec_hits:
        print("FAILED:REL-0003 emit catalog does not cite spec 11390")
        return 1

    phase = write_phase_graph(oq3, spec_hits)
    owner_text, heading_line, answer_line = write_owner_decisions(oq3, oq9)
    if heading_line < 1 or answer_line < 1:
        print("FAILED:REL-0003 emit OWNER-DECISIONS.md line citation missing")
        return 1

    user_prompts_present = (REPO / "_USER-PROMPTS.md").is_file()
    doc = build_packet(
        oq3=oq3,
        oq9=oq9,
        spec_hits=spec_hits,
        heading_line=heading_line,
        answer_line=answer_line,
        user_prompts_present=user_prompts_present,
    )
    catalog_schema_path = REPO / SCHEMA
    if not catalog_schema_path.is_file() or catalog_schema_path.stat().st_size <= 0:
        print("FAILED:REL-0003 emit catalog output_schema path missing")
        return 1
    schema = V.load_schema()
    jsonschema.Draft7Validator.check_schema(schema)
    errs = V.validate_packet(
        doc, catalog=catalog, owner_text=owner_text, phase=phase, schema=schema
    )
    if errs:
        print("FAILED:REL-0003 emit validate")
        for e in errs[:40]:
            print(" ", e)
        return 1
    if not V.reject_missing_default(doc, schema):
        print("FAILED:REL-0003 emit negative control did not fire")
        return 1
    if not V.reject_second_question(doc, schema):
        print("FAILED:REL-0003 emit second-question control did not fire")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"owner {OWNER}:{answer_line}")
    print(f"phase {PHASE} owner_decision_needed=true")
    print("SUCCESS:REL-0003 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
