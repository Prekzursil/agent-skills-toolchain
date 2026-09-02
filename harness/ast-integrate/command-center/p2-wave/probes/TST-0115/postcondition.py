"""Independent postconditions: existence, parse, content. Exit 0 is not enough."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
QUICKSTART_DOC = REPO / "docs" / "quickstart.md"
ADVANCED_DOC = REPO / "docs" / "advanced-workflows.md"
ID_RE = re.compile(r"ast-examples run --id ([A-Za-z0-9-]+)")


def extract_ids(markdown: Path) -> list[str]:
    text = markdown.read_text(encoding="utf-8")
    ids = ID_RE.findall(text)
    if not ids:
        raise ValueError(f"no example ids in {markdown}")
    return ids


def documented_quickstart_ids() -> list[str]:
    return extract_ids(QUICKSTART_DOC)


def documented_advanced_ids() -> list[str]:
    return extract_ids(ADVANCED_DOC)


def load_artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    if path.stat().st_size <= 0:
        raise ValueError(f"empty artifact {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"artifact is not an object: {path}")
    return doc


def _errors(example_id: str, doc: dict[str, Any]) -> list[str]:
    err: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            err.append(msg)

    if example_id == "quickstart-hello":
        tally = doc.get("tally") if isinstance(doc.get("tally"), dict) else {}
        need(doc.get("kind") == "council-run", "kind")
        need(doc.get("spec_id") == "quickstart-hello", "spec_id")
        need(doc.get("sentinel") == "SUCCESS:COUNCIL", "sentinel")
        need(doc.get("status") == "SUCCESS", "status")
        need(tally.get("yes") == 2, "tally.yes")
        need(tally.get("no") == 0, "tally.no")
        need(doc.get("origin") == "wheel", "origin-wheel")
    elif example_id == "quickstart-presets":
        presets = doc.get("presets") if isinstance(doc.get("presets"), list) else []
        ids = {p.get("id") for p in presets if isinstance(p, dict)}
        need(doc.get("kind") == "preset-catalog", "kind")
        need(doc.get("count") == 3, "count")
        need(ids >= {"C-M01", "C-02", "C-03"}, "preset-ids")
        need(doc.get("origin") == "wheel", "origin-wheel")
    elif example_id == "advanced-resume":
        need(doc.get("kind") == "council-run", "kind")
        need(doc.get("resumed") is True, "resumed")
        need(doc.get("spec_id") == "advanced-resume", "spec_id")
        need(doc.get("checkpoint_id") == "ck-adv-1", "checkpoint_id")
        need(doc.get("deciding_rule") == "majority-quorum", "deciding_rule")
        need(doc.get("sentinel") == "SUCCESS:COUNCIL", "sentinel")
        need(doc.get("origin") == "wheel", "origin-wheel")
    elif example_id == "advanced-import-dag":
        units = doc.get("units") if isinstance(doc.get("units"), list) else []
        need(doc.get("kind") == "typed-workflow", "kind")
        need(doc.get("source_adapter") == "generic_dag", "source_adapter")
        need(len(units) == 2, "unit-count")
        for unit in units:
            if not isinstance(unit, dict):
                err.append("unit-not-object")
                continue
            need(unit.get("wait") is True, f"{unit.get('id')}.wait")
            need(int(unit.get("timeout_seconds") or 0) > 0, f"{unit.get('id')}.timeout")
            need(bool(unit.get("prompt_file")), f"{unit.get('id')}.prompt_file")
            argv = unit.get("argv") if isinstance(unit.get("argv"), list) else []
            need("--prompt" not in argv, f"{unit.get('id')}.no-inline-prompt")
        need(doc.get("origin") == "wheel", "origin-wheel")
    else:
        err.append(f"unknown-example:{example_id}")
    return err


def check_artifact(example_id: str, path: Path) -> list[str]:
    try:
        doc = load_artifact(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, FileNotFoundError) as exc:
        return [f"unreadable:{type(exc).__name__}:{exc}"]
    return _errors(example_id, doc)


def check_doc_object(example_id: str, doc: dict[str, Any]) -> list[str]:
    return _errors(example_id, doc)
