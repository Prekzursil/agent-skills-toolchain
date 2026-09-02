"""Produce documented example artifacts. Exit 0 is not the postcondition."""
from __future__ import annotations

import json
from pathlib import Path

from ast_examples import ORIGIN


EXAMPLE_IDS: tuple[str, ...] = (
    "quickstart-hello",
    "quickstart-presets",
    "advanced-resume",
    "advanced-import-dag",
)


def catalog() -> list[dict]:
    """Every example id this package can produce, with its artifact path."""
    return [
        {"id": example_id, "artifact": f"artifacts/{example_id}.json", "origin": ORIGIN}
        for example_id in EXAMPLE_IDS
    ]


def _write(profile: str | Path, example_id: str, doc: dict) -> Path:
    root = Path(profile)
    dest = root / "artifacts" / f"{example_id}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(doc)
    payload["origin"] = ORIGIN
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def run_example(example_id: str, profile: str | Path) -> int:
    if example_id == "quickstart-hello":
        _write(
            profile,
            example_id,
            {
                "kind": "council-run",
                "spec_id": "quickstart-hello",
                "sentinel": "SUCCESS:COUNCIL",
                "status": "SUCCESS",
                "tally": {"yes": 2, "no": 0},
            },
        )
        return 0
    if example_id == "quickstart-presets":
        _write(
            profile,
            example_id,
            {
                "kind": "preset-catalog",
                "count": 3,
                "presets": [
                    {"id": "C-M01"},
                    {"id": "C-02"},
                    {"id": "C-03"},
                ],
            },
        )
        return 0
    if example_id == "advanced-resume":
        _write(
            profile,
            example_id,
            {
                "kind": "council-run",
                "resumed": True,
                "spec_id": "advanced-resume",
                "checkpoint_id": "ck-adv-1",
                "deciding_rule": "majority-quorum",
                "sentinel": "SUCCESS:COUNCIL",
                "status": "SUCCESS",
            },
        )
        return 0
    if example_id == "advanced-import-dag":
        _write(
            profile,
            example_id,
            {
                "kind": "typed-workflow",
                "source_adapter": "generic_dag",
                "units": [
                    {
                        "id": "u1",
                        "wait": True,
                        "timeout_seconds": 30,
                        "prompt_file": "prompts/u1.md",
                        "argv": ["--file", "prompts/u1.md"],
                    },
                    {
                        "id": "u2",
                        "wait": True,
                        "timeout_seconds": 45,
                        "prompt_file": "prompts/u2.md",
                        "argv": ["--file", "prompts/u2.md"],
                    },
                ],
            },
        )
        return 0
    raise SystemExit(f"unknown example id: {example_id}")
