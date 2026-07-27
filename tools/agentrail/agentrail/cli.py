"""THE CLI. Every command emits the SAME envelope, on both the success and the failure path.

Output is one JSON object on stdout carrying agentspec's four mandated fields --
``status`` / ``summary`` / ``next_actions`` / ``artifacts`` -- plus ``error`` on a failure and
``terminal`` (the ``SUCCESS:<id>`` / ``FAILED:<id> <reason>`` marker) always. A caller can parse
one shape regardless of outcome, and no path produces error-only output without next steps.

THERE IS NO ``--prompt`` FLAG, deliberately. Accepting prompt TEXT would put it on this
process's own argv -- precisely the measured failure (``os error 206`` at
``payload_len=34472``) the package exists to prevent. The prompt arrives by ``--prompt-file`` or
by ``--prompt-stdin``, and agentrail then routes it to the rail by file or stdin.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from agentspec.argv import ArgvTooLong, PolicyViolation, PromptOnArgv
from agentspec.envelope import Observation, success, warning
from agentspec.terminal import success_line

from agentrail import CONFIG_VERSION
from agentrail.deploy import SHIM_NAME, deploy_shim
from agentrail.plan import (
    DispatchPlan,
    DispatchRefused,
    checked_unit_id,
    plan_with_retry,
)
from agentrail.ports import CollectingWarnings
from agentrail.rails import ConfigError, RailRow, expand_rows, load_rows, row_by_name
from agentrail.report import (
    RailReport,
    argv_too_long,
    refusal,
    resolution_failure,
    transport_failure,
)
from agentrail.resolve import ExecutableNotFound, Resolution, glob_ambiguity, resolve
from agentrail.runner import Ports, default_ports, run_plan

PROG = "agentrail"
EXIT_OK = 0
EXIT_ERROR = 1
DEFAULT_CONFIG = Path(__file__).with_name("rails.toml")


@dataclass(frozen=True, slots=True)
class CommandResult:
    """One command's outcome: the shared envelope plus its terminal marker.

    The marker is carried rather than derived at print time so ``run`` can surface the ORACLE's
    marker (keyed to the work-unit id) instead of a second, weaker one invented by the CLI.
    """

    observation: Observation
    terminal: str


@dataclass(frozen=True, slots=True)
class Environment:
    """Everything the CLI needs from the outside world, injected so it can be faked whole."""

    ports: Ports
    home: str
    tools_dir: str
    config_path: str
    out: Callable[[str], None]
    stdin_text: Callable[[], str]


def default_environment() -> Environment:
    """Production wiring. The one function that reads the real machine."""
    return Environment(
        ports=default_ports(),
        home=str(Path.home()),
        tools_dir=str(Path(__file__).resolve().parents[2]),
        config_path=str(DEFAULT_CONFIG),
        out=_print,
        stdin_text=_read_stdin,
    )


def main(argv: Sequence[str] | None = None, env: Environment | None = None) -> int:
    """Run one command. Returns a process exit code; never raises for an expected failure.

    The trailing ``except ValueError`` is a NET, not the primary defence -- every guard in
    agentrail (:class:`~agentrail.rails.ConfigError`,
    :class:`~agentrail.plan.DispatchRefused`, :class:`~agentrail.report.UnknownReason`) and
    every guard in agentspec (``PromptOnArgv``, ``PolicyViolation``, ``ArgvTooLong``, and the
    ``ValueError`` :func:`agentspec.terminal.success_line` raises) is a ``ValueError``, so that
    one clause is exactly the "a guard refused" family. It is NOT ``except Exception``: a
    ``TypeError`` or ``AttributeError`` is a programming defect and dressing it up as a
    policy-violation envelope would hide it.

    MEASURED: without this arm, ``plan <rail> --unit-id "wu 1"`` printed a bare traceback and
    NO envelope at all -- strictly worse than the "error-only output without next steps"
    anti-pattern, since there were no next steps and no marker either. The specific arms above
    stay because they render RICHER envelopes; this one only guarantees that no path can
    escape without one.
    """
    environment = default_environment() if env is None else env
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    handler: Callable[[argparse.Namespace, Environment], CommandResult] = args.handler
    try:
        result = handler(args, environment)
    except ConfigError as exc:
        result = _envelope_error(_config_failure(exc))
    except ArgvTooLong as exc:
        result = _envelope_error(
            argv_too_long(_unit(args), cmdline_len=exc.cmdline_len, cap=exc.cap)
        )
    except (PromptOnArgv, PolicyViolation) as exc:
        result = _envelope_error(_policy_failure(_unit(args), exc))
    except ValueError as exc:
        result = _envelope_error(_policy_failure(_unit(args), exc))
    environment.out(render(result))
    return EXIT_OK if result.observation.status != "error" else EXIT_ERROR


def console_main() -> int:
    """The ``[project.scripts]`` entry point."""
    return main()


def build_parser() -> argparse.ArgumentParser:
    """The command surface. Each subcommand binds its own handler, so there is no dispatch
    table to drift out of sync with this list."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Config-driven multi-rail agent dispatch over the agentspec safety core. "
            "Rails are TOML rows; the prompt never reaches argv."
        ),
    )
    parser.add_argument("--config", default=None, help="path to a rails.toml override")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("rails", help="list the configured rail rows")
    listing.set_defaults(handler=_cmd_rails)

    resolving = sub.add_parser("resolve", help="resolve one rail's executable")
    resolving.add_argument("rail")
    resolving.set_defaults(handler=_cmd_resolve)

    planning = sub.add_parser("plan", help="build a dispatch plan without running it")
    _add_dispatch_args(planning)
    planning.set_defaults(handler=_cmd_plan)

    running = sub.add_parser(
        "run", help="dispatch a unit to a rail and judge its receipt"
    )
    _add_dispatch_args(running)
    running.add_argument("--cwd", default=None, help="working directory for the rail")
    running.set_defaults(handler=_cmd_run)

    deploying = sub.add_parser("deploy", help=f"install the {SHIM_NAME} shim")
    deploying.add_argument(
        "--target", default=None, help=f"path to write {SHIM_NAME} to"
    )
    deploying.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing shim (default is to REFUSE and leave it untouched)",
    )
    deploying.set_defaults(handler=_cmd_deploy)
    return parser


def _add_dispatch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("rail")
    parser.add_argument("--unit-id", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--prompt-file", default=None, help="read the prompt from this file"
    )
    source.add_argument(
        "--prompt-stdin",
        action="store_true",
        help="read the prompt from this process's stdin",
    )
    parser.add_argument(
        "--spill-dir", default=".", help="where a file-transport prompt is written"
    )
    parser.add_argument("--receipt-path", default=None)
    parser.add_argument("--timeout-s", type=int, default=None)
    parser.add_argument("--flag", action="append", default=[], dest="flags")
    parser.add_argument(
        "--allow-unverified",
        action="store_true",
        help="permit a rail whose headless operation is UNVERIFIED",
    )


def _cmd_rails(args: argparse.Namespace, env: Environment) -> CommandResult:
    rows = _rows(args, env)
    verified = tuple(row.name for row in rows if row.verified)
    return _ok(
        success(
            f"{len(rows)} rail row(s) from config v{CONFIG_VERSION}: "
            f"{len(verified)} verified, {len(rows) - len(verified)} UNVERIFIED",
            next_actions=(
                "run `agentrail resolve <rail>` to check an executable resolves",
                "add a rail by adding a [rail.<name>] row -- no Python change is needed",
            ),
            artifacts=tuple(_describe(row) for row in rows),
        ),
        "rails",
    )


def _cmd_resolve(args: argparse.Namespace, env: Environment) -> CommandResult:
    row = row_by_name(_rows(args, env), args.rail)
    try:
        resolution = resolve(row, env.ports.fs, sink=CollectingWarnings())
    except ExecutableNotFound as exc:
        return _envelope_error(
            resolution_failure(row.name, row.name, exc.reason, tried=exc.tried)
        )
    matches = glob_ambiguity(row, env.ports.fs)
    artifacts = (
        f"exe={resolution.exe}",
        f"resolved-by={resolution.source}",
        f"glob-matches={len(matches)}",
        *resolution.warnings,
    )
    if resolution.degraded:
        return _ok(
            warning(
                f"{row.name}: resolved to a FALLBACK shim, not the vendor executable",
                next_actions=("repair the install so the primary glob matches",),
                artifacts=artifacts,
            ),
            row.name,
        )
    return _ok(
        success(
            f"{row.name}: resolved {resolution.exe}",
            next_actions=("run `agentrail plan <rail>` to build a dispatch",),
            artifacts=artifacts,
        ),
        row.name,
    )


def _cmd_plan(args: argparse.Namespace, env: Environment) -> CommandResult:
    prepared = _prepare(args, env)
    if isinstance(prepared, CommandResult):
        return prepared
    _, plan, _ = prepared
    return _ok(
        success(
            f"{plan.unit_id}: planned {plan.rail_name} via {plan.transport} "
            f"({plan.argv_plan.cmdline_len} argv chars)",
            next_actions=("re-run the same command as `run` to dispatch it",),
            artifacts=_plan_artifacts(plan),
        ),
        plan.unit_id,
    )


def _cmd_run(args: argparse.Namespace, env: Environment) -> CommandResult:
    prepared = _prepare(args, env)
    if isinstance(prepared, CommandResult):
        return prepared
    row, plan, resolution = prepared
    report = run_plan(
        plan,
        row=row,
        resolution=resolution,
        fs=env.ports.fs,
        spawn=env.ports.spawn,
        clock=env.ports.clock,
        cwd=args.cwd,
    )
    return CommandResult(observation=report.observation, terminal=report.terminal)


def _cmd_deploy(args: argparse.Namespace, env: Environment) -> CommandResult:
    target = args.target or str(Path(env.home) / ".local" / "bin" / SHIM_NAME)
    decision = deploy_shim(
        env.ports.fs,
        target=target,
        tools_dirs=candidate_tools_dirs(env),
        overwrite=args.overwrite,
    )
    artifacts = (f"target={decision.target}", f"action={decision.action}")
    if decision.writes:
        return _ok(
            success(
                f"{SHIM_NAME}: {decision.action} -> {decision.target}",
                next_actions=(
                    f"run `{PROG} --help` from a shell outside the checkout",
                ),
                artifacts=artifacts,
            ),
            "deploy",
        )
    return _ok(
        warning(
            f"{SHIM_NAME}: {decision.rationale}",
            next_actions=(
                "diff the existing shim against the rendered one",
                "re-run with --overwrite once you have confirmed it is stale",
            ),
            artifacts=artifacts,
        ),
        "deploy",
    )


def candidate_tools_dirs(env: Environment) -> tuple[str, ...]:
    """Tools roots for the shim to probe, best first: the CANONICAL checkout, then this one.

    The canonical checkout leads because a shim generated from a throwaway git worktree dies
    when that worktree is pruned -- the same defect class as a hardcoded codex path, one level
    up. ``env.tools_dir`` follows so the shim also works from wherever ``deploy`` was actually
    run, including before the change has merged into the canonical checkout.
    """
    canonical = str(Path(env.home) / "source" / "agent-skills-toolchain" / "tools")
    ordered = [canonical, env.tools_dir]
    return tuple(dict.fromkeys(ordered))


def _prepare(
    args: argparse.Namespace, env: Environment
) -> tuple[RailRow, DispatchPlan, Resolution] | CommandResult:
    """Shared plan construction. Returns an ENVELOPE on any refusal, never a bare exception.

    The unit id is checked FIRST -- before the row lookup, before the verified gate, before the
    prompt is read and long before anything is spawned. Every one of those steps renders a
    terminal marker keyed to the id, so an id agentspec cannot render has to be rejected while
    rejecting it is still cheap. Measured with the check missing: ``run`` reached the rail
    (``spawned=1``) and then discarded its result.
    """
    checked_unit_id(args.unit_id)
    row = row_by_name(_rows(args, env), args.rail)
    if not row.verified and not args.allow_unverified:
        return _envelope_error(_unverified(row, args.unit_id))

    prompt = _prompt(args, env)
    if isinstance(prompt, CommandResult):
        return prompt

    try:
        resolution = resolve(row, env.ports.fs, sink=CollectingWarnings())
    except ExecutableNotFound as exc:
        return _envelope_error(
            resolution_failure(args.unit_id, row.name, exc.reason, tried=exc.tried)
        )
    try:
        plan = plan_with_retry(
            row,
            resolution.exe,
            unit_id=args.unit_id,
            prompt=prompt,
            spill_dir=args.spill_dir,
            receipt_path=args.receipt_path,
            timeout_s=args.timeout_s,
            flags=tuple(args.flags),
        )
    except DispatchRefused as exc:
        return _envelope_error(refusal(args.unit_id, exc.violations))
    return row, plan, resolution


def _prompt(args: argparse.Namespace, env: Environment) -> str | CommandResult:
    """Read the prompt from a file or from stdin. Never from argv."""
    if args.prompt_stdin:
        text = env.stdin_text()
    else:
        raw = env.ports.fs.read_bytes(args.prompt_file)
        if raw is None:
            return _envelope_error(
                transport_failure(
                    args.unit_id,
                    "env-missing",
                    detail=f"prompt file {args.prompt_file!r} does not exist",
                    next_action="point --prompt-file at a readable file",
                    retry_instruction="do NOT retry: nothing changes until the file exists",
                    stop_condition=(
                        f"stop immediately and report FAILED {args.unit_id} env-missing"
                    ),
                )
            )
        text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        return _envelope_error(
            transport_failure(
                args.unit_id,
                "policy-violation",
                detail="the prompt is empty; agentspec refuses an empty prompt",
                next_action="supply a non-empty prompt",
                retry_instruction="unrecoverable by retry -- the caller must be fixed",
                stop_condition=(
                    f"stop immediately and report FAILED {args.unit_id} policy-violation"
                ),
            )
        )
    return text


def _unverified(row: RailRow, unit_id: str) -> RailReport:
    return transport_failure(
        unit_id,
        "policy-violation",
        detail=(
            f"rail {row.name!r} is INSTALLED but its headless operation is UNVERIFIED "
            f"({row.notes})"
        ),
        next_action=(
            f"run the settling experiment for {row.name!r}, or pass --allow-unverified"
        ),
        retry_instruction=(
            "do NOT retry as-is. --allow-unverified opts in explicitly and accepts that the "
            "dispatch may hang until its timeout."
        ),
        stop_condition=f"stop immediately and report FAILED {unit_id} policy-violation",
        artifacts=(f"rail={row.name}", "verified=false"),
    )


def _config_failure(exc: ConfigError) -> RailReport:
    return transport_failure(
        PROG,
        "policy-violation",
        detail=f"{type(exc).__name__}: {exc}",
        next_action="fix rails.toml (or the arguments) and re-run",
        retry_instruction="unrecoverable by retry -- the configuration must be fixed",
        stop_condition=f"stop immediately and report FAILED {PROG} policy-violation",
    )


def _policy_failure(unit_id: str, exc: Exception) -> RailReport:
    return transport_failure(
        unit_id,
        "policy-violation",
        detail=f"{type(exc).__name__}: {exc}",
        next_action="fix the rail row so the prompt stays off argv, then re-plan",
        retry_instruction=(
            "unrecoverable by retry -- a prompt on argv is a CALLER defect, and widening the "
            "transport enum would reintroduce the measured os error 206"
        ),
        stop_condition=f"stop immediately and report FAILED {unit_id} policy-violation",
    )


def _rows(args: argparse.Namespace, env: Environment) -> tuple[RailRow, ...]:
    path = args.config or env.config_path
    raw = env.ports.fs.read_bytes(path)
    if raw is None:
        raise ConfigError(f"rails config {path!r} does not exist")
    return expand_rows(load_rows(raw.decode("utf-8")), {"HOME": env.home})


def _plan_artifacts(plan: DispatchPlan) -> tuple[str, ...]:
    items = [
        f"argv={' '.join(plan.argv)}",
        f"transport={plan.transport}",
        f"timeout_s={plan.timeout_s}",
    ]
    if plan.spilled:
        items.append(f"spilled-from={plan.native_transport}->{plan.transport}")
    if plan.spill is not None:
        items.append(f"prompt={plan.spill.path}")
    items.extend(f"retry={decision.rationale}" for decision in plan.retries)
    return tuple(items)


def _describe(row: RailRow) -> str:
    mark = "verified" if row.verified else "UNVERIFIED"
    return (
        f"{row.name} [{mark}] native={row.native_transport} "
        f"receipt={row.receipt_format} timeout={row.default_timeout_s}s"
    )


def _unit(args: argparse.Namespace) -> str:
    """A MARKER-SAFE unit id for a failure raised before a handler could name one.

    Falls back to :data:`PROG` when the caller's own id is the unusable thing. Rendering a
    failure envelope needs a legal marker id, so echoing the offending id back into
    :func:`agentspec.terminal.failure_line` would raise a SECOND ``ValueError`` while reporting
    the first -- the error path destroying its own output.

    HONEST REACHABILITY NOTE: with :func:`_prepare` validating the id first, no CLI invocation
    today can reach the fallback -- an unusable id becomes a :class:`ConfigError` long before
    any of the arms that call this. It is kept, and unit-tested directly in BOTH states, for
    the same reason the ``except ValueError`` net above is kept: those arms exist for paths
    nobody wired, and the one thing an error path must never do is raise. That is a deliberate
    exception to this package's no-unreachable-defensive-code rule, and it is stated here
    rather than left for a reader to discover as an untested branch.
    """
    candidate = str(getattr(args, "unit_id", None) or PROG)
    try:
        success_line(candidate)
    except ValueError:
        return PROG
    return candidate


def _ok(observation: Observation, unit_id: str) -> CommandResult:
    return CommandResult(observation=observation, terminal=success_line(unit_id))


def _envelope_error(report: RailReport) -> CommandResult:
    return CommandResult(observation=report.observation, terminal=report.terminal)


def _wire(result: CommandResult) -> dict[str, object]:
    payload: dict[str, object] = dict(result.observation.as_dict())
    payload["terminal"] = result.terminal
    return payload


def render(result: CommandResult) -> str:
    """The ONE printer, and the ONLY reason a control byte cannot reach the operator's console.

    An envelope field can legitimately carry operator-supplied text -- a ``--flag`` lands in
    ``artifacts`` as ``argv=...``, a rails.toml ``notes`` lands in the ``rails`` listing -- and
    agentrail control-strips none of it. What neutralises an OSC-8 or OSC-52 sequence is that
    the output is JSON: RFC 8259 forbids a raw C0 control inside a string, so :mod:`json`
    escapes ESC as ``\\u001b`` unconditionally.

    MEASURED, because the obvious guess is wrong: ``ensure_ascii`` is NOT what does this.
    ``json.dumps({"k": "a\\x1b]8;;x\\x07"}, ensure_ascii=False)`` still emits ``\\u001b`` --
    the flag governs NON-ASCII (>= U+0080) only. It is passed explicitly anyway for a smaller,
    honest reason: pure-ASCII output cannot mojibake through a Windows console codepage.

    So the load-bearing invariant is "the envelope is printed AS JSON", and the change that
    would break it is a plain-text renderer, not a keyword. That is what the
    ``printer-downgraded-to-plain-text`` mutation row reverts. Extracted from :func:`main`
    because an invariant living inside an inline ``json.dumps`` call cannot be mutation-gated.
    """
    return json.dumps(_wire(result), indent=2, sort_keys=True, ensure_ascii=True)


def _print(line: str) -> None:
    print(line)


def _read_stdin() -> str:
    return sys.stdin.read()
