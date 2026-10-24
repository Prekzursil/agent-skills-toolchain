#!/usr/bin/env python
"""account-hopper — per-account budget tracking and account rotation over accounts YOU fund.

What this is for: you hold more than one cloud account, you have decided how
much of your own money each one may spend, and you run jobs that can outlive a
single account's budget. You want the launcher to ask "which account should I
hop to next, and have I got room left?" without tracking it in your head. The
tool answers from a ledger of what you have already spent, and ``hop`` closes
out the account you are leaving and names the next one in the same step.

Built for the Modal-profile rotation pattern (drain one funded account, relay
the job's checkpointed state to the next, resume), but there is nothing
Modal-specific in it — the accounts are just names.

DELIBERATE NON-FEATURES, each one load-bearing rather than unfinished:

* **No network calls.** This module never talks to Modal, or to anything else.
  Caps come only from your config file. That is the structural guarantee that
  nothing here can trigger off a *provider-side* limit: it cannot read one. A
  budget is a number you chose, not a wall someone else put up.
* **No switching.** ``select`` and ``hop`` print a profile name on stdout and
  exit. Neither sets ``MODAL_PROFILE``, spawns a subprocess, or touches any
  account; ``hop`` writes only its own ledger line. Acting on the answer —
  switching profiles, relaying job state — is the caller's explicit step, so a
  human (or a reviewed launcher) stays in the loop.
* **No account discovery.** An account is eligible only if you enrolled it in the
  config by hand with a cap and ``funded: true``. The tool never enumerates the
  profiles configured on the machine, so it cannot assemble a fleet on your
  behalf; growing one stays a deliberate edit you make.
* **No credentials.** It knows profile *names* and nothing else. It never reads,
  stores or prints a token, and it has no code path that could.

Money is tracked in float and rounded to cents at every boundary. At the scale
this is for (hundreds of entries, dollars not microdollars) the representation
error is ~1e-13, which is irrelevant against a headroom threshold measured in
whole dollars. If this ever needs to be exact to the cent for billing purposes,
switch to ``decimal.Decimal`` rather than adding more rounding.

Stdlib only. Usable as a library or a CLI; see README.md.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Exit codes. 3 is distinct from 2 on purpose: "you asked a well-formed question
# and the answer is no" is a routine outcome a launcher should branch on, whereas
# 2 means the invocation or config was broken and a human needs to look.
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NO_ACCOUNT = 3

STRATEGIES = ("order", "most-remaining")


class ConfigError(Exception):
    """Config or ledger input is unusable. Carries a message fit for stderr."""


@dataclass(frozen=True)
class Account:
    """One enrolled account: a profile name and the cap the user set for it."""

    profile: str
    cap_usd: float
    funded: bool
    note: str = ""


@dataclass(frozen=True)
class Config:
    accounts: tuple[Account, ...]
    global_ceiling_usd: float | None
    min_headroom_usd: float


@dataclass(frozen=True)
class Entry:
    """One recorded spend. Append-only; never rewritten."""

    ts: float
    profile: str
    usd: float
    job_id: str
    note: str


@dataclass(frozen=True)
class Status:
    """Derived view of one account: cap, spent, remaining, and eligibility.

    ``remaining_usd`` is this account's own headroom (cap minus its spend).
    ``effective_remaining_usd`` is what is ACTUALLY spendable on it right now,
    which is the lesser of that and whatever is left under the global ceiling.
    Eligibility and every threshold test use the effective figure: the account
    figure alone would let a launcher overshoot the ceiling by the difference.
    """

    profile: str
    cap_usd: float
    spent_usd: float
    remaining_usd: float
    effective_remaining_usd: float
    funded: bool
    eligible: bool
    reason: str


def _money(value: object, field: str) -> float:
    """Coerce to a finite, non-negative float. Rejects NaN/inf explicitly.

    NaN is the dangerous one: every comparison against it is False, so a NaN cap
    or a NaN spend would make an account silently fail (or silently pass) every
    threshold test instead of erroring. Refuse it at the boundary.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{field}: expected a number, got {type(value).__name__}")
    out = float(value)
    if not math.isfinite(out):
        raise ConfigError(f"{field}: must be a finite number, got {out!r}")
    if out < 0:
        raise ConfigError(f"{field}: must not be negative, got {out}")
    return out


def load_config(path: str | Path) -> Config:
    """Read and validate the user-authored config. Never writes."""
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"config not found: {p}") from None
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config is not valid JSON: {p}: {exc}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"config must be a JSON object: {p}")

    accounts_raw = raw.get("accounts")
    if not isinstance(accounts_raw, list) or not accounts_raw:
        raise ConfigError("config.accounts must be a non-empty list")

    accounts: list[Account] = []
    seen: set[str] = set()
    for i, item in enumerate(accounts_raw):
        where = f"config.accounts[{i}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{where}: must be an object")
        profile = item.get("profile")
        if not isinstance(profile, str) or not profile.strip():
            raise ConfigError(f"{where}.profile: must be a non-empty string")
        profile = profile.strip()
        # A duplicate would make "spent" ambiguous and let one cap shadow another.
        if profile in seen:
            raise ConfigError(f"{where}.profile: duplicate account {profile!r}")
        seen.add(profile)
        cap = _money(item.get("cap_usd"), f"{where}.cap_usd")
        if cap <= 0:
            raise ConfigError(f"{where}.cap_usd: must be greater than 0, got {cap}")
        funded = item.get("funded")
        if not isinstance(funded, bool):
            raise ConfigError(
                f"{where}.funded: must be true or false (explicitly). Mark an "
                f"account true only if YOU fund it and the cap is your own money."
            )
        note = item.get("note") or ""
        if not isinstance(note, str):
            raise ConfigError(f"{where}.note: must be a string")
        accounts.append(Account(profile=profile, cap_usd=cap, funded=funded, note=note))

    ceiling_raw = raw.get("global_ceiling_usd")
    ceiling: float | None = None
    if ceiling_raw is not None:
        ceiling = _money(ceiling_raw, "config.global_ceiling_usd")
        if ceiling <= 0:
            raise ConfigError("config.global_ceiling_usd: must be greater than 0")

    headroom_raw = raw.get("min_headroom_usd")
    headroom = (
        0.0 if headroom_raw is None else _money(headroom_raw, "config.min_headroom_usd")
    )

    return Config(
        accounts=tuple(accounts),
        global_ceiling_usd=ceiling,
        min_headroom_usd=headroom,
    )


def read_entries(path: str | Path) -> list[Entry]:
    """Read the append-only spend log. A missing file means "nothing spent yet".

    A malformed line is fatal rather than skipped: silently ignoring one would
    under-report spend, which is the single failure this tool exists to prevent.
    """
    p = Path(path)
    if not p.is_file():
        return []
    entries: list[Entry] = []
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{p}:{lineno}: corrupt ledger line: {exc}") from None
        if not isinstance(obj, dict):
            raise ConfigError(f"{p}:{lineno}: ledger line must be an object")
        profile = obj.get("profile")
        if not isinstance(profile, str) or not profile.strip():
            raise ConfigError(f"{p}:{lineno}: entry.profile missing")
        entries.append(
            Entry(
                ts=_money(obj.get("ts", 0), f"{p}:{lineno}: entry.ts"),
                profile=profile.strip(),
                usd=_money(obj.get("usd"), f"{p}:{lineno}: entry.usd"),
                job_id=str(obj.get("job_id") or ""),
                note=str(obj.get("note") or ""),
            )
        )
    return entries


def spent_by_account(entries: list[Entry]) -> dict[str, float]:
    """Total spend per profile, rounded to cents."""
    out: dict[str, float] = {}
    for e in entries:
        out[e.profile] = round(out.get(e.profile, 0.0) + e.usd, 2)
    return out


def total_spent(entries: list[Entry]) -> float:
    # float() keeps the JSON contract stable: sum(()) is int 0, which would
    # serialise as `0` rather than `0.0` on an empty ledger.
    return round(float(sum(e.usd for e in entries)), 2)


def ceiling_remaining(cfg: Config, entries: list[Entry]) -> float | None:
    """Dollars left under the global ceiling, or None when no ceiling is set.

    Never negative: an overshoot already recorded reads as zero room left.
    """
    if cfg.global_ceiling_usd is None:
        return None
    return max(0.0, round(cfg.global_ceiling_usd - total_spent(entries), 2))


def account_status(cfg: Config, entries: list[Entry]) -> list[Status]:
    """Cap/spent/remaining and an eligibility verdict for every enrolled account.

    Order mirrors the config, which is also the default selection priority.
    """
    spent_map = spent_by_account(entries)
    ceiling_room = ceiling_remaining(cfg, entries)
    out: list[Status] = []
    for acct in cfg.accounts:
        spent = spent_map.get(acct.profile, 0.0)
        remaining = round(acct.cap_usd - spent, 2)
        # The ceiling is a cap on the TOTAL, so the room it leaves is shared by
        # every account. Spendable here is whichever limit binds first.
        effective = remaining if ceiling_room is None else min(remaining, ceiling_room)
        if not acct.funded:
            eligible, reason = False, "not marked funded in config"
        elif remaining <= 0:
            eligible, reason = False, "cap reached"
        elif effective <= 0:
            eligible, reason = False, "global ceiling reached"
        elif effective < cfg.min_headroom_usd:
            # Say WHICH limit bound, so a refusal is actionable: raising the
            # ceiling and raising a cap are different fixes.
            bound = (
                "global ceiling"
                if ceiling_room is not None and ceiling_room < remaining
                else "account cap"
            )
            eligible, reason = (
                False,
                f"below min headroom (${effective:.2f} < "
                f"${cfg.min_headroom_usd:.2f}, bound by {bound})",
            )
        else:
            eligible, reason = True, "ok"
        out.append(
            Status(
                profile=acct.profile,
                cap_usd=acct.cap_usd,
                spent_usd=spent,
                remaining_usd=remaining,
                effective_remaining_usd=effective,
                funded=acct.funded,
                eligible=eligible,
                reason=reason,
            )
        )
    return out


def ceiling_blocked(cfg: Config, entries: list[Entry]) -> str:
    """Return a refusal reason if the global ceiling is spent, else ""."""
    if cfg.global_ceiling_usd is None:
        return ""
    spent = total_spent(entries)
    if spent >= cfg.global_ceiling_usd:
        return (
            f"global ceiling reached: spent ${spent:.2f} of "
            f"${cfg.global_ceiling_usd:.2f} across all accounts"
        )
    return ""


def select_account(
    cfg: Config, entries: list[Entry], strategy: str = "order"
) -> tuple[Status | None, str]:
    """Pick an account with headroom. Returns ``(status, reason)``.

    ``order`` (default) walks the config order and takes the first eligible
    account, which spends one account down before moving to the next — the
    "use A until its cap, then B" shape. ``most-remaining`` takes the largest
    effective balance instead, spreading spend across accounts.

    Eligibility is computed against ``effective_remaining_usd``, so the global
    ceiling binds even while an account still has per-account headroom. The
    all-spent case is checked first purely to give a clearer message.
    """
    if strategy not in STRATEGIES:
        raise ConfigError(f"unknown strategy {strategy!r}; pick one of {STRATEGIES}")
    blocked = ceiling_blocked(cfg, entries)
    if blocked:
        return None, blocked
    rows = [s for s in account_status(cfg, entries) if s.eligible]
    if not rows:
        room = ceiling_remaining(cfg, entries)
        if room is not None and room < cfg.min_headroom_usd:
            return None, (
                f"only ${room:.2f} left under the ${cfg.global_ceiling_usd:.2f} "
                f"global ceiling, below the ${cfg.min_headroom_usd:.2f} min headroom"
            )
        return None, "no enrolled account has headroom"
    if strategy == "most-remaining":
        # Rank on the effective figure because it is the one that governs. Note
        # this is clarity, not correctness: C is global, every account is clipped
        # by the same C, and min(r, C) is monotone in r, so ranking by raw
        # remaining would pick an equally-spendable account and differ only on
        # ties. Keep the name in the key so those ties resolve deterministically.
        rows.sort(key=lambda s: (-s.effective_remaining_usd, s.profile))
    return rows[0], "ok"


def record_spend(
    ledger_path: str | Path,
    cfg: Config,
    profile: str,
    usd: float,
    job_id: str = "",
    note: str = "",
    dry_run: bool = False,
    now: float | None = None,
) -> Entry:
    """Append one spend entry. With ``dry_run`` it validates and writes nothing.

    Recording against an account that is not enrolled is an error, not an
    implicit enrolment: a typo would otherwise open a shadow account with no cap
    and silently absorb spend that no ceiling applies to.
    """
    known = {a.profile for a in cfg.accounts}
    if profile not in known:
        raise ConfigError(
            f"{profile!r} is not enrolled in the config "
            f"(enrolled: {', '.join(sorted(known)) or 'none'})"
        )
    amount = _money(usd, "--usd")
    entry = Entry(
        ts=time.time() if now is None else now,
        profile=profile,
        usd=round(amount, 2),
        job_id=job_id,
        note=note,
    )
    if not dry_run:
        p = Path(ledger_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "ts": entry.ts,
                "profile": entry.profile,
                "usd": entry.usd,
                "job_id": entry.job_id,
                "note": entry.note,
            },
            sort_keys=True,
        )
        # Append mode: one short line per write, so a crash cannot corrupt an
        # existing entry. The log is never rewritten in place.
        with p.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return entry


def default_ledger_path(config_path: str | Path) -> Path:
    """Ledger sits beside the config unless the caller says otherwise."""
    return Path(config_path).resolve().parent / "spend.jsonl"


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    cfg_path = args.config or os.environ.get("ACCOUNT_HOPPER_CONFIG") or ""
    if not cfg_path:
        raise ConfigError("no config: pass --config PATH or set ACCOUNT_HOPPER_CONFIG")
    ledger = (
        args.ledger
        or os.environ.get("ACCOUNT_HOPPER_LEDGER")
        or default_ledger_path(cfg_path)
    )
    return Path(cfg_path), Path(ledger)


def _cmd_status(args: argparse.Namespace) -> int:
    cfg_path, ledger_path = _resolve_paths(args)
    cfg = load_config(cfg_path)
    entries = read_entries(ledger_path)
    rows = account_status(cfg, entries)
    if args.json:
        payload = {
            "accounts": [
                {
                    "profile": s.profile,
                    "cap_usd": s.cap_usd,
                    "spent_usd": s.spent_usd,
                    "remaining_usd": s.remaining_usd,
                    "effective_remaining_usd": s.effective_remaining_usd,
                    "funded": s.funded,
                    "eligible": s.eligible,
                    "reason": s.reason,
                }
                for s in rows
            ],
            "total_spent_usd": total_spent(entries),
            "global_ceiling_usd": cfg.global_ceiling_usd,
            "ceiling_remaining_usd": ceiling_remaining(cfg, entries),
            "ceiling_blocked": bool(ceiling_blocked(cfg, entries)),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_OK
    width = max(len(s.profile) for s in rows)
    for s in rows:
        mark = "ok " if s.eligible else "-- "
        # Show the effective figure when the ceiling has clipped it, so the
        # number on screen is the one that will actually be honoured.
        clipped = (
            ""
            if s.effective_remaining_usd == s.remaining_usd
            else f" (spendable ${s.effective_remaining_usd:.2f})"
        )
        print(
            f"{mark}{s.profile:<{width}}  remaining ${s.remaining_usd:>8.2f} "
            f"of ${s.cap_usd:>8.2f}   spent ${s.spent_usd:>8.2f}   "
            f"{s.reason}{clipped}"
        )
    spent = total_spent(entries)
    if cfg.global_ceiling_usd is None:
        print(f"\ntotal spent ${spent:.2f} (no global ceiling set)")
    else:
        room = ceiling_remaining(cfg, entries)
        print(
            f"\ntotal spent ${spent:.2f} of ${cfg.global_ceiling_usd:.2f} ceiling"
            f"  (${room:.2f} left under it)"
        )
    blocked = ceiling_blocked(cfg, entries)
    if blocked:
        print(f"REFUSING: {blocked}")
    return EXIT_OK


def _cmd_select(args: argparse.Namespace) -> int:
    cfg_path, ledger_path = _resolve_paths(args)
    cfg = load_config(cfg_path)
    entries = read_entries(ledger_path)
    picked, reason = select_account(cfg, entries, strategy=args.strategy)
    if picked is None:
        print(f"no account available: {reason}", file=sys.stderr)
        return EXIT_NO_ACCOUNT
    # Bare profile name on stdout so it composes:
    #   MODAL_PROFILE="$(account_hopper.py select --config c.json)" modal run ...
    # Acting on it stays the caller's explicit step; this tool does not switch.
    print(picked.profile)
    if args.verbose:
        # Lead with the spendable figure: it is the one a launcher must respect.
        msg = (
            f"spendable ${picked.effective_remaining_usd:.2f} "
            f"(account remaining ${picked.remaining_usd:.2f} of "
            f"${picked.cap_usd:.2f})"
        )
        if picked.effective_remaining_usd < picked.remaining_usd:
            msg += " — clipped by the global ceiling"
        print(msg, file=sys.stderr)
    return EXIT_OK


def _cmd_hop(args: argparse.Namespace) -> int:
    """The rotation step: close out one account, name the next one to hop to.

    With ``--account``/``--usd`` it first records that spend (identical
    validation and dry-run semantics to ``record``), then answers select's
    question against the updated ledger. With no ``--account`` it is a pure
    select — the first hop. Under ``--dry-run`` the pending spend is included
    in the preview, so the printed next account is what a real hop would pick,
    while nothing is written.

    stdout stays a bare profile name so the launcher can compose it; everything
    else goes to stderr. Exit 3 means the rotation is out of budget — a routine
    outcome the launcher branches on, not a crash.
    """
    if args.account is None and args.usd is not None:
        raise ConfigError("--usd only makes sense together with --account")
    if args.account is not None and args.usd is None:
        raise ConfigError("--usd is required with --account")
    cfg_path, ledger_path = _resolve_paths(args)
    cfg = load_config(cfg_path)
    note = ""
    pending: list[Entry] = []
    if args.account is not None:
        entry = record_spend(
            ledger_path,
            cfg,
            profile=args.account,
            usd=args.usd,
            job_id=args.job_id or "",
            note=args.note or "",
            dry_run=args.dry_run,
        )
        prefix = "would record" if args.dry_run else "recorded"
        note = f"{prefix} ${entry.usd:.2f} on {entry.profile}; "
        if args.dry_run:
            # A preview must answer for the world WITH the pending spend, or it
            # would hand out the account the real hop would refuse.
            pending = [entry]
    # Non-dry-run re-reads from disk so the answer reflects the real ledger.
    entries = read_entries(ledger_path) + pending
    picked, reason = select_account(cfg, entries, strategy=args.strategy)
    if picked is None:
        print(f"no account available: {reason}", file=sys.stderr)
        if note:
            print(f"{note}nothing left to hop to", file=sys.stderr)
        return EXIT_NO_ACCOUNT
    print(picked.profile)
    tail = " [dry-run: nothing written]" if args.dry_run else ""
    print(
        f"{note}next: {picked.profile} "
        f"(spendable ${picked.effective_remaining_usd:.2f}){tail}",
        file=sys.stderr,
    )
    return EXIT_OK


def _cmd_record(args: argparse.Namespace) -> int:
    cfg_path, ledger_path = _resolve_paths(args)
    cfg = load_config(cfg_path)
    entry = record_spend(
        ledger_path,
        cfg,
        profile=args.account,
        usd=args.usd,
        job_id=args.job_id or "",
        note=args.note or "",
        dry_run=args.dry_run,
    )
    # Re-derive from disk so the figures shown are the ledger's, not a guess.
    # Under --dry-run nothing was written, so subtract the pending amount.
    pending = entry.usd if args.dry_run else 0.0
    after_entries = read_entries(ledger_path)
    # The profile was validated as enrolled above, so its row always exists.
    row = next(
        s for s in account_status(cfg, after_entries) if s.profile == entry.profile
    )
    prefix = "would record" if args.dry_run else "recorded"
    projected = round(row.remaining_usd - pending, 2)
    tail = f"; remaining ${projected:.2f} of ${row.cap_usd:.2f}"
    room = ceiling_remaining(cfg, after_entries)
    if room is not None:
        tail += f", ${round(room - pending, 2):.2f} under the global ceiling"
    print(f"{prefix} ${entry.usd:.2f} on {entry.profile}{tail}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="account_hopper.py",
        description=(
            "Account hopper: per-account budget ledger plus the rotation step. "
            "Reports, selects, records, and names the next account to hop to; "
            "never switches anything and never calls the network."
        ),
    )
    ap.add_argument(
        "--config", help="path to the JSON config (or ACCOUNT_HOPPER_CONFIG)"
    )
    ap.add_argument("--ledger", help="path to spend.jsonl (default: beside the config)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="show cap/spent/remaining for every account")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(func=_cmd_status)

    s = sub.add_parser("select", help="print the profile name to use next")
    s.add_argument("--strategy", choices=STRATEGIES, default="order")
    s.add_argument("--verbose", action="store_true", help="headroom note on stderr")
    s.set_defaults(func=_cmd_select)

    s = sub.add_parser(
        "hop",
        help="record what the current account spent, then print the next account",
    )
    s.add_argument(
        "--account",
        help="the account you are leaving (enrolled profile name); omit for a pure first hop",
    )
    s.add_argument(
        "--usd", type=float, help="amount spent on it, >= 0 (required with --account)"
    )
    s.add_argument("--job-id", help="your job identifier, for the audit trail")
    s.add_argument("--note", help="free-text note")
    s.add_argument("--strategy", choices=STRATEGIES, default="order")
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="preview the hop including the pending spend, write nothing",
    )
    s.set_defaults(func=_cmd_hop)

    s = sub.add_parser("record", help="append a spend entry for a finished job")
    s.add_argument("--account", required=True, help="enrolled profile name")
    s.add_argument("--usd", required=True, type=float, help="amount spent, >= 0")
    s.add_argument("--job-id", help="your job identifier, for the audit trail")
    s.add_argument("--note", help="free-text note")
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and show the effect, write nothing",
    )
    s.set_defaults(func=_cmd_record)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover - thin CLI entry point
    sys.exit(main())
