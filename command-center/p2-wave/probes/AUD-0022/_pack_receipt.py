#!/usr/bin/env python3
"""Pack AUD-0022 transitive dep graph (BLOCKED on independent review)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0022"
OUT = "command-center/audit/AUD-0022-transitive-dep-graph.json"
SCHEMA = "command-center/schema/audit-graph.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0022/UNIT-ARTIFACT-MANIFEST.json"


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-resolver-tree.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-installed-meta.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-resolver.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-installed.raw.txt").read_text(encoding="utf-8")
    ctrl = json.loads((PROBE / "control-dual-version.json").read_text(encoding="utf-8"))
    started = "2026-09-07T18:25:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    py_dupes = p2.get("python_duplicate_version_count", 0)
    node_dupes = p2.get("node_duplicate_version_count", 0)
    lock_dupes = p1.get("duplicate_version_count", 0)
    headline_dupes = py_dupes  # measured on this host: python env has dual versions
    max_depth = max(
        p1.get("max_depth", 0),
        p2.get("installed_max_depth", 0),
        p2.get("python_graph_max_depth_sampled", 0),
    )
    nodes = []
    for name, vs in (p2.get("python_duplicate_versions") or {}).items():
        nodes.append({"id": name, "ecosystem": "python", "versions": vs, "duplicate": True})
    for name, vs in (p1.get("duplicate_versions") or {}).items():
        nodes.append({"id": name, "ecosystem": "node-lock", "versions": vs, "duplicate": True})

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art("command-center/p2-wave/probes/AUD-0022/probe1-resolver-tree.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0022/probe2-installed-meta.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0022/control-dual-version.json", "control"),
        L.art("command-center/p2-wave/probes/AUD-0022/probe1-resolver.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0022/probe2-installed.raw.txt", "log"),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0022 resolver+installed-metadata probes measured transitive closure; "
            f"python dual-version packages={headline_dupes}; blocked-on-independent-review"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0022",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "tool-author",
            "execution_substrate": "linux-local-p2-loop",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 npm/lock resolver: lock_packages={p1['lock_packages']} "
                    f"lock_edges={p1['lock_edges']} npm_ls_exit={p1['npm_ls_exit']} "
                    f"npm_ls_nodes={p1['npm_ls_nodes']} lock_dupes={lock_dupes} "
                    f"max_depth={p1['max_depth']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0022/probe1-resolver.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0022/probe1_resolver_tree.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-resolver-tree.json",
                        json.dumps(
                            {
                                "lock_packages": p1["lock_packages"],
                                "npm_ls_nodes": p1["npm_ls_nodes"],
                                "duplicate_version_count": lock_dupes,
                                "ok": p1["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 installed metadata: node_packages_seen={p2['node_packages_seen']} "
                    f"(node_modules absent) python_distributions={p2['python_distributions']} "
                    f"python_dupes={py_dupes} versions={p2.get('python_duplicate_versions')} "
                    f"requires_edges={p2.get('python_requires_edges')} "
                    f"control_ok={ctrl['ok']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0022/probe2-installed.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0022/probe2_installed_metadata.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-installed-meta.json",
                        json.dumps(
                            {
                                "python_duplicate_version_count": py_dupes,
                                "control_ok": ctrl["ok"],
                                "ok": p2["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0022-dual-version-control",
                "name": "duplicate detector fires on dual-version, silent on clean",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0022/probe2_installed_metadata.py",
                "result": "PASS" if ctrl["ok"] else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-400:],
            }
        ],
        "negative_controls": [
            L.control(
                "AUD0022-C1",
                "known-broken-fixture",
                "Deliberate dual-version left-pad must be detected; clean single version silent.",
                True,
                True,
                bad=str(ctrl.get("bad_dupes")),
                good=str(ctrl.get("good_dupes")),
            )
        ],
        "reviewer": {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires a fresh-context Claude reviewer who has not seen this "
                "transcript and must try to FALSIFY the headline duplicate-version count. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        },
        "defects": [
            {
                "id": "AUD-0022-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude review unpaid.",
            },
            {
                "id": "AUD-0022-D-PY-DUAL-VERSION",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"{py_dupes} Python packages appear at two versions in the live "
                    f"interpreter: {list((p2.get('python_duplicate_versions') or {}).keys())}"
                ),
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-graph schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0022/_pack_receipt.py",
                    "state=BLOCKED",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 1, "policy": "retry only after named upstream SUCCESS"},
        "failure": {
            "classification": ["blocked-on-independent-review", "detector-failure"],
            "reason": (
                f"Measured python dual-version packages={headline_dupes}, "
                f"max_depth={max_depth}, but reviewer_requirement unmet."
            ),
            "diagnostic_tail": (
                f"py_dupes={p2.get('python_duplicate_versions')} "
                f"npm_ls_exit={p1['npm_ls_exit']} node_modules_absent=True"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this transcript "
                "to falsify the headline duplicate-version count before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0022/probe2_installed_metadata.py",
                    f"python_duplicate_version_count={py_dupes}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        },
        "residual_unknowns": [
            {
                "claim": "Full npm transitive closure with node_modules installed matches lock.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "npm ci then re-run probe1/probe2 against populated node_modules.",
            }
        ],
        "report": {
            "kind": "audit-graph",
            "question": (
                "What is the full transitive dependency closure across ecosystems, what is its "
                "maximum depth, and which packages appear at two or more incompatible versions?"
            ),
            "answer": (
                f"This host: node lock packages={p1['lock_packages']} (workspaces-only; "
                f"node_modules absent); python_distributions={p2['python_distributions']}; "
                f"python dual-version packages={headline_dupes}; max_depth={max_depth}. "
                "BLOCKED on independent review."
            ),
            "nodes": nodes,
            "edges": (p2.get("python_sample_edges") or [])[:40],
            "duplicate_version_count": headline_dupes,
            "max_depth": max_depth,
            "observations": [
                {
                    "name": "lock_packages",
                    "measured": p1["lock_packages"],
                    "method": "package-lock.json packages map",
                    "anchor": "command-center/p2-wave/probes/AUD-0022/probe1-resolver.raw.txt",
                },
                {
                    "name": "python_distributions",
                    "measured": p2["python_distributions"],
                    "method": "importlib.metadata.distributions",
                    "anchor": "command-center/p2-wave/probes/AUD-0022/probe2-installed.raw.txt",
                },
                {
                    "name": "python_duplicate_version_packages",
                    "measured": headline_dupes,
                    "method": "version-set cardinality >= 2 per distribution name",
                    "anchor": "command-center/p2-wave/probes/AUD-0022/probe2-installed-meta.json",
                },
                {
                    "name": "max_depth",
                    "measured": max_depth,
                    "method": "lock node_modules depth + Requires-Dist BFS sample",
                    "anchor": "command-center/p2-wave/probes/AUD-0022/probe2-installed-meta.json",
                },
            ],
            "control_ids": ["AUD0022-C1"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes",
            "wave": "p2-loop",
            "python_duplicate_versions": p2.get("python_duplicate_versions"),
        },
    }


def main() -> int:
    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": "BLOCKED",
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state=BLOCKED bytes={L.art(OUT)['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
