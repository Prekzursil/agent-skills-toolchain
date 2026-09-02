"""IMP-0230-style authoring gate for the four IMP-0240 blueprints.

A blueprint that omits any required element cannot be registered. Each
omission produces a distinct rejection code so a missing smoke test cannot
be reported as a missing preset.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BLUEPRINTS = HERE / "blueprints"
PRESETS = HERE / "presets"
EXAMPLES = HERE / "examples"
TAXONOMY = HERE / "taxonomy.json"

REQUIRED_ELEMENTS = (
    "typed_workflow",
    "runnable_example",
    "preset",
    "stopping_rules",
    "smoke_test",
    "capability_vector",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_taxonomy() -> dict[str, Any]:
    doc = _load(TAXONOMY)
    if not isinstance(doc.get("version"), str) or not doc.get("axes"):
        raise ValueError("taxonomy missing version or axes")
    return doc


def _reject(code: str, detail: str) -> dict[str, Any]:
    return {"accepted": False, "code": code, "detail": detail}


def validate_blueprint(doc: dict[str, Any], *, taxonomy: dict[str, Any] | None = None) -> dict[str, Any]:
    tax = taxonomy or load_taxonomy()
    if doc.get("kind") != "workflow_blueprint":
        return _reject("typed_workflow", "kind must be workflow_blueprint")
    if not isinstance(doc.get("id"), str) or not doc["id"].startswith("wf."):
        return _reject("typed_workflow", "id must be a wf.* string")
    stages = doc.get("stages")
    if not isinstance(stages, list) or len(stages) < 1:
        return _reject("typed_workflow", "stages must be a non-empty list")
    for stage in stages:
        if not isinstance(stage, dict) or not stage.get("id") or not stage.get("kind"):
            return _reject("typed_workflow", "each stage needs id and kind")

    example_id = doc.get("example_id")
    example_path = EXAMPLES / f"{example_id}.json" if isinstance(example_id, str) else None
    if not example_path or not example_path.is_file():
        return _reject("runnable_example", f"example_id missing on disk: {example_id}")
    example = _load(example_path)
    if example.get("runnable") is not True:
        return _reject("runnable_example", "example.runnable must be true")

    preset_id = doc.get("preset_id")
    preset_path = PRESETS / f"{preset_id}.json" if isinstance(preset_id, str) else None
    if not preset_path or not preset_path.is_file():
        return _reject("preset", f"preset_id missing on disk: {preset_id}")

    stopping = doc.get("stopping")
    if not isinstance(stopping, dict):
        return _reject("stopping_rules", "stopping object required")
    if "max_stages" not in stopping or "on_error" not in stopping:
        return _reject("stopping_rules", "stopping needs max_stages and on_error")
    if stopping.get("on_error") not in {"halt", "record-and-halt"}:
        return _reject("stopping_rules", "on_error must halt (no silent continue)")

    smoke = doc.get("smoke_test")
    if not isinstance(smoke, dict) or not smoke.get("id") or not smoke.get("entry"):
        return _reject("smoke_test", "smoke_test.id and smoke_test.entry required")

    vector = doc.get("capability_vector")
    if not isinstance(vector, dict):
        return _reject("capability_vector", "capability_vector object required")
    if vector.get("taxonomy_id") != tax["id"]:
        return _reject("capability_vector", "taxonomy_id does not match declared taxonomy")
    if vector.get("taxonomy_version") != tax["version"]:
        return _reject("capability_vector", "taxonomy_version mismatch (unversioned edit)")
    axes = vector.get("axes")
    if not isinstance(axes, dict) or not axes:
        return _reject("capability_vector", "axes map required")
    unknown = set(axes) - set(tax["axes"])
    if unknown:
        return _reject("capability_vector", f"undeclared axes {sorted(unknown)}")
    return {
        "accepted": True,
        "code": "ok",
        "id": doc["id"],
        "elements": list(REQUIRED_ELEMENTS),
    }


def register_all() -> dict[str, Any]:
    tax = load_taxonomy()
    accepted: list[str] = []
    rejected: list[dict[str, Any]] = []
    for path in sorted(BLUEPRINTS.glob("wf.*.json")):
        doc = _load(path)
        result = validate_blueprint(doc, taxonomy=tax)
        if result["accepted"]:
            accepted.append(doc["id"])
        else:
            rejected.append({"path": path.name, **result})
    return {
        "taxonomy_version": tax["version"],
        "accepted": accepted,
        "rejected": rejected,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
    }


def omission_control(doc: dict[str, Any], drop: str) -> dict[str, Any]:
    """One-at-a-time omission must produce the matching distinct code."""
    mutant = json.loads(json.dumps(doc))
    if drop == "typed_workflow":
        mutant["kind"] = "notes"
    elif drop == "runnable_example":
        mutant["example_id"] = "does-not-exist"
    elif drop == "preset":
        mutant["preset_id"] = "does-not-exist"
    elif drop == "stopping_rules":
        mutant.pop("stopping", None)
    elif drop == "smoke_test":
        mutant.pop("smoke_test", None)
    elif drop == "capability_vector":
        mutant.pop("capability_vector", None)
    else:
        raise ValueError(drop)
    result = validate_blueprint(mutant)
    return {"dropped": drop, "code": result.get("code"), "accepted": result["accepted"]}
