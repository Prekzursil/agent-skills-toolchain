"""IMP-0206 probe 2 (source): the threshold is declared, versioned, frozen.

load_threshold returns the versioned spec (1.0.0) with a content hash and
frozen=True; the spec file declares not_tuned_per_run. A per-run override
is REFUSED by both detect() and load_threshold() (PerRunThresholdTuneError)
- the threshold is not tuned per run. Two loads agree byte-for-byte.

Exit 0 iff the version chain and both override refusals hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE
for _ in range(6):
    if (REPO / "command-center" / "p2-wave").is_dir():
        break
    REPO = REPO.parent
for _p in (str(REPO / "command-center" / "lib"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from overfit_detector.corpus import build_corpus  # noqa: E402
from overfit_detector.detector import detect  # noqa: E402
from overfit_detector.threshold import (  # noqa: E402
    PerRunThresholdTuneError,
    load_threshold,
)
from overfit_detector.workflows import TrueRuleWorkflow  # noqa: E402

spec = load_threshold()
spec2 = load_threshold()

load_override_fired = False
try:
    load_threshold(threshold_override=0.99)
except PerRunThresholdTuneError:
    load_override_fired = True

detect_override_fired = False
try:
    detect(TrueRuleWorkflow(), build_corpus(80), threshold_override=0.10)
except PerRunThresholdTuneError:
    detect_override_fired = True

raw = json.loads(
    (REPO / "command-center" / "lib" / "overfit_detector" / "threshold_v1.json")
    .read_text(encoding="utf-8")
)

checks = {
    "versioned": spec.get("version") == "1.0.0" and bool(spec.get("id")),
    "gap_declared": isinstance(spec.get("gap_abs"), (int, float)),
    "min_heldout_declared": isinstance(spec.get("min_heldout_n"), int),
    "content_hash_present": bool(spec.get("spec_sha256"))
        and len(str(spec["spec_sha256"])) == 64,
    "frozen_flag": spec.get("frozen") is True,
    "not_tuned_per_run_declared": raw.get("not_tuned_per_run") is True,
    "loads_are_deterministic": spec == spec2,
    "load_override_refused": load_override_fired,
    "detect_override_refused": detect_override_fired,
}

result = {
    "probe": "probe2-threshold-versioned",
    "unit_id": "IMP-0206",
    "checks": checks,
    "threshold": {k: spec.get(k) for k in (
        "id", "version", "gap_abs", "min_heldout_n", "frozen", "not_tuned_per_run",
        "spec_sha256")},
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0206-probe2 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0206-probe2 threshold versioned and frozen; per-run overrides refused")
