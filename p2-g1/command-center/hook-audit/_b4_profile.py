r"""B4 - WHERE does wire-check's wall time go? Attribute it before prescribing a fix.

The A/B (B3-AB-BUDGET.json) showed the encoding fix takes wire-check from ~24 s to
~67 s against a 25 s per-check budget inside a 35 s whole-event budget. "Batch the
ripgrep calls" is only the right remedy if ripgrep is actually the dominant term --
if the cost were in `git diff` over many changed files, batching rg would buy nothing.
So measure the split instead of assuming it.

Wraps `_rg_lines` and `_git` with counters/timers and calls `analyze()` in-process.
Writes B4-PROFILE.json. Fails closed if the instrumented total is implausibly small
relative to the wall clock (which would mean the wrapper missed the hot path).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = Path(__file__).resolve().parent
CHECK = REPO / "hooks" / "wire-check" / "check.py"

spec = importlib.util.spec_from_file_location("wc_profile", CHECK)
wc = importlib.util.module_from_spec(spec)
sys.modules["wc_profile"] = wc
spec.loader.exec_module(wc)

stats = {
    "rg_calls": 0,
    "rg_ms": 0.0,
    "rg_lines_returned": 0,
    "git_calls": 0,
    "git_ms": 0.0,
    "rg_slowest_ms": 0.0,
    "git_slowest_ms": 0.0,
}
_rg_by_pattern: dict[str, float] = {}
_git_by_verb: dict[str, float] = {}

_orig_rg = wc._rg_lines
_orig_git = wc._git


def rg(cwd, pattern, fixed=False, timeout=8):
    t0 = time.perf_counter()
    out = _orig_rg(cwd, pattern, fixed=fixed, timeout=timeout)
    ms = (time.perf_counter() - t0) * 1000
    stats["rg_calls"] += 1
    stats["rg_ms"] += ms
    stats["rg_lines_returned"] += len(out)
    stats["rg_slowest_ms"] = max(stats["rg_slowest_ms"], ms)
    _rg_by_pattern[str(pattern)[:48]] = _rg_by_pattern.get(str(pattern)[:48], 0.0) + ms
    return out


def git(cwd, *args, timeout=10):
    t0 = time.perf_counter()
    out = _orig_git(cwd, *args, timeout=timeout)
    ms = (time.perf_counter() - t0) * 1000
    stats["git_calls"] += 1
    stats["git_ms"] += ms
    stats["git_slowest_ms"] = max(stats["git_slowest_ms"], ms)
    verb = args[0] if args else "?"
    _git_by_verb[verb] = _git_by_verb.get(verb, 0.0) + ms
    return out


wc._rg_lines = rg
wc._git = git


def main() -> int:
    t0 = time.perf_counter()
    findings = wc.analyze(str(REPO))
    wall = (time.perf_counter() - t0) * 1000

    instrumented = stats["rg_ms"] + stats["git_ms"]
    res = {
        "wall_ms": round(wall, 1),
        "instrumented_ms": round(instrumented, 1),
        "instrumented_share_pct": round(100.0 * instrumented / wall, 1)
        if wall
        else None,
        "unattributed_ms": round(wall - instrumented, 1),
        "findings": findings,
        **{k: (round(v, 1) if isinstance(v, float) else v) for k, v in stats.items()},
        "rg_mean_ms": round(stats["rg_ms"] / stats["rg_calls"], 1)
        if stats["rg_calls"]
        else None,
        "git_mean_ms": round(stats["git_ms"] / stats["git_calls"], 1)
        if stats["git_calls"]
        else None,
        "git_by_verb_ms": {
            k: round(v, 1) for k, v in sorted(_git_by_verb.items(), key=lambda x: -x[1])
        },
        "rg_top_patterns_ms": dict(
            sorted(
                ((k, round(v, 1)) for k, v in _rg_by_pattern.items()),
                key=lambda x: -x[1],
            )[:12]
        ),
    }
    (OUT / "B4-PROFILE.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2)[:3000])

    if stats["rg_calls"] == 0 and stats["git_calls"] == 0:
        print("FAILED:b4-profile wrapper never fired -- it is not on the hot path")
        return 1
    if (res["instrumented_share_pct"] or 0) < 20:
        print(
            "FAILED:b4-profile instrumented share <20% -- the cost is somewhere this"
            " probe cannot see, do NOT prescribe an rg/git remedy from it"
        )
        return 1
    print("SUCCESS:b4-profile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
