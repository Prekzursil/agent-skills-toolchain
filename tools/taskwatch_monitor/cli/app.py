"""taskwatch — general-purpose long-task progress monitor (CLI surface).

Subcommands over the declarative registry + snapshot engine:

  taskwatch register <template> <id> [--config k=v ...] [--registry P] [--remediate]
  taskwatch list   [--registry P] [--json]
  taskwatch status [--registry P] [--json] [--watch] [--history DB]
                   [--stall-after SECS] [--interval SECS]

``status`` renders a one-shot report by default, machine-readable JSON with
``--json``, and the live rich TUI (leg/stage grids, GPU sparkline, p50/p90 ETA,
BLIND banner, stall flag) with ``--watch``. The render-string builders live in
:mod:`ui.render` (100% covered); the rich Live loop is :func:`ui.tui.run_watch`
(coverage-omitted presentation code).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.models import TaskSpec
from core.history import HistoryStore
from core.registry import RegistryError
from probes.templates import TemplateError, build_from_template

from . import engine, store
from ui import render, tui

DEFAULT_REGISTRY = "taskwatch.toml"


def _coerce_scalar(value: str) -> object:
    """Coerce a ``--config`` value string into bool/int/float/str."""
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _parse_config(pairs: list[str]) -> dict[str, object]:
    """Parse ``key=value`` config pairs; raise :class:`ValueError` on a bad entry."""
    config: dict[str, object] = {}
    for pair in pairs:
        key, sep, raw = pair.partition("=")
        if not sep or not key:
            raise ValueError(f"config entry {pair!r} must be key=value")
        config[key] = _coerce_scalar(raw)
    return config


def _load_specs_or_none(path: Path) -> list[TaskSpec] | None:
    """Load a registry, printing a message and returning None on error."""
    try:
        return store.load_specs(path)
    except RegistryError as exc:
        print(f"Registry error: {exc}")
        return None


def _load_priors(history: str | None, specs: list[TaskSpec]) -> dict[str, float]:
    """Build a task-type → prior-duration map from the sqlite history store."""
    if not history:
        return {}
    priors: dict[str, float] = {}
    with HistoryStore(history) as hist:
        for spec in specs:
            prior = hist.prior(spec.history_key)
            if prior is not None:
                priors[spec.history_key] = prior.p50
    return priors


def cmd_register(args: argparse.Namespace) -> int:
    try:
        config = _parse_config(args.config)
    except ValueError as exc:
        print(exc)
        return 2
    try:
        spec = build_from_template(
            args.template, args.id, config, remediate=args.remediate
        )
    except TemplateError as exc:
        print(exc)
        return 2
    path = Path(args.registry)
    specs = _load_specs_or_none(path)
    if specs is None:
        return 2
    try:
        specs = store.append_spec(specs, spec)
    except RegistryError as exc:
        print(exc)
        return 2
    store.save_specs(path, specs)
    print(f"Registered '{spec.id}' ({spec.adapter}/{spec.parser or '—'}) → {path}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    specs = _load_specs_or_none(Path(args.registry))
    if specs is None:
        return 2
    if args.json:
        json.dump([spec.to_dict() for spec in specs], sys.stdout, indent=2)
        return 0
    print(render.render_registry_table(specs))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    specs = _load_specs_or_none(Path(args.registry))
    if specs is None:
        return 2
    if not specs:
        print("No tasks registered. Use 'register' first.")
        return 0
    if args.watch:
        tui.run_watch(specs, interval=args.interval, stall_after_s=args.stall_after)
        return 0
    priors = _load_priors(args.history, specs)
    views = engine.snapshot(specs, priors=priors, stall_after_s=args.stall_after)
    if args.json:
        json.dump([view.to_dict() for view in views], sys.stdout, indent=2)
        return 0
    print(render.render_status_report(views))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="taskwatch", description="General-purpose long-task progress monitor."
    )
    sub = parser.add_subparsers(dest="command")

    reg = sub.add_parser("register", help="register a task from a template")
    _ = reg.add_argument("template", help="template name (see probes.templates)")
    _ = reg.add_argument("id", help="unique task id")
    _ = reg.add_argument(
        "--config",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="config entry (repeatable), e.g. --config path=/logs/run.log",
    )
    _ = reg.add_argument("--registry", default=DEFAULT_REGISTRY)
    _ = reg.add_argument("--remediate", action="store_true")
    reg.set_defaults(func=cmd_register)

    lst = sub.add_parser("list", help="list registered tasks")
    _ = lst.add_argument("--registry", default=DEFAULT_REGISTRY)
    _ = lst.add_argument("--json", action="store_true")
    lst.set_defaults(func=cmd_list)

    st = sub.add_parser("status", help="show task status (one-shot / --watch / --json)")
    _ = st.add_argument("--registry", default=DEFAULT_REGISTRY)
    _ = st.add_argument("--json", action="store_true")
    _ = st.add_argument("--watch", action="store_true")
    _ = st.add_argument("--history", default=None, help="sqlite priors DB path")
    _ = st.add_argument(
        "--stall-after",
        type=float,
        default=engine.DEFAULT_STALL_AFTER_S,
        dest="stall_after",
    )
    _ = st.add_argument("--interval", type=float, default=2.0)
    st.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv[1:])
    if getattr(args, "command", None) is None:
        parser.print_help()
        return 2
    result = args.func(args)
    return int(result)


if __name__ == "__main__":  # pragma: no cover - module entrypoint guard
    raise SystemExit(main(sys.argv))
