#!/usr/bin/env python3
"""Probe 2: independent reviewer re-derives binding RPM from observed throughput.

Does not import quotas.py (documented tables). Counts t=0 burst successes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import observe as O  # noqa: E402
import sim as S  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0058.json"
SENTINEL = "SUCCESS:BLD-0058"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0058-probe2 {msg}")
    return 1


def main() -> int:
    src = (HERE / "observe.py").read_text(encoding="utf-8")
    if "\nimport quotas" in src or "from quotas import" in src:
        return fail("observer imports documented quota tables")
    if not O.bucket_independent_of_docs_constant():
        return fail("TokenBucket(7) did not yield 7 successes")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    scaled = int((doc.get("scale") or {}).get("scaled_n") or 0)
    if scaled < 10:
        return fail(f"scaled_n {scaled}")

    derived = O.rederive(scaled)
    observed = derived["observed_rpm"]
    burst = S.fire(S.burst_times(scaled))
    if observed != burst.n_200:
        return fail(f"observed {observed} != burst.n_200 {burst.n_200}")
    if burst.n_429 <= 0:
        return fail("reviewer burst produced no 429s")

    rec_obs = (doc.get("reviewer_measurement") or {}).get("observed_rpm")
    if rec_obs != observed:
        return fail(f"receipt observed_rpm {rec_obs} != {observed}")

    binding = doc.get("binding_constraint") or {}
    if binding.get("numeric_value") != observed:
        return fail(
            f"binding {binding.get('numeric_value')} != observed {observed}"
        )
    if binding.get("status") == "NOT-CHECKED":
        return fail("binding was NOT-CHECKED")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("reviewer not independent")
    if rev.get("verdict") != "PASS":
        return fail(f"reviewer verdict {rev.get('verdict')}")
    if rev.get("reads_documented_tables") is not False:
        return fail("reviewer claimed to read docs tables")

    print(
        json.dumps(
            {
                "probe": "probe2-observed-throughput",
                "observed_rpm": observed,
                "burst_429": burst.n_429,
                "method": derived["method"],
                "reads_documented_tables": False,
                "binding_id": binding.get("id"),
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:BLD-0058-probe2 observed_rpm={observed} "
        f"binding={binding.get('id')} independent-throughput"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
