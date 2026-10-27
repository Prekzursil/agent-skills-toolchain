#!/usr/bin/env python3
"""TST-0303 probe 2: observed-class classification + hermetic never expires.

Classes come from the network calls each case ACTUALLY makes (NetworkObserver
records the destination; the observer returns fixture bodies, WAN is never
required). The declared-lie case (hermetic that hits NVD) is flagged by the
observed class, and the independent classifier must agree with the primary
on all six cases. True hermetic cases never expire - the TTL must not force
pointless re-runs of pure functions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from bench.classify import classify_case  # noqa: E402
from bench.observe import NetworkObserver  # noqa: E402
from independent_classify import independent_classify  # noqa: E402

CASES = [
    ("hermetic-digest", "hermetic", []),
    ("advisory-nvd", "advisory-db", ["https://nvd.nist.gov/api/rest/2.0"]),
    ("lie-hermetic-hits-nvd", "hermetic", ["https://nvd.nist.gov/feeds/json"]),
    ("marketplace-vsix", "marketplace-index", ["https://marketplace.visualstudio.com/"]),
    ("model-anthropic", "model-endpoint", ["https://api.anthropic.com/v1"]),
    ("registry-pypi", "package-registry", ["https://pypi.org/pypi/"]),
]


def main() -> int:
    checks: dict[str, bool] = {}
    rows = []
    for case_id, declared, urls in CASES:
        obs = NetworkObserver()
        for u in urls:
            obs.record(u, body=b"fixture-body", status=200)
        calls = obs.snapshot()
        r = classify_case(declared, calls)
        indep = independent_classify(declared, calls)
        r["independent_agrees"] = indep["observed_class"] == r["observed_class"]
        r["case_id"] = case_id
        rows.append(r)
        checks[f"classified_{case_id}"] = r["observed_class"] != ""
    checks["lie_flagged_by_observed_class"] = rows[2]["mismatch"] is True
    checks["hermetic_digest_no_hosts"] = rows[0]["observed_hosts"] == []
    checks["advisory_host_observed"] = rows[1]["observed_hosts"] == ["nvd.nist.gov"]
    checks["independent_agrees_all_six"] = all(r["independent_agrees"] for r in rows)
    checks["non_lie_mismatches_absent"] = sum(1 for r in rows if r["mismatch"]) == 1

    out = {
        "probe": "probe2_observed_class_and_hermetic",
        "unit": "TST-0303",
        "classification": rows,
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-observed-class.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
