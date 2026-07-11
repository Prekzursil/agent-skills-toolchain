"""Tests for core/registry.py — TOML registry loader."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.registry import (  # noqa: E402
    RegistryError,
    load_registry,
    load_registry_file,
)

_GOOD = """
[[task]]
id = "fep-1"
adapter = "local-file-tail"
parser = "fep-line"
eta_model = "linear-frac"
notify = ["terminal", "stall"]
remediate = true
task_type = "fep-edge"

[task.config]
path = "/logs/fep.log"
pattern = "edge"

[[task]]
id = "glob-1"
adapter = "file-exists-glob"
notify = "terminal"
"""


class TestLoadRegistry:
    def test_parses_multiple_tasks(self):
        specs = load_registry(_GOOD)
        assert len(specs) == 2
        first = specs[0]
        assert first.id == "fep-1"
        assert first.adapter == "local-file-tail"
        assert first.notify == ["terminal", "stall"]
        assert first.remediate is True
        assert first.history_key == "fep-edge"
        assert first.config["path"] == "/logs/fep.log"
        # single-string notify coerces to one-element list
        assert specs[1].notify == ["terminal"]

    def test_empty_document(self):
        assert load_registry("") == []

    def test_invalid_toml(self):
        with pytest.raises(RegistryError, match="invalid TOML"):
            load_registry("this = = broken")

    def test_task_not_array(self):
        with pytest.raises(RegistryError, match="array of tables"):
            load_registry('task = "oops"')

    def test_entry_not_table(self):
        with pytest.raises(RegistryError, match="must be a table"):
            load_registry("task = [1, 2]")

    def test_missing_id(self):
        with pytest.raises(RegistryError, match="missing a non-empty string 'id'"):
            load_registry('[[task]]\nadapter = "http-json"')

    def test_empty_id(self):
        with pytest.raises(RegistryError, match="'id'"):
            load_registry('[[task]]\nid = ""\nadapter = "http-json"')

    def test_missing_adapter(self):
        with pytest.raises(RegistryError, match="missing a non-empty string 'adapter'"):
            load_registry('[[task]]\nid = "a"')

    def test_unknown_adapter(self):
        with pytest.raises(RegistryError, match="unknown adapter"):
            load_registry('[[task]]\nid = "a"\nadapter = "carrier-pigeon"')

    def test_non_table_config(self):
        with pytest.raises(RegistryError, match="non-table 'config'"):
            load_registry('[[task]]\nid = "a"\nadapter = "http-json"\nconfig = 5')

    def test_non_bool_remediate(self):
        with pytest.raises(RegistryError, match="non-boolean 'remediate'"):
            load_registry(
                '[[task]]\nid = "a"\nadapter = "http-json"\nremediate = "yes"'
            )

    def test_bad_notify_type(self):
        with pytest.raises(RegistryError, match="string or list of strings"):
            load_registry('[[task]]\nid = "a"\nadapter = "http-json"\nnotify = 5')

    def test_duplicate_id(self):
        doc = (
            '[[task]]\nid = "dup"\nadapter = "http-json"\n'
            '[[task]]\nid = "dup"\nadapter = "process-pid"'
        )
        with pytest.raises(RegistryError, match="duplicate task id"):
            load_registry(doc)


class TestLoadRegistryFile:
    def test_reads_file(self, tmp_path: Path):
        p = tmp_path / "reg.toml"
        _ = p.write_text(_GOOD, encoding="utf-8")
        specs = load_registry_file(p)
        assert len(specs) == 2

    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(RegistryError, match="cannot read registry"):
            load_registry_file(tmp_path / "nope.toml")
