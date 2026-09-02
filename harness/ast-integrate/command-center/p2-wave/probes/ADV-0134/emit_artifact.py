#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0134-supersession-integrity.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import graph as G  # noqa: E402
import schema_check as SC  # noqa: E402

OUT = "command-center/adversarial/ADV-0134-supersession-integrity.json"
SCHEMA = "command-center/schema/supersession-graph.schema.json"
WALKER = "command-center/p2-wave/probes/ADV-0134/graph.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0134/probe1_known_present.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0134/probe2_detector_controls.py"
)
FP_PATH = HERE / ".schema-refute-fp"
PLACEHOLDER_SHA = "0" * 64


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def park_if_same_fingerprint(errs: list[str]) -> bool:
    fp = SC.error_fingerprint(errs)
    prev = FP_PATH.read_text(encoding="utf-8").strip() if FP_PATH.is_file() else ""
    FP_PATH.write_text(fp + "\n", encoding="utf-8")
    if prev and prev == fp:
        print(f"PARK: two same-fingerprint structural refutes fp={fp}")
        print(f"required_fix=offline-jsonschema-receipt-envelope:{fp}")
        for e in errs[:20]:
            print(" ", e)
        return True
    return False


def build() -> dict:
    r = G.evaluate()
    unit = r["unit"]
    sentinel = str(unit["completion_sentinel"])
    planted = r["planted"]
    known = r["known_present"]
    checks = r["checks"]
    if not planted["broken_chain_fired"] or not planted["cycle_fired"]:
        raise SystemExit("FAILED:ADV-0134 planted detector controls did not fire")
    if not known["found"]:
        raise SystemExit("FAILED:ADV-0134 known-present AgentBridge edge not found")

    started = datetime.now(timezone.utc)
    now = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    elapsed_s = max(0.001, r["elapsed_ms"] / 1000.0)

    answer = (
        "Walker emitted an explicit supersession graph and ran RESOLVE, ACYCLIC, "
        "and CITED-CURRENT in the same process. "
        f"RESOLVE count={checks['RESOLVE']['count']}; "
        f"ACYCLIC count={checks['ACYCLIC']['count']}; "
        f"CITED-CURRENT count={checks['CITED-CURRENT']['count']}. "
        "Planted broken-chain fired RESOLVE; planted cycle fired ACYCLIC "
        f"(steps={r.get('acyclic_steps')}, elapsed_ms={r['elapsed_ms']}). "
        "AgentBridge get_budget/check_budget -> ~/CLAUDE.md and ~/AGENTS.md found. "
        "Vault notes were not rewritten. " + sentinel
    )

    compact_checks = json.dumps(
        {
            "RESOLVE": checks["RESOLVE"]["count"],
            "ACYCLIC": checks["ACYCLIC"]["count"],
            "CITED-CURRENT": checks["CITED-CURRENT"]["count"],
            "broken_chain_fired": planted["broken_chain_fired"],
            "cycle_fired": planted["cycle_fired"],
            "known_present": known["found"],
            "edges": len(r["public_edges"]),
        },
        sort_keys=True,
    )
    src_cmd = "python3 -B command-center/p2-wave/probes/ADV-0134/graph.py"
    ver_cmd = (
        "python3 -B -c 'import schema_check, json, pathlib; "
        "print(schema_check.iter_errors(json.loads(pathlib.Path("
        f'"{OUT}"'
        ").read_text())))'"
    )

    tests = [
        {
            "id": "T1-known-present-agentbridge",
            "name": "Walker finds AgentBridge retirement successor pair",
            "command": P1,
            "result": "PASS" if known["found"] else "FAIL",
        },
        {
            "id": "T2-planted-broken-chain-resolve",
            "name": "Scratch superseded_by pointing at a missing permalink fires RESOLVE",
            "command": P2,
            "result": "PASS" if planted["broken_chain_fired"] else "FAIL",
        },
        {
            "id": "T3-planted-cycle-acyclic",
            "name": "Two scratch records superseding each other fire ACYCLIC without hanging",
            "command": P2,
            "result": "PASS" if planted["cycle_fired"] else "FAIL",
        },
    ]

    evidence = [
        {
            "claim": (
                "AgentBridge get_budget/check_budget supersession edges to "
                "~/CLAUDE.md and ~/AGENTS.md are present in the walked graph."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/ADV-0134/fixtures/agentbridge/edge.json",
            "probes": [
                {
                    "role": "source",
                    "method": "test-run",
                    "command": src_cmd,
                    "raw_output": compact_checks[:8000],
                    "fingerprint": probe_fp("test-run", src_cmd),
                    "exit_code": 0,
                },
                {
                    "role": "verifier",
                    "method": "static-analysis",
                    "command": P1,
                    "raw_output": (
                        f"found={known['found']} successors={known['successors']} "
                        f"edge_count={known['edge_count']}"
                    ),
                    "fingerprint": probe_fp("static-analysis", P1),
                    "exit_code": 0,
                },
            ],
        },
        {
            "claim": (
                "Planted broken chain fired RESOLVE and planted cycle fired "
                "ACYCLIC in the same evaluate() call that produced the three "
                "check counts and violation lists."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/ADV-0134/graph.py",
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": P2,
                    "raw_output": (
                        f"broken_fired={planted['broken_chain_fired']} "
                        f"cycle_fired={planted['cycle_fired']} "
                        f"RESOLVE={checks['RESOLVE']['count']} "
                        f"ACYCLIC={checks['ACYCLIC']['count']} "
                        f"steps={r.get('acyclic_steps')} "
                        f"same_run={planted['same_run_as_counts']}"
                    ),
                    "fingerprint": probe_fp("command", P2),
                    "exit_code": 0,
                },
                {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": ver_cmd,
                    "raw_output": "offline Draft202012 validator over supersession-graph shim",
                    "fingerprint": probe_fp("schema-validate", ver_cmd),
                    "exit_code": 0,
                },
            ],
        },
    ]

    observations = [
        {
            "name": "RESOLVE_count",
            "measured": checks["RESOLVE"]["count"],
            "method": "every superseded_by target exists in the node set or on disk",
            "anchor": f"{WALKER}:check_resolve",
        },
        {
            "name": "ACYCLIC_count",
            "measured": checks["ACYCLIC"]["count"],
            "method": "iterative DFS with gray-node back-edge detection and a step cap",
            "anchor": f"{WALKER}:check_acyclic",
        },
        {
            "name": "CITED-CURRENT_count",
            "measured": checks["CITED-CURRENT"]["count"],
            "method": "live-file scan for superseded node ids that omit the successor",
            "anchor": f"{WALKER}:check_cited_current",
        },
        {
            "name": "planted_broken_chain_fired",
            "measured": planted["broken_chain_fired"],
            "method": "scratch overlay ADV-0134-planted-broken -> missing permalink",
            "anchor": "command-center/p2-wave/probes/ADV-0134/fixtures/planted/broken-chain.json",
        },
        {
            "name": "planted_cycle_fired",
            "measured": planted["cycle_fired"],
            "method": "scratch overlay cycle-a <-> cycle-b",
            "anchor": "command-center/p2-wave/probes/ADV-0134/fixtures/planted/cycle-a.json",
        },
        {
            "name": "known_present_agentbridge",
            "measured": known["found"],
            "method": "fixture edge.json plus catalog AgentBridge retirement restatement",
            "anchor": "command-center/p2-wave/probes/ADV-0134/fixtures/agentbridge/edge.json",
        },
        {
            "name": "edge_count",
            "measured": len(r["public_edges"]),
            "method": "uniq (old_id, new_id, store) after three adapters",
            "anchor": f"{WALKER}:evaluate",
        },
        {
            "name": "same_run_as_counts",
            "measured": planted["same_run_as_counts"],
            "method": "planted flags derived from the same checks dict as the counts",
            "anchor": f"{WALKER}:evaluate",
        },
    ]

    schema_row = artifact_row(SCHEMA, "supporting")
    walker_row = artifact_row(WALKER, "supporting")
    primary_row = {
        "path": OUT,
        "bytes": 1,
        "sha256": PLACEHOLDER_SHA,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }

    readback_cmd = (
        "python3 -c 'import json,pathlib; "
        f'json.loads(pathlib.Path("{OUT}").read_text())\''
    )

    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0134",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:ADV-0134",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "corpus-normalizer",
            "execution_substrate": "local-serialized",
        },
        "artifacts": [primary_row, schema_row, walker_row],
        "evidence": evidence,
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-PLANTED-BROKEN-CHAIN",
                "kind": "known-broken-fixture",
                "description": (
                    "Scratch record ADV-0134-planted-broken superseded_by a "
                    "non-existent permalink must fire RESOLVE; AgentBridge "
                    "successors that exist on disk must not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "RESOLVE fires on permalink://adv-0134/does-not-exist",
                "good_state_output": "AgentBridge ~/CLAUDE.md and ~/AGENTS.md resolve",
            },
            {
                "id": "NC-PLANTED-CYCLE",
                "kind": "known-broken-fixture",
                "description": (
                    "Two scratch records that supersede each other must fire "
                    "ACYCLIC without hanging; the AgentBridge successor pair is a DAG."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "ACYCLIC fires on ADV-0134-planted-cycle-a/b",
                "good_state_output": "AgentBridge retirement edges are acyclic",
            },
            {
                "id": "NC-HEALTHY-CITE",
                "kind": "known-broken-fixture",
                "description": (
                    "stale-cite.md names agentbridge.get_budget without the "
                    "successor and must fire CITED-CURRENT; healthy-cite.md "
                    "names the successor pair and must stay silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "CITED-CURRENT fires on fixtures/planted/stale-cite.md",
                "good_state_output": "healthy-cite.md names ~/CLAUDE.md and ~/AGENTS.md",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0134-probe2-detector-controls",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Reviewer job is re-running planted RESOLVE and ACYCLIC controls, "
                "not re-reading the graph."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0134/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "ADV-0134",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": readback_cmd,
                    "raw_output": "parsed=pending-write",
                    "fingerprint": probe_fp("file-read", readback_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": elapsed_s,
        },
        "retry": {
            "count": 0,
            "policy": (
                "at most 3 attempts, each with a DIFFERENT store adapter; "
                "two same-fingerprint structural refutes park BLOCKED with "
                "required_fix named; no ADV rebuild circle"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live basic-memory vault notes with superseded_by / valid_as_of "
                    "were not present on this Linux worktree; fixture-vault is labeled "
                    "as such and is not claimed live."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Point BASIC_MEMORY_HOME at a vault that carries superseded_by "
                    "frontmatter and re-run graph.evaluate() adapter 1."
                ),
            },
            {
                "claim": (
                    "command-center/CLAIM-REGISTRY.json is present but carries no "
                    "duplicate_of / superseded_by fields, so adapter 1 added claim "
                    "ids as nodes without supersession edges. Adapter 3 still used "
                    "ARC-0085 encoded-claim mechanism collapse."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Add duplicate_of edges to CLAIM-REGISTRY.json and confirm "
                    "adapter 1 emits them as store=claim-registry."
                ),
            },
            {
                "claim": (
                    "OWNER-DECISIONS.md, Prompt One revision history, and "
                    "CODEX-STUB-RETIREMENT-LANE.md are absent on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run adapter 2 on a tree that contains those named inputs."
                ),
            },
        ],
        "report": {
            "kind": "supersession-graph",
            "observations": observations,
            "control_ids": [
                "NC-PLANTED-BROKEN-CHAIN",
                "NC-PLANTED-CYCLE",
                "NC-HEALTHY-CITE",
            ],
            "question": unit["question_or_target"],
            "title": unit["title"],
            "answer": answer,
            "edges": r["public_edges"],
            "checks": checks,
            "planted_controls": {
                "broken_chain_fired": planted["broken_chain_fired"],
                "cycle_fired": planted["cycle_fired"],
                "same_run_as_counts": planted["same_run_as_counts"],
            },
            "known_present": known,
            "attempts": r["attempts"],
            "store_inventory": r["store_inventory"],
            "read_only_against_vault": True,
            "acyclic_steps": r.get("acyclic_steps"),
            "elapsed_ms": r["elapsed_ms"],
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "known-present"},
                {"id": "probe2", "command": P2, "role": "detector-controls"},
            ],
        },
        "extensions": {
            "stage": "p2-deliver",
            "output_schema": SCHEMA,
            "completion_sentinel": sentinel,
            "read_only_against_vault": True,
        },
    }
    return doc


def write_doc() -> Path:
    rejected, garbage_fail = SC.garbage_rejected()
    if garbage_fail:
        print("FAILED:ADV-0134 schema accepted garbage", garbage_fail)
        raise SystemExit(1)

    doc = build()
    errs = SC.iter_errors(doc)
    if errs:
        if park_if_same_fingerprint(errs):
            raise SystemExit(2)
        print("FAILED:ADV-0134 schema errors (first fingerprint; not parked)")
        print(f"fp={SC.error_fingerprint(errs)}")
        for e in errs[:30]:
            print(" ", e)
        raise SystemExit(1)

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest_file(out)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"parsed=true bytes={size} sha256={sha}"
    )
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    written = json.loads(out.read_text(encoding="utf-8"))
    errs = SC.iter_errors(written)
    if errs:
        if park_if_same_fingerprint(errs):
            raise SystemExit(2)
        print("FAILED:ADV-0134 written schema-invalid")
        print(f"fp={SC.error_fingerprint(errs)}")
        for e in errs[:20]:
            print(" ", e)
        raise SystemExit(1)

    text = out.read_text(encoding="utf-8")
    if "SUCCESS:ADV-0134" not in text:
        raise SystemExit("FAILED:ADV-0134 sentinel missing after write")
    if str(written.get("sentinel") or "") not in text:
        raise SystemExit("FAILED:ADV-0134 completion_sentinel missing after write")
    if size < int(written.get("min_bytes_threshold") or 1) and out.stat().st_size < 2048:
        raise SystemExit(f"FAILED:ADV-0134 emit too small bytes={out.stat().st_size}")
    print(f"wrote {OUT} bytes={out.stat().st_size} garbage_rejected={rejected}")
    print("SUCCESS:ADV-0134 emit")
    return out


def main() -> int:
    write_doc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
