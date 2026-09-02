#!/usr/bin/env python3
"""Compare each load-bearing briefing premise to the current artifact bytes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from census import census, json_id_present, walk_json_ids
from tense import briefing_open_collision

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lineage(path: Path) -> dict:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "resolved_url": path.resolve().as_uri(),
        "resolved_url": path.resolve().as_uri(),
        "requested_path": str(path),
        "fetch_timestamp": utc_now(),
        "fetch_timestamp": utc_now(),
        "sha256_of_fetched_bytes": digest,
        "sha256_of_fetched_bytes": digest,
        "bytes": len(raw),
    }


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split_option_arch(root: Path, rels: list[str]) -> tuple[str, str, list[Path]]:
    option_text = ""
    arch_text = ""
    paths: list[Path] = []
    for rel in rels:
        p = root / rel
        paths.append(p)
        text = _read(p)
        name = p.name.upper()
        if "OPTION" in name:
            option_text += text
        else:
            arch_text += text
    return option_text, arch_text, paths


def evaluate_premise(root: Path, premise: dict) -> dict:
    check = str(premise.get("check") or "")
    briefing_path = root / str(premise["briefing_rel"])
    briefing = _read(briefing_path)
    tense = briefing_open_collision(briefing)
    artifacts = list(premise.get("artifact_rels") or [])
    fire = False
    reason = ""
    measurement: dict = {}
    signals: list[dict] = []
    lineage_rows = [lineage(briefing_path)]

    if check == "mnn-collision-open":
        option_text, arch_text, paths = _split_option_arch(root, artifacts)
        for p in paths:
            lineage_rows.append(lineage(p))
        measurement = census(option_text, arch_text)
        fixed = measurement["literal_collision_count"] == 0 and measurement["reprefix_applied"]
        # Stale-open: briefing still presents a FIXED collision as live.
        fire = bool(tense["asserts_open_collision"] and fixed)
        if fire:
            reason = (
                "briefing present-tense open collision while architecture is "
                "MECH-prefixed and literal collision count is 0"
            )
        elif tense["asserts_open_collision"] and not fixed:
            reason = "briefing open-collision claim matches live collision"
        else:
            reason = "briefing does not assert an open collision"
        signals = [
            {
                "id": "S1-briefing-tense",
                "instrument": tense["instrument"],
                "observation": {
                    "asserts_open_collision": tense["asserts_open_collision"],
                    "mech_token_count": tense["mech_token_count"],
                    "collision_line": tense["collision_line"],
                },
            },
            {
                "id": "S2-id-census",
                "instrument": measurement["instrument"],
                "observation": {
                    "literal_collision_count": measurement["literal_collision_count"],
                    "architecture_bare_m_count": measurement["architecture_bare_m_count"],
                    "architecture_mech_count": measurement["architecture_mech_count"],
                    "reprefix_applied": measurement["reprefix_applied"],
                },
            },
        ]
    elif check == "mech-reprefix-applied":
        _, arch_text, paths = _split_option_arch(root, artifacts)
        for p in paths:
            lineage_rows.append(lineage(p))
        measurement = census("", arch_text)
        applied = bool(measurement["reprefix_applied"])
        # Fire when a "current reprefix" claim is false.
        fire = not applied
        reason = (
            "architecture still has bare M-NN tokens"
            if fire
            else "architecture is MECH-prefixed with zero bare M-NN"
        )
        signals = [
            {
                "id": "S1-mech-token-census",
                "instrument": measurement["instrument"],
                "observation": {
                    "architecture_mech_count": measurement["architecture_mech_count"],
                    "reprefix_applied": applied,
                },
            },
            {
                "id": "S2-bare-m-absence",
                "instrument": "python-re-negative-lookbehind-bare-M",
                "observation": {
                    "architecture_bare_m_count": measurement["architecture_bare_m_count"]
                },
            },
        ]
    elif check == "json-unit-id-present":
        target = str(premise.get("unit_id") or "")
        path = root / artifacts[0]
        lineage_rows.append(lineage(path))
        raw = path.read_text(encoding="utf-8")
        regex_hit = json_id_present(raw, target)
        parsed = json.loads(raw)
        walk_hit = target in walk_json_ids(parsed)
        measurement = {
            "unit_id": target,
            "regex_hit": regex_hit,
            "json_walk_hit": walk_hit,
        }
        fire = not (regex_hit and walk_hit)
        reason = (
            f"unit id {target} absent from catalog"
            if fire
            else f"unit id {target} present in catalog (json walk + regex)"
        )
        signals = [
            {
                "id": "S1-json-walk",
                "instrument": "json-loads-recursive-id-walk",
                "observation": {"json_walk_hit": walk_hit},
            },
            {
                "id": "S2-raw-regex",
                "instrument": "raw-bytes-quoted-id-regex",
                "observation": {"regex_hit": regex_hit},
            },
        ]
    else:
        raise ValueError(f"unknown check {check}")

    return {
        "id": premise.get("id"),
        "text": premise.get("text"),
        "asserted_status": premise.get("asserted_status"),
        "check": check,
        "fire": fire,
        "verdict": "STALE-OPEN" if fire and check == "mnn-collision-open" else (
            "FALSE-CURRENT" if fire else "SILENT"
        ),
        "reason": reason,
        "expect_fire": premise.get("expect_fire"),
        "tense": tense,
        "measurement": measurement,
        "signals": signals,
        "source_lineage": lineage_rows,
        "briefing_path": _rel(briefing_path),
    }


def evaluate_pack(root: Path) -> dict:
    pack = json.loads((root / "pack.json").read_text(encoding="utf-8"))
    rows = [evaluate_premise(root, p) for p in pack.get("premises") or []]
    mismatches = [
        r["id"]
        for r in rows
        if r.get("expect_fire") is not None and bool(r["fire"]) != bool(r["expect_fire"])
    ]
    return {
        "pack_id": pack.get("id"),
        "kind": pack.get("kind"),
        "root": str(root),
        "premises": rows,
        "fired_ids": [r["id"] for r in rows if r["fire"]],
        "silent_ids": [r["id"] for r in rows if not r["fire"]],
        "control_mismatches": mismatches,
        "ok": not mismatches,
    }


def named_inputs_present() -> list[dict]:
    rels = [
        "_USER-PROMPTS.md",
        "command-center/sources/REGISTER.md",
        "command-center/CLAIM-REGISTRY.json",
        "17-DECISION-LOG.md",
        "command-center/OPTION-ID-RESOLUTION.json",
        "13-ARCHITECTURE-CANDIDATES.md",
        "07-OPTION-UNIVERSE.md",
    ]
    rows = []
    for rel in rels:
        p = REPO / rel
        rows.append({"path": rel, "present": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0})
    return rows
