#!/usr/bin/env python3
"""Pack AUD-0057 assertion-strength census.

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

UNIT = "AUD-0057"
OUT = "command-center/audit/AUD-0057-assertion-strength-census.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0057/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when a cross-vendor Codex review PASS is on disk."""
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
    p1 = json.loads((PROBE / "probe1-default-census.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-mutate-defaults.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-default-census.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-mutate-defaults.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T19:50:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    unex = int(p1["unexercised_count"])
    exercised = int(p1["exercised_count"])
    defs_n = int(p1["defs_with_defaults"])
    suite_holes = int(p1["suite_local_hole_count"])
    high_unex = int(p1["high_risk_unexercised_count"])
    control1 = bool(p1["control"]["ok"])
    control2 = bool(p2["control"]["ok"])
    holes_confirmed = int(p2["holes_confirmed_count"])
    both_states = bool(p2["control"]["both_states"])

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
            "command-center/p2-wave/probes/AUD-0057/probe1-default-census.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0057/probe2-mutate-defaults.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0057/probe1-default-census.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0057/probe2-mutate-defaults.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0057/fixtures/planted_defaults.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0057/fixtures/test_planted_weak.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0057/fixtures/test_planted_strong.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0057/fixtures/mention_only_noise.py",
            "fixture",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0057/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Which tests pass an argument explicitly on every path such that the "
        "function's DEFAULT value is never exercised - the exact shape that let a "
        "1024-to-512 default change survive a 15-of-15 green suite?"
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
        sentinel = "SUCCESS:AUD-0057"
        headline = (
            f"defs={defs_n} unexercised={unex} exercised={exercised} "
            f"suite_local_holes={suite_holes} high_risk_unexercised={high_unex} "
            f"holes_confirmed={holes_confirmed} both_states={both_states}. "
            "Independent cross-vendor Codex probe2 re-run PASS."
        )
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-PASS"
        defects = [
            {
                "id": "AUD-0057-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Cross-vendor Codex re-run of probe 2 PASS recorded.",
            },
            {
                "id": "AUD-0057-D-SUITE-HOLES",
                "severity": "P2",
                "status": "open" if suite_holes else "resolved",
                "summary": (
                    f"suite_local_holes={suite_holes} high_risk_unexercised={high_unex}; "
                    f"mutation holes_confirmed={holes_confirmed}."
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
                "the second probe (default mutation in scratch worktree). Unavailable "
                "in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0057 default-census + mutation probes measured; "
            f"unexercised={unex} suite_local_holes={suite_holes} "
            f"holes_confirmed={holes_confirmed}; blocked-on-independent-review"
        )
        headline = (
            f"defs={defs_n} unexercised={unex} exercised={exercised} "
            f"suite_local_holes={suite_holes} high_risk_unexercised={high_unex} "
            f"holes_confirmed={holes_confirmed} both_states={both_states}. "
            "BLOCKED on cross-vendor Codex probe2 re-run."
        )
        failure = {
            "classification": ["blocked-on-independent-review", "green-not-live"],
            "reason": (
                "Named probes completed with planted both-states control and "
                "mutation-gate weak-suite hole confirmed, but catalog "
                "reviewer_requirement is unmet (cross-vendor Codex must re-run "
                "ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"unexercised={unex} suite_holes={suite_holes} "
                f"control1={control1} control2={control2} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY "
                "command-center/p2-wave/probes/AUD-0057/probe2_mutate_defaults.py "
                "and compare the mutation receipt before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0057/probe2_mutate_defaults.py",
                    f"holes_confirmed={holes_confirmed} both_states={both_states}",
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
                "id": "AUD-0057-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0057-D-SUITE-HOLES",
                "severity": "P2",
                "status": "open" if suite_holes else "resolved",
                "summary": (
                    f"suite_local_holes={suite_holes}; planted+mutation-gate weak "
                    f"suites confirmed; holes_confirmed={holes_confirmed}."
                ),
            },
        ]

    findings_sample = []
    for h in (p1.get("suite_local_holes") or [])[:30]:
        findings_sample.append(
            {
                "test_file": h["test_file"],
                "func": h["func"],
                "param": h["param"],
                "default_repr": h["default_repr"],
                "supply_count": h["supply_count"],
                "global_status": h["global_status"],
                "kind": "suite-local-hole",
            }
        )
    for r in (p1.get("high_risk_unexercised") or [])[:10]:
        findings_sample.append(
            {
                "path": r["path"],
                "func": r["func"],
                "param": r["param"],
                "default_repr": r["default_repr"],
                "supply_count": r["supply_count"],
                "kind": "global-unexercised",
            }
        )

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0057",
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
                    f"Probe 1 AST census: sources={p1['source_file_count']} "
                    f"tests={p1['test_file_count']} defs={defs_n} "
                    f"unexercised={unex} exercised={exercised} "
                    f"suite_local_holes={suite_holes} "
                    f"high_risk_unexercised={high_unex}; "
                    f"planted_unex={p1['control']['planted_unexercised_status']} "
                    f"planted_ex={p1['control']['planted_exercised_status']}; "
                    f"control_ok={control1}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0057/probe1-default-census.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0057/probe1_default_census.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-default-census.json",
                        json.dumps(
                            {
                                "unexercised_count": unex,
                                "suite_local_hole_count": suite_holes,
                                "high_risk_unexercised_count": high_unex,
                                "control_ok": control1,
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
                    f"Probe 2 scratch-worktree mutation: mode={p2['worktree_mode']}; "
                    f"both_states={both_states} holes_confirmed={holes_confirmed}; "
                    f"weak_hole={p2.get('mutation_gate_weak_hole_confirmed')} "
                    f"strong_kills={p2.get('mutation_gate_strong_kills_mutant')} "
                    f"completion_red={p2.get('completion_default_exercised_turns_red')}; "
                    f"control_ok={control2}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0057/probe2-mutate-defaults.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0057/probe2_mutate_defaults.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-mutate-defaults.json",
                        json.dumps(
                            {
                                "control_ok": control2,
                                "both_states": both_states,
                                "holes_confirmed_count": holes_confirmed,
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
                "id": "AUD-0057-planted-both-states",
                "name": (
                    "both-states control: covered default mutation turns RED; "
                    "unexercised default mutation stays GREEN"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0057/probe2_mutate_defaults.py",
                "result": "PASS" if both_states else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-800:],
            },
            {
                "id": "AUD-0057-mutation-gate-weak-hole",
                "name": (
                    "DEFAULT_MIN_BYTES mutation survives weak suite (GREEN) and is "
                    "killed by strong suite (RED)"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0057/probe2_mutate_defaults.py",
                "result": (
                    "PASS"
                    if p2.get("mutation_gate_weak_hole_confirmed")
                    and p2.get("mutation_gate_strong_kills_mutant")
                    else "FAIL"
                ),
                "assertions": 2,
                "output_tail": raw2[-600:],
            },
            {
                "id": "AUD-0057-mention-only-not-counted",
                "name": "use-vs-mention: string mentions must not inflate call sites",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0057/probe1_default_census.py",
                "result": (
                    "PASS"
                    if p1["control"]["mention_only_call_hits"] == 0
                    else "FAIL"
                ),
                "assertions": 1,
                "output_tail": raw1[-400:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0057-C1",
                "known-broken-fixture",
                "Planted covered default must turn RED when mutated (harness can go red).",
                True,
                True,
                bad="covered default mutation stayed green",
                good=f"planted_exercised_turned_red={p2['control']['planted_exercised_turned_red']}",
            ),
            L.control(
                "AUD0057-C2",
                "mutation",
                "Planted unexercised default must stay GREEN when mutated (hole confirmed).",
                True,
                True,
                bad="unexercised default mutation turned red (false hole)",
                good=f"planted_unexercised_stayed_green={p2['control']['planted_unexercised_stayed_green']}",
            ),
            L.control(
                "AUD0057-C3",
                "malformed-input",
                "mention_only_noise.py strings must not count as Call sites.",
                True,
                True,
                bad="mention-only strings inflated call_site_count",
                good=f"mention_only_call_hits={p1['control']['mention_only_call_hits']}",
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
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0057/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
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
                    "CLI flag defaults and config-file defaults outside Python "
                    "function signatures are in census scope per the BLD twin but "
                    "not scanned by this AST pass."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend probe 1 to argparse/click option defaults and JSON/YAML "
                    "config keys with zero exercising callers."
                ),
            },
            {
                "claim": (
                    "CI-invocation join (BLD twin): a default unexercised in the "
                    "SHIPPED configuration when CI never passes the flag."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Join suite-local holes to quality.yml invocation argv; report "
                    "defaults never passed by CI."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0057-C1", "AUD0057-C2", "AUD0057-C3"],
            "observations": [
                {
                    "name": "defs_with_defaults",
                    "measured": defs_n,
                    "method": "AST FunctionDef defaults in scoped production modules",
                    "anchor": "command-center/p2-wave/probes/AUD-0057/probe1-default-census.json",
                },
                {
                    "name": "unexercised_count",
                    "measured": unex,
                    "method": "all test Call/kwargs sites supply the param explicitly",
                    "anchor": "command-center/p2-wave/probes/AUD-0057/probe1-default-census.raw.txt",
                },
                {
                    "name": "suite_local_hole_count",
                    "measured": suite_holes,
                    "method": "per-test-file supply>0 omit=0 for high-risk defaults",
                    "anchor": "command-center/p2-wave/probes/AUD-0057/probe1-default-census.json",
                },
                {
                    "name": "holes_confirmed_count",
                    "measured": holes_confirmed,
                    "method": "scratch worktree default mutation stays GREEN",
                    "anchor": "command-center/p2-wave/probes/AUD-0057/probe2-mutate-defaults.json",
                },
                {
                    "name": "both_states_control_ok",
                    "measured": both_states,
                    "method": "covered→RED and unexercised→GREEN planted mutations",
                    "anchor": "command-center/p2-wave/probes/AUD-0057/probe2-mutate-defaults.raw.txt",
                },
            ],
            "findings_sample": findings_sample,
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-finding",
            "wave": "p2",
            "anti_false_green": anti,
            "probe1_summary": {
                "unexercised_count": unex,
                "exercised_count": exercised,
                "suite_local_hole_count": suite_holes,
                "high_risk_unexercised_count": high_unex,
            },
            "probe2_summary": {
                "holes_confirmed_count": holes_confirmed,
                "both_states": both_states,
                "worktree_mode": p2.get("worktree_mode"),
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-default-census.json",
        PROBE / "probe2-mutate-defaults.json",
        PROBE / "probe1-default-census.raw.txt",
        PROBE / "probe2-mutate-defaults.raw.txt",
        PROBE / "fixtures" / "planted_defaults.py",
        PROBE / "fixtures" / "test_planted_weak.py",
        PROBE / "fixtures" / "test_planted_strong.py",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0057 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

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
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out3.strip())
    return 0 if rc_adm3 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
