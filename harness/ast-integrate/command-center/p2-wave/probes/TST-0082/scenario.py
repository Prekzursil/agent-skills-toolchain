"""Fixture plugin: healthy hooks.json versus the Codex $schema zero-load plant.

Catalog inputs hooks/_dispatch/manifest.json and hooks/_dispatch/test_wiring.py
are absent at repo root on this worktree. The probe uses a fixture plugin that
preserves those names so the dispatch list is executable rather than inferred.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0082"

# Dispatch names (manifest) -> client event vocabulary (hooks.json).
EVENTS: tuple[tuple[str, str], ...] = (
    ("pre-tool", "PreToolUse"),
    ("post-tool", "PostToolUse"),
    ("session-start", "SessionStart"),
    ("stop", "Stop"),
)

SCHEMA_PLANT = "https://json-schema.org/draft/2020-12/schema"
WRITER_REL = "command-center/p2-wave/probes/TST-0082/hook_writer.py"
MANIFEST_REL = (
    "command-center/p2-wave/probes/TST-0082/fixtures/plugin/"
    "hooks/_dispatch/manifest.json"
)
WIRING_REL = (
    "command-center/p2-wave/probes/TST-0082/fixtures/plugin/"
    "hooks/_dispatch/test_wiring.py"
)
HEALTHY_REL = "command-center/p2-wave/probes/TST-0082/fixtures/healthy/hooks.json"
MALFORMED_REL = (
    "command-center/p2-wave/probes/TST-0082/fixtures/malformed/hooks.json"
)
CAPTURE_HEALTHY_REL = (
    "command-center/p2-wave/probes/TST-0082/captures/healthy-receipt.txt"
)
CAPTURE_MALFORMED_REL = (
    "command-center/p2-wave/probes/TST-0082/captures/malformed-receipt.txt"
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0082/probe1_each_hook.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0082/probe2_malformed.py"
)
OUT = "command-center/receipts/TST-0082.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
SENTINEL = (
    "SUCCESS:TST-0082 emitted only when each declared hook event produced a "
    "written RECEIPT line from a child process under a healthy hooks.json, and "
    "the same trigger against a $schema-bearing hooks.json loaded ZERO hooks "
    "while the plugin files still looked installed. Registration is not "
    "execution. Any other terminal state is FAILED:TST-0082."
)
QUESTION = (
    "Failure class :11303. Measured precedent: a $schema key in hooks.json "
    "made Codex load ZERO hooks while everything looked installed. Target: an "
    "end-to-end probe that triggers each hook event and asserts an observable "
    "side effect - registration is not execution."
)


def plugin_root() -> Path:
    return HERE / "fixtures" / "plugin"


def healthy_path() -> Path:
    return REPO / HEALTHY_REL


def malformed_path() -> Path:
    return REPO / MALFORMED_REL


def writer_path() -> Path:
    return REPO / WRITER_REL


def manifest_path() -> Path:
    return REPO / MANIFEST_REL


def _command(event: str, hook_id: str) -> str:
    return f"python3 -B {WRITER_REL} {event} {hook_id}"


def hooks_object() -> dict:
    body: dict[str, list] = {}
    for hook_id, event in EVENTS:
        body[event] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": _command(event, hook_id),
                    }
                ],
            }
        ]
    return body


def _dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def ensure_fixtures() -> dict[str, str]:
    """Write healthy and malformed hooks.json plus the dispatch manifest."""
    plugin = plugin_root()
    dispatch = plugin / "hooks" / "_dispatch"
    dispatch.mkdir(parents=True, exist_ok=True)
    man = {
        "hooks": [hook_id for hook_id, _event in EVENTS],
        "mounts": ["fs"],
    }
    _dump(dispatch / "manifest.json", man)
    wiring = dispatch / "test_wiring.py"
    if not wiring.is_file():
        wiring.write_text(
            (
                '"""Fixture stand-in for hooks/_dispatch/test_wiring.py."""\n'
                "from __future__ import annotations\n\n"
                "import json\n"
                "from pathlib import Path\n\n"
                "def declared_hook_ids() -> list[str]:\n"
                "    doc = json.loads((Path(__file__).parent / "
                "'manifest.json').read_text(encoding='utf-8'))\n"
                "    return list(doc['hooks'])\n"
            ),
            encoding="utf-8",
        )
    hooks = hooks_object()
    _dump(healthy_path(), {"hooks": hooks})
    _dump(
        malformed_path(),
        {"$schema": SCHEMA_PLANT, "hooks": hooks},
    )
    return {
        "healthy": HEALTHY_REL,
        "malformed": MALFORMED_REL,
        "manifest": MANIFEST_REL,
        "writer": WRITER_REL,
    }


def catalog_inputs() -> list[dict]:
    rows = []
    for rel in (
        "_USER-PROMPTS.md",
        "hooks/_dispatch/manifest.json",
        "hooks/_dispatch/test_wiring.py",
    ):
        path = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": path.is_file(),
                "note": (
                    "catalog input present"
                    if path.is_file()
                    else "absent on this worktree; fixture plugin used instead"
                ),
            }
        )
    return rows


def receipt_payload(doc: dict) -> dict:
    """Merge report overlay so probes can read tests/controls from either layer."""
    if not isinstance(doc, dict):
        return {}
    out = dict(doc)
    report = doc.get("report")
    if isinstance(report, dict):
        out.update(report)
    return out
