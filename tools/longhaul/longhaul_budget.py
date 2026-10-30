#!/usr/bin/env python
"""longhaul budget — per-account lines and a global ceiling over accounts YOU fund.

What this answers, for the one account the caller has already chosen: may new
work start here, can it fund a job of this size, and must work already running
here pause now? It never picks an account. There is no selection strategy, no
rotation and no hop: when an account reaches its line the answer is "no", and
which account to use next is the user's explicit choice.

Origins (see MIGRATION.md): the config, ledger and ceiling logic of
``tools/account-hopper`` (including its ceiling fix,
``effective_remaining_usd = min(account room, ceiling room)``), the measured-spend
option of the unmerged modal-budget-ledger PR 2, and the per-account
threshold-minus-margin line of the fractal-compute steward's budget guard.

THE NUMBERS, PER ACCOUNT

* ``cap_usd`` — what the account may spend in total, your number.
* ``line_usd`` — ``cap_usd - pause_margin_usd``. New work stops here and running
  work is paused here, BEFORE the cap. With no margin the line is the cap.
* ``effective_remaining_usd`` — what is actually spendable: the lesser of the
  room to this account's line and the room to the global line (the global
  ceiling minus the same margin), because the ceiling binds the total.

DELIBERATE NON-FEATURES

* **No network and no subprocess.** Measured spend is read by
  ``longhaul_measure`` and handed in as a plain dict, so every rule here is a
  pure function you can test without a provider.
* **No switching and no selection.** Functions answer about a named profile.
* **No account discovery.** Only accounts you enrolled, with ``funded`` set
  explicitly, exist here.
* **No credentials.** Profile names only.

Stdlib only.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3

SOURCE_LEDGER = "ledger"
SOURCE_MEASURED = "measured"
SPEND_SOURCES = (SOURCE_LEDGER, SOURCE_MEASURED)
METERS = ("metered", "billed")


class ConfigError(Exception):
    """Config or ledger input is unusable. Carries a message fit for stderr."""


@dataclass(frozen=True)
class Account:
    profile: str
    cap_usd: float
    funded: bool
    closed: bool = False
    note: str = ""
    meter: str = ""
    pause_margin_usd: float | None = None

    def margin(self, cfg: Config) -> float:
        return (
            cfg.pause_margin_usd
            if self.pause_margin_usd is None
            else self.pause_margin_usd
        )

    def line(self, cfg: Config) -> float:
        return round(self.cap_usd - self.margin(cfg), 2)

    def meter_for(self, cfg: Config) -> str:
        return self.meter or cfg.meter


@dataclass(frozen=True)
class Config:
    accounts: tuple[Account, ...]
    global_ceiling_usd: float | None
    min_headroom_usd: float = 0.0
    pause_margin_usd: float = 0.0
    spend_source: str = SOURCE_LEDGER
    meter: str = "metered"
    cycle: str = "this month"

    def account(self, profile: str) -> Account:
        for acct in self.accounts:
            if acct.profile == profile:
                return acct
        known = ", ".join(a.profile for a in self.accounts)
        raise ConfigError(
            f"{profile!r} is not enrolled in the config (enrolled: {known})"
        )

    def global_line(self) -> float | None:
        if self.global_ceiling_usd is None:
            return None
        return round(self.global_ceiling_usd - self.pause_margin_usd, 2)


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
    profile: str
    cap_usd: float
    line_usd: float
    spent_usd: float
    line_room_usd: float
    effective_remaining_usd: float
    funded: bool
    closed: bool
    eligible: bool
    reason: str
    measured: bool


def _money(value: object, field: str) -> float:
    """A finite, non-negative float. NaN is refused: it fails every comparison."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{field}: expected a number, got {type(value).__name__}")
    out = float(value)
    if not math.isfinite(out):
        raise ConfigError(f"{field}: must be a finite number, got {out!r}")
    if out < 0:
        raise ConfigError(f"{field}: must not be negative, got {out}")
    return out


def _flag(item: dict, key: str, where: str, required: bool) -> bool:
    value = item.get(key)
    if value is None and not required:
        return False
    if not isinstance(value, bool):
        raise ConfigError(f"{where}.{key}: must be true or false (explicitly)")
    return value


def _account(item: object, where: str, cfg_margin: float) -> Account:
    if not isinstance(item, dict):
        raise ConfigError(f"{where}: must be an object")
    profile = item.get("profile")
    if not isinstance(profile, str) or not profile.strip():
        raise ConfigError(f"{where}.profile: must be a non-empty string")
    cap = _money(item.get("cap_usd"), f"{where}.cap_usd")
    if cap <= 0:
        raise ConfigError(f"{where}.cap_usd: must be greater than 0, got {cap}")
    if not isinstance(item.get("funded"), bool):
        raise ConfigError(
            f"{where}.funded: must be true or false (explicitly). Mark an account "
            f"true only if YOU fund it and the cap is your own money."
        )
    note = item.get("note") or ""
    if not isinstance(note, str):
        raise ConfigError(f"{where}.note: must be a string")
    meter = item.get("meter") or ""
    if meter and meter not in METERS:
        raise ConfigError(f"{where}.meter: must be one of {METERS}")
    margin_raw = item.get("pause_margin_usd")
    margin = (
        None if margin_raw is None else _money(margin_raw, f"{where}.pause_margin_usd")
    )
    if (cfg_margin if margin is None else margin) >= cap:
        raise ConfigError(f"{where}: pause margin must be below cap_usd ({cap})")
    return Account(
        profile=profile.strip(),
        cap_usd=cap,
        funded=item["funded"],
        closed=_flag(item, "closed", where, required=False),
        note=note,
        meter=meter,
        pause_margin_usd=margin,
    )


def load_config(path: str | Path) -> Config:
    """Read and validate the user-authored config. Never writes."""
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"config not found: {p}") from None
    except (OSError, ValueError) as exc:
        raise ConfigError(
            f"config is unreadable or not valid JSON: {p}: {exc}"
        ) from None
    if not isinstance(raw, dict):
        raise ConfigError(f"config must be a JSON object: {p}")
    margin_raw = raw.get("pause_margin_usd")
    margin = (
        0.0 if margin_raw is None else _money(margin_raw, "config.pause_margin_usd")
    )
    accounts_raw = raw.get("accounts")
    if not isinstance(accounts_raw, list) or not accounts_raw:
        raise ConfigError("config.accounts must be a non-empty list")
    accounts: list[Account] = []
    for i, item in enumerate(accounts_raw):
        acct = _account(item, f"config.accounts[{i}]", margin)
        if any(a.profile == acct.profile for a in accounts):
            # A duplicate would make "spent" ambiguous and let one cap shadow another.
            raise ConfigError(
                f"config.accounts[{i}].profile: duplicate {acct.profile!r}"
            )
        accounts.append(acct)
    ceiling: float | None = None
    if raw.get("global_ceiling_usd") is not None:
        ceiling = _money(raw["global_ceiling_usd"], "config.global_ceiling_usd")
        if ceiling <= margin:
            raise ConfigError(
                "config.global_ceiling_usd: must be above pause_margin_usd"
            )
    headroom_raw = raw.get("min_headroom_usd")
    headroom = (
        0.0 if headroom_raw is None else _money(headroom_raw, "config.min_headroom_usd")
    )
    source = raw.get("spend_source") or SOURCE_LEDGER
    if source not in SPEND_SOURCES:
        raise ConfigError(f"config.spend_source: must be one of {SPEND_SOURCES}")
    meter = raw.get("meter") or "metered"
    if meter not in METERS:
        raise ConfigError(f"config.meter: must be one of {METERS}")
    cycle = raw.get("cycle") or "this month"
    if not isinstance(cycle, str) or not cycle.strip():
        raise ConfigError("config.cycle: must be a non-empty string")
    return Config(
        accounts=tuple(accounts),
        global_ceiling_usd=ceiling,
        min_headroom_usd=headroom,
        pause_margin_usd=margin,
        spend_source=source,
        meter=meter,
        cycle=cycle.strip(),
    )


def read_entries(path: str | Path) -> list[Entry]:
    """Read the append-only spend log. A missing file means "nothing recorded".

    A malformed line is fatal rather than skipped: ignoring one would
    under-report spend, which is the failure this module exists to prevent.
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
        except ValueError as exc:
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


def recorded_by_account(entries: list[Entry]) -> dict[str, float]:
    out: dict[str, float] = {}
    for e in entries:
        out[e.profile] = round(out.get(e.profile, 0.0) + e.usd, 2)
    return out


def spent_by_account(
    cfg: Config, entries: list[Entry], measured: dict[str, float] | None = None
) -> dict[str, float]:
    """Spend per ENROLLED account: the measured figure where there is one, else
    the recorded total. An account missing from ``measured`` keeps its recorded
    total rather than reading zero, because zero looks like a full budget."""
    recorded = recorded_by_account(entries)
    measured = measured or {}
    return {
        a.profile: round(
            float(measured.get(a.profile, recorded.get(a.profile, 0.0))), 2
        )
        for a in cfg.accounts
    }


def total_spent(
    cfg: Config, entries: list[Entry], measured: dict[str, float] | None = None
) -> float:
    # float() keeps the JSON contract stable on an empty config sum.
    return round(float(sum(spent_by_account(cfg, entries, measured).values())), 2)


def ceiling_room(
    cfg: Config, entries: list[Entry], measured: dict[str, float] | None = None
) -> float | None:
    """Dollars left under the global LINE, or None with no ceiling. Never negative."""
    line = cfg.global_line()
    if line is None:
        return None
    return max(0.0, round(line - total_spent(cfg, entries, measured), 2))


def account_status(
    cfg: Config, entries: list[Entry], measured: dict[str, float] | None = None
) -> list[Status]:
    """Line, spend, spendable room and a verdict for every enrolled account."""
    spent_map = spent_by_account(cfg, entries, measured)
    room = ceiling_room(cfg, entries, measured)
    out: list[Status] = []
    for acct in cfg.accounts:
        spent = spent_map[acct.profile]
        line = acct.line(cfg)
        line_room = max(0.0, round(line - spent, 2))
        effective = line_room if room is None else min(line_room, room)
        if not acct.funded:
            eligible, reason = False, "not marked funded in config"
        elif acct.closed:
            eligible, reason = False, "closed to new work in config"
        elif line_room <= 0:
            eligible, reason = False, f"at its line (spent ${spent:.2f} >= ${line:.2f})"
        elif effective <= 0:
            eligible, reason = False, "global line reached"
        elif effective < cfg.min_headroom_usd:
            bound = (
                "global line"
                if room is not None and room < line_room
                else "account line"
            )
            eligible, reason = (
                False,
                f"below min headroom (${effective:.2f} < ${cfg.min_headroom_usd:.2f}, "
                f"bound by {bound})",
            )
        else:
            eligible, reason = True, "ok"
        out.append(
            Status(
                profile=acct.profile,
                cap_usd=acct.cap_usd,
                line_usd=line,
                spent_usd=spent,
                line_room_usd=line_room,
                effective_remaining_usd=effective,
                funded=acct.funded,
                closed=acct.closed,
                eligible=eligible,
                reason=reason,
                measured=bool(measured) and acct.profile in (measured or {}),
            )
        )
    return out


def check_profile(
    cfg: Config,
    entries: list[Entry],
    profile: str,
    projected_usd: float = 0.0,
    measured: dict[str, float] | None = None,
) -> tuple[Status, str]:
    """May new work of ``projected_usd`` start on ``profile``? ("" means yes).

    Raises ConfigError for an unenrolled profile. Never suggests another
    account: the next account is the user's explicit choice.
    """
    cfg.account(profile)
    projected = _money(projected_usd, "projected_usd")
    status = next(
        s for s in account_status(cfg, entries, measured) if s.profile == profile
    )
    if not status.eligible:
        return status, status.reason
    if projected > status.effective_remaining_usd:
        return status, (
            f"cannot fund a ${projected:.2f} job: ${status.effective_remaining_usd:.2f} "
            f"spendable before the pause line"
        )
    return status, ""


def pause_targets(
    cfg: Config, entries: list[Entry], measured: dict[str, float] | None = None
) -> dict[str, str]:
    """profile -> reason, for every account whose RUNNING work must pause now.

    An account pauses at its own line, and every account pauses once the total
    reaches the global line. Both lines sit ``pause_margin_usd`` below the cap
    they protect, so the pause lands before the provider's hard stop.
    """
    spent_map = spent_by_account(cfg, entries, measured)
    total = round(sum(spent_map.values()), 2)
    glob = cfg.global_line()
    out: dict[str, str] = {}
    for acct in cfg.accounts:
        spent = spent_map[acct.profile]
        line = acct.line(cfg)
        if spent >= line:
            out[acct.profile] = f"spend ${spent:.2f} >= line ${line:.2f}"
        elif glob is not None and total >= glob:
            out[acct.profile] = f"total ${total:.2f} >= global line ${glob:.2f}"
    return out


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
    implicit enrolment: a typo would otherwise open an uncapped shadow account.
    """
    cfg.account(profile)
    entry = Entry(
        ts=time.time() if now is None else now,
        profile=profile,
        usd=round(_money(usd, "--usd"), 2),
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
        # One short append per write: a crash cannot corrupt an existing entry.
        with p.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return entry
