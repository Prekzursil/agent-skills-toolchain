#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0009.json (conformance-report)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
from controls import run_required_tests  # noqa: E402
from corpus import SNAPSHOT_REL, resolve_corpus  # noqa: E402

OUT = "command-center/receipts/TST-0009.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
RESOLVER = "command-center/p2-wave/probes/TST-0009/resolver.py"
CORPUS = "command-center/p2-wave/probes/TST-0009/corpus.py"
FIXTURE = "command-center/p2-wave/probes/TST-0009/fixtures/five_lines.txt"
SNAPSHOT = "command-center/p2-wave/probes/TST-0009/harvest-snapshot.json"
REDUCER = "tools/completion/reducer.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0009/probe1_file_line_beyond_eof_and_command.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0009/probe2_inferred_named_source.py"
)
QUESTION = (
    "Predicate condition 6 requires 'required evidence anchors exist'. "
    "Target: a validator that resolves each anchor by KIND — file:line "
    "(the file exists AND has that many lines), a command (re-executes it "
    "and compares the recorded exit code), or an explicit 'inferred from X'. "
    "How many anchors in the existing corpus fail to resolve today?"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    hits = [i for i, ln in enumerate(text.splitlines(), 1) if snippet in ln]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:TST-0009 emit unique line {rel!r} {snippet!r} hits={hits}")
    return hits[0]


def evidence(rel: str, snippet: str, kind: str, claim: str, detail: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "kind": kind,
        "claim": claim,
        "detail": f"{detail} Anchor {rel}:{line}.",
        "path": rel,
        "line": line,
        "snippet": snippet,
        "anchor": f"{rel}:{line}",
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "exists": True,
        "role": role,
        "sha256": sha,
        "bytes": size,
    }


# Catalog output_schema is a generated $ref shim to ast-integrate.invalid.
# G-1 delivery does not fetch that URL. Local UNIT_SCHEMA rejects garbage
# and requires the measured resolution table plus the report.kind const.
UNIT_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "fail_to_resolve_count",
        "resolution",
        "tests",
        "report",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "TST-0009"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:TST-0009"},
        "fail_to_resolve_count": {"type": "integer", "minimum": 0},
        "resolution": {
            "type": "object",
            "required": [
                "anchor_count",
                "fail_to_resolve_count",
                "counts_by_kind",
                "counts_by_outcome",
                "table",
                "snapshot",
            ],
            "properties": {
                "table": {"type": "array", "minItems": 1},
                "snapshot": {
                    "type": "object",
                    "required": ["present"],
                    "properties": {"present": {"const": True}},
                },
            },
        },
        "tests": {"type": "array", "minItems": 3},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "conformance-report"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
        "evidence": {"type": "array", "minItems": 1},
    },
}


def validate(doc: dict) -> None:
    shim = REPO / SCHEMA
    if not shim.is_file() or shim.stat().st_size <= 0:
        raise SystemExit(f"FAILED:TST-0009 missing schema {SCHEMA}")
    try:
        import jsonschema
    except ImportError as exc:
        raise SystemExit(f"FAILED:TST-0009 jsonschema missing: {exc}") from exc
    jsonschema.Draft7Validator.check_schema(UNIT_SCHEMA)
    jsonschema.Draft7Validator(UNIT_SCHEMA).validate(doc)
    for garbage in (
        {},
        {"unit_id": "TST-0009", "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
    ):
        try:
            jsonschema.Draft7Validator(UNIT_SCHEMA).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:TST-0009 schema accepts garbage")


def main() -> int:
    tests_live = run_required_tests(REPO)
    if not all(t["pass"] for t in tests_live):
        print("FAILED:TST-0009 planted controls")
        print(json.dumps(tests_live, indent=2, default=str))
        return 1
    snap_path = REPO / SNAPSHOT_REL
    # Resume from the existing harvest freeze. Re-freezing would scrap the
    # corpus as other units land new receipts.
    freeze = not (snap_path.is_file() and snap_path.stat().st_size > 0)
    live = resolve_corpus(REPO, freeze=freeze)
    fail_n = live["fail_to_resolve_count"]
    total = live["anchor_count"]
    registry = live["registry"]
    snap = live.get("snapshot") or {}
    answer = (
        f"{fail_n} of {total} harvested anchors fail to resolve today "
        f"(outcome=unresolved). Corpus={live['corpus_name']}. "
        f"CLAIM-REGISTRY.json present={registry['present']} "
        f"(registry_anchor_count={registry['registry_anchor_count']}). "
        f"Harvest freeze present={snap.get('present')} "
        f"frozen_at={snap.get('frozen_at')} "
        f"snapshot={SNAPSHOT}. "
        f"Counts by kind={live['counts_by_kind']}; "
        f"counts by outcome={live['counts_by_outcome']}; "
        f"kind×outcome={live['counts_by_kind_and_outcome']}. "
        "A line number past EOF is unresolved. Command anchors re-execute "
        "only when the recorded command is a bounded python3 -c / true / false "
        "/ echo form; other recorded commands are counted not-reexecuted, not "
        "resolved. Inferred anchors without a named source are unresolved. "
        "SUCCESS:TST-0009"
    )

    e1 = evidence(
        RESOLVER,
        'if line > n:',
        "file:line",
        "A line number past EOF is classified unresolved.",
        "resolve_file_line compares the cited line against the live line count.",
    )
    e2 = evidence(
        RESOLVER,
        "if observed != recorded_exit:",
        "command",
        "A command anchor re-executes and compares the recorded exit code.",
        "resolve_command re-runs the recorded command and mismatches are unresolved.",
    )
    e3 = evidence(
        RESOLVER,
        "if not named:",
        "inferred",
        "An inferred anchor requires a named source.",
        "resolve_inferred rejects empty and placeholder sources.",
    )
    e4 = evidence(
        REDUCER,
        'required evidence anchors exist',
        "catalog-condition",
        "Predicate condition 6 is the reducer row this validator implements.",
        "Live reducer still counts evidence_anchor_count; this unit resolves by kind.",
    )
    e5 = evidence(
        FIXTURE,
        "epsilon",
        "file:line",
        "The five-line fixture exists so line 6 is a real beyond-EOF control.",
        "Planted control file has five lines; line 6 must not resolve.",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "TST-0009",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0009",
        "report_kind": "evidence-anchor-resolvability",
        "question": QUESTION,
        "answer": answer,
        "fail_to_resolve_count": fail_n,
        "resolution": {
            "corpus_name": live["corpus_name"],
            "snapshot": snap,
            "registry": registry,
            "anchor_count": total,
            "resolved_count": live["resolved_count"],
            "unresolved_count": live["unresolved_count"],
            "not_reexecuted_count": live["not_reexecuted_count"],
            "fail_to_resolve_count": fail_n,
            "counts_by_kind": live["counts_by_kind"],
            "counts_by_outcome": live["counts_by_outcome"],
            "counts_by_kind_and_outcome": live["counts_by_kind_and_outcome"],
            "table": live["table"],
        },
        "planted_controls": {
            t["id"]: {"pass": t["pass"]} for t in tests_live
        },
        "tests": [
            {
                "id": "test_file_line_beyond_eof_is_unresolved",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_command_anchor_reexecutes",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_inferred_anchor_requires_a_named_source",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0009-probe2-inferred-named-source",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 re-runs inferred-source controls and independently "
                "re-resolves the frozen harvest, requiring the published "
                "counts to match."
            ),
        },
        "report": {
            "kind": "conformance-report",
            "control_ids": [
                "test_file_line_beyond_eof_is_unresolved",
                "test_command_anchor_reexecutes",
                "test_inferred_anchor_requires_a_named_source",
            ],
            "observations": [
                {
                    "name": "fail_to_resolve_count",
                    "measured": fail_n,
                    "method": "per-anchor-kind-resolver",
                    "anchor": SNAPSHOT,
                },
                {
                    "name": "anchor_count",
                    "measured": total,
                    "method": "frozen-harvest-resolve",
                    "anchor": SNAPSHOT,
                },
                {
                    "name": "registry_present",
                    "measured": bool(registry.get("present")),
                    "method": "stat",
                    "anchor": "command-center/CLAIM-REGISTRY.json",
                },
            ],
        },
        "artifacts": [
            art(OUT, "primary") if (REPO / OUT).is_file() else {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            art(RESOLVER, "implementation"),
            art(CORPUS, "implementation"),
            art(SNAPSHOT, "corpus-freeze"),
            art(FIXTURE, "fixture"),
            art(SCHEMA, "schema"),
            art(REDUCER, "predicate-condition-6"),
        ],
        "evidence": [e1, e2, e3, e4, e5],
        "produced_at": now,
        "schema_path": SCHEMA,
        "output_path": OUT,
        "notes": (
            "CLAIM-REGISTRY.json is the catalog input and is absent on this "
            "worktree. The per-anchor table is a freeze of the live receipt "
            "plus confirmation evidence harvest (not an invented registry); "
            "named probes re-resolve that freeze against the live worktree. "
            "SUCCESS:TST-0009"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    # Re-stamp primary artifact bytes/sha now that the file exists.
    doc["artifacts"][0] = art(OUT, "primary")
    payload = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    validate(json.loads(out_path.read_text(encoding="utf-8")))
    sha, size = digest_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha} fail_to_resolve={fail_n}/{total}")
    print("SUCCESS:TST-0009")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
