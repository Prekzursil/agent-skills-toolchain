"""Drift contract against the sibling monitorcore package.

mcpctl reuses ``monitorcore.textsafe.strip_controls`` when importable and falls back
to a local copy of the same regex otherwise. That duplication is only safe if the two
cannot drift apart silently, so this file loads monitorcore's real module **by path**
-- not by import -- and asserts byte-for-byte agreement over the whole 0x00-0xFF
range.

Loading by path is deliberate: it means the drift detector runs in EVERY environment
(local dev and CI alike) with no ``pip install -e ../monitorcore`` and no
``pytest.mark.skipif``. A skip would make this file silent in exactly the state it
exists to catch -- the both-states failure mode. If monitorcore moves, is renamed, or
loses either symbol, these tests FAIL loudly rather than quietly doing nothing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from mcpctl import safety

_MONITORCORE = Path(__file__).resolve().parents[2] / "monitorcore" / "monitorcore"

#: Synthetic parent package for the by-path load. See :func:`_ensure_contract_package`.
_CONTRACT_PKG = "_contract_monitorcore"


def _ensure_contract_package() -> None:
    """Register a synthetic parent package so monitorcore's RELATIVE imports resolve.

    Loading a package's module by path under a FLAT name leaves ``__package__`` empty, so a
    perfectly legitimate intra-package ``from .textsafe import strip_controls`` fails with
    ``ImportError: attempted relative import with no known parent package``. That is a defect
    in the loader, not in monitorcore: a package is entitled to import its own siblings, so
    this loader has to MODEL the package rather than forbid the import.

    MEASURED 2026-07-27: monitorcore gained ``redact.scrub`` (strip-then-redact, the shared
    ingest floor) which imports ``.textsafe``; the flat-name load then failed two contract
    tests in CI while the package itself was perfectly healthy.

    Pointing the synthetic parent's ``__path__`` at the real directory makes the sibling
    resolve from that SAME on-disk tree, so this remains a genuine BY-PATH load -- still no
    ``pip install -e ../monitorcore``, still no ``skipif``, which is the whole reason this
    contract can run in every environment.
    """
    if _CONTRACT_PKG not in sys.modules:
        pkg = ModuleType(_CONTRACT_PKG)
        pkg.__path__ = [str(_MONITORCORE)]
        sys.modules[_CONTRACT_PKG] = pkg


def _load_by_path(module_name: str) -> ModuleType:
    path = _MONITORCORE / f"{module_name}.py"
    if not path.is_file():
        pytest.fail(
            f"monitorcore drift: expected {path} to exist. mcpctl's safety layer "
            "documents a reuse relationship with it; update mcpctl/safety.py and "
            "this contract together if the sibling package moved."
        )
    _ensure_contract_package()
    spec = importlib.util.spec_from_file_location(
        f"{_CONTRACT_PKG}.{module_name}", path
    )
    if (
        spec is None or spec.loader is None
    ):  # pragma: no cover -- unreachable for a real .py
        pytest.fail(f"monitorcore drift: {path} is not loadable as a module")
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: the relative-import machinery looks the parent+child up in
    # sys.modules while executing the module body.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_upstream_textsafe_exposes_strip_controls():
    textsafe = _load_by_path("textsafe")
    assert hasattr(textsafe, "strip_controls"), (
        "monitorcore.textsafe.strip_controls disappeared -- mcpctl/safety.py names it "
        "as the single source of truth for the control-byte class"
    )


def test_local_fallback_matches_upstream_over_the_whole_byte_range():
    """The load-bearing agreement check: same input, same output, all 256 code points."""
    textsafe = _load_by_path("textsafe")
    upstream_strip = textsafe.strip_controls
    for code_point in range(0x100):
        sample = f"a{chr(code_point)}b"
        assert safety._fallback_strip_controls(sample) == upstream_strip(sample), (
            f"control-byte class drift at U+{code_point:04X}"
        )


def test_upstream_redact_still_masks_a_shape_mcpctl_delegates_to_it():
    """monitorcore keeps its own patterns; mcpctl only ever layers MORE on top."""
    redact_mod = _load_by_path("redact")
    fake_pat = "ghp_" + "A" * 36
    masked, count = redact_mod.redact(f"tok={fake_pat}")
    assert fake_pat not in masked
    assert count >= 1


def test_pick_strip_uses_upstream_when_available_and_fallback_otherwise():
    def sentinel_strip(text: str) -> str:
        return f"upstream:{text}"

    upstream = safety.Upstream(strip_controls=sentinel_strip, redact=lambda t: (t, 0))
    assert safety.pick_strip(upstream)("x") == "upstream:x"
    assert safety.pick_strip(None)("a\x1bb") == "ab"


def test_load_upstream_returns_none_when_monitorcore_is_absent():
    def raising_importer(name: str) -> ModuleType:
        raise ImportError(name)

    assert safety.load_upstream(raising_importer) is None


def test_load_upstream_binds_both_callables_when_the_import_succeeds():
    textsafe = _load_by_path("textsafe")
    redact_mod = _load_by_path("redact")
    modules = {"monitorcore.textsafe": textsafe, "monitorcore.redact": redact_mod}

    def fake_importer(name: str) -> ModuleType:
        return modules[name]

    upstream = safety.load_upstream(fake_importer)
    assert upstream is not None
    assert upstream.strip_controls("a\x1bb") == "ab"
    assert upstream.redact("plain") == ("plain", 0)


def test_make_redactor_layers_upstream_after_the_local_patterns():
    calls: list[str] = []

    def recording_redact(text: str) -> tuple[str, int]:
        calls.append(text)
        return text.replace("LEFTOVER", "[UPSTREAM]"), 1

    upstream = safety.Upstream(strip_controls=str, redact=recording_redact)
    redactor = safety.make_redactor(upstream)
    out = redactor("sk-" + "A" * 20 + " LEFTOVER")
    assert "[REDACTED:api-key]" in out
    assert "[UPSTREAM]" in out
    # Upstream saw the ALREADY-locally-masked text: mcpctl's layer runs first.
    assert "[REDACTED:api-key]" in calls[0]


def test_make_redactor_without_upstream_still_masks_and_collapses_home():
    redactor = safety.make_redactor(None)
    out = redactor("xai-" + "Z" * 30 + " at C:/Users/bob/x")
    assert "[REDACTED:xai-key]" in out
    assert "bob" not in out
    assert "~/x" in out
