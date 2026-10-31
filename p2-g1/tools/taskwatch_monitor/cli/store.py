"""Registry-file persistence for the ``register`` / ``list`` commands.

A registry is the same ``[[task]]`` TOML the core loader
(:func:`core.registry.load_registry`) already parses; this module adds the write
side — :func:`render_registry` serialises a list of :class:`~core.models.TaskSpec`
back to TOML that round-trips, and :func:`append_spec` enforces the unique-id
rule before a new task lands. The pure string builders keep 100% branch coverage
reachable; only :func:`load_specs`/:func:`save_specs` touch the filesystem.
"""

from __future__ import annotations

from pathlib import Path

import tomlkit

from core.models import TaskSpec
from core.registry import RegistryError, load_registry, load_registry_file


def render_registry(specs: list[TaskSpec]) -> str:
    """Serialise ``specs`` to a ``[[task]]`` TOML document (round-trips)."""
    doc = tomlkit.document()
    aot = tomlkit.aot()
    for spec in specs:
        table = tomlkit.table()
        table["id"] = spec.id
        table["adapter"] = spec.adapter
        if spec.parser:
            table["parser"] = spec.parser
        table["eta_model"] = spec.eta_model
        table["notify"] = list(spec.notify)
        if spec.remediate:
            table["remediate"] = True
        if spec.task_type:
            table["task_type"] = spec.task_type
        if spec.config:
            config_table = tomlkit.table()
            for key, value in spec.config.items():
                config_table[key] = value
            table["config"] = config_table
        aot.append(table)
    doc["task"] = aot
    return tomlkit.dumps(doc)


def append_spec(specs: list[TaskSpec], spec: TaskSpec) -> list[TaskSpec]:
    """Return ``specs`` + ``spec``, raising on a duplicate id (grill S9)."""
    if any(existing.id == spec.id for existing in specs):
        raise RegistryError(f"duplicate task id '{spec.id}'")
    return [*specs, spec]


def load_specs(path: Path) -> list[TaskSpec]:
    """Load specs from ``path``; a missing file is an empty registry."""
    if not path.exists():
        return []
    return load_registry_file(path)


def save_specs(path: Path, specs: list[TaskSpec]) -> None:
    """Write ``specs`` to ``path`` as a registry TOML document."""
    text = render_registry(specs)
    # Validate the rendered document round-trips before it hits disk.
    _ = load_registry(text)
    path.write_text(text, encoding="utf-8")
