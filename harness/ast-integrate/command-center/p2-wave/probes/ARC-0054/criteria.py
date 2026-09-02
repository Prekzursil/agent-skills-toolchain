"""Machine-checkable UX predicates for ARC-0054.

Each named failure mode is a predicate over a real artifact (error string,
blueprint field, catalog JSON, dry-run plan, repair receipt). A criterion
without an evaluator here is advisory.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

PAGE_BUDGET = 24
A1_WF_ID = "wf.catalog-class.discovery-only"
HAPPENED = "HAPPENED:"
MEANS = "MEANS:"
NEXT = "NEXT:"
BOUND_KEYS = ("max_stages", "max_rounds", "max_seconds", "timeout_seconds")
DOC_KEYS = ("doc", "description", "owner_facing")
DISPOSITION_KEYS = ("on_error", "on_timeout", "on_unresolved")
CMD_MARKERS = ("python3", "python ", "/", ".py", "--")


def parse_error_contract(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for raw in text.splitlines():
        ln = raw.strip()
        upper = ln.upper()
        for label, key in ((HAPPENED, "HAPPENED"), (MEANS, "MEANS"), (NEXT, "NEXT")):
            if upper.startswith(label):
                found[key] = ln[len(label) :].strip()
    return found


def error_names_next_action(text: str) -> tuple[bool, str]:
    found = parse_error_contract(text)
    if len(found.get("HAPPENED") or "") < 8:
        return False, "happened-missing"
    if len(found.get("MEANS") or "") < 8:
        return False, "means-missing"
    nxt = found.get("NEXT") or ""
    if len(nxt) < 8:
        return False, "next-missing"
    if not any(tok in nxt for tok in CMD_MARKERS):
        return False, "next-not-commandlike"
    return True, "ok"


def next_paths(text: str) -> list[str]:
    nxt = parse_error_contract(text).get("NEXT") or ""
    out: list[str] = []
    for tok in nxt.split():
        t = tok.strip("\"'")
        if "/" in t or t.endswith(".py"):
            out.append(t)
    return out


def next_action_reachable(text: str, repo: Path | None = None) -> tuple[bool, str]:
    repo = repo or REPO
    ok, why = error_names_next_action(text)
    if not ok:
        return False, why
    paths = next_paths(text)
    if not paths:
        return False, "no-path-in-next"
    for rel in paths:
        p = Path(rel)
        cand = p if p.is_absolute() else repo / rel
        if not cand.exists():
            return False, f"unreachable:{rel}"
    return True, "ok"


def live_measure_error(uid: str = "ARC-0054", reason: str = "predicate:absent") -> str:
    """Instance of command-center/p2-wave/_measure_one_delivered.py:28."""
    return f"FAILED:delivered {uid} {reason}"


def contract_rewrite_of_measure_error() -> str:
    nxt = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/_measure_one_delivered.py ARC-0054"
    )
    return (
        "HAPPENED: G-1 delivery measure rejected ARC-0054 (predicate:absent).\n"
        "MEANS: named probes, an honest non-BLOCKED artifact, and a per-unit "
        "manifest row are not all present; cloud ok=true is not delivery.\n"
        f"NEXT: {nxt}"
    )


def reviewer_trap_error() -> str:
    return (
        "HAPPENED: G-1 delivery measure rejected ARC-0054 (predicate:absent).\n"
        "MEANS: the product surface named a next action that cannot be run.\n"
        "NEXT: python3 command-center/phase3/A8/DESIGN.json"
    )


def stopping_documented(workflow: dict[str, Any]) -> tuple[bool, str]:
    stopping = workflow.get("stopping")
    if not isinstance(stopping, dict):
        return False, "stopping-absent"
    bound = any(isinstance(stopping.get(k), int) and stopping[k] >= 1 for k in BOUND_KEYS)
    if not bound:
        return False, "no-finite-bound"
    if not any(stopping.get(k) for k in DISPOSITION_KEYS):
        return False, "no-terminal-disposition"
    if not any(
        isinstance(stopping.get(k), str) and len(stopping[k].strip()) >= 16 for k in DOC_KEYS
    ):
        return False, "stopping-undocumented"
    return True, "ok"


def load_a1_workflow(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    doc = json.loads((repo / "command-center/phase3/A1/DESIGN.json").read_text(encoding="utf-8"))
    for sample in doc.get("samples") or []:
        if sample.get("id") == A1_WF_ID:
            cfg = ((sample.get("transcription") or {}).get("config")) or {}
            if isinstance(cfg, dict) and cfg:
                return cfg
    raise RuntimeError(f"A1 DESIGN.json missing {A1_WF_ID}")


def documented_copy(workflow: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(workflow))
    stopping = dict(out.get("stopping") or {})
    n_stages = len(out.get("stages") or [])
    if not any(isinstance(stopping.get(k), int) and stopping[k] >= 1 for k in BOUND_KEYS):
        stopping["max_stages"] = max(1, n_stages) if n_stages else 1
    if not any(stopping.get(k) for k in DISPOSITION_KEYS):
        stopping["on_error"] = "halt"
    bound = stopping.get("max_stages") or stopping.get("max_rounds") or 1
    disp = stopping.get("on_error") or stopping.get("on_timeout") or "halt"
    stopping["doc"] = (
        f"Stop after {bound} bound units; on_error={disp} "
        "and name the last completed stage id to the owner."
    )
    out["stopping"] = stopping
    return out


def catalog_stats(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    rel = "command-center/WORK-UNIT-CATALOG.json"
    units = json.loads((repo / rel).read_text(encoding="utf-8")).get("work_units") or []
    prefixes = Counter(str(u.get("id") or "").split("-")[0] for u in units if isinstance(u, dict))
    largest = max(prefixes.values()) if prefixes else 0
    largest_name = prefixes.most_common(1)[0][0] if prefixes else ""
    return {
        "path": rel,
        "n_items": len(units),
        "largest_bucket": largest,
        "largest_bucket_name": largest_name,
        "page_budget": PAGE_BUDGET,
        "has_job_index": (repo / "command-center/phase3/A8/DESIGN.json").is_file(),
        "prefix_counts": dict(prefixes.most_common(8)),
    }


def catalog_browseable(
    n_items: int,
    largest_bucket: int,
    has_job_index: bool,
    page_budget: int = PAGE_BUDGET,
) -> tuple[bool, str]:
    if n_items <= page_budget:
        return True, "fits-one-page"
    if has_job_index and largest_bucket <= page_budget:
        return True, "indexed-pages"
    return False, "too-large-unindexed"


def phase3_roster(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    root = repo / "command-center/phase3"
    names = sorted(
        p.name for p in root.iterdir() if p.is_dir() and re.fullmatch(r"A\d+", p.name)
    )
    return {
        "path": "command-center/phase3",
        "n_items": len(names),
        "ids": names,
        "page_budget": PAGE_BUDGET,
        "has_job_index": True,
        "largest_bucket": len(names),
    }


def dryrun_honest(plan: dict[str, Any], observed: dict[str, Any]) -> tuple[bool, str]:
    plan_files = set(plan.get("files") or [])
    obs_files = set(observed.get("files") or [])
    if not obs_files <= plan_files:
        return False, "underdeclared-files"
    try:
        plan_bytes = int(plan.get("bytes") or 0)
        obs_bytes = int(observed.get("bytes") or 0)
    except (TypeError, ValueError):
        return False, "bytes-unparseable"
    if plan_bytes < obs_bytes:
        return False, "underdeclared-bytes"
    return True, "ok"


def repair_status_ok(result: dict[str, Any], *, expect_healthy: bool) -> tuple[bool, str]:
    status = str(result.get("status") or "").upper().replace("_", "-")
    if not status:
        return False, "silent-empty-status"
    if expect_healthy:
        if status in {"SUCCESS", "OK", "PASS", "REPAIRED"}:
            return False, "healthy-reported-as-success"
        if status != "NO-OP":
            return False, f"healthy-not-noop:{status}"
        if int(result.get("bytes_written") or 0) != 0:
            return False, "healthy-wrote-bytes"
        return True, "noop"
    if status != "REPAIRED":
        return False, f"broken-not-repaired:{status}"
    if int(result.get("bytes_written") or 0) <= 0:
        return False, "repaired-but-silent-write"
    return True, "repaired"


AUTHOR_FAILURE_MODES = (
    {
        "id": "FM-ERROR-NO-NEXT",
        "title": "Error message naming no next action",
        "predicate": "error_names_next_action",
        "artifact_class": "error-string",
        "executable": True,
        "seeded_classes": ["exit-zero-with-missing-artifact", "detector-silent-in-both-states"],
    },
    {
        "id": "FM-STOP-UNDOCUMENTED",
        "title": "Workflow whose stopping rule is undocumented",
        "predicate": "stopping_documented",
        "artifact_class": "blueprint-field",
        "executable": True,
        "seeded_classes": [
            "council-deliberation-underspecified-stop",
            "trigger-mandated-threshold-unspecified",
        ],
    },
    {
        "id": "FM-CATALOG-UNBROWSEABLE",
        "title": "Catalog too large to browse",
        "predicate": "catalog_browseable",
        "artifact_class": "catalog-json",
        "executable": True,
        "seeded_classes": [
            "ignoring-an-existing-superior-workflow",
            "permission-boundary-colliding-catalog-merge",
        ],
    },
    {
        "id": "FM-DRYRUN-UNDERSTATES",
        "title": "Dry-run that misrepresents cost",
        "predicate": "dryrun_honest",
        "artifact_class": "dry-run-output",
        "executable": True,
        "seeded_classes": ["gameable-metric", "overclaim", "single-signal-verification"],
    },
    {
        "id": "FM-REPAIR-SILENT",
        "title": "Repair command that silently does nothing",
        "predicate": "repair_status_ok",
        "artifact_class": "repair-receipt",
        "executable": True,
        "seeded_classes": [
            "remote-harvest-silently-does-nothing",
            "exit-zero-with-missing-artifact",
        ],
    },
)
