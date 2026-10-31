"""Shared V-FIELDS CI harness for IMP-0437 (and TST-0038 historical-disarm).

Writes an isolated catalog + matching graph + matching register digest so
validate.py can be invoked the same way CI invokes it, without REACH-6 / V-GRAPH
noise from the live tree. Mutations (drop defaults, drop one defaulted field)
are applied to the sandbox copy only.
"""

from __future__ import annotations

import copy
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalog as cat

REPO = cat.repo_root()
VALIDATE_REL = "tools/command-center/validate.py"
VALIDATE = REPO / VALIDATE_REL
WORKFLOW_REL = ".github/workflows/quality.yml"
REQUIRE_COMPLETE_FLAG = "--require-complete"
DISARM_FLAG = "--no-require-complete"
SINGLE_FIELD = "timeout_seconds"

# Keys validate.py actually reads. Dropping work_units keeps the sandbox small
# (the live catalog also carries ~2,007 work units that this gate does not scan).
_SANDBOX_KEYS = (
    "schema_version",
    "contract",
    "provenance",
    "terminal_dispositions",
    "defaults",
    "owner_questions",
    "items",
)


def workflow_path() -> Path:
    return REPO / WORKFLOW_REL


def workflow_arms_require_complete() -> bool:
    """True when a non-comment line invokes validate.py with --require-complete."""
    path = workflow_path()
    if not path.is_file():
        return False
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        if VALIDATE_REL in stripped and REQUIRE_COMPLETE_FLAG in stripped:
            return True
    return False


def real_catalog() -> dict[str, Any]:
    return cat.load()


def mini_catalog() -> dict[str, Any]:
    """One open item whose 11 operational fields resolve only from defaults."""
    defaults = {
        "assignment": {
            "model": "opus",
            "role": "implementer",
            "vendor": "anthropic",
        },
        "evidence_requirement": "two mechanically independent signals",
        "execution_substrate": "local",
        "failure_classification": ["green-not-live"],
        "output_schema": "command-center/schema/receipt.schema.json",
        "owner_approval_required": False,
        "retry_policy": "two strikes then pivot",
        "reviewer_requirement": "independent reviewer",
        "tests_required": ["both-states control"],
        "timeout_seconds": 1800,
        "tool_permissions": ["Read"],
    }
    item = {
        "id": "R-A01",
        "title": "mini field-completeness fixture",
        "phase": "0",
        "target": "arm V-FIELDS in CI",
        "inputs": ["fixture"],
        "dependencies": [],
        "completion_sentinel": "SUCCESS:R-A01",
        "output_path": "command-center/receipts/R-A01.json",
        "next_smallest_action": "run validate.py --require-complete",
        "status": "OPEN",
        "disposition": None,
        "program": "P2",
        "section": "OUTSTANDING",
    }
    return {
        "schema_version": cat.SCHEMA_VERSION,
        "defaults": defaults,
        "owner_questions": [],
        "items": [item],
    }


def _sandbox_doc(
    catalog: dict[str, Any],
    *,
    drop_defaults: bool = False,
    drop_default_field: str | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {}
    for key in _SANDBOX_KEYS:
        if key in catalog:
            doc[key] = copy.deepcopy(catalog[key])
    if "items" not in doc:
        doc["items"] = copy.deepcopy(cat.items(catalog))
    if drop_defaults:
        doc.pop("defaults", None)
    elif drop_default_field:
        defaults = doc.get("defaults")
        if not isinstance(defaults, dict) or drop_default_field not in defaults:
            raise KeyError(
                f"defaults.{drop_default_field} missing; cannot drop it"
            )
        defaults = dict(defaults)
        del defaults[drop_default_field]
        doc["defaults"] = defaults
    return doc


def write_sandbox(
    dest: Path,
    catalog: dict[str, Any],
    *,
    drop_defaults: bool = False,
    drop_default_field: str | None = None,
) -> Path:
    """Materialise catalog.json + graph.json + REGISTER.md under dest.

    Returns dest. run_validate() reads those three names.
    """
    dest.mkdir(parents=True, exist_ok=True)
    register = dest / "REGISTER.md"
    register.write_bytes(b"IMP-0437 isolated register\n")
    digest = hashlib.sha256(register.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    doc = _sandbox_doc(
        catalog, drop_defaults=drop_defaults, drop_default_field=drop_default_field
    )
    provenance = dict(doc.get("provenance") or {})
    provenance["register"] = "REGISTER.md"
    provenance["register_sha256"] = digest
    doc["provenance"] = provenance
    cat.save(doc, dest / "catalog.json")
    cat.save(cat.build_graph(doc), dest / "graph.json")
    return dest


def run_validate(sandbox: Path, flags: list[str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [
        sys.executable,
        "-B",
        str(VALIDATE),
        "--catalog",
        str(sandbox / "catalog.json"),
        "--graph",
        str(sandbox / "graph.json"),
        "--register",
        str(sandbox / "REGISTER.md"),
    ]
    if flags:
        cmd.extend(flags)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {
        "exit_code": proc.returncode,
        "output": text,
        "vfields": "V-FIELDS" in text,
        "command": cmd,
        "flags": list(flags or []),
    }
