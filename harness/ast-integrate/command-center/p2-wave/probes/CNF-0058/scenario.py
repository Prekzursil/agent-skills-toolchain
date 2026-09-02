#!/usr/bin/env python3
"""Known-broken fixture pair for CNF-0058 layout+consumer detector.

Two produced artifact trees (before/after) plus a consumer inventory:
tools, workflows, gates, and a prose-only handbook. The after tree moves
a path, changes a filename pattern, and adds an unreferenced scratch file.
"""
from __future__ import annotations

import json
from pathlib import Path

UNIT_ID = "CNF-0058"
HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# Changed paths the detector must classify.
MOVED_FROM = "reports/layout-index.json"
MOVED_TO = "artifacts/layout-index.json"
PATTERN_FROM = "dist/tool-output.json"
PATTERN_TO = "dist/tool-output.ndjson"
NO_CONSUMER_ADDED = "tmp/scratch-debug.json"
NO_CONSUMER_ORPHAN = "orphan/unreferenced.bin"
STABLE_CONSUMED = "reports/gate-summary.json"

PROSE_DOC = "docs/operator-handbook.md"
WORKFLOW_CONSUMER = "workflows/publish-layout.json"
GATE_CONSUMER = "gates/check-tool-output.sh"
TOOL_CONSUMER = "tools/read_gate_summary.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manifest(mapping: dict[str, str]) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "title": "produced-artifact-layout",
            "artifacts": mapping,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def materialize(root: Path | None = None) -> dict[str, Path]:
    """Write before/after trees and the consumer inventory. Idempotent."""
    base = root or FIXTURES
    before = base / "trees" / "before"
    after = base / "trees" / "after"
    consumers = base / "consumers"

    before_map = {
        "gate-summary": STABLE_CONSUMED,
        "layout-index": MOVED_FROM,
        "tool-output": PATTERN_FROM,
        "orphan": NO_CONSUMER_ORPHAN,
    }
    after_map = {
        "gate-summary": STABLE_CONSUMED,
        "layout-index": MOVED_TO,
        "tool-output": PATTERN_TO,
        "orphan": NO_CONSUMER_ORPHAN,
        "scratch": NO_CONSUMER_ADDED,
    }

    _write(before / "ARTIFACT-MANIFEST.json", _manifest(before_map))
    _write(before / STABLE_CONSUMED, json.dumps({"gate": "ok", "state": "before"}) + "\n")
    _write(before / MOVED_FROM, json.dumps({"index": ["gate-summary", "tool-output"]}) + "\n")
    _write(before / PATTERN_FROM, json.dumps({"records": 2, "fmt": "json"}) + "\n")
    _write(before / NO_CONSUMER_ORPHAN, "orphan-bytes\n")

    _write(after / "ARTIFACT-MANIFEST.json", _manifest(after_map))
    _write(after / STABLE_CONSUMED, json.dumps({"gate": "ok", "state": "after"}) + "\n")
    _write(after / MOVED_TO, json.dumps({"index": ["gate-summary", "tool-output"]}) + "\n")
    _write(after / PATTERN_TO, json.dumps({"records": 2, "fmt": "ndjson"}) + "\n")
    _write(after / NO_CONSUMER_ORPHAN, "orphan-bytes\n")
    _write(after / NO_CONSUMER_ADDED, json.dumps({"debug": True, "not_shipped": True}) + "\n")

    _write(
        consumers / TOOL_CONSUMER,
        "#!/usr/bin/env python3\n"
        f'GATE_SUMMARY = "{STABLE_CONSUMED}"\n'
        "def load(root):\n"
        "    return (root / GATE_SUMMARY).read_text(encoding='utf-8')\n",
    )
    _write(
        consumers / WORKFLOW_CONSUMER,
        json.dumps(
            {
                "id": "publish-layout",
                "kind": "workflow",
                "reads": [MOVED_FROM],
                "note": "still points at the pre-move layout-index path",
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        consumers / GATE_CONSUMER,
        "#!/usr/bin/env bash\n"
        f"test -f \"{PATTERN_FROM}\" || exit 2\n",
    )
    _write(
        consumers / PROSE_DOC,
        "# Operator handbook\n\n"
        "After each confirmation run, open `artifacts/layout-index.json` and confirm\n"
        "the produced layout listing. This path is documented only in this handbook;\n"
        "no tool, workflow, or gate opens it. A path referenced only in prose still\n"
        "counts as a consumer.\n",
    )

    return {"before": before, "after": after, "consumers": consumers}


if __name__ == "__main__":
    paths = materialize()
    for k, v in paths.items():
        print(f"{k} {v}")
