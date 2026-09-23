"""The inference-hub call ledger: one JSON line per call, one file per UTC day.

Rows carry identifiers, counts and money - never prompt text. The prompt is
represented by :func:`prompt_digest` (the first 16 hex characters of the sha256
of its canonical JSON), and :meth:`Ledger.record` refuses any entry that smells
like text: a key named ``text`` / ``content`` / ``messages`` anywhere in the
entry, or any string longer than :data:`MAX_STRING_LENGTH`.

Layout: ``<root>/YYYY-MM-DD.jsonl``. The root comes from the constructor, else
the ``INFERENCE_HUB_LEDGER`` environment variable, else
``policy.hub.ledgerPath`` resolved against the repo root
(:func:`resolve_ledger_root`). Appends are single ``write`` calls under a
process-wide lock, so concurrent hub calls never interleave bytes - the same
bounded-sink idiom as ``tools/mcp/_shared/hardening.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hub.registry import find_repo_root

__all__ = [
    "DEFAULT_LEDGER_PATH",
    "FORBIDDEN_KEYS",
    "LEDGER_ENV",
    "LEDGER_FIELDS",
    "MAX_STRING_LENGTH",
    "Ledger",
    "prompt_digest",
    "resolve_ledger_root",
]

LEDGER_ENV = "INFERENCE_HUB_LEDGER"
DEFAULT_LEDGER_PATH = "state/inference-ledger"
MAX_STRING_LENGTH = 256

LEDGER_FIELDS: tuple[str, ...] = (
    "ts",
    "ledger_id",
    "endpoint",
    "model",
    "remote_id",
    "caller",
    "prompt_sha256_16",
    "prompt_tokens",
    "completion_tokens",
    "latency_ms",
    "status",
    "error_class",
    "cost_usd",
    "cost_basis",
    "tags",
)

FORBIDDEN_KEYS: frozenset[str] = frozenset({"text", "content", "messages"})


def prompt_digest(messages: Any) -> str:
    """sha256 of the canonical JSON of ``messages``, first 16 hex characters."""
    canonical = json.dumps(
        messages, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def resolve_ledger_root(
    policy: Mapping[str, Any] | None,
    environ: Mapping[str, str],
    repo_root: Path,
) -> Path:
    """``INFERENCE_HUB_LEDGER`` (relative paths against the repo root), else policy."""
    override = environ.get(LEDGER_ENV, "")
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.is_absolute() else repo_root / candidate
    hub_policy = (policy or {}).get("hub") or {}
    return repo_root / str(hub_policy.get("ledgerPath") or DEFAULT_LEDGER_PATH)


def _guard(value: Any, path: str) -> None:
    """Raise ValueError when ``value`` could be carrying prompt text."""
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise ValueError(
                f"ledger entry {path}: string longer than {MAX_STRING_LENGTH} chars"
            )
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_KEYS:
                raise ValueError(f"ledger entry {path}: key {key!r} is never recorded")
            _guard(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for position, child in enumerate(value):
            _guard(child, f"{path}[{position}]")


class Ledger:
    """Append-only daily JSONL ledger."""

    root: Path

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        policy: Mapping[str, Any] | None = None,
        environ: Mapping[str, str] | None = None,
        repo_root: Path | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if root is not None:
            self.root = Path(root)
        else:
            env = os.environ if environ is None else environ
            base = repo_root if repo_root is not None else find_repo_root()
            if base is None:
                raise ValueError("ledger root: no repo root found and no path given")
            self.root = resolve_ledger_root(policy, env, base)
        self._clock = clock
        self._lock = threading.Lock()

    prompt_digest = staticmethod(prompt_digest)

    def day_file(self, when: float | None = None) -> Path:
        stamp = self._clock() if when is None else when
        day = datetime.fromtimestamp(stamp, tz=timezone.utc).strftime("%Y-%m-%d")
        return self.root / f"{day}.jsonl"

    def record(self, entry: Mapping[str, Any]) -> str:
        """Append one row and return its ``ledger_id``."""
        unknown = sorted(set(map(str, entry)) - set(LEDGER_FIELDS))
        if unknown:
            forbidden = [key for key in unknown if key in FORBIDDEN_KEYS]
            if forbidden:
                raise ValueError(
                    f"ledger entry: key {forbidden[0]!r} is never recorded"
                )
            raise ValueError(f"ledger entry: unknown keys {unknown}")
        row: dict[str, Any] = {field: entry.get(field) for field in LEDGER_FIELDS}
        now = self._clock()
        if row["ts"] is None:
            moment = datetime.fromtimestamp(now, tz=timezone.utc)
            row["ts"] = (
                moment.strftime("%Y-%m-%dT%H:%M:%S.")
                + f"{moment.microsecond // 1000:03d}Z"
            )
        if row["ledger_id"] is None:
            row["ledger_id"] = uuid.uuid4().hex[:16]
        if row["tags"] is None:
            row["tags"] = []
        cost = row["cost_usd"]
        if cost is not None and (
            isinstance(cost, bool) or not isinstance(cost, (int, float))
        ):
            raise ValueError("ledger entry: cost_usd must be a number or null")
        if not isinstance(row["tags"], list):
            raise ValueError("ledger entry: tags must be a list")
        _guard(row, "entry")
        line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            with self.day_file(now).open("a", encoding="utf-8") as handle:
                handle.write(line)
        return str(row["ledger_id"])

    def today_entries(self, endpoint: str | None = None) -> list[dict[str, Any]]:
        """Parsed rows of today's file (corrupt lines skipped), optionally per endpoint."""
        path = self.day_file()
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(parsed, dict):
                    continue
                if endpoint is None or parsed.get("endpoint") == endpoint:
                    rows.append(parsed)
        return rows

    def sum_cost_today(self, endpoint: str | None = None) -> float | None:
        """Sum of today's numeric ``cost_usd``; None when no row carries a number."""
        costs = [
            row["cost_usd"]
            for row in self.today_entries(endpoint)
            if isinstance(row.get("cost_usd"), (int, float))
            and not isinstance(row.get("cost_usd"), bool)
        ]
        if not costs:
            return None
        return float(sum(costs))
