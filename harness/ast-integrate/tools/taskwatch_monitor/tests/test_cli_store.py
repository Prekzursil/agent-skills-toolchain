"""Tests for cli/store.py — registry render / append / load / save."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import TaskSpec  # noqa: E402
from core.registry import RegistryError, load_registry  # noqa: E402
from cli import store  # noqa: E402


def _rich_spec() -> TaskSpec:
    return TaskSpec(
        id="fep-1",
        adapter="local-file-tail",
        parser="fep-databricks",
        eta_model="per-phase-weighted",
        notify=["terminal", "stall"],
        remediate=True,
        task_type="fep-databricks",
        config={"path": "/logs/fep.log", "stall_after_s": 120},
    )


def _minimal_spec() -> TaskSpec:
    return TaskSpec(id="proc-1", adapter="process-pid", parser="", config={"pid": 42})


# ── render_registry round-trip ─────────────────────────────────────────────────


def test_render_registry_roundtrips():
    specs = [_rich_spec(), _minimal_spec()]
    text = store.render_registry(specs)
    reparsed = load_registry(text)
    assert [s.to_dict() for s in reparsed] == [s.to_dict() for s in specs]


def test_render_registry_omits_empty_optional_fields():
    text = store.render_registry([_minimal_spec()])
    assert "parser" not in text
    assert "remediate" not in text


def test_render_registry_spec_without_config():
    spec = TaskSpec(id="x", adapter="process-pid", parser="", config={})
    text = store.render_registry([spec])
    assert "config" not in text


# ── append_spec ────────────────────────────────────────────────────────────────


def test_append_spec_ok():
    specs = [_rich_spec()]
    grown = store.append_spec(specs, _minimal_spec())
    assert [s.id for s in grown] == ["fep-1", "proc-1"]


def test_append_spec_rejects_duplicate():
    specs = [_rich_spec()]
    with pytest.raises(RegistryError, match="duplicate task id"):
        _ = store.append_spec(specs, _rich_spec())


# ── load_specs / save_specs ────────────────────────────────────────────────────


def test_load_specs_missing_file_is_empty(tmp_path):
    assert store.load_specs(tmp_path / "absent.toml") == []


def test_save_then_load_roundtrips(tmp_path):
    path = tmp_path / "reg.toml"
    specs = [_rich_spec(), _minimal_spec()]
    store.save_specs(path, specs)
    loaded = store.load_specs(path)
    assert [s.to_dict() for s in loaded] == [s.to_dict() for s in specs]
