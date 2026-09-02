"""Fixture information-partition lattice and per-seat stream assembly.

Blind first-pass, staged release, and fishbowl observer are all the same
type: a seat may see a bundle iff the bundle is unpartitioned or the
seat is in the bundle's allowed set. Leak paths (shared transcript,
synthesis, tool results) are assembled explicitly so a scan of delivered
bytes is the measurement, not a read of the config.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from canaries import CONTROL_CANARY, FACT_SENTENCE, PARTITION_CANARY

LATTICE_ID = "cnf0093-who-may-see-what-when"
OWNING_SEAT = "seat-a"
NON_OWNING = ("seat-b", "seat-c")
UNPARTITIONED_FIELD = "shared-briefing"

PRIVATE_BUNDLE = (
    f"Private evidence for {OWNING_SEAT} only. Token {PARTITION_CANARY}. "
    f"Fact: {FACT_SENTENCE}."
)
SHARED_BUNDLE = (
    f"Unpartitioned briefing visible to every seat. Control token "
    f"{CONTROL_CANARY}. Topic: whether the catalog class should stay "
    f"discovery-only this round."
)
PUBLIC_TALK = (
    "Round-1 independent briefs: seat-a argues discovery-only; seat-b "
    "asks for a rollback rehearsal; seat-c wants a freeze hook named."
)
PUBLIC_SYNTHESIS = (
    "Moderator synthesis: three seats remain split on discovery-only "
    "versus rollback rehearsal. No private evidence is restated."
)
PUBLIC_TOOL = (
    "tool:catalog.lookup result for all seats: workflow "
    "wf.catalog-class.discovery-only is registered."
)

# Laundered leak: restates the private fact without copying PARTITION_CANARY.
LAUNDERED_SYNTHESIS = (
    "Moderator synthesis later restated that the magenta widget serial "
    "is QZ4419BETA, which only partition P-A was supposed to hold."
)
VERBATIM_TRANSCRIPT_LEAK = (
    PUBLIC_TALK + f" Seat-a accidentally pasted {PARTITION_CANARY} into the shared log."
)
TOOL_LEAK = (
    PUBLIC_TOOL + f" Shared tool result also echoed {PARTITION_CANARY} from P-A."
)


def spec_holding() -> dict[str, Any]:
    return {
        "id": "holding",
        "redaction": True,
        "bundles": [
            {
                "id": "bundle-pa",
                "partition_id": "P-A",
                "allowed_seats": [OWNING_SEAT],
                "text": PRIVATE_BUNDLE,
            },
            {
                "id": "bundle-shared",
                "partition_id": None,
                "allowed_seats": [OWNING_SEAT, *NON_OWNING],
                "text": SHARED_BUNDLE,
            },
        ],
        "shared_transcript": PUBLIC_TALK,
        "synthesis": PUBLIC_SYNTHESIS,
        "tool_results": PUBLIC_TOOL,
    }


def spec_leak_transcript() -> dict[str, Any]:
    spec = spec_holding()
    spec["id"] = "leak-shared-transcript"
    spec["shared_transcript"] = VERBATIM_TRANSCRIPT_LEAK
    return spec


def spec_leak_synthesis() -> dict[str, Any]:
    spec = spec_holding()
    spec["id"] = "leak-synthesis-paraphrase"
    spec["synthesis"] = LAUNDERED_SYNTHESIS
    return spec


def spec_leak_tools() -> dict[str, Any]:
    spec = spec_holding()
    spec["id"] = "leak-tool-results"
    spec["tool_results"] = TOOL_LEAK
    return spec


def spec_redaction_disabled() -> dict[str, Any]:
    spec = spec_holding()
    spec["id"] = "redaction-disabled"
    spec["redaction"] = False
    return spec


def _bundle_visible(seat: str, bundle: dict, redaction: bool) -> bool:
    if not redaction:
        return True
    if bundle.get("partition_id") is None:
        return True
    return seat in (bundle.get("allowed_seats") or [])


def assemble(spec: dict[str, Any]) -> dict[str, Any]:
    """Deliver per-seat context plus the three leak-path streams."""
    spec = deepcopy(spec)
    redaction = bool(spec.get("redaction", True))
    seats = [OWNING_SEAT, *NON_OWNING]
    per_seat: dict[str, dict[str, str]] = {}
    for seat in seats:
        visible = [
            b["text"]
            for b in spec["bundles"]
            if _bundle_visible(seat, b, redaction)
        ]
        private_ctx = "\n".join(visible)
        per_seat[seat] = {
            "private_context": private_ctx,
            "shared_transcript": spec["shared_transcript"],
            "synthesis": spec["synthesis"],
            "tool_results": spec["tool_results"],
        }
    return {
        "run_id": spec["id"],
        "redaction": redaction,
        "lattice_id": LATTICE_ID,
        "owning_seat": OWNING_SEAT,
        "non_owning_seats": list(NON_OWNING),
        "unpartitioned_field": UNPARTITIONED_FIELD,
        "seats": per_seat,
        "shared_transcript": spec["shared_transcript"],
        "synthesis": spec["synthesis"],
        "tool_results": spec["tool_results"],
    }


def non_owning_streams(assembled: dict[str, Any]) -> list[dict]:
    """Every stream a non-owning participant can read, plus shared stages."""
    rows: list[dict] = []
    for seat in assembled["non_owning_seats"]:
        view = assembled["seats"][seat]
        for stream, text in view.items():
            rows.append(
                {
                    "stream": stream,
                    "participant": seat,
                    "text": text,
                    "path": f"{assembled['run_id']}/{seat}/{stream}",
                }
            )
    for stream in ("shared_transcript", "synthesis", "tool_results"):
        rows.append(
            {
                "stream": f"stage:{stream}",
                "participant": "shared-stage",
                "text": assembled[stream],
                "path": f"{assembled['run_id']}/stage/{stream}",
            }
        )
    return rows


def owning_streams(assembled: dict[str, Any]) -> list[dict]:
    seat = assembled["owning_seat"]
    view = assembled["seats"][seat]
    return [
        {
            "stream": stream,
            "participant": seat,
            "text": text,
            "path": f"{assembled['run_id']}/{seat}/{stream}",
        }
        for stream, text in view.items()
    ]


def live_partition_module(repo) -> dict[str, Any]:
    rel = "tools/council/integrity/partition.py"
    path = repo / rel
    return {
        "path": rel,
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
    }
