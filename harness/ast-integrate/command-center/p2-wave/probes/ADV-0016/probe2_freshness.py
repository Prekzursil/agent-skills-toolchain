#!/usr/bin/env python3
"""Probe 2: execute a freshness-sensitive gate twice with advisory injection.

Mechanically different from probe 1 (no YAML AST walk). Sequence:
  1. Negative control: empty local mirror, two live-gate runs, both green.
  2. Injection: write a synthetic advisory into the mirror; third live run red.
  3. Cache contrast: stored first-run result stays green after the same injection.
  4. quality.yml-equivalent (substring check, not AST): stays green after injection.
  5. Real GHSA document for lodash@4.17.11 injected on a fresh live gate: red.

The probe itself exits 0 only when that experimental contract holds.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    FIXTURE_PACKAGES,
    QUALITY_REL,
    REAL_GHSA_ADVISORY,
    SYNTHETIC_ADVISORY,
    UNIT,
    cached_gate,
    live_gate,
    sha256_json,
    workflow_equivalent_gate,
    write_advisory,
)


def main() -> int:
    quality_path = REPO / QUALITY_REL
    quality_text = quality_path.read_text(encoding="utf-8") if quality_path.is_file() else ""

    with tempfile.TemporaryDirectory(prefix="adv0016-p2-") as raw:
        tmp = Path(raw)
        empty = tmp / "mirror-empty"
        empty.mkdir()
        injected = tmp / "mirror-injected"
        injected.mkdir()
        real_mirror = tmp / "mirror-real"
        real_mirror.mkdir()
        store = tmp / "stored-green.json"

        control_a = live_gate(FIXTURE_PACKAGES, empty)
        control_b = live_gate(FIXTURE_PACKAGES, empty)
        cached_before = cached_gate(FIXTURE_PACKAGES, empty, store)

        syn_path = write_advisory(injected, SYNTHETIC_ADVISORY)
        live_after = live_gate(FIXTURE_PACKAGES, injected)
        cached_after = cached_gate(FIXTURE_PACKAGES, injected, store)
        quality_after = workflow_equivalent_gate(quality_text)

        ghsa_path = write_advisory(real_mirror, REAL_GHSA_ADVISORY)
        live_real = live_gate(FIXTURE_PACKAGES, real_mirror)

    control_green = bool(control_a["ok"] and control_b["ok"] and not control_a["hits"] and not control_b["hits"])
    injection_red = bool(not live_after["ok"] and live_after["hits"])
    cache_stayed_green = bool(cached_after.get("ok") is True and cached_after.get("read_store") is True)
    quality_ignored = bool(quality_after.get("ok") is True and not quality_after.get("invokes_scanner"))
    real_red = bool(not live_real["ok"] and any(h.get("advisory_id") == REAL_GHSA_ADVISORY["id"] for h in live_real["hits"]))
    cached_first_green = bool(cached_before["ok"] and not cached_before.get("read_store"))

    payload = {
        "probe": "probe2-freshness",
        "unit_id": UNIT,
        "instrument": (
            "two live executions against a local advisory mirror; synthetic "
            "advisory written between runs; cached-store contrast; quality.yml "
            "substring equivalent"
        ),
        "fixture_packages": list(FIXTURE_PACKAGES),
        "synthetic_advisory_id": SYNTHETIC_ADVISORY["id"],
        "synthetic_advisory_sha256": sha256_json(SYNTHETIC_ADVISORY),
        "real_advisory_id": REAL_GHSA_ADVISORY["id"],
        "real_advisory_published": REAL_GHSA_ADVISORY["published"],
        "real_advisory_sha256": sha256_json(REAL_GHSA_ADVISORY),
        "control_run_a": control_a,
        "control_run_b": control_b,
        "cached_before_injection": cached_before,
        "live_after_synthetic": live_after,
        "cached_after_synthetic": cached_after,
        "quality_equivalent_after_synthetic": quality_after,
        "live_after_real_ghsa": live_real,
        "injected_files": [syn_path.name, ghsa_path.name],
        "negative_control_second_run_stayed_green": control_green,
        "negative_control_second_run_stayed_green": control_green,
        "live_went_red_after_synthetic": injection_red,
        "live_went_red_after_synthetic": injection_red,
        "cached_stayed_green_after_synthetic": cache_stayed_green,
        "cached_stayed_green_after_synthetic": cache_stayed_green,
        "quality_yml_ignored_injection": quality_ignored,
        "quality_yml_ignored_injection": quality_ignored,
        "live_went_red_after_real_ghsa": real_red,
        "live_went_red_after_real_ghsa": real_red,
        "cached_first_run_was_green_store": cached_first_green,
        "live_after_synthetic": live_after,
        "control_run_b": control_b,
        "cached_after_synthetic": cached_after,
        "pass": bool(
            control_green
            and injection_red
            and cache_stayed_green
            and quality_ignored
            and real_red
            and cached_first_green
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not payload["pass"]:
        print("FAILED:ADV-0016-probe2 injection/control contract did not hold")
        return 1
    print("SUCCESS:ADV-0016-probe2 live gate goes red after injection; control stays green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
