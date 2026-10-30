#!/usr/bin/env python
"""longhaul — run long cloud jobs on accounts you fund, without losing work or overspending.

One CLI over four parts (see README.md):

* budget      ``status`` / ``check`` / ``record`` — per-account lines and a global
              ceiling, from a ledger or from measured spend (longhaul_budget);
* measure     ``measure`` — read real spend from ``modal billing summary`` and keep
              the high-water mark (longhaul_measure);
* run/watch   ``run`` starts a command on the profile you name, after ``check``;
              ``watch`` pauses that profile's calls before the cap and respawns
              only calls that finished with an error (longhaul_watch);
* checkpoint  ``checkpoint mirror|resume|verify`` — generations with verify-on-read
              (longhaul_checkpoint).

The profile is ALWAYS the caller's explicit choice: every command that acts on an
account takes ``--profile``, and nothing here picks, rotates or hops to another
account. When an account is at its line the answer is exit 3, with the reason.

Exit codes: 0 fine · 2 bad invocation or config · 3 refused or paused by budget.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import longhaul_budget as lb  # noqa: E402
import longhaul_checkpoint as lc  # noqa: E402
import longhaul_measure as lm  # noqa: E402
import longhaul_watch as lw  # noqa: E402


def _paths(args: argparse.Namespace) -> tuple[Path, Path]:
    cfg = args.config or os.environ.get("LONGHAUL_CONFIG") or ""
    if not cfg:
        raise lb.ConfigError("no config: pass --config PATH or set LONGHAUL_CONFIG")
    state = args.state_dir or os.environ.get("LONGHAUL_STATE_DIR") or ""
    return Path(cfg), (Path(state) if state else Path(cfg).resolve().parent)


def _measured(
    cfg: lb.Config, state: Path, args: argparse.Namespace
) -> dict[str, float] | None:
    """High-water measured spend for every funded account, or None for the ledger."""
    if cfg.spend_source != lb.SOURCE_MEASURED or getattr(args, "no_measure", False):
        return None
    pairs = [(a.profile, a.meter_for(cfg)) for a in cfg.accounts if a.funded]
    try:
        marks, _ = lm.measure_accounts(
            pairs,
            cfg.cycle,
            state / "highwater.json",
            cache_path=state / "spend-cache.json",
            ttl=getattr(args, "cache_ttl", lm.DEFAULT_CACHE_TTL),
        )
    except lm.SpendError as exc:
        raise lb.ConfigError(f"measuring spend: {exc}") from None
    return marks


def _stored_marks(cfg: lb.Config, state: Path) -> dict[str, float]:
    """The persisted high-water marks for this month, for when measuring fails.
    Raises ConfigError if there are none: the watch cannot judge a line blind."""
    try:
        month = lm.read_highwater(state / "highwater.json").get(
            lm.cycle_key(cfg.cycle), {}
        )
    except lm.SpendError as exc:
        raise lb.ConfigError(f"no usable high-water marks: {exc}") from None
    marks = {
        a.profile: month[f"{a.profile}/{a.meter_for(cfg)}"]
        for a in cfg.accounts
        if a.funded and f"{a.profile}/{a.meter_for(cfg)}" in month
    }
    if not marks:
        raise lb.ConfigError("measuring failed and no high-water marks are stored yet")
    return marks


def _load(
    args: argparse.Namespace,
) -> tuple[lb.Config, list[lb.Entry], Path, dict | None]:
    cfg_path, state = _paths(args)
    cfg = lb.load_config(cfg_path)
    entries = lb.read_entries(state / "spend.jsonl")
    return cfg, entries, state, _measured(cfg, state, args)


def _cmd_status(args: argparse.Namespace) -> int:
    cfg, entries, _state, measured = _load(args)
    rows = lb.account_status(cfg, entries, measured)
    if args.json:
        print(
            json.dumps(
                {
                    "accounts": [r.__dict__ for r in rows],
                    "total_spent_usd": lb.total_spent(cfg, entries, measured),
                    "global_ceiling_usd": cfg.global_ceiling_usd,
                    "global_line_usd": cfg.global_line(),
                    "global_room_usd": lb.ceiling_room(cfg, entries, measured),
                    "spend_source": cfg.spend_source
                    if measured is not None
                    else "ledger",
                    "cycle": cfg.cycle,
                    "pause": lb.pause_targets(cfg, entries, measured),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return lb.EXIT_OK
    width = max(len(r.profile) for r in rows)
    for r in rows:
        mark = "ok " if r.eligible else "-- "
        print(
            f"{mark}{r.profile:<{width}}  spent ${r.spent_usd:>8.2f}  line ${r.line_usd:>8.2f}"
            f"  cap ${r.cap_usd:>8.2f}  spendable ${r.effective_remaining_usd:>8.2f}  {r.reason}"
        )
    total = lb.total_spent(cfg, entries, measured)
    line = cfg.global_line()
    print(
        f"\ntotal ${total:.2f}"
        + (
            ""
            if line is None
            else f" of global line ${line:.2f} (ceiling ${cfg.global_ceiling_usd:.2f})"
        )
    )
    if measured is not None:
        print(
            f"source: measured {cfg.meter} spend, high-water for {cfg.cycle!r}; caps are per month"
        )
    else:
        print("source: ledger (recorded by hand)")
    for profile, why in lb.pause_targets(cfg, entries, measured).items():
        print(f"PAUSE {profile}: {why}")
    return lb.EXIT_OK


def _check(args: argparse.Namespace) -> tuple[int, str]:
    cfg, entries, _state, measured = _load(args)
    status, why = lb.check_profile(
        cfg, entries, args.profile, args.projected_usd, measured
    )
    if why:
        print(
            f"refused: {args.profile}: {why}. Choose an account yourself; "
            f"`longhaul.py status` lists them.",
            file=sys.stderr,
        )
        return lb.EXIT_REFUSED, ""
    print(
        f"{args.profile}: ${status.effective_remaining_usd:.2f} spendable before its line",
        file=sys.stderr,
    )
    return lb.EXIT_OK, args.profile


def _cmd_check(args: argparse.Namespace) -> int:
    rc, profile = _check(args)
    if rc == lb.EXIT_OK:
        print(profile)
    return rc


def _cmd_record(args: argparse.Namespace) -> int:
    cfg_path, state = _paths(args)
    cfg = lb.load_config(cfg_path)
    entry = lb.record_spend(
        state / "spend.jsonl",
        cfg,
        args.profile,
        args.usd,
        job_id=args.job_id or "",
        note=args.note or "",
        dry_run=args.dry_run,
    )
    print(
        f"{'would record' if args.dry_run else 'recorded'} ${entry.usd:.2f} on {entry.profile}"
    )
    return lb.EXIT_OK


def _cmd_measure(args: argparse.Namespace) -> int:
    cfg_path, state = _paths(args)
    cfg = lb.load_config(cfg_path)
    pairs = [
        (a.profile, a.meter_for(cfg))
        for a in cfg.accounts
        if a.funded and (not args.profile or a.profile == args.profile)
    ]
    if args.profile and not pairs:
        raise lb.ConfigError(f"{args.profile!r} is not an enrolled, funded account")
    try:
        marks, readings = lm.measure_accounts(
            pairs, cfg.cycle, state / "highwater.json"
        )
    except lm.SpendError as exc:
        raise lb.ConfigError(f"measuring spend: {exc}") from None
    for profile, meter in pairs:
        r = readings[profile]
        print(
            f"{profile}: metered ${r.metered_usd:.2f}  billed ${r.billed_usd:.2f}  "
            f"credits ${r.credits_applied_usd:.2f}  -> high-water {meter} ${marks[profile]:.2f}"
        )
    return lb.EXIT_OK


def scoped_env(profile: str, base: dict[str, str] | None = None) -> dict[str, str]:
    """The environment for work on ``profile``: MODAL_PROFILE set, token overrides
    removed (they would silently pin every call to whichever account they belong to)."""
    env = lm.child_env(base)
    env["MODAL_PROFILE"] = lm.validate_profile(profile)
    return env


def _cmd_run(args: argparse.Namespace) -> int:
    rc, _ = _check(args)
    if rc != lb.EXIT_OK:
        return rc
    cmd = list(args.cmd)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        raise lb.ConfigError("run: give the command after --")
    proc = subprocess.run(cmd, env=scoped_env(args.profile), check=False)  # noqa: S603 - the user's own argv, no shell
    return int(proc.returncode)


def _cmd_watch(args: argparse.Namespace) -> int:
    cfg_path, state = _paths(args)
    cfg = lb.load_config(cfg_path)
    cfg.account(args.profile)
    backend = args.backend
    if backend is None:
        # Scope THIS process to the chosen profile before the SDK is imported, so
        # the default Modal client is that account and no token is handled here.
        for key in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"):
            os.environ.pop(key, None)
        os.environ["MODAL_PROFILE"] = lm.validate_profile(args.profile)
        backend = lw.ModalCalls()
    paused = False
    measured: dict[str, float] | None = None
    first = True
    while True:
        entries = lb.read_entries(state / "spend.jsonl")
        try:
            measured = _measured(cfg, state, args)
        except lb.ConfigError as exc:
            # A failed measurement must not stop the watch (its calls would go
            # unpaused) and must never read as zero. Fall back to the last figures
            # this loop saw, else to the stored high-water marks.
            if first:
                measured = _stored_marks(cfg, state)
            print(
                f"{lw.stamp()} MEASURE-FAILED {exc}; using the last known high-water marks"
            )
        first = False
        reason = lb.pause_targets(cfg, entries, measured).get(args.profile, "")
        plan = lw.run_tick(args.calls, args.profile, reason, backend)
        paused = paused or any(a.kind == "pause" for a in plan.actions)
        if plan.pending == 0 or args.once:
            if plan.pending == 0:
                print(
                    f"{lw.stamp()} {'PAUSED' if paused else 'ALL DONE'} {args.profile}: no pending calls"
                )
            return lb.EXIT_REFUSED if paused else lb.EXIT_OK
        time.sleep(args.period)


def _cmd_checkpoint(args: argparse.Namespace) -> int:
    try:
        if args.action == "verify":
            n, result = lc.latest_verified(args.durable, quick=args.quick)
            print(
                f"{'ok' if result.ok else 'REFUSED'}: generation {n}: {result.reason}"
            )
            return lb.EXIT_OK if result.ok else lb.EXIT_REFUSED
        if args.action == "resume":
            res = lc.resume_into(args.durable, args.work)
            print(
                f"resumed generation {res.generation}: {res.hydrated} file(s), {res.bytes_written} bytes"
            )
            return lb.EXIT_OK
        r = lc.DurableCheckpoint(
            args.work, args.durable, handle_signals=False, keep_generations=args.keep
        ).mirror_now()
        print(
            f"generation {r.generation}: {r.copied} copied / {r.linked} linked, "
            f"read-back {'ok' if r.verified else 'FAILED'}, pruned {list(r.pruned)}"
        )
        return lb.EXIT_OK if r.verified else lb.EXIT_REFUSED
    except lc.CheckpointError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return lb.EXIT_REFUSED


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="longhaul.py", description=__doc__.split("\n\n")[0]
    )
    ap.add_argument("--config", help="JSON config (or LONGHAUL_CONFIG)")
    ap.add_argument(
        "--state-dir", help="ledger/high-water/cache dir (default: beside the config)"
    )
    ap.add_argument(
        "--no-measure", action="store_true", help="use the recorded ledger only"
    )
    ap.add_argument("--cache-ttl", type=float, default=lm.DEFAULT_CACHE_TTL)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="spend, line and spendable room per account")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_status)

    for name, func, text in (
        ("check", _cmd_check, "may new work start on --profile? prints it on yes"),
        ("run", _cmd_run, "check, then run CMD scoped to --profile"),
    ):
        s = sub.add_parser(name, help=text)
        s.add_argument("--profile", required=True)
        s.add_argument("--projected-usd", type=float, default=0.0)
        if name == "run":
            s.add_argument("cmd", nargs=argparse.REMAINDER)
        s.set_defaults(func=func)

    s = sub.add_parser("record", help="append a spend entry to the ledger")
    s.add_argument("--profile", required=True)
    s.add_argument("--usd", type=float, required=True)
    s.add_argument("--job-id")
    s.add_argument("--note")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=_cmd_record)

    s = sub.add_parser("measure", help="read real spend and raise the high-water marks")
    s.add_argument("--profile")
    s.set_defaults(func=_cmd_measure)

    s = sub.add_parser(
        "watch", help="pause before the cap; respawn only finished errors"
    )
    s.add_argument("--profile", required=True)
    s.add_argument("--calls", required=True, help="call ledger (calls.jsonl)")
    s.add_argument("--period", type=float, default=180.0)
    s.add_argument("--once", action="store_true", help="one tick, then exit")
    s.set_defaults(func=_cmd_watch, backend=None)

    s = sub.add_parser(
        "checkpoint", help="mirror / resume / verify a durable directory"
    )
    s.add_argument("action", choices=("mirror", "resume", "verify"))
    s.add_argument("--durable", required=True)
    s.add_argument("--work")
    s.add_argument("--keep", type=int, default=lc.DEFAULT_KEEP_GENERATIONS)
    s.add_argument("--quick", action="store_true", help="verify: sizes only")
    s.set_defaults(func=_cmd_checkpoint)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "checkpoint" and args.action != "verify" and not args.work:
        print("error: checkpoint mirror/resume need --work", file=sys.stderr)
        return lb.EXIT_USAGE
    try:
        return int(args.func(args))
    except (lb.ConfigError, lm.SpendError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return lb.EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover - thin CLI entry point
    sys.exit(main())
