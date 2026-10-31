"""Declarative TOML task registry loader (grill S9).

A registry file is a list of ``[[task]]`` tables:

    [[task]]
    id = "fep-edge-1"
    adapter = "local-file-tail"
    parser = "fep-line"
    eta_model = "linear-frac"
    notify = ["terminal", "stall"]
    remediate = false
    task_type = "fep-edge"

    [task.config]
    path = "/logs/fep.log"
    pattern = "edge (\\d+)/(\\d+)"

Only ``id`` and ``adapter`` are required; everything else has a defaulted value
on :class:`~core.models.TaskSpec`. Unknown ids must be unique. Parsing is pure
string→objects so it is fully testable without touching the filesystem
(``load_registry_file`` is the thin path-reading wrapper).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import tomlkit

from .models import TaskSpec

_VALID_ADAPTERS = frozenset(
    {"local-file-tail", "file-exists-glob", "http-json", "process-pid", "ssh-exec"}
)


class RegistryError(ValueError):
    """Raised when a registry document is structurally invalid."""


def _as_str_list(value: object) -> list[str]:
    """Coerce a TOML value into a list[str] (single string → one-element list)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in cast("list[object]", value)]
    raise RegistryError(
        f"expected string or list of strings, got {type(value).__name__}"
    )


def _parse_task(index: int, raw: dict[str, object]) -> TaskSpec:
    task_id = raw.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise RegistryError(f"task[{index}] is missing a non-empty string 'id'")

    adapter = raw.get("adapter")
    if not isinstance(adapter, str) or not adapter:
        raise RegistryError(f"task '{task_id}' is missing a non-empty string 'adapter'")
    if adapter not in _VALID_ADAPTERS:
        raise RegistryError(
            f"task '{task_id}' has unknown adapter '{adapter}'; "
            f"valid adapters are {sorted(_VALID_ADAPTERS)}"
        )

    notify_raw = raw.get("notify", [])
    notify = _as_str_list(notify_raw)

    config_raw = raw.get("config", {})
    if not isinstance(config_raw, dict):
        raise RegistryError(f"task '{task_id}' has a non-table 'config'")
    config = cast("dict[str, object]", config_raw)

    remediate = raw.get("remediate", False)
    if not isinstance(remediate, bool):
        raise RegistryError(f"task '{task_id}' has a non-boolean 'remediate'")

    return TaskSpec(
        id=task_id,
        adapter=adapter,
        parser=str(raw.get("parser", "")),
        eta_model=str(raw.get("eta_model", "linear-frac")),
        notify=notify,
        remediate=remediate,
        task_type=str(raw.get("task_type", "")),
        config=dict(config),
    )


def load_registry(text: str) -> list[TaskSpec]:
    """Parse a registry TOML string into a list of :class:`TaskSpec`.

    Raises :class:`RegistryError` on a malformed document, a missing required
    field, an unknown adapter, or a duplicate task id.
    """
    try:
        doc = tomlkit.parse(text).unwrap()
    except Exception as exc:  # noqa: BLE001 - normalise any parse failure
        raise RegistryError(f"invalid TOML: {exc}") from exc

    tasks_raw = doc.get("task", [])
    if not isinstance(tasks_raw, list):
        raise RegistryError("'task' must be an array of tables ([[task]])")

    specs: list[TaskSpec] = []
    seen: set[str] = set()
    for index, entry in enumerate(cast("list[object]", tasks_raw)):
        if not isinstance(entry, dict):
            raise RegistryError(f"task[{index}] must be a table")
        spec = _parse_task(index, cast("dict[str, object]", entry))
        if spec.id in seen:
            raise RegistryError(f"duplicate task id '{spec.id}'")
        seen.add(spec.id)
        specs.append(spec)
    return specs


def load_registry_file(path: Path) -> list[TaskSpec]:
    """Read a registry file from disk and parse it (thin I/O wrapper)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RegistryError(f"cannot read registry '{path}': {exc}") from exc
    return load_registry(text)
