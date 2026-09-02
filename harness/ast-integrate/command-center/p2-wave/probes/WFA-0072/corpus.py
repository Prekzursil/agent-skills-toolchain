#!/usr/bin/env python3
"""Load the 284-candidate registry, or reconstruct it from catalog locks.

Live 08-WORKFLOW-CANDIDATE-REGISTRY.json is the preferred source. On this
Linux worktree it is absent; reconstruction locks family counts and the
WFA-0005 classification histogram and assigns runtime via written rule
R-RUNTIME-1. Reconstructed identities are labeled; inspect-recovered A-family
ids are the only names taken from a prior source inspect.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

FAMILY_COUNTS = {
    "A-saved-workflow": 10,
    "B-repo-workflow": 4,
    "C-repo-tool": 25,
    "D-harness-runtime": 6,
    "E-agent": 19,
    "F-plugin": 21,
    "G-skill": 96,
    "H-executed-corpus": 72,
    "I-command": 31,
}

CLASS_HISTOGRAM = {
    "ADOPT-AS-IS": 122,
    "UNKNOWN-NEEDS-PROBE": 44,
    "DISTILL": 43,
    "RETIRE": 24,
    "ADOPT-WITH-WRAPPER": 20,
    "REPAIR": 15,
    "EXTEND": 6,
    "MERGE": 6,
    "SPECIALIZE": 4,
}

# Six of the seven WFA-0027 runtimes occupy family D (n=6).
D_RUNTIMES = (
    "langgraph",
    "crewai",
    "autogen",
    "temporal",
    "airflow",
    "prefect",
)

A_SAVED = [
    ("wf-saved-agentic-repair-reliability", "agentic-repair-reliability.js", "inspect"),
    ("wf-saved-bc-stage-compendium-enrichment", "bc-stage-compendium-enrichment.js", "inspect"),
    ("wf-saved-codex-auth-research-fanout", "codex-auth-research-fanout.mjs", "inspect"),
    ("wf-saved-design-gate", "design-gate.mjs", "inspect"),
    ("wf-saved-harness-self-improve-sweep", "harness-self-improve-sweep.js", "inspect"),
    ("wf-saved-plan-gate", "plan-gate.mjs", "catalog-WFA-0045"),
    ("wf-saved-a07-reconstructed", "a07-reconstructed.js", "reconstructed"),
    ("wf-saved-a08-reconstructed", "a08-reconstructed.js", "reconstructed"),
    ("wf-saved-a09-reconstructed", "a09-reconstructed.js", "reconstructed"),
    ("wf-saved-a10-reconstructed", "a10-reconstructed.js", "reconstructed"),
]

PLANT_ID = "wf-saved-agentic-repair-reliability"

REGISTRY_SOUGHT = [
    Path(
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "08-WORKFLOW-CANDIDATE-REGISTRY.json"
    ),
    Path(
        "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/"
        "08-WORKFLOW-CANDIDATE-REGISTRY.json"
    ),
    Path("/root/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/wfa/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    HERE / "fixtures/08-WORKFLOW-CANDIDATE-REGISTRY.json",
]


def _cand(
    cid: str,
    name: str,
    family: str,
    classification: str,
    runtime: str,
    identity_kind: str,
    **extra,
) -> dict:
    row = {
        "id": cid,
        "name": name,
        "family": family,
        "classification": classification,
        "runtime": runtime,
        "imports": [],
        "processes": [],
        "manifest_requires": [],
        "mechanisms": "",
        "notes": "",
        "identity_kind": identity_kind,
        "runtime_source": extra.pop("runtime_source", "family-rule-R-RUNTIME-1"),
    }
    row.update(extra)
    return row


def locate_registry() -> dict:
    hits = []
    for path in REGISTRY_SOUGHT:
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        rec = {"path": str(path), "exists": exists, "bytes": size}
        if exists and size > 0:
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            rec["sha256"] = hashlib.sha256(raw).hexdigest()
            hits.append(rec)
            return {"present": True, "chosen": rec, "sought": [str(p) for p in REGISTRY_SOUGHT]}
        hits.append(rec)
    return {
        "present": False,
        "chosen": None,
        "sought": [str(p) for p in REGISTRY_SOUGHT],
        "probes": hits,
    }


def _parse_live(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        rows = doc.get("candidates") or doc.get("records") or []
    else:
        rows = []
    out = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("id") or raw.get("name") or "")
        if not cid:
            continue
        out.append(
            {
                "id": cid,
                "name": str(raw.get("name") or cid),
                "family": str(raw.get("family") or ""),
                "classification": str(
                    raw.get("classification")
                    or (raw.get("disposition") or "")
                ),
                "runtime": str(raw.get("runtime") or ""),
                "imports": list(raw.get("imports") or []),
                "processes": list(raw.get("processes") or []),
                "manifest_requires": list(
                    raw.get("manifest_requires") or raw.get("requires") or []
                ),
                "mechanisms": raw.get("mechanisms")
                if isinstance(raw.get("mechanisms"), str)
                else json.dumps(raw.get("mechanisms") or ""),
                "notes": str(raw.get("notes") or ""),
                "identity_kind": "live-registry",
                "runtime_source": "live-registry",
                "does": str(raw.get("does") or ""),
            }
        )
    return out


def reconstruct() -> list[dict]:
    """Catalog-locked 284-row reconstruction. Written before scoring.

    R-RUNTIME-1: A/C/E/F/G/H/I → claude-code (chosen plane). B → github-actions.
    D → the six torn-down runtimes. Classification: D and A are ADOPT-AS-IS;
    B is ADOPT-WITH-WRAPPER; remaining ADOPT-AS-IS fills G then H; remaining
    ADOPT-WITH-WRAPPER fills H; leftover rows take the rest of the histogram
    in family order C, E, F, I, H.
    """
    if sum(FAMILY_COUNTS.values()) != 284:
        raise RuntimeError("family counts do not sum to 284")
    if sum(CLASS_HISTOGRAM.values()) != 284:
        raise RuntimeError("class histogram does not sum to 284")

    by_family: dict[str, list[dict]] = {k: [] for k in FAMILY_COUNTS}

    for cid, name, kind in A_SAVED:
        by_family["A-saved-workflow"].append(
            _cand(cid, name, "A-saved-workflow", "", "claude-code", kind)
        )
    for i in range(FAMILY_COUNTS["B-repo-workflow"]):
        by_family["B-repo-workflow"].append(
            _cand(
                f"wf-repo-{i+1:02d}",
                f"repo-workflow-{i+1:02d}.yml",
                "B-repo-workflow",
                "",
                "github-actions",
                "reconstructed",
            )
        )
    for i in range(FAMILY_COUNTS["C-repo-tool"]):
        by_family["C-repo-tool"].append(
            _cand(
                f"tool-repo-{i+1:02d}",
                f"tool-{i+1:02d}",
                "C-repo-tool",
                "",
                "claude-code",
                "reconstructed",
            )
        )
    for i, rt in enumerate(D_RUNTIMES):
        by_family["D-harness-runtime"].append(
            _cand(
                f"rt-{rt}",
                f"{rt}-runtime",
                "D-harness-runtime",
                "",
                rt,
                "reconstructed",
            )
        )
    for i in range(FAMILY_COUNTS["E-agent"]):
        by_family["E-agent"].append(
            _cand(
                f"agent-{i+1:02d}",
                f"agent-{i+1:02d}",
                "E-agent",
                "",
                "claude-code",
                "reconstructed",
            )
        )
    for i in range(FAMILY_COUNTS["F-plugin"]):
        by_family["F-plugin"].append(
            _cand(
                f"plugin-{i+1:02d}",
                f"plugin-{i+1:02d}",
                "F-plugin",
                "",
                "claude-code",
                "reconstructed",
            )
        )
    for i in range(FAMILY_COUNTS["G-skill"]):
        by_family["G-skill"].append(
            _cand(
                f"skill-{i+1:02d}",
                f"skill-{i+1:02d}",
                "G-skill",
                "",
                "claude-code",
                "reconstructed",
            )
        )
    for i in range(FAMILY_COUNTS["H-executed-corpus"]):
        by_family["H-executed-corpus"].append(
            _cand(
                f"corpus-{i+1:02d}",
                f"corpus-{i+1:02d}",
                "H-executed-corpus",
                "",
                "claude-code",
                "reconstructed",
            )
        )
    for i in range(FAMILY_COUNTS["I-command"]):
        by_family["I-command"].append(
            _cand(
                f"cmd-{i+1:02d}",
                f"cmd-{i+1:02d}",
                "I-command",
                "",
                "claude-code",
                "reconstructed",
            )
        )

    for fam, n in FAMILY_COUNTS.items():
        if len(by_family[fam]) != n:
            raise RuntimeError(f"{fam} want {n} got {len(by_family[fam])}")

    # Classification assignment (deterministic, written before scoring).
    for row in by_family["D-harness-runtime"]:
        row["classification"] = "ADOPT-AS-IS"
    for row in by_family["A-saved-workflow"]:
        row["classification"] = "ADOPT-AS-IS"
    for row in by_family["B-repo-workflow"]:
        row["classification"] = "ADOPT-WITH-WRAPPER"
    for row in by_family["G-skill"]:
        row["classification"] = "ADOPT-AS-IS"
    for row in by_family["H-executed-corpus"][:10]:
        row["classification"] = "ADOPT-AS-IS"
    for row in by_family["H-executed-corpus"][10:26]:
        row["classification"] = "ADOPT-WITH-WRAPPER"

    leftover_classes = (
        ["UNKNOWN-NEEDS-PROBE"] * CLASS_HISTOGRAM["UNKNOWN-NEEDS-PROBE"]
        + ["DISTILL"] * CLASS_HISTOGRAM["DISTILL"]
        + ["RETIRE"] * CLASS_HISTOGRAM["RETIRE"]
        + ["REPAIR"] * CLASS_HISTOGRAM["REPAIR"]
        + ["EXTEND"] * CLASS_HISTOGRAM["EXTEND"]
        + ["MERGE"] * CLASS_HISTOGRAM["MERGE"]
        + ["SPECIALIZE"] * CLASS_HISTOGRAM["SPECIALIZE"]
    )
    unlabeled: list[dict] = []
    for fam in ("C-repo-tool", "E-agent", "F-plugin", "I-command", "H-executed-corpus"):
        unlabeled.extend(r for r in by_family[fam] if not r["classification"])
    if len(unlabeled) != len(leftover_classes):
        raise RuntimeError(
            f"leftover mismatch unlabeled={len(unlabeled)} classes={len(leftover_classes)}"
        )
    for row, cls in zip(unlabeled, leftover_classes):
        row["classification"] = cls

    ordered = []
    for fam in FAMILY_COUNTS:
        ordered.extend(by_family[fam])
    _assert_locks(ordered)
    return ordered


def _assert_locks(rows: list[dict]) -> None:
    if len(rows) != 284:
        raise RuntimeError(f"n={len(rows)}")
    fam = Counter(r["family"] for r in rows)
    cls = Counter(r["classification"] for r in rows)
    if dict(fam) != FAMILY_COUNTS:
        raise RuntimeError(f"family lock fail {dict(fam)}")
    if dict(cls) != CLASS_HISTOGRAM:
        raise RuntimeError(f"class lock fail {dict(cls)}")
    if cls.get("TRANSLATE", 0) != 0:
        raise RuntimeError("reconstruction must start at TRANSLATE=0")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate ids")


def overlay_plant(rows: list[dict], enabled: bool) -> list[dict]:
    """Both-states plant: ADOPT-AS-IS with chosen-plane runtime string but a LangGraph import."""
    out = []
    for row in rows:
        copy = json.loads(json.dumps(row))
        if enabled and copy.get("id") == PLANT_ID:
            copy["imports"] = ["langgraph"]
            copy["notes"] = "plant: runtime string claims claude-code; import is langgraph"
            copy["plant"] = True
        out.append(copy)
    return out


def overlay_benign_lib(rows: list[dict], enabled: bool) -> list[dict]:
    """Legitimate library import must stay silent on the guard."""
    out = []
    for row in rows:
        copy = json.loads(json.dumps(row))
        if enabled and copy.get("id") == PLANT_ID:
            copy["imports"] = ["jsonschema"]
            copy["notes"] = "benign library import; not a second control plane"
        out.append(copy)
    return out


def load_candidates() -> tuple[list[dict], dict]:
    loc = locate_registry()
    if loc.get("present") and loc.get("chosen"):
        path = Path(loc["chosen"]["path"])
        rows = _parse_live(path)
        meta = {
            "kind": "live-registry",
            "n": len(rows),
            "locator": loc,
            "rule": None,
        }
        return rows, meta
    rows = reconstruct()
    meta = {
        "kind": "catalog-locked-reconstruction",
        "n": len(rows),
        "locator": loc,
        "rule": (
            "R-RUNTIME-1 written before scoring: A/C/E/F/G/H/I runtime=claude-code; "
            "B=github-actions; D=langgraph,crewai,autogen,temporal,airflow,prefect. "
            "Classification locks match WFA-0005 histogram. This is not a claim that "
            "the Windows snapshot used these runtime strings."
        ),
        "inspect_recovered_ids": [x[0] for x in A_SAVED if x[2] == "inspect"],
        "family_counts": dict(FAMILY_COUNTS),
        "classification_histogram": dict(CLASS_HISTOGRAM),
    }
    return rows, meta
