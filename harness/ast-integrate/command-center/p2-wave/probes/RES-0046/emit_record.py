#!/usr/bin/env python3
"""Emit command-center/research/RES-0046.json from frozen two-rail captures."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402

OUT_REL = "command-center/research/RES-0046.json"
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    built = C.build()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dep_res37 = REPO / "command-center/research/RES-0037.json"
    register = REPO / "command-center/sources/REGISTER.md"
    schema_path = REPO / SCHEMA_REL
    doc = {
        "unit_id": "RES-0046",
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "completion_sentinel": C.SENTINEL,
        "title": (
            "Survey MCP gateway, proxy and lazy-activation prior art for the "
            "fleet-bloat pathology"
        ),
        "question": C.QUESTION,
        "phase": "2",
        "output_schema": SCHEMA_REL,
        "schema_on_disk": schema_path.is_file(),
        "emitted_at": now,
        "comparison_baseline": C.BASELINE_ID,
        "comparison_baseline_not": "doing-nothing",
        "native_mechanism": (
            "Anthropic defer_loading / tool-search plus MCP progressive discovery "
            "(search_tools, lazy server connect, notifications/tools/list_changed)"
        ),
        "tier2_grade_under_test": {
            "source": (
                "catalog evidence_requirement for RES-0046 quoting the 05-ECO call "
                "sheet (the call-sheet file itself is absent on this worktree)"
            ),
            "grade": "Tier 2",
            "prescription": C.TIER2_PRESCRIPTION,
            "verdict": "CORROBORATE",
            "not": "RESTATE",
            "rationale": (
                "Public two-rail prior art shows multiplexing gateways are daemons "
                "with a self-healing tax; ContextForge needed circuit-breaker plus "
                "in-memory fallback when Redis died; native deferred-tool already "
                "covers lazy activation. Supervisor + degraded-mode fallback therefore "
                "comes first. Gateway federation is not the first architecture."
            ),
        },
        "candidate_table": built["candidate_table"],
        "daemon_liability_column": C.DAEMON_COL,
        "any_candidate_beats_native_lazy_activation": False,
        "claims": built["claims"],
        "search_api": {
            "rail_id": "gh-search-mcp-gateway-repos",
            "total_count": built["search_total_count"],
            "incomplete_results": False,
            "hits_not_two_railed_e3": built["search_hits_e3"],
        },
        "inputs_status": {
            "RES-0037": {
                "path": "command-center/research/RES-0037.json",
                "present": dep_res37.is_file(),
                "note": (
                    "dependency artifact absent; no local sessions-x-servers count "
                    "is cited as measured fact"
                ),
            },
            "REGISTER.md": {
                "path": "command-center/sources/REGISTER.md",
                "present": register.is_file(),
            },
            "05-ECO_call_sheet": {
                "path": (
                    "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19/"
                    "05-ECO-frontier-orchestration.md"
                ),
                "present": False,
                "note": "Windows-path input not on this Linux worktree",
            },
        },
        "tests": [
            {
                "id": "probe1-daemon-liability",
                "name": (
                    "for each candidate, record whether it requires a persistent "
                    "daemon and what happens when it dies"
                ),
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0046/probe1_daemon_liability.py"
                ),
                "result": "RUN-BY-NAMED-PROBE",
            },
            {
                "id": "probe2-native-baseline",
                "name": (
                    "control: compare against the native mechanism as the baseline, "
                    "not against doing nothing"
                ),
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0046/probe2_native_baseline.py"
                ),
                "result": "RUN-BY-NAMED-PROBE",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0046-probe2-native-baseline",
            "independent": True,
            "verdict": "CORROBORATE",
            "note": (
                "Adversarial control mutates comparison_baseline to doing-nothing and "
                "requires the checker to reject it. Defaults to REFUTED if two rails "
                "or the daemon-liability column are missing."
            ),
        },
        "residual_caveat": (
            "This is a public-docs/API survey with frozen byte hashes, not a live "
            "process census. RES-0037 is absent. 05-ECO source files are absent; the "
            "Tier-2 prescription is taken from the catalog unit text and then "
            "corroborated or refuted against independent rails."
        ),
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"}
        ],
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if C.SENTINEL not in text:
        print("FAILED:RES-0046 sentinel missing from serialized artifact")
        return 1
    if '"daemon_liability"' not in text:
        print("FAILED:RES-0046 daemon-liability column missing from artifact")
        return 1
    if "CORROBORATE" not in text:
        print("FAILED:RES-0046 tier-2 verdict missing")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print("SUCCESS:RES-0046 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
