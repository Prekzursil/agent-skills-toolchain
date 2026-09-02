#!/usr/bin/env python3
"""Merge the models registry into Grok Build's ``config.toml`` as ``[model."<id>"]`` blocks.

Grok CLI (Grok Build) reads ``%USERPROFILE%\\.grok\\config.toml`` (``$GROK_HOME``
overrides the directory) and takes custom models from ``[model."<id>"]`` tables with
``model``, ``base_url``, ``env_key`` (string or array of environment-variable
NAMES), ``api_backend`` (``chat_completions`` | ``responses`` | ``messages``) and
``context_window``; ``[endpoints] models_base_url`` makes it fetch ``{base}/models``
and inherit ``base_url`` into partial overrides. This renderer owns one block per
model the ``grok`` runtime takes natively, each introduced by a
``# managed-by: .agents/models.json <hash>`` comment as its first line. Everything
else - ``[models]``, an unmanaged ``[endpoints]``, ``[model.*]`` blocks without the
marker, every other table and the preamble - is carried over byte-identical, and an
unmanaged live block wins over the registry when both name the same model id.
Managed blocks whose id left the selection are removed.

The ``[endpoints]`` block for the Cursor bridge is rendered only while that
endpoint's ``wire.completions`` carries a ``probed`` receipt (D9); the seed's
``declared`` never renders it and a hand-declared ``native`` is not a receipt.
``api_key =`` is never rendered: credentials travel as ``env_key`` names. The live
text must parse with ``tomllib`` before it is merged into and the merged text must
parse before it is reported, written or checked. ``--smoke`` runs ``grok inspect``
with ``GROK_HOME`` at the live file's directory and restores the backup when it
fails.
"""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import models_control_plane as models
import models_materialize_common as common


NAME = "grok-models-merge"
RUNTIME = "grok"
DEFAULT_LIVE_CONFIG = r"%USERPROFILE%\.grok\config.toml"
MODEL_HEADER_RE = re.compile(r'^\[model\."(?P<id>[^"]+)"\]$')
# A table header may be indented and carry a trailing comment (both legal TOML);
# recognising them keeps such a hand-written block from being glued to the managed
# block above it and replaced or removed together with it.
BLOCK_START_RE = re.compile(
    r"^(?P<marker># managed-by: \.agents/models\.json [0-9a-f]{16}[ \t]*\n)?"
    r"[ \t]*\[(?P<header>[^\n]+?)\][ \t]*(?:#[^\n]*)?$",
    re.MULTILINE,
)
ENDPOINTS_HEADER = "endpoints"
# Wire keys in preference order with the api_backend value Grok expects for each.
API_BACKENDS = (
    ("responses", "responses"),
    ("completions", "chat_completions"),
    ("messages", "messages"),
)
DEFAULT_API_BACKEND = "chat_completions"
READY_STATES = frozenset({"native", "probed"})
SMOKE_COMMAND = ("grok", "inspect")


class GrokMergeError(ValueError):
    """Raised when the merged config text cannot be produced safely."""


@dataclass
class Block:
    """One live TOML region: the preamble (``header`` None) or a table with its body."""

    header: str | None
    text: str
    managed: bool = False
    model_id: str | None = None


@dataclass
class Merge:
    """The merged text plus what happened to the managed regions."""

    text: str
    rendered: dict[str, str]
    endpoints_block: str | None
    removed: list[str] = field(default_factory=list)
    live_only: list[str] = field(default_factory=list)

    @property
    def managed_text(self) -> str:
        return "".join(self.rendered.values()) + (self.endpoints_block or "")


def toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def split_blocks(content: str) -> list[Block]:
    """Split on table headers; a marker comment directly above a header belongs to it."""
    matches = list(BLOCK_START_RE.finditer(content))
    if not matches:
        return [Block(None, content)] if content else []
    blocks: list[Block] = []
    preamble = content[: matches[0].start()]
    if preamble:
        blocks.append(Block(None, preamble))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        header = match.group("header")
        model = MODEL_HEADER_RE.match(f"[{header}]")
        blocks.append(
            Block(
                header,
                content[match.start() : end],
                managed=match.group("marker") is not None,
                model_id=None if model is None else model.group("id"),
            )
        )
    return blocks


def api_backend(config: Mapping[str, Any], model_id: str) -> str:
    """The best wire the model has natively or probed, in Grok's vocabulary."""
    wire = models.effective_capabilities(config, model_id)["wire"]
    for key, backend in API_BACKENDS:
        if models.lattice_state(wire[key]) in READY_STATES:
            return backend
    return DEFAULT_API_BACKEND


def render_model_block(
    config: Mapping[str, Any], model_id: str, model: Mapping[str, Any], marker: str
) -> str:
    endpoint = config["endpoints"][model["endpoint"]]
    lines = [
        f"# {marker}",
        f"[model.{toml_string(model_id)}]",
        f"base_url = {toml_string(endpoint['baseUrl'])}",
        f"model = {toml_string(model['remoteId'])}",
    ]
    auth = endpoint["auth"]
    if auth is not None:
        names = ", ".join(toml_string(name) for name in (auth["env"], *auth["altEnv"]))
        lines.append(f"env_key = [{names}]")
    lines.append(f"api_backend = {toml_string(api_backend(config, model_id))}")
    lines.append(f"context_window = {int(model['context'])}")
    return "\n".join(lines) + "\n"


def render_endpoints_block(config: Mapping[str, Any], marker: str) -> str | None:
    """``[endpoints] models_base_url`` for the Cursor bridge once its wire is probed.

    The gate is the probe receipt itself (``{"state": "probed", ...}``), not the
    lattice rank: a ``native`` written by hand proves nothing about ``/v1/models``.
    """
    bridge = models.select_target_endpoints(config, RUNTIME).get(
        models.CURSOR_BRIDGE_ENDPOINT
    )
    if (
        bridge is None
        or models.lattice_state(bridge["wire"]["completions"]) != "probed"
    ):
        return None
    return (
        f"# {marker}\n[{ENDPOINTS_HEADER}]\n"
        f"models_base_url = {toml_string(bridge['baseUrl'])}\n"
    )


def render_blocks(config: Mapping[str, Any]) -> tuple[dict[str, str], str | None]:
    marker = common.managed_marker(config)
    rendered = {
        model_id: render_model_block(config, model_id, model, marker)
        for model_id, model in models.select_target_models(config, RUNTIME).items()
    }
    return rendered, render_endpoints_block(config, marker)


def _replace(rendered: str, original: str) -> str:
    """The rendered block keeping the blank lines that trailed the block it replaces."""
    suffix = original[len(original.rstrip("\n")) :]
    return rendered.rstrip("\n") + (suffix or "\n")


def _append(output: str, text: str) -> str:
    if output and not output.endswith("\n\n"):
        output += "\n" if output.endswith("\n") else "\n\n"
    return output + text


def merge(
    live_text: str | None, rendered: Mapping[str, str], endpoints_block: str | None
) -> Merge:
    """Replace managed blocks in place, drop stale ones, append new ones at the end."""
    pending = dict(rendered)
    pending_endpoints = endpoints_block
    removed: list[str] = []
    live_only: list[str] = []
    output = ""
    for block in split_blocks(live_text or ""):
        if block.model_id is not None:
            if not block.managed:
                if pending.pop(block.model_id, None) is not None:
                    live_only.append(block.model_id)
                output += block.text
            elif block.model_id in pending:
                output += _replace(pending.pop(block.model_id), block.text)
            else:
                removed.append(block.model_id)
        elif block.header == ENDPOINTS_HEADER:
            if not block.managed:
                if pending_endpoints is not None:
                    live_only.append(ENDPOINTS_HEADER)
                    pending_endpoints = None
                output += block.text
            elif pending_endpoints is not None:
                output += _replace(pending_endpoints, block.text)
                pending_endpoints = None
            else:
                removed.append(ENDPOINTS_HEADER)
        else:
            output += block.text
    for model_id in sorted(pending):
        output = _append(output, pending[model_id])
    if pending_endpoints is not None:
        output = _append(output, pending_endpoints)
    return Merge(output, dict(rendered), endpoints_block, removed, live_only)


def _require_toml(text: str, message: str) -> None:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise GrokMergeError(f"{message} ({error})") from error


def render(config: Mapping[str, Any], live_text: str | None) -> Merge:
    """Merge the registry into the live text; both it and the result must parse."""
    if live_text:
        _require_toml(
            live_text, "live config does not parse as TOML; refusing to merge into it"
        )
    rendered, endpoints_block = render_blocks(config)
    result = merge(live_text, rendered, endpoints_block)
    _require_toml(result.text, "merged config does not parse as TOML")
    return result


def main(argv: list[str] | None = None, *, run: common.Runner | None = None) -> int:
    parser = common.build_parser(NAME, default_live=DEFAULT_LIVE_CONFIG)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help=f"after --write, run `{' '.join(SMOKE_COMMAND)}` with GROK_HOME at the "
        "live file's directory and roll back when it fails",
    )
    args = parser.parse_args(argv)
    live_path = common.live_path(args)
    try:
        config, live_text = common.load_inputs(args)
        result = render(config, live_text)
        common.assert_no_secret_values(
            result.managed_text, os.environ, models.credential_names(config)
        )
    except (
        models.ModelsRegistryError,
        GrokMergeError,
        common.SecretValueError,
    ) as error:
        return common.fail(NAME, str(error))
    if not args.quiet:
        common.print_routing_report(models.routing_report(config, RUNTIME))
    changed = result.text != (live_text or "")
    counts: dict[str, object] = {
        "models": len(result.rendered),
        "endpoints_block": result.endpoints_block is not None,
    }
    tail: dict[str, object] = {
        "removed": len(result.removed),
        "live_only": len(result.live_only),
        "changed": changed,
    }
    if args.check:
        if changed:
            print(f"FAILED:{NAME} check drift={live_path.name}")
            return 1
        return common.print_success(NAME, **counts, written=False, **tail)
    if not args.write or not changed:
        return common.print_success(NAME, **counts, written=False, **tail)
    backup = common.write_with_backup(live_path, result.text, backup=not args.no_backup)
    if args.smoke:
        env = {**os.environ, "GROK_HOME": str(live_path.parent)}
        if not common.smoke_and_rollback(
            SMOKE_COMMAND, [live_path], {live_path: backup}, run=run, env=env
        ):
            return common.fail(
                NAME,
                f"smoke '{' '.join(SMOKE_COMMAND)}' failed; {live_path} restored",
            )
        return common.print_success(NAME, **counts, written=True, **tail, smoke=True)
    return common.print_success(NAME, **counts, written=True, **tail)


if __name__ == "__main__":
    raise SystemExit(main())
