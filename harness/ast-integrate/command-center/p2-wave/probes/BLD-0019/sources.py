#!/usr/bin/env python3
"""Locate live BLD-0019 inputs; write fixture stand-ins when live files are absent.

Ground truth for namespaces is the option-universe and architecture-candidate
artifacts (post-fix MECH-N). The decision log is loaded only as a STALE
document to be contradicted, never as a namespace resolver.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

FAMILY_M_NUMS = tuple(list(range(1, 32)) + [40, 41])
MECH_NUMS = tuple(range(1, 39))
CTRL_DUAL = "CTRL-DUAL-1"
CTRL_MISSING = "CTRL-MISSING-1"

LIVE_UNIVERSE = (
    "07-OPTION-UNIVERSE.json",
    "07-OPTION-UNIVERSE.md",
    "command-center/07-OPTION-UNIVERSE.json",
    "command-center/07-OPTION-UNIVERSE.md",
)
LIVE_DOC13 = (
    "13-ARCHITECTURE-CANDIDATES.md",
    "command-center/13-ARCHITECTURE-CANDIDATES.md",
)
LIVE_LOG = (
    "17-DECISION-LOG.md",
    "command-center/17-DECISION-LOG.md",
)
LIVE_RES = (
    "command-center/OPTION-ID-RESOLUTION.json",
    "OPTION-ID-RESOLUTION.json",
)
LIVE_CC24 = "command-center/receipts/CC-0024.json"
LIVE_SYN28 = "command-center/synthesis/SYN-0028.option-closure.json"
LIVE_CATALOG = "command-center/WORK-UNIT-CATALOG.json"


def first_live(relatives: tuple[str, ...]) -> Path | None:
    for rel in relatives:
        path = REPO / rel
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _parse_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def has_disposition_lists(path: Path) -> bool:
    """True only when the file is a terminal-disposition list, not a census.

    Live command-center/OPTION-ID-RESOLUTION.json on this worktree is the
    CC-0021 namespace census (33/38/31/7/2). It has no implemented /
    superseded / rejected_with_owner_reasoning arrays, so using it as the
    closer's disposition source starves the planted dual-disposition control.
    """
    doc = _parse_json(path)
    if not isinstance(doc, dict):
        return False
    return any(
        k in doc
        for k in ("implemented", "superseded", "rejected_with_owner_reasoning")
    )


def family_m_ids() -> list[str]:
    return [f"M-{n}" for n in FAMILY_M_NUMS]


def mech_ids() -> list[str]:
    return [f"MECH-{n}" for n in MECH_NUMS]


def universe_only_ids() -> list[str]:
    return ["M-40", "M-41"]


def doc13_only_ids() -> list[str]:
    return [f"MECH-{n}" for n in range(32, 39)]


def overlap_nums() -> list[int]:
    return list(range(1, 32))


def _universe_json() -> dict:
    cards = []
    for n in FAMILY_M_NUMS:
        cards.append(
            {
                "id": f"M-{n}",
                "family": "M",
                "title": f"option-universe family M card {n}",
                "kind": "option",
            }
        )
    cards.append(
        {
            "id": CTRL_DUAL,
            "family": "CTRL",
            "title": "planted dual-disposition control card",
            "kind": "control",
        }
    )
    return {
        "reconstruction": "catalog-arithmetic-family-M",
        "catalog_claimed_total": 283,
        "family_m_count": 33,
        "note": (
            "Live 07-OPTION-UNIVERSE.{md,json} is absent on this worktree. "
            "Family M is reconstructed from the catalog-stated 33/38/31/7/2 "
            "arithmetic (CC-0021 evidence: counts 33/38/31/7/2). The other "
            "250 option ids cannot be named without the corpus."
        ),
        "cards": cards,
    }


def _doc13_md() -> str:
    lines = [
        "# 13 Architecture Candidates",
        "",
        "Post-fix namespace since 2026-08-07: every mechanism card id uses the",
        "MECH- prefix. This document carries zero bare option-family tokens.",
        "",
    ]
    for n in MECH_NUMS:
        lines.append(f"## MECH-{n}")
        lines.append("")
        lines.append(
            f"Mechanism card {n}. Architecture-candidate mechanism, post-fix id."
        )
        lines.append("")
    return "\n".join(lines) + "\n"


def _decision_log_md() -> str:
    lines = [
        "# 17 Decision log",
        "",
        "This log is stale relative to the 2026-08-07 re-prefix of architecture",
        "candidate identifiers. Do not treat present-tense collision prose as",
        "live ground truth.",
        "",
    ]
    while len(lines) < 174:
        lines.append(
            f"Queued follow-up {len(lines)}: option-id namespace work remains open."
        )
    lines.append(
        "The 31-way option-id collision between universe family M and "
        "architecture-candidate mechanism cards is live and Queued as P2-09."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def _resolution_json() -> dict:
    return {
        "rule": (
            "POST-FIX. Resolve identifiers against 07-OPTION-UNIVERSE and "
            "13-ARCHITECTURE-CANDIDATES. 17-DECISION-LOG still states the "
            "collision in the present tense and must not be used as a "
            "namespace resolver."
        ),
        "namespaces": [
            {
                "id": "option-universe-family-m",
                "prefix": "M",
                "declaring_artifact": "07-OPTION-UNIVERSE",
                "ids": family_m_ids(),
            },
            {
                "id": "doc13-mechanisms",
                "prefix": "MECH",
                "declaring_artifact": "13-ARCHITECTURE-CANDIDATES",
                "ids": mech_ids(),
            },
        ],
        "implemented": [CTRL_DUAL],
        "superseded": [],
        "rejected_with_owner_reasoning": [],
    }


def _dual_overlay() -> dict:
    return {
        "rejected_with_owner_reasoning": {
            CTRL_DUAL: {
                "owner_decision": "OQ-CONTROL",
                "reason": "planted second terminal disposition for AMBIGUOUS control",
            }
        }
    }


def ensure_fixtures() -> dict[str, Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    paths = {
        "universe": FIX / "07-OPTION-UNIVERSE.json",
        "doc13": FIX / "13-ARCHITECTURE-CANDIDATES.md",
        "log": FIX / "17-DECISION-LOG.md",
        "resolution": FIX / "OPTION-ID-RESOLUTION.json",
        "dual": FIX / "dual-overlay.json",
    }
    paths["universe"].write_text(
        json.dumps(_universe_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    paths["doc13"].write_text(_doc13_md(), encoding="utf-8")
    paths["log"].write_text(_decision_log_md(), encoding="utf-8")
    paths["resolution"].write_text(
        json.dumps(_resolution_json(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["dual"].write_text(
        json.dumps(_dual_overlay(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return paths


def source_row(path: Path | None, used_for: str, origin: str, fallback: str) -> dict:
    if path is not None and path.is_file():
        try:
            rel = path.relative_to(REPO).as_posix()
        except ValueError:
            rel = str(path)
        return {
            "path": rel,
            "present": True,
            "used_for": used_for,
            "origin": origin,
        }
    return {
        "path": fallback,
        "present": False,
        "used_for": used_for,
        "origin": "absent",
    }


def load_sources() -> dict:
    fixtures = ensure_fixtures()
    live_u = first_live(LIVE_UNIVERSE)
    live_d = first_live(LIVE_DOC13)
    live_l = first_live(LIVE_LOG)
    live_r_raw = first_live(LIVE_RES)
    live_r_is_disp = live_r_raw is not None and has_disposition_lists(live_r_raw)
    live_r = live_r_raw if live_r_is_disp else None
    cc24 = REPO / LIVE_CC24
    syn = REPO / LIVE_SYN28
    catalog = REPO / LIVE_CATALOG

    universe_path = live_u if live_u is not None else fixtures["universe"]
    doc13_path = live_d if live_d is not None else fixtures["doc13"]
    log_path = live_l if live_l is not None else fixtures["log"]
    res_path = live_r if live_r is not None else fixtures["resolution"]

    def used(live: Path | None, fixture: Path, used_for: str, live_name: str) -> dict:
        path = live if live is not None else fixture
        row = source_row(
            path,
            used_for,
            "live" if live is not None else "fixture-reconstructed",
            live_name,
        )
        row["live_lookup"] = live_name
        row["live_present"] = live is not None
        return row

    return {
        "repo": REPO,
        "here": HERE,
        "universe_path": universe_path,
        "doc13_path": doc13_path,
        "log_path": log_path,
        "resolution_path": res_path,
        "dual_path": fixtures["dual"],
        "catalog_path": catalog if catalog.is_file() else None,
        "cc24_path": cc24 if cc24.is_file() else None,
        "syn28_path": syn if syn.is_file() else None,
        "meta": {
            "option_universe": used(
                live_u,
                fixtures["universe"],
                "option-id declarations (family M and any other families present)",
                LIVE_UNIVERSE[0],
            ),
            "architecture_candidates": used(
                live_d,
                fixtures["doc13"],
                "MECH-N mechanism-card declarations (post-fix namespace)",
                LIVE_DOC13[0],
            ),
            "decision_log": used(
                live_l,
                fixtures["log"],
                "stale-prose negative control only; not a namespace resolver",
                LIVE_LOG[0],
            ),
            "option_id_resolution": used(
                live_r,
                fixtures["resolution"],
                "explicit implemented/superseded/rejected lists when present",
                LIVE_RES[0],
            ),
            "option_id_resolution_live_file": {
                **source_row(
                    live_r_raw,
                    (
                        "terminal-disposition lists"
                        if live_r_is_disp
                        else "namespace census only; not a terminal-disposition list"
                    ),
                    "live" if live_r_raw is not None else "absent",
                    LIVE_RES[0],
                ),
                "has_disposition_lists": live_r_is_disp,
            },
            "catalog": source_row(
                catalog if catalog.is_file() else None,
                "join: work-unit mentions; never a declaring registry for MECH-N",
                "live",
                LIVE_CATALOG,
            ),
            "cc_0024": source_row(
                cc24 if cc24.is_file() else None,
                "numeric-floor records consumed, not re-extracted",
                "live" if cc24.is_file() else "absent",
                LIVE_CC24,
            ),
            "syn_0028": source_row(
                syn if syn.is_file() else None,
                "terminal option-id closure; wins on conflict",
                "live" if syn.is_file() else "absent",
                LIVE_SYN28,
            ),
        },
        "used_fixture_universe": live_u is None,
        "used_fixture_doc13": live_d is None,
        "used_fixture_log": live_l is None,
    }
