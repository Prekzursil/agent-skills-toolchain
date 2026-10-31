"""Read-only CLI: print the MCP inventory, topology, credential map, or conflicts.

This unit performs NO state change of any kind. There is no enable/disable, no
reconnect, no config edit, and no file write anywhere in the package -- a test
(``test_the_module_exposes_no_write_capability``) asserts that mechanically over the
package source rather than trusting this docstring.

Every invocation ends in a terminal-state line (``SUCCESS:<id> ...`` /
``FAILED:<id> <reason>``) and every ``--json`` payload carries the shared observation
envelope: ``status`` / ``summary`` / ``next_actions`` / ``artifacts``, plus a root-cause
hint, a retry instruction and an explicit stop condition on the error path.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from mcpctl import envelope, render, sources
from mcpctl.matrix import Liveness, Row, build_rows, summarise
from mcpctl.scopes import PRECEDENCE
from mcpctl.topology import SourceDocs, Topology, build_topology

__all__ = ["main"]

_RENDERERS: dict[str, Callable[[tuple[Row, ...]], str]] = {
    "matrix": render.render_matrix,
    "credentials": render.render_credentials,
    "conflicts": render.render_conflicts,
}


class Loader(Protocol):
    """The injected source-loading seam (defaults to :func:`mcpctl.sources.load_sources`)."""

    def __call__(
        self, paths: sources.SourcePaths, **kwargs: object
    ) -> tuple[SourceDocs, tuple[sources.SourceProblem, ...]]: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcpctl",
        description=(
            "Read-only MCP inventory across the five on-disk configuration scopes. "
            "Never writes, never toggles, never reconnects."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="matrix",
        choices=["matrix", "topology", "credentials", "conflicts"],
        help="what to print (default: matrix)",
    )
    parser.add_argument(
        "--home", default=None, help="home directory to read the scopes from"
    )
    parser.add_argument(
        "--project",
        default=None,
        help=(
            "projects[] key to apply. Matched EXACTLY -- an ancestor directory's row is "
            "never substituted, because the host keys projects by the session's exact cwd."
        ),
    )
    parser.add_argument(
        "--json", action="store_true", help="emit the observation envelope as JSON"
    )
    return parser


def _classify(
    problems: tuple[sources.SourceProblem, ...], row_count: int
) -> envelope.Envelope:
    total = len(sources.source_paths(Path(".")).as_tuple())
    if problems and len(problems) == total:
        labels = ", ".join(p.label for p in problems)
        return envelope.error(
            f"all {total} configuration sources are unreadable ({labels})",
            root_cause=(
                "every candidate scope failed to read or parse; the first reported "
                f"reason was {problems[0].reason}"
            ),
            retry=(
                "verify --home points at the right profile, then validate each file "
                "with `python -m json.tool <path>` and re-run once"
            ),
            stop_condition=(
                "stop after ONE retry: a second identical failure across all five "
                "sources is a wrong --home or a corrupt profile, not a transient read, "
                "and retrying again cannot change the result"
            ),
        )
    if problems:
        plural = "s" if len(problems) > 1 else ""
        return envelope.warning(
            f"read {row_count} server(s); {len(problems)} source{plural} unreadable "
            f"({', '.join(p.label for p in problems)})",
            next_actions=(
                "inspect the unreadable source(s) listed above; the inventory below is "
                "complete only for the scopes that parsed",
            ),
        )
    return envelope.success(
        f"read {row_count} server(s) across the configuration scopes",
        next_actions=(
            "run `mcpctl conflicts` to see any scope disagreement",
            "run `mcpctl credentials` for the variable-name map",
        ),
    )


def _topology_payload(top: Topology) -> dict[str, object]:
    return {
        "project_key": top.project_key,
        "project_row_found": top.project_row_found,
        "enable_all_project_servers": top.enable_all_project_servers,
        "approved_mcpjson": list(top.approved_mcpjson),
        "precedence": [s.value for s in PRECEDENCE],
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    loader: Loader | None = None,
    liveness: dict[str, Liveness] | None = None,
    write: Callable[[str], None] = print,
) -> int:
    """Run the CLI. Returns 0 on success/warning and 1 on error."""
    args = _parser().parse_args(argv)
    load = sources.load_sources if loader is None else loader
    home = sources.default_home() if args.home is None else Path(args.home)

    docs, problems = load(sources.source_paths(home))
    top = build_topology(docs, project_key=args.project)
    rows = build_rows(top, liveness={} if liveness is None else liveness)
    env = _classify(problems, len(rows))
    unit = f"mcpctl-{args.command}"
    terminal = envelope.terminal_line(unit, env)

    if args.json:
        payload: dict[str, object] = {
            "envelope": env.to_dict(),
            "counts": summarise(rows),
            "rows": [r.to_dict() for r in rows],
            "problems": [
                {"label": p.label, "path": p.path, "reason": p.reason} for p in problems
            ],
            "terminal": terminal,
        }
        payload.update(_topology_payload(top))
        write(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if env.status == "error" else 0

    if args.command == "topology":
        write(render.render_topology(top))
    else:
        write(_RENDERERS[args.command](rows))
    write("")
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
