"""Live forced-mismatch dispatch: typed DEGRADED, partial preserved (IMP-0423)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "dispatch"))

from degrade_loudly import DegradeLoudly, VERDICT_DEGRADED

FIXTURE = HERE / "fixtures" / "preserved-partial.json"


def main() -> int:
    d = DegradeLoudly()
    partial = FIXTURE
    assert partial.is_file() and partial.stat().st_size > 0, "fixture partial missing"
    body = partial.read_bytes()
    d.seed_partial(partial, body)

    forced = d.mismatch_request(partial)  # streaming=True, vendor openai
    live = d.dispatch(forced, d.openai_fixture())  # openai fixture lacks streaming
    assert live.verdict == VERDICT_DEGRADED, "verdict=" + str(live.verdict)
    assert live.ordinary_looking_success is False
    assert live.mismatches and live.mismatches[0].field == "streaming"

    substituted = d.dispatch_with_fallback(
        forced, d.openai_fixture(), d.anthropic_fixture()
    )
    assert substituted.verdict == VERDICT_DEGRADED
    assert substituted.substitution_refused is True

    retried = d.retry_mismatch(live)
    assert retried.verdict == VERDICT_DEGRADED and retried.retry_refused is True

    d.assert_partial_preserved(partial, body)
    live_sha = hashlib.sha256(partial.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

    report = {
        "probe": "probe1-mismatch",
        "unit_id": "IMP-0423",
        "verdict": live.verdict,
        "mismatch_field": live.mismatches[0].field,
        "substitution_refused": substituted.substitution_refused,
        "retry_refused": retried.retry_refused,
        "ordinary_looking_success": False,
        "preserved_partial": {
            "path": "command-center/p2-wave/probes/IMP-0423/fixtures/preserved-partial.json",
            "bytes": partial.stat().st_size,
            "sha256": live_sha,
        },
        "sentinel": "SENTINEL:IMP-0423:DEGRADED-LOUD-AND-PRESERVED",
    }
    print(json.dumps(report, indent=2))
    print("SUCCESS:IMP-0423-probe1 mismatch is DEGRADED; partial preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
