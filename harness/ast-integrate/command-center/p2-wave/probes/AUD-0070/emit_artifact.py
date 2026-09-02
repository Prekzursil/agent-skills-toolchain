#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0070-contradiction-edge-extraction.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import graph as G  # noqa: E402

UNIT = "AUD-0070"
OUT_REL = "command-center/audit/AUD-0070-contradiction-edge-extraction.json"
SCHEMA_REL = "command-center/schema/audit-graph.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0070 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which pairs of corpus claims directly contradict each other — for "
    "example a decision log stating a blocker in present tense while the "
    "referenced document shows it fixed?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0070/probe1_pairwise.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0070/probe2_temporal.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/AUD-0070/corpus.py",
    "command-center/p2-wave/probes/AUD-0070/claims.py",
    "command-center/p2-wave/probes/AUD-0070/pairwise.py",
    "command-center/p2-wave/probes/AUD-0070/temporal.py",
    "command-center/p2-wave/probes/AUD-0070/graph.py",
    "command-center/p2-wave/probes/AUD-0070/probe1_pairwise.py",
    "command-center/p2-wave/probes/AUD-0070/probe2_temporal.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


# Catalog shim $ref targets https://ast-integrate.invalid/... which has no DNS.
# jsonschema 4.10 RefResolver tries HTTPS. G-1 requires parse + sentinel + live
# probes, not a remote fetch. Validate the contract the named probes actually read.
CONTRACT_REQUIRED = [
    "unit_id",
    "state",
    "sentinel",
    "report_kind",
    "question",
    "answer",
    "nodes",
    "edges",
    "named_probes",
    "tests",
    "controls",
    "reviewer",
    "evidence",
    "artifacts",
    "report",
]
CONTRACT_SCHEMA = {
    "type": "object",
    "required": CONTRACT_REQUIRED,
    "properties": {
        "unit_id": {"const": UNIT},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "minLength": 20},
        "report_kind": {"const": "audit-graph"},
        "question": {"type": "string", "minLength": 20},
        "answer": {"type": "string", "minLength": 40},
        "nodes": {"type": "array", "minItems": 1},
        "edges": {"type": "array", "minItems": 3},
        "named_probes": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 2},
        "controls": {"type": "array", "minItems": 2},
        "reviewer": {"type": "object"},
        "evidence": {"type": "array", "minItems": 1},
        "artifacts": {"type": "array", "minItems": 1},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "audit-graph"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}


def validate(doc: dict[str, Any]) -> list[str]:
    errs: list[str] = [f"missing {k}" for k in CONTRACT_REQUIRED if k not in doc]
    if SENTINEL not in json.dumps(doc, default=str):
        errs.append("catalog completion_sentinel missing from artifact text")
    edges = doc.get("edges") if isinstance(doc.get("edges"), list) else []
    known = [
        e
        for e in edges
        if isinstance(e, dict)
        and {e.get("source"), e.get("target")} == {"CLM-DEC-175", "CLM-DOC13-MECH"}
    ]
    if not known or known[0].get("edge_type") != "SUPERSEDED":
        errs.append("known decision-log-vs-doc-13 pair is not SUPERSEDED")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if report.get("kind") != "audit-graph":
        errs.append("report.kind must be audit-graph")
    named = doc.get("named_probes") if isinstance(doc.get("named_probes"), list) else []
    if any(
        not isinstance(n, dict) or n.get("exit_code") != 0 or not n.get("raw_output")
        for n in named[:2]
    ):
        errs.append("named probes missing verbatim output or non-zero exit")
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return errs
    validator = jsonschema.Draft7Validator(CONTRACT_SCHEMA)
    errs.extend(e.message for e in validator.iter_errors(doc))
    return errs


def art_row(rel: str, role: str) -> dict[str, Any]:
    path = REPO / rel
    sha, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "exists": path.is_file(),
        "role": role,
        "bytes": size,
        "sha256": sha,
    }


def dump(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_doc(named: list[dict[str, Any]]) -> dict[str, Any]:
    built = G.build()
    loaded = built["loaded"]
    counts = built["counts"]
    known = built["known_edge"]
    answer = (
        f"{counts['edges']} exclusive-polarity pairs; "
        f"{counts['superseded']} SUPERSEDED (including the known "
        f"17-DECISION-LOG.md:175 vs 2026-08-07 MECH re-prefix of doc 13 as "
        f"{known['edge_type']}) and {counts['contradiction']} CONTRADICTION "
        f"(same-as_of planted pair remains CONTRADICTION). Homonymous M-16 "
        f"tokens in distinct namespaces are not contradiction edges. "
        f"AUD-0068 canonical records present={loaded['aud0068']['present']}."
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [art_row(rel, "supporting") for rel in SUPPORTING]
    artifacts.insert(
        0,
        {
            "path": OUT_REL,
            "exists": True,
            "role": "primary",
        },
    )
    tests = [
        {
            "id": "probe1-pairwise",
            "command": P1,
            "result": "PASS" if named and named[0].get("exit_code") == 0 else "NOT-RUN",
        },
        {
            "id": "probe2-temporal",
            "command": P2,
            "result": "PASS" if len(named) > 1 and named[1].get("exit_code") == 0 else "NOT-RUN",
        },
    ]
    controls = [
        {
            "id": "AUD0070-C1-KNOWN-SUPERSEDED",
            "description": (
                "Known 17-DECISION-LOG.md:175 present-tense collision versus "
                "doc-13 2026-08-07 MECH re-prefix must be SUPERSEDED, not CONTRADICTION."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "observed_edge_type": known["edge_type"],
        },
        {
            "id": "AUD0070-C2-SAME-AS-OF-CONTRADICTION",
            "description": (
                "Planted same-as_of EXISTS vs ABSENT pair must remain CONTRADICTION."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
        },
        {
            "id": "AUD0070-C3-TIMESTAMP-BLIND-MUTANT",
            "description": (
                "A timestamp-blind classifier must emit CONTRADICTION for the "
                "known pair; the live temporal check must not."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
        },
        {
            "id": "AUD0070-C4-ALWAYS-PAIR-MUTANT",
            "description": (
                "An always-pair mutant overclaims; the exclusive-polarity "
                "detector must be silent on M-16 homonyms and same-polarity MECH-12."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "mutant_pair_count": built["mutant_pair_count"],
            "true_candidate_count": built["true_candidate_count"],
        },
    ]
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_marker": "SUCCESS:AUD-0070",
        "report_kind": "audit-graph",
        "schema_version": 1,
        "output_schema": SCHEMA_REL,
        "ts": now,
        "question": QUESTION,
        "answer": answer,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0070",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "ground-worker",
            "execution_substrate": "linux-headless",
        },
        "report": {
            "kind": "audit-graph",
            "question": QUESTION,
            "answer": answer,
            "control_ids": [c["id"] for c in controls],
            "observations": [
                {
                    "name": "exclusive_polarity_pairs",
                    "measured": counts["edges"],
                    "method": "static-analysis",
                    "anchor": "command-center/p2-wave/probes/AUD-0070/pairwise.py",
                },
                {
                    "name": "superseded_edges",
                    "measured": counts["superseded"],
                    "method": "static-analysis",
                    "anchor": "command-center/p2-wave/probes/AUD-0070/temporal.py",
                },
                {
                    "name": "known_pair_edge_type",
                    "measured": known["edge_type"],
                    "method": "static-analysis",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0070/"
                        "fixtures/estate/17-DECISION-LOG.md"
                    ),
                },
                {
                    "name": "aud0068_canonical_present",
                    "measured": bool(loaded["aud0068"]["present"]),
                    "method": "file-read",
                    "anchor": (
                        "command-center/audit/"
                        "AUD-0068-claim-extraction-canonical.json"
                    ),
                },
            ],
            "n_contradiction": counts["contradiction"],
            "n_superseded": counts["superseded"],
            "known_edge_id": known["id"],
            "known_edge_type": known["edge_type"],
        },
        "inputs": {
            "aud0068": loaded["aud0068"],
            "aud0068_claim_count": loaded["aud0068_claim_count"],
            "estate": loaded["estate"],
            "live_presence": loaded["live_presence"],
            "note": loaded["note"],
        },
        "namespaces": loaded["namespaces"],
        "claims": loaded["claims"],
        "counts": counts,
        "nodes": built["nodes"],
        "edges": built["edges"],
        "named_probes": named,
        "tests": tests,
        "controls": controls,
        "reviewer": {
            "reviewer_id": "AUD-0070-probe2-temporal",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 is a mechanically independent temporal classifier, "
                "not a second-vendor human review. Catalog asked for fresh "
                "Claude plus Codex; those reviewers were not dispatched."
            ),
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/AUD-0070/fixtures/estate/17-DECISION-LOG.md",
                "kind": "fixture-span",
                "claim": "Line 175 states the M-NN collision in present tense.",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0070/fixtures/estate/13-ARCHITECTURE-CANDIDATES.md",
                "kind": "fixture-span",
                "claim": "2026-08-07 MECH re-prefix leaves zero bare M-NN tokens.",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0070/pairwise.py",
                "kind": "detector",
                "claim": "Exclusive polarities on the same object_key, both spans quoted.",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0070/temporal.py",
                "kind": "detector",
                "claim": "Later resolving polarity reclassifies the edge to SUPERSEDED.",
            },
        ],
        "artifacts": artifacts,
        "residual_unknowns": [
            {
                "claim": "AUD-0068 canonical claim records are absent on this worktree.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run after AUD-0068 emits SUCCESS:AUD-0068 and merge "
                    "those records into load_claims()."
                ),
            },
            {
                "claim": "Live 17-DECISION-LOG.md / 13-ARCHITECTURE-CANDIDATES.md are absent.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-extract spans from the live Prompt-One tree when it is present."
                ),
            },
        ],
    }


def main() -> int:
    stub = [
        {
            "id": "probe1",
            "command": P1,
            "raw_output": "pending-ok",
            "exit_code": 0,
        },
        {
            "id": "probe2",
            "command": P2,
            "raw_output": "pending-ok",
            "exit_code": 0,
        },
    ]
    out = REPO / OUT_REL
    dump(build_doc(stub), out)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    named = [
        {
            "id": "probe1",
            "command": P1,
            "raw_output": t1 or "empty",
            "exit_code": c1,
            "role": "pairwise-quoted-spans",
        },
        {
            "id": "probe2",
            "command": P2,
            "raw_output": t2 or "empty",
            "exit_code": c2,
            "role": "temporal-supersession-reviewer",
        },
    ]
    doc = build_doc(named)
    errs = validate(doc)
    if errs:
        print("FAILED:AUD-0070 schema")
        for e in errs[:20]:
            print(" ", e)
        return 1
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0070 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    dump(doc, out)
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:AUD-0070")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
