#!/usr/bin/env python
"""harness-bench/bench.py - background REGRESSION NET producer for the semantic skill-router.

Rides the EXISTING background-digest bus - it adds NO new Claude Code hook event, NO new
runtime, NO new MCP. A low-frequency (weekly) Windows Scheduled Task named
`ClaudeHarnessBench` runs this script; it:

  1. runs `python eval.py --json` (the shipped HYBRID router eval, SEMROUTER_NO_RECORD=1),
  2. compares HYBRID skill/mcp recall against a stored baseline,
  3. on a DROP, appends ONE `[YYYY-MM-DD HH:MM:SS] [harness-bench] ... | PROPOSE: ...` line
     to the background digest. That is LOG + PROPOSE only - it NEVER auto-acts. The existing
     background-digest reader surfaces the line once at the next SessionStart.

Ratchets the baseline UP on improvement (so the bar only rises and a fixed regression stops
re-firing); the FIRST run seeds the baseline silently. FAIL-OPEN everywhere: a broken eval,
missing file, parse error, or non-JSON output returns 0 with no digest and never raises into
the scheduler.

Anti-overfit rationale: a green regression net is what LICENSES aggressive skill pruning -
if HYBRID recall does not drop, removing a skill did not hurt routing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

THIS = Path(__file__).resolve().parent
EVAL_PY = THIS.parent / "semantic-router" / "eval.py"
HOME = Path.home()

# The command surfaced in the digest for a human to re-run the full eval by hand.
PROPOSE_CMD = "python C:/Users/Prekzursil/.claude/hooks/semantic-router/eval.py"

# A variant object needs these int keys for a comparison to be valid.
_REQUIRED = ("skill_hit", "skill_total", "mcp_hit", "mcp_total")

# How long to let the (weekly, offline) eval run before giving up - fail-open on timeout.
_EVAL_TIMEOUT_S = 1200


def _digest_path() -> Path:
    """Match the background-digest reader's default + BG_DIGEST_FILE override."""
    return Path(os.environ.get(
        "BG_DIGEST_FILE", str(HOME / ".claude" / "BACKGROUND-DIGEST.md")))


def _baseline_path() -> Path:
    return Path(os.environ.get("BENCH_BASELINE", str(THIS / "baseline.json")))


def _default_eval_runner() -> str | None:
    """Run `python eval.py --json` (same interpreter) and return raw stdout, or None."""
    try:
        res = subprocess.run(
            [sys.executable, str(EVAL_PY), "--json"],
            capture_output=True, text=True, encoding="utf-8", timeout=_EVAL_TIMEOUT_S)
        if res.returncode != 0:
            return None
        return res.stdout
    except Exception:
        return None


def _semantic_backend_down() -> bool:
    """True only when the Ollama embedding lane is CONFIRMED unreachable. A recall drop with
    the semantic backend down is infra, not a router regression (the intent+capabilities lanes
    keep HYBRID at/above LEXICAL, so a recall-ratio guard cannot tell them apart). Fail-open:
    any probe error -> False (treat as up), so a flaky probe never SILENCES a real regression."""
    try:
        sr_dir = str(THIS.parent / "semantic-router")
        if sr_dir not in sys.path:
            sys.path.insert(0, sr_dir)
        import embed  # noqa: PLC0415  (sibling hook module, path added above)
        ok, _ = embed.health()
        return ok is False
    except Exception:
        return False


def _valid_variant(obj) -> bool:
    return isinstance(obj, dict) and all(isinstance(obj.get(k), int) for k in _REQUIRED)


def _parse_hybrid(raw: str | None) -> dict | None:
    """Extract the validated HYBRID variant from eval --json stdout. None on any problem."""
    if not raw:
        return None
    try:
        hyb = json.loads(raw)["hybrid"]
    except Exception:
        return None
    return hyb if _valid_variant(hyb) else None


def _load_baseline() -> dict | None:
    path = _baseline_path()
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if _valid_variant(data) else None


def _write_baseline(cur: dict) -> None:
    """Write the baseline ATOMICALLY (temp + os.replace) so a killed/interrupted run can
    never leave a half-written baseline.json that a later run would read as corrupt."""
    path = _baseline_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _regression_desc(base: dict, cur: dict) -> str:
    """Human-readable 'baseline -> current' for whichever recall(s) dropped."""
    parts = []
    if cur["skill_hit"] < base["skill_hit"]:
        parts.append(f"skill recall {base['skill_hit']}/{base['skill_total']} "
                     f"-> {cur['skill_hit']}/{cur['skill_total']}")
    if cur["mcp_hit"] < base["mcp_hit"]:
        parts.append(f"mcp recall {base['mcp_hit']}/{base['mcp_total']} "
                     f"-> {cur['mcp_hit']}/{cur['mcp_total']}")
    return "HYBRID router " + "; ".join(parts)


def _append_digest(desc: str) -> None:
    """Append ONE entry line to the digest (utf-8; guaranteed on its own line)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [harness-bench] {desc} | PROPOSE: {PROPOSE_CMD}"
    path = _digest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    try:
        if path.exists():
            data = path.read_bytes()
            if data and not data.endswith(b"\n"):
                prefix = "\n"  # don't fuse onto a newline-less last line
    except Exception:
        prefix = ""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(prefix + line + "\n")


def main(argv=None, eval_runner=None) -> int:
    """Return 0 ALWAYS (fail-open); never raise into the scheduler.

    eval_runner: zero-arg callable returning raw `eval.py --json` stdout (or None). Injected
    by the tests so no real eval subprocess runs; defaults to _default_eval_runner.
    """
    try:
        runner = eval_runner or _default_eval_runner
        cur = _parse_hybrid(runner())
        if cur is None:
            return 0  # broken / garbage / non-JSON eval -> silent

        base = _load_baseline()
        if base is None:
            # Distinguish a genuinely ABSENT baseline (first run -> seed) from a
            # corrupt-but-PRESENT one (killed mid-write / bad edit). NEVER reseed on
            # corrupt: that could silently replace a healthy bar with a degraded run.
            if _baseline_path().exists():
                return 0  # corrupt baseline -> skip; keep the (unknown) higher bar
            _write_baseline(cur)  # first run: seed the bar silently
            return 0

        # Regression takes priority: a drop on EITHER axis logs + keeps the higher bar.
        if cur["skill_hit"] < base["skill_hit"] or cur["mcp_hit"] < base["mcp_hit"]:
            # A drop is a ROUTER regression only if the semantic backend was actually up;
            # an Ollama-down run craters recall for infra reasons -> do not cry wolf.
            if _semantic_backend_down():
                return 0
            _append_digest(_regression_desc(base, cur))
            return 0

        # No regression here: ratchet up iff strictly better on at least one axis.
        if cur["skill_hit"] > base["skill_hit"] or cur["mcp_hit"] > base["mcp_hit"]:
            _write_baseline(cur)
        return 0  # otherwise unchanged -> silent
    except Exception as exc:  # fail-open: never crash the scheduler
        try:
            print(f"harness-bench: {exc}", file=sys.stderr)
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
