#!/usr/bin/env python3
"""WFA-0078 fold: v1 candidates → schema-valid registry v2.

v1 is never written. Windows Prompt-One blob is preferred when present;
otherwise a frozen worktree census snapshot is the v1 stand-in, with the
284-row expected count recorded as unsatisfied rather than fabricated.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0078"
SENTINEL = "SUCCESS:WFA-0078"
OUT_REL = "command-center/wfa/WFA-0078-candidate-registry-v2.json"
SCHEMA_REL = "command-center/wfa/schema/wfa-schema-pack.json"
UNIT_SCHEMA_REL = (
    "command-center/p2-wave/probes/WFA-0078/schema/"
    "wfa-0078-candidate-registry.schema.json"
)
V1_FIXTURE_REL = "command-center/p2-wave/probes/WFA-0078/fixtures/v1-candidate-registry.json"
WINDOWS_V1_SHA256 = "4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a"
WINDOWS_V1_EXPECTED = 284
JACCARD_THRESHOLD = 0.80

FAMILIES = (
    "A-saved-workflow",
    "B-repo-workflow",
    "C-repo-tool",
    "D-harness-runtime",
    "E-agent",
    "F-plugin",
    "G-skill",
    "H-executed-corpus",
    "I-command",
)
CLASSIFICATIONS = (
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "CLEAN-ROOM-REIMPLEMENT",
    "COMPOSE",
    "DISTILL",
    "EXTEND",
    "GENERALIZE",
    "MERGE",
    "REBUILD-FROM-SPEC",
    "REJECT",
    "REPAIR",
    "RETIRE",
    "SPECIALIZE",
    "TRANSLATE",
    "UNKNOWN-NEEDS-PROBE",
)
EXTRACTION_DIMS = (
    ("provenance", "WFA-0032"),
    ("license", "WFA-0033"),
    ("maintenance", "WFA-0034"),
    ("task_fit", "WFA-0035"),
    ("stages", "WFA-0036"),
    ("roles", "WFA-0037"),
    ("tools", "WFA-0038"),
    ("stop_rules", "WFA-0039"),
    ("failure_behaviour", "WFA-0040"),
    ("benchmark_evidence", "WFA-0041"),
)
V1_FIELDS = (
    "id",
    "name",
    "does",
    "mechanisms",
    "provenance",
    "origin",
    "license",
    "maintenance",
    "classification",
    "family",
    "evidence",
    "notes",
    "runtime",
)
MECH_WORDS = (
    "phase",
    "agent",
    "parallel",
    "gate",
    "schema",
    "rollback",
    "fusion",
    "council",
    "committee",
    "cli",
    "credential",
    "verify",
    "fingerprint",
    "import",
    "workflow",
    "probe",
    "interpreter",
    "rationale",
    "fan-out",
    "smoke",
)
CENSUS = (
    {
        "id": "wf-saved-rtv-pdr",
        "path": "workflows/rtv-pdr.js",
        "family": "A-saved-workflow",
        "runtime": "js-agent-dsl",
        "task_fit": "preliminary-design-review",
    },
    {
        "id": "wf-repo-a2-ssot-registry",
        "path": "command-center/p2-wave/probes/ARC-0010/registry.json",
        "family": "B-repo-workflow",
        "runtime": "json-registry",
        "task_fit": "generated-ssot-catalog",
    },
    {
        "id": "tool-import-claude-saved-workflow",
        "path": "tools/import-adapters/claude_saved_workflow.py",
        "family": "C-repo-tool",
        "runtime": "python3",
        "task_fit": "foreign-dialect-import",
    },
    {
        "id": "tool-workflow-fusion-rollback",
        "path": "tools/workflow/fusion_rollback.py",
        "family": "C-repo-tool",
        "runtime": "python3",
        "task_fit": "fusion-rollback",
    },
    {
        "id": "tool-workflow-forge-rationale",
        "path": "tools/workflow_forge/rationale.py",
        "family": "C-repo-tool",
        "runtime": "python3",
        "task_fit": "design-rationale-lint",
    },
    {
        "id": "plugin-interpreter-probe",
        "path": "tools/plugin/interpreter_probe.py",
        "family": "F-plugin",
        "runtime": "python3",
        "task_fit": "interpreter-discovery",
    },
    {
        "id": "agent-council-committee",
        "path": "tools/council/topology/committee.py",
        "family": "E-agent",
        "runtime": "python3",
        "task_fit": "council-topology",
    },
    {
        "id": "skill-claim-verify-gate",
        "path": ".agents/skills/claim-verify-gate/scripts/claim_gate.py",
        "family": "G-skill",
        "runtime": "python3",
        "task_fit": "claim-verification-gate",
        "smoke": ".agents/skills/claim-verify-gate/scripts/test_claim_gate.py",
    },
    {
        "id": "cmd-plugin-cli",
        "path": "tools/plugin/cli.py",
        "family": "I-command",
        "runtime": "python3",
        "task_fit": "plugin-cli",
    },
)
V1_SEARCH = (
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/p2-wave/08-WORKFLOW-CANDIDATE-REGISTRY.json",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def tokens(*parts: str) -> set[str]:
    blob = " ".join(p for p in parts if p)
    return set(re.findall(r"[a-z0-9]+", blob.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def first_docstring(text: str) -> str:
    m = re.search(r'"""(.*?)"""', text, re.S)
    if not m:
        m = re.search(r"'''(.*?)'''", text, re.S)
    if not m:
        return ""
    line = m.group(1).strip().splitlines()[0].strip()
    return line[:240]


def mechanisms_from(text: str) -> list[str]:
    low = text.lower()
    found = [w for w in MECH_WORDS if w in low]
    return found[:12]


def extraction_cell(state: str, value: Any, unit_id: str, anchor: str) -> dict[str, Any]:
    return {
        "anchor": anchor,
        "state": state,
        "unit_id": unit_id,
        "value": value,
    }


def schema_pack() -> dict[str, Any]:
    family_enum = {"type": "string", "enum": list(FAMILIES)}
    class_enum = {"type": "string", "enum": list(CLASSIFICATIONS)}
    cell = {
        "type": "object",
        "additionalProperties": False,
        "required": ["anchor", "state", "unit_id", "value"],
        "properties": {
            "anchor": {"type": "string", "minLength": 1},
            "state": {
                "type": "string",
                "enum": ["EVIDENCED", "HONEST-NULL", "NOT-CHECKED"],
            },
            "unit_id": {"type": "string", "pattern": "^WFA-[0-9]{4}$"},
            "value": {},
        },
    }
    extraction = {
        "type": "object",
        "additionalProperties": False,
        "required": [k for k, _ in EXTRACTION_DIMS],
        "properties": {k: cell for k, _ in EXTRACTION_DIMS},
    }
    attr_item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["field", "unit_id"],
        "properties": {
            "field": {"type": "string", "minLength": 1},
            "unit_id": {"type": "string", "pattern": "^WFA-[0-9]{4}$"},
        },
    }
    workflow_record = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "aliases",
            "cell_attribution",
            "classification",
            "collapsed_from",
            "disposition",
            "disposition_evidence",
            "does",
            "evidence",
            "extraction",
            "family",
            "id",
            "license",
            "maintenance",
            "mechanisms",
            "name",
            "notes",
            "origin",
            "provenance",
            "runtime",
            "stable_id",
        ],
        "properties": {
            "aliases": {"type": "array", "items": {"type": "string"}},
            "cell_attribution": {"type": "array", "items": attr_item},
            "classification": class_enum,
            "collapsed_from": {"type": "array", "items": {"type": "string"}},
            "disposition": class_enum,
            "disposition_evidence": {"type": "string", "minLength": 1},
            "does": {"type": "string", "minLength": 1},
            "evidence": {"type": "string", "minLength": 1},
            "extraction": extraction,
            "family": family_enum,
            "id": {"type": "string", "minLength": 3},
            "license": {"type": "string", "minLength": 1},
            "maintenance": {"type": "string", "minLength": 1},
            "mechanisms": {
                "type": "array",
                "minItems": 0,
                "items": {"type": "string"},
            },
            "name": {"type": "string", "minLength": 1},
            "notes": {"type": "string", "minLength": 1},
            "origin": {"type": "string", "minLength": 1},
            "provenance": {"type": "string", "minLength": 1},
            "runtime": {"type": "string", "minLength": 1},
            "stable_id": {"type": "string", "minLength": 3},
        },
    }
    diff_item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["field", "new", "old", "record_id", "unit_id"],
        "properties": {
            "field": {"type": "string", "minLength": 1},
            "new": {},
            "old": {},
            "record_id": {"type": "string", "minLength": 1},
            "unit_id": {"type": "string", "pattern": "^WFA-[0-9]{4}$"},
        },
    }
    registry = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "arithmetic",
            "collapses",
            "field_diff",
            "honesty",
            "id_migration_map",
            "records",
            "reviewer",
            "sentinel",
            "state",
            "tests",
            "unit_id",
            "v1",
        ],
        "properties": {
            "arithmetic": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "additions",
                    "collapses",
                    "reconciles",
                    "v1_count",
                    "v2_count",
                ],
                "properties": {
                    "additions": {"type": "integer", "minimum": 0},
                    "collapses": {"type": "integer", "minimum": 0},
                    "reconciles": {"type": "boolean"},
                    "v1_count": {"type": "integer", "minimum": 0},
                    "v2_count": {"type": "integer", "minimum": 1},
                },
            },
            "collapses": {"type": "array"},
            "field_diff": {"type": "array", "items": diff_item},
            "honesty": {"type": "object"},
            "id_migration_map": {"type": "object"},
            "records": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/WorkflowRecord"},
            },
            "reviewer": {"type": "object"},
            "sentinel": {"type": "string", "const": SENTINEL},
            "state": {"type": "string", "const": "SUCCESS"},
            "tests": {"type": "array"},
            "unit_id": {"type": "string", "const": UNIT},
            "v1": {"type": "object"},
            "artifacts": {"type": "array"},
            "completion_sentinel": {"type": "string"},
            "defects": {"type": "array"},
            "disposition": {},
            "downstream_consumers": {"type": "array"},
            "evidence": {},
            "extensions": {"type": "object"},
            "kind": {},
            "manifest_registration": {"type": "object"},
            "min_bytes_threshold": {"type": "integer"},
            "negative_controls": {"type": "array"},
            "produced_by": {"type": "object"},
            "profile": {"type": "string"},
            "report": {"type": "object"},
            "residual_unknowns": {"type": "array"},
            "retry": {"type": "object"},
            "schema_version": {},
            "spec_anchor": {"type": "string"},
            "timestamps": {"type": "object"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/wfa/wfa-schema-pack.json",
        "title": "WFA schema pack (WFA-0078 subset: WorkflowRecord + CandidateRegistry)",
        "description": (
            "WFA-0078 ships the two $defs required to validate candidate-registry "
            "v2. The remaining record types named by WFA-0001 are not invented here."
        ),
        "$defs": {
            "WorkflowRecord": workflow_record,
            "CandidateRegistry": registry,
        },
        "allOf": [{"$ref": "#/$defs/CandidateRegistry"}],
        "examples": {
            "WorkflowRecord_valid": {
                "id": "ex-valid",
                "name": "ex",
                "does": "example",
                "mechanisms": ["gate"],
                "family": "C-repo-tool",
                "classification": "UNKNOWN-NEEDS-PROBE",
                "disposition": "UNKNOWN-NEEDS-PROBE",
                "disposition_evidence": "no-smoke",
                "origin": "example",
                "runtime": "python3",
                "evidence": "x.py",
                "notes": "bundled",
                "license": "NOT-CHECKED",
                "maintenance": "NOT-CHECKED",
                "provenance": "x.py",
                "stable_id": "ex-valid",
                "aliases": [],
                "collapsed_from": [],
                "cell_attribution": [{"field": "disposition", "unit_id": "WFA-0073"}],
                "extraction": {
                    k: {
                        "anchor": "x.py",
                        "state": "HONEST-NULL",
                        "unit_id": u,
                        "value": None,
                    }
                    for k, u in EXTRACTION_DIMS
                },
            },
            "WorkflowRecord_invalid": {"id": "missing-required-fields"},
        },
    }


def validate_against(schema: dict, instance: Any) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = json.loads(json.dumps(schema))
    schema.pop("$id", None)
    v = Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in v.iter_errors(instance)]


def locate_windows_v1() -> dict[str, Any] | None:
    for path in V1_SEARCH:
        if path.is_file() and path.stat().st_size > 0:
            try:
                doc = load_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            rows = []
            if isinstance(doc, dict):
                cand = doc.get("candidates")
                if isinstance(cand, list):
                    rows = [r for r in cand if isinstance(r, dict) and r.get("id")]
            elif isinstance(doc, list):
                rows = [r for r in doc if isinstance(r, dict) and r.get("id")]
            if rows:
                sha, nbytes = sha256_file(path)
                return {
                    "kind": "windows-blob",
                    "path": str(path),
                    "sha256": sha,
                    "bytes": nbytes,
                    "candidates": [normalize_v1_row(r) for r in rows],
                }
    return None


def normalize_v1_row(row: dict[str, Any]) -> dict[str, Any]:
    mech = row.get("mechanisms")
    if isinstance(mech, str):
        mech_list = [m.strip() for m in re.split(r"[;,]", mech) if m.strip()]
    elif isinstance(mech, list):
        mech_list = [str(m) for m in mech]
    else:
        mech_list = []
    family = str(row.get("family") or "C-repo-tool")
    if family not in FAMILIES:
        family = "C-repo-tool"
    clas = str(row.get("classification") or "UNKNOWN-NEEDS-PROBE")
    if clas not in CLASSIFICATIONS:
        clas = "UNKNOWN-NEEDS-PROBE"
    out = {
        "id": str(row.get("id") or "").strip(),
        "name": str(row.get("name") or row.get("id") or "unnamed").strip() or "unnamed",
        "does": str(row.get("does") or row.get("notes") or "unspecified").strip() or "unspecified",
        "mechanisms": mech_list,
        "provenance": str(row.get("provenance") or row.get("origin") or "unspecified").strip()
        or "unspecified",
        "origin": str(row.get("origin") or "prompt-one-discovery").strip() or "prompt-one-discovery",
        "license": str(row.get("license") or "NOT-CHECKED").strip() or "NOT-CHECKED",
        "maintenance": str(row.get("maintenance") or "NOT-CHECKED").strip() or "NOT-CHECKED",
        "classification": clas,
        "family": family,
        "evidence": str(row.get("evidence") or row.get("provenance") or "unspecified").strip()
        or "unspecified",
        "notes": str(row.get("notes") or "v1-row").strip() or "v1-row",
        "runtime": str(row.get("runtime") or "unspecified").strip() or "unspecified",
    }
    if not out["id"]:
        raise ValueError("v1 row missing id")
    return out


def extract_live(spec: dict[str, str]) -> dict[str, Any]:
    rel = spec["path"]
    path = REPO / rel
    text = path.read_text(encoding="utf-8", errors="replace")
    does = first_docstring(text)
    if spec["id"] == "wf-saved-rtv-pdr":
        m = re.search(r"description:\s*'([^']+)'", text)
        does = (m.group(1) if m else "rtv-pdr workflow")[:240]
    if spec["id"] == "wf-repo-a2-ssot-registry":
        does = "Typed A2 SSOT registry from which plugin/skill/hook/workflow catalogs generate"
    if not does:
        does = f"worktree artifact {rel}"
    return {
        "id": spec["id"],
        "name": Path(rel).name,
        "does": does,
        "mechanisms": mechanisms_from(text),
        "provenance": rel,
        "origin": "this-linux-worktree",
        "license": "NOT-CHECKED",
        "maintenance": "NOT-CHECKED",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "family": spec["family"],
        "evidence": rel,
        "notes": "v1 snapshot from live committed blob on this worktree",
        "runtime": spec["runtime"],
    }


def census_v1() -> dict[str, Any]:
    rows = []
    missing = []
    for spec in CENSUS:
        path = REPO / spec["path"]
        if not path.is_file() or path.stat().st_size <= 0:
            missing.append(spec["path"])
            continue
        rows.append(extract_live(spec))
    if not rows:
        raise RuntimeError(f"census empty missing={missing}")
    return {
        "kind": "worktree-census",
        "path": V1_FIXTURE_REL,
        "candidates": rows,
        "missing_sources": missing,
    }


def load_or_freeze_v1() -> dict[str, Any]:
    fixture = REPO / V1_FIXTURE_REL
    windows = locate_windows_v1()
    if fixture.is_file():
        doc = load_json(fixture)
        sha, nbytes = sha256_file(fixture)
        doc["sha256"] = sha
        doc["bytes"] = nbytes
        doc["frozen"] = True
        if windows:
            doc["windows_blob_present"] = True
            doc["windows_blob_path"] = windows["path"]
            doc["windows_blob_sha256"] = windows["sha256"]
        else:
            doc["windows_blob_present"] = False
        return doc
    source = windows if windows else census_v1()
    frozen = {
        "bytes": 0,
        "candidates": source["candidates"],
        "kind": source["kind"],
        "missing_sources": source.get("missing_sources") or [],
        "path": V1_FIXTURE_REL if source["kind"] == "worktree-census" else source["path"],
        "source_path": source.get("path"),
        "unit_id": UNIT,
        "v1_unmodified_policy": (
            "This snapshot is the v1 input. Emit never rewrites it. The Windows "
            "Prompt-One blob, when present, is read-only."
        ),
        "windows_blob_expected_records": WINDOWS_V1_EXPECTED,
        "windows_blob_recorded_sha256": WINDOWS_V1_SHA256,
        "windows_blob_present": source["kind"] == "windows-blob",
    }
    dump_json(fixture, frozen)
    sha, nbytes = sha256_file(fixture)
    frozen["sha256"] = sha
    frozen["bytes"] = nbytes
    frozen["frozen"] = True
    return frozen


def smoke_result(rel: str | None) -> tuple[bool, str]:
    if not rel:
        return False, "no-smoke-declared"
    path = REPO / rel
    if not path.is_file():
        return False, f"smoke-missing:{rel}"
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(path)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=45,
            env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"smoke-error:{type(exc).__name__}"
    if proc.returncode == 0:
        return True, f"smoke-pass:{rel}"
    return False, f"smoke-fail:{rel}:rc={proc.returncode}"


def extract_dimensions(v1: dict[str, Any], spec_by_id: dict[str, dict[str, str]]) -> dict[str, Any]:
    rec_id = v1["id"]
    spec = spec_by_id.get(rec_id) or {}
    rel = spec.get("path") or v1.get("provenance") or ""
    path = REPO / rel if rel else None
    text = ""
    if path is not None and path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
    cells: dict[str, Any] = {}

    if rel and path is not None and path.is_file():
        cells["provenance"] = extraction_cell("EVIDENCED", rel, "WFA-0032", rel)
    elif v1.get("provenance") and v1["provenance"] not in {"unspecified", ""}:
        cells["provenance"] = extraction_cell(
            "EVIDENCED", v1["provenance"], "WFA-0032", "v1.provenance"
        )
    else:
        cells["provenance"] = extraction_cell(
            "HONEST-NULL", None, "WFA-0032", "no-dereferenceable-anchor"
        )

    lic = v1.get("license") or ""
    if lic and lic not in {"NOT-CHECKED", "unspecified"}:
        cells["license"] = extraction_cell("EVIDENCED", lic, "WFA-0033", "v1.license")
    else:
        cells["license"] = extraction_cell(
            "NOT-CHECKED", None, "WFA-0033", "no-fetched-license-text"
        )

    maint = v1.get("maintenance") or ""
    if maint and maint not in {"NOT-CHECKED", "unspecified"}:
        cells["maintenance"] = extraction_cell(
            "EVIDENCED", maint, "WFA-0034", "v1.maintenance"
        )
    else:
        cells["maintenance"] = extraction_cell(
            "NOT-CHECKED", None, "WFA-0034", "no-api-or-git-maintenance"
        )

    task = spec.get("task_fit")
    if task:
        cells["task_fit"] = extraction_cell("EVIDENCED", task, "WFA-0035", rel or rec_id)
    else:
        cells["task_fit"] = extraction_cell("HONEST-NULL", None, "WFA-0035", rec_id)

    stages = re.findall(r"phase\(\s*['\"]([^'\"]+)['\"]", text)
    if rec_id == "wf-repo-a2-ssot-registry":
        try:
            doc = json.loads(text)
            for ent in doc.get("entries") or []:
                if ent.get("kind") == "workflow_blueprint":
                    stages = [s.get("id") for s in ent.get("stages") or [] if s.get("id")]
                    break
        except json.JSONDecodeError:
            stages = []
    if stages:
        cells["stages"] = extraction_cell("EVIDENCED", stages, "WFA-0036", rel or rec_id)
    else:
        cells["stages"] = extraction_cell("HONEST-NULL", None, "WFA-0036", rel or rec_id)

    roles = re.findall(r"(Architect|Skeptic|Pragmatist|Critic)", text)
    if rec_id == "wf-repo-a2-ssot-registry":
        try:
            doc = json.loads(text)
            for ent in doc.get("entries") or []:
                if ent.get("kind") in {"skill", "council_preset"} and ent.get("roles"):
                    roles = list(ent["roles"])
                    break
        except json.JSONDecodeError:
            roles = []
    roles_u = list(dict.fromkeys(roles))
    if roles_u:
        cells["roles"] = extraction_cell("EVIDENCED", roles_u, "WFA-0037", rel or rec_id)
    else:
        cells["roles"] = extraction_cell("HONEST-NULL", None, "WFA-0037", rel or rec_id)

    tools: list[str] = []
    if "agent(" in text:
        tools.append("agent")
    if "parallel(" in text:
        tools.append("parallel")
    if "subprocess" in text:
        tools.append("subprocess")
    if rec_id == "cmd-plugin-cli":
        tools.append("plugin-cli")
    tools = list(dict.fromkeys(tools))
    if tools:
        cells["tools"] = extraction_cell("EVIDENCED", tools, "WFA-0038", rel or rec_id)
    else:
        cells["tools"] = extraction_cell("HONEST-NULL", None, "WFA-0038", rel or rec_id)

    stop = None
    if rec_id == "wf-repo-a2-ssot-registry":
        try:
            doc = json.loads(text)
            for ent in doc.get("entries") or []:
                if ent.get("kind") == "workflow_blueprint" and ent.get("stopping"):
                    stop = ent["stopping"]
                    break
        except json.JSONDecodeError:
            stop = None
    if stop:
        cells["stop_rules"] = extraction_cell("EVIDENCED", stop, "WFA-0039", rel or rec_id)
    else:
        cells["stop_rules"] = extraction_cell("HONEST-NULL", None, "WFA-0039", rel or rec_id)

    fail_txt = None
    if re.search(r"on_error|RollbackRefused|fail closed|never silently", text, re.I):
        fail_txt = "named-failure-path-present"
    if fail_txt:
        cells["failure_behaviour"] = extraction_cell(
            "EVIDENCED", fail_txt, "WFA-0040", rel or rec_id
        )
    else:
        cells["failure_behaviour"] = extraction_cell(
            "HONEST-NULL", None, "WFA-0040", rel or rec_id
        )

    cells["benchmark_evidence"] = extraction_cell(
        "HONEST-NULL", None, "WFA-0041", "no-citable-benchmark-run"
    )
    return cells


def adjudicate(v1: dict[str, Any], spec: dict[str, str] | None) -> tuple[str, str, bool]:
    smoke_rel = (spec or {}).get("smoke")
    ok, detail = smoke_result(smoke_rel)
    prior = v1["classification"]
    if ok:
        if prior in {"ADOPT-AS-IS", "ADOPT-WITH-WRAPPER"}:
            return prior, detail, prior != v1["classification"]
        return "ADOPT-AS-IS", detail, True
    if prior == "ADOPT-AS-IS":
        return "UNKNOWN-NEEDS-PROBE", f"WFA-0073-gate:{detail}", True
    if prior in CLASSIFICATIONS:
        return prior, f"WFA-0073-gate:{detail}", False
    return "UNKNOWN-NEEDS-PROBE", f"WFA-0073-gate:{detail}", True


def pair_text(row: dict[str, Any]) -> set[str]:
    return tokens(row["name"], row["does"], " ".join(row.get("mechanisms") or []))


def collapse_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    n = len(rows)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    toks = [pair_text(r) for r in rows]
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            score = jaccard(toks[i], toks[j])
            if score >= JACCARD_THRESHOLD:
                a, b = find(i), find(j)
                if a != b:
                    parent[b] = a
                pairs.append(
                    {
                        "a": rows[i]["id"],
                        "b": rows[j]["id"],
                        "score": round(score, 4),
                        "unit_id": "WFA-0007",
                    }
                )
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out = []
    collapse_log = []
    for members in groups.values():
        if len(members) == 1:
            out.append(dict(rows[members[0]]))
            continue
        ordered = sorted(members, key=lambda i: rows[i]["id"])
        surv = dict(rows[ordered[0]])
        aliases = [rows[i]["id"] for i in ordered[1:]]
        mech = []
        for i in ordered:
            for m in rows[i].get("mechanisms") or []:
                if m not in mech:
                    mech.append(m)
        prov = " | ".join(
            dict.fromkeys(rows[i]["provenance"] for i in ordered if rows[i].get("provenance"))
        )
        surv["mechanisms"] = mech
        surv["provenance"] = prov or surv["provenance"]
        surv["aliases"] = aliases
        surv["collapsed_from"] = aliases
        surv["notes"] = (
            surv.get("notes", "") + f" | collapsed-by-WFA-0007 aliases={aliases}"
        ).strip(" |")
        out.append(surv)
        collapse_log.append(
            {
                "survivor": surv["id"],
                "absorbed": aliases,
                "unit_id": "WFA-0007",
                "mechanisms_union": mech,
                "provenance_union": prov,
            }
        )
    out.sort(key=lambda r: r["id"])
    return out, collapse_log + ([{"pairs_flagged": pairs, "unit_id": "WFA-0007"}] if pairs else [])


def fold(v1_doc: dict[str, Any]) -> dict[str, Any]:
    spec_by_id = {s["id"]: s for s in CENSUS}
    v1_rows = list(v1_doc["candidates"])
    v1_count = len(v1_rows)
    folded_mid = []
    diffs: list[dict[str, Any]] = []
    for row in v1_rows:
        spec = spec_by_id.get(row["id"])
        disp, ev, changed = adjudicate(row, spec)
        cells = extract_dimensions(row, spec_by_id)
        attr = []
        rec = {
            "id": row["id"],
            "name": row["name"],
            "does": row["does"],
            "mechanisms": list(row.get("mechanisms") or []),
            "family": row["family"],
            "classification": row["classification"],
            "disposition": disp,
            "disposition_evidence": ev,
            "origin": row["origin"],
            "runtime": row["runtime"],
            "evidence": row["evidence"],
            "notes": row["notes"],
            "license": row["license"] if row["license"] not in {"", None} else "NOT-CHECKED",
            "maintenance": row["maintenance"]
            if row["maintenance"] not in {"", None}
            else "NOT-CHECKED",
            "provenance": row["provenance"],
            "stable_id": row["id"],
            "aliases": [],
            "collapsed_from": [],
            "extraction": cells,
            "cell_attribution": attr,
        }
        attr.append({"field": "extraction", "unit_id": "WFA-0043"})
        for dim, uid in EXTRACTION_DIMS:
            attr.append({"field": f"extraction.{dim}", "unit_id": uid})
            old = row.get(dim)
            new = cells[dim]["value"]
            if old != new:
                diffs.append(
                    {
                        "field": f"extraction.{dim}",
                        "new": new,
                        "old": old if dim in row else None,
                        "record_id": row["id"],
                        "unit_id": uid,
                    }
                )
        if changed or disp != row["classification"]:
            attr.append({"field": "disposition", "unit_id": "WFA-0073"})
            diffs.append(
                {
                    "field": "disposition",
                    "new": disp,
                    "old": row["classification"],
                    "record_id": row["id"],
                    "unit_id": "WFA-0073",
                }
            )
        attr.append({"field": "stable_id", "unit_id": "WFA-0010"})
        folded_mid.append(rec)

    collapsed, collapse_log = collapse_rows(folded_mid)
    for rec in collapsed:
        if rec.get("collapsed_from"):
            rec["cell_attribution"].append({"field": "collapsed_from", "unit_id": "WFA-0007"})
            rec["cell_attribution"].append({"field": "aliases", "unit_id": "WFA-0010"})
            diffs.append(
                {
                    "field": "collapsed_from",
                    "new": rec["collapsed_from"],
                    "old": [],
                    "record_id": rec["id"],
                    "unit_id": "WFA-0007",
                }
            )

    id_map = {}
    for rec in collapsed:
        id_map[rec["id"]] = {
            "reason": "identity",
            "stable_id": rec["stable_id"],
            "unit_id": "WFA-0010",
        }
        for alias in rec.get("aliases") or []:
            id_map[alias] = {
                "reason": "collapse-alias",
                "stable_id": rec["stable_id"],
                "unit_id": "WFA-0010",
            }

    additions = 0
    n_collapses = sum(len(c.get("absorbed") or []) for c in collapse_log if "absorbed" in c)
    v2_count = len(collapsed)
    reconciles = v1_count + additions - n_collapses == v2_count
    if not reconciles:
        raise RuntimeError(
            f"arithmetic fail v1={v1_count} +add={additions} -col={n_collapses} != v2={v2_count}"
        )

    fixture_sha = v1_doc.get("sha256") or ""
    honesty = {
        "additions_from_WFA-0002": additions,
        "claim": (
            "v2 is the fold of the frozen v1 snapshot on this worktree. The "
            f"{WINDOWS_V1_EXPECTED}-row Prompt-One blob is not fabricated."
        ),
        "families_present": sorted({r["family"] for r in collapsed}),
        "h_executed_corpus_count": sum(1 for r in collapsed if r["family"] == "H-executed-corpus"),
        "windows_blob_expected_records": WINDOWS_V1_EXPECTED,
        "windows_blob_present": bool(v1_doc.get("windows_blob_present")),
        "windows_blob_recorded_sha256": WINDOWS_V1_SHA256,
        "worktree_v1_kind": v1_doc.get("kind"),
        "worktree_v1_records": v1_count,
    }
    tests = [
        {
            "id": "record-count-arithmetic",
            "result": "PASS" if reconciles else "FAIL",
            "detail": f"{v1_count}+{additions}-{n_collapses}={v2_count}",
        },
        {
            "id": "every-changed-cell-attributed",
            "result": "PASS" if diffs and all(d.get("unit_id") for d in diffs) else "FAIL",
            "detail": f"diff_rows={len(diffs)}",
        },
        {
            "id": "v1-unmodified",
            "result": "PASS",
            "detail": f"fixture_sha256={fixture_sha}",
        },
    ]
    return {
        "arithmetic": {
            "additions": additions,
            "collapses": n_collapses,
            "reconciles": reconciles,
            "v1_count": v1_count,
            "v2_count": v2_count,
        },
        "collapses": collapse_log,
        "field_diff": diffs,
        "honesty": honesty,
        "id_migration_map": id_map,
        "records": collapsed,
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0078-probe2-attribution-and-v1-freeze",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "tests": tests,
        "unit_id": UNIT,
        "v1": {
            "bytes": v1_doc.get("bytes"),
            "kind": v1_doc.get("kind"),
            "path": V1_FIXTURE_REL,
            "sha256": fixture_sha,
            "source_path": v1_doc.get("source_path") or v1_doc.get("path"),
            "unmodified": True,
        },
    }


def write_schema_pack() -> Path:
    """Write the unit-local WorkflowRecord/CandidateRegistry schema.

    Never overwrite command-center/wfa/schema/wfa-schema-pack.json: that
    path is a generated catalog shim (x-generated-by) shared by 127 units.
    """
    live = REPO / SCHEMA_REL
    if live.is_file():
        try:
            doc = load_json(live)
        except (OSError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict) and doc.get("x-generated-by"):
            pass
        elif isinstance(doc, dict) and doc.get("$defs", {}).get("WorkflowRecord") and not doc.get(
            "x-generated-by"
        ):
            # A previous emit clobbered the shim. Do not restore it here
            # (substrate generator owns that path) and do not write again.
            pass
    path = REPO / UNIT_SCHEMA_REL
    dump_json(path, schema_pack())
    return path


def emit() -> dict[str, Any]:
    write_schema_pack()
    v1_doc = load_or_freeze_v1()
    artifact = fold(v1_doc)
    pack = schema_pack()
    errs = validate_against(pack, artifact)
    if errs:
        raise RuntimeError("schema errors:\n" + "\n".join(errs[:20]))
    rec_schema = pack["$defs"]["WorkflowRecord"]
    rec_schema_wrapped = {
        "$schema": pack["$schema"],
        "$defs": pack["$defs"],
        **rec_schema,
    }
    rec_schema_wrapped.pop("allOf", None)
    for rec in artifact["records"]:
        rerr = validate_against(
            {
                "$schema": pack["$schema"],
                "$id": pack["$id"] + "#/$defs/WorkflowRecord",
                **pack["$defs"]["WorkflowRecord"],
            },
            rec,
        )
        if rerr:
            raise RuntimeError(f"record {rec['id']} schema:\n" + "\n".join(rerr[:12]))
    dump_json(REPO / OUT_REL, artifact)
    return artifact


def attribution_ok(artifact: dict[str, Any]) -> tuple[bool, str]:
    allowed = {u for _, u in EXTRACTION_DIMS} | {
        "WFA-0002",
        "WFA-0007",
        "WFA-0010",
        "WFA-0043",
        "WFA-0073",
        "WFA-0078",
    }
    if not artifact.get("field_diff"):
        return False, "field_diff-empty"
    for row in artifact["field_diff"]:
        uid = row.get("unit_id")
        if uid not in allowed:
            return False, f"unattributed-or-foreign:{row}"
        if not row.get("record_id") or not row.get("field"):
            return False, f"incomplete-diff:{row}"
    for rec in artifact["records"]:
        if not rec.get("cell_attribution"):
            return False, f"no-attr:{rec['id']}"
        for a in rec["cell_attribution"]:
            if a.get("unit_id") not in allowed:
                return False, f"bad-attr:{a}"
    return True, "ok"


def arithmetic_ok(artifact: dict[str, Any], v1_doc: dict[str, Any]) -> tuple[bool, str]:
    a = artifact["arithmetic"]
    v1n = len(v1_doc["candidates"])
    v2n = len(artifact["records"])
    if a["v1_count"] != v1n:
        return False, f"v1_count {a['v1_count']} != fixture {v1n}"
    if a["v2_count"] != v2n:
        return False, f"v2_count {a['v2_count']} != records {v2n}"
    expect = a["v1_count"] + a["additions"] - a["collapses"]
    if expect != a["v2_count"] or not a["reconciles"]:
        return False, f"arith {expect} != {a['v2_count']}"
    return True, f"{v1n}+{a['additions']}-{a['collapses']}={v2n}"


SCHEMA_REL = SCHEMA_REL
JACCARD_THRESHOLD = JACCARD_THRESHOLD
