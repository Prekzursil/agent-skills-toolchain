#!/usr/bin/env python3
"""WFA-0143 workflow-scout: search four source classes, verify provenance, rank.

Does not synthesize workflows. A hit whose provenance cannot be resolved is
UNKNOWN-NEEDS-PROBE and is never placed in the ranked set. Existing hits
always rank above any build_proposal.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCE_CLASSES = ("local", "repository", "marketplace", "public")
STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "be",
        "by",
        "find",
        "for",
        "from",
        "in",
        "into",
        "is",
        "not",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "using",
        "with",
        "without",
        "existing",
        "workflow",
        "workflows",
        "source",
        "public",
        "used",
    }
)
TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
KNOWN_LICENSES = frozenset(
    {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "Unlicense",
        "CC0-1.0",
        "MPL-2.0",
    }
)
REGISTRY_CANDIDATES = [
    Path(
        "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/"
        "08-WORKFLOW-CANDIDATE-REGISTRY.json"
    ),
    Path("/root/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "wfa" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
]


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def file_line(path: Path, needle: str) -> str:
    r = rel(path)
    if path.is_file():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if needle in line:
                return f"{r}:{i}"
    return f"{r}:1"


def tokenize(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall((text or "").lower()) if t not in STOP}


def locate_registry() -> dict[str, Any]:
    for path in REGISTRY_CANDIDATES:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            n = 0
            if isinstance(data, dict):
                n = len(data.get("candidates") or [])
            elif isinstance(data, list):
                n = len(data)
            return {"present": True, "path": str(path), "n_candidates": n}
    return {
        "present": False,
        "path": None,
        "n_candidates": 0,
        "tried": [str(p) for p in REGISTRY_CANDIDATES],
    }


def load_goals() -> dict[str, dict[str, Any]]:
    path = HERE / "fixtures" / "goals.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture_corpus() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    root = HERE / "fixtures" / "sources"
    for cls in SOURCE_CLASSES:
        folder = root / cls
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            rec = json.loads(path.read_text(encoding="utf-8"))
            rec["_source_path"] = rel(path)
            rec["source_class"] = rec.get("source_class") or cls
            records.append(rec)
    return records


def live_overlays() -> list[dict[str, Any]]:
    overlay: list[dict[str, Any]] = []
    plugin = REPO / ".claude-plugin" / "plugin.json"
    if plugin.is_file():
        doc = json.loads(plugin.read_text(encoding="utf-8"))
        overlay.append(
            {
                "id": "live-marketplace-" + str(doc.get("name") or "plugin"),
                "name": doc.get("name") or "plugin",
                "does": (doc.get("description") or "")
                + " live marketplace plugin manifest on this worktree",
                "mechanisms": ["plugin-manifest"],
                "source_class": "marketplace",
                "license": "UNKNOWN",
                "maintenance": "unknown",
                "kind": "existing",
                "provenance": {"kind": "file", "ref": ".claude-plugin/plugin.json"},
                "_source_path": rel(plugin),
                "_live": True,
            }
        )
    market = REPO / ".claude-plugin" / "marketplace.json"
    if market.is_file():
        overlay.append(
            {
                "id": "live-marketplace-listing-harness",
                "name": "harness-marketplace",
                "does": "marketplace listing generated from the typed registry",
                "mechanisms": ["marketplace-listing"],
                "source_class": "marketplace",
                "license": "UNKNOWN",
                "maintenance": "unknown",
                "kind": "existing",
                "provenance": {
                    "kind": "file",
                    "ref": ".claude-plugin/marketplace.json",
                },
                "_source_path": rel(market),
                "_live": True,
            }
        )
    return overlay


def load_corpus(*, include_live: bool = False) -> list[dict[str, Any]]:
    records = load_fixture_corpus()
    if include_live:
        records.extend(live_overlays())
    return records


def source_census(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {cls: 0 for cls in SOURCE_CLASSES}
    for rec in records:
        cls = str(rec.get("source_class") or "")
        if cls in counts:
            counts[cls] += 1
    return counts


def score_candidate(goal_tokens: set[str], rec: dict[str, Any]) -> float:
    blob = " ".join(
        [
            str(rec.get("id") or ""),
            str(rec.get("name") or ""),
            str(rec.get("does") or ""),
            " ".join(str(x) for x in (rec.get("mechanisms") or [])),
            str(rec.get("kind") or ""),
        ]
    )
    cand_tokens = tokenize(blob)
    overlap = goal_tokens & cand_tokens
    if not overlap:
        return 0.0
    long_hits = {t for t in overlap if len(t) >= 8}
    if len(overlap) < 2 and not long_hits:
        return 0.0
    union = goal_tokens | cand_tokens
    jaccard = len(overlap) / max(1, len(union))
    coverage = len(overlap) / max(1, len(goal_tokens))
    return round(0.55 * coverage + 0.45 * jaccard, 6)


def resolve_provenance(rec: dict[str, Any]) -> dict[str, Any]:
    prov = rec.get("provenance") if isinstance(rec.get("provenance"), dict) else {}
    kind = str(prov.get("kind") or "file")
    ref = str(prov.get("ref") or "").strip()
    if not ref:
        return {
            "resolved": False,
            "reason": "missing-provenance-ref",
            "path": None,
            "sha256": None,
        }
    if kind == "file":
        path = Path(ref)
        if not path.is_absolute():
            path = REPO / ref
        if path.is_file():
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            digest = hashlib.sha256(raw).hexdigest()
            expected = prov.get("sha256")
            if expected and str(expected) != digest:
                return {
                    "resolved": False,
                    "reason": "sha256-mismatch",
                    "path": rel(path),
                    "sha256": digest,
                }
            return {
                "resolved": True,
                "reason": None,
                "path": rel(path),
                "sha256": digest,
            }
        return {
            "resolved": False,
            "reason": "file-missing",
            "path": ref.replace("\\", "/"),
            "sha256": None,
        }
    if kind == "url":
        snapshot = str(prov.get("snapshot") or "").strip()
        if snapshot:
            snap_path = Path(snapshot)
            if not snap_path.is_absolute():
                snap_path = REPO / snapshot
            if snap_path.is_file():
                raw = snap_path.read_bytes().replace(b"\r\n", b"\n")
                return {
                    "resolved": True,
                    "reason": None,
                    "path": rel(snap_path),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "url": ref,
                }
        return {
            "resolved": False,
            "reason": "url-without-resolvable-snapshot",
            "path": ref,
            "sha256": None,
        }
    return {
        "resolved": False,
        "reason": f"unknown-provenance-kind:{kind}",
        "path": ref,
        "sha256": None,
    }


def license_report(rec: dict[str, Any]) -> dict[str, Any]:
    raw = str(rec.get("license") or "").strip()
    if not raw:
        return {"license": "UNKNOWN", "known_spdx": False}
    return {"license": raw, "known_spdx": raw in KNOWN_LICENSES}


def _hit_record(
    rec: dict[str, Any],
    *,
    score: float,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    src = REPO / rec["_source_path"]
    lic = license_report(rec)
    return {
        "id": rec["id"],
        "name": rec.get("name"),
        "source_class": rec.get("source_class"),
        "kind": rec.get("kind") or "existing",
        "license": lic["license"],
        "known_spdx": lic["known_spdx"],
        "maintenance": rec.get("maintenance") or "unknown",
        "score": score,
        "does": rec.get("does"),
        "evidence_anchor": file_line(src, str(rec["id"])),
        "provenance": provenance,
        "live": bool(rec.get("_live")),
    }


def scout(goal: dict[str, Any], *, include_live: bool = False) -> dict[str, Any]:
    intent = str(goal.get("intent") or "")
    goal_tokens = tokenize(intent)
    records = load_corpus(include_live=include_live)
    census = source_census(records)
    ranked_raw: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    skipped = 0
    for rec in records:
        sc = score_candidate(goal_tokens, rec)
        if sc <= 0:
            skipped += 1
            continue
        prov = resolve_provenance(rec)
        hit = _hit_record(rec, score=sc, provenance=prov)
        if not prov.get("resolved"):
            unknown.append(
                {
                    **hit,
                    "disposition": "UNKNOWN-NEEDS-PROBE",
                    "unknown_reason": prov.get("reason"),
                }
            )
            continue
        ranked_raw.append(hit)
    # rank-existing-above-build: existing hits (kind != build_proposal) sort first.
    ranked_raw.sort(
        key=lambda h: (
            0 if h.get("kind") != "build_proposal" else 1,
            -float(h.get("score") or 0),
            str(h.get("id") or ""),
        )
    )
    ranked = []
    for i, hit in enumerate(ranked_raw, 1):
        row = dict(hit)
        row["rank"] = i
        ranked.append(row)
    return {
        "goal": {
            "id": goal.get("id"),
            "intent": intent,
            "tokens": sorted(goal_tokens),
        },
        "pipeline": [
            "ingest-typed-goal",
            "search-local",
            "search-repository",
            "search-marketplace",
            "search-public",
            "verify-provenance",
            "verify-license",
            "rank-existing-above-build",
        ],
        "sources_searched": list(SOURCE_CLASSES),
        "source_census": census,
        "n_corpus": len(records),
        "n_skipped_no_overlap": skipped,
        "ranked": ranked,
        "unknown_needs_probe": unknown,
        "include_live": include_live,
        "registry": locate_registry(),
    }


def run_named_goal(name: str, *, include_live: bool = False) -> dict[str, Any]:
    goals = load_goals()
    if name not in goals:
        raise KeyError(name)
    return scout(goals[name], include_live=include_live)


def main() -> int:
    name = "known_existing"
    include_live = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--goal" and i + 1 < len(args):
            name = args[i + 1]
            i += 2
            continue
        if args[i] == "--live":
            include_live = True
            i += 1
            continue
        i += 1
    result = run_named_goal(name, include_live=include_live)
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
