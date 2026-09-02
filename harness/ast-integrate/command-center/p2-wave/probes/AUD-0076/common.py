"""Shared paths and planted-canary constants for AUD-0076."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0076"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/audit/AUD-0076-owner-requirement-recovery.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_SCHEMA_REL = "platform/schema/receipt.schema.json"
CATALOG = REPO / CATALOG_REL
OUT = REPO / OUT_REL
SCHEMA = REPO / SCHEMA_REL

PLANTED_TOKEN = "AUD0076-PLANTED-CANARY-PURPLE-RECEIPT"
PLANTED_TEXT = (
    "The owner requires every frobnicator to emit a purple receipt tagged "
    f"{PLANTED_TOKEN} and this sentence must not match any live artifact."
)

COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0076 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which owner requirements stated across the 375-message transcript are "
    "not represented in any current artifact, decision, or work unit?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0076/probe1_extract.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0076/probe2_classify.py"
)

TRANSCRIPT_CANDIDATES = (
    "_USER-PROMPTS.md",
    "command-center/_USER-PROMPTS.md",
    "command-center/p2-wave/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    str(Path.home() / ".claude/harness-restore-20260806/_USER-PROMPTS.md"),
)

BINDING_SEEDS = (
    {
        "id": "REQ-BIND-DELETE-ALL",
        "text": (
            "Retirement scope is DELETE-ALL across five trees "
            "(owner-approved deletion of 77 files)."
        ),
        "needles": ("DELETE-ALL across five trees", "owner-approved DELETE-ALL"),
    },
    {
        "id": "REQ-BIND-SALVAGE",
        "text": "Salvage home for retained modules is tools/lib/ shared tree.",
        "needles": ("salvage home = tools/lib/", "salvage into tools/lib"),
    },
    {
        "id": "REQ-BIND-NOREMOTE",
        "text": (
            "No-remote repos: triage first, never create remotes."
        ),
        "needles": ("never create remotes", "no-remote repos = triage first"),
    },
    {
        "id": "REQ-BIND-OPUS",
        "text": (
            "Substantive subagents default to Opus, not Sonnet "
            "(owner aside / performance floor)."
        ),
        "needles": (
            "Opus-not-Sonnet subagent preference",
            "substantive subagents default to Opus",
        ),
    },
)


def find_line(text: str, snippet: str) -> int:
    idx = text.find(snippet)
    if idx < 0:
        return -1
    return text[:idx].count("\n") + 1


def probe_fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def _from_containers(doc: dict, key: str) -> Any:
    for container in (doc.get("report"), doc.get("extensions"), doc):
        if isinstance(container, dict) and key in container:
            return container[key]
    return None


def artifact_requirements(doc: dict) -> list[dict]:
    reqs = _from_containers(doc, "requirements")
    if isinstance(reqs, list):
        return [r for r in reqs if isinstance(r, dict)]
    return []


def artifact_probe_records(doc: dict) -> dict:
    rec = _from_containers(doc, "named_probe_records")
    return rec if isinstance(rec, dict) else {}


def audit_finding_validator():
    """Disk-only validator for the catalog output_schema $ref shim.

    jsonschema 4.10 Draft7Validator follows the shim $ref over HTTPS to
    ast-integrate.invalid and raises. Load the physical profiles + receipt
    schemas from disk instead.
    """
    from jsonschema import Draft202012Validator, RefResolver

    profiles = json.loads((REPO / PROFILES_REL).read_text(encoding="utf-8"))
    receipt = json.loads((REPO / RECEIPT_SCHEMA_REL).read_text(encoding="utf-8"))
    store = {profiles["$id"]: profiles, receipt["$id"]: receipt}
    schema = {"$ref": profiles["$id"] + "#/$defs/audit-finding"}
    resolver = RefResolver(base_uri=profiles["$id"], referrer=profiles, store=store)
    return Draft202012Validator(schema, resolver=resolver)
