"""Resolve the spec Final Deliverables list and probe each path on disk.

_USER-PROMPTS.md:11402-11435 is not on this worktree (same finding as
BLD-0043 / CNL-0068). This module (1) searches known restore paths,
(2) if the spec is present, parses those lines, (3) otherwise reconstructs
only catalog-cited items that name a line in 11402-11435 or are explicitly
called a Prompt Two final deliverable. Completeness against the unread
34-line list is NOT-CHECKED.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from classify import ABSENT, DIR_INCOMPLETE, EMPTY, PRESENT, classify_path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

SPEC_CANDIDATES = (
    REPO / "_USER-PROMPTS.md",
    REPO / "command-center" / "_USER-PROMPTS.md",
    REPO / "command-center" / "p2-wave" / "_USER-PROMPTS.md",
    Path.home() / ".claude" / "harness-restore-20260806" / "_USER-PROMPTS.md",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"),
    Path("/root/.claude/harness-restore-20260806/_USER-PROMPTS.md"),
)

SPEC_START = 11402
SPEC_END = 11435


def _catalog_line(text: str, needle: str) -> int:
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return 1


def locate_spec() -> dict[str, Any]:
    tried: list[dict[str, Any]] = []
    for cand in SPEC_CANDIDATES:
        exists = cand.is_file()
        tried.append({"path": str(cand), "exists": exists})
        if exists and cand.stat().st_size > 0:
            return {
                "present": True,
                "path": str(cand),
                "bytes": cand.stat().st_size,
                "tried": tried,
            }
    return {"present": False, "path": None, "bytes": 0, "tried": tried}


def parse_spec_items(spec_path: Path) -> list[dict[str, Any]]:
    lines = spec_path.read_text(encoding="utf-8", errors="replace").splitlines()
    chunk = lines[SPEC_START - 1 : SPEC_END]
    items: list[dict[str, Any]] = []
    bullet = re.compile(r"^(?:[-*•]|\d+[\.)])\s+")
    for offset, line in enumerate(chunk):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if bullet.match(stripped) or stripped[:1].isalpha():
            text = bullet.sub("", stripped).strip().strip("`")
            if len(text) < 8:
                continue
            items.append(
                {
                    "id": f"FD-SPEC-{SPEC_START + offset}",
                    "text": text,
                    "spec_line": SPEC_START + offset,
                    "source": "spec-lines-11402-11435",
                }
            )
    return items


def _contracted_items(catalog_text: str) -> list[dict[str, Any]]:
    """Catalog-cited members of the 11402-11435 list plus named P2 deliverables."""
    return [
        {
            "id": "FD-11431",
            "text": "architecture diagrams",
            "spec_line": 11431,
            "source": "catalog-citation",
            "catalog_line": _catalog_line(catalog_text, "_USER-PROMPTS.md:11431"),
            "candidate_paths": [
                "command-center/synthesis/SYN-0044.diagram-set.json",
            ],
            "required_member": None,
        },
        {
            "id": "FD-11433",
            "text": "verified decision trace",
            "spec_line": 11433,
            "source": "catalog-citation",
            "catalog_line": _catalog_line(catalog_text, "_USER-PROMPTS.md:11433"),
            "candidate_paths": [
                "command-center/synthesis/SYN-0005.decision-trace.json",
            ],
            "required_member": None,
        },
        {
            "id": "FD-11435",
            "text": (
                "a final evidence-backed report distinguishing VERIFIED, "
                "INFERRED, UNVERIFIED, REJECTED, and DEFERRED items"
            ),
            "spec_line": 11435,
            "source": "catalog-citation",
            "catalog_line": _catalog_line(catalog_text, "_USER-PROMPTS.md:11435"),
            "candidate_paths": [
                "command-center/synthesis/SYN-0041.final-report.json",
            ],
            "required_member": None,
        },
        {
            "id": "FD-11413",
            "text": (
                "decomposability and lineage preservation "
                "(08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json)"
            ),
            "spec_line": 11413,
            "source": "catalog-citation",
            "catalog_line": _catalog_line(catalog_text, "11413"),
            "candidate_paths": [
                "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
                "command-center/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
            ],
            "required_member": None,
        },
        {
            "id": "FD-08WF",
            "text": (
                "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json "
                "(explicitly a Prompt Two final deliverable)"
            ),
            "spec_line": None,
            "source": "catalog-named-p2-final-deliverable",
            "catalog_line": _catalog_line(
                catalog_text, "it is also a Prompt Two final deliverable"
            ),
            "candidate_paths": [
                "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
                "command-center/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
            ],
            "required_member": None,
        },
        {
            "id": "FD-10WF",
            "text": (
                "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json "
                "(one of the two fusion artifacts also named as Prompt Two "
                "final deliverables)"
            ),
            "spec_line": None,
            "source": "catalog-named-p2-final-deliverable",
            "catalog_line": _catalog_line(
                catalog_text, "Two of the three are ALSO Prompt Two final deliverables"
            ),
            "candidate_paths": [
                "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
                "command-center/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
            ],
            "required_member": None,
        },
    ]


def _bind_spec_paths(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """If the spec text is live, attach contracted paths by name match."""
    contracted = _contracted_items(CATALOG.read_text(encoding="utf-8"))
    by_token = [
        ("architecture diagram", contracted[0]),
        ("decision trace", contracted[1]),
        ("evidence-backed report", contracted[2]),
        ("VERIFIED", contracted[2]),
        ("08-WORKFLOW-PROVENANCE", contracted[3]),
        ("10-WORKFLOW-MERGE", contracted[5]),
    ]
    out: list[dict[str, Any]] = []
    for item in items:
        blob = item["text"]
        bound = dict(item)
        bound.setdefault("candidate_paths", [])
        bound.setdefault("required_member", None)
        for token, src in by_token:
            if token.lower() in blob.lower() and src.get("candidate_paths"):
                bound["candidate_paths"] = list(src["candidate_paths"])
                bound["bound_from"] = src["id"]
                break
        out.append(bound)
    return out


def resolve_and_probe(item: dict[str, Any]) -> dict[str, Any]:
    rels = list(item.get("candidate_paths") or [])
    if not rels:
        return {
            **item,
            "resolved_path": None,
            "verdict": ABSENT,
            "bytes": 0,
            "sha256": None,
            "probes": [],
            "detail": "no concrete path bound; cannot claim PRESENT",
        }
    probes: list[dict[str, Any]] = []
    chosen: dict[str, Any] | None = None
    for rel in rels:
        rec = classify_path(
            REPO / rel,
            required_member=item.get("required_member"),
        )
        rec["relpath"] = rel.replace("\\", "/")
        probes.append(rec)
        if rec["verdict"] == PRESENT and chosen is None:
            chosen = rec
        elif chosen is None:
            chosen = rec
    assert chosen is not None
    return {
        **item,
        "resolved_path": chosen.get("relpath") or rels[0],
        "verdict": chosen["verdict"],
        "bytes": chosen.get("bytes") or 0,
        "sha256": chosen.get("sha256"),
        "st_size": chosen.get("st_size"),
        "probes": [
            {
                "relpath": p.get("relpath"),
                "verdict": p["verdict"],
                "bytes": p.get("bytes") or 0,
                "sha256": p.get("sha256"),
                "st_size": p.get("st_size"),
                "exists": p.get("exists"),
                "is_dir": p.get("is_dir"),
                "is_file": p.get("is_file"),
            }
            for p in probes
        ],
    }


def sweep() -> dict[str, Any]:
    catalog_text = CATALOG.read_text(encoding="utf-8")
    spec = locate_spec()
    completeness = "NOT-CHECKED"
    source = "catalog-reconstruction"
    if spec["present"]:
        raw_items = parse_spec_items(Path(spec["path"]))
        items = _bind_spec_paths(raw_items)
        source = "spec-lines-11402-11435"
        completeness = "parsed-from-spec"
        if not items:
            items = _contracted_items(catalog_text)
            source = "catalog-reconstruction-empty-spec-slice"
            completeness = "NOT-CHECKED"
    else:
        items = _contracted_items(catalog_text)

    probed = [resolve_and_probe(it) for it in items]
    by_verdict: dict[str, list[str]] = {
        PRESENT: [],
        EMPTY: [],
        ABSENT: [],
        DIR_INCOMPLETE: [],
    }
    for row in probed:
        by_verdict.setdefault(row["verdict"], [])
        by_verdict[row["verdict"]].append(row["id"])

    no_artifact = by_verdict.get(ABSENT, [])
    return {
        "spec": spec,
        "source": source,
        "completeness_vs_unread_list": completeness,
        "item_count": len(probed),
        "items": probed,
        "present": by_verdict.get(PRESENT, []),
        "empty": by_verdict.get(EMPTY, []),
        "absent": no_artifact,
        "dir_incomplete": by_verdict.get(DIR_INCOMPLETE, []),
        "answer": (
            "Items on the reconstructed Final Deliverables list with no "
            "artifact on disk (ABSENT): "
            + (", ".join(no_artifact) if no_artifact else "(none)")
            + ". EMPTY="
            + json.dumps(by_verdict.get(EMPTY, []))
            + " DIR-INCOMPLETE="
            + json.dumps(by_verdict.get(DIR_INCOMPLETE, []))
            + " PRESENT="
            + json.dumps(by_verdict.get(PRESENT, []))
            + f". reconstruction_source={source} "
            f"completeness={completeness}."
        ),
        "global_artifact_manifest": {
            "path": "command-center/ARTIFACT-MANIFEST.json",
            "present": (REPO / "command-center" / "ARTIFACT-MANIFEST.json").is_file(),
            "note": (
                "Unit originally registers into ARTIFACT-MANIFEST.json. "
                "G-1 for this delivery writes the per-unit "
                "UNIT-ARTIFACT-MANIFEST.json only; global unit_manifest.py "
                "--write is forbidden."
            ),
        },
    }
