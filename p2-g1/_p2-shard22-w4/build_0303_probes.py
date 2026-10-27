#!/usr/bin/env python3
"""Build the TST-0303 probe lane scripts."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent / "command-center" / "p2-wave" / "probes" / "TST-0303"

P1 = '''#!/usr/bin/env python3
"""TST-0303 probe 1: an expired result cannot satisfy a gate.

Both-states with an injected clock on the SAME advisory oracle: captured_at
past the class TTL is refused (cite-as NOT-CHECKED); captured_at within TTL
is accepted. The hermetic both-states complement: a TRUE hermetic PASS aged
3650 days still cites as current (the TTL must not force pointless re-runs),
while the misdeclared hermetic that actually hit NVD expires.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.expire import cite_as_current, gate_accepts  # noqa: E402


@dataclass
class Result:
    result_id: str
    case_id: str
    verdict: str
    observed_class: str
    captured_at: datetime


NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


def main() -> int:
    checks: dict[str, bool] = {}
    expired_adv = Result(
        "planted-expired-advisory", "advisory-nvd", "PASS", "advisory-db",
        NOW - timedelta(seconds=86401),
    )
    fresh_adv = Result(
        "fresh-advisory", "advisory-nvd", "PASS", "advisory-db",
        NOW - timedelta(seconds=3600),
    )
    g_exp = gate_accepts(expired_adv, NOW)
    g_fresh = gate_accepts(fresh_adv, NOW)
    checks["expired_advisory_gate_refused"] = g_exp["accepted"] is False
    checks["expired_cites_not_checked"] = (
        cite_as_current(expired_adv, NOW).status == "EXPIRED-NOT-CHECKED"
    )
    checks["fresh_advisory_gate_accepts"] = g_fresh["accepted"] is True
    checks["same_oracle_both_states"] = (
        expired_adv.observed_class == fresh_adv.observed_class
    )

    ancient_hermetic = Result(
        "ancient-hermetic", "hermetic-digest", "PASS", "hermetic",
        NOW - timedelta(days=3650),
    )
    g_herm = gate_accepts(ancient_hermetic, NOW)
    checks["hermetic_ancient_still_current"] = g_herm["accepted"] is True
    checks["hermetic_cite_current"] = (
        cite_as_current(ancient_hermetic, NOW).status == "CURRENT"
    )
    lie = Result(
        "planted-expired-lie", "lie-hermetic-hits-nvd", "PASS", "advisory-db",
        NOW - timedelta(seconds=86401),
    )
    checks["misdeclared_hermetic_expires"] = gate_accepts(lie, NOW)["accepted"] is False

    from bench.expire import dashboard  # noqa: E402

    dash = dashboard([expired_adv, fresh_adv, ancient_hermetic, lie], NOW)
    checks["expired_count_is_2"] = dash["expired_count"] == 2
    checks["greens_carry_age"] = all(
        "age_seconds" in g for g in dash["greens"]
    )
    checks["green_count_is_2"] = len(dash["greens"]) == 2

    out = {
        "probe": "probe1_expired_cannot_gate",
        "unit": "TST-0303",
        "expired_gate": g_exp,
        "fresh_gate": g_fresh,
        "hermetic_gate": g_herm,
        "dashboard": dash,
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-expired.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True, default=str) + "\\n",
        encoding="utf-8",
    )
    print(json.dumps(out, sort_keys=True, default=str))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P2 = '''#!/usr/bin/env python3
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
        json.dumps(out, indent=1, sort_keys=True) + "\\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

IND = '''#!/usr/bin/env python3
"""Independent classifier for TST-0303: a mechanically different instrument.

Where bench.classify reads the ttl_table.json host map, this classifier
derives the class from the URL PATH SHAPE and TLD evidence directly, so the
two instruments must agree by convergence, not by sharing the table.
"""
from __future__ import annotations

from typing import Any

_ADVISORY_TLDS = ("gov", "org")
_ADVISORY_HINTS = ("nvd", "cve", "advisory", "osv")
_MODEL_HINTS = ("api.anthropic", "api.openai", "model", "v1/completions")
_MARKET_HINTS = ("marketplace", "vsix", "vsx", "pypi.org/pypi")


def _host(url: str) -> str:
    rest = url.split("://", 1)[1] if "://" in url else url
    return rest.split("/", 1)[0].split(":", 1)[0]


def independent_classify(declared: str, calls: list[dict[str, Any]]) -> dict:
    if not calls:
        return {"observed_class": "hermetic", "evidence": "zero network calls"}
    url = str(calls[0].get("url") or "")
    low = url.lower()
    host = _host(url)
    if any(h in low for h in _MODEL_HINTS):
        return {"observed_class": "model-endpoint", "evidence": host}
    if any(h in low for h in _MARKET_HINTS):
        if "pypi.org" in host:
            return {"observed_class": "package-registry", "evidence": host}
        return {"observed_class": "marketplace-index", "evidence": host}
    if any(h in low for h in _ADVISORY_HINTS):
        return {"observed_class": "advisory-db", "evidence": host}
    tld = host.rsplit(".", 1)[-1]
    if tld in _ADVISORY_TLDS:
        return {"observed_class": "advisory-db", "evidence": host}
    return {"observed_class": "unknown-live", "evidence": host}
'''

TEST = '''"""TST-0303 expiry unit tests (mirrors the probe checks as pytest)."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.expire import cite_as_current, gate_accepts  # noqa: E402
from bench.ttl import ttl_for  # noqa: E402

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


@dataclass
class Result:
    result_id: str
    case_id: str
    verdict: str
    observed_class: str
    captured_at: datetime


def test_ttl_table_classes():
    assert ttl_for("hermetic") is None
    assert ttl_for("advisory-db") == 86400
    assert ttl_for("model-endpoint") == 21600
    assert ttl_for("unknown-live") == 3600


def test_expired_cannot_gate():
    r = Result("x", "advisory-nvd", "PASS", "advisory-db",
               NOW - timedelta(seconds=86401))
    assert gate_accepts(r, NOW)["accepted"] is False
    assert cite_as_current(r, NOW).status == "EXPIRED-NOT-CHECKED"


def test_fresh_and_hermetic_still_current():
    fresh = Result("y", "advisory-nvd", "PASS", "advisory-db",
                   NOW - timedelta(seconds=3600))
    assert gate_accepts(fresh, NOW)["accepted"] is True
    old = Result("z", "hermetic-digest", "PASS", "hermetic",
                 NOW - timedelta(days=3650))
    assert gate_accepts(old, NOW)["accepted"] is True
'''


def main() -> int:
    LANE.mkdir(parents=True, exist_ok=True)
    (LANE / "probe1_expired_cannot_gate.py").write_text(
        P1.replace('\\\\n', "\\n"), encoding="utf-8"
    )
    (LANE / "probe2_observed_class_and_hermetic.py").write_text(
        P2.replace('\\\\n', "\\n"), encoding="utf-8"
    )
    (LANE / "independent_classify.py").write_text(IND, encoding="utf-8")
    tests = REPO_TESTS = HERE.parent / "tools" / "bench" / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_expire.py").write_text(TEST, encoding="utf-8")
    init = tests / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
    print("built TST-0303 probe lane + test file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
