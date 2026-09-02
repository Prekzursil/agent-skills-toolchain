"""Largest fixture workflow for IMP-0142 dry-run probes."""

from __future__ import annotations

from typing import Any


def largest_workflow() -> dict[str, Any]:
    """A wide workflow: 64 units, 4 fan-outs of 16, pipeline + barriers.

    This is the 'largest fixture workflow' named in the catalog row. Cardinality
    is declared (max_cardinality=16 per fan-out) so dry-run can resolve bounds
    without spawning the 64 units.
    """
    units: list[dict[str, Any]] = []
    rails = ("opus", "sonnet", "codex")
    for i in range(64):
        rail = rails[i % 3]
        units.append(
            {
                "id": f"u{i:02d}",
                "title": f"largest-fixture unit {i:02d}",
                "routing": {
                    "rail": rail,
                    "fallbacks": ["sonnet"] if rail != "sonnet" else ["opus"],
                },
            }
        )
    fanouts = []
    for g in range(4):
        ids = [f"u{i:02d}" for i in range(g * 16, (g + 1) * 16)]
        fanouts.append(
            {
                "type": "fan_out",
                "id": f"fo{g}",
                "unit_ids": ids,
                "max_cardinality": 16,
            }
        )
    barriers = [
        {"type": "barrier", "id": f"b{g}", "wait_for": [f"fo{g}"]} for g in range(4)
    ]
    pipeline = {
        "type": "pipeline",
        "id": "pipe-main",
        "stages": ["fo0", "b0", "fo1", "b1", "fo2", "b2", "fo3", "b3"],
    }
    return {
        "id": "wf-largest-imp0142",
        "spec_version": "1",
        "params": [
            {
                "id": "region",
                "kind": "enum",
                "enum": ["us", "eu", "ap"],
                "default": "us",
                "required": False,
            },
            {
                "id": "batch_size",
                "kind": "integer",
                "default": 8,
                "required": False,
            },
            {
                "id": "api_token",
                "kind": "secret_ref",
                "required": True,
                "ref": {"source": "env", "name": "IMP0142_API_TOKEN"},
            },
        ],
        "units": units,
        "nodes": fanouts + barriers + [pipeline],
    }


def dry_run_params() -> dict[str, Any]:
    """Caller bindings. secret_ref stays a pointer; no literal token."""
    return {
        "region": "eu",
        "batch_size": 16,
        "api_token": {"source": "env", "name": "IMP0142_API_TOKEN"},
    }
