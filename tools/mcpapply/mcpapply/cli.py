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
from datetime import datetime, timezone
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
from mcpapply.guard import make_guard
from mcpapply.impact import Cost, Impact, Regime, TokenBasis, preview, render_impact
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
            "projects[] key to write. Matched EXACTLY -- an ancestor row is never "
            "substituted, because the host keys projects by the session's exact cwd. "
            "Without it, a disable falls back to the root list, which does NOT prevent "
            "the server process from spawning."
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
    write: Callable[[str], None] = print,
) -> int:
    """Run the CLI. Returns 0 on success/warning, 1 on error."""
    args = _parser().parse_args(argv)
    load = sources.load_sources if loader is None else loader
    file_store: FileStore = RealFileStore() if store is None else store
    clock = datetime.now(timezone.utc) if now is None else now
    home = sources.default_home() if args.home is None else Path(args.home)
    paths = sources.source_paths(home)

    docs, problems = load(paths)
    top = build_topology(docs, project_key=args.project)

    if args.command == "gui":
        return _gui_command(
            args,
            paths=paths,
            docs=docs,
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

    plan = build_plan([change], project_key=args.project)
    costs = _costs_from(args, file_store)
    impact = preview(plan, costs, regime=Regime(_regime_name(args.tool_search)))
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
    docs: SourceDocs,
    store: FileStore,
    clock: datetime,
    runner: Callable[[Sequence[str]], str] | None,
    serve_fn: Callable[[gui.GuiPorts, int], int] | None,
    liveness: Mapping[str, Liveness] | None,
    write: Callable[[str], None],
) -> int:
    costs = _costs_from(args, store)
    regime = Regime(_regime_name(args.tool_search))
    live = {} if liveness is None else dict(liveness)

    def rows() -> tuple[Row, ...]:
        top = build_topology(docs, project_key=args.project)
        return build_rows(top, liveness=live)

    def plan_for(intent: str, server_name: str) -> Plan:
        top = build_topology(docs, project_key=args.project)
        if intent not in _MUTATORS:
            raise ValueError(f"unknown intent {intent!r}")
        change = build_change(intent, top, server_name, args.spec, args.scope)
        return build_plan([change], project_key=args.project)

    def do_apply(plan: Plan, confirmed: bool) -> ApplyResult:
        return apply_plan(
            plan,
            paths=paths,
            store=store,
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
        plan_for=plan_for,
        impact_for=lambda plan: preview(plan, costs, regime=regime),
        apply_plan=do_apply,
        token=gui.new_token(),
    )
    shell = serve_fn or (lambda p, n: _run_gui(p, port=n, write=write))
    return shell(ports, args.port)
