#!/usr/bin/env python3
"""Probe 2: independent parse reread; mention-filter mutant must fail."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0004-probe2 {msg}")
    return 1


def reread_anchor(anchor: str, ident: str) -> tuple[bool, str]:
    path_s, _, line_s = anchor.rpartition(":")
    path = REPO / path_s
    if not path.is_file():
        return False, f"missing:{path_s}"
    try:
        line_n = int(line_s)
    except ValueError:
        return False, f"bad-line:{line_s}"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line_n < 1 or line_n > len(lines):
        return False, f"line-oob:{line_n}"
    window = "\n".join(lines[max(0, line_n - 2) : min(len(lines), line_n + 2)])
    if ident not in window and ident not in path.read_text(encoding="utf-8", errors="replace"):
        return False, f"snippet-miss:{ident}"
    return True, f"{path_s}:{line_n}"


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    parsed = E.scan(include_live=True, method="parse")
    regexed = E.scan(include_live=False, method="regex")
    if parsed["control"]["code_ids"] != regexed["control"]["code_ids"]:
        return fail("regex/parse control code mismatch")
    if parsed["control"]["doc_ids"] != regexed["control"]["doc_ids"]:
        return fail("regex/parse control doc mismatch")

    tests = E.evaluate_controls(parsed["control"])
    if any(t["result"] != "PASS" for t in tests):
        return fail("recomputed controls failed")

    # Mutant: treating mention-only lines as live docs must surface wf.removed-v2.
    mutant_docs = set(parsed["control"]["doc_ids"]) | parsed["control"]["mention_ids"]
    if "workflow_id:wf.removed-v2" not in mutant_docs:
        return fail("mutant did not capture mention-only workflow")
    if "workflow_id:wf.removed-v2" in parsed["control"]["doc_ids"]:
        return fail("mention filter failed; removed-v2 counted live")

    reread = (doc.get("reviewer") or {}).get("reread") or []
    if len(reread) < 5:
        return fail("reviewer reread short")
    for i, row in enumerate(reread[:5]):
        ok, why = reread_anchor(row["anchor"], row["identifier"])
        print(f"reread[{i}] {row['identifier']} ok={ok} {why}")
        if not ok:
            return fail(why)

    live_undoc_receipt = sum(
        1 for x in doc.get("undocumented") or [] if x.get("source") == "live"
    )
    live_undoc_now = parsed["live"]["counts"]["undocumented"]
    if live_undoc_receipt != live_undoc_now:
        return fail(
            f"live undocumented receipt={live_undoc_receipt} recomputed={live_undoc_now}"
        )

    print(
        "SUCCESS:BLD-0004-probe2 parse-reread mention-mutant-rejected "
        f"live_undocumented={live_undoc_now}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
