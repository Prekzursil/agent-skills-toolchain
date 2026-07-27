"""The mutation CLI. DRY RUN BY DEFAULT on every path that can change anything.

``mcpapply disable foo`` prints the exact diff and writes nothing. Only
``mcpapply disable foo --apply`` writes, and even then it backs the file up first,
refuses if a host session is running, refuses if the file moved under it, and prints
the restore command.

Reading is entirely delegated to :mod:`mcpctl` -- the five scopes, their measured
precedence, the object-shaped ``deniedMcpServers``, the exact-cwd ``projects`` row and
the credential-name-only redaction all come from there. This package adds only the
inverse (which scope to WRITE), the writer, the impact preview, the live channel and
the GUI. Every seam a test needs is injected: the loader, the file store, the clock,
the process guard and the server runner.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

from mcpctl import envelope, sources
from mcpctl.matrix import Liveness, Row, build_rows
from mcpctl.safety import safe
from mcpctl.scopes import ScopeId
from mcpctl.topology import SourceDocs, build_topology

from mcpapply import server as gui
from mcpapply.apply import (
    ApplyResult,
    FileStore,
    RealFileStore,
    apply_plan,
    render_result,
)
from mcpapply.backup import Clock, fixed_clock, make_clock
from mcpapply.guard import make_guard
from mcpapply.impact import (
    TOOL_BLOCK_OVERHEAD_TOKENS,
    Cost,
    Impact,
    Regime,
    TokenBasis,
    preview,
    render_impact,
)
from mcpapply.live import (
    INTENT_OPS,
    LiveClient,
    LiveOutcome,
    default_live_client,
    render_live,
    run_live,
)
from mcpapply.plan import (
    Change,
    Plan,
    build_plan,
    plan_add,
    plan_disable,
    plan_edit,
    plan_enable,
    plan_reconnect,
    plan_remove,
    render_plan,
)

__all__ = ["build_change", "load_costs", "main"]

_MUTATORS = ("enable", "disable", "add", "remove", "edit", "reconnect")

#: Verbs that have no on-disk representation at all -- they exist only as a control
#: frame. Running one without ``--live`` used to print ``SUCCESS: 0 file(s) written``,
#: which reads as "done" for an operation that never happened.
_LIVE_ONLY_COMMANDS = ("reconnect",)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcpapply",
        description=(
            "Mutate MCP configuration across the five on-disk scopes, preview the "
            "token/RAM impact, drive the live control channel, or open the localhost "
            "GUI. DRY RUN BY DEFAULT: nothing is written without --apply."
        ),
    )
    parser.add_argument("command", choices=[*_MUTATORS, "gui"])
    parser.add_argument("server", nargs="?", default="", help="server name")
    parser.add_argument(
        "--home", default=None, help="home directory holding the scopes"
    )
    parser.add_argument(
        "--project",
        default=None,
        help=(
            "projects[] key to write. Separators are normalised to forward slashes "
            "(the host's own spelling), but the key is otherwise matched EXACTLY -- an "
            "ancestor row is never substituted, because the host keys projects by the "
            "session's exact cwd. Without it, a disable falls back to the root list, "
            "which does NOT prevent the server process from spawning."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually write. Without this flag nothing on disk changes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="accept the race and write while a host session is running",
    )
    parser.add_argument(
        "--scope",
        default=ScopeId.CLAUDE_USER.value,
        choices=[ScopeId.CLAUDE_USER.value, ScopeId.MCP_JSON.value],
        help="definition scope for `add` (default: claude-user)",
    )
    parser.add_argument("--spec", default="", help="JSON server spec for add/edit")
    parser.add_argument(
        "--costs",
        default=None,
        help="JSON file of per-server measured costs for the impact preview",
    )
    parser.add_argument(
        "--tool-search",
        default=None,
        help="ENABLE_TOOL_SEARCH value, so the token figure names its regime",
    )
    parser.add_argument(
        "--fleet-size",
        type=int,
        default=0,
        help=(
            "how many tool-bearing servers are loaded now. Only used to decide whether "
            f"the one-off {TOOL_BLOCK_OVERHEAD_TOKENS}-token tool block is reclaimed "
            "too (it is, and only, when the plan removes the last of them)."
        ),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "carry the change out over the stream-json control channel instead of "
            "writing config. REQUIRED for `reconnect`, which has no on-disk form. "
            "Refused outright when the recorded evidence for that (scope, op) pair "
            "says it does not work."
        ),
    )
    parser.add_argument(
        "--live-cwd",
        default=None,
        help=(
            "cwd for the control session (default: this process's). mcp_toggle "
            "persists its write to projects[<the control session's cwd>], so the wrong "
            "value lands the change under the wrong project row."
        ),
    )
    parser.add_argument("--port", type=int, default=0, help="GUI port (0 = ephemeral)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    return parser


def build_change(
    command: str, top: object, name: str, spec_text: str, scope: str
) -> Change:
    """Dispatch one CLI verb to its planner. Raises ``ValueError`` on a bad spec."""
    from mcpctl.topology import Topology

    topology = cast("Topology", top)
    if command in ("add", "edit"):
        try:
            parsed = json.loads(spec_text or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"--spec is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("--spec must be a JSON object")
        spec = cast("Mapping[str, object]", parsed)
        if command == "add":
            return plan_add(topology, name, spec, scope=ScopeId(scope))
        return plan_edit(topology, name, spec)
    return {
        "enable": plan_enable,
        "disable": plan_disable,
        "remove": plan_remove,
        "reconnect": plan_reconnect,
    }[command](topology, name)


def load_costs(text: str) -> dict[str, Cost]:
    """Parse a measured-cost file. An unknown/absent field stays ``None``."""
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("the costs file must be a JSON object keyed by server name")
    out: dict[str, Cost] = {}
    for name, entry in cast("Mapping[str, object]", raw).items():
        record = cast("Mapping[str, object]", entry) if isinstance(entry, dict) else {}
        basis = record.get("token_basis")
        out[safe(str(name))] = Cost(
            tool_count=_int(record.get("tool_count")),
            token_cost=_int(record.get("token_cost")),
            token_basis=TokenBasis(basis)
            if isinstance(basis, str) and basis in {b.value for b in TokenBasis}
            else TokenBasis.NOT_MEASURED,
            commit_bytes=_int(record.get("commit_bytes")),
            proc_count=_int(record.get("proc_count")),
            remote=record.get("remote") is True,
            measured_at=str(record["measured_at"]) if "measured_at" in record else None,
        )
    return out


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class _Server(Protocol):
    """The subset of ``ThreadingHTTPServer`` the GUI shell drives.

    ``server_address`` is declared as a read-only PROPERTY, not an attribute: a
    mutable protocol attribute is invariant, and ``ThreadingHTTPServer`` types its
    address as ``_AfInetAddress | _AfInet6Address``, which is not assignable to a
    mutable ``object`` slot. Read-only makes it covariant, which is all this shell
    needs -- it prints the bound address and never sets it.
    """

    @property
    def server_address(self) -> object: ...

    def serve_forever(self) -> None: ...

    def server_close(self) -> None: ...


def _run_gui(
    ports: gui.GuiPorts,
    *,
    port: int,
    write: Callable[[str], None],
    make_server: Callable[[gui.GuiPorts, int], _Server] = lambda p, n: gui.serve(
        p, port=n
    ),
) -> int:
    """Start the GUI and block until Ctrl-C.

    ``make_server`` is injected so this shell is covered without a test having to
    assert that a blocking call blocks; the real :func:`mcpapply.server.serve` is
    exercised for real (over a live loopback socket) in ``tests/test_server.py``.
    """
    httpd = make_server(ports, port)
    address = cast("tuple[object, object]", httpd.server_address)
    write(
        f"mcpapply GUI on http://{address[0]!s}:{address[1]!s}/  "
        "(token is in the page; Ctrl-C to stop)"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        write("stopped")
    finally:
        httpd.server_close()
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    loader: Callable[
        [sources.SourcePaths], tuple[SourceDocs, tuple[sources.SourceProblem, ...]]
    ]
    | None = None,
    store: FileStore | None = None,
    now: datetime | None = None,
    runner: Callable[[Sequence[str]], str] | None = None,
    serve_fn: Callable[[gui.GuiPorts, int], int] | None = None,
    liveness: Mapping[str, Liveness] | None = None,
    client_for: Callable[[str], LiveClient] | None = None,
    write: Callable[[str], None] = print,
) -> int:
    """Run the CLI. Returns 0 on success/warning, 1 on error."""
    args = _parser().parse_args(argv)
    load = sources.load_sources if loader is None else loader
    file_store: FileStore = RealFileStore() if store is None else store
    # A CLOCK, not an instant. The GUI runs for hours and derives a backup filename
    # per write; one frozen datetime meant every apply after the first overwrote the
    # sidecar the previous one told the operator to restore from.
    clock: Clock = make_clock() if now is None else fixed_clock(now)
    home = sources.default_home() if args.home is None else Path(args.home)
    paths = sources.source_paths(home)
    project_key = _project_key(args.project)

    docs, problems = load(paths)

    if args.command == "gui":
        return _gui_command(
            args,
            paths=paths,
            load=load,
            project_key=project_key,
            store=file_store,
            clock=clock,
            runner=runner,
            serve_fn=serve_fn,
            liveness=liveness,
            write=write,
        )

    if not args.server:
        return _fail(
            write,
            args.command,
            f"`{args.command}` needs a server name",
            root_cause="the positional SERVER argument was empty",
            retry=f"re-run as `mcpapply {args.command} <server>`",
            stop_condition="stop immediately; this is a usage error, not a transient failure",
        )

    top = build_topology(docs, project_key=project_key)
    if args.live or args.command in _LIVE_ONLY_COMMANDS:
        return _live_command(args, top, client_for=client_for, write=write)

    try:
        change = build_change(args.command, top, args.server, args.spec, args.scope)
    except ValueError as exc:
        return _fail(
            write,
            args.command,
            safe(str(exc)),
            root_cause="the requested change could not be planned from the given arguments",
            retry="correct the argument named above and re-run once",
            stop_condition="stop after ONE retry: a repeated parse failure is a bad "
            "argument, not a transient condition",
        )

    plan = build_plan([change], project_key=project_key)
    try:
        costs = _costs_from(args, file_store)
    except (OSError, ValueError) as exc:
        return _fail(
            write,
            args.command,
            safe(f"--costs could not be read: {exc}"),
            root_cause="the measured-cost file named by --costs is missing or is not a "
            "JSON object keyed by server name",
            retry="correct or drop --costs and re-run once",
            stop_condition="stop after ONE retry: a missing or malformed file is a "
            "standing condition, not a transient one",
        )
    impact = preview(
        plan,
        costs,
        regime=Regime(_regime_name(args.tool_search)),
        fleet_size=args.fleet_size,
    )
    result = apply_plan(
        plan,
        paths=paths,
        store=file_store,
        now=clock,
        apply=args.apply,
        guard=make_guard(
            runner=runner,
            force=args.force,
            touches_user_scope=_touches_user_scope(plan),
        ),
    )
    return _report(args, plan, impact, result, problems, write)


def _project_key(raw: str | None) -> str | None:
    """Normalise a ``--project`` value to the host's own key spelling.

    The host keys ``projects`` by an absolute path with FORWARD slashes. Passing a
    Windows-native path straight through created a brand-new row nobody reads: the
    requested disable silently did not land, ``~/.claude.json`` gained a junk row that
    accumulated on every repeat, and the terminal line still said SUCCESS.

    This is separator normalisation ONLY -- :func:`mcpctl.sources.project_key_for` does
    no ancestor walk, and neither does this, because substituting a parent row for a
    missing one is exactly the mis-targeting ``--help`` warns about.
    """
    return None if raw is None else sources.project_key_for(Path(raw))


def _live_command(
    args: argparse.Namespace,
    top: object,
    *,
    client_for: Callable[[str], LiveClient] | None,
    write: Callable[[str], None],
) -> int:
    """Route one verb through the control channel instead of the config writer."""
    from mcpctl.topology import Topology

    if args.command not in INTENT_OPS:
        return _fail(
            write,
            args.command,
            f"`{args.command}` has no control-channel form",
            root_cause=f"only {', '.join(sorted(INTENT_OPS))} map to a control frame; "
            f"`{args.command}` is a configuration-document mutation",
            retry=f"re-run `mcpapply {args.command} {args.server}` without --live",
            stop_condition="stop immediately; this is a usage error, not a transient failure",
        )
    if args.command in _LIVE_ONLY_COMMANDS and not args.live:
        return _fail(
            write,
            args.command,
            f"`{args.command}` writes no configuration and needs --live",
            root_cause=f"`{args.command}` exists only as a control frame, so without "
            "--live it would have reported success while doing nothing at all",
            retry=f"re-run as `mcpapply {args.command} {args.server} --live --apply`",
            stop_condition="stop immediately; this is a usage error, not a transient failure",
        )
    topology = cast("Topology", top)
    scopes = topology.scopes_of(safe(args.server))
    scope = scopes[0] if scopes else ScopeId(args.scope)
    cwd = str(Path.cwd()) if args.live_cwd is None else args.live_cwd
    build = client_for or (lambda where: default_live_client(cwd=where))
    outcome = run_live(
        intent=args.command,
        server=safe(args.server),
        scope=scope,
        apply=args.apply,
        client_for=lambda: build(cwd),
    )
    return _report_live(args, outcome, write)


def _classify_live(outcome: LiveOutcome) -> envelope.Envelope:
    if outcome.refusal:
        return envelope.error(
            f"refused: {outcome.refusal}",
            root_cause="the recorded per-scope evidence marks this control operation "
            "as not working; offering it anyway would be an overclaim",
            retry="use the configuration path instead (`mcpapply disable/enable` "
            "without --live), which is written and verified on disk",
            stop_condition="stop immediately: this is a standing evidence verdict, not "
            "a transient failure",
        )
    if outcome.dry_run:
        return envelope.success(
            "DRY RUN: no control session started, zero frames sent",
            next_actions=("re-run with --apply to send it",),
        )
    return envelope.success(
        f"{len(outcome.sent)} control frame(s) sent",
        next_actions=(
            "mcp_toggle PERSISTS to ~/.claude.json; re-read the matrix to confirm",
        ),
    )


def _report_live(
    args: argparse.Namespace, outcome: LiveOutcome, write: Callable[[str], None]
) -> int:
    env = _classify_live(outcome)
    terminal = envelope.terminal_line(f"mcpapply-{args.command}", env)
    if args.json:
        write(
            json.dumps(
                {
                    "envelope": env.to_dict(),
                    "live": outcome.to_dict(),
                    "terminal": terminal,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if env.status == "error" else 0
    write(render_live(outcome))
    if env.status == "error":
        write(f"root cause: {env.root_cause}")
        write(f"retry: {env.retry}")
        write(f"stop: {env.stop_condition}")
    for action in env.next_actions:
        write(f"next: {action}")
    write(terminal)
    return 1 if env.status == "error" else 0


def _regime_name(tool_search: str | None) -> str:
    from mcpapply.impact import regime_from_env

    return regime_from_env(tool_search).value


def _costs_from(args: argparse.Namespace, store: FileStore) -> dict[str, Cost]:
    if args.costs is None:
        return {}
    return load_costs(store.read_text(Path(args.costs)))


def _touches_user_scope(plan: Plan) -> bool:
    return any(
        edit.scope in (ScopeId.CLAUDE_USER, ScopeId.CLAUDE_USER_DISABLED)
        for change in plan.changes
        for edit in change.edits
    )


def _fail(
    write: Callable[[str], None],
    unit: str,
    summary: str,
    *,
    root_cause: str,
    retry: str,
    stop_condition: str,
) -> int:
    env = envelope.error(
        summary, root_cause=root_cause, retry=retry, stop_condition=stop_condition
    )
    write(f"root cause: {env.root_cause}")
    write(f"retry: {env.retry}")
    write(f"stop: {env.stop_condition}")
    write(envelope.terminal_line(f"mcpapply-{unit}", env))
    return 1


def _classify(result: ApplyResult, dry_run_requested: bool) -> envelope.Envelope:
    if result.blocked:
        return envelope.error(
            f"refused to write: {result.blocked}",
            root_cause="a fail-closed precondition rejected the write",
            retry="resolve the condition above (usually: close every Claude Code "
            "window) and re-run with --apply",
            stop_condition="stop after ONE retry: a second identical refusal is a "
            "standing condition, not a transient one",
        )
    if result.problems and not result.dry_run and not result.written:
        # A refusal that wrote NOTHING is a failure, not a warning. The stale-write
        # refusal -- the entire justification for the deliberate no-lock design -- and
        # an unparseable target both land here, and both used to print SUCCESS with
        # exit 0, so `mcpapply disable X --apply && echo landed` printed "landed".
        return envelope.error(
            f"{len(result.problems)} problem(s); NOTHING was written -- the requested "
            "change did not happen",
            root_cause="every target was refused before the write (the file moved "
            "under the preview, or it could not be parsed)",
            retry="re-run with --apply so the plan is rebuilt against the current "
            "contents",
            stop_condition="stop after ONE retry: a second identical refusal is a "
            "standing condition, not a race",
        )
    if result.problems:
        return envelope.warning(
            f"{len(result.problems)} problem(s); {len(result.written)} file(s) written",
            next_actions=("inspect the problems listed above before re-running",),
        )
    if dry_run_requested:
        return envelope.success(
            "DRY RUN: nothing written",
            next_actions=("re-run with --apply to commit this exact diff",),
        )
    return envelope.success(
        f"{len(result.written)} file(s) written",
        next_actions=("the restore command above puts every file back",),
        artifacts=tuple(b.backup for b in result.backups),
    )


def _report(
    args: argparse.Namespace,
    plan: Plan,
    impact: Impact,
    result: ApplyResult,
    problems: tuple[sources.SourceProblem, ...],
    write: Callable[[str], None],
) -> int:
    env = _classify(result, result.dry_run and not result.blocked)
    terminal = envelope.terminal_line(f"mcpapply-{args.command}", env)
    if args.json:
        write(
            json.dumps(
                {
                    "envelope": env.to_dict(),
                    "plan": plan.to_dict(),
                    "impact": impact.to_dict(),
                    "result": result.to_dict(),
                    "problems": [
                        {"label": p.label, "path": p.path, "reason": p.reason}
                        for p in problems
                    ],
                    "terminal": terminal,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if env.status == "error" else 0
    write(render_plan(plan))
    write("")
    write(render_impact(impact))
    write("")
    write(render_result(result))
    for problem in problems:
        write(f"UNREADABLE {problem.label} ({problem.path}): {problem.reason}")
    if env.status == "error":
        write(f"root cause: {env.root_cause}")
        write(f"retry: {env.retry}")
        write(f"stop: {env.stop_condition}")
    for action in env.next_actions:
        write(f"next: {action}")
    write(terminal)
    return 1 if env.status == "error" else 0


def _gui_command(
    args: argparse.Namespace,
    *,
    paths: sources.SourcePaths,
    load: Callable[
        [sources.SourcePaths], tuple[SourceDocs, tuple[sources.SourceProblem, ...]]
    ],
    project_key: str | None,
    store: FileStore,
    clock: Clock,
    runner: Callable[[Sequence[str]], str] | None,
    serve_fn: Callable[[gui.GuiPorts, int], int] | None,
    liveness: Mapping[str, Liveness] | None,
    write: Callable[[str], None],
) -> int:
    """Serve the GUI, RE-READING the configuration on every request.

    The documents are deliberately NOT captured at launch. A snapshot made the GUI
    unable to undo its own change -- after disabling a server it planned against a
    world where that had never happened, wrote nothing, and went on rendering the
    server as enabled -- and it also silently hid a file that became unparseable while
    the window was open. Re-reading costs one file read per request on a loopback
    socket, which is nothing next to being wrong.
    """
    costs = _costs_from(args, store)
    regime = Regime(_regime_name(args.tool_search))
    live = {} if liveness is None else dict(liveness)

    def current() -> tuple[object, tuple[sources.SourceProblem, ...]]:
        docs, problems = load(paths)
        return build_topology(docs, project_key=project_key), problems

    def rows() -> tuple[Row, ...]:
        from mcpctl.topology import Topology

        top, _ = current()
        return build_rows(cast("Topology", top), liveness=live)

    def problems() -> tuple[str, ...]:
        _, found = current()
        return tuple(f"{p.label} ({p.path}): {p.reason}" for p in found)

    def plan_for(intent: str, server_name: str) -> Plan:
        if intent not in gui.GUI_INTENTS:
            raise ValueError(
                f"intent {intent!r} is not offered by the GUI; the GUI offers "
                f"{', '.join(gui.GUI_INTENTS)}. Definition edits need a --spec this "
                "form cannot carry, and `remove`/`reconnect` are CLI-only."
            )
        top, _ = current()
        change = build_change(intent, top, server_name, args.spec, args.scope)
        return build_plan([change], project_key=project_key)

    def do_apply(plan: Plan, confirmed: bool) -> ApplyResult:
        return apply_plan(
            plan,
            paths=paths,
            store=store,
            # The CALLABLE, so every apply in this long-lived process derives its own
            # backup filename instead of clobbering the previous sidecar.
            now=clock,
            apply=confirmed,
            guard=make_guard(
                runner=runner,
                force=args.force,
                touches_user_scope=_touches_user_scope(plan),
            ),
        )

    ports = gui.GuiPorts(
        rows=rows,
        problems=problems,
        plan_for=plan_for,
        impact_for=lambda plan: preview(
            plan, costs, regime=regime, fleet_size=args.fleet_size
        ),
        apply_plan=do_apply,
        token=gui.new_token(),
    )
    shell = serve_fn or (lambda p, n: _run_gui(p, port=n, write=write))
    return shell(ports, args.port)
