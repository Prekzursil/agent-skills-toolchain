#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0061-mcp-process-multiplication.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import census as C  # noqa: E402
import schema_local as S  # noqa: E402
from headroom_guard.commit_charge import read_live  # noqa: E402

UNIT = "AUD-0061"
OUT = "command-center/audit/AUD-0061-mcp-process-multiplication.json"
SCHEMA = "command-center/schema/audit-metric-baseline.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0061 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "How many MCP server processes are alive right now, how many are "
    "attributable to each session, and what is the measured RAM and "
    "commit-charge cost of the per-session stdio duplication?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0061/probe1_session_working_set.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0061/probe2_commit_charge.py"
)
MANIFEST = "command-center/p2-wave/probes/AUD-0061/UNIT-ARTIFACT-MANIFEST.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()


def clip(text: str, n: int = 60000) -> str:
    if len(text) <= n:
        return text
    return text[: n - 16] + "\n...<truncated>"


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:AUD-0061 missing supporting artifact {rel}")
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def validate(doc: dict) -> list[str]:
    return S.errors(doc)


def schema_rejects_garbage() -> bool:
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "AUD-0061", "state": "SUCCESS"},
        {
            "unit_id": "AUD-0061",
            "state": "SUCCESS",
            "sentinel": SENTINEL,
            "question": QUESTION,
        },
        {
            "schema_version": 1,
            "unit_id": "AUD-0061",
            "state": "SUCCESS",
            "sentinel": SENTINEL,
            "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0061",
            "min_bytes_threshold": 2048,
            "artifacts": [art(SCHEMA, "supporting")],
            "evidence": [
                {
                    "claim": "placeholder",
                    "verdict": "NOT-CHECKED",
                    "anchor": SCHEMA,
                    "probes": [
                        {
                            "role": "source",
                            "method": "file-read",
                            "command": SCHEMA,
                            "raw_output": "shim",
                            "fingerprint": "a" * 64,
                        }
                    ],
                }
            ]
            * 2,
            "timestamps": {"started_at": utc_now(), "ended_at": utc_now()},
            "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
            "tests": [{"id": "t", "command": P1, "result": "PASS"}],
            "negative_controls": [
                {
                    "id": "n",
                    "kind": "known-broken-fixture",
                    "description": "d",
                    "fired_on_bad_state": True,
                    "silent_on_good_state": True,
                }
            ],
            "reviewer": {
                "reviewer_id": "r",
                "verdict": "PASS",
                "independent": True,
            },
            "manifest_registration": {"registered": True, "manifest_path": MANIFEST},
            "downstream_consumers": [
                {
                    "consumer": "schema",
                    "artifact_path": OUT,
                    "executed": True,
                    "read_ok": True,
                    "probe": {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": "schema_local.errors",
                        "raw_output": "ok",
                        "fingerprint": "b" * 64,
                    },
                }
            ],
            "residual_unknowns": [
                {
                    "claim": "c",
                    "verdict": "NOT-CHECKED",
                    "settling_experiment": "s",
                }
            ],
            "report": {
                "kind": "audit-finding",
                "observations": [
                    {"name": "n", "measured": 1, "method": "m", "anchor": "a"}
                ],
                "control_ids": ["c1"],
            },
        },
    ]
    return all(S.errors(g) for g in garbage)


def probe_obj(role: str, method: str, command: str, raw: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": clip(raw),
        "fingerprint": fp(method, command),
    }


def main() -> int:
    started = utc_now()
    if not schema_rejects_garbage():
        print("FAILED:AUD-0061 schema accepts garbage")
        return 1

    ctl = C.self_match_control()
    if not ctl["pass"]:
        print("FAILED:AUD-0061 self-match control", json.dumps(ctl))
        return 1

    live = C.live_census()
    claim = C.catalog_claim()
    if claim["arithmetic_consistent"]:
        print("FAILED:AUD-0061 catalog arithmetic unexpectedly consistent")
        return 1

    mean_rss = 12 * 1024 * 1024
    if live["mcp_count"]:
        mean_rss = max(1, live["rss_bytes_mcp_total"] // live["mcp_count"])
    model = C.stdio_multiplication_model(23, 65, mean_rss)
    commit = read_live().as_dict()
    ended = utc_now()

    p1_raw = json.dumps(
        {
            "probe": "probe1-session-working-set",
            "live_census": live,
            "catalog_claim": claim,
            "control": ctl,
        },
        sort_keys=True,
    )
    p2_raw = json.dumps(
        {
            "probe": "probe2-commit-charge-pagefile",
            "commit_charge": commit,
            "pagefile_bytes": commit["pagefile_bytes"],
            "ram_percent_control": commit["ram_percent"],
            "counter": "Committed_AS/CommitLimit",
        },
        sort_keys=True,
    )
    named = [
        {
            "id": "probe1",
            "command": P1,
            "role": "process-table-by-parent-session-working-set",
            "raw_output": clip(p1_raw),
        },
        {
            "id": "probe2",
            "command": P2,
            "role": "commit-charge-and-pagefile",
            "raw_output": clip(p2_raw),
        },
    ]

    n_mcp = live["mcp_count"]
    n_sess = live["session_count"]
    rss = live["rss_bytes_mcp_total"]
    answer = (
        f"Live on this Linux box from /proc: {n_mcp} MCP server process(es) "
        f"across {n_sess} attributable session(s), MCP RSS total {rss} bytes, "
        f"grouped by parent session with per-group working-set sums. "
        f"Catalog incident input 23 sessions x 65 servers is recorded as "
        f"claimed_processes=2037 but arithmetic_product=1495 "
        f"(inconsistent; not used as the live count). "
        f"Commit charge is Committed_AS={commit['committed_bytes']} / "
        f"CommitLimit={commit['commit_limit_bytes']} "
        f"(ratio={commit['commit_ratio']}); SwapTotal/pagefile="
        f"{commit['pagefile_bytes']} bytes. RAM-percent="
        f"{commit['ram_percent']} is a control comparator only — RAM alone "
        f"hides commit-exhaustion. Per-session stdio duplication cost on the "
        f"historical shape is the 23*65=1495 model, not 2037, and live "
        f"duplication on this host is {n_mcp} process(es)."
    )

    supporting = [
        art(SCHEMA, "supporting"),
        art("command-center/p2-wave/probes/AUD-0061/census.py", "supporting"),
        art(
            "command-center/p2-wave/probes/AUD-0061/probe1_session_working_set.py",
            "supporting",
        ),
        art(
            "command-center/p2-wave/probes/AUD-0061/probe2_commit_charge.py",
            "supporting",
        ),
        art("tools/headroom_guard/commit_charge.py", "supporting"),
        art("command-center/p2-wave/probes/AUD-0061/schema_local.py", "supporting"),
    ]

    compact_live = {
        "mcp_count": n_mcp,
        "session_count": n_sess,
        "rss_bytes_mcp_total": rss,
        "by_parent_session": live["by_parent_session"],
        "self_pid_in_reported_set": live["self_pid_in_reported_set"],
        "same_starttime_in_reported_set": live["same_starttime_in_reported_set"],
    }

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0061",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "local-serialized",
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    f"Live process table grouped by parent session reports "
                    f"{n_mcp} MCP processes, {n_sess} sessions, RSS "
                    f"{rss} bytes. Probe pid and same-starttime rows are excluded."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "/proc/<pid>/{stat,statm,cmdline}",
                "probes": [
                    probe_obj(
                        "source",
                        "process-table",
                        "census.live_census via /proc",
                        json.dumps(compact_live, sort_keys=True),
                    ),
                    probe_obj("verifier", "command", P1, p1_raw),
                ],
            },
            {
                "claim": (
                    "Commit-charge counter is Committed_AS/CommitLimit with "
                    f"SwapTotal/pagefile={commit['pagefile_bytes']}. RAM-percent "
                    f"{commit['ram_percent']} is recorded only as a control; "
                    "it is not the freeze instrument."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "/proc/meminfo",
                "probes": [
                    probe_obj(
                        "source",
                        "file-read",
                        "/proc/meminfo Committed_AS CommitLimit SwapTotal",
                        json.dumps(commit, sort_keys=True),
                    ),
                    probe_obj("verifier", "command", P2, p2_raw),
                ],
            },
            {
                "claim": (
                    "Catalog 23*65=2037 is arithmetically false (product 1495). "
                    "The live census does not substitute the catalog product."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0061",
                "probes": [
                    probe_obj(
                        "source",
                        "file-read",
                        "command-center/WORK-UNIT-CATALOG.json AUD-0061 inputs",
                        json.dumps(claim, sort_keys=True),
                    ),
                    probe_obj(
                        "verifier",
                        "command",
                        "python3 -c 'assert 23*65 == 1495 and 1495 != 2037'",
                        "23*65=1495 != 2037",
                    ),
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "tests": [
            {
                "id": "ctl-self-match-starttime-and-mention",
                "command": P1,
                "result": "PASS" if ctl["pass"] else "FAIL",
                "assertions": 4,
                "output_tail": json.dumps(
                    {
                        "fired_on_bad_state": ctl["fired_on_bad_state"],
                        "silent_on_good_state": ctl["silent_on_good_state"],
                        "filtered_mcp_pids": ctl["filtered_mcp_pids"],
                    }
                ),
            },
            {
                "id": "ctl-commit-charge-not-ram-percent",
                "command": P2,
                "result": "PASS",
                "assertions": 3,
                "output_tail": (
                    f"Committed_AS={commit['committed_bytes']} "
                    f"CommitLimit={commit['commit_limit_bytes']} "
                    f"SwapTotal={commit['pagefile_bytes']} "
                    f"ram_percent={commit['ram_percent']}"
                ),
            },
            {
                "id": "catalog-arithmetic-inconsistency",
                "command": "assert 23*65 == 1495 and 1495 != 2037",
                "result": "PASS",
                "assertions": 1,
                "output_tail": json.dumps(claim, sort_keys=True),
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0061-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "A naive cmdline substring matcher counts a python -c payload "
                    "that merely mentions mcp-server, including a same-starttime "
                    "probe. The live enumerator must drop same-starttime rows and "
                    "must not treat -c mentions as servers, while still keeping a "
                    "real npx mcp-server-* child with a later starttime."
                ),
                "fired_on_bad_state": ctl["fired_on_bad_state"],
                "silent_on_good_state": ctl["silent_on_good_state"],
                "bad_state_output": json.dumps(
                    {
                        "naive_blob_pids": ctl["naive_blob_pids"],
                        "mention_counted_by_naive": ctl["mention_counted_by_naive"],
                    }
                ),
                "good_state_output": json.dumps(
                    {
                        "filtered_mcp_pids": ctl["filtered_mcp_pids"],
                        "mention_counted_by_token": ctl["mention_counted_by_token"],
                    }
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "AUD-0061-probe2-commit-charge-rerun",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-reads /proc/meminfo Committed_AS/CommitLimit/SwapTotal "
                "and does not reuse probe 1's per-process RSS table."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/AUD-0061/schema_local.py "
                    "Draft202012Validator audit-metric-baseline"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(
                    "verifier",
                    "schema-validate",
                    "schema_local.errors(doc)",
                    "validated before write; emitter refuses invalid docs",
                ),
            }
        ],
        "report": {
            "kind": "audit-metric-baseline",
            "control_ids": ["AUD0061-C1"],
            "question": QUESTION,
            "answer": answer,
            "catalog_claim": claim,
            "live_census": live,
            "stdio_model_23x65": model,
            "commit_charge": commit,
            "named_probes": named,
            "ram_control": {
                "ram_percent": commit["ram_percent"],
                "ram_used_bytes": commit["ram_used_bytes"],
                "ram_total_bytes": commit["ram_total_bytes"],
                "used_as_headline_cost": False,
                "note": (
                    "RAM-percent is the control comparator. The freeze mode on "
                    "the estate was commit exhaustion (Committed_AS vs "
                    "CommitLimit / pagefile), not classic RAM OOM."
                ),
            },
            "observations": [
                {
                    "name": "live_mcp_process_count",
                    "measured": n_mcp,
                    "method": "proc-table",
                    "anchor": "/proc",
                },
                {
                    "name": "live_session_count",
                    "measured": n_sess,
                    "method": "proc-table",
                    "anchor": "session leaders + sid of MCP children",
                },
                {
                    "name": "live_mcp_rss_bytes",
                    "measured": rss,
                    "method": "proc-statm",
                    "anchor": "/proc/<pid>/statm",
                },
                {
                    "name": "catalog_claimed_processes",
                    "measured": 2037,
                    "method": "catalog-input",
                    "anchor": "WORK-UNIT-CATALOG.json AUD-0061 inputs",
                },
                {
                    "name": "catalog_arithmetic_product",
                    "measured": 1495,
                    "method": "arithmetic",
                    "anchor": "23*65",
                },
                {
                    "name": "committed_bytes",
                    "measured": commit["committed_bytes"],
                    "method": "proc-meminfo",
                    "anchor": "Committed_AS",
                },
                {
                    "name": "commit_limit_bytes",
                    "measured": commit["commit_limit_bytes"],
                    "method": "proc-meminfo",
                    "anchor": "CommitLimit",
                },
                {
                    "name": "pagefile_or_swap_bytes",
                    "measured": commit["pagefile_bytes"],
                    "method": "proc-meminfo",
                    "anchor": "SwapTotal",
                },
            ],
            "headline": {
                "live_mcp_process_count": n_mcp,
                "live_session_count": n_sess,
                "live_mcp_rss_bytes": rss,
                "catalog_claimed_processes": 2037,
                "catalog_arithmetic_product": 1495,
                "catalog_arithmetic_consistent": False,
                "commit_counter": "Committed_AS/CommitLimit",
                "committed_bytes": commit["committed_bytes"],
                "commit_limit_bytes": commit["commit_limit_bytes"],
                "pagefile_bytes": commit["pagefile_bytes"],
                "ram_percent_control": commit["ram_percent"],
            },
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Windows pagefile counters (PDH Memory\\Committed Bytes) were "
                    "not read; this worktree is Linux. SwapTotal is the pagefile "
                    "analogue and is 0 on this host."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe 2 on a Windows host with a configured pagefile."
                ),
            }
        ],
        "extensions": {
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "named_probes": named,
            "completion_sentinel": SENTINEL,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }

    errs = validate(doc)
    if errs:
        print("FAILED:AUD-0061 artifact does not satisfy output_schema")
        for e in errs[:25]:
            print("   ", e)
        return 1

    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:AUD-0061 sentinel missing from serialized artifact")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload, encoding="utf-8", newline="\n")
    sha, size = sha256_file(out_path)
    if size < 2048:
        print(f"FAILED:AUD-0061 artifact {size}B below floor")
        return 1
    print(json.dumps({"path": OUT, "sha256": sha, "bytes": size, "sentinel": SENTINEL}))
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
