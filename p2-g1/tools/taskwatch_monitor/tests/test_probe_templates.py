"""Tests for probes/templates.py — task-template registry entries."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.adapters import adapter_from_spec  # noqa: E402
from core.models import TaskSpec  # noqa: E402
from probes.registry import PROBES  # noqa: E402
from probes.templates import (  # noqa: E402
    TEMPLATES,
    TemplateError,
    build_from_template,
    template_for,
)


class TestBuild:
    def test_builds_spec_with_defaults_and_override(self):
        tpl = TEMPLATES["generic-logfile"]
        spec = tpl.build("t1", {"path": "/logs/run.log"}, remediate=True)
        assert isinstance(spec, TaskSpec)
        assert spec.id == "t1"
        assert spec.adapter == "local-file-tail"
        assert spec.parser == "generic-logfile"
        assert spec.remediate is True
        assert spec.task_type == "generic-logfile"
        assert spec.config["path"] == "/logs/run.log"

    def test_build_without_config_raises_on_missing_required(self):
        # No config passed and no default for the required 'path' key.
        tpl = TEMPLATES["generic-logfile"]
        with pytest.raises(TemplateError, match="missing config"):
            _ = tpl.build("t2")

    def test_missing_required_config_raises(self):
        tpl = TEMPLATES["bpmd-modal"]
        with pytest.raises(TemplateError, match="missing config"):
            _ = tpl.build("t3", {"path": ""})


class TestBuildFromTemplate:
    def test_unknown_template(self):
        with pytest.raises(TemplateError, match="unknown template"):
            _ = build_from_template("nope", "t4")

    def test_known_template(self):
        spec = build_from_template("modal", "t5", {"path": "/x"})
        assert spec.task_type == "modal"


class TestTemplateFor:
    def test_hit(self):
        assert template_for("fep-databricks") is not None

    def test_miss(self):
        assert template_for("mystery") is None


class TestRoundTrip:
    def test_every_template_builds_a_working_adapter(self):
        cfg: dict[str, object] = {"path": "/tmp/x.log", "url": "http://x"}
        for name in TEMPLATES:
            spec = build_from_template(name, f"id-{name}", dict(cfg))
            # The produced spec must round-trip through the core adapter factory.
            assert adapter_from_spec(spec) is not None

    def test_probe_parsers_resolve(self):
        # Every template that names a probe parser must resolve to one.
        for tpl in TEMPLATES.values():
            if tpl.parser:
                assert tpl.parser in PROBES
