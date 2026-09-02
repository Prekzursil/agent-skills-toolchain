#!/usr/bin/env python3
"""Probe 2: usage trace — which exposed tools were actually invoked.

Use-vs-mention: a prose mention of aud0060_fixture_gamma must not count as an
invocation. aud0060_fixture_alpha is planted as a real tool_use.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixture_server import EXPECTED_NAMES  # noqa: E402
from usage import measure  # noqa: E402

UNIT = "AUD-0060"
ART = REPO / "command-center/audit/AUD-0060-mcp-tool-surface-inventory.json"
SENTINEL = (
    "SUCCESS:AUD-0060 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    exposed = list(EXPECTED_NAMES) + ["CreateGoal", "GenerateImage", "UpdateGoal"]
    live = measure(exposed)
    print(json.dumps({"live": live}, sort_keys=True, default=str)[:12000])
    if not live["control"]["pass"]:
        return fail("use-vs-mention control failed")
    if live["control"]["gamma_counted_as_invocation"]:
        return fail("prose mention of gamma counted as invocation")
    if not live["control"]["alpha_used"]:
        return fail("planted alpha tool_use not seen")
    unused = live["exposed_vs_used"]["unused"]
    if "aud0060_fixture_gamma" not in unused:
        return fail("gamma must be unused on the live+control surface")
    if live["exposed_vs_used"]["finding"] == "all-exposed-tools-invoked":
        return fail("finding folded unused tools into all-invoked")

    if not ART.is_file():
        return fail(f"artifact absent {ART}")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    finding = ((doc.get("report") or {}).get("headline") or {}).get("usage_finding")
    if not finding:
        return fail("artifact missing usage_finding")
    if finding == "all-exposed-tools-invoked" and live["exposed_vs_used"]["unused_count"]:
        return fail("artifact claimed all-invoked while unused tools exist")
    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-usage-trace",
                "unit_id": UNIT,
                "files_scanned": live["live"]["files_scanned"],
                "mcp_invocations": live["live"]["mcp_invocation_count"],
                "first_party_invocations": live["live"]["first_party_invocation_count"],
                "unused_exposed": unused,
                "finding": live["exposed_vs_used"]["finding"],
                "use_vs_mention": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:AUD-0060-probe2 usage trace discriminates used vs unused; "
        "gamma mention is not an invocation"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
