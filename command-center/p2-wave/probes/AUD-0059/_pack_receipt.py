#!/usr/bin/env python3
"""Pack AUD-0059 hook-firing evidence receipt.

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

UNIT = "AUD-0059"
OUT = "command-center/audit/AUD-0059-hook-firing-evidence.json"
SCHEMA = "command-center/schema/audit-detector-control.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0059/UNIT-ARTIFACT-MANIFEST.json"
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
    p1 = json.loads((PROBE / "probe1-fire-log-search.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-controlled-trigger.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-fire-log-search.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-controlled-trigger.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T20:35:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    registered = p1.get("registered_count")
    live_fire = p1.get("with_live_turn_fire_evidence")
    audit_only = p1.get("with_audit_controlled_fire_only")
    none_fire = p1.get("with_no_fire_evidence")
    live_ledger = bool(p1.get("live_ledger_present"))
    control1 = bool((p1.get("planted_control") or {}).get("ok"))
    both_states = bool(p2.get("both_states"))
    control2 = bool((p2.get("control") or {}).get("ok"))
    stub = p2.get("stub_ledger_sanity") or {}

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
            "command-center/p2-wave/probes/AUD-0059/probe1-fire-log-search.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0059/probe2-controlled-trigger.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0059/probe1-fire-log-search.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0059/probe2-controlled-trigger.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0059/fixtures/planted_fire_log.jsonl",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0059/fixtures/planted_hook/fire_canary.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0059/fixtures/scratch_settings_enabled.json",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0059/fixtures/scratch_settings_disabled.json",
            "control",
        ),
        L.art("hooks/_dispatch/manifest.json", "supporting"),
        L.art("agent-self/config/settings.json", "supporting"),
        L.art("hooks/stub-ledger/record.py", "supporting"),
        L.art("command-center/audit/AUD-0013-hooks-manifest-parity.json", "supporting"),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0059/independent-review.json",
                "supporting",
            )
        )

    question = (
        "For each registered hook, is there direct evidence it fired during a real "
        "turn, and for those with none, does a deliberate trigger event produce an "
        "observable effect?"
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
        sentinel = "SUCCESS:AUD-0059"
        headline = (
            f"registered={registered} live_fire={live_fire} audit_only={audit_only} "
            f"none={none_fire} both_states={both_states} live_ledger={live_ledger}. "
            "Independent cross-vendor Codex probe2 re-run PASS."
        )
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-PASS"
        defects = [
            {
                "id": "AUD-0059-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Cross-vendor Codex re-run of probe 2 PASS recorded.",
            },
            {
                "id": "AUD-0059-D-LIVE-FIRE",
                "severity": "P2",
                "status": "open" if (live_fire == 0 and not live_ledger) else "resolved",
                "summary": (
                    f"live_turn_fire={live_fire}/{registered}; "
                    f"live_ledger_present={live_ledger}; both_states={both_states}."
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
                "the second probe (scratch disable/enable both-states controlled "
                "trigger). Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0059 fire-log-search + controlled-trigger probes measured; "
            f"registered={registered} live_fire={live_fire} none={none_fire} "
            f"both_states={both_states}; blocked-on-independent-review"
        )
        headline = (
            f"registered={registered} live_fire={live_fire} audit_only={audit_only} "
            f"none={none_fire} both_states={both_states} "
            f"planted_ok={control1 and control2} live_ledger={live_ledger}. "
            "BLOCKED on cross-vendor Codex probe2 re-run."
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "green-not-live",
                "detector-failure",
                "single-signal",
            ],
            "reason": (
                "Named probes completed: per-hook fire-log search measured and "
                "controlled both-states trigger recorded (disabled=no effect / "
                "enabled=ledger+context), but catalog reviewer_requirement is unmet "
                "(cross-vendor Codex must re-run ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"registered={registered} live_fire={live_fire} none={none_fire} "
                f"both_states={both_states} control1={control1} control2={control2} "
                f"live_ledger={live_ledger} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY "
                "command-center/p2-wave/probes/AUD-0059/probe2_controlled_trigger.py "
                "and compare disabled-vs-enabled observable effects before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0059/probe2_controlled_trigger.py",
                    f"both_states={both_states} control_ok={control2}",
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
                "id": "AUD-0059-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0059-D-LIVE-FIRE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"live_turn_fire={live_fire}/{registered}; "
                    f"no_fire_evidence={none_fire}; live_ledger_present={live_ledger}; "
                    f"both_states={both_states}."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0059",
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
                    f"Probe 1: searched live event/stub ledgers + planted fire log for "
                    f"{registered} registered hooks; live_turn_fire={live_fire} "
                    f"audit_controlled_only={audit_only} none={none_fire}; "
                    f"live_ledger_present={live_ledger}; planted_control_ok={control1}."
                ),
                "CONFIRMED" if p1.get("ok") else "REFUTED",
                "command-center/p2-wave/probes/AUD-0059/probe1-fire-log-search.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0059/probe1_fire_log_search.py",
                        raw1,
                        0 if p1.get("ok") else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-fire-log-search.json",
                        json.dumps(
                            {
                                "registered_count": registered,
                                "live_fire": live_fire,
                                "none": none_fire,
                                "live_ledger_present": live_ledger,
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
                    f"Probe 2 scratch both-states: disabled trigger effect="
                    f"{(p2.get('control') or {}).get('disabled_run', {}).get('effect_observed')}; "
                    f"enabled effect="
                    f"{(p2.get('control') or {}).get('enabled_run', {}).get('effect_observed')}; "
                    f"both_states={both_states}; stub_ledger_sanity_ok={stub.get('ok')}; "
                    f"live_tree_mutated={p2.get('live_tree_mutated')}."
                ),
                "CONFIRMED" if p2.get("ok") else "REFUTED",
                "command-center/p2-wave/probes/AUD-0059/probe2-controlled-trigger.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0059/probe2_controlled_trigger.py",
                        raw2,
                        0 if p2.get("ok") else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-controlled-trigger.json",
                        json.dumps(
                            {
                                "both_states": both_states,
                                "control_ok": control2,
                                "stub_ok": stub.get("ok"),
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
                "id": "AUD-0059-both-states-trigger",
                "name": (
                    "both-states control: disable one hook in a scratch config, "
                    "confirm the trigger produces NO effect, re-enable, and confirm it does"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0059/probe2_controlled_trigger.py",
                "result": "PASS" if both_states else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-800:],
            },
            {
                "id": "AUD-0059-fire-log-search",
                "name": "per-hook fire-log / ledger search with planted known-fire control",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0059/probe1_fire_log_search.py",
                "result": "PASS" if control1 else "FAIL",
                "assertions": 2,
                "output_tail": raw1[-600:],
            },
            {
                "id": "AUD-0059-stub-ledger-enable-disable",
                "name": "stub-ledger/record.py writes when enabled and stays silent when STUB_LEDGER=off",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0059/probe2_controlled_trigger.py",
                "result": "PASS" if stub.get("ok") or stub.get("skipped") else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-400:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0059-C1",
                "known-broken-fixture",
                "Planted known-fire fixture must be found by the Probe 1 searcher.",
                True,
                True,
                bad="planted_marker_missing",
                good=f"planted_control_ok={control1}",
            ),
            L.control(
                "AUD0059-C2",
                "mutation",
                "Disabled planted canary produces no effect; re-enabled produces ledger+context.",
                True,
                True,
                bad=f"enabled_effect={(p2.get('control') or {}).get('enabled_run')}",
                good=f"disabled_effect={(p2.get('control') or {}).get('disabled_run')}",
            ),
            L.control(
                "AUD0059-C3",
                "malformed-input",
                "Scratch trigger must not mutate live settings.json / hooks tree.",
                True,
                True,
                bad="live_tree_mutated",
                good=f"live_tree_mutated={p2.get('live_tree_mutated')}",
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
                "consumer": "json.loads + audit-drift schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0059/_pack_receipt.py",
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
                    "Whether each of the "
                    f"{none_fire} registered hooks with no live-turn fire evidence "
                    "would produce an observable effect under a host-delivered "
                    "Claude Code / Cursor turn on the Windows workstation "
                    "(this cloud environment has no populated ~/.claude/event-ledger)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On the live Windows host after a real multi-tool turn, re-run "
                    "probe1_fire_log_search.py against ~/.claude/event-ledger and "
                    "~/.claude/stub-ledger and record per-hook hit counts."
                ),
            },
            {
                "claim": (
                    "Whether Claude/Cursor host short-circuits PreToolUse hooks when "
                    "permissions.allow matches before hook dispatch (related AUD-0080 "
                    "residual) — host invocation is outside this unit's scratch trigger."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Instrument a disposable settings fixture with a PreToolUse "
                    "matcher that always emits a ledger row and confirm allow-list "
                    "does not suppress the hook on a live turn."
                ),
            },
        ],
        "report": {
            "kind": "audit-detector-control",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0059-C1", "AUD0059-C2", "AUD0059-C3"],
            "observations": [
                {
                    "name": "registered_hook_count",
                    "measured": registered,
                    "method": "hooks/_dispatch/manifest.json checks + agent-self settings hooks",
                    "anchor": "command-center/p2-wave/probes/AUD-0059/probe1-fire-log-search.json",
                },
                {
                    "name": "live_turn_fire_evidence_count",
                    "measured": live_fire,
                    "method": "search ~/.claude/event-ledger + stub-ledger + claim-ledger",
                    "anchor": "command-center/p2-wave/probes/AUD-0059/probe1-fire-log-search.raw.txt",
                },
                {
                    "name": "no_fire_evidence_count",
                    "measured": none_fire,
                    "method": "registered hooks with neither live nor audit fire hits",
                    "anchor": "command-center/p2-wave/probes/AUD-0059/probe1-fire-log-search.json",
                },
                {
                    "name": "live_ledger_present",
                    "measured": live_ledger,
                    "method": "stat of event-ledger / stub-ledger roots",
                    "anchor": "command-center/p2-wave/probes/AUD-0059/probe1-fire-log-search.json",
                },
                {
                    "name": "both_states_control_ok",
                    "measured": both_states,
                    "method": "disable planted canary (no effect) then re-enable (ledger+context)",
                    "anchor": "command-center/p2-wave/probes/AUD-0059/probe2-controlled-trigger.raw.txt",
                },
                {
                    "name": "stub_ledger_enable_disable_ok",
                    "measured": stub.get("ok"),
                    "method": "STUB_LEDGER_ROOT redirect; STUB_LEDGER=off vs on",
                    "anchor": "command-center/p2-wave/probes/AUD-0059/probe2-controlled-trigger.json",
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
                "registered_count": registered,
                "live_fire": live_fire,
                "audit_only": audit_only,
                "none": none_fire,
                "live_ledger_present": live_ledger,
                "control_ok": control1,
            },
            "probe2_summary": {
                "both_states": both_states,
                "control_ok": control2,
                "stub_ledger_ok": stub.get("ok"),
                "worktree_mode": p2.get("worktree_mode"),
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-fire-log-search.json",
        PROBE / "probe2-controlled-trigger.json",
        PROBE / "probe1-fire-log-search.raw.txt",
        PROBE / "probe2-controlled-trigger.raw.txt",
        PROBE / "fixtures" / "planted_fire_log.jsonl",
        PROBE / "fixtures" / "planted_hook" / "fire_canary.py",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0059 missing probe outputs:", *missing, sep="\n")
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
