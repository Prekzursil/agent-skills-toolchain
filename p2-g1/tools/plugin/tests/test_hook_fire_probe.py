"""IMP-0039 tests: installed is not loaded; the probe must observe a real fire."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.hook_fire_probe import filesystem_only_verdict, run_probe  # noqa: E402
from plugin.hook_client import client_document  # noqa: E402

SENTINEL_SRC = (
    "import os, pathlib\n"
    "sentinel = pathlib.Path(os.environ['HOOK_FIRE_SENTINEL_PATH'])\n"
    "sentinel.parent.mkdir(parents=True, exist_ok=True)\n"
    "sentinel.write_text('HOOK_FIRED:' + os.environ['HOOK_FIRE_NONCE'] + ':' + os.environ['HOOK_FIRE_ID'] + chr(10), encoding='utf-8')\n"
)


def _plant(root, healthy):
    root.mkdir(parents=True, exist_ok=True)
    hooks = {"hooks": {"pre-tool": [
        {"id": "hook.pre-tool", "hooks": [{"command": "scripts/emit_sentinel.py"}]}]}}
    if healthy:
        doc = hooks
    else:
        doc = {"$schema": "https://example.invalid/x.json", "hooks": hooks["hooks"]}
    (root / "hooks.json").write_text(json.dumps(doc), encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "emit_sentinel.py").write_text(SENTINEL_SRC, encoding="utf-8")
    return root


def test_probe_reports_fired_on_healthy_config():
    with tempfile.TemporaryDirectory() as td:
        root = _plant(Path(td) / "healthy", True)
        report = run_probe(root)
        client = client_document(root)
        assert report.verdict == "FIRED", report.as_dict()
        assert report.sentinel_observed is True
        assert report.trigger_count >= 1
        assert client["loaded"] == report.inventory_loaded
        assert client["loaded"] == ["hook.pre-tool"]
        assert filesystem_only_verdict(root) == "FIRED"


def test_both_states_broken_config_reports_not_fired():
    with tempfile.TemporaryDirectory() as td:
        root = _plant(Path(td) / "broken", False)
        report = run_probe(root)
        client = client_document(root)
        assert report.verdict == "NOT-FIRED"
        assert report.sentinel_observed is False
        assert report.extra_keys == ["$schema"]
        assert (root / "hooks.json").is_file()
        assert (root / "scripts" / "emit_sentinel.py").is_file()
        assert client["loaded"] == []


def test_probe_cannot_pass_on_filesystem_evidence_alone():
    with tempfile.TemporaryDirectory() as td:
        root = _plant(Path(td) / "broken", False)
        fs = filesystem_only_verdict(root)
        real = run_probe(root).verdict
        assert fs == "FIRED" and real == "NOT-FIRED" and fs != real
