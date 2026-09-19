"""Backend-selector unit tests: precedence + fail-closed + load/resolve."""

from __future__ import annotations

import pytest

import backends
from schema import DEFAULT_BACKEND


# --------------------------------------------------------------------------- #
# select_backend_name — pure precedence + fail-closed
# --------------------------------------------------------------------------- #
def test_default_when_nothing_set():
    assert backends.select_backend_name(None, env={}) == DEFAULT_BACKEND
    assert backends.select_backend_name("", env={}) == "online"


def test_env_selects_when_no_arg():
    assert backends.select_backend_name(None, {"BIOMNI_BACKEND": "databricks"}) == (
        "databricks"
    )


def test_arg_overrides_env():
    env = {"BIOMNI_BACKEND": "databricks"}
    assert backends.select_backend_name("online", env) == "online"


def test_arg_case_and_whitespace_insensitive():
    assert backends.select_backend_name("  DataBricks  ", {}) == "databricks"


def test_invalid_arg_falls_back_to_env():
    assert backends.select_backend_name("nope", {"BIOMNI_BACKEND": "databricks"}) == (
        "databricks"
    )


def test_invalid_arg_and_invalid_env_fail_closed_to_online():
    assert backends.select_backend_name("nope", {"BIOMNI_BACKEND": "garbage"}) == (
        "online"
    )


def test_never_raises_on_weird_input():
    # Selection must be total — no exception for any string.
    for val in ("", "   ", "ONLINE", "x" * 1000, "online;databricks"):
        assert backends.select_backend_name(val, {}) in ("online", "databricks")


def test_uses_os_environ_when_env_omitted(monkeypatch):
    monkeypatch.setenv("BIOMNI_BACKEND", "databricks")
    assert backends.select_backend_name(None) == "databricks"
    monkeypatch.delenv("BIOMNI_BACKEND", raising=False)
    assert backends.select_backend_name(None) == "online"


# --------------------------------------------------------------------------- #
# load_backend / resolve_backend — registration, caching, unavailability
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _clean_cache():
    backends.reset_cache()
    yield
    backends.reset_cache()


def test_register_and_load_backend():
    from fake_backend import FakeBackend

    fb = FakeBackend("databricks")
    backends.register_backend("databricks", fb)
    assert backends.load_backend("databricks") is fb


def test_resolve_backend_uses_selector(monkeypatch):
    from fake_backend import FakeBackend

    monkeypatch.setenv("BIOMNI_BACKEND", "databricks")
    fb = FakeBackend("databricks")
    backends.register_backend("databricks", fb)
    assert backends.resolve_backend() is fb


def test_real_adapters_now_load_as_biomnibackend():
    # Post-reconciliation (R1): both real adapters subclass BiomniBackend and load
    # through the real gate (no AdapterUnavailable / isinstance failure).
    for name in ("online", "databricks"):
        adapter = backends.load_backend(name)
        assert isinstance(adapter, backends.BiomniBackend)
        assert adapter.name == name


def test_load_unavailable_adapter_raises(monkeypatch):
    # Force every candidate factory for online to fail -> a clear AdapterUnavailable
    # (the loader still fails loudly when an adapter genuinely cannot be built).
    monkeypatch.setitem(
        backends._ADAPTER_SPECS, "online", (("no_such_module", "get_backend"),)
    )
    with pytest.raises(backends.AdapterUnavailable):
        backends.load_backend("online")


def test_resolve_unavailable_raises_not_silent_swap(monkeypatch):
    # databricks selected but its adapter cannot load -> a clear AdapterUnavailable,
    # NOT a silent fallback to a working online.
    monkeypatch.setenv("BIOMNI_BACKEND", "databricks")
    monkeypatch.setitem(
        backends._ADAPTER_SPECS, "databricks", (("no_such_module", "get_backend"),)
    )
    with pytest.raises(backends.AdapterUnavailable):
        backends.resolve_backend()
