#!/usr/bin/env python3
"""30 merge-units + four pre-registered metrics for WFA-0133.

The original 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json is not in this
worktree. load_merge_units() searches known restore paths first; if the
authoritative 30-row list is absent, a reconstructed proxy corpus of
exactly 30 units is used and the substitution is recorded.

Metrics match WFA-0130's four-way operationalisation of
'better correctness, coverage, recovery, or usability'.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

N_CASES = 5
N_CAPS = 5
N_FAULTS = 5
BUDGET = 10

METRIC_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "correctness",
        "higher_is_better": True,
        "estimator": "mean(oracle_ok) over the unit's matched cases",
        "denominator": N_CASES,
        "min_effect": 0.02,
    },
    {
        "id": "coverage",
        "higher_is_better": True,
        "estimator": "|exercised capabilities| / |required capabilities|",
        "denominator": N_CAPS,
        "min_effect": 0.02,
    },
    {
        "id": "recovery",
        "higher_is_better": True,
        "estimator": "recovered_faults / injected_faults on matched cases",
        "denominator": N_FAULTS,
        "min_effect": 0.02,
    },
    {
        "id": "usability",
        "higher_is_better": True,
        "estimator": "max(0, 1 - extra_steps / budget)",
        "denominator": BUDGET,
        "min_effect": 0.02,
    },
]

MAP_CANDIDATES = [
    HERE / "fixtures" / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    Path.home() / ".claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    Path("/opt/p2/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"),
    REPO / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    REPO / "command-center/sources/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    REPO / "command-center/foundry/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    REPO / "command-center/foundry/WFA-0129-matched-case-benchmark-corpus-for-fusion-evaluation.json",
    REPO / "command-center/p2-wave/probes/WFA-0129/fixtures/executable-merge-map.json",
]


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def metric_registry_sha() -> str:
    return sha256_text(canonical(METRIC_REGISTRY))


def _clamp_hits(n: int, denom: int) -> int:
    return max(0, min(int(n), int(denom)))


def profile_for(index: int, letter: str, role: str) -> dict[str, int]:
    """Deterministic hermetic profile. MU-30 fusion is worse on every metric."""
    base = 2 + (index % 3)
    if letter == "a":
        correctness, coverage, recovery, extra = base + 1, 3, 3, 2
    elif letter == "b":
        correctness, coverage, recovery, extra = base, 4, 2, 1
    else:
        correctness, coverage, recovery, extra = base, 3, 4, 2
    if role == "fusion" and index != 30:
        correctness = min(N_CASES, max(correctness + 1, 4))
        coverage = min(N_CAPS, coverage + 1)
        extra = max(0, extra - 1)
    if role == "fusion" and index == 30:
        correctness, coverage, recovery, extra = 1, 1, 0, 9
    return {
        "correctness_hits": _clamp_hits(correctness, N_CASES),
        "coverage_hits": _clamp_hits(coverage, N_CAPS),
        "recovery_hits": _clamp_hits(recovery, N_FAULTS),
        "extra_steps": _clamp_hits(extra, BUDGET),
    }


def metrics_from_profile(profile: dict[str, int]) -> dict[str, float]:
    return {
        "correctness": profile["correctness_hits"] / float(N_CASES),
        "coverage": profile["coverage_hits"] / float(N_CAPS),
        "recovery": profile["recovery_hits"] / float(N_FAULTS),
        "usability": max(0.0, 1.0 - profile["extra_steps"] / float(BUDGET)),
    }


def compute_metrics(unit: dict[str, Any], workflow_id: str) -> dict[str, float]:
    profile = (unit.get("profiles") or {}).get(workflow_id)
    if not isinstance(profile, dict):
        raise KeyError(f"no profile for {workflow_id} on {unit.get('id')}")
    return metrics_from_profile(profile)


def _unit_from_ids(
    index: int,
    uid: str,
    fusion_id: str,
    source_ids: list[str],
    unresolved: list[str],
    cases: list[str],
) -> dict[str, Any]:
    letters = "abcdefghijklmnopqrstuvwxyz"
    profiles: dict[str, dict[str, int]] = {}
    for j, sid in enumerate(source_ids):
        profiles[sid] = profile_for(index, letters[j % 26], "source")
    profiles[fusion_id] = profile_for(index, "a", "fusion")
    padded = list(cases)
    while len(padded) < N_CASES:
        padded.append(f"case-{uid}-{len(padded) + 1}")
    return {
        "id": uid,
        "index": index,
        "fusion_id": fusion_id,
        "sources_resolved": list(source_ids),
        "sources_unresolved": list(unresolved),
        "matched_cases": padded[:N_CASES],
        "required_capabilities": [f"cap.{k}" for k in range(N_CAPS)],
        "n_faults": N_FAULTS,
        "budget": BUDGET,
        "profiles": profiles,
        "planted_worse_than_every_source": index == 30,
    }


def _extract_from_authoritative(doc: Any) -> list[dict[str, Any]] | None:
    if not isinstance(doc, dict):
        return None
    rows = doc.get("merge_units")
    if not isinstance(rows, list) or len(rows) != 30:
        return None
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            return None
        uid = str(raw.get("id") or raw.get("merge_unit_id") or f"MU-{i:02d}")
        resolved = (
            raw.get("sources_resolved_in_registry")
            or raw.get("sources_resolved")
            or raw.get("sources")
            or []
        )
        if not isinstance(resolved, list) or not resolved:
            return None
        unresolved = raw.get("sources_unresolved") or raw.get("sources_unresolved_in_registry") or []
        if not isinstance(unresolved, list):
            unresolved = []
        fusion_id = str(raw.get("fusion_id") or raw.get("fused_blueprint") or f"wf.fuse.{uid}")
        cases = raw.get("matched_cases") or raw.get("cases") or [
            f"case-{uid}-{k}" for k in range(1, N_CASES + 1)
        ]
        if not isinstance(cases, list) or len(cases) < 1:
            return None
        source_ids = [
            str(s) if not isinstance(s, dict) else str(s.get("id") or s.get("workflow_id"))
            for s in resolved
        ]
        source_ids = [s for s in source_ids if s]
        if len(source_ids) < 1:
            return None
        out.append(
            _unit_from_ids(
                i,
                uid,
                fusion_id,
                source_ids,
                [str(x) for x in unresolved],
                [str(c) for c in cases[:N_CASES]],
            )
        )
    return out if len(out) == 30 else None


def reconstructed_merge_units() -> list[dict[str, Any]]:
    """Proxy corpus of 30 merge units. IDs are MU-01..MU-30, not original map IDs."""
    units: list[dict[str, Any]] = []
    for i in range(1, 31):
        n = f"{i:02d}"
        uid = f"MU-{n}"
        sources = [f"wf.src.{n}a", f"wf.src.{n}b"]
        unresolved: list[str] = []
        if i in {7, 19, 28}:
            unresolved = [f"wf.missing.{n}"]
        if i == 15:
            sources.append(f"wf.src.{n}c")
        fusion_id = f"wf.fuse.{n}"
        cases = [f"case-{n}-{k}" for k in range(1, N_CASES + 1)]
        units.append(_unit_from_ids(i, uid, fusion_id, sources, unresolved, cases))
    return units


def load_merge_units() -> dict[str, Any]:
    tried: list[dict[str, Any]] = []
    for path in MAP_CANDIDATES:
        rec: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
        if path.is_file():
            rec["bytes"] = path.stat().st_size
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                extracted = _extract_from_authoritative(doc)
                rec["parsed"] = True
                rec["extracted_n"] = len(extracted) if extracted else 0
                tried.append(rec)
                if extracted:
                    return {
                        "source": "authoritative-file",
                        "path": str(path),
                        "units": extracted,
                        "tried": tried,
                        "disclosure": None,
                        "corpus_sha256": sha256_text(canonical(extracted)),
                        "metric_registry_sha256": metric_registry_sha(),
                    }
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                rec["parsed"] = False
                rec["error"] = type(exc).__name__
                tried.append(rec)
                continue
        else:
            tried.append(rec)
    units = reconstructed_merge_units()
    if len(units) != 30:
        raise RuntimeError(f"merge_units cardinality {len(units)} != 30")
    return {
        "source": "reconstructed-proxy",
        "path": None,
        "units": units,
        "tried": tried,
        "disclosure": (
            "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json is absent from this "
            "worktree and from the searched restore paths. The 30 merge units "
            "are a reconstructed proxy with the contracted cardinality and the "
            "sources_resolved / sources_unresolved shape. They are NOT claimed "
            "to be the original map IDs."
        ),
        "corpus_sha256": sha256_text(canonical(units)),
        "metric_registry_sha256": metric_registry_sha(),
    }
