"""Shared helpers and fixtures for the hub core-module tests.

Not a ``conftest.py`` (another work unit owns that file). Test modules put
``tools/mcp/inference-hub`` on ``sys.path`` and import from here explicitly::

    from tests import conftest_hub as helpers
    registry = helpers.registry  # re-exported fixture

Every secret-shaped string used by the tests is assembled at runtime from
harmless fragments so no committed literal matches a credential pattern.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

HUB_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HUB_ROOT.parents[2]
SEED_REGISTRY = REPO_ROOT / ".agents" / "models.json"

Mutator = Callable[[dict[str, Any]], None]

_PREFIX_PARTS: dict[str, tuple[str, ...]] = {
    "huggingface": ("hf", "_"),
    "github_token": ("gh", "p", "_"),
    "github_pat": ("github", "_pat", "_"),
    "openrouter": ("sk", "-or", "-v1", "-"),
    "anthropic": ("sk", "-ant", "-"),
    "openai_project": ("sk", "-proj", "-"),
    "openai": ("sk", "-"),
    "digitalocean": ("dop", "_v1", "_"),
    "slack": ("xox", "b", "-"),
}

DEFAULT_BODY = "Ab9" * 12


def load_seed() -> dict[str, Any]:
    """Return a deep copy of the real ``.agents/models.json``."""
    with SEED_REGISTRY.open(encoding="utf-8") as handle:
        return copy.deepcopy(json.load(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def make_registry_copy(
    target_dir: Path,
    mutate: Mutator | None = None,
    name: str = "models.json",
) -> Path:
    """Write a (possibly mutated) copy of the seed registry and return its path."""
    config = load_seed()
    if mutate is not None:
        mutate(config)
    target = target_dir / name
    write_json(target, config)
    return target


def make_repo_layout(tmp_path: Path, mutate: Mutator | None = None) -> Path:
    """Create ``<tmp>/repo/.agents/models.json`` and return the fake repo root."""
    repo_root = tmp_path / "repo"
    make_registry_copy(repo_root / ".agents", mutate)
    return repo_root


def pem_block() -> str:
    dashes = "-" * 5
    head = dashes + "BEGIN RSA PRIVATE" + " KEY" + dashes
    tail = dashes + "END RSA PRIVATE" + " KEY" + dashes
    return head + "\nMIIBogIBAAJBALRiMLAH\n" + tail


def secret_like(kind: str, body: str | None = None) -> str:
    """Build a token-shaped string for ``kind`` without committing a literal."""
    if kind == "aws_access_key":
        return "AK" + "IA" + "Z7Q4" * 4
    if kind == "jwt":
        return "ey" + "J" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    if kind == "private_key":
        return pem_block()
    return "".join(_PREFIX_PARTS[kind]) + (body if body is not None else DEFAULT_BODY)


@pytest.fixture
def seed_registry_path(tmp_path: Path) -> Path:
    return make_registry_copy(tmp_path)


@pytest.fixture
def registry(seed_registry_path: Path, tmp_path: Path) -> Any:
    from hub.registry import Registry

    return Registry(seed_registry_path, environ={}, repo_root=tmp_path)


@pytest.fixture
def ledger(tmp_path: Path) -> Any:
    from hub.ledger import Ledger

    return Ledger(tmp_path / "ledger")
