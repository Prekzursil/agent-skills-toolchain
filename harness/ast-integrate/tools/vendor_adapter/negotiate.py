"""Cross-vendor capability negotiation (IMP-0419).

Each vendor adapter publishes a TYPED descriptor; capability atoms are
flattened from those typed fields, the side-by-side matrix and the negotiated
common subset are COMPUTED set operations, and a unit whose requirements are
not all available is REFUSED with the missing atoms named and granted EMPTY —
never silently downgraded.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

HERE = Path(__file__).resolve().parent
DESCRIPTOR_DIR = HERE / "descriptors"

CONTEXT_THRESHOLDS = (128000, 200000, 272000, 1000000)
VERDICT_NEGOTIATED = "NEGOTIATED"
VERDICT_REFUSED = "REFUSED"


def load_published_descriptors(directory: Path | str | None = None) -> dict[str, dict[str, Any]]:
    root = Path(directory) if directory is not None else DESCRIPTOR_DIR
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        out[str(doc.get("vendor") or path.stem)] = doc
    return out


def atoms_from_descriptor(doc: Mapping[str, Any]) -> set[str]:
    """Flatten one typed descriptor into capability atoms."""
    atoms: set[str] = set()
    for tool in doc.get("tools") or []:
        atoms.add(f"tool:{tool}")
    perm = doc.get("permission_model") or {}
    if perm.get("kind"):
        atoms.add(f"permission_model:{perm['kind']}")
    if perm.get("fail_closed") is True:
        atoms.add("permission:fail_closed")
    if perm.get("output_last_message_file") is True:
        atoms.add("permission:output_last_message_file")
    stream = doc.get("streaming") or {}
    if stream.get("token_stream") is True:
        atoms.add("streaming:token_stream")
    if stream.get("blocking_foreground") is True:
        atoms.add("streaming:blocking_foreground")
    schema = doc.get("schema_support") or {}
    if schema.get("json_schema") is True:
        atoms.add("schema:json_schema")
    if schema.get("typed_work_result") is True:
        atoms.add("schema:typed_work_result")
    if schema.get("structured_outputs") is True:
        atoms.add("schema:structured_outputs")
    prompt = doc.get("prompt_transport") or {}
    if prompt.get("inline_allowed") is True:
        atoms.add("prompt:inline_allowed")
    if prompt.get("file_required") is True:
        atoms.add("prompt:file_required")
    tokens = int(doc.get("context_window_tokens") or 0)
    for threshold in CONTEXT_THRESHOLDS:
        if tokens >= threshold:
            atoms.add(f"context_window>={threshold}")
    return atoms


def union_atoms(descriptors: Mapping[str, Mapping[str, Any]]) -> set[str]:
    out: set[str] = set()
    for doc in descriptors.values():
        out |= atoms_from_descriptor(doc)
    return out


def common_subset(descriptors: Mapping[str, Mapping[str, Any]]) -> set[str]:
    groups = [atoms_from_descriptor(doc) for doc in descriptors.values()]
    if not groups:
        return set()
    return set.intersection(*groups)


def capability_matrix(descriptors: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    per = {vendor: atoms_from_descriptor(doc) for vendor, doc in descriptors.items()}
    vendors = sorted(per)
    union: set[str] = set()
    for group in per.values():
        union |= group
    rows: list[dict[str, Any]] = []
    for cap in sorted(union):
        holders = [v for v in vendors if cap in per[v]]
        if len(holders) == len(vendors):
            marker = "SHARED"
            exclusive_to = None
        else:
            marker = "VENDOR-ONLY"
            exclusive_to = holders[0] if len(holders) == 1 else None
        rows.append(
            {
                "capability": cap,
                "marker": marker,
                "exclusive_to": exclusive_to,
                "vendors": {v: (cap in per[v]) for v in vendors},
            }
        )
    return rows


def intersection_cost(descriptors: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    per = {vendor: atoms_from_descriptor(doc) for vendor, doc in descriptors.items()}
    inter = common_subset(descriptors)
    union = union_atoms(descriptors)
    others: dict[str, set[str]] = {}
    for vendor, group in per.items():
        rest: set[str] = set()
        for other, ogroup in per.items():
            if other != vendor:
                rest |= ogroup
        others[vendor] = group - rest
    return {
        "context_window_tokens": min(
            int(doc.get("context_window_tokens") or 0) for doc in descriptors.values()
        ),
        "intersection_size": len(inter),
        "union_size": len(union),
        "vendor_only_size": len(union) - len(inter),
        "exclusive": {v: sorted(a) for v, a in sorted(others.items())},
        "derivation": "set-intersection+min-context",
    }


def unit_required_atoms(unit: Mapping[str, Any]) -> set[str]:
    atoms: set[str] = set()
    for tool in unit.get("tool_permissions") or unit.get("required_tools") or []:
        atoms.add(f"tool:{tool}")
    for cap in unit.get("required_capabilities") or []:
        atoms.add(str(cap))
    if unit.get("require_prompt_file") is True:
        atoms.add("prompt:file_required")
    if unit.get("require_streaming") is True:
        atoms.add("streaming:token_stream")
    tokens = unit.get("min_context_window_tokens")
    if tokens:
        atoms.add(f"context_window>={int(tokens)}")
    return atoms


@dataclass
class NegotiationResult:
    verdict: str
    vendor: str | None
    required: list[str] = field(default_factory=list)
    granted: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "vendor": self.vendor,
            "required": list(self.required),
            "granted": list(self.granted),
            "missing": list(self.missing),
            "reason": self.reason,
        }


def _negotiate(required: set[str], available: set[str], vendor: str | None) -> NegotiationResult:
    missing = sorted(required - available)
    if missing:
        # REFUSED grants NOTHING: a partial grant is the silent downgrade.
        return NegotiationResult(
            verdict=VERDICT_REFUSED,
            vendor=vendor,
            required=sorted(required),
            granted=[],
            missing=missing,
            reason="missing capability atoms: " + ", ".join(missing),
        )
    return NegotiationResult(
        verdict=VERDICT_NEGOTIATED,
        vendor=vendor,
        required=sorted(required),
        granted=sorted(required),
        missing=[],
        reason="all required atoms available",
    )


def negotiate_for_vendor(
    unit: Mapping[str, Any], vendor: str, descriptors: Mapping[str, Mapping[str, Any]]
) -> NegotiationResult:
    return _negotiate(
        unit_required_atoms(unit), atoms_from_descriptor(descriptors[vendor]), vendor
    )


def negotiate_cross_vendor(
    unit: Mapping[str, Any], descriptors: Mapping[str, Mapping[str, Any]]
) -> NegotiationResult:
    return _negotiate(unit_required_atoms(unit), common_subset(descriptors), None)


def is_silent_downgrade(result: Any) -> bool:
    """NEGOTIATED while requirements went missing (or under-granted) — banned."""
    if isinstance(result, Mapping):
        verdict = result.get("verdict")
        missing: Iterable[str] = result.get("missing") or []
        required = set(result.get("required") or [])
        granted = set(result.get("granted") or [])
    else:
        verdict = result.verdict
        missing = result.missing or []
        required = set(result.required or [])
        granted = set(result.granted or [])
    if verdict != VERDICT_NEGOTIATED:
        return False
    return bool(list(missing)) or granted != required


__all__ = [
    "CONTEXT_THRESHOLDS",
    "NegotiationResult",
    "VERDICT_NEGOTIATED",
    "VERDICT_REFUSED",
    "atoms_from_descriptor",
    "capability_matrix",
    "common_subset",
    "intersection_cost",
    "is_silent_downgrade",
    "load_published_descriptors",
    "negotiate_cross_vendor",
    "negotiate_for_vendor",
    "union_atoms",
    "unit_required_atoms",
]
