"""Tests for the transport_port seam (WU-0b)."""

import pytest

from wearables.transport import (
    FakeTransport,
    TransportError,
    TransportPort,
    ToolUniverseTransport,
    fetch_json,
)


def test_fake_transport_returns_canned_json():
    fake = FakeTransport({("ChEMBL", "CHEMBL40"): {"ki": 12.0}})
    assert fake.fetch_json("ChEMBL", "CHEMBL40") == {"ki": 12.0}


def test_fake_transport_unknown_key_raises_transport_error():
    fake = FakeTransport({})
    with pytest.raises(TransportError):
        fake.fetch_json("ChEMBL", "missing")


def test_fake_transport_error_fixture_raises():
    fake = FakeTransport({("ChEMBL", "boom"): TransportError("HTTP 500")})
    with pytest.raises(TransportError) as exc:
        fake.fetch_json("ChEMBL", "boom")
    assert "HTTP 500" in str(exc.value)


def test_fake_transport_records_calls():
    fake = FakeTransport({("PubChem", "k"): {"ok": True}})
    fake.fetch_json("PubChem", "k")
    assert fake.calls == [("PubChem", "k")]


def test_fake_transport_satisfies_protocol():
    fake = FakeTransport({})
    assert isinstance(fake, TransportPort)


def test_module_fetch_json_delegates_to_port():
    fake = FakeTransport({("GtoPdb", "1"): {"v": 1}})
    assert fetch_json(fake, "GtoPdb", "1") == {"v": 1}


def test_production_adapter_raises_without_live_mcp():
    adapter = ToolUniverseTransport(executor=None)
    with pytest.raises(NotImplementedError):
        adapter.fetch_json("ChEMBL", "CHEMBL40")


def test_production_adapter_calls_injected_executor():
    captured = {}

    def fake_executor(tool_name, arguments):
        captured["tool"] = tool_name
        captured["args"] = arguments
        return {"result": "ok"}

    adapter = ToolUniverseTransport(executor=fake_executor)
    out = adapter.fetch_json("ChEMBL", "CHEMBL40")
    assert out == {"result": "ok"}
    assert captured["args"]["source"] == "ChEMBL"
    assert captured["args"]["key"] == "CHEMBL40"


def test_production_adapter_wraps_executor_failure():
    def boom(tool_name, arguments):
        raise RuntimeError("mcp down")

    adapter = ToolUniverseTransport(executor=boom)
    with pytest.raises(TransportError):
        adapter.fetch_json("ChEMBL", "CHEMBL40")
