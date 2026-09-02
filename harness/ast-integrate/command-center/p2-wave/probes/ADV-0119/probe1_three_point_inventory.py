#!/usr/bin/env python3
"""Probe 1: three-point inventory of user data, config, and commands."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_honest_rollback  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0119-rollback-user-data-preservation.json"
SENTINEL_FRAG = "SUCCESS:ADV-0119 emitted ONLY when the artifact"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
UNIT = "ADV-0119"


def _check_artifact() -> tuple[int, dict | None]:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0119-probe1 artifact missing")
        return 1, None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:ADV-0119-probe1 unparseable {exc}")
        return 1, None
    if SENTINEL_FRAG not in text:
        print("FAILED:ADV-0119-probe1 sentinel-absent")
        return 1, None
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:ADV-0119-probe1 self-declared:{st}")
        return 1, None
    if doc.get("unit_id") != UNIT:
        print("FAILED:ADV-0119-probe1 unit_id", doc.get("unit_id"))
        return 1, None
    return 0, doc


def main() -> int:
    rc, doc = _check_artifact()
    if rc != 0:
        return rc
    with tempfile.TemporaryDirectory(prefix="adv0119-p1-") as tmp:
        honest = run_honest_rollback(Path(tmp))
    diff = honest.get("diff") or {}
    missing = list(diff.get("missing_files") or [])
    altered = list(diff.get("altered_files") or [])
    missing_cmds = list(diff.get("missing_commands") or [])
    leftover_cmds = list(diff.get("leftover_commands") or [])
    payload = {
        "ok": bool(honest.get("pass")),
        "probe": "probe1-three-point-inventory",
        "unit_id": UNIT,
        "missing_files": missing,
        "altered_files": altered,
        "missing_commands": missing_cmds,
        "leftover_commands": leftover_cmds,
        "user_byte_identical": diff.get("user_byte_identical"),
        "commands_restored": diff.get("commands_restored"),
        "no_n_only_leftover": diff.get("no_n_only_leftover"),
        "leftover_n_format_state": honest.get("leftover_n_format_state"),
        "disposable_prefix": honest.get("disposable_prefix"),
        "live_canary_intact": honest.get("live_canary_intact"),
        "pre_commands": (honest.get("pre_upgrade") or {}).get("commands"),
        "post_upgrade_commands": (honest.get("post_upgrade") or {}).get("commands"),
        "post_rollback_commands": (honest.get("post_rollback") or {}).get("commands"),
        "n1_sha256": (honest.get("packages") or {}).get("n1_sha256"),
    }
    print(json.dumps(payload, sort_keys=True))
    if not honest.get("pass"):
        print("FAILED:ADV-0119-probe1 honest rollback inventory")
        return 1
    if missing or altered or missing_cmds:
        print("FAILED:ADV-0119-probe1 pre-upgrade items absent after rollback")
        return 1
    if leftover_cmds:
        print("FAILED:ADV-0119-probe1 N leftovers in command inventory")
        return 1
    art_inv = ((doc or {}).get("three_point_inventory") or {})
    if art_inv.get("user_byte_identical") is not True:
        print("FAILED:ADV-0119-probe1 artifact inventory claim drifted")
        return 1
    print(
        "SUCCESS:ADV-0119-probe1 three-point inventory; "
        "pre-upgrade user data and N-1 commands present post-rollback"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
