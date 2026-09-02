"""Local six-element blueprint contract (IMP-0230 catalog text).

IMP-0230 is not delivered on this tree. This module implements the six
elements the catalog names so IMP-0236 does not ship nameless JSON. It does
not claim to be the estate-wide scaffold generator.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

REQUIRED_ELEMENTS: tuple[str, ...] = (
    "typed_workflow",
    "runnable_example",
    "preset",
    "stopping_rules",
    "smoke_test",
    "capability_vector",
)

STAGE_REQUIRED = ("id", "kind")


class ContractError(ValueError):
    """A blueprint omitted a required element or a required sub-field."""


def _as_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def _as_sequence(value: Any, name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ContractError(f"{name} must be an array")
    return value


def omission_failures(blueprint: Mapping[str, Any]) -> list[str]:
    """Return one distinct failure token per missing required element.

    Used as the local analogue of IMP-0230's 'six one-at-a-time omissions
    produce six distinct rejections' gate.
    """
    failures: list[str] = []
    for element in REQUIRED_ELEMENTS:
        if element not in blueprint or blueprint[element] in (None, "", {}, []):
            failures.append(f"missing:{element}")
    return failures


def validate_blueprint(blueprint: Mapping[str, Any]) -> None:
    missing = omission_failures(blueprint)
    if missing:
        raise ContractError("; ".join(missing))

    wf = _as_mapping(blueprint["typed_workflow"], "typed_workflow")
    stages = _as_sequence(wf.get("stages"), "typed_workflow.stages")
    if not stages:
        raise ContractError("typed_workflow.stages must be non-empty")
    for i, stage in enumerate(stages):
        st = _as_mapping(stage, f"typed_workflow.stages[{i}]")
        for key in STAGE_REQUIRED:
            if not st.get(key):
                raise ContractError(f"typed_workflow.stages[{i}].{key} required")

    example = _as_mapping(blueprint["runnable_example"], "runnable_example")
    if not example.get("fixture") and not example.get("sources"):
        raise ContractError("runnable_example needs fixture or sources")

    preset = _as_mapping(blueprint["preset"], "preset")
    if not preset.get("id"):
        raise ContractError("preset.id required")

    stopping = _as_mapping(blueprint["stopping_rules"], "stopping_rules")
    if "max_claims" not in stopping and "halt_on" not in stopping:
        raise ContractError("stopping_rules needs max_claims or halt_on")

    smoke = _as_mapping(blueprint["smoke_test"], "smoke_test")
    if not smoke.get("id"):
        raise ContractError("smoke_test.id required")

    vector = _as_mapping(blueprint["capability_vector"], "capability_vector")
    if not vector:
        raise ContractError("capability_vector must be non-empty")


def fingerprint(blueprint: Mapping[str, Any]) -> str:
    """Structural fingerprint: stage kinds + source classes + evidence classes.

    Distinct blueprints must not share this fingerprint (IMP-0232 concern,
    computed locally so the four IMP-0236 entries are not one blueprint
    wearing four names).
    """
    wf = blueprint.get("typed_workflow") or {}
    stages = tuple(
        str(s.get("kind") or "")
        for s in (wf.get("stages") or [])
        if isinstance(s, Mapping)
    )
    sources = tuple(sorted(str(x) for x in (blueprint.get("source_classes") or [])))
    evidence = tuple(
        sorted(str(x) for x in (blueprint.get("evidence_classes") or []))
    )
    caps = tuple(
        sorted(
            f"{k}={v}"
            for k, v in (blueprint.get("capability_vector") or {}).items()
        )
    )
    return "|".join(
        [
            str(blueprint.get("id") or ""),
            ",".join(stages),
            ",".join(sources),
            ",".join(evidence),
            ",".join(caps),
        ]
    )


def distinctness(blueprints: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    fps: dict[str, str] = {}
    collisions: list[list[str]] = []
    seen: dict[str, str] = {}
    for bp in blueprints:
        bid = str(bp.get("id") or "")
        fp = fingerprint(bp)
        fps[bid] = fp
        # Compare without the id prefix so two renamed copies collide.
        structural = fp.split("|", 1)[1] if "|" in fp else fp
        if structural in seen:
            collisions.append([seen[structural], bid])
        else:
            seen[structural] = bid
    return {
        "fingerprints": fps,
        "collisions": collisions,
        "distinct": not collisions,
        "count": len(fps),
    }
