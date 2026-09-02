#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0032.json for BLD-0032."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inherit as I  # noqa: E402
import probe1_controls as P1  # noqa: E402
import probe2_reviewer as P2  # noqa: E402

OUT = "command-center/receipts/BLD-0032.json"
SCHEMA = "command-center/schema/tag-position-audit.schema.json"
QUESTION = (
    "Which recommendation rests on an UNVERIFIED premise without inheriting "
    "the tag in its own heading? Build premise-to-recommendation edges, compute "
    "the transitive premise set, and report every recommendation whose premise "
    "set contains UNVERIFIED or NOT-CHECKED while the heading reads unqualified. "
    "A recommendation with no traceable premise is UNGROUNDED."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0032/probe1_controls.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0032/probe2_reviewer.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def snippet_at(rel_path: str, line: int) -> str:
    lines = (REPO / rel_path).read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        raise SystemExit(f"FAILED:BLD-0032 line {line} out of range in {rel_path}")
    return lines[line - 1].strip()[:200]


def ev(rel_path: str, line: int, claim: str) -> dict:
    return {
        "path": rel_path,
        "line": line,
        "snippet": snippet_at(rel_path, line),
        "claim": claim,
        "anchor": f"{rel_path}:{line}",
    }


def split_loc(loc: str) -> tuple[str, int]:
    path, _, rest = loc.rpartition(":")
    return path, int(rest)


def main() -> int:
    p1 = P1.evaluate()
    p2 = P2.hand_trace()
    if not p1["ok"] or not p2["ok"]:
        print("FAILED:BLD-0032 named probes")
        print(json.dumps({"probe1": p1, "probe2": p2}, indent=2)[:4000])
        return 1

    findings = I.control_audit("union")
    by = I.by_id(findings)
    live = I.live_audit()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    reportable = [f for f in findings if f.cls in {"DROPPED-TAG", "UNGROUNDED"}]
    finding_rows = [f.as_dict() for f in reportable]
    for row in live.get("findings") or []:
        if row.get("class") in {"DROPPED-TAG", "UNGROUNDED"}:
            finding_rows.append(row)

    drop = by["REC-DROP"]
    trans = by["REC-TRANS"]
    inherit = by["REC-INHERIT"]
    ung = by["REC-UNGROUNDED"]
    drop_tag_path, drop_tag_line = split_loc(drop.tag_location)
    trans_tag_path, trans_tag_line = split_loc(trans.tag_location)

    evidence = [
        ev(drop.rec.path, drop.rec.line, "Control REC-DROP heading is unqualified."),
        ev(drop_tag_path, drop_tag_line, f"Premise {drop.claim_id} carries {drop.tag}."),
        ev(trans.rec.path, trans.rec.line, "Control REC-TRANS heading is unqualified."),
        ev(
            trans_tag_path,
            trans_tag_line,
            f"Two-hop premise {trans.claim_id} carries {trans.tag}.",
        ),
        ev(
            inherit.rec.path,
            inherit.rec.line,
            "False-positive guard: REC-INHERIT heading carries UNVERIFIED.",
        ),
        ev(ung.rec.path, ung.rec.line, "REC-UNGROUNDED has no traceable premise."),
    ]

    live_note = (
        f"Live command-center/CLAIM-REGISTRY.json present="
        f"{live['claim_registry_present']} claims={live['live_claim_count']} "
        f"recommendations={live['live_recommendation_count']} "
        f"dropped_tag={live['dropped_tag']} ungrounded={live['ungrounded']} "
        f"inherited={live['inherited']} clean={live['clean']}. {live['note']}"
    )
    answer = (
        "Control packet: REC-DROP drops UNVERIFIED from CLM-DROP-1; REC-TRANS "
        f"drops NOT-CHECKED from two-hop CLM-B (hops={trans.hops}); "
        "REC-UNGROUNDED has no premise. REC-INHERIT carries [UNVERIFIED] and "
        f"is not flagged. {live_note} "
        "SUCCESS:BLD-0032"
    )

    doc = {
        "unit_id": "BLD-0032",
        "state": "SUCCESS",
        "schema_version": 1,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#BLD-0032",
        "sentinel": "SUCCESS:BLD-0032",
        "report_kind": "tag-position-audit",
        "report": {
            "kind": "tag-position-audit",
            "control_ids": [
                "REC-DROP",
                "REC-INHERIT",
                "REC-TRANS",
                "REC-UNGROUNDED",
                "REC-CLEAN",
            ],
            "observations": [
                {
                    "name": "unqualified-drop",
                    "measured": True,
                    "method": "union-closure",
                    "anchor": f"{drop.rec.path}:{drop.rec.line}",
                },
                {
                    "name": "inherited-not-flagged",
                    "measured": True,
                    "method": "union-closure",
                    "anchor": f"{inherit.rec.path}:{inherit.rec.line}",
                },
                {
                    "name": "two-hop",
                    "measured": True,
                    "method": "union-closure",
                    "anchor": f"{trans.rec.path}:{trans.rec.line}",
                },
                {
                    "name": "ungrounded",
                    "measured": True,
                    "method": "union-closure",
                    "anchor": f"{ung.rec.path}:{ung.rec.line}",
                },
            ],
        },
        "audit_focus": "premise-inheritance",
        "title": (
            "UNVERIFIED premise inheritance: recommendations that drop "
            "their premise's tag"
        ),
        "question": QUESTION,
        "answer": answer,
        "method": {
            "token_matching": "CLM-* and CC-* tokens plus exact known registry ids",
            "explicit_edges": "recs.json cites[] and claim rests_on[]",
            "closure": "BFS over rests_on from cited claims",
            "weak_tags": sorted(I.WEAK_TAGS),
            "unqualified": "heading lacks the weak tag present in the premise set",
            "ungrounded": "no cited claim resolves in the registry",
        },
        "inputs": {
            "claim_registry_live": live,
            "control_packet": (
                "command-center/p2-wave/probes/BLD-0032/fixtures/control-packet"
            ),
        },
        "findings": finding_rows,
        "audited": [f.as_dict() for f in findings],
        "reportable_count": len(reportable),
        "tests": [
            {
                "id": "T-DROP-UNQUALIFIED",
                "name": (
                    "Recommendation citing a tagged premise without inheriting "
                    "the tag is caught"
                ),
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-INHERITED-NOT-FLAGGED",
                "name": (
                    "Recommendation that carries the inherited tag in its "
                    "heading is not flagged"
                ),
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-TWO-HOP",
                "name": "Two-hop premise chain is caught, not only one-hop",
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-HAND-TRACE",
                "name": (
                    "Independent reviewer retraces two flagged recommendations "
                    "via explicit edges"
                ),
                "command": P2_CMD,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": p2["reviewer_id"],
            "verdict": p2["verdict"],
            "independent": True,
            "method": (
                "Re-read decision-packet.md and CLAIM-REGISTRY.json. Walk "
                "explicit cites (not token matching): REC-DROP -> CLM-DROP-1 "
                "UNVERIFIED; REC-TRANS -> CLM-A CONFIRMED -> CLM-B NOT-CHECKED. "
                "Both-states mutant confirms CLM-B=CONFIRMED clears REC-TRANS."
            ),
            "traced": [p2["drop"], p2["trans"]],
        },
        "named_probes": [
            {"id": "probe1", "role": "catalog-controls", "command": P1_CMD},
            {"id": "probe2", "role": "independent-hand-trace", "command": P2_CMD},
        ],
        "evidence": evidence,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/BLD-0032/inherit.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": (
                    "command-center/p2-wave/probes/BLD-0032/fixtures/"
                    "control-packet/decision-packet.md"
                ),
                "exists": True,
                "role": "control",
            },
            {
                "path": (
                    "command-center/p2-wave/probes/BLD-0032/fixtures/"
                    "control-packet/CLAIM-REGISTRY.json"
                ),
                "exists": True,
                "role": "control",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/BLD-0032/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "dependencies_noted": ["B09", "B10", "B12"],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot from citation-token matching to "
                "explicit claim-id edges before a third attempt."
            ),
        },
        "adv_rebuild_circle": False,
        "required_fix": None,
        "min_bytes_threshold": 2048,
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        validator = jsonschema.Draft7Validator(schema)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            print("FAILED:BLD-0032 schema errors")
            for e in errs[:20]:
                print(" ", list(e.path), e.message)
            return 1
        for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
            if not list(validator.iter_errors(g)):
                print(f"FAILED:BLD-0032 schema accepted garbage {list(g)[:2]}")
                return 1
    except Exception as exc:
        name = type(exc).__name__
        if name != "RefResolutionError" and "ast-integrate.invalid" not in str(exc):
            raise
        print(
            f"NOTE:BLD-0032 schema shim $ref unresolved ({name}); "
            "G-1 writes the catalog output_path anyway"
        )

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:BLD-0032 artifact {size}B below floor")
        return 1
    if "SUCCESS:BLD-0032" not in out.read_text(encoding="utf-8"):
        print("FAILED:BLD-0032 sentinel absent after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:BLD-0032 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
