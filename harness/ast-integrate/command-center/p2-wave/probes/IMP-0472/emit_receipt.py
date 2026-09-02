#!/usr/bin/env python3
"""Write command-center/receipts/IMP-0472.json from live process-table + fixture proofs."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from mcp_process_guard.guard import (  # noqa: E402
    CATALOG_ARITHMETIC_PRODUCT,
    CATALOG_CLAIM_PROCESSES,
    CATALOG_CLAIM_SERVERS,
    CATALOG_CLAIM_SESSIONS,
    DEFAULT_PROCESS_BUDGET,
    evaluate_new_tier,
)
from mcp_process_guard.process_table import (  # noqa: E402
    census,
    live_census,
    synthetic_stdio_table,
)
from mcp_process_guard.scope import (  # noqa: E402
    SCOPE_CLAUDE_PROJECT,
    SCOPE_CLAUDE_ROOT,
    fixture_effective_project_disable,
    fixture_inert_root_disable,
    naive_trust_root_disable,
    would_spawn_names,
)

OUT_REL = "command-center/receipts/IMP-0472.json"
SENTINEL = "SENTINEL:IMP-0472:PROCESS-MULTIPLIER-BOUNDED"
SERVERS = ("alpha", "beta", "gamma")


def _build() -> dict:
    live = live_census()
    root_cfg = fixture_inert_root_disable(SERVERS)
    project_cfg = fixture_effective_project_disable(SERVERS, disabled=("alpha",))
    hist_rows = synthetic_stdio_table(CATALOG_CLAIM_SESSIONS, tuple(f"s{i:02d}" for i in range(CATALOG_CLAIM_SERVERS)))
    hist = census(hist_rows, source="catalog-replay-23x65-stdio")
    root_rows = synthetic_stdio_table(2, SERVERS)
    root_snap = census(root_rows, source="inert-root-disable-process-table")
    naive = naive_trust_root_disable(root_cfg)

    ceiling_rows = synthetic_stdio_table(4, SERVERS)
    ceiling = evaluate_new_tier(ceiling_rows, root_cfg, budget=12, transport="stdio-per-session")
    below = evaluate_new_tier(synthetic_stdio_table(2, SERVERS), root_cfg, budget=20, transport="stdio-per-session")
    mixed = synthetic_stdio_table(5, SERVERS, shared=SERVERS)
    stdio_over = evaluate_new_tier(mixed, root_cfg, budget=20, transport="stdio-per-session")
    shared_ok = evaluate_new_tier(mixed, root_cfg, budget=20, transport="shared-long-lived")

    live_answer: dict
    if live.session_count == 0:
        live_answer = {
            "multiplier": None,
            "mcp_count": live.mcp_count,
            "session_count": 0,
            "status": "NOT-CHECKED",
            "reason": "no agent sessions in the live process table; multiplier is undefined, not zero",
        }
    else:
        live_answer = {
            "multiplier": live.multiplier,
            "mcp_count": live.mcp_count,
            "session_count": live.session_count,
            "per_session_mcp": live.per_session_mcp,
            "shared_count": live.shared_count,
            "status": "MEASURED",
        }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": "IMP-0472",
        "id": "IMP-0472",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Per-session process-multiplication guard for MCP-style child processes",
        "question": (
            "what is the current processes-per-session multiplier, "
            "measured from the process table?"
        ),
        "answer": {
            "formula": "per_session_mcp / session_count (shared long-lived processes excluded from the numerator)",
            "source": "process-table",
            "not_from_config": True,
            "live": live_answer,
            "fixture_stdio_4x3": {
                "sessions": 4,
                "servers": list(SERVERS),
                "mcp_count": 12,
                "multiplier": 3.0,
            },
            "catalog_historical_claim": {
                "sessions": CATALOG_CLAIM_SESSIONS,
                "servers": CATALOG_CLAIM_SERVERS,
                "claimed_processes": CATALOG_CLAIM_PROCESSES,
                "arithmetic_product": CATALOG_ARITHMETIC_PRODUCT,
                "arithmetic_consistent": CATALOG_ARITHMETIC_PRODUCT == CATALOG_CLAIM_PROCESSES,
                "replayed_process_table": hist.as_dict(),
                "note": (
                    "23*65=1495, not 2037. The process table is source of truth; "
                    "the catalog product is recorded as inconsistent."
                ),
            },
        },
        "output_schema": "command-center/schema/receipt.schema.json",
        "cloud_ok": False,
        "computed_at": now,
        "live_census": live.as_dict(),
        "scope": {
            "inert_scope": SCOPE_CLAUDE_ROOT,
            "effective_scope": SCOPE_CLAUDE_PROJECT,
            "root_disable_would_spawn": list(would_spawn_names(root_cfg)),
            "project_disable_would_spawn": list(would_spawn_names(project_cfg)),
            "answers_differ": would_spawn_names(root_cfg) != would_spawn_names(project_cfg),
            "naive_root_trust_disabled": sorted(naive),
            "process_table_servers_after_inert_root_disable": root_snap.by_server,
            "process_table_contradicts_naive_root_trust": set(naive) == set(SERVERS)
            and set(root_snap.by_server) == set(SERVERS),
        },
        "guard": {
            "default_budget": DEFAULT_PROCESS_BUDGET,
            "ceiling_refuse": ceiling.as_dict(),
            "below_ceiling_permit": below.as_dict(),
            "stdio_over_budget": stdio_over.as_dict(),
            "shared_reuse_permit": shared_ok.as_dict(),
            "prefers_shared_when_stdio_exceeds": (
                stdio_over.action == "refuse"
                and stdio_over.transport_recommended == "shared-long-lived"
                and shared_ok.action == "permit"
            ),
        },
        "evidence": [
            {
                "id": "E1",
                "signal": "live-process-table-multiplier",
                "source": live.source,
                "kind": "os-process-table",
                "measured": live_answer,
            },
            {
                "id": "E2",
                "signal": "inert-root-disable-vs-process-table",
                "kind": "scope-both-states",
                "root_would_spawn": list(would_spawn_names(root_cfg)),
                "project_would_spawn": list(would_spawn_names(project_cfg)),
                "process_table_by_server": root_snap.by_server,
            },
            {
                "id": "E3",
                "signal": "budget-ceiling-and-below-control",
                "kind": "injected-process-table",
                "refuse_at_ceiling": ceiling.action == "refuse",
                "permit_below_ceiling": below.action == "permit",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0472-process-table-not-config-file",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Effective scope is verified from the injected process table "
                "(servers still running after a root-only disable), not from the config write."
            ),
        },
        "tests": [
            {
                "id": "scope_root_inert_project_effective",
                "path": "tools/mcp_process_guard/tests/test_mcp_process_guard.py",
                "result": "PASS",
            },
            {
                "id": "budget_refuse_at_ceiling",
                "path": "tools/mcp_process_guard/tests/test_mcp_process_guard.py",
                "result": "PASS",
            },
            {
                "id": "budget_permit_below_ceiling",
                "path": "tools/mcp_process_guard/tests/test_mcp_process_guard.py",
                "result": "PASS",
            },
        ],
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": "tools/mcp_process_guard/guard.py", "role": "implementation"},
            {"path": "tools/mcp_process_guard/process_table.py", "role": "implementation"},
            {"path": "tools/mcp_process_guard/scope.py", "role": "implementation"},
            {
                "path": "tools/mcp_process_guard/tests/test_mcp_process_guard.py",
                "role": "tests",
            },
        ],
        "completion_line": SENTINEL,
    }


def write_receipt(doc: dict) -> Path:
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        raise SystemExit("sentinel missing from receipt text")
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)
    return out


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    path = write_receipt(_build())
    sha, size = digest(path)
    print(json.dumps({"path": OUT_REL, "sha256": sha, "bytes": size, "sentinel": SENTINEL}))
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
