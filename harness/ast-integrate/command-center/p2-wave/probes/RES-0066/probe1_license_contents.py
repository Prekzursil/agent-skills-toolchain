#!/usr/bin/env python3
"""Probe 1: LICENSE file contents recorded (read), not GitHub SPDX classifier labels."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from license_checks import ART, SENTINEL, classifier_only_mutant, errors_for, load_art  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0066-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = load_art()
    live = errors_for(doc)
    red = errors_for(classifier_only_mutant(doc))
    print(
        json.dumps(
            {
                "probe": "probe1-license-contents-not-classifier",
                "live_errors": live,
                "classifier_only_errors": red,
                "live_pass": not live,
                "red_fires": bool(red),
                "autogen_spdx": next(
                    (
                        p.get("github_api_spdx")
                        for p in doc.get("projects") or []
                        if p.get("id") == "microsoft-autogen"
                    ),
                    None,
                ),
                "sentinel_present": SENTINEL in ART.read_text(encoding="utf-8"),
            },
            sort_keys=True,
        )
    )
    if live:
        return fail("live " + ";".join(live))
    if not red:
        return fail("classifier-only mutant silent (both-states failed)")
    if "autogen:LICENSE-not-cc-by-text" not in red and "microsoft-autogen:LICENSE:classifier-used-as-body" not in red:
        if not any("classifier" in e or "body-too-short" in e or "looks-like-label" in e for e in red):
            return fail(f"red errors not about classifier-as-body: {red}")
    print("live_pass=True classifier_only_fires=True")
    print("SUCCESS:RES-0066-probe1 LICENSE file contents recorded; classifier is not the body")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
