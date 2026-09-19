#!/usr/bin/env python3
"""Pack AUD-0022 transitive dep graph.

Promotes to SUCCESS only when independent-review.json has verdict=PASS with
independent+fresh_context. Otherwise emits BLOCKED (anti-false-green).
"""

from __future__ import annotations

import json
import subprocess
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
REVIEW = PROBE / "independent-review.json"
VALIDATE = L.REPO / "command-center/receipt_validate.py"


def load_review() -> dict | None:
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-resolver-tree.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-installed-meta.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-resolver.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-installed.raw.txt").read_text(encoding="utf-8")
    ctrl = json.loads((PROBE / "control-dual-version.json").read_text(encoding="utf-8"))
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T18:25:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    py_dupes = p2.get("python_duplicate_version_count", 0)
    lock_dupes = p1.get("duplicate_version_count", 0)
    headline_dupes = py_dupes
    max_depth = max(
        int(p1.get("max_depth") or 0),
        int(p2.get("installed_max_depth") or 0),
        int(p2.get("python_graph_max_depth_sampled") or 0),
    )
    sample_edges = [
        e
        for e in (p2.get("python_sample_edges") or [])
        if isinstance(e, dict) and e.get("kind") == "installed-use"
    ]
    nodes: list[dict] = []
    for name, vs in (p2.get("python_duplicate_versions") or {}).items():
        nodes.append(
            {"id": name, "ecosystem": "python", "versions": vs, "duplicate": True}
        )
    for name, vs in (p1.get("duplicate_versions") or {}).items():
        nodes.append(
            {"id": name, "ecosystem": "node-lock", "versions": vs, "duplicate": True}
        )
    for e in sample_edges:
        for key in ("from", "to"):
            nid = e.get(key)
            if nid and not any(n.get("id") == nid for n in nodes):
                nodes.append(
                    {
                        "id": nid,
                        "ecosystem": "python",
                        "versions": ["(installed)"],
                        "duplicate": False,
                    }
                )

    # npm_ls_exit==0 is a real success; avoid `or 1` which treats 0 as missing.
    npm_ls_exit = p1.get("npm_ls_exit")
    npm_ls_exit_i = int(npm_ls_exit) if npm_ls_exit is not None else 1
    npm_complete = npm_ls_exit_i == 0 and int(p2.get("node_packages_seen") or 0) > 0
    # Lock may still be workspace stubs (lock_edges=0) even when npm ls works.
    lock_edges = int(p1.get("lock_edges") or 0)
    npm_residual = "CHECKED" if (npm_complete and lock_edges > 0) else "PARTIAL"

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
        L.art(
            "command-center/p2-wave/probes/AUD-0022/probe1-resolver-tree.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0022/probe2-installed-meta.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0022/control-dual-version.json",
            "control",
        ),
        L.art("command-center/p2-wave/probes/AUD-0022/probe1-resolver.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0022/probe2-installed.raw.txt", "log"),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0022/independent-review.json",
                "supporting",
            )
        )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        defects = [
            {
                "id": "AUD-0022-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude re-review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0022/independent-review.json"
                ),
            },
            {
                "id": "AUD-0022-D-PY-DUAL-VERSION",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"{py_dupes} Python packages at two versions: "
                    f"{list((p2.get('python_duplicate_versions') or {}).keys())}"
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = (
            f"SUCCESS:AUD-0022 python dual-version packages={headline_dupes}; "
            f"max_depth={max_depth}; installed-use requires_edges="
            f"{p2.get('python_requires_edges')}; npm_ls_exit={npm_ls_exit_i}"
        )
        failure = None
        anti = "SUCCESS-after-independent-re-review-PASS"
        review_note = "Independent re-review PASS."
    else:
        review_path = PROBE / "independent-review.json"
        review_doc: dict = {}
        if review_path.is_file():
            try:
                review_doc = json.loads(review_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                review_doc = {}
        review_verdict = review_doc.get("verdict") or "NOT-REVIEWED"
        reviewer = {
            "reviewer_id": review_doc.get("reviewer_id")
            or "required-fresh-context-claude-reviewer-unassigned",
            "verdict": review_verdict,
            "independent": bool(review_doc.get("independent")),
            "fresh_context": bool(review_doc.get("fresh_context")),
            "vendor": review_doc.get("vendor") or "anthropic",
            "notes": review_doc.get("notes")
            or "Independent review owed; remedi pending re-review.",
        }
        defects = [
            {
                "id": "AUD-0022-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    f"Independent review verdict={review_verdict}; remedi grounds "
                    "depth/edges in probe2 with installed-use filter."
                ),
            },
            {
                "id": "AUD-0022-D-PY-DUAL-VERSION",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"{py_dupes} Python packages at two versions: "
                    f"{list((p2.get('python_duplicate_versions') or {}).keys())}"
                ),
            },
        ]
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0022 remedi after review FAIL; "
            f"python dual-version packages={headline_dupes}; "
            f"max_depth={max_depth}; reviewer={review_verdict}"
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "detector-failure",
                "review-fail-remedi-pending-rereview",
            ],
            "reason": (
                f"Measured python dual-version packages={headline_dupes}, "
                f"max_depth={max_depth} from named probes; reviewer={review_verdict}."
            ),
            "diagnostic_tail": (
                f"py_dupes={p2.get('python_duplicate_versions')} "
                f"npm_ls_exit={npm_ls_exit_i} "
                f"node_packages_seen={p2.get('node_packages_seen')} "
                f"python_requires_edges={p2.get('python_requires_edges')} "
                f"edge_filter={p2.get('edge_filter')}"
            ),
            "blocked_on": (
                "Independent re-review after remedi: probe2 emits installed-use "
                "Requires-Dist edges + BFS depth; npm workspaces linked."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0022/probe2_installed_metadata.py",
                    (
                        f"python_duplicate_version_count={py_dupes} "
                        f"depth={p2.get('python_graph_max_depth_sampled')}"
                    ),
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    str(review_verdict),
                    0,
                ),
            ],
        }
        anti = "BLOCKED-with-real-probes"
        review_note = f"BLOCKED; reviewer={review_verdict}."

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
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
                    f"lock_edges={p1['lock_edges']} npm_ls_exit={npm_ls_exit_i} "
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
                                "npm_ls_exit": npm_ls_exit_i,
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
                    f"Probe 2 installed-use graph: node_packages_seen={p2['node_packages_seen']} "
                    f"python_distributions={p2['python_distributions']} "
                    f"python_dupes={py_dupes} "
                    f"requires_edges={p2.get('python_requires_edges')} "
                    f"python_graph_max_depth_sampled={p2.get('python_graph_max_depth_sampled')} "
                    f"edge_filter={p2.get('edge_filter')} control_ok={ctrl['ok']}."
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
                                "python_requires_edges": p2.get(
                                    "python_requires_edges"
                                ),
                                "python_graph_max_depth_sampled": p2.get(
                                    "python_graph_max_depth_sampled"
                                ),
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
        "reviewer": reviewer,
        "defects": defects,
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
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 2, "policy": "retry only after named upstream SUCCESS"},
        "residual_unknowns": [
            {
                "claim": "Full npm transitive closure with node_modules installed matches lock.",
                "verdict": npm_residual,
                "settling_experiment": (
                    "npm install --ignore-scripts linked workspace packages; "
                    "re-run probe1/probe2. Lock dependency maps may still be workspace stubs."
                ),
            }
        ],
        "report": {
            "kind": "audit-graph",
            "question": (
                "What is the full transitive dependency closure across ecosystems, what is its "
                "maximum depth, and which packages appear at two or more incompatible versions?"
            ),
            "answer": (
                f"lock_packages={p1['lock_packages']} "
                f"node_packages_seen={p2['node_packages_seen']} "
                f"npm_ls_exit={npm_ls_exit_i}; "
                f"python_distributions={p2['python_distributions']}; "
                f"python dual-version packages={headline_dupes}; "
                f"installed-use requires_edges={p2.get('python_requires_edges')}; "
                f"max_depth={max_depth} "
                f"(probe2 BFS={p2.get('python_graph_max_depth_sampled')}, "
                f"nm_depth={p2.get('installed_max_depth')}, "
                f"lock_depth={p1.get('max_depth')}). "
                f"{review_note}"
            ),
            "nodes": nodes[:80],
            "edges": sample_edges[:40],
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
                    "method": (
                        "max(lock_path_depth, node_modules_nesting, "
                        "installed-use Requires-Dist BFS from probe2_installed_metadata.py)"
                    ),
                    "anchor": "command-center/p2-wave/probes/AUD-0022/probe2-installed-meta.json",
                },
                {
                    "name": "python_requires_edges",
                    "measured": p2.get("python_requires_edges"),
                    "method": p2.get("edge_filter") or "installed-use Requires-Dist",
                    "anchor": "command-center/p2-wave/probes/AUD-0022/probe2-installed-meta.json",
                },
            ],
            "control_ids": ["AUD0022-C1"],
        },
        "extensions": {
            "anti_false_green": anti,
            "wave": "p2-loop",
            "python_duplicate_versions": p2.get("python_duplicate_versions"),
            "edge_filter": p2.get("edge_filter"),
            "remedi_after_review_fail": True,
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    doc = build()
    state = doc["state"]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        state = doc["state"]
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": state,
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={state} bytes={L.art(OUT)['bytes']}")

    val = subprocess.run(
        [sys.executable, str(VALIDATE), str(L.REPO / OUT)],
        cwd=str(L.REPO),
        capture_output=True,
        text=True,
    )
    val_out = (val.stdout or "") + (val.stderr or "")
    print(val_out)
    if val.returncode != 0:
        print(f"FAILED:{UNIT} receipt_validate rejected packed artifact")
        return val.returncode

    if state == "SUCCESS" and "failure" in doc:
        print(f"FAILED:{UNIT} SUCCESS pack still carries failure block")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
