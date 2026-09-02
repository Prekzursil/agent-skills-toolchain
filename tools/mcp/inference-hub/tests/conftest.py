"""Generic fixtures for the inference-hub test suites.

Puts ``tools/mcp/inference-hub`` on ``sys.path`` so ``from testing.fake_openai_v1
import FakeOpenAIServer`` resolves, and starts/stops one fake upstream per
profile. Hub-specific fixtures belong in ``tests/conftest_hub.py`` (loaded via
``pytest_plugins``), not here.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from testing.fake_openai_v1 import FakeOpenAIServer  # noqa: E402


def _serve(profile: str) -> Iterator[FakeOpenAIServer]:
    with FakeOpenAIServer(profile) as fake:
        yield fake


@pytest.fixture
def fake_openai() -> Iterator[FakeOpenAIServer]:
    yield from _serve("openai")


@pytest.fixture
def fake_ollama() -> Iterator[FakeOpenAIServer]:
    yield from _serve("ollama")


@pytest.fixture
def fake_hf_router() -> Iterator[FakeOpenAIServer]:
    yield from _serve("hf-router")


@pytest.fixture
def fake_auth2api() -> Iterator[FakeOpenAIServer]:
    yield from _serve("auth2api")


@pytest.fixture
def fake_lmstudio() -> Iterator[FakeOpenAIServer]:
    yield from _serve("lmstudio")
