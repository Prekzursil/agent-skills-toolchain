#!/usr/bin/env python3
"""Probe 1: revert-red and restore-green in the same scratch session.

Failure must return when only the load-bearing hunk is reversed, and must
disappear when that hunk is restored. Tests stay byte-identical.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import protocol as P  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0032-hunk-revert-causality.json"
RAW = HERE / "probe1-revert-restore.raw.json"


def main() -> int:
    try:
        result = P.run_protocol()
    except P.ProtocolError as exc:
        print(f"FAILED:CNF-0032-probe1 protocol {exc}")
        return 1

    matched = [r for r in result["rows"] if r["matched_revert_red_restore_green"]]
    intact = all(r["tests_intact"] and r["same_session"] for r in result["rows"])
    payload = {
        "examined": result["counts"]["examined"],
        "matched_pairs": len(matched),
        "matched_ids": [r["id"] for r in matched],
        "tests_intact": intact,
        "shared_checkout_untouched": result["shared_checkout_untouched"],
        "git_unused": result["git_add_commit_checkout_not_used"],
        "pass": False,
    }
    if len(matched) < 1:
        print("FAILED:CNF-0032-probe1 no matched revert-red/restore-green pair")
        RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if not intact:
        print("FAILED:CNF-0032-probe1 tests mutated or not same-session")
        RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if not result["shared_checkout_untouched"]:
        print("FAILED:CNF-0032-probe1 shared checkout touched")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:CNF-0032-probe1 artifact state={doc.get('state')}")
            return 1
        rec = (doc.get("counts") or {}).get("matched_revert_red_restore_green")
        if rec != len(matched):
            print(
                f"FAILED:CNF-0032-probe1 artifact matched={rec} live={len(matched)}"
            )
            return 1
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:CNF-0032" not in text:
            print("FAILED:CNF-0032-probe1 sentinel absent")
            return 1

    payload["pass"] = True
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"matched={len(matched)} ids={payload['matched_ids']} "
        f"tests_intact={intact} git_unused=True"
    )
    print("SUCCESS:CNF-0032-probe1 revert-red and restore-green same session")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
