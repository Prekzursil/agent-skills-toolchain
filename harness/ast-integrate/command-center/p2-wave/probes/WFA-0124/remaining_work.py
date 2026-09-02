"""Concrete remaining-work items. A category label is not schedulable."""
from __future__ import annotations

import re
from typing import Any

VAGUE = frozenset(
    {
        "implement",
        "fix",
        "todo",
        "later",
        "polish",
        "make executable",
        "executable",
        "do it",
        "tbd",
        "n/a",
        "category",
        "gap",
        "work",
    }
)
FIELD_OR_PATH = re.compile(
    r"(/)|(\.json\b)|(\.py\b)|(\bstages\b)|(\bgates\b)|(\bstop\b)|"
    r"(\be2e\b)|(\bdiscovery_only\b)|(\bsource_anchor\b)|(\bWFA-\d{4}\b)|"
    r"(09-WORKFLOW-BLUEPRINT-LIBRARY)",
    re.IGNORECASE,
)
ACCEPT_OBS = re.compile(
    r"(exists|is_file|exit_code|sha256|parse|classification|len\(|"
    r"flagship_identified|discovery_only|Path\.|size>|bytes|"
    r"load_ir|source_anchor)",
    re.IGNORECASE,
)
TASK_ID_RE = re.compile(r"^[A-Z][A-Z0-9_.-]{5,}$")


def is_concrete(task: Any) -> tuple[bool, str]:
    if not isinstance(task, dict):
        return False, "not-object"
    for key in ("task_id", "action", "acceptance", "owner_lane"):
        val = task.get(key)
        if not isinstance(val, str) or not val.strip():
            return False, f"missing:{key}"
    tid = task["task_id"].strip()
    action = task["action"].strip()
    acceptance = task["acceptance"].strip()
    lane = task["owner_lane"].strip()
    if not TASK_ID_RE.match(tid):
        return False, "task_id-shape"
    if action.lower() in VAGUE or len(action) < 40:
        return False, "action-vague-or-short"
    if not FIELD_OR_PATH.search(action):
        return False, "action-no-path-or-field"
    if len(acceptance) < 24 or not ACCEPT_OBS.search(acceptance):
        return False, "acceptance-not-observable"
    if lane.lower() in VAGUE or len(lane) < 4:
        return False, "owner_lane-vague"
    return True, "ok"


def all_concrete(tasks: list[Any]) -> tuple[bool, list[str]]:
    bad: list[str] = []
    if not isinstance(tasks, list) or not tasks:
        return False, ["empty-list"]
    for i, t in enumerate(tasks):
        ok, why = is_concrete(t)
        if not ok:
            bad.append(f"{i}:{why}")
    return (not bad), bad


def remeasure_after_change() -> dict[str, str]:
    """Schedulable remesure task. Acceptance must pass is_concrete()."""
    return {
        "task_id": "RW-REMEASURE-AFTER-LIBRARY-CHANGE",
        "action": (
            "Re-run command-center/p2-wave/probes/WFA-0124/emit_artifact.py "
            "after any change to 09-WORKFLOW-BLUEPRINT-LIBRARY.json or "
            "workflows/ so the measured executable count is not stale."
        ),
        "acceptance": (
            "Path.is_file() is true for command-center/wfa/"
            "WFA-0124-blueprint-executability-gap.json; probe1 exit_code==0 "
            "and sha256 of that output_path matches UNIT-ARTIFACT-MANIFEST.json."
        ),
        "owner_lane": "WFA-0124-remeasure",
    }


def library_absent_backlog() -> list[dict[str, str]]:
    return [
        {
            "task_id": "RW-RESTORE-09-LIBRARY",
            "action": (
                "Place the real 09-WORKFLOW-BLUEPRINT-LIBRARY.json (45-field "
                "records) at repo-root or command-center/sources/. Do not "
                "synthesize members from catalog_claim=108 and do not rebuild "
                "an ADV library circle."
            ),
            "acceptance": (
                "Path.is_file() is true for 09-WORKFLOW-BLUEPRINT-LIBRARY.json "
                "and expand_library_file yields n>=1 members matching the "
                "file's own records, not the catalog integer."
            ),
            "owner_lane": "library-restore-not-ADV",
        },
        {
            "task_id": "RW-DELIVER-WFA-0044-IR",
            "action": (
                "Deliver command-center/wfa/WFA-0044-workflow-ir-spec.json so "
                "IR load binds to the vendor-neutral WorkflowIR schema rather "
                "than this unit's local stages/gates/stop contract."
            ),
            "acceptance": (
                "WFA-0044 output_path exists, parses as JSON, and "
                "ir_contract.schema_path points at that file."
            ),
            "owner_lane": "WFA-0044",
        },
        {
            "task_id": "RW-SELECT-40-FLAGSHIP",
            "action": (
                "After live members exist and smoke writes artifacts, compute "
                "the 40-flagship subset by the identification rule "
                "(classification==executable AND e2e.path AND e2e.run_id AND "
                "e2e.pass). Do not pick forty ids by title."
            ),
            "acceptance": (
                "len(flagship_identified)==40 or the honest deficit is "
                "recorded; claimed-without-e2e ids are absent from the subset."
            ),
            "owner_lane": "IMP-0233",
        },
    ]


def member_work_template(bid: str = "<blueprint-id>") -> list[dict[str, str]]:
    return [
        {
            "task_id": "RW-FLIP-DISCOVERY-FLAG",
            "action": (
                f"On blueprint {bid} in 09-WORKFLOW-BLUEPRINT-LIBRARY.json, set "
                "discovery_only=false only after stages, gates, and stop are "
                "populated so is_placeholder() returns false on reload."
            ),
            "acceptance": (
                "JSON field discovery_only is false and declared_discovery_only"
                "(doc) returns False on reload of that id."
            ),
            "owner_lane": "blueprint-author",
        },
        {
            "task_id": "RW-IR-LOAD-FIELDS",
            "action": (
                f"Populate {bid} stages[].id, stages[].kind, gates, stop/"
                "stopping, and source_anchor so load_ir succeeds against the "
                "local WorkflowIR contract (WFA-0044 schema when present)."
            ),
            "acceptance": (
                "load_ir(doc).ok is true, ir.stages is non-empty, and every "
                "node has a source_anchor string."
            ),
            "owner_lane": "WFA-0044-adapter",
        },
        {
            "task_id": "RW-SMOKE-ARTIFACT",
            "action": (
                f"Add a runnable stages[].kind=python script (.py) on {bid} "
                "that writes a declared output under a clean tempfile "
                "(WFA0124_OUT) and record the smoke invocation plus exit_code."
            ),
            "acceptance": (
                "classification==executable, exit_code==0, and artifact_path "
                "exists with size>0 after the clean-temp smoke."
            ),
            "owner_lane": "IMP-0231-harness",
        },
        {
            "task_id": "RW-FLAGSHIP-E2E-IF-SELECTED",
            "action": (
                f"If {bid} is in the 40-flagship subset, add e2e.path to a "
                "test that asserts a postcondition on the produced artifact "
                "(exists, min bytes, json parse) and record e2e.run_id."
            ),
            "acceptance": (
                "flagship_identified includes this id; e2e.run_id is "
                "non-empty; deleting e2e.path demotes it out of the subset."
            ),
            "owner_lane": "IMP-0233-flagship-contract",
        },
    ]


def remaining_for_row(
    *,
    bid: str,
    executable: bool,
    ir_ok: bool,
    smoke_ok: bool,
    flagship_ok: bool,
    claimed_flagship: bool,
    discovery_only: bool,
) -> list[dict[str, str]]:
    """Exact remaining work for one measured blueprint. Empty only if smoke-ok
    and (not claimed flagship, or flagship identified)."""
    items: list[dict[str, str]] = []
    tmpl = {t["task_id"]: t for t in member_work_template(bid)}
    if discovery_only and not executable:
        items.append(tmpl["RW-FLIP-DISCOVERY-FLAG"])
    if not ir_ok:
        items.append(tmpl["RW-IR-LOAD-FIELDS"])
    if ir_ok and not smoke_ok:
        items.append(tmpl["RW-SMOKE-ARTIFACT"])
    if claimed_flagship and not flagship_ok:
        items.append(tmpl["RW-FLAGSHIP-E2E-IF-SELECTED"])
    if not items and not executable:
        items.append(tmpl["RW-IR-LOAD-FIELDS"])
        items.append(tmpl["RW-SMOKE-ARTIFACT"])
    return items


def category_label_mutant(bid: str) -> list[dict[str, str]]:
    """Deliberately vague remaining work. Detector must reject this."""
    return [
        {
            "task_id": "todo",
            "action": "make executable",
            "acceptance": "done",
            "owner_lane": "later",
        }
    ]
