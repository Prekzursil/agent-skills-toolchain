#!/usr/bin/env python3
"""Probe 2: live scan matches receipt; redaction; honest NOT-CHECKED; no rotation."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import live as live_mod  # noqa: E402
from scanner import PREFIX_ANTHROPIC, PREFIX_GITHUB, PREFIX_AWS  # noqa: E402

ART = REPO / "command-center/receipts/CC-0011.json"
BODY_LEAK = re.compile(
    r"(?:sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}"
    r"|AKIA[0-9A-Z]{16}|sk-proj-[A-Za-z0-9_-]{20,})"
)


def main() -> int:
    if not ART.is_file():
        print("FAILED:CC-0011-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CC-0011-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CC-0011" not in text:
        print("FAILED:CC-0011-probe2 sentinel absent")
        return 1

    scanned = live_mod.live_scan()
    live_doc = doc.get("live_scan") or {}
    checks = [
        ("credential_shaped", int(live_doc.get("credential_shaped_count", -1)), scanned["credential_shaped_count"]),
        ("placeholder", int(live_doc.get("placeholder_count", -1)), scanned["placeholder_count"]),
        ("synthetic", int(live_doc.get("synthetic_count", -1)), scanned["synthetic_count"]),
        ("hit_count", int(live_doc.get("hit_count", -1)), scanned["hit_count"]),
    ]
    for name, recorded, measured in checks:
        print(f"{name} recorded={recorded} measured={measured}")
        if recorded != measured:
            print(f"FAILED:CC-0011-probe2 {name} drift")
            return 1

    cov = doc.get("coverage") or {}
    hist = cov.get("command_center_git_history") or {}
    if hist.get("coverage") != "NOT-CHECKED":
        print("FAILED:CC-0011-probe2 live git history overclaimed")
        return 1
    rb = cov.get("rollback_manifest") or {}
    if rb.get("coverage") != "NOT-CHECKED":
        print("FAILED:CC-0011-probe2 rollback overclaimed")
        return 1
    hs = cov.get("harness_restore") or {}
    if hs.get("coverage") != "NOT-CHECKED":
        print("FAILED:CC-0011-probe2 harness-restore overclaimed")
        return 1
    print("honest_not_checked git_history=True rollback=True harness=True")

    # Receipt must not embed secret bodies. Prefix-only mentions are allowed.
    leaks = []
    for m in BODY_LEAK.finditer(text):
        token = m.group(0)
        # Allow a prefix-only leftover if somehow matching; bodies have extra chars.
        if token in {PREFIX_ANTHROPIC, PREFIX_GITHUB, PREFIX_AWS, "sk-ant-", "ghp_", "AKIA"}:
            continue
        leaks.append(token[: max(len(PREFIX_ANTHROPIC), 7)])
    # Also refuse well-known example bodies and ADV-0024 fixture bodies.
    forbidden_snippets = [
        "IOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI",
        "NOTAREALKEY",
        "A1b2C3d4E5f6G7h8I9j0",
        "FIXTUREZz9Yy8Xx7Ww6",
    ]
    for snip in forbidden_snippets:
        if snip in text:
            leaks.append("snippet:" + snip[:12])
    print(f"redaction_leaks={len(leaks)}")
    if leaks:
        print("FAILED:CC-0011-probe2 receipt contains secret body or fixture body")
        return 1

    life = doc.get("credential_lifecycle") or {}
    if life.get("rotated") or life.get("revoked") or life.get("unset"):
        print("FAILED:CC-0011-probe2 lifecycle mutated")
        return 1
    if life.get("printed_beyond_zero_entropy_prefix"):
        print("FAILED:CC-0011-probe2 printed beyond prefix")
        return 1
    reviewer = doc.get("reviewer") or {}
    if not reviewer.get("independent") or reviewer.get("verdict") != "PASS":
        print("FAILED:CC-0011-probe2 reviewer")
        return 1
    if not reviewer.get("confirmed_no_credential_modified_rotated_or_unset"):
        print("FAILED:CC-0011-probe2 reviewer lifecycle confirmation missing")
        return 1
    print("lifecycle_unmodified=True reviewer=PASS")
    print("SUCCESS:CC-0011-probe2 live-receipt redaction honest-coverage no-rotation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
