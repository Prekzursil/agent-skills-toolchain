#!/usr/bin/env python
"""longhaul measure — what each account has ACTUALLY spent, from Modal's own CLI.

The ledger knows what you told it; this knows what Modal says. Hand-entered
amounts drift the moment a job dies before it is recorded, so a measured figure
is the better input to a budget decision. Ported from the unmerged
modal-budget-ledger PR 2 (``modal_spend.py``), plus the fractal-compute
steward's high-water rule.

Invocation is exactly ``modal billing summary --json --profile <P> --for <cycle>``.
The payload is decimal strings (``"0E-8"``, ``"38.08001548"``) with
``metered_cost``, ``billed_cost`` and ``adjustments.credits``.

THE HIGH-WATER RULE. Successive readings of one account are NOT monotone:
``metered_cost`` was observed to fall (43.79 -> 40.78, and 38.31 -> 38.08) as
the provider re-rated usage. A budget decision on a falling reading would hand
back money already spent, so every decision uses the maximum ever read for that
account in that billing month, persisted in ``highwater.json``.

THE ONE RULE THIS FILE KEEPS: it reads **spend**, never a **limit**. Nothing
here fetches a quota, a plan allowance or a provider-side ceiling; every
threshold comes from the user's config.

Two details that are easy to get wrong:

* ``MODAL_TOKEN_ID`` / ``MODAL_TOKEN_SECRET`` in the environment override
  profile selection, so a child that inherits them meters whichever account the
  tokens belong to while appearing to honour ``--profile``. They are stripped
  from the child environment (never from the caller's).
* ``--profile`` is an argv element, never shell text, and is validated so a name
  cannot be read as a flag.

A failed measurement raises; it never reads as zero, because zero looks like a
fresh account with its whole budget intact.

Stdlib only. The only module in longhaul that starts the provider CLI.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

_PROFILE_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_MONTH_RE = re.compile(r"\A\d{4}-(0[1-9]|1[0-2])\Z")
DEFAULT_TIMEOUT = 60.0
DEFAULT_CACHE_TTL = 240.0
METERS = ("metered", "billed")


class SpendError(Exception):
    """Measurement failed. Message is fit for stderr; never contains a token."""


@dataclass(frozen=True)
class SpendReading:
    """What one account spent in one billing month, in dollars."""

    profile: str
    metered_usd: float
    billed_usd: float
    credits_applied_usd: float
    cycle: str
    fetched_at: float

    def by_meter(self, meter: str) -> float:
        if meter == "metered":
            return self.metered_usd
        if meter == "billed":
            return self.billed_usd
        raise SpendError(f"unknown meter {meter!r}; pick one of {METERS}")


def _to_usd(raw: object, field: str) -> float:
    if raw is None:
        raise SpendError(f"{field}: missing from the billing payload")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, ArithmeticError):
        raise SpendError(f"{field}: not a number: {raw!r}") from None
    if not value.is_finite():
        raise SpendError(f"{field}: not finite: {raw!r}")
    return round(float(value), 2)


def validate_profile(profile: object) -> str:
    """Reject anything that could be read as a flag or fall through to ambient."""
    if not isinstance(profile, str) or not _PROFILE_RE.match(profile):
        raise SpendError(
            f"invalid profile name {profile!r}: expected 1-64 chars of "
            f"[A-Za-z0-9._-] starting with alphanumeric"
        )
    return profile


def child_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """A copy of the environment with the token and profile overrides removed."""
    env = dict(os.environ if base is None else base)
    for key in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "MODAL_PROFILE"):
        env.pop(key, None)
    return env


def cycle_key(cycle: str, now: float | None = None) -> str:
    """The calendar month a cycle names, so high-water marks reset at its boundary."""
    t = time.gmtime(time.time() if now is None else now)
    if cycle == "this month":
        return f"{t.tm_year:04d}-{t.tm_mon:02d}"
    if cycle == "last month":
        year, month = (t.tm_year, t.tm_mon - 1) if t.tm_mon > 1 else (t.tm_year - 1, 12)
        return f"{year:04d}-{month:02d}"
    if _MONTH_RE.match(cycle):
        return cycle
    raise SpendError(
        f"unknown cycle {cycle!r}: use 'this month', 'last month' or YYYY-MM"
    )


def _default_runner(argv: list[str], timeout: float) -> tuple[int, str, str]:
    proc = subprocess.run(  # noqa: S603 - fixed argv, validated profile, no shell
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=child_env(),
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _extract_json(stdout: str) -> dict:
    """The JSON object in stdout, tolerating warning noise around it."""
    text = stdout.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise SpendError("no JSON object in `modal billing summary --json` output")
    try:
        obj = json.loads(text[start : end + 1])
    except ValueError as exc:
        raise SpendError(f"billing payload is not valid JSON: {exc}") from None
    if not isinstance(obj, dict):
        raise SpendError("billing payload is not a JSON object")
    return obj


def parse_summary(obj: dict, profile: str, cycle: str, now: float) -> SpendReading:
    """Build a reading from an already-parsed payload. Pure; no I/O."""
    adjustments = obj.get("adjustments")
    credits_raw = (adjustments if isinstance(adjustments, dict) else {}).get(
        "credits", "0"
    )
    return SpendReading(
        profile=profile,
        metered_usd=_to_usd(obj.get("metered_cost"), "metered_cost"),
        billed_usd=_to_usd(obj.get("billed_cost"), "billed_cost"),
        # Credits arrive negative (they offset metered cost); report the magnitude.
        credits_applied_usd=abs(_to_usd(credits_raw, "adjustments.credits")),
        cycle=cycle,
        fetched_at=now,
    )


def fetch_spend(
    profile: str,
    cycle: str = "this month",
    timeout: float = DEFAULT_TIMEOUT,
    runner: object = None,
    modal_bin: str = "modal",
    now: float | None = None,
) -> SpendReading:
    """Measure one account. ``runner`` is injectable so tests never shell out."""
    validate_profile(profile)
    cycle_key(cycle)
    argv = [
        modal_bin,
        "billing",
        "summary",
        "--json",
        "--profile",
        profile,
        "--for",
        cycle,
    ]
    call = _default_runner if runner is None else runner
    try:
        rc, out, err = call(argv, timeout)  # type: ignore[operator]
    except subprocess.TimeoutExpired:
        raise SpendError(f"{profile}: `modal billing summary` timed out") from None
    except FileNotFoundError:
        raise SpendError(f"{modal_bin!r} not found on PATH") from None
    if rc != 0:
        detail = (err or out or "").strip().splitlines()
        tail = detail[-1][:200] if detail else f"exit {rc}"
        raise SpendError(f"{profile}: billing query failed: {tail}")
    return parse_summary(
        _extract_json(out), profile, cycle, time.time() if now is None else now
    )


def _read_json(path: Path) -> dict:
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return blob if isinstance(blob, dict) else {}


def _write_json(path: Path, blob: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(blob, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def fetch_spend_cached(
    profile: str,
    cache_path: str | Path,
    ttl: float = DEFAULT_CACHE_TTL,
    cycle: str = "this month",
    now: float | None = None,
    **kwargs: object,
) -> SpendReading:
    """``fetch_spend`` behind a TTL cache. A damaged cache is dropped, never fatal."""
    stamp = time.time() if now is None else now
    path = Path(cache_path)
    profiles = _read_json(path).get("profiles")
    cached = profiles if isinstance(profiles, dict) else {}
    row = cached.get(profile)
    if isinstance(row, dict) and row.get("cycle") == cycle:
        try:
            age = stamp - float(row.get("fetched_at") or 0)
            if 0 <= age < ttl:
                return SpendReading(
                    profile=profile,
                    metered_usd=float(row["metered_usd"]),
                    billed_usd=float(row["billed_usd"]),
                    credits_applied_usd=float(row.get("credits_applied_usd") or 0.0),
                    cycle=cycle,
                    fetched_at=float(row["fetched_at"]),
                )
        except (KeyError, TypeError, ValueError):
            pass
    reading = fetch_spend(profile, cycle=cycle, now=stamp, **kwargs)  # type: ignore[arg-type]
    cached[profile] = {
        "metered_usd": reading.metered_usd,
        "billed_usd": reading.billed_usd,
        "credits_applied_usd": reading.credits_applied_usd,
        "cycle": reading.cycle,
        "fetched_at": reading.fetched_at,
    }
    try:
        _write_json(path, {"profiles": cached})
    except OSError:
        pass  # the cache is an optimisation
    return reading


def read_highwater(path: str | Path) -> dict[str, dict[str, float]]:
    """``{month: {"<profile>/<meter>": usd}}``. Corrupt entries are refused loudly:
    silently dropping one would lower a high-water mark."""
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SpendError(f"high-water store {p} is unreadable: {exc}") from None
    if not isinstance(blob, dict):
        raise SpendError(f"high-water store {p} is not a JSON object")
    out: dict[str, dict[str, float]] = {}
    for month, rows in blob.items():
        if not isinstance(rows, dict):
            raise SpendError(f"high-water store {p}: {month!r} is not an object")
        clean: dict[str, float] = {}
        for key, value in rows.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                raise SpendError(f"high-water store {p}: {month}/{key} = {value!r}")
            clean[str(key)] = float(value)
        out[str(month)] = clean
    return out


def raise_highwater(
    path: str | Path, month: str, readings: dict[str, float]
) -> dict[str, float]:
    """Merge readings into the store as ``max(old, new)`` and return the marks."""
    store = read_highwater(path)
    rows = store.setdefault(month, {})
    for key, value in readings.items():
        rows[key] = round(max(rows.get(key, 0.0), float(value)), 2)
    _write_json(Path(path), store)
    return dict(rows)


def measure_accounts(
    accounts: list[tuple[str, str]],
    cycle: str,
    highwater_path: str | Path,
    cache_path: str | Path | None = None,
    ttl: float | None = None,
    **kwargs: object,
) -> tuple[dict[str, float], dict[str, SpendReading]]:
    """Measure ``(profile, meter)`` pairs; return high-water spend and raw readings.

    The decision figure for each profile is the maximum ever read this month.
    """
    readings: dict[str, SpendReading] = {}
    for profile, _meter in accounts:
        if cache_path is not None and ttl is not None:
            readings[profile] = fetch_spend_cached(
                profile, cache_path, ttl=ttl, cycle=cycle, **kwargs
            )
        else:
            readings[profile] = fetch_spend(profile, cycle=cycle, **kwargs)  # type: ignore[arg-type]
    month = cycle_key(cycle)
    marks = raise_highwater(
        highwater_path,
        month,
        {f"{p}/{m}": readings[p].by_meter(m) for p, m in accounts},
    )
    return {p: marks[f"{p}/{m}"] for p, m in accounts}, readings
