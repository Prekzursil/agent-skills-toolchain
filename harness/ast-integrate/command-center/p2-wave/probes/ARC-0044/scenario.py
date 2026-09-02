"""Run both vendors, write the two artifacts, quote the semantic divergence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapter import (
    HERE,
    WORK_UNIT,
    dispatch,
    effect_identity_guard,
    harness_predicate,
    semantic_key,
)

RUNS = HERE / "artifacts" / "runs"
EFFECTS = HERE / "artifacts" / "effects"
VENDORS = ("claude-confirm", "codex-auto")


def run_scenario() -> dict[str, Any]:
    arts: dict[str, Any] = {}
    for vendor in VENDORS:
        arts[vendor] = dispatch(vendor, WORK_UNIT, RUNS, EFFECTS)

    claude = arts["claude-confirm"]
    codex = arts["codex-auto"]
    pred_c = harness_predicate(claude)
    pred_x = harness_predicate(codex)
    keys_differ = semantic_key(claude) != semantic_key(codex)
    guard = effect_identity_guard(claude, codex)
    marker_c = EFFECTS / "claude-confirm" / WORK_UNIT["target_rel"]
    marker_x = EFFECTS / "codex-auto" / WORK_UNIT["target_rel"]
    marker_c_present = marker_c.is_file()
    marker_x_present = marker_x.is_file() and marker_x.read_text(encoding="utf-8").strip() == WORK_UNIT["body"]

    quoted = {
        "claude-confirm": {
            "writes_applied": claude["writes_applied"],
            "body": claude["body"],
            "effect_digest": claude["effect_digest"],
            "permission_model": claude["permission_model"],
        },
        "codex-auto": {
            "writes_applied": codex["writes_applied"],
            "body": codex["body"],
            "effect_digest": codex["effect_digest"],
            "permission_model": codex["permission_model"],
        },
    }
    ok = (
        pred_c
        and pred_x
        and keys_differ
        and guard.get("ok") is False
        and not marker_c_present
        and marker_x_present
        and claude["writes_applied"] == 0
        and codex["writes_applied"] == 1
        and claude["body"] == ""
        and codex["body"] == WORK_UNIT["body"]
    )
    return {
        "pass": ok,
        "both_predicate_pass": pred_c and pred_x,
        "semantic_divergence": keys_differ,
        "guard_would_fail_loudly": guard.get("ok") is False,
        "guard_marker": guard.get("marker"),
        "claude_writes_applied": claude["writes_applied"],
        "codex_writes_applied": codex["writes_applied"],
        "quoted_divergence": quoted,
        "artifact_paths": {
            "claude-confirm": str((RUNS / "claude-confirm.json").relative_to(HERE.parents[3])),
            "codex-auto": str((RUNS / "codex-auto.json").relative_to(HERE.parents[3])),
        },
        "marker_claude_present": marker_c_present,
        "marker_codex_present": marker_x_present,
        "observable": "effect.digest (and writes_applied / marker.txt bytes)",
        "work_unit_class": WORK_UNIT["class"],
    }


if __name__ == "__main__":
    import sys

    out = run_scenario()
    print(json.dumps({k: out[k] for k in sorted(out) if k != "pass"}, indent=2, sort_keys=True))
    sys.exit(0 if out.get("pass") else 1)
