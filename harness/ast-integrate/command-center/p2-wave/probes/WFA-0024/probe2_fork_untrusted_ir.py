#!/usr/bin/env python3
"""Probe 2: fork-chain collapse, untrusted DATA, keyword≠IR.

A three-repo fork chain counts once. A payload that would write a file if
exec'd must be parsed without creating that file. Marketing copy containing
'gate' is not a gate construct. A structural JSON spec is.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sweep as S  # noqa: E402

PWNED = Path("/tmp/WFA-0024-PWNED")


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0024-probe2 {msg}")
    return 1


def load(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    if PWNED.exists():
        PWNED.unlink()

    chain = load("fork_chain.json")
    collapsed = S.dedup_fork_chains(chain["records"])
    if collapsed["unique_count"] != 1:
        return fail(f"fork chain unique_count={collapsed['unique_count']} want=1")
    if collapsed["raw_count"] != 3:
        return fail(f"raw_count={collapsed['raw_count']} want=3")
    keep = collapsed["canonical"][0]
    if keep.get("fork_root") != "origin/multiagent-spec":
        return fail(f"root={keep.get('fork_root')}")
    if keep.get("full_name") != "origin/multiagent-spec":
        return fail("canonical should be the non-fork origin")

    payload = load("untrusted_payload.json")
    parsed = S.parse_ir(payload["text"], payload["filename"])
    if not parsed["injection_detected"]:
        return fail("injection marker not flagged")
    if PWNED.exists():
        PWNED.unlink()
        return fail("payload was executed; untrusted DATA was not held")
    if parsed.get("ok") is not True:
        return fail(f"python payload should parse as AST, got {parsed}")

    marketing = load("keyword_only.json")
    kw = S.parse_ir(marketing["text"], marketing["filename"])
    if not kw["keyword_hits"]:
        return fail("marketing copy should still record keyword hits")
    if kw["construct_present"]:
        return fail("keyword-only file must not count as IR evidence")

    structural = load("structural_workflow.json")
    ir = S.parse_ir(structural["text"], structural["filename"])
    if not ir["construct_present"]:
        return fail(f"structural spec produced no constructs: {ir}")
    need = {
        "typed-state-graph",
        "agent-role",
        "interrupt-resume-gate",
        "max-turns-stop-rule",
        "role-handoff",
    }
    have = set(ir["constructs"])
    missing = sorted(need - have)
    if missing:
        return fail(f"structural IR missing {missing} have={sorted(have)}")

    print(
        json.dumps(
            {
                "forks": collapsed,
                "untrusted": {
                    "injection_detected": parsed["injection_detected"],
                    "pwned_exists": PWNED.exists(),
                    "constructs": parsed.get("constructs"),
                },
                "keyword_only": {
                    "keyword_hits": kw["keyword_hits"],
                    "construct_present": kw["construct_present"],
                },
                "structural": ir,
                "pass": True,
            },
            indent=1,
            sort_keys=True,
        )
    )
    print(
        "fork_unique=1 injection_flagged=True pwned_absent=True "
        "keyword_not_evidence=True structural_ir=True"
    )
    print("SUCCESS:WFA-0024-probe2 fork-dedup untrusted-DATA keyword-vs-IR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
