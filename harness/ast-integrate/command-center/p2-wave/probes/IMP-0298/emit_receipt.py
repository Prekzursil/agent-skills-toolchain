#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0298.json from live governor fixtures."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import (  # noqa: E402
    ALL_DIMENSIONS,
    COMPLETE_CONTROL,
    EXHAUST_FIXTURES,
    TITLE_DIMENSIONS,
)
from tools.council.budget.governor import (  # noqa: E402
    BUDGET_EXHAUSTED,
    BUDGET_DIMENSIONS,
    EXHAUSTION_POLICY,
    UnknownBudgetDimensionError,
    BudgetGovernor,
    governor_token_count,
    marker_is_load_bearing,
    run_fixture,
)
from tools.council.budget.transport import transport_token_count  # noqa: E402

OUT = "command-center/receipts/IMP-0298.json"
GOVERNOR = "tools/council/budget/governor.py"
TRANSPORT = "tools/council/budget/transport.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    unknown_ok = False
    unknown_detail = ""
    try:
        BudgetGovernor({"budgets": {"not_a_real_dial": 1}})
    except UnknownBudgetDimensionError as exc:
        unknown_ok = True
        unknown_detail = str(exc)

    rows: list[dict] = []
    for dim in ALL_DIMENSIONS:
        fx = EXHAUST_FIXTURES[dim]
        result = run_fixture(spec=fx["spec"], events=fx["events"])
        rows.append(
            {
                "dimension": dim,
                "title_dimension": dim in TITLE_DIMENSIONS,
                "policy": EXHAUSTION_POLICY[dim],
                "complete": result["complete"],
                "markers": result["markers"],
                "exhausted_dimensions": result["exhausted_dimensions"],
                "text": result["text"],
                "labelled": BUDGET_EXHAUSTED in result["markers"],
                "usage": result["usage"],
                "governor_token_count": result["governor_token_count"],
                "transport_token_count": result["transport_token_count"],
                "token_count_comparison": result["token_count_comparison"],
            }
        )

    complete = run_fixture(
        spec=COMPLETE_CONTROL["spec"], events=COMPLETE_CONTROL["events"]
    )
    partial = run_fixture(
        spec=EXHAUST_FIXTURES["tokens"]["spec"],
        events=EXHAUST_FIXTURES["tokens"]["events"],
    )
    load = marker_is_load_bearing(complete, partial)

    sample = "alpha bravo charlie delta echo"
    gov_n = governor_token_count(sample)
    tr_n = transport_token_count(sample)

    all_labelled = all(r["labelled"] and not r["complete"] for r in rows)
    title_ok = all(
        r["labelled"] for r in rows if r["dimension"] in TITLE_DIMENSIONS
    )
    if not unknown_ok or not all_labelled or not load.get("pass") or gov_n == tr_n:
        print("FAILED:IMP-0298 live fixtures did not support a SUCCESS receipt")
        print(f"  unknown_ok={unknown_ok} all_labelled={all_labelled} load={load.get('pass')} gov={gov_n} tr={tr_n}")
        return 1

    gov_sha, gov_bytes = sha256_file(REPO / GOVERNOR)
    tr_sha, tr_bytes = sha256_file(REPO / TRANSPORT)

    doc = {
        "unit_id": "IMP-0298",
        "id": "IMP-0298",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0298",
        "completion_sentinel": "SUCCESS:IMP-0298",
        "title": "Budget governor for effort, tokens, tool calls, turns, time and experiments",
        "profile": "council-budget-module",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0298; CNL-0008 12-dial exhaustion semantics; "
            "CouncilSpec budgets section (charter/participants/roles/engagement/budgets/...)"
        ),
        "artifact_paths": [
            GOVERNOR,
            TRANSPORT,
            "tools/council/budget/__init__.py",
            "command-center/p2-wave/probes/IMP-0298/probe1_exhaust_each_dimension.py",
            "command-center/p2-wave/probes/IMP-0298/probe2_marker_and_transport.py",
            "command-center/p2-wave/probes/IMP-0298/fixtures.py",
            OUT,
        ],
        "evidence": [
            {
                "claim": "Every declared budget dimension exhausts with BUDGET_EXHAUSTED; none complete unlabelled.",
                "verdict": "PASS",
                "anchor": GOVERNOR + ":EXHAUSTION_POLICY",
                "detail": {
                    "dimensions": list(ALL_DIMENSIONS),
                    "title_dimensions": list(TITLE_DIMENSIONS),
                    "schema_dimensions": list(BUDGET_DIMENSIONS),
                    "rows": rows,
                },
            },
            {
                "claim": "Governor whitespace-word count compared to independent transport UTF-8-ceil-div-4 count.",
                "verdict": "PASS",
                "anchor": TRANSPORT + ":transport_token_count",
                "detail": {
                    "sample": sample,
                    "governor_whitespace_words": gov_n,
                    "transport_utf8_ceil_div4": tr_n,
                    "algorithms_differ": True,
                    "counts_equal": gov_n == tr_n,
                    "partial_run_comparison": partial.get("token_count_comparison"),
                },
            },
        ],
        "test_ids": [
            "probe1_exhaust_each_dimension",
            "probe2_marker_and_transport",
        ],
        "negative_control_ids": [
            "NC-strip-BUDGET_EXHAUSTED",
            "NC-unknown-budget-key-fail-closed",
        ],
        "reviewer_verdict": "PASS",
        "residual_unknowns": [
            "IMP-0264 kernel.py is absent on this worktree; fixtures drive BudgetGovernor.commit_turn directly. A topology that later writes participant output without the governor would be a kernel bypass, not a governor defect.",
            "IMP-0261 councilspec.schema.json is absent; budgets keys are the 12 CNL-0008 dials encoded in BUDGET_DIMENSIONS. A later schema with extra keys will fail closed (UnknownBudgetDimensionError) until the governor is extended.",
            "Token counts are compared, not required to match. Transport uses UTF-8 bytes ceil-div 4; a vendor tokenizer would be a third signal.",
            "minimum_engagement here is a numeric floor on engagement_units, not IMP-0299's filler-vs-substance metric.",
            "Mechanical reviewer is probe2 (starts from the negative-control tests). A separate human reviewer in a fresh context was not a different process in this session.",
        ],
        "falsifiable_question": (
            "when a budget is exhausted mid-turn, does the council produce a "
            "truncated-but-labelled result or an unlabelled partial that reads as complete?"
        ),
        "falsifiable_answer": (
            "truncated-but-labelled. Mid-turn token overflow keeps a prefix and stamps "
            "BUDGET_EXHAUSTED. Time overflow keeps in-flight text and stamps the same marker. "
            "An unlabelled partial is a defect. SUCCESS:IMP-0298"
        ),
        "negative_control": {
            "id": "NC-strip-BUDGET_EXHAUSTED",
            "result": load,
            "unknown_key_fail_closed": unknown_ok,
            "unknown_key_detail": unknown_detail,
        },
        "exhaustion_policy": dict(EXHAUSTION_POLICY),
        "title_dimensions_labelled": title_ok,
        "all_twelve_labelled": all_labelled,
        "governor": {
            "path": GOVERNOR,
            "sha256": gov_sha,
            "bytes": gov_bytes,
        },
        "transport": {
            "path": TRANSPORT,
            "sha256": tr_sha,
            "bytes": tr_bytes,
        },
        "cloud_ok": False,
        "min_bytes_threshold": 2048,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "produced_by": {
            "role": "implementer",
            "execution_substrate": "linux-local",
            "unit": "IMP-0298",
        },
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0298 receipt {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:IMP-0298 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
