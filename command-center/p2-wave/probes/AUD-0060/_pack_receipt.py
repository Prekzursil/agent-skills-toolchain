#!/usr/bin/env python3
"""Pack AUD-0060 MCP tool-surface inventory.

Honest BLOCKED: owner-host live MCP fleet unreachable on linux-cursor-cloud;
planted control + session namespaces measured; catalog requires fresh-context
Claude falsify review before SUCCESS. Never stubs SUCCESS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0060"
OUT = "command-center/audit/AUD-0060-mcp-tool-surface-inventory.json"
SCHEMA = "command-center/schema/audit-metric-baseline.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0060/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


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
    p1 = json.loads((PROBE / "probe1-tool-surface.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-usage-trace.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-tool-surface.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-usage-trace.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None and bool(p1.get("owner_host_mcp_reachable"))
    # SUCCESS also requires owner-host reachability — never green on planted-only.
    started = "2026-09-07T20:10:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    enabled = int(p1["aud0015_enabled_declared_count"])
    unreachable = int(p1["aud0015_enabled_unreachable_count"])
    session_tools = int(p1["session_tool_count_sum"])
    session_schema = int(p1["session_schema_bytes_sum"])
    live_nonzero = int(p1["live_nonzero_server_count"])
    control1 = bool(p1["control"]["ok"])
    control2 = bool(p2["control"]["ok"])
    hist_verified = int(
        (p2.get("historical_capability_matrix") or {}).get("call_verified_count") or 0
    )
    planted_tc = (p1.get("planted_control_row") or {}).get("tool_count")
    planted_sb = (p1.get("planted_control_row") or {}).get("schema_bytes")

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
            "command-center/p2-wave/probes/AUD-0060/probe1-tool-surface.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0060/probe2-usage-trace.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0060/probe1-tool-surface.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0060/probe2-usage-trace.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0060/fixtures/planted_zero_tools_server.py",
            "control",
        ),
        L.art(
            "tools/mcp/mcp-http-host/_fake_mcp_server.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0060/fixtures/session_namespace_census.json",
            "fixture",
        ),
        L.art(
            "command-center/audit/AUD-0015-mcp-scope-resolution.json",
            "supporting",
        ),
    ]
    if rev is not None:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0060/independent-review.json",
                "supporting",
            )
        )

    question = (
        "For every configured MCP server, how many tools does it expose, what is "
        "the token cost of those tool definitions, and which of them does this "
        "program actually need?"
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
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0060"
        headline = (
            f"enabled_declared={enabled} live_nonzero={live_nonzero} "
            f"session_tools={session_tools} planted_tools={planted_tc}. "
            "Independent re-review PASS."
        )
        failure = None
        anti = "SUCCESS-after-independent-re-review-PASS"
        defects = [
            {
                "id": "AUD-0060-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Independent fresh-context Claude review PASS recorded.",
            }
        ]
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not seen "
                "this unit's transcript and must try to FALSIFY the headline count "
                "before PASS. Owner-host MCP unreachable on this substrate; review unpaid; BLOCKED."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0060 planted control + session namespaces measured; "
            f"AUD-0015 enabled_declared={enabled} all UNREACHABLE on "
            "linux-cursor-cloud (tool_count=null, not invented); "
            "blocked-on-independent-review+scope-mismatch"
        )
        headline = (
            f"enabled_declared={enabled} unreachable={unreachable} "
            f"session_tools={session_tools} session_schema_bytes={session_schema} "
            f"planted_fake_mcp_tools={planted_tc} schema_bytes={planted_sb} "
            f"hist_call_verified={hist_verified}; "
            "owner_host_mcp_reachable=False. BLOCKED on independent fresh-context "
            "Claude falsify review + live MCP scope-mismatch."
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "detector-failure",
                "scope-mismatch",
            ],
            "reason": (
                "Named probes completed with planted non-zero control and session "
                "namespace census, but AUD-0015 ENABLED-DECLARED owner-host servers "
                "are unreachable on linux-cursor-cloud (tool counts left null) and "
                "catalog reviewer_requirement is unmet (fresh-context Claude must "
                "falsify headline counts)."
            ),
            "diagnostic_tail": (
                f"enabled={enabled} unreachable={unreachable} "
                f"session_tools={session_tools} planted_tools={planted_tc} "
                f"control1={control1} control2={control2} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Re-run on a substrate with owner-host MCP mounted OR accept "
                "session+planted scope explicitly; then dispatch one fresh-context "
                "Claude reviewer who has not seen this unit's transcript to FALSIFY "
                f"headline session_tools={session_tools} "
                f"enabled_declared={enabled} unreachable={unreachable} "
                "before PASS, not re-read the artifact."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0060/probe1_tool_surface.py",
                    f"live_nonzero={live_nonzero} unreachable={unreachable}",
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
        anti = "BLOCKED-pending-independent-review-with-real-probes-no-invented-counts"
        defects = [
            {
                "id": "AUD-0060-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Independent fresh-context Claude review unpaid; headline tool "
                    "counts must be falsified by a reviewer who did not author this census."
                ),
            },
            {
                "id": "AUD-0060-D-SCOPE",
                "severity": "P1",
                "status": "open",
                "summary": (
                    f"All {unreachable}/{enabled} AUD-0015 ENABLED-DECLARED servers "
                    "UNREACHABLE on linux-cursor-cloud; live tool_count left null "
                    "(not invented as zero)."
                ),
            },
            {
                "id": "AUD-0060-D-USAGE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "Owner-host session usage corpus not mounted; cannot settle "
                    "large-surface-zero-invocation finding. Historical "
                    f"call_verified={hist_verified} from capability-matrix artifact."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0060",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "linux-cursor-cloud",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1: planted fake-mcp tools={planted_tc} "
                    f"schema_bytes={planted_sb}; AUD-0015 enabled_declared={enabled} "
                    f"unreachable={unreachable} (tool_count=null); "
                    f"session_tools={session_tools} "
                    f"session_schema_bytes={session_schema}; "
                    f"control_ok={control1} enumerator_reaching={p1.get('enumerator_reaching')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0060/probe1-tool-surface.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0060/probe1_tool_surface.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-tool-surface.json",
                        json.dumps(
                            {
                                "enabled": enabled,
                                "unreachable": unreachable,
                                "session_tools": session_tools,
                                "planted_tools": planted_tc,
                                "control_ok": control1,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2: planted whoami tools/call ok={control2}; "
                    f"owner_session_corpus_mounted=False; "
                    f"historical_call_verified={hist_verified}; "
                    f"text_corpus_distinct="
                    f"{(p2.get('text_corpus') or {}).get('distinct_invocation_fingerprints')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0060/probe2-usage-trace.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0060/probe2_usage_trace.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe2-usage-trace.json",
                        json.dumps(
                            {
                                "control_ok": control2,
                                "hist_call_verified": hist_verified,
                                "owner_sessions_mounted": False,
                            }
                        ),
                        0,
                    ),
                ],
                "likely",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0060-control-nonzero-connected",
                "name": (
                    "control: counter reports non-zero tool count for a server "
                    "known to be connected (planted fake-mcp)"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0060/probe1_tool_surface.py",
                "result": "PASS"
                if p1["control"].get("fired_nonzero_on_connected")
                else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-800:],
            },
            {
                "id": "AUD-0060-control-zero-empty",
                "name": "both-states: planted zero-tools server reports tool_count=0",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0060/probe1_tool_surface.py",
                "result": "PASS"
                if p1["control"].get("silent_zero_on_empty")
                else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-500:],
            },
            {
                "id": "AUD-0060-planted-usage-call",
                "name": "control: planted tools/call whoami records an invocation",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0060/probe2_usage_trace.py",
                "result": "PASS" if control2 else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-500:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0060-C1",
                "known-broken-fixture",
                "Connected planted fake-mcp must report tool_count>0.",
                True,
                True,
                bad="planted fake-mcp reported zero or failed handshake",
                good=f"planted_tools={planted_tc}",
            ),
            L.control(
                "AUD0060-C2",
                "mutation",
                "Planted zero-tools server must report tool_count=0 (not null).",
                True,
                True,
                bad="zero-tools server did not report exact 0",
                good=f"zero_tools={p1['control']['planted_zero_tools'].get('tool_count')}",
            ),
            L.control(
                "AUD0060-C3",
                "malformed-input",
                "UNREACHABLE owner-host servers must keep tool_count=null (not invented 0).",
                True,
                True,
                bad="unreachable servers given invented numeric tool_count",
                good=f"unreachable_null_counts={unreachable}",
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
                "two strikes then pivot (AGENTS.md 4b): after the second failure with "
                "the same detector, enumerate at least 2 mechanically different "
                "detectors before a third attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live tools/list counts for all AUD-0015 ENABLED-DECLARED "
                    "owner-host MCP servers."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 on the owner Windows host with ~/.claude.json "
                    "mounted using command-center/mcp-audit/probe_capability.py "
                    "--mounted and join to this receipt."
                ),
            },
            {
                "claim": (
                    "Which exposed tools have zero invocations across recent "
                    "owner-host sessions (large surface, unused)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Ingest Claude/Cursor session transcripts and tally "
                    "mcp__<server>__<tool> invocations per server."
                ),
            },
        ],
        "report": {
            "kind": "audit-metric-baseline",
            "question": question,
            "headline": headline,
            "observations": [
                {
                    "name": "aud0015_enabled_declared_count",
                    "measured": enabled,
                    "method": "AUD-0015 report.servers effective_state=ENABLED-DECLARED",
                    "anchor": "command-center/audit/AUD-0015-mcp-scope-resolution.json",
                },
                {
                    "name": "aud0015_enabled_unreachable_count",
                    "measured": unreachable,
                    "method": "live tools/list attempt on linux-cursor-cloud",
                    "anchor": "command-center/p2-wave/probes/AUD-0060/probe1-tool-surface.json",
                },
                {
                    "name": "session_tool_count_sum",
                    "measured": session_tools,
                    "method": "GetDynamicTools ready namespaces on this session",
                    "anchor": "command-center/p2-wave/probes/AUD-0060/fixtures/session_namespace_census.json",
                },
                {
                    "name": "session_schema_bytes_sum",
                    "measured": session_schema,
                    "method": "len(json.dumps(tools, sort_keys=True)) per ready namespace",
                    "anchor": "command-center/p2-wave/probes/AUD-0060/fixtures/session_namespace_census.json",
                },
                {
                    "name": "planted_fake_mcp_tool_count",
                    "measured": int(planted_tc or 0),
                    "method": "stdio initialize+tools/list vs _fake_mcp_server.py",
                    "anchor": "command-center/p2-wave/probes/AUD-0060/probe1-tool-surface.raw.txt",
                },
                {
                    "name": "planted_fake_mcp_schema_bytes",
                    "measured": int(planted_sb or 0),
                    "method": "serialized tools/list payload bytes",
                    "anchor": "command-center/p2-wave/probes/AUD-0060/probe1-tool-surface.json",
                },
                {
                    "name": "historical_call_verified_count",
                    "measured": hist_verified,
                    "method": "command-center/mcp-audit/capability-matrix.json summary",
                    "anchor": "command-center/mcp-audit/capability-matrix.json",
                },
                {
                    "name": "live_nonzero_server_count",
                    "measured": live_nonzero,
                    "method": "planted + session namespaces with tool_count>0",
                    "anchor": "command-center/p2-wave/probes/AUD-0060/probe1-tool-surface.json",
                },
            ],
            "control_ids": ["AUD0060-C1", "AUD0060-C2", "AUD0060-C3"],
        },
        "extensions": {
            "anti_false_green": anti,
            "wave": "p2-wave1",
            "artifact_class": "audit-metric-baseline",
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "owner_host_mcp_reachable": False,
            "probe1_summary": {
                "enabled": enabled,
                "unreachable": unreachable,
                "session_tools": session_tools,
                "session_schema_bytes": session_schema,
                "planted_tools": planted_tc,
            },
            "probe2_summary": {
                "planted_call_ok": control2,
                "hist_call_verified": hist_verified,
                "owner_sessions_mounted": False,
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-tool-surface.json",
        PROBE / "probe2-usage-trace.json",
        PROBE / "probe1-tool-surface.raw.txt",
        PROBE / "probe2-usage-trace.raw.txt",
        PROBE / "fixtures" / "planted_zero_tools_server.py",
        PROBE / "fixtures" / "session_namespace_census.json",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0060 missing probe outputs:", *missing, sep="\n")
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
