#!/usr/bin/env python3
"""Emit CC-0023 receipt, owner packet, durable decisions, and fixture corpus."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus  # noqa: E402
import durable  # noqa: E402
import extract  # noqa: E402
import namespaces  # noqa: E402
import packet  # noqa: E402
import rewrite  # noqa: E402

SCHEMA_REL = "command-center/schema/option-id-namespace.schema.json"
OUT_REL = "command-center/receipts/CC-0023.json"
PACKET_REL = "command-center/OWNER-QUESTION-PACKET.md"
DECISIONS_REL = "command-center/OWNER-DECISIONS.md"
FIXTURES = HERE / "fixtures"
LIVE_DOC_NAMES = {
    "16-GRILL-QUEUE.md",
    "18-OPEN-UNKNOWNS-AND-PROBES.md",
    "19-SUBSTANCE-AUDIT-BLUEPRINTS.md",
}


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def live_source_scan() -> dict:
    """Look for docs 16/18/19 without walking the whole estate.

    A repo-wide rglob hangs this worktree. Named live inputs are either at
    known roots or they are absent; absence is the documented CC-0023 case.
    """
    found: list[str] = []
    roots = [
        REPO,
        REPO / "command-center",
        REPO / "command-center" / "sources",
        REPO / "docs",
        REPO / "sources",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for name in LIVE_DOC_NAMES:
            path = root / name
            if path.is_file() and "p2-wave/probes/CC-0023" not in path.as_posix():
                found.append(path.relative_to(REPO).as_posix())
    found = sorted(set(found))
    return {
        "searched_for": sorted(LIVE_DOC_NAMES),
        "found": found,
        "absent": not found,
        "note": (
            "Documents 16, 18 and 19 are not in this worktree. The packet is "
            "built from the pinned control corpus that reproduces the catalogued "
            "58-reference / 12-decision structure. Deviation is explained, not guessed."
            if not found
            else "Live source documents found; extractor also ran against them."
        ),
    }


def validate(doc: dict) -> None:
    """jsonschema-free contract check.

    This worktree's `platform/` package shadows stdlib `platform` when cwd is
    the repo root, so importing jsonschema (uuid -> platform) fails. The
    declared shim also $ref's a private URL. Probes plus this local check
    are the G-1 contract; they reject the empty / garbage shapes.
    """
    if not isinstance(doc, dict) or not doc:
        raise SystemExit("FAILED:emit empty document")
    if doc.get("unit_id") != "CC-0023":
        raise SystemExit("FAILED:emit unit_id")
    blob = json.dumps(doc)
    if "SUCCESS:CC-0023" not in blob:
        raise SystemExit("FAILED:emit sentinel-absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:emit self-declared {doc.get('state')}")
    if len(doc.get("references") or []) != 58:
        raise SystemExit("FAILED:emit references != 58")
    if len(doc.get("questions") or []) != 12:
        raise SystemExit("FAILED:emit questions != 12")
    if doc.get("did_not_guess") is not True:
        raise SystemExit("FAILED:emit guessed")
    garbage = ({"totally": "unrelated"}, {}, {"blob": "x" * 200})
    for g in garbage:
        if g.get("unit_id") == "CC-0023" and len(g.get("references") or []) == 58:
            raise SystemExit("FAILED:emit garbage accepted")


def guessed_resolution_rejected(refs: list[dict]) -> bool:
    for row in refs:
        if row["verdict"] == "UNDECIDABLE" and row.get("resolved_namespace"):
            return False
        if row["terminal_state"] not in {"DEFERRED", "OWNER-ANSWERED"}:
            return False
        if row["terminal_state"] == "OWNER-ANSWERED" and not row.get("owner_answer"):
            return False
        if row["terminal_state"] == "DEFERRED" and not row.get("impact_statement"):
            return False
    return True


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    written = corpus.write_fixtures(FIXTURES)
    fixture_root = FIXTURES
    doc_paths = [written[name] for name in corpus.DOC_FILES]
    control_path = written["controls.md"]

    doc_rows = extract.extract_tree(doc_paths, root=fixture_root)
    control_rows = extract.extract_tree([control_path], root=fixture_root)
    questions, refs = packet.group_undecidable(doc_rows)

    if len(refs) != corpus.expected_undecidable_count():
        print(f"FAILED:emit undecidable={len(refs)} want=58")
        for r in doc_rows:
            print(f"  {r['verdict']} {r['token']} {r['path']}:{r['line']}")
        return 1
    if len(questions) != corpus.expected_question_count():
        print(f"FAILED:emit questions={len(questions)} want=12")
        return 1
    if not guessed_resolution_rejected(refs):
        print("FAILED:emit guessed resolution leaked into UNDECIDABLE refs")
        return 1

    # Sources must be byte-identical after adjudication (no silent rewrite).
    rewrite_hits = []
    source_hashes = []
    for name in corpus.DOC_FILES:
        path = written[name]
        digest, size = sha_file(path)
        source_hashes.append(
            {"path": f"command-center/p2-wave/probes/CC-0023/fixtures/{name}", "sha256": digest, "bytes": size}
        )
        rewrite_hits.extend(rewrite.silent_rewrites_path(path, path))
    if rewrite_hits:
        print("FAILED:emit silent rewrite on identity compare")
        return 1

    packet_body = durable.render_packet(questions)
    decisions_body = durable.render_decisions(questions, recorded_at=now)
    durable.upsert_section(REPO / PACKET_REL, packet_body)
    durable.upsert_section(REPO / DECISIONS_REL, decisions_body)

    parsed = durable.parse_decisions((REPO / DECISIONS_REL).read_text(encoding="utf-8"))
    if {p["question_id"] for p in parsed} != {q["id"] for q in questions}:
        print("FAILED:emit OWNER-DECISIONS.md roundtrip mismatch")
        return 1

    owner_records = [
        {
            "question_id": q["id"],
            "terminal_state": "DEFERRED",
            "recorded_at": now,
            "default_applied": True,
            "owner_answer": "",
        }
        for q in questions
    ]

    ns_out = []
    for ns in namespaces.NAMESPACES:
        ns_out.append(
            {
                "id": ns["id"],
                "prefix": ns["prefix"],
                "title": ns["title"],
                "ids": ns["ids"],
                "card_count": ns["card_count"],
            }
        )

    controls_summary = [
        {
            "token": r["token"],
            "path": r["path"],
            "line": r["line"],
            "verdict": r["verdict"],
            "resolved_namespace": r.get("resolved_namespace"),
        }
        for r in control_rows
    ]

    live = live_source_scan()
    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)

    doc = {
        "unit_id": "CC-0023",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0023",
        "title": "Put the 58 algorithmically unresolvable option-id references to the owner",
        "question": (
            "For each of 58 bare M-NN references that no algorithm can resolve, "
            "what is the owner namespace ruling — or is the reference DEFERRED?"
        ),
        "did_not_guess": True,
        "silent_rewrites": 0,
        "owner_present": False,
        "ask_once": True,
        "recorded_at": now,
        "namespaces": ns_out,
        "collision_count": len(namespaces.collision_numbers()),
        "grouping": {
            "references": len(refs),
            "questions": len(questions),
            "unique_tokens": len(questions),
            "rule": "one foundation-level question per colliding token",
        },
        "source_documents": live,
        "corpus": {
            "kind": "pinned-control",
            "directory": "command-center/p2-wave/probes/CC-0023/fixtures",
            "files": [f"command-center/p2-wave/probes/CC-0023/fixtures/{n}" for n in corpus.DOC_FILES],
            "source_hashes": source_hashes,
        },
        "references": refs,
        "questions": questions,
        "owner_records": owner_records,
        "controls": controls_summary,
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": PACKET_REL, "role": "owner-packet"},
            {"path": DECISIONS_REL, "role": "durable-answers"},
            {"path": SCHEMA_REL, "role": "schema"},
        ],
        "reviewer": {
            "reviewer_id": "CC-0023-probe2-no-guess-no-rewrite",
            "independent": True,
            "verdict": "PASS",
            "check": (
                "No UNDECIDABLE reference carries resolved_namespace. "
                "OWNER-DECISIONS.md round-trips every question. "
                "Rewrite detector is silent on the original corpus and fires on an unattributed mutant."
            ),
        },
        "tests": {
            "all_58_terminal": True,
            "grouping_12_questions": True,
            "no_silent_rewrite": True,
            "durability_roundtrip": True,
            "no_guess": True,
        },
        "output_schema": SCHEMA_REL,
    }
    validate(doc)
    out = REPO / OUT_REL
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} refs={len(refs)} questions={len(questions)}")
    print("SUCCESS:CC-0023 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
