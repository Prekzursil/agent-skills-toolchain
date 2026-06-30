#!/usr/bin/env python3
r"""CALIBRATED SILENCE — the proactive-interjection operating-point gate.

Every proactive interjection (a clarifying question, a skill/MCP route, a "gem"
insight, a persistence nudge, a resurfaced open loop) is a Signal-Detection-Theory
decision: surfacing a USEFUL interjection is a hit; surfacing a NOISE one when the
user is busy/tired is a false alarm that costs trust and fatigue. This module turns
"should I interject?" into one adaptive operating-point call that LEARNS from how the
user actually reacted, so the agent can be proactive AND human-like WITHOUT fatiguing.

THE DECISION (per interjection type `itype`):

    interject  iff  ev >= criterion

    ev        = p_useful * value[itype]            # SDT evidence axis
    p_useful  = Wilson-smoothed hit-rate           # acted / (acted + ignored), learned
    criterion = base_threshold + fatigue_bump      # adaptive operating point

Equivalently the EFFECTIVE per-type probability bar is

    p_useful >= (base_threshold + fatigue_bump) / value[itype]

i.e. the criterion is RAISED by fatigue and LOWERED by a type's intrinsic value, and
we compare it against the learned hit-rate. That is exactly the task's "criterion =
base_threshold adjusted by (a) rolling hit-rate and (b) a fatigue proxy raising the bar"
— (a) enters through p_useful (the evidence), (b) through the fatigue bump.

FATIGUE PROXY (each capped, summed, then clamped to FATIGUE_MAX) raises the bar from:
  (a) recent correction-rate  — fraction of recent interjections the user dismissed
      ('annoyed'); a self-contained proxy for "the user is pushing back a lot". An
      explicit context['correction_rate'] (e.g. a truer transcript-derived rate)
      overrides the ledger proxy.
  (b) terse prompts / caveman mode — context['prompt'] very short -> the user wants
      less chatter right now.
  (c) late hour — derivable from the clock (context['now'] override for tests).
  (d) recent-interjection density this session — many interjections already fired
      recently -> back off.

COLD START (don't over-suppress before learning): when the type has fewer than
MIN_SAMPLES reacted samples we ALLOW unconditionally. The Wilson smoothing also pulls
a low-n estimate toward a neutral 0.5 prior, so suppression only emerges once a clear
ignore/annoy pattern has accumulated. See SELF-CALIBRATION-PLAN.md (Huang ICLR'24):
the learning signal is EXTERNAL (the user's next-turn behavior), never self-judgment.

FAIL-OPEN IS A HARD INVARIANT. Suppression is the dangerous failure here, so ANY
error (corrupt ledger, bad input, unreadable file) returns ALLOW. A global kill-switch
(env CALIBRATED_SILENCE=off) also forces ALLOW so the whole system is reversible
without touching any consumer.

This module is PURE, FAST (a few ms; stdlib-only; no network, no model call) and
IMPORTABLE. Consumers call `should_interject(itype, context)` BEFORE emitting and
`record_interjection(itype, context_key, session_id)` WHEN they do emit. The companion
log_reaction.py writes the reaction back so the hit-rate has a learning signal.

CLI (evidence/debugging):
    python calibrated_silence.py --probe suggestion '{"prompt":"no"}'
    python calibrated_silence.py --stats
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- paths
# Code lives in ~/.claude/hooks/calibrated-silence/; the durable ledger (DATA) lives
# in ~/.claude/calibrated-silence/ (separate from code, per spec). LEDGER_PATH is a
# module global so tests/demo can repoint it (the persist-nudge SEEN_DIR convention).
HOME = Path.home()
LEDGER_PATH = HOME / ".claude" / "calibrated-silence" / "interjections.jsonl"

VALID_TYPES = ("question", "suggestion", "gem", "route", "nudge", "resurface")
VALID_REACTIONS = ("acted", "ignored", "annoyed", "unknown")


# --------------------------------------------------------------------------- tunables
def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except Exception:
        return default


# Core operating point.
BASE_THRESHOLD = _env_float("CALSIL_BASE_THRESHOLD", 0.40)  # neutral criterion
MIN_SAMPLES = _env_int("CALSIL_MIN_SAMPLES", 5)  # cold-start allow band
DEFAULT_VALUE = _env_float("CALSIL_DEFAULT_VALUE", 1.0)
# Per-type intrinsic value (V in EV). Higher value -> a lower effective probability bar
# (a high-compounding "gem" earns a slot more easily than a routine nudge). Tunable priors.
VALUE = {
    "question": 1.0,
    "suggestion": 0.9,
    "gem": 1.3,
    "route": 1.0,
    "nudge": 0.85,
    "resurface": 1.1,
}

# Fatigue weights (each contribution is bounded; the sum is clamped to FATIGUE_MAX so
# fatigue can RAISE the bar but never make a genuinely high-value/high-hit interjection
# impossible — total silence is itself a failure mode we refuse).
FATIGUE_MAX = _env_float("CALSIL_FATIGUE_MAX", 0.30)
FATIGUE_CORR_W = _env_float("CALSIL_FATIGUE_CORR_W", 0.18)  # x correction-rate in [0,1]
FATIGUE_TERSE = _env_float("CALSIL_FATIGUE_TERSE", 0.08)  # flat, if prompt is terse
FATIGUE_LATE = _env_float("CALSIL_FATIGUE_LATE", 0.05)  # flat, if late hour
FATIGUE_DENSITY_W = _env_float("CALSIL_FATIGUE_DENSITY_W", 0.14)  # x density/cap

# Windows / counts.
CORR_RECENT = _env_int("CALSIL_CORR_RECENT", 12)  # rows for the correction proxy
DENSITY_WINDOW = _env_int("CALSIL_DENSITY_WINDOW", 1800)  # seconds counted as "recent"
DENSITY_CAP = _env_int("CALSIL_DENSITY_CAP", 4)  # density saturates here
TERSE_WORDS = _env_int("CALSIL_TERSE_WORDS", 4)  # <= this many words == terse
WILSON_Z = _env_float("CALSIL_WILSON_Z", 1.96)  # 95% smoothing constant
LEDGER_MAX = _env_int("CALSIL_LEDGER_MAX", 5000)  # rows kept on a rewrite/trim
_TRIM_BYTES = 2_000_000  # append-path size guard


def _disabled() -> bool:
    return os.environ.get("CALIBRATED_SILENCE", "").strip().lower() in (
        "off",
        "0",
        "false",
        "no",
    )


# --------------------------------------------------------------------------- ledger I/O
def _ledger_path(path=None) -> Path:
    return Path(path) if path else LEDGER_PATH


def read_rows(path=None) -> list:
    """Return the ledger as a list of dict rows. [] on any error (fail-open read)."""
    p = _ledger_path(path)
    out = []
    try:
        if not p.exists():
            return out
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue  # skip a single corrupt line, keep the rest
                if isinstance(row, dict):
                    out.append(row)
    except Exception:
        return []
    return out


def _atomic_write_rows(rows, path=None) -> bool:
    """Rewrite the ledger atomically (os.replace), keeping only the last LEDGER_MAX rows."""
    p = _ledger_path(path)
    tmp = None
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        rows = rows[-LEDGER_MAX:]
        tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
        with tmp.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp, p)
        return True
    except Exception:
        try:
            if tmp and tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return False


def _maybe_trim(path=None) -> None:
    """Cheap append-path size guard: if the file has grown large (e.g. the reaction
    logger is not wired yet), rewrite keeping the last LEDGER_MAX rows. Fail-open."""
    p = _ledger_path(path)
    try:
        if p.exists() and p.stat().st_size > _TRIM_BYTES:
            _atomic_write_rows(read_rows(p), p)
    except Exception:
        pass


def record_interjection(
    itype, context_key, session_id="default", *, surfaced=True, path=None, now=None
) -> bool:
    """Append one interjection row (reaction='unknown') so the hit-rate gets a denominator.

    Consumers MUST call this WHEN they actually surface an interjection (right after the
    matching `should_interject` returns True and the message is emitted). Append-only and
    O(1) so concurrent sessions do not clobber each other. Fail-open -> returns False.
    """
    p = _ledger_path(path)
    try:
        row = {
            "ts": float(now if now is not None else time.time()),
            "type": str(itype),
            "context_key": str(context_key),
            "session_id": str(session_id or "default"),
            "surfaced": bool(surfaced),
            "reaction": "unknown",
        }
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        _maybe_trim(p)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- statistics
def wilson_center(acted: int, n: int, z: float = None) -> float:
    """Wilson score-interval CENTER for `acted` successes in `n` trials.

    The center (not the lower bound) is used deliberately: it is a SMOOTHED point
    estimate that pulls toward a neutral 0.5 prior when n is small, so a couple of
    early ignores cannot drive the estimate to 0 and over-suppress. As n grows it
    converges to the raw hit-rate. Returns 0.5 for n<=0 (maximally uncertain).
    """
    if n <= 0:
        return 0.5
    z = WILSON_Z if z is None else z
    phat = acted / n
    z2 = z * z
    return (phat + z2 / (2 * n)) / (1 + z2 / n)


def counts_by_type(rows) -> dict:
    """{itype: {'acted':a,'ignored':i,'annoyed':n,'unknown':u}} over all rows."""
    out = {}
    for row in rows:
        try:
            t = str(row.get("type") or "")
            r = str(row.get("reaction") or "unknown")
            bucket = out.setdefault(
                t, {"acted": 0, "ignored": 0, "annoyed": 0, "unknown": 0}
            )
            if r not in bucket:
                r = "unknown"
            bucket[r] += 1
        except Exception:
            continue
    return out


def hit_rate(itype, rows=None):
    """Return (p_useful, acted, ignored) for `itype`. p_useful is Wilson-smoothed."""
    rows = read_rows() if rows is None else rows
    c = counts_by_type(rows).get(str(itype), {"acted": 0, "ignored": 0})
    a, i = int(c.get("acted", 0)), int(c.get("ignored", 0))
    return wilson_center(a, a + i), a, i


# --------------------------------------------------------------------------- fatigue inputs
def _now_epoch(context) -> float:
    now = context.get("now")
    try:
        if now is None:
            return time.time()
        if hasattr(now, "timestamp"):  # datetime
            return float(now.timestamp())
        return float(now)  # epoch number
    except Exception:
        return time.time()


def _hour(context):
    try:
        return time.localtime(_now_epoch(context)).tm_hour
    except Exception:
        return None


def _is_terse(prompt) -> bool:
    """Terse / caveman: very few words. A proxy for 'the user wants less chatter now'."""
    try:
        p = str(prompt or "").strip().lstrip("*").strip()
        if not p:
            return False
        return len(p.split()) <= TERSE_WORDS
    except Exception:
        return False


def _recent_correction_rate(rows, context) -> float:
    """Fraction of the most recent CORR_RECENT classified interjections that were
    'annoyed' (a dismissal). Session-scoped when context['session_id'] is given.
    Self-contained proxy for the user's recent correction/pushback rate."""
    try:
        sid = context.get("session_id")
        classified = [
            r
            for r in rows
            if str(r.get("reaction")) in ("acted", "ignored", "annoyed")
            and (sid is None or str(r.get("session_id")) == str(sid))
        ]
        classified = classified[-CORR_RECENT:]
        if not classified:
            return 0.0
        annoyed = sum(1 for r in classified if str(r.get("reaction")) == "annoyed")
        return annoyed / len(classified)
    except Exception:
        return 0.0


def _recent_density(rows, context) -> int:
    """How many interjections were surfaced recently (DENSITY_WINDOW) this session."""
    try:
        sid = context.get("session_id")
        now = _now_epoch(context)
        cnt = 0
        for r in rows:
            if not r.get("surfaced", True):
                continue
            if sid is not None and str(r.get("session_id")) != str(sid):
                continue
            try:
                if now - float(r.get("ts", 0)) <= DENSITY_WINDOW:
                    cnt += 1
            except Exception:
                continue
        return cnt
    except Exception:
        return 0


def fatigue_bump(itype, context, rows):
    """Return (bump, detail_str). bump in [0, FATIGUE_MAX]. Pure; reads only `rows`+context."""
    bump = 0.0
    parts = []
    try:
        # (a) recent correction-rate (explicit override wins over the ledger proxy)
        cr = context.get("correction_rate")
        cr = _recent_correction_rate(rows, context) if cr is None else cr
        try:
            cr = max(0.0, min(1.0, float(cr)))
        except Exception:
            cr = 0.0
        if cr > 0:
            bump += FATIGUE_CORR_W * cr
            parts.append(f"corr={cr:.2f}")

        # (b) terse / caveman prompt
        if "prompt" in context and _is_terse(context.get("prompt")):
            bump += FATIGUE_TERSE
            parts.append("terse")

        # (c) late hour
        h = _hour(context)
        if h is not None and (h < 6 or h >= 23):
            bump += FATIGUE_LATE
            parts.append(f"late={h}")

        # (d) recent-interjection density this session
        d = _recent_density(rows, context)
        if d > 0:
            bump += FATIGUE_DENSITY_W * (min(d, DENSITY_CAP) / DENSITY_CAP)
            parts.append(f"dens={d}")

        bump = min(bump, FATIGUE_MAX)
    except Exception:
        return 0.0, ""  # fail-open: no fatigue penalty on error
    return bump, (" " + " ".join(parts) if parts else "")


# --------------------------------------------------------------------------- the gate
def should_interject(itype: str, context: dict = None):
    """Decide whether to surface an interjection of type `itype`.

    Returns (allow: bool, reason: str). NEVER raises. FAIL-OPEN: any error, a corrupt
    ledger, or the global kill-switch returns (True, ...) — suppression is the dangerous
    failure, so we default to allowing the interjection.

    `context` (all optional):
        prompt          str   the current user prompt (terseness signal)
        session_id      str   scopes density + correction-rate to this session
        correction_rate float explicit recent correction rate (overrides ledger proxy)
        now             float|datetime  clock override (tests; late-hour signal)
        ledger_path     str|Path        ledger override (tests/demo isolation)
    """
    context = context or {}
    try:
        if _disabled():
            return True, "allow:disabled (CALIBRATED_SILENCE=off)"

        path = context.get("ledger_path")
        rows = read_rows(path)
        c = counts_by_type(rows).get(str(itype), {"acted": 0, "ignored": 0})
        acted, ignored = int(c.get("acted", 0)), int(c.get("ignored", 0))
        n = acted + ignored

        # cold start: never suppress before we have learned anything
        if n < MIN_SAMPLES:
            return (
                True,
                f"allow:cold-start n={n}<{MIN_SAMPLES} (acted={acted} ignored={ignored})",
            )

        p_useful = wilson_center(acted, n)
        value = VALUE.get(str(itype), DEFAULT_VALUE)
        ev = p_useful * value
        bump, detail = fatigue_bump(itype, context, rows)
        criterion = BASE_THRESHOLD + bump

        base = (
            f"p={p_useful:.2f} v={value} ev={ev:.3f} crit={criterion:.3f} "
            f"(base={BASE_THRESHOLD} fat={bump:.3f}{detail}) n={n}"
        )
        if ev >= criterion:
            return True, "allow " + base
        return False, "suppress " + base
    except Exception as e:  # pragma: no cover - defensive
        return True, f"allow:fail-open {type(e).__name__}"


# --------------------------------------------------------------------------- CLI (evidence)
def _cli(argv) -> int:
    if len(argv) >= 2 and argv[1] == "--stats":
        rows = read_rows()
        cbt = counts_by_type(rows)
        print(f"ledger: {LEDGER_PATH}  rows={len(rows)}")
        for t in sorted(cbt):
            c = cbt[t]
            p, a, i = hit_rate(t, rows)
            print(
                f"  {t:11s} acted={c['acted']:<4} ignored={c['ignored']:<4} "
                f"annoyed={c['annoyed']:<4} unknown={c['unknown']:<4}  p_useful={p:.2f}"
            )
        return 0
    if len(argv) >= 2 and argv[1] == "--probe":
        itype = argv[2] if len(argv) > 2 else "suggestion"
        ctx = {}
        if len(argv) > 3:
            try:
                ctx = json.loads(argv[3])
            except Exception:
                ctx = {}
        allow, reason = should_interject(itype, ctx)
        print(f"{itype}: {'ALLOW' if allow else 'SUPPRESS'}  | {reason}")
        return 0
    print(__doc__.strip().splitlines()[0])
    print("usage: calibrated_silence.py [--stats | --probe <type> '<json-context>']")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
