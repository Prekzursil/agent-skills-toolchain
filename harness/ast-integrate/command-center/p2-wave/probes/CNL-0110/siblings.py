#!/usr/bin/env python3
"""On-disk sibling catalog for nearest-neighbour comparison.

12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree. The only
12-COUNCIL-sourced body transcribed here is council.preset.catalog-class.editable
from command-center/p2-wave/probes/ARC-0003/samples.json. C13/C14 are the
CNL-0102 catalog-cited reconstruction of this unit's two arms, not library bytes.
Probe fixtures that happen to be named 12-COUNCIL-*.json are not the library.
"""
from __future__ import annotations

from pathlib import Path

from preset import PROFILE_AXES, distance, fingerprint, preset as load_preset

REPO = Path(__file__).resolve().parents[4]

LIBRARY_CANDIDATES = (
    REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "sources" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)


def library_search() -> dict:
    hits = []
    per_name = []
    for path in LIBRARY_CANDIDATES:
        present = path.is_file()
        rel = path.relative_to(REPO).as_posix()
        per_name.append({"path": rel, "present": present})
        if present:
            hits.append(rel)
    return {
        "twelve_council_present": bool(hits),
        "search_paths": [p.relative_to(REPO).as_posix() for p in LIBRARY_CANDIDATES],
        "glob_hits": hits,
        "per_name": per_name,
        "search_space_note": (
            "Library file absent at the three well-known paths. Nearest "
            "12-COUNCIL sibling is computed over the on-disk transcription of "
            "council.preset.catalog-class.editable (ARC-0003 samples.json), not "
            "over the missing 72-record file, and not over other units' probe "
            "fixtures that reuse the library filename. This cannot prove "
            "uniqueness among the unread 72."
        ),
    }


def catalog_class_editable_fp() -> dict:
    return {
        "role_set": tuple(sorted(["Architect", "Skeptic", "Pragmatist", "Critic"])),
        "protocol_schedule": ("single-protocol",),
        "elicit_voting_rule": "unanimous-or-record-dissent",
        "reconcile_voting_rule": "unanimous-or-record-dissent",
        "elicit_stop": "max_rounds==8",
        "reconcile_stop": "max_rounds==8",
        "phase_split": False,
        "unreconcilable_outcome": "BLOCKED",
        "balance_metric": "none-four-voice-fixed",
    }


def forecast_elicitation_fp() -> dict:
    return {
        "role_set": tuple(sorted(["forecaster", "resolver", "scorer"])),
        "protocol_schedule": ("p-elicit-forecasts",),
        "elicit_voting_rule": "proper-scoring-rule",
        "reconcile_voting_rule": "proper-scoring-rule",
        "elicit_stop": "every-forecast-has-resolution-date",
        "reconcile_stop": "every-forecast-has-resolution-date",
        "phase_split": False,
        "unreconcilable_outcome": "unscored-forecast-rejected",
        "balance_metric": "none-expert-panel",
    }


def c13_elicitation_fp() -> dict:
    """CNL-0102 named family preset C13 (catalog-cited reconstruction)."""
    return {
        "role_set": tuple(sorted(["Proposer", "Mediator", "Skeptic", "Clerk"])),
        "protocol_schedule": ("P23", "P01", "P22"),
        "elicit_voting_rule": "approval",
        "reconcile_voting_rule": "approval",
        "elicit_stop": "stakeholder_coverage >= 0.90 AND max_rounds == 5",
        "reconcile_stop": "stakeholder_coverage >= 0.90 AND max_rounds == 5",
        "phase_split": False,
        "unreconcilable_outcome": "unspecified",
        "balance_metric": "stakeholder_coverage",
    }


def c14_reconciliation_fp() -> dict:
    """CNL-0102 named family preset C14 (catalog-cited reconstruction)."""
    return {
        "role_set": tuple(sorted(["Mediator", "Advocate", "Skeptic", "Owner"])),
        "protocol_schedule": ("P12", "P09", "P56"),
        "elicit_voting_rule": "consent",
        "reconcile_voting_rule": "consent",
        "elicit_stop": "unreconciled_pairs == 0 OR outcome == irreducible_disagreement",
        "reconcile_stop": "unreconciled_pairs == 0 OR outcome == irreducible_disagreement",
        "phase_split": False,
        "unreconcilable_outcome": "irreducible_disagreement",
        "balance_metric": "none",
    }


def sibling_rows() -> list[dict]:
    return [
        {
            "id": "council.preset.catalog-class.editable",
            "source": "12-COUNCIL-transcription:ARC-0003/samples.json",
            "twelve_council_sourced": True,
            "fp": catalog_class_editable_fp(),
        },
        {
            "id": "C13",
            "source": "CNL-0102-catalog-cited-reconstruction:requirements-elicitation",
            "twelve_council_sourced": False,
            "fp": c13_elicitation_fp(),
        },
        {
            "id": "C14",
            "source": "CNL-0102-catalog-cited-reconstruction:requirements-conflict-reconciliation",
            "twelve_council_sourced": False,
            "fp": c14_reconciliation_fp(),
        },
        {
            "id": "council.preset.forecasting.expert-elicitation",
            "source": "CNL-0112-catalog-question-reconstruction",
            "twelve_council_sourced": False,
            "fp": forecast_elicitation_fp(),
        },
        {
            "id": "NEG.name-clone-of-cnl-0110",
            "source": "planted-mechanism-duplicate",
            "twelve_council_sourced": False,
            "fp": fingerprint(load_preset()),
            "planted_duplicate": True,
        },
    ]


def _jsonable_fp(fp: dict) -> dict:
    out = {}
    for k, v in fp.items():
        if isinstance(v, tuple):
            out[k] = list(v)
        else:
            out[k] = v
    return out


def nearest(ours: dict | None = None) -> dict:
    ours = ours or fingerprint(load_preset())
    rows = []
    for s in sibling_rows():
        dist, differ = distance(ours, s["fp"])
        rows.append(
            {
                "id": s["id"],
                "source": s["source"],
                "twelve_council_sourced": s["twelve_council_sourced"],
                "planted_duplicate": bool(s.get("planted_duplicate")),
                "distance": dist,
                "axes_differ": differ,
                "axes_same": [a for a in PROFILE_AXES if a not in differ],
            }
        )
    real = [r for r in rows if not r["planted_duplicate"]]
    sourced = [r for r in real if r["twelve_council_sourced"]]
    sourced.sort(key=lambda r: (r["distance"], r["id"]))
    real.sort(key=lambda r: (r["distance"], r["id"]))
    planted = next(r for r in rows if r["planted_duplicate"])
    return {
        "ours": _jsonable_fp(ours),
        "rows": rows,
        "nearest_twelve_council_sourced": sourced[0] if sourced else None,
        "nearest_on_disk_excluding_planted": real[0] if real else None,
        "planted_duplicate": planted,
        "library": library_search(),
    }
