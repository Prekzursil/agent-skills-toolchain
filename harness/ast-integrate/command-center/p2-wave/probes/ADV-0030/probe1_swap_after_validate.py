#!/usr/bin/env python3
"""Probe 1: swap staged payload bytes after validation, observe install.

Runtime instrumentation of the production sequence. Mechanically different
from probe 2 (AST). Control: no-swap install must succeed with original
digest. Negative: a boolean-trust mutant installs the same swap.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

UNIT = "ADV-0030"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    report = H.measure()
    control = report["control"]
    pre = report["swap_after_validate_before_digest"]
    post = report["swap_after_digest_before_place"]
    naive_good = report["naive_good"]
    naive_bad = report["naive_bad"]
    payload = {
        "probe": "probe1-swap-after-validate",
        "unit_id": UNIT,
        "method": "live-monkeypatch-after-payload_digest-then-place",
        "instrumentation_ok": report["instrumentation_ok"],
        "control_ok": control["ok"],
        "control_installed_original": control["installed_original"],
        "control_src_digest_stable": control["src_digest_stable"],
        "handoff_matches_src": control["handoff_matches_src"],
        "pre_digest_refused": pre["refused"],
        "pre_digest_error_type": pre["error_type"],
        "pre_digest_dest_exists": pre["dest_exists"],
        "pre_digest_installed_swapped": pre["installed_swapped"],
        "post_digest_installed_swapped": post["toctou_installed_swapped"],
        "post_digest_installed_original": post["installed_original"],
        "post_digest_error_type": post["error_type"],
        "post_digest_digest_calls": post["digest_calls"],
        "naive_good_installed_original": naive_good["installed_original"],
        "naive_bad_installed_swapped": naive_bad["installed_swapped"],
        "production_refuses_pre_digest_swap": report[
            "production_refuses_pre_digest_swap"
        ],
        "production_installs_post_digest_swap": report[
            "production_installs_post_digest_swap"
        ],
        "pass": bool(report["instrumentation_ok"] and pre["refused"]),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not report["instrumentation_ok"]:
        return fail("instrumentation/control failed; swap result is uninterpretable")
    if not control["ok"]:
        return fail("no-swap control did not install original bytes")
    if not pre["refused"]:
        return fail("pre-digest swap was not refused by production digest check")
    if pre["installed_swapped"]:
        return fail("pre-digest swap still landed in dest")
    if not naive_good["installed_original"]:
        return fail("naive good-state install did not keep original bytes")
    if not naive_bad["installed_swapped"]:
        return fail("naive mutant did not install swapped bytes (vacuous swap)")
    print(
        "control_ok="
        f"{control['ok']} pre_digest_refused={pre['refused']} "
        f"post_digest_swapped={post['toctou_installed_swapped']} "
        f"naive_bad_swapped={naive_bad['installed_swapped']}"
    )
    print(
        f"SUCCESS:{UNIT}-probe1 swap-after-validate; "
        "control original; pre-digest refused; post-digest observed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
