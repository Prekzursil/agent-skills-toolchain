#!/usr/bin/env python3
"""Shared primitives for the ``.agents/models.json`` renderers.

Every ``merge_generated_<runtime>_models.py`` script is a dry run by default,
prints exactly one ``SUCCESS:<name> ...`` or ``FAILED:<name> ...`` line, takes
``--write`` explicitly (timestamped backup first, atomic replacement second),
reports drift read-only with ``--check`` and explains every (endpoint, runtime)
decision with ``ROUTE:`` lines. This module owns those behaviours so the
renderers only differ in what they render.

Secrets never appear as values: ``env_reference`` renders a runtime's own
reference syntax for an environment-variable NAME and ``assert_no_secret_values``
refuses any rendered text that carries a set credential value or a literal
secret shape (L6). Import idiom: sibling scripts ``import
models_materialize_common as common`` after putting ``.agents/scripts`` on
``sys.path``.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import mcp_control_plane as control
import models_control_plane as models


__all__ = [
    "ENV_REFERENCE_STYLES",
    "MANAGED_MARKER_RE",
    "MARKER_PREFIX",
    "MIN_SECRET_VALUE_LENGTH",
    "RenderResult",
    "SecretValueError",
    "assert_no_secret_values",
    "backup_file",
    "build_parser",
    "env_reference",
    "fail",
    "literal_secret_kind",
    "live_path",
    "load_inputs",
    "managed_marker",
    "print_routing_report",
    "print_success",
    "read_text",
    "remove_with_backup",
    "rollback",
    "smoke_and_rollback",
    "strip_v1",
    "write_with_backup",
]

MARKER_PREFIX = "managed-by: .agents/models.json"
MANAGED_MARKER_RE = re.compile(
    r"managed-by: \.agents/models\.json (?P<hash>[0-9a-f]{16})"
)
# Shorter values are not scanned for: they would match everywhere. Mirrors the
# inference hub's outbound redaction threshold.
MIN_SECRET_VALUE_LENGTH = 8
ENV_REFERENCE_STYLES: dict[str, str] = {
    "bash": "${{{name}}}",
    "goose": "{name}",
    "grok": '["{name}"]',
    "cursor": "${{env:{name}}}",
    "opencode": "{{env:{name}}}",
}
BACKUP_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"

Runner = Callable[..., Any]


class SecretValueError(ValueError):
    """Raised when rendered text carries a credential value or a literal secret."""


@dataclass
class RenderResult:
    """What one renderer produced for one runtime."""

    runtime: str
    managed: dict[str, Any]
    routing: list[dict[str, Any]]
    written: bool = False
    backup: pathlib.Path | None = None
    drift: list[str] = field(default_factory=list)


def managed_marker(config: Mapping[str, Any]) -> str:
    """The marker every managed block/file carries: prefix + registry hash."""
    return f"{MARKER_PREFIX} {models.registry_hash(config)}"


def build_parser(
    name: str,
    default_live: pathlib.PurePath | str,
    *,
    description: str | None = None,
) -> argparse.ArgumentParser:
    """The shared renderer CLI: dry run by default, --write / --check exclusive."""
    parser = argparse.ArgumentParser(
        prog=name,
        description=description
        or f"Render .agents/models.json for {name}; dry run unless --write is given.",
    )
    parser.add_argument(
        "--registry",
        default=str(models.DEFAULT_REGISTRY_PATH),
        help="path to the models registry (default: the repo's .agents/models.json)",
    )
    parser.add_argument(
        "--live",
        default=str(default_live),
        help="the runtime's live config path this renderer merges into",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write",
        action="store_true",
        help="write the merged result back to --live (timestamped backup first)",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="report drift between --live and the rendered result; write nothing",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="skip the timestamped backup before writing",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="hide the ROUTE: routing-report lines",
    )
    return parser


def live_path(args: argparse.Namespace) -> pathlib.Path:
    """``--live`` with environment placeholders expanded (``%APPDATA%``, ``$HOME``)."""
    return pathlib.Path(os.path.expandvars(str(args.live)))


def read_text(path: pathlib.Path) -> str | None:
    """File content, or None when the path is absent or not a regular file."""
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def load_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], str | None]:
    """Load and validate the registry; read the live file when it is one.

    Warnings go to stderr as ``WARNING:models-registry ...``. Every failure is
    raised as ``ModelsRegistryError`` so a renderer's single ``except`` turns it
    into its ``FAILED:`` line; the message names paths, never values.
    """
    registry_path = pathlib.Path(args.registry)
    try:
        config = models.load_registry(registry_path)
    except OSError as error:
        raise models.ModelsRegistryError(
            f"{registry_path}: cannot read registry ({error.strerror or error})"
        ) from error
    for warning in models.validate_registry(config):
        print(f"WARNING:models-registry {warning}", file=sys.stderr)
    target = live_path(args)
    try:
        live_text = read_text(target)
    except OSError as error:
        raise models.ModelsRegistryError(
            f"{target}: cannot read live config ({error.strerror or error})"
        ) from error
    return config, live_text


def _timestamp() -> str:
    return datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)


def backup_file(path: pathlib.Path) -> pathlib.Path | None:
    """Copy ``path`` to ``<name>.bak-<YYYYmmdd-HHMMSS>``; None when it does not exist."""
    if not path.exists():
        return None
    base = path.with_name(f"{path.name}.bak-{_timestamp()}")
    candidate = base
    counter = 0
    while candidate.exists():
        counter += 1
        candidate = base.with_name(f"{base.name}-{counter}")
    shutil.copy2(path, candidate)
    return candidate


def write_with_backup(
    path: pathlib.Path | str, content: str, *, backup: bool = True
) -> pathlib.Path | None:
    """Back up the live file (when it exists and ``backup``), then write atomically."""
    target = pathlib.Path(path)
    backup_path = backup_file(target) if backup else None
    control.atomic_write_text(target, content)
    return backup_path


def remove_with_backup(
    path: pathlib.Path | str, *, backup: bool = True
) -> pathlib.Path | None:
    """Back up (when ``backup``) and delete a managed file; None when it is absent."""
    target = pathlib.Path(path)
    if not target.exists():
        return None
    backup_path = backup_file(target) if backup else None
    target.unlink()
    return backup_path


def print_routing_report(rows: Iterable[Mapping[str, Any]]) -> None:
    """One ``ROUTE:`` line per (endpoint, runtime) row of ``models.routing_report``."""
    for row in rows:
        alternative = row["alternative"] or "-"
        print(
            f"ROUTE:{row['runtime']} {row['endpoint']} {row['decision']} "
            f"reason={row['reason']} alternative={alternative} "
            f"wrappers={row['wrappers']}"
        )


def _format_count(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def print_success(name: str, **counts: object) -> int:
    """Print the single ``SUCCESS:<name> k=v ...`` line; returns the exit code 0."""
    rendered = " ".join(
        f"{key}={_format_count(value)}" for key, value in counts.items()
    )
    print(f"SUCCESS:{name} {rendered}".rstrip())
    return 0


def fail(name: str, reason: str) -> int:
    """Print the single ``FAILED:<name> <reason>`` line; returns the exit code 2."""
    print(f"FAILED:{name} {' '.join(reason.split())}")
    return 2


def _atomic_write_bytes(path: pathlib.Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def rollback(
    written: Iterable[pathlib.Path],
    backups: Mapping[pathlib.Path, pathlib.Path | None],
) -> list[pathlib.Path]:
    """Restore every written path from its backup byte-for-byte; delete new files."""
    restored: list[pathlib.Path] = []
    for path in written:
        backup = backups.get(path)
        if backup is not None and backup.exists():
            _atomic_write_bytes(path, backup.read_bytes())
        elif path.exists():
            path.unlink()
        restored.append(path)
    return restored


def smoke_and_rollback(
    cmd: Sequence[str],
    written: Iterable[pathlib.Path],
    backups: Mapping[pathlib.Path, pathlib.Path | None],
    *,
    run: Runner | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Run the post-write smoke command; on any failure restore every backup.

    The smoke's output is never echoed (a runtime may print its config, values
    included). A missing binary counts as a failure: a write nobody can verify
    is rolled back rather than trusted.
    """
    runner: Runner = subprocess.run if run is None else run
    paths = list(written)
    try:
        completed = runner(
            list(cmd),
            capture_output=True,
            text=True,
            check=False,
            env=None if env is None else dict(env),
        )
        ok = completed.returncode == 0
    except OSError:
        ok = False
    if ok:
        return True
    rollback(paths, backups)
    return False


def env_reference(name: str, style: str) -> str:
    """Render an environment-variable NAME in a runtime's reference syntax."""
    if control.ENV_NAME_RE.fullmatch(name) is None:
        raise ValueError(f"{name!r} is not an environment variable name")
    template = ENV_REFERENCE_STYLES.get(style)
    if template is None:
        raise ValueError(
            f"unknown env reference style {style!r}; expected one of "
            + ", ".join(sorted(ENV_REFERENCE_STYLES))
        )
    return template.format(name=name)


def literal_secret_kind(text: str) -> str | None:
    """Name the literal-secret shape found in ``text``, or None when clean."""
    if models.PEM_PRIVATE_KEY_RE.search(text):
        return "pem-private-key"
    for token in models.SECRET_TOKEN_SPLIT_RE.split(text):
        if models.AWS_ACCESS_KEY_RE.fullmatch(token):
            return "aws-access-key"
        if not token or control.ENV_NAME_RE.fullmatch(token):
            continue
        if control.LITERAL_SECRET_RE.search(token):
            return "token-prefix"
        if models.EXTRA_LITERAL_SECRET_RE.search(token):
            return "slack-token"
    return None


def assert_no_secret_values(
    text: str, environ: Mapping[str, str], names: Iterable[str]
) -> None:
    """Refuse rendered text that carries a set credential value or a secret shape.

    ``names`` are the credential environment-variable names the registry
    declares (``models.credential_names``); each one that is set in ``environ``
    must not appear in ``text``. Messages carry the NAME and length only.
    """
    for name in sorted(set(names)):
        value = environ.get(name)
        if value and len(value) >= MIN_SECRET_VALUE_LENGTH and value in text:
            raise SecretValueError(
                f"rendered text contains the value of {name} (len={len(value)}); "
                "credentials are referenced by name only (L6)"
            )
    kind = literal_secret_kind(text)
    if kind is not None:
        raise SecretValueError(
            f"rendered text contains a literal secret ({kind}); credentials are "
            "referenced by name only (L6)"
        )


def strip_v1(url: str) -> str:
    """An OpenAI-compatible base URL without its trailing ``/v1`` segment."""
    return url[: -len("/v1")] if url.endswith("/v1") else url
