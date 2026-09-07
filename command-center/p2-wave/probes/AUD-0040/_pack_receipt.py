#!/usr/bin/env python3
"""Pack AUD-0040 DEPENDENCY-GRAPH vs catalog parity / byte-parity gate.

Honest BLOCKED pending cross-vendor Codex re-run of ONLY probe 2
(catalog reviewer_requirement). Never stubs SUCCESS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0040"
OUT = "command-center/audit/AUD-0040-depgraph-catalog-parity.json"
SCHEMA = "command-center/schema/audit-detector-control.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0040/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when a cross-vendor Codex review PASS that re-ran probe 2 is on disk."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"openai", "codex"}:
        return None
    if rev.get("reran_probe") not in {2, "2", "probe2"} and not rev.get("probe2_rerun"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads(
        (PROBE / "probe1-generator-byte-compare.json").read_text(encoding="utf-8")
    )
    p2 = json.loads((PROBE / "probe2-gate-both-states.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-generator-byte-compare.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-gate-both-states.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T20:30:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    byte_equal = bool(p1.get("byte_equal"))
    json_equal = bool(p1.get("json_equal"))
    node_count = p1.get("node_count")
    edge_count = p1.get("edge_count")
    control1 = bool((p1.get("control") or {}).get("ok"))
    both_states = bool(p2.get("both_states"))
    control2 = bool((p2.get("control") or {}).get("ok"))
    rc_good = p2.get("unmodified_exit_code")
    rc_bad = p2.get("mutated_exit_code")
    live = p2.get("live_gate") or {}

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
            "command-center/p2-wave/probes/AUD-0040/probe1-generator-byte-compare.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0040/probe2-gate-both-states.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0040/probe1-generator-byte-compare.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0040/probe2-gate-both-states.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0040/fixtures/planted_pair/catalog.json",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0040/fixtures/planted_pair/DEPENDENCY-GRAPH.json",
            "control",
        ),
        L.art("command-center/DEPENDENCY-GRAPH.json", "supporting"),
        L.art("tools/command-center/catalog.py", "supporting"),
        L.art("tools/command-center/validate.py", "supporting"),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0040/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Is DEPENDENCY-GRAPH.json still byte-derivable from WORK-UNIT-CATALOG.json "
        "by its generator, and does the CI byte-parity gate actually fail when the "
        "two diverge?"
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": bool(rev.get("fresh_context", True)),
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0040"
        headline = (
            f"byte_equal={byte_equal} nodes={node_count} edges={edge_count} "
            f"gate_unmod_exit={rc_good} gate_mut_exit={rc_bad} "
            f"both_states={both_states}. "
            "Independent cross-vendor Codex probe2 re-run PASS."
        )
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-PASS"
        defects = [
            {
                "id": "AUD-0040-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Cross-vendor Codex re-run of probe 2 PASS recorded.",
            },
            {
                "id": "AUD-0040-D-PARITY",
                "severity": "P2",
                "status": "resolved" if byte_equal and both_states else "open",
                "summary": (
                    f"byte_equal={byte_equal} both_states={both_states} "
                    f"unmod_exit={rc_good} mut_exit={rc_bad}."
                ),
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog requires one cross-vendor Codex reviewer who re-runs ONLY "
                "the second probe (scratch one-byte catalog mutation vs validate.py "
                "V-GRAPH gate). Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0040 generator-byte-compare + gate-both-states probes measured; "
            f"byte_equal={byte_equal} both_states={both_states} "
            f"unmod_exit={rc_good} mut_exit={rc_bad}; blocked-on-independent-review"
        )
        headline = (
            f"byte_equal={byte_equal} nodes={node_count} edges={edge_count} "
            f"gate_unmod_exit={rc_good} gate_mut_exit={rc_bad} "
            f"both_states={both_states} planted_ok={control1 and control2}. "
            "BLOCKED on cross-vendor Codex probe2 re-run."
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "detector-failure",
                "green-not-live",
            ],
            "reason": (
                "Named probes completed: generator byte-parity measured and CI "
                "V-GRAPH gate both-states control recorded (exit 0 unmodified / "
                "non-zero after one-byte catalog change), but catalog "
                "reviewer_requirement is unmet (cross-vendor Codex must re-run "
                "ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"byte_equal={byte_equal} both_states={both_states} "
                f"control1={control1} control2={control2} "
                f"unmod_exit={rc_good} mut_exit={rc_bad} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY "
                "command-center/p2-wave/probes/AUD-0040/probe2_gate_both_states.py "
                "and compare the both-states exit codes before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0040/probe2_gate_both_states.py",
                    f"both_states={both_states} unmod={rc_good} mut={rc_bad}",
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
        }
        anti = "BLOCKED-pending-cross-vendor-codex-probe2-with-real-probes"
        defects = [
            {
                "id": "AUD-0040-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0040-D-PARITY",
                "severity": "P2",
                "status": "resolved" if byte_equal and both_states else "open",
                "summary": (
                    f"generator byte_equal={byte_equal}; gate both_states="
                    f"{both_states} (unmod_exit={rc_good} mut_exit={rc_bad})."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0040",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "tool-author",
            "execution_substrate": "linux-cursor-cloud",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1: regenerated DEPENDENCY-GRAPH via "
                    f"catalog.build_graph+save; byte_equal={byte_equal} "
                    f"json_equal={json_equal} committed_sha="
                    f"{(p1.get('committed_sha256') or '')[:16]} "
                    f"regen_sha={(p1.get('regenerated_sha256') or '')[:16]} "
                    f"nodes={node_count} edges={edge_count}; "
                    f"planted_control_ok={control1}."
                ),
                "CONFIRMED" if p1.get("ok") else "REFUTED",
                "command-center/p2-wave/probes/AUD-0040/probe1-generator-byte-compare.raw.txt",
                [
                    L.probe(
                        "source",
                        "byte-compare",
                        "python3 -B command-center/p2-wave/probes/AUD-0040/probe1_generator_byte_compare.py",
                        raw1,
                        0 if p1.get("ok") else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-generator-byte-compare.json",
                        json.dumps(
                            {
                                "byte_equal": byte_equal,
                                "json_equal": json_equal,
                                "node_count": node_count,
                                "edge_count": edge_count,
                                "control_ok": control1,
                                "ok": p1.get("ok"),
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 scratch both-states: unmodified validate.py "
                    f"exit={rc_good}; one-byte effort flip exit={rc_bad}; "
                    f"both_states={both_states} v_graph_seen="
                    f"{live.get('v_graph_seen')}; planted_ok={control2}; "
                    f"live_tree_mutated={live.get('live_tree_mutated')}."
                ),
                "CONFIRMED" if p2.get("ok") else "REFUTED",
                "command-center/p2-wave/probes/AUD-0040/probe2-gate-both-states.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0040/probe2_gate_both_states.py",
                        raw2,
                        0 if p2.get("ok") else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-gate-both-states.json",
                        json.dumps(
                            {
                                "both_states": both_states,
                                "unmodified_exit_code": rc_good,
                                "mutated_exit_code": rc_bad,
                                "control_ok": control2,
                                "ok": p2.get("ok"),
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
                "id": "AUD-0040-both-states-gate",
                "name": (
                    "both-states control: gate exit 0 on unmodified pair and "
                    "non-zero after a one-byte catalog change"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0040/probe2_gate_both_states.py",
                "result": "PASS" if both_states else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-800:],
            },
            {
                "id": "AUD-0040-generator-byte-parity",
                "name": "re-run build_graph+save must byte-match committed DEPENDENCY-GRAPH.json",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0040/probe1_generator_byte_compare.py",
                "result": "PASS" if byte_equal and json_equal else "FAIL",
                "assertions": 2,
                "output_tail": raw1[-600:],
            },
            {
                "id": "AUD-0040-planted-pair-control",
                "name": "planted catalog/graph matches; one-byte effort flip diverges",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0040/probe1_generator_byte_compare.py",
                "result": "PASS" if control1 and control2 else "FAIL",
                "assertions": 2,
                "output_tail": raw1[-400:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0040-C1",
                "known-broken-fixture",
                "Planted pair regenerates byte-identical; mutated effort diverges.",
                True,
                True,
                bad=f"planted_bad_diverges={(p1.get('control') or {}).get('bad_diverges')}",
                good=f"planted_good_equal={(p1.get('control') or {}).get('good_equal')}",
            ),
            L.control(
                "AUD0040-C2",
                "mutation",
                "CI validate.py V-GRAPH exits 0 unmodified and non-zero after one-byte catalog change.",
                True,
                True,
                bad=f"mutated_exit={rc_bad} v_graph={live.get('v_graph_seen')}",
                good=f"unmodified_exit={rc_good}",
            ),
            L.control(
                "AUD0040-C3",
                "malformed-input",
                "Scratch mutation must not touch the live WORK-UNIT-CATALOG / DEPENDENCY-GRAPH pair.",
                True,
                True,
                bad="live_tree_mutated",
                good=f"live_tree_mutated={live.get('live_tree_mutated')}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated the tree; "
                "restore from the AUD-0092 backup, record the mutation, and escalate"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether render.py --check (OWNER-DECISIONS / ARTIFACT-MANIFEST) "
                    "would also turn RED on the same one-byte catalog change — this "
                    "unit measured the V-GRAPH gate in validate.py only."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "In the same scratch tree, run "
                    "`python tools/command-center/render.py --check --root <scratch>` "
                    "after the effort flip and record exit code beside V-GRAPH."
                ),
            },
            {
                "claim": (
                    "work_units[] (2007 AUD/IMP/…) are outside DEPENDENCY-GRAPH "
                    "derivation today (graph is over items[]=103); catalog-vs-graph "
                    "parity for work_units is a different question."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Confirm build_graph reads only catalog.items; document that "
                    "AUD-* edges live elsewhere or extend the generator under a "
                    "separate unit."
                ),
            },
        ],
        "report": {
            "kind": "audit-detector-control",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0040-C1", "AUD0040-C2", "AUD0040-C3"],
            "observations": [
                {
                    "name": "generator_byte_equal",
                    "measured": byte_equal,
                    "method": "catalog.build_graph+save vs committed DEPENDENCY-GRAPH.json",
                    "anchor": "command-center/p2-wave/probes/AUD-0040/probe1-generator-byte-compare.json",
                },
                {
                    "name": "node_count",
                    "measured": node_count,
                    "method": "build_graph(catalog)['node_count']",
                    "anchor": "command-center/DEPENDENCY-GRAPH.json",
                },
                {
                    "name": "edge_count",
                    "measured": edge_count,
                    "method": "build_graph(catalog)['edge_count']",
                    "anchor": "command-center/DEPENDENCY-GRAPH.json",
                },
                {
                    "name": "gate_unmodified_exit_code",
                    "measured": rc_good,
                    "method": "python tools/command-center/validate.py on live pair",
                    "anchor": "command-center/p2-wave/probes/AUD-0040/probe2-gate-both-states.raw.txt",
                },
                {
                    "name": "gate_mutated_exit_code",
                    "measured": rc_bad,
                    "method": "validate.py after one-byte items[].effort flip in scratch",
                    "anchor": "command-center/p2-wave/probes/AUD-0040/probe2-gate-both-states.json",
                },
                {
                    "name": "both_states_control_ok",
                    "measured": both_states,
                    "method": "unmodified exit==0 AND mutated exit!=0",
                    "anchor": "command-center/p2-wave/probes/AUD-0040/probe2-gate-both-states.raw.txt",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-detector-control",
            "wave": "p2",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "probe1_summary": {
                "byte_equal": byte_equal,
                "json_equal": json_equal,
                "node_count": node_count,
                "edge_count": edge_count,
                "control_ok": control1,
            },
            "probe2_summary": {
                "both_states": both_states,
                "unmodified_exit_code": rc_good,
                "mutated_exit_code": rc_bad,
                "control_ok": control2,
                "worktree_mode": p2.get("worktree_mode"),
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-generator-byte-compare.json",
        PROBE / "probe2-gate-both-states.json",
        PROBE / "probe1-generator-byte-compare.raw.txt",
        PROBE / "probe2-gate-both-states.raw.txt",
        PROBE / "fixtures" / "planted_pair" / "catalog.json",
        PROBE / "fixtures" / "planted_pair" / "DEPENDENCY-GRAPH.json",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0040 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build()
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc = build(primary=L.art(OUT, "primary"))
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    errs = L.validate(doc, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS:", *errs[:20], sep="\n", file=sys.stderr)
        return 1

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    final = json.loads(out_path.read_text(encoding="utf-8"))
    errs = L.validate(final, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS after admit:", *errs[:20], sep="\n", file=sys.stderr)
        return 1

    rc_adm3, adm_out3 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )

    man = {
        "unit_id": UNIT,
        "primary": OUT,
        "schema": SCHEMA,
        "state": final["state"],
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "artifacts": final["artifacts"],
        "packed_at": final["timestamps"]["ended_at"],
        "receipt_validate": adm_out3.strip().splitlines()[-1]
        if adm_out3.strip()
        else "",
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out3.strip())
    return 0 if rc_adm3 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
