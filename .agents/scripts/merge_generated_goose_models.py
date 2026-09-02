#!/usr/bin/env python3
"""Merge the models registry into Goose's ``custom_providers/`` directory.

Goose 1.x loads every ``*.json`` under ``%APPDATA%\\Block\\goose\\config\\custom_providers``
(``~/.config/goose/custom_providers`` elsewhere) as a declarative provider
(``DeclarativeProviderConfig``). This renderer writes one ``<endpoint-id>.json``
per endpoint the ``goose`` runtime takes natively and manages the directory as a
file set: it writes and deletes only files whose text carries the
``managed-by: .agents/models.json <hash>`` marker (rendered into ``description``),
so a hand-written ``goose-cursor-proxy.json`` is never touched. A rendered name
that collides with an unmarked file is refused rather than overwritten.

Fields rendered, all documented by Goose: ``name``, ``engine``, ``display_name``,
``description``, ``api_key_env`` (an environment-variable NAME, omitted when the
endpoint has no auth), ``base_url`` (the host, without the ``/v1`` Goose adds
through ``base_path``), ``base_path``, ``models[{name, context_limit}]``,
``supports_streaming`` and ``requires_auth``. An endpoint without registry
models renders an empty ``models`` list, which makes Goose discover
``/v1/models`` itself.

``written`` and ``deleted`` in the ``SUCCESS:`` line count the changes the run
applies (``--write``) or would apply (dry run, ``--check``); ``preserved`` counts
the unmarked files left alone. ``--smoke`` runs ``goose info`` after a write and
restores every backup when it fails.
"""

from __future__ import annotations

import json
import os
import pathlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import models_control_plane as models
import models_materialize_common as common


NAME = "goose-models-merge"
RUNTIME = "goose"
DEFAULT_LIVE_DIR = r"%APPDATA%\Block\goose\config\custom_providers"
ENGINE = "openai"
BASE_PATH = "v1/chat/completions"
SMOKE_COMMAND = ("goose", "info")


class GooseMergeError(ValueError):
    """Raised when the live ``custom_providers/`` directory cannot be merged safely."""


@dataclass
class Plan:
    """The rendered file set and how it differs from the live directory."""

    rendered: dict[str, str]
    model_count: int
    writes: list[str] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)

    @property
    def drift(self) -> list[str]:
        return self.writes + self.deletes


def render_provider(
    endpoint_id: str,
    endpoint: Mapping[str, Any],
    selected: Mapping[str, Mapping[str, Any]],
    marker: str,
) -> dict[str, Any]:
    """One declarative provider object for an endpoint and the models it serves."""
    auth = endpoint["auth"]
    payload: dict[str, Any] = {
        "name": endpoint_id,
        "engine": ENGINE,
        "display_name": endpoint["label"],
        "description": f"{endpoint['label']} - {marker}",
    }
    if auth is not None:
        payload["api_key_env"] = common.env_reference(auth["env"], "goose")
    payload["base_url"] = common.strip_v1(endpoint["baseUrl"])
    payload["base_path"] = BASE_PATH
    payload["models"] = [
        {"name": model["remoteId"], "context_limit": model["context"]}
        for model in selected.values()
        if model["endpoint"] == endpoint_id
    ]
    payload["supports_streaming"] = True
    payload["requires_auth"] = auth is not None
    return payload


def render_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_files(config: Mapping[str, Any]) -> tuple[dict[str, str], int]:
    """``<endpoint-id>.json`` -> content for every endpoint the runtime takes."""
    endpoints = models.select_target_endpoints(config, RUNTIME)
    selected = models.select_target_models(config, RUNTIME)
    marker = common.managed_marker(config)
    rendered = {
        f"{endpoint_id}.json": render_json(
            render_provider(endpoint_id, endpoint, selected, marker)
        )
        for endpoint_id, endpoint in endpoints.items()
    }
    return rendered, len(selected)


def scan_live(live_dir: pathlib.Path) -> tuple[dict[str, str], set[str]]:
    """Existing ``*.json`` files as name -> text, plus the names carrying the marker."""
    existing: dict[str, str] = {}
    marked: set[str] = set()
    if not live_dir.is_dir():
        return existing, marked
    for path in sorted(live_dir.glob("*.json")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        existing[path.name] = text
        if common.MANAGED_MARKER_RE.search(text) is not None:
            marked.add(path.name)
    return existing, marked


def plan(config: Mapping[str, Any], live_dir: pathlib.Path) -> Plan:
    """Decide which files to write and delete; refuse to overwrite unmarked ones."""
    rendered, model_count = render_files(config)
    existing, marked = scan_live(live_dir)
    for name in sorted(rendered):
        if name in existing and name not in marked:
            raise GooseMergeError(
                f"{live_dir / name} exists without the managed marker; "
                "refusing to overwrite an unmarked provider file"
            )
    return Plan(
        rendered=rendered,
        model_count=model_count,
        writes=[
            name for name in sorted(rendered) if existing.get(name) != rendered[name]
        ],
        deletes=[name for name in sorted(marked) if name not in rendered],
        preserved=[name for name in sorted(existing) if name not in marked],
    )


def apply(
    merge_plan: Plan, live_dir: pathlib.Path, *, backup: bool
) -> tuple[list[pathlib.Path], dict[pathlib.Path, pathlib.Path | None]]:
    """Write and delete the planned files; return the touched paths and their backups."""
    written: list[pathlib.Path] = []
    backups: dict[pathlib.Path, pathlib.Path | None] = {}
    for name in merge_plan.writes:
        path = live_dir / name
        backups[path] = common.write_with_backup(
            path, merge_plan.rendered[name], backup=backup
        )
        written.append(path)
    for name in merge_plan.deletes:
        path = live_dir / name
        backups[path] = common.remove_with_backup(path, backup=backup)
        written.append(path)
    return written, backups


def main(argv: list[str] | None = None, *, run: common.Runner | None = None) -> int:
    parser = common.build_parser(NAME, default_live=DEFAULT_LIVE_DIR)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help=f"after --write, run `{' '.join(SMOKE_COMMAND)}` and roll back when it fails",
    )
    args = parser.parse_args(argv)
    live_dir = common.live_path(args)
    try:
        config, _ = common.load_inputs(args)
        merge_plan = plan(config, live_dir)
        common.assert_no_secret_values(
            "".join(merge_plan.rendered.values()),
            os.environ,
            models.credential_names(config),
        )
    except (
        models.ModelsRegistryError,
        GooseMergeError,
        common.SecretValueError,
    ) as error:
        return common.fail(NAME, str(error))
    if not args.quiet:
        common.print_routing_report(models.routing_report(config, RUNTIME))
    counts: dict[str, object] = {
        "endpoints": len(merge_plan.rendered),
        "models": merge_plan.model_count,
        "written": len(merge_plan.writes),
        "deleted": len(merge_plan.deletes),
        "preserved": len(merge_plan.preserved),
    }
    if args.check:
        if merge_plan.drift:
            print(f"FAILED:{NAME} check drift={','.join(merge_plan.drift)}")
            return 1
        return common.print_success(NAME, **counts, write=False)
    if not args.write:
        return common.print_success(NAME, **counts, write=False)
    written, backups = apply(merge_plan, live_dir, backup=not args.no_backup)
    if args.smoke:
        if not common.smoke_and_rollback(SMOKE_COMMAND, written, backups, run=run):
            return common.fail(
                NAME,
                f"smoke '{' '.join(SMOKE_COMMAND)}' failed; restored "
                f"{len(written)} path(s) under {live_dir}",
            )
        return common.print_success(NAME, **counts, write=True, smoke=True)
    return common.print_success(NAME, **counts, write=True)


if __name__ == "__main__":
    raise SystemExit(main())
