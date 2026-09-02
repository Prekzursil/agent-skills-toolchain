#!/usr/bin/env python3
"""Validate and route ``.agents/routing-policy.json`` (task classes with PACE rungs).

The policy carries names only: every model or endpoint reference must resolve in
``.agents/models.json``. Each task class has a Primary / Alternate / Contingency /
Emergency plan whose rungs are distinguishable means; ``E`` is a handoff procedure
over ``basic-memory :8765`` and ``agent-mail :8812``, never a model. Rationale for
the committed policy lives in ``.provenance/.agents/routing-policy.json.md``.
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import json
import math
import pathlib
import re
import sys
from collections.abc import Mapping
from types import ModuleType
from typing import Any, TextIO


NAME = "routing-policy"
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_POLICY_PATH = SCRIPTS_DIR.parent / "routing-policy.json"
DEFAULT_REGISTRY_PATH = SCRIPTS_DIR.parent / "models.json"
SCHEMA_VERSION = 1
SUM_TOLERANCE = 1e-9

TOP_LEVEL_KEYS = frozenset({"schemaVersion", "classes", "review"})
CLASS_REQUIRED_KEYS = frozenset(
    {
        "primary",
        "escalate_to",
        "floors",
        "exponents",
        "spend_share",
        "pace",
        "justification",
    }
)
CLASS_KEYS = CLASS_REQUIRED_KEYS | {"pinned_until", "callers"}
EXPONENT_KEYS = frozenset({"quality", "speed", "cost"})
RUNGS = ("P", "A", "C", "E")
PACE_KEYS = frozenset(RUNGS) | {"triggers"}
REVIEW_KEYS = frozenset({"cadence", "last_review", "owner"})
REVIEW_CADENCES = frozenset({"weekly", "monthly", "quarterly"})
LATTICE_STATES = frozenset({"native", "probed", "declared", "emulated", "absent"})
CAPABILITY_KEYS = frozenset(
    {
        "wire.completions",
        "wire.responses",
        "wire.messages",
        "features.streaming",
        "features.usage",
        "features.tools",
        "features.tool_choice",
        "features.structured_output",
        "features.vision",
        "features.reasoning",
    }
)
TRIGGERS = frozenset(
    {
        "timeout",
        "BACKEND_AUTH",
        "BACKEND_RATE_LIMITED",
        "BACKEND_UNAVAILABLE",
        "BACKEND_ERROR",
        "MALFORMED_RESPONSE",
        "TIMEOUT_NO_OUTPUT",
        "TIMEOUT_PARTIAL",
        "BUDGET_EXCEEDED",
        "CONCURRENCY_SATURATED",
        "CREDENTIAL_MISSING",
        "ENDPOINT_DISABLED",
        "MODEL_DISABLED",
        "UNSUPPORTED_CAPABILITY",
        "HALTED",
    }
)
RUNTIMES = (
    "codex",
    "grok",
    "goose",
    "opencode",
    "aider",
    "fabric",
    "cursor",
    "claude",
    "agy",
    "gemini",
)
SIDECAR_CALLERS = frozenset({"codex", "cli"})
KNOWN_CALLERS = frozenset(RUNTIMES) | SIDECAR_CALLERS
PROCEDURE_PREFIXES = ("handoff:", "procedure:")
EMERGENCY_HANDOFF_TERMS = ("basic-memory :8765", "agent-mail :8812")
CLASS_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LITERAL_SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:hf_|sk-|gh[pousr]_|github_pat_|AKIA|xox[abp]-)[A-Za-z0-9_-]{8,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)

Resolved = tuple[str, Mapping[str, Any], str, Mapping[str, Any]]


class PolicyError(ValueError):
    """Raised when the routing policy violates the shared contract."""


def _models_module() -> ModuleType | None:
    scripts_dir = str(SCRIPTS_DIR)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        return importlib.import_module("models_control_plane")
    except ImportError:
        return None


def _read_json(path: pathlib.Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PolicyError(f"missing {path}") from None
    except OSError as error:
        raise PolicyError(f"unreadable {path}: {error}") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise PolicyError(
            f"invalid JSON in {path}: {error.msg} at line {error.lineno}"
        ) from None


def _check_registry_shape(registry: object, label: str) -> Mapping[str, Any]:
    if (
        not isinstance(registry, Mapping)
        or not isinstance(registry.get("endpoints"), Mapping)
        or not isinstance(registry.get("models"), Mapping)
    ):
        raise PolicyError(f"{label} must contain endpoints and models objects")
    return registry


def load_registry(path: pathlib.Path | str = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    """Load the models registry through the sibling validator module when present."""
    registry_path = pathlib.Path(path)
    module = _models_module()
    if module is None:
        registry = _read_json(registry_path)
    else:
        try:
            registry = module.load_registry(registry_path)
        except (OSError, ValueError) as error:
            raise PolicyError(f"registry {registry_path}: {error}") from None
    return dict(_check_registry_shape(registry, f"registry {registry_path}"))


def load_policy(path: pathlib.Path | str = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    """Read the policy file; missing, unreadable or non-object files are errors."""
    policy_path = pathlib.Path(path)
    policy = _read_json(policy_path)
    if not isinstance(policy, Mapping):
        raise PolicyError(f"{policy_path} must contain a JSON object")
    return dict(policy)


def is_procedure(ref: object) -> bool:
    """A rung that is a procedure step (``handoff:`` / ``procedure:``), not a model."""
    return isinstance(ref, str) and ref.startswith(PROCEDURE_PREFIXES)


def resolve_ref(registry: Mapping[str, Any], ref: str) -> Resolved:
    """Resolve ``<model-id>``, ``<model-id>@<endpoint-id>`` or an alias (V-P2)."""
    aliases = registry.get("aliases")
    if not isinstance(aliases, Mapping):
        aliases = {}
    name, _, pinned = ref.partition("@")
    model_id = str(aliases.get(name, name))
    model = registry["models"].get(model_id)
    if not isinstance(model, Mapping):
        raise PolicyError(f"V-P2 unknown model reference {ref!r}")
    endpoint_id = str(model.get("endpoint"))
    endpoint = registry["endpoints"].get(endpoint_id)
    if not isinstance(endpoint, Mapping):
        raise PolicyError(
            f"V-P2 model {model_id!r} names a missing endpoint {endpoint_id!r}"
        )
    if pinned and pinned != endpoint_id:
        raise PolicyError(
            f"V-P2 {ref!r}: model {model_id!r} lives on endpoint {endpoint_id!r}"
        )
    return model_id, model, endpoint_id, endpoint


def _resolve(where: str, registry: Mapping[str, Any], ref: str) -> Resolved:
    try:
        return resolve_ref(registry, ref)
    except PolicyError as error:
        raise PolicyError(f"{where}: {error}") from None


def _object(
    where: str, value: object, allowed: frozenset[str], required: frozenset[str]
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PolicyError(f"V-P1 {where}: must be an object")
    keys = {str(key) for key in value}
    unknown = sorted(keys - allowed)
    if unknown:
        raise PolicyError(f"V-P1 {where}: unknown key {unknown[0]!r}")
    missing = sorted(required - keys)
    if missing:
        raise PolicyError(f"V-P1 {where}: missing key {missing[0]!r}")
    return value


def _text(where: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"V-P1 {where}: must be a nonempty string")
    return value


def _names(
    where: str,
    value: object,
    vocabulary: frozenset[str] | None,
    *,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise PolicyError(f"V-P1 {where}: must be a nonempty string list")
    names = [_text(f"{where}[{index}]", item) for index, item in enumerate(value)]
    if len(set(names)) != len(names):
        raise PolicyError(f"V-P1 {where}: repeats an entry")
    if vocabulary is not None:
        unknown = sorted(set(names) - vocabulary)
        if unknown:
            raise PolicyError(f"V-P1 {where}: unknown entry {unknown[0]!r}")
    return names


def _fraction(where: str, rule: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 <= value <= 1.0
    ):
        raise PolicyError(f"{rule} {where}: must be a number between 0 and 1")
    return float(value)


def _iso_date(where: str, value: object) -> None:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        raise PolicyError(f"V-P12 {where}: must be an ISO date (YYYY-MM-DD)")
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise PolicyError(f"V-P12 {where}: {value!r} is not a calendar date") from None


def _reject_names_only(value: object, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_names_only(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_names_only(child, f"{path}[{index}]")
    elif isinstance(value, str) and ("://" in value or LITERAL_SECRET_RE.search(value)):
        raise PolicyError(f"L6 {path}: names only; URL or credential-shaped text found")


def _validate_exponents(where: str, value: object) -> None:
    exponents = _object(where, value, EXPONENT_KEYS, EXPONENT_KEYS)
    total = sum(
        _fraction(f"{where}.{key}", "V-P3", exponents[key])
        for key in sorted(EXPONENT_KEYS)
    )
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=SUM_TOLERANCE):
        raise PolicyError(
            f"V-P3 {where}: quality + speed + cost must be 1.0, got {total:.6f}"
        )


def _validate_floors(where: str, value: object) -> None:
    if not isinstance(value, Mapping):
        raise PolicyError(f"V-P11 {where}: must be an object")
    for raw_key, state in value.items():
        key = str(raw_key)
        if key not in CAPABILITY_KEYS:
            raise PolicyError(f"V-P11 {where}.{key}: unknown capability")
        if not isinstance(state, str) or state not in LATTICE_STATES:
            raise PolicyError(f"V-P11 {where}.{key}: {state!r} is not a lattice state")


def _callers(where: str, value: object) -> frozenset[str] | None:
    if value is None:
        return None
    return frozenset(
        _names(f"{where}.callers", value, KNOWN_CALLERS, allow_empty=False)
    )


def _status(model: Mapping[str, Any], endpoint: Mapping[str, Any]) -> str:
    if model.get("enabled") is not True or endpoint.get("enabled") is not True:
        return "disabled"
    return str(model.get("status"))


def _is_sidecar(endpoint_id: str, endpoint: Mapping[str, Any]) -> bool:
    return endpoint_id == "openrouter" or endpoint.get("sidecarOnly") is True


def _rung_records(
    where: str, pace: Mapping[str, Any], registry: Mapping[str, Any]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for rung in RUNGS:
        ref = _text(f"{where}.{rung}", pace.get(rung))
        if is_procedure(ref):
            if rung == "P":
                raise PolicyError(
                    f"V-P14 {where}.P: the primary rung must be a model, not a procedure"
                )
            records.append(
                {"rung": rung, "ref": ref, "kind": "procedure", "status": "procedure"}
            )
            continue
        if rung == "E":
            raise PolicyError(
                f"V-P7 {where}.E: must be a handoff procedure, not a model"
            )
        model_id, model, endpoint_id, endpoint = _resolve(
            f"{where}.{rung}", registry, ref
        )
        records.append(
            {
                "rung": rung,
                "ref": ref,
                "kind": "model",
                "model_id": model_id,
                "endpoint": endpoint_id,
                "status": _status(model, endpoint),
            }
        )
    return records


def _check_pace(
    where: str,
    records: list[dict[str, Any]],
    registry: Mapping[str, Any],
    primary_id: str,
) -> None:
    endpoints = registry["endpoints"]
    models = [record for record in records if record["kind"] == "model"]
    if records[0]["model_id"] != primary_id:
        raise PolicyError(
            f"V-P14 {where}.P: {records[0]['ref']!r} must name the primary model "
            f"{primary_id!r}"
        )
    cursor = [r["rung"] for r in models if str(r["endpoint"]).startswith("cursor-")]
    if len(cursor) > 1:
        raise PolicyError(
            f"V-P5 {where}: rungs {'/'.join(cursor)} share the cursor-* bridge; "
            "at most one may (L3)"
        )
    if not any(
        r["kind"] == "procedure" or endpoints[r["endpoint"]].get("kind") == "local"
        for r in records[:-1]
    ):
        raise PolicyError(
            f"V-P6 {where}: P/A/C need one rung on a local endpoint or a procedure step"
        )
    emergency = records[-1]["ref"]
    missing = [term for term in EMERGENCY_HANDOFF_TERMS if term not in emergency]
    if missing:
        raise PolicyError(f"V-P7 {where}.E: the handoff must name {missing[0]!r}")
    seen: dict[str, str] = {}
    for record in models:
        endpoint_id = str(record["endpoint"])
        if endpoint_id in seen:
            raise PolicyError(
                f"V-P8 {where}: rungs {seen[endpoint_id]} and {record['rung']} share "
                f"endpoint {endpoint_id!r}"
            )
        seen[endpoint_id] = str(record["rung"])


def _validate_class(
    name: str, spec: object, registry: Mapping[str, Any], warnings: list[str]
) -> float:
    where = f"classes.{name}"
    fields = _object(where, spec, CLASS_KEYS, CLASS_REQUIRED_KEYS)
    primary_ref = _text(f"{where}.primary", fields["primary"])
    escalation_refs = _names(
        f"{where}.escalate_to", fields["escalate_to"], None, allow_empty=True
    )
    if primary_ref in escalation_refs:
        raise PolicyError(f"V-P1 {where}.escalate_to: repeats the primary")
    _text(f"{where}.justification", fields["justification"])
    callers = _callers(where, fields.get("callers"))
    _validate_exponents(f"{where}.exponents", fields["exponents"])
    share = _fraction(f"{where}.spend_share", "V-P4", fields["spend_share"])
    _validate_floors(f"{where}.floors", fields["floors"])
    if "pinned_until" in fields:
        _iso_date(f"{where}.pinned_until", fields["pinned_until"])
    pace = _object(f"{where}.pace", fields["pace"], PACE_KEYS, PACE_KEYS)
    _names(f"{where}.pace.triggers", pace["triggers"], TRIGGERS, allow_empty=False)

    primary = _resolve(f"{where}.primary", registry, primary_ref)
    escalations = [
        _resolve(f"{where}.escalate_to", registry, ref) for ref in escalation_refs
    ]
    records = _rung_records(f"{where}.pace", pace, registry)

    primary_status = _status(primary[1], primary[3])
    if primary_status != "live":
        raise PolicyError(
            f"V-P13 {where}.primary: {primary_ref!r} is {primary_status}; "
            "the primary must be enabled and live"
        )
    for ref, resolved in zip(escalation_refs, escalations):
        status = _status(resolved[1], resolved[3])
        if status != "live":
            warnings.append(f"V-P13 {where}.escalate_to: {ref!r} is {status}")
    for record in records:
        if record["kind"] == "model" and record["status"] != "live":
            warnings.append(
                f"V-P13 {where}.pace.{record['rung']}: {record['ref']!r} is "
                f"{record['status']}"
            )

    endpoints = registry["endpoints"]
    sidecar = [
        ref
        for ref, (_, _, endpoint_id, endpoint) in [
            (primary_ref, primary),
            *zip(escalation_refs, escalations),
        ]
        if _is_sidecar(endpoint_id, endpoint)
    ]
    sidecar += [
        record["ref"]
        for record in records
        if record["kind"] == "model"
        and _is_sidecar(record["endpoint"], endpoints[record["endpoint"]])
    ]
    if sidecar and (callers is None or not callers <= SIDECAR_CALLERS):
        raise PolicyError(
            f"V-P9 {where}: OpenRouter reference {sidecar[0]!r} needs callers within "
            "codex/cli (L1)"
        )

    retires = primary[3].get("retiresWhen")
    if retires and not any(not e[3].get("retiresWhen") for e in escalations):
        raise PolicyError(
            f"V-P10 {where}: primary endpoint {primary[2]!r} retires ({retires}); "
            "add an escalation on an endpoint without retiresWhen (L3)"
        )

    _check_pace(f"{where}.pace", records, registry, primary[0])
    return share


def validate_policy(
    policy: Mapping[str, Any], registry: Mapping[str, Any]
) -> list[str]:
    """Return warnings; raise ``PolicyError`` on the first error."""
    _check_registry_shape(registry, "registry")
    warnings: list[str] = []
    top = _object("policy", policy, TOP_LEVEL_KEYS, TOP_LEVEL_KEYS)
    if top["schemaVersion"] != SCHEMA_VERSION:
        raise PolicyError(f"V-P1 policy.schemaVersion: must be {SCHEMA_VERSION}")
    _reject_names_only(top, "policy")
    classes = top["classes"]
    if not isinstance(classes, Mapping) or not classes:
        raise PolicyError("V-P1 policy.classes: must be a nonempty object")
    total = 0.0
    for raw_name, spec in classes.items():
        name = str(raw_name)
        if not CLASS_NAME_RE.fullmatch(name):
            raise PolicyError(
                f"V-P1 classes.{name}: class names are lower-case hyphen-case"
            )
        total += _validate_class(name, spec, registry, warnings)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=SUM_TOLERANCE):
        raise PolicyError(
            f"V-P4 policy.classes: spend_share must sum to 1.0, got {total:.6f}"
        )
    review = _object("review", top["review"], REVIEW_KEYS, REVIEW_KEYS)
    if _text("review.cadence", review["cadence"]) not in REVIEW_CADENCES:
        raise PolicyError(
            f"V-P1 review.cadence: must be one of {sorted(REVIEW_CADENCES)}"
        )
    _iso_date("review.last_review", review["last_review"])
    _text("review.owner", review["owner"])
    return warnings


def route(
    policy: Mapping[str, Any], registry: Mapping[str, Any], task_class: str
) -> list[dict[str, Any]]:
    """Return the ordered P/A/C/E rungs of ``task_class`` with each rung's status."""
    _check_registry_shape(registry, "registry")
    classes = policy.get("classes")
    spec = classes.get(task_class) if isinstance(classes, Mapping) else None
    if not isinstance(spec, Mapping):
        raise PolicyError(f"unknown task class {task_class!r}")
    pace = spec.get("pace")
    if not isinstance(pace, Mapping):
        raise PolicyError(f"classes.{task_class}.pace: must be an object")
    return _rung_records(f"classes.{task_class}.pace", pace, registry)


def load_policy_or_fallback(
    path: pathlib.Path | str,
    registry: Mapping[str, Any],
    *,
    stderr: TextIO | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Load and validate the policy; on any failure print one loud line and fall back."""
    stream = sys.stderr if stderr is None else stderr
    try:
        policy = load_policy(path)
        validate_policy(policy, registry)
    except PolicyError as error:
        print(f"FAILED:{NAME} {error}; falling back to registry slots", file=stream)
        return None, "fallback"
    return policy, "policy"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="routing_policy", description=__doc__)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument("--class", dest="task_class", default=None)
    args = parser.parse_args(argv)
    try:
        registry = load_registry(args.registry)
        policy = load_policy(args.policy)
        warnings = validate_policy(policy, registry)
        names = [args.task_class] if args.task_class else list(policy["classes"])
        routes = {name: route(policy, registry, name) for name in names}
    except PolicyError as error:
        print(f"FAILED:{NAME} {error}")
        return 2
    if args.as_json:
        payload = {
            "policy": str(args.policy),
            "registry": str(args.registry),
            "classes": list(policy["classes"]),
            "warnings": warnings,
            "routes": routes,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    summary = (
        f"SUCCESS:{NAME} classes={len(policy['classes'])} warnings={len(warnings)}"
    )
    if args.task_class:
        summary += f" class={args.task_class} rungs={len(routes[args.task_class])}"
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
