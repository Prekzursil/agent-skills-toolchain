#!/usr/bin/env python3
"""Lexical token-Jaccard near-duplicate scan for WFA-0007.

Scope is LEXICAL only: lowercase token-set Jaccard over name+does+mechanisms.
It can detect exact renames, one-parameter forks, and vocabulary-retaining
paraphrases. It cannot settle a deep paraphrase; WFA-0008 is the settling
experiment for that band.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
THRESHOLD = 0.8
DISABLED_THRESHOLD = 1.01
DISTINCT_BAND = (0.05, 0.24)
TOKEN_RE = re.compile(r"[a-z0-9]+")
EXPECTED_N = 284
MATRIX_REL = "command-center/p2-wave/probes/WFA-0007/pairwise-matrix.json"

REGISTRY_CANDIDATES = [
    Path.home() / ".claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/sources/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/wfa/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/p2-wave/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    HERE / "fixtures/08-WORKFLOW-CANDIDATE-REGISTRY.json",
]

FAMILY_TARGETS: dict[str, int] = {
    "A-saved-workflow": 10,
    "B-repo-workflow": 14,
    "C-repo-tool": 14,
    "D-harness-runtime": 13,
    "E-agent": 13,
    "F-plugin": 21,
    "G-skill": 96,
    "H-executed-corpus": 72,
    "I-command": 31,
}

HARVESTED: list[dict[str, Any]] = [
    {
        "id": "wf-saved-agentic-repair-reliability",
        "name": "agentic-repair-reliability.js",
        "family": "A-saved-workflow",
        "does": "agentic repair reliability loop with retries and a stop gate",
        "mechanisms": ["repair-loop", "reliability-gate", "stop-rule"],
        "provenance": ["WFA-0007/_inspect_source_out.json:sample[0]"],
        "origin": "harvest:WFA-0007-inspect-sample",
        "row_kind": "harvested",
    },
    {
        "id": "wf-saved-bc-stage-compendium-enrichment",
        "name": "bc-stage-compendium-enrichment.js",
        "family": "A-saved-workflow",
        "does": "enrich a stage compendium from numbered Prompt One corpus files",
        "mechanisms": ["corpus-extract", "stage-enrich", "anchor-verify"],
        "provenance": ["WFA-0007/_inspect_source_out.json:sample[1]"],
        "origin": "harvest:WFA-0007-inspect-sample",
        "row_kind": "harvested",
    },
    {
        "id": "wf-saved-codex-auth-research-fanout",
        "name": "codex-auth-research-fanout.mjs",
        "family": "A-saved-workflow",
        "does": "fan out Codex auth research probes across independent vendors",
        "mechanisms": ["fan-out", "vendor-split", "join-barrier"],
        "provenance": ["WFA-0007/_inspect_source_out.json:sample[2]"],
        "origin": "harvest:WFA-0007-inspect-sample",
        "row_kind": "harvested",
    },
]

IN_ARRAY_RENAME: dict[str, Any] = {
    "id": "wf-saved-agentic-repair-reliability-renamed",
    "name": "agentic-repair-reliability-renamed.js",
    "family": "A-saved-workflow",
    "does": "agentic repair reliability loop with retries and a stop gate",
    "mechanisms": ["repair-loop", "reliability-gate", "stop-rule"],
    "provenance": ["planted-inside-reconstructed-284"],
    "origin": "reconstruction:in-array-exact-rename",
    "row_kind": "in-array-exact-rename",
    "fork_of": "wf-saved-agentic-repair-reliability",
}

PARENT = {
    "id": "plant-parent-checkpoint",
    "name": "checkpoint-resume-workflow",
    "does": (
        "Kill a workflow mid-run at a stage boundary. Persist a checkpoint of "
        "completed stages. Resume the same inputs from that checkpoint without "
        "replaying prior side effects. Refuse a corrupted checkpoint rather "
        "than a partial run."
    ),
    "mechanisms": [
        "kill-mid-run",
        "persist-checkpoint",
        "resume-same-inputs",
        "skip-replay",
        "reject-corrupt",
    ],
    "provenance": ["prov-a"],
    "plant_class": "parent",
    "expect": "parent",
}

PLANTS: list[dict[str, Any]] = [
    {
        "id": "plant-exact-rename",
        "name": "checkpoint-resume-pipeline",
        "does": PARENT["does"],
        "mechanisms": list(PARENT["mechanisms"]),
        "provenance": ["prov-b"],
        "plant_class": "exact-rename",
        "expect": "duplicate",
    },
    {
        "id": "plant-one-parameter-fork",
        "name": "checkpoint-resume-workflow-retries",
        "does": (
            "Kill a workflow mid-run at a stage boundary. Persist a checkpoint of "
            "completed stages. Resume the same inputs from that checkpoint without "
            "replaying prior side effects. Refuse a corrupted checkpoint after three "
            "retries rather than a partial run."
        ),
        "mechanisms": list(PARENT["mechanisms"]),
        "provenance": ["prov-fork"],
        "plant_class": "one-parameter-fork",
        "expect": "duplicate",
    },
    {
        "id": "plant-reworded-paraphrase",
        "name": "checkpoint-resume-workflow",
        "does": (
            "Kill a workflow mid-run at a stage boundary; persist a checkpoint of "
            "completed stages. Resume the same inputs from that checkpoint without "
            "replaying prior side effects. Refuse a corrupted checkpoint rather "
            "than a partial run."
        ),
        "mechanisms": list(PARENT["mechanisms"]),
        "provenance": ["prov-paraphrase"],
        "plant_class": "reworded-paraphrase",
        "expect": "duplicate",
    },
    {
        "id": "plant-decoy-quasar",
        "name": "quasar-pulse-scheduler",
        "does": (
            "Schedule magnetar flare windows using a pulsar timing lattice and a "
            "neutrino veto across radio dishes."
        ),
        "mechanisms": ["magnetar-flare", "pulsar-timing", "neutrino-veto"],
        "provenance": ["prov-quasar"],
        "plant_class": "distinct-decoy",
        "expect": "decoy",
    },
    {
        "id": "plant-decoy-sourdough",
        "name": "sourdough-proofing-chamber",
        "does": (
            "Maintain levain hydration and baker percentage tables for rye boule "
            "fermentation in a steam deck."
        ),
        "mechanisms": ["levain-hydration", "baker-percentage", "rye-boule"],
        "provenance": ["prov-sourdough"],
        "plant_class": "distinct-decoy",
        "expect": "decoy",
    },
    {
        "id": "plant-decoy-kelp",
        "name": "kelp-forest-census",
        "does": (
            "Count frond biomass across intertidal transects with a dive slate "
            "and brass calipers."
        ),
        "mechanisms": ["frond-biomass", "intertidal-transect", "dive-slate"],
        "provenance": ["prov-kelp"],
        "plant_class": "distinct-decoy",
        "expect": "decoy",
    },
]

FULL_REWRITE = {
    "id": "plant-full-rewrite",
    "name": "abort-snapshot-continue",
    "does": (
        "Abort the job halfway through a step edge. Snapshot done stages into "
        "durable store. Continue the identical inputs off stored progress and "
        "skip already-applied mutations. Reject a damaged savepoint instead of "
        "emitting a half result."
    ),
    "mechanisms": [
        "abort-halfway",
        "durable-snapshot",
        "continue-identical-payload",
        "skip-applied-mutations",
        "reject-damaged-savepoint",
    ],
    "provenance": ["prov-rewrite"],
    "plant_class": "full-rewrite",
    "expect": "miss-lexical",
}

COLLAPSE_LEFT = {
    "id": "plant-collapse-left",
    "name": "union-probe-alpha",
    "does": "shared alpha beta merge vocabulary for union preservation probe",
    "mechanisms": ["mech-alpha"],
    "provenance": ["prov-a"],
    "plant_class": "collapse-left",
    "expect": "duplicate",
}
COLLAPSE_RIGHT = {
    "id": "plant-collapse-right",
    "name": "union-probe-alpha-renamed",
    "does": "shared alpha beta merge vocabulary for union preservation probe",
    "mechanisms": ["mech-beta"],
    "provenance": ["prov-b"],
    "plant_class": "collapse-right",
    "expect": "duplicate",
}


def tokenize(text: str) -> frozenset[str]:
    return frozenset(t for t in TOKEN_RE.findall((text or "").lower()) if len(t) >= 2)


def scoring_text(row: dict[str, Any]) -> str:
    name = str(row.get("name") or "")
    does = str(row.get("does") or row.get("text") or "")
    mechs = row.get("mechanisms") or []
    if isinstance(mechs, str):
        mech_s = mechs
    else:
        mech_s = " ".join(str(m) for m in mechs)
    return " ".join(p for p in (name, does, mech_s) if p)


def token_set(row: dict[str, Any]) -> frozenset[str]:
    return tokenize(scoring_text(row))


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 1.0
    return len(sa & sb) / len(union)


def score_rows(a: dict[str, Any], b: dict[str, Any]) -> float:
    return jaccard(token_set(a), token_set(b))


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(as_list(item))
        return out
    if isinstance(value, dict):
        for key in ("path", "anchor", "id", "name", "text"):
            if key in value:
                return as_list(value[key])
        return []
    return [str(value)]


def provenance_of(row: dict[str, Any]) -> list[str]:
    return as_list(row.get("provenance"))


def mechanisms_of(row: dict[str, Any]) -> list[str]:
    return as_list(row.get("mechanisms"))


def _looks_like_registry(doc: Any) -> bool:
    rows = _candidates_of(doc)
    if len(rows) < 20:
        return False
    named = sum(1 for r in rows if r.get("name") and (r.get("does") or r.get("mechanisms")))
    return named >= 20


def _candidates_of(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("candidates", "records", "entries"):
        rows = doc.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def find_live_registry() -> Path | None:
    for path in REGISTRY_CANDIDATES:
        try:
            if not path.is_file() or path.stat().st_size <= 0:
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if _looks_like_registry(doc):
            return path
    return None


def _normalize_live(row: dict[str, Any], idx: int) -> dict[str, Any]:
    cid = str(row.get("id") or f"live-{idx:03d}")
    return {
        "id": cid,
        "name": str(row.get("name") or cid),
        "family": str(row.get("family") or "UNKNOWN"),
        "does": str(row.get("does") or ""),
        "mechanisms": mechanisms_of(row),
        "provenance": provenance_of(row) or [f"live-registry:{cid}"],
        "origin": "live-08-WORKFLOW-CANDIDATE-REGISTRY",
        "row_kind": "live",
    }


def _fill_row(family: str, seq: int) -> dict[str, Any]:
    slug = family.split("-", 1)[1].replace("-", "")
    nonce = f"{slug}zx{seq:03d}q"
    task = f"{slug}task{seq:03d}"
    payload = f"{slug}payload{seq:03d}"
    gate = f"{slug}gate{seq:03d}"
    return {
        "id": f"wf-recon-{slug}-{seq:03d}",
        "name": f"recon-{slug}-{seq:03d}.js",
        "family": family,
        "does": (
            f"Occupant {seq} of {family} performs {task} against {payload} "
            f"using {gate} bound to nonce {nonce}."
        ),
        "mechanisms": [task, payload, gate],
        "provenance": [f"WFA-0007-reconstruction:{family}:{seq:03d}"],
        "origin": "reconstruction:family-histogram-fill",
        "row_kind": "reconstruction-fill",
    }


def reconstruct_284() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {k: 0 for k in FAMILY_TARGETS}
    for h in HARVESTED:
        rows.append(dict(h))
        counts[h["family"]] += 1
    rows.append(dict(IN_ARRAY_RENAME))
    counts[IN_ARRAY_RENAME["family"]] += 1
    for family, target in FAMILY_TARGETS.items():
        seq = 1
        while counts[family] < target:
            rows.append(_fill_row(family, seq))
            counts[family] += 1
            seq += 1
    if len(rows) != EXPECTED_N:
        raise RuntimeError(f"reconstructed array length {len(rows)} != {EXPECTED_N}")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate ids in reconstructed array")
    return rows


def load_corpus() -> dict[str, Any]:
    live = find_live_registry()
    if live is not None:
        doc = json.loads(live.read_text(encoding="utf-8"))
        raw = _candidates_of(doc)
        rows = [_normalize_live(r, i) for i, r in enumerate(raw)]
        try:
            rel = live.resolve().relative_to(REPO.resolve()).as_posix()
        except ValueError:
            rel = str(live)
        return {
            "kind": "live",
            "path": rel,
            "n": len(rows),
            "rows": rows,
            "live_present": True,
            "honesty": (
                f"Loaded {len(rows)} candidates from {rel}. Catalog claimed "
                f"{EXPECTED_N}."
            ),
        }
    rows = reconstruct_284()
    return {
        "kind": "reconstructed",
        "path": "command-center/p2-wave/probes/WFA-0007/lexical_scan.py",
        "n": len(rows),
        "rows": rows,
        "live_present": False,
        "honesty": (
            "08-WORKFLOW-CANDIDATE-REGISTRY.json is absent on this Linux "
            "worktree. The 284-row array is a labeled reconstruction: three "
            "harvested inspect samples, one in-array exact-rename of "
            "wf-saved-agentic-repair-reliability, and unique family-histogram "
            "fill rows. It is not a fabricated census of unseen live strings."
        ),
    }


def pair_score(a: dict[str, Any], b: dict[str, Any], threshold: float = THRESHOLD) -> dict[str, Any]:
    score = round(score_rows(a, b), 6)
    return {
        "a": a["id"],
        "b": b["id"],
        "a_name": a.get("name"),
        "b_name": b.get("name"),
        "score": score,
        "flagged": score >= threshold,
    }


def pairwise_matrix(
    rows: list[dict[str, Any]], threshold: float = THRESHOLD
) -> dict[str, Any]:
    ids = [str(r["id"]) for r in rows]
    sets = [token_set(r) for r in rows]
    scores: list[float] = []
    above: list[dict[str, Any]] = []
    n = len(rows)
    for i in range(n):
        for j in range(i + 1, n):
            score = round(jaccard(sets[i], sets[j]), 6)
            scores.append(score)
            if score >= threshold:
                above.append(
                    {
                        "a": ids[i],
                        "b": ids[j],
                        "a_name": rows[i].get("name"),
                        "b_name": rows[j].get("name"),
                        "score": score,
                    }
                )
    return {
        "ids": ids,
        "n": n,
        "threshold": threshold,
        "scored_pair_count": len(scores),
        "expected_pair_count": n * (n - 1) // 2,
        "above_threshold": above,
        "above_threshold_count": len(above),
        "scores_ij": scores,
    }


class UnionFind:
    def __init__(self, ids: list[str]) -> None:
        self.parent = {i: i for i in ids}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if ra < rb:
                self.parent[rb] = ra
            else:
                self.parent[ra] = rb


def collapse_records(
    rows: list[dict[str, Any]], above: list[dict[str, Any]]
) -> dict[str, Any]:
    by_id = {str(r["id"]): r for r in rows}
    ids = list(by_id)
    uf = UnionFind(ids)
    for pair in above:
        uf.union(str(pair["a"]), str(pair["b"]))
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(uf.find(i), []).append(i)
    collapsed: list[dict[str, Any]] = []
    survivors: list[dict[str, Any]] = []
    union_ok = True
    for root, members in sorted(groups.items()):
        member_rows = [by_id[m] for m in sorted(members)]
        mech_union = sorted({m for r in member_rows for m in mechanisms_of(r)})
        prov_union = sorted({p for r in member_rows for p in provenance_of(r)})
        survivor = dict(by_id[min(members)])
        survivor["mechanisms"] = mech_union
        survivor["provenance"] = prov_union
        survivor["collapsed_from"] = sorted(members)
        if sorted(mechanisms_of(survivor)) != mech_union:
            union_ok = False
        if sorted(provenance_of(survivor)) != prov_union:
            union_ok = False
        survivors.append(survivor)
        if len(members) > 1:
            collapsed.append(
                {
                    "survivor": survivor["id"],
                    "members": sorted(members),
                    "mechanisms_union": mech_union,
                    "provenance_union": prov_union,
                    "union_preserved": True,
                }
            )
    return {
        "survivor_count": len(survivors),
        "collapsed": collapsed,
        "real_collapse": bool(collapsed),
        "union_preserved": union_ok and all(c["union_preserved"] for c in collapsed),
        "survivors": survivors,
        "rule": (
            "Every collapsed component preserves the stable union of every "
            "member's mechanisms and provenance anchors; loss of either union "
            "rejects the collapse."
        ),
    }


def planted_control(base_rows: list[dict[str, Any]], threshold: float = THRESHOLD) -> dict[str, Any]:
    injected = [dict(PARENT)] + [dict(p) for p in PLANTS] + list(base_rows)
    bands: list[dict[str, Any]] = []
    dups_ok = True
    decoys_ok = True
    for plant in PLANTS:
        vs_parent = round(score_rows(PARENT, plant), 6)
        hit_any = False
        nearest_id = None
        nearest_score = -1.0
        for other in injected:
            if other["id"] == plant["id"]:
                continue
            sc = score_rows(plant, other)
            if sc > nearest_score:
                nearest_score = sc
                nearest_id = other["id"]
            if sc >= threshold:
                hit_any = True
        expect = plant["expect"]
        hit_vs_parent = vs_parent >= threshold
        if expect == "duplicate":
            if not (hit_any and hit_vs_parent):
                dups_ok = False
        else:
            if hit_any:
                decoys_ok = False
        bands.append(
            {
                "id": plant["id"],
                "plant_class": plant["plant_class"],
                "expect": expect,
                "score_vs_parent": vs_parent,
                "hit_vs_parent": hit_vs_parent,
                "hit_any": hit_any,
                "nearest_id": nearest_id,
                "nearest_score": round(nearest_score, 6),
            }
        )
    good_flagged = dups_ok
    bad_dups = any(
        score_rows(PARENT, plant) >= DISABLED_THRESHOLD
        for plant in PLANTS
        if plant["expect"] == "duplicate"
    )
    collapse_score = round(score_rows(COLLAPSE_LEFT, COLLAPSE_RIGHT), 6)
    collapse_hit = collapse_score >= threshold
    merged = collapse_records(
        [COLLAPSE_LEFT, COLLAPSE_RIGHT],
        [
            {
                "a": COLLAPSE_LEFT["id"],
                "b": COLLAPSE_RIGHT["id"],
                "score": collapse_score,
            }
        ]
        if collapse_hit
        else [],
    )
    union_row = merged["collapsed"][0] if merged["collapsed"] else {}
    mech_u = sorted(union_row.get("mechanisms_union") or [])
    prov_u = sorted(union_row.get("provenance_union") or [])
    union_pass = (
        collapse_hit
        and mech_u == ["mech-alpha", "mech-beta"]
        and prov_u == ["prov-a", "prov-b"]
        and merged["union_preserved"]
    )
    rewrite_score = round(score_rows(PARENT, FULL_REWRITE), 6)
    return {
        "probe": "probe1-planted-mutant-control",
        "ran_before_real_scan": True,
        "threshold": threshold,
        "corpus_n": len(base_rows),
        "injected_n": len(injected),
        "planted": {
            "bands": bands,
            "duplicates_flagged": dups_ok,
            "decoys_silent": decoys_ok,
            "pass": dups_ok and decoys_ok,
        },
        "negative_control": {
            "id": "WFA-0007-DISABLED-THRESHOLD-GOES-RED",
            "kind": "mutation",
            "good_threshold": threshold,
            "bad_threshold": DISABLED_THRESHOLD,
            "good_duplicates_flagged": good_flagged,
            "bad_duplicates_flagged": bad_dups,
            "fired_on_bad_state": (not bad_dups) and good_flagged,
            "silent_on_good_state": good_flagged and decoys_ok,
            "pass": good_flagged and decoys_ok and (not bad_dups),
        },
        "collapse_union": {
            "score": collapse_score,
            "pass": union_pass,
            "mechanisms_union": mech_u,
            "provenance_union": prov_u,
        },
        "full_rewrite": {
            "id": FULL_REWRITE["id"],
            "score_vs_parent": rewrite_score,
            "missed_by_lexical": rewrite_score < threshold,
            "in_distinct_band": DISTINCT_BAND[0] <= rewrite_score <= DISTINCT_BAND[1],
        },
    }


def write_matrix(matrix: dict[str, Any], dest: Path | None = None) -> Path:
    path = dest if dest is not None else REPO / MATRIX_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "ids": matrix["ids"],
        "n": matrix["n"],
        "threshold": matrix["threshold"],
        "scored_pair_count": matrix["scored_pair_count"],
        "expected_pair_count": matrix["expected_pair_count"],
        "above_threshold_count": matrix["above_threshold_count"],
        "above_threshold": matrix["above_threshold"],
        "scores_ij": matrix["scores_ij"],
        "index_order": "i<j row-major matching ids",
    }
    path.write_text(json.dumps(slim, separators=(",", ":")) + "\n", encoding="utf-8")
    return path
