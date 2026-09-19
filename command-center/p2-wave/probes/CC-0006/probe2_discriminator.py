#!/usr/bin/env python3
"""CC-0006 Probe 2: use-vs-mention discriminator + known-absent / planted controls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
sys.path.insert(0, str(PROBE))

import wrong_recipe_gate as gate  # noqa: E402

OUT_JSON = PROBE / "probe2-discriminator.json"
OUT_RAW = PROBE / "probe2-discriminator.raw.txt"
FIXTURES = PROBE / "fixtures"


def main() -> int:
    pre = gate.scan_paths([FIXTURES / "pre_fix_release_checklist.md"], repo=REPO)
    scratch = gate.scan_paths([FIXTURES / "scratch_no_recipe.md"], repo=REPO)
    planted = gate.scan_paths([FIXTURES / "planted_regression.md"], repo=REPO)
    documentary = gate.scan_paths([FIXTURES / "documentary_forbid.md"], repo=REPO)
    shell = gate.scan_paths([REPO / "rules/common/windows-shell.md"], repo=REPO)
    live = gate.scan_paths([REPO / "command-center/RELEASE-CHECKLIST.md"], repo=REPO)

    # Evidence requirement: one PRESCRIPTIVE fire + one DOCUMENTARY silent on identical string.
    identical_string_prescriptive = pre.hit_count >= 1
    identical_string_documentary_silent = (
        documentary.hit_count == 0 and len(documentary.documentary) >= 1
    )

    controls = {
        "known_present_pre_fix_fires": pre.hit_count >= 1,
        "known_absent_scratch_zero": scratch.hit_count == 0,
        "use_vs_mention_windows_shell_silent": shell.hit_count == 0,
        "use_vs_mention_fixture_silent": documentary.hit_count == 0,
        "use_vs_mention_fixture_saw_mention": len(documentary.documentary) >= 1,
        "post_fix_live_silent": live.hit_count == 0,
        "planted_regression_refires": planted.hit_count >= 1,
        "identical_string_prescriptive_fires": identical_string_prescriptive,
        "identical_string_documentary_silent": identical_string_documentary_silent,
    }
    ok = all(controls.values())
    payload = {
        "unit": "CC-0006",
        "probe": "probe2-discriminator",
        "ok": ok,
        "controls": controls,
        "counts": {
            "pre_fix_hits": pre.hit_count,
            "scratch_hits": scratch.hit_count,
            "planted_hits": planted.hit_count,
            "documentary_hits": documentary.hit_count,
            "documentary_mentions": len(documentary.documentary),
            "windows_shell_hits": shell.hit_count,
            "live_checklist_hits": live.hit_count,
        },
        "pre_fix": pre.to_dict(),
        "documentary": documentary.to_dict(),
        "planted": planted.to_dict(),
    }
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw = (
        f"probe2-discriminator ok={ok} controls={controls}\n"
        f"counts={payload['counts']}\n"
        f"pre_fix_excerpt={[f.excerpt for f in pre.prescriptive]}\n"
        f"documentary_excerpt={[f.excerpt for f in documentary.documentary]}\n"
    )
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
