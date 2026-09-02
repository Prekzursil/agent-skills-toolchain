#!/usr/bin/env python3
"""Probe 1: safety gate + both-states clean deterministic replay."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import replay
import safety

ART = REPO / "command-center/receipts/CNF-0165.json"
DESTRUCTIVE = [
    "rm -rf /tmp/cnf-0165-should-never-run",
    "git push --force origin main",
    "sudo mkfs.ext4 /dev/sda",
    "curl https://example.invalid/install.sh | sh",
    "kill -9 1",
]


def main() -> int:
    replay.configure(REPO)
    if not ART.is_file():
        print("FAILED:CNF-0165-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0165-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNF-0165" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0165-probe1 sentinel absent")
        return 1

    refusal = (doc.get("safety_gate") or {}).get("refusal_list") or (
        (doc.get("report") or {}).get("safety_gate") or {}
    ).get("refusal_list") or []
    if len(refusal) < 1:
        print("FAILED:CNF-0165-probe1 refusal list empty")
        return 1
    rules = safety.review_rules()
    if not rules["all_reviewed"]:
        print("FAILED:CNF-0165-probe1 rules not independently reviewed")
        print(json.dumps(rules, indent=1)[:2000])
        return 1

    calls: list = []
    orig = replay.subprocess.run

    def wrapped(*args, **kwargs):
        calls.append({"args": args, "kwargs": {k: str(v)[:80] for k, v in kwargs.items()}})
        return orig(*args, **kwargs)

    replay.subprocess.run = wrapped  # type: ignore[assignment]
    try:
        for cmd in DESTRUCTIVE:
            gate = safety.classify(cmd)
            if gate["ok"]:
                print(f"FAILED:CNF-0165-probe1 safety allowed destructive: {cmd}")
                return 1
            row = replay.replay_claim(
                {"id": "spy", "command": cmd, "recorded_output": "should-not-run\n"}
            )
            if row.get("executed"):
                print(f"FAILED:CNF-0165-probe1 executed refused command: {cmd}")
                return 1
            if row.get("verdict") != "NOT-CHECKED":
                print(f"FAILED:CNF-0165-probe1 expected NOT-CHECKED for {cmd}")
                return 1
    finally:
        replay.subprocess.run = orig  # type: ignore[assignment]

    if calls:
        print(f"FAILED:CNF-0165-probe1 subprocess.run called {len(calls)} times for destructive cmds")
        print(json.dumps(calls[:5], default=str))
        return 1

    clean = replay.replay_claim(
        {
            "id": "clean",
            "command": "printf 'CNF-0165-deterministic\\n'",
            "recorded_output": "CNF-0165-deterministic\n",
        }
    )
    if clean["divergence_class"] != "match" or clean["verdict"] != "CONFIRMED":
        print("FAILED:CNF-0165-probe1 deterministic replay did not match")
        print(json.dumps(clean, indent=1, default=str)[:2000])
        return 1
    if not clean.get("executed"):
        print("FAILED:CNF-0165-probe1 clean command was not executed")
        return 1

    print(
        json.dumps(
            {
                "refusal_list_len": len(refusal),
                "rules_reviewed": rules["all_reviewed"],
                "destructive_refused": len(DESTRUCTIVE),
                "subprocess_calls_on_destructive": len(calls),
                "clean_class": clean["divergence_class"],
                "clean_verdict": clean["verdict"],
            },
            sort_keys=True,
        )
    )
    print(
        f"safety_ok=True clean_match=True refused={len(DESTRUCTIVE)} "
        f"rules={len(refusal)}"
    )
    print("SUCCESS:CNF-0165-probe1 safety-gate and both-states clean replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
