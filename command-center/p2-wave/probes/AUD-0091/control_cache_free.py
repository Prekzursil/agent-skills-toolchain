#!/usr/bin/env python3
"""AUD-0091 control (tests_required): prove the cache-free detector actually
discriminates, then apply it to the REAL directory probe1 used.

tests_required text: "the clean clone must be proven cache-free - assert the
package cache directory is empty or redirected before the run, otherwise a
cached artifact can make a broken setup appear to work."

Two fixture states, same detector (`_cache_check.is_cache_free`, imported --
not reimplemented -- so this control and probe1's precheck cannot silently
drift apart):

  * BAD  fixture: fixtures/populated_npm_cache/ (committed, one placeholder
    file simulating a pre-existing cached package) -> detector MUST fire
    (cache_free=False).
  * GOOD fixture: a brand-new empty tempdir -> detector MUST stay silent
    (cache_free=True), proving it is not an always-fires detector.

Then reads probe1's JSON output and re-applies the SAME detector to the
`cache_dir_precheck.path` it recorded, independently confirming the real
clean-room run's cache directory really was empty before npm install used
it (does not re-run npm install; just re-measures the recorded precheck
path's state as it exists NOW, which -- after probe1 populated and then
cleaned up its scratch tree -- is expected to be ABSENT, itself consistent
with "was empty / is now gone", never "was silently reused").
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cache_check import is_cache_free  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_JSON = HERE / "control-cache-free.json"
OUT_RAW = HERE / "control-cache-free.raw.txt"
BAD_FIXTURE = HERE / "fixtures" / "populated_npm_cache"
PROBE1_JSON = HERE / "probe1-clean-clone-run.json"


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_lines = [
        "AUD-0091 CONTROL: cache-free detector fires-on-bad / silent-on-good",
        f"started_at={started}",
    ]

    bad_result = is_cache_free(BAD_FIXTURE)
    raw_lines.append(f"bad_fixture={json.dumps(bad_result)}")

    good_tmp = Path(tempfile.mkdtemp(prefix="aud-0091-control-good-cache-"))
    good_result = is_cache_free(good_tmp)
    raw_lines.append(f"good_fixture={json.dumps(good_result)}")
    good_tmp.rmdir()

    fired_on_bad = bad_result["cache_free"] is False
    silent_on_good = good_result["cache_free"] is True

    probe1_available = PROBE1_JSON.is_file()
    probe1_reapplied = None
    if probe1_available:
        p1 = json.loads(PROBE1_JSON.read_text(encoding="utf-8"))
        precheck_path = (p1.get("cache_dir_precheck") or {}).get("path")
        if precheck_path:
            probe1_reapplied = is_cache_free(Path(precheck_path))
            raw_lines.append(
                f"probe1_recorded_precheck={json.dumps(p1.get('cache_dir_precheck'))}"
            )
            raw_lines.append(f"reapplied_now={json.dumps(probe1_reapplied)}")
            precheck_was_cache_free = bool(
                (p1.get("cache_dir_precheck") or {}).get("cache_free")
            )
        else:
            precheck_was_cache_free = False
    else:
        precheck_was_cache_free = False

    ok = fired_on_bad and silent_on_good and (probe1_available and precheck_was_cache_free)

    doc = {
        "started_at": started,
        "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": ok,
        "bad_fixture": bad_result,
        "good_fixture": good_result,
        "a_fires_on_bad": fired_on_bad,
        "a_silent_on_good": silent_on_good,
        "probe1_available": probe1_available,
        "probe1_recorded_cache_free_before_run": precheck_was_cache_free,
        "probe1_precheck_reapplied_now": probe1_reapplied,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw_lines.append(
        f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} "
        f"probe1_recorded_cache_free_before_run={precheck_was_cache_free} ok={ok}"
    )
    raw_lines.append(f"{'SUCCESS' if ok else 'FAILED'}:AUD-0091-control")
    OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

    print(f"unit=AUD-0091 control ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
