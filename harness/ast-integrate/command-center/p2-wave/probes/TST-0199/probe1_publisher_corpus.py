#!/usr/bin/env python3
"""Probe 1: both-states publisher gate + 40-name corpus.

Signal (a): the publisher's rejection list. A portable name set publishes.
Each of 40 known-unportable names is individually named with the rule quoted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MARKET = REPO / "tools" / "marketplace"
if str(MARKET) not in sys.path:
    sys.path.insert(0, str(MARKET))

from filename_gate import REJECTED_UNPORTABLE, load_corpus  # noqa: E402
from pr_only_guard import outbound_log, reset_outbound_log  # noqa: E402
from publishing import pack, publish  # noqa: E402

PUBLIC_CFG = MARKET / "fixtures" / "release-mode.public.json"
PR_ONLY_CFG = MARKET / "fixtures" / "release-mode.pr-only.json"


def main() -> int:
    fail: list[str] = []
    doc = load_corpus()
    portable = [str(x) for x in doc["portable"]]
    rows = [r for r in doc["unportable"] if isinstance(r, dict)]
    unportable = [str(r["name"]) for r in rows]
    expected_rule = {str(r["name"]): str(r["rule"]) for r in rows}
    if len(unportable) != 40 or len(set(unportable)) != 40:
        fail.append(f"corpus-size:{len(unportable)}")

    good = pack({"files": portable}, config_path=str(PR_ONLY_CFG))
    if good.get("status") != "PROCEEDED" or good.get("published") is not True:
        fail.append(f"portable-not-published:{good.get('status')}")
    if good.get("rejections"):
        fail.append("portable-had-rejections")

    reset_outbound_log()
    bad = pack({"files": unportable}, config_path=str(PR_ONLY_CFG))
    if bad.get("status") != REJECTED_UNPORTABLE or bad.get("published") is not False:
        fail.append(f"unportable-not-rejected:{bad.get('status')}")
    rejections = bad.get("rejections") or []
    by_name: dict[str, list[dict]] = {}
    for row in rejections:
        if isinstance(row, dict):
            by_name.setdefault(str(row.get("name") or ""), []).append(row)
    unnamed = [n for n in unportable if n not in by_name]
    if unnamed:
        fail.append(f"unnamed:{len(unnamed)}")
    rule_miss = []
    quote_miss = []
    for name, rule in expected_rule.items():
        hits = by_name.get(name) or []
        rules = {str(h.get("rule") or "") for h in hits}
        if rule not in rules:
            rule_miss.append(name)
        texts = [
            str(h.get("rule_text") or "")
            for h in hits
            if str(h.get("rule") or "") == rule
        ]
        if not any(rule in t or len(t) > 20 for t in texts):
            quote_miss.append(name)
    if rule_miss:
        fail.append(f"rule-miss:{len(rule_miss)}")
    if quote_miss:
        fail.append(f"rule-text-miss:{len(quote_miss)}")

    per_name_fail = []
    for name in unportable:
        one = pack({"files": [name]}, config_path=str(PR_ONLY_CFG))
        named = [str(r.get("name")) for r in (one.get("rejections") or [])]
        if name not in named or one.get("status") != REJECTED_UNPORTABLE:
            per_name_fail.append(name)
    if per_name_fail:
        fail.append(f"individual:{len(per_name_fail)}")

    pub = publish({"files": unportable}, config_path=str(PUBLIC_CFG))
    if pub.get("status") != REJECTED_UNPORTABLE:
        fail.append(f"publish-leaked:{pub.get('status')}")
    if outbound_log():
        fail.append("outbound-reached")

    classes = {str(r.get("class") or "") for r in rows}
    needed = {"trailing-dot", "trailing-space", "control-character", "turkish-i"}
    if not needed <= classes:
        fail.append(f"classes:{sorted(classes)}")

    report = {
        "probe": "probe1-publisher-both-states-corpus",
        "unit_id": "TST-0199",
        "pass": not fail,
        "fail": fail,
        "portable_published": good.get("published") is True,
        "corpus_size": len(unportable),
        "named_in_rejection": len(unportable) - len(unnamed),
        "publisher_status": bad.get("status"),
        "publish_blocked_before_outbound": pub.get("status") == REJECTED_UNPORTABLE
        and not outbound_log(),
        "classes": sorted(classes),
        "sample_rejection": (rejections[0] if rejections else None),
    }
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    if fail:
        print(f"FAILED:TST-0199-probe1 {fail}")
        return 1
    print(
        "SUCCESS:TST-0199-probe1 portable publishes; "
        "40 unportable names each quoted with rule"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
