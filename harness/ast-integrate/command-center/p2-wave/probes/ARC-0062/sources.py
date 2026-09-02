"""Source entry paths for A3, A4, A6, A7 (and live A1/A2/A5 interfaces).

A3/A4/A6/A7 DESIGN.json files are absent on this tree. Paths are bound to
catalog questions (substring must occur) so a catalog rewrite that drops
the named surface fails this module rather than silently shrinking the set.

If a source DESIGN.json later carries entry_paths, those ids win and must
still cover the catalog-bound id set (a DESIGN that omits a bound id is a gap).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

EPOCHS = (
    "install-time",
    "activation-time",
    "dispatch-time",
    "workflow-invocation-time",
)

# Catalog-bound source-dossier paths (reconciliation minuend).
SOURCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "A3.install.package-content",
        "source_architecture": "A3",
        "source_unit": "ARC-0020",
        "epoch": "install-time",
        "arrival": "marketplace",
        "effect": "execute_package_bytes",
        "plane_checks": ["marketplace_signature_verify", "lockfile_pin_check"],
        "must_contain": ["package content", "install path skips"],
    },
    {
        "id": "A3.install.update-pinned",
        "source_architecture": "A3",
        "source_unit": "ARC-0017",
        "epoch": "install-time",
        "arrival": "marketplace",
        "effect": "replace_installed_package",
        "plane_checks": ["marketplace_signature_verify", "lockfile_pin_check"],
        "must_contain": ["install/update/rollback"],
    },
    {
        "id": "A3.install.rollback",
        "source_architecture": "A3",
        "source_unit": "ARC-0017",
        "epoch": "install-time",
        "arrival": "marketplace",
        "effect": "restore_pinned_package",
        "plane_checks": ["marketplace_signature_verify", "lockfile_pin_check"],
        "must_contain": ["install/update/rollback"],
    },
    {
        "id": "A3.dispatch.installed-package",
        "source_architecture": "A3",
        "source_unit": "ARC-0020",
        "epoch": "dispatch-time",
        "arrival": "marketplace",
        "effect": "run_installed_package",
        "plane_checks": ["marketplace_signature_verify"],
        "must_contain": ["executing ANY package content"],
    },
    {
        "id": "A4.activate.materialize",
        "source_architecture": "A4",
        "source_unit": "ARC-0024",
        "epoch": "activation-time",
        "arrival": "gateway",
        "effect": "materialize_capability",
        "plane_checks": ["gateway_index_lookup", "gateway_budget_check"],
        "must_contain": ["materializes"],
    },
    {
        "id": "A4.activate.after-declared-permission-edit",
        "source_architecture": "A4",
        "source_unit": "ARC-0027",
        "epoch": "activation-time",
        "arrival": "gateway",
        "effect": "materialize_capability",
        "plane_checks": ["gateway_index_lookup", "declared_permission_edit"],
        "must_contain": ["INDEX time, SELECTION time or ACTIVATION time"],
    },
    {
        "id": "A4.dispatch.activated-capability",
        "source_architecture": "A4",
        "source_unit": "ARC-0027",
        "epoch": "dispatch-time",
        "arrival": "gateway",
        "effect": "invoke_activated_capability",
        "plane_checks": ["gateway_index_lookup"],
        "must_contain": ["activation path"],
    },
    {
        "id": "A6.install.vendor-tool-register",
        "source_architecture": "A6",
        "source_unit": "ARC-0038",
        "epoch": "install-time",
        "arrival": "adapter",
        "effect": "register_vendor_tool",
        "plane_checks": ["adapter_never_forward", "adapter_sanitize"],
        "must_contain": ["per-vendor adapters"],
    },
    {
        "id": "A6.dispatch.cross-vendor-unit",
        "source_architecture": "A6",
        "source_unit": "ARC-0041",
        "epoch": "dispatch-time",
        "arrival": "adapter",
        "effect": "dispatch_cross_vendor_unit",
        "plane_checks": ["adapter_sanitize", "adapter_never_forward"],
        "must_contain": ["second vendor's output is untrusted DATA"],
    },
    {
        "id": "A6.dispatch.adapter-forward",
        "source_architecture": "A6",
        "source_unit": "ARC-0041",
        "epoch": "dispatch-time",
        "arrival": "adapter",
        "effect": "forward_adapter_fields",
        "plane_checks": ["adapter_never_forward"],
        "must_contain": ["NEVER forward"],
    },
    {
        "id": "A6.dispatch.quarantine-then-read",
        "source_architecture": "A6",
        "source_unit": "ARC-0041",
        "epoch": "dispatch-time",
        "arrival": "adapter",
        "effect": "read_quarantined_artifact",
        "plane_checks": ["adapter_sanitize"],
        "must_contain": ["quarantined"],
    },
    {
        "id": "A7.install.signed-artifact",
        "source_architecture": "A7",
        "source_unit": "ARC-0045",
        "epoch": "install-time",
        "arrival": "a7",
        "effect": "accept_signed_artifact",
        "plane_checks": ["signed_provenance_check"],
        "must_contain": ["signed provenance-bearing artifacts"],
    },
    {
        "id": "A7.activate.grant-materialize",
        "source_architecture": "A7",
        "source_unit": "ARC-0045",
        "epoch": "activation-time",
        "arrival": "a7",
        "effect": "materialize_grant",
        "plane_checks": ["least_privilege_grant_table"],
        "must_contain": ["least-privilege capability grants"],
    },
    {
        "id": "A7.dispatch.skill",
        "source_architecture": "A7",
        "source_unit": "ARC-0045",
        "epoch": "dispatch-time",
        "arrival": "a7",
        "effect": "invoke_skill",
        "plane_checks": [],
        "must_contain": ["every capability invocation crosses it"],
    },
    {
        "id": "A7.dispatch.hook",
        "source_architecture": "A7",
        "source_unit": "ARC-0045",
        "epoch": "dispatch-time",
        "arrival": "a7",
        "effect": "invoke_hook",
        "plane_checks": [],
        "must_contain": ["every capability invocation crosses it"],
    },
    {
        "id": "A7.dispatch.mcp-tool",
        "source_architecture": "A7",
        "source_unit": "ARC-0045",
        "epoch": "dispatch-time",
        "arrival": "a7",
        "effect": "invoke_mcp_tool",
        "plane_checks": [],
        "must_contain": ["every capability invocation crosses it"],
    },
    {
        "id": "A7.dispatch.council",
        "source_architecture": "A7",
        "source_unit": "ARC-0045",
        "epoch": "dispatch-time",
        "arrival": "a7",
        "effect": "invoke_council",
        "plane_checks": ["injection_resistant_boundary"],
        "must_contain": ["injection-resistant boundaries"],
    },
    {
        "id": "A7.workflow.invoke",
        "source_architecture": "A7",
        "source_unit": "ARC-0045",
        "epoch": "workflow-invocation-time",
        "arrival": "a7",
        "effect": "invoke_workflow",
        "plane_checks": ["injection_resistant_boundary"],
        "must_contain": ["workflow and council content"],
    },
)

# Live interfaces on this tree (not in the A3/A4/A6/A7 catalog minuend).
LIVE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "A1.install.load-skill",
        "source_architecture": "A1",
        "source_unit": "ARC-0003",
        "epoch": "install-time",
        "arrival": "a1_config",
        "effect": "load_static_skill",
        "plane_checks": [],
        "live_role": "skills",
        "live_path": "command-center/phase3/A1/DESIGN.json",
    },
    {
        "id": "A1.install.load-hook",
        "source_architecture": "A1",
        "source_unit": "ARC-0003",
        "epoch": "install-time",
        "arrival": "a1_config",
        "effect": "load_static_hook",
        "plane_checks": [],
        "live_role": "hooks",
        "live_path": "command-center/phase3/A1/DESIGN.json",
    },
    {
        "id": "A1.install.load-mcp-mount",
        "source_architecture": "A1",
        "source_unit": "ARC-0003",
        "epoch": "install-time",
        "arrival": "a1_config",
        "effect": "load_mcp_mount",
        "plane_checks": [],
        "live_role": "mcp-mounts",
        "live_path": "command-center/phase3/A1/DESIGN.json",
    },
    {
        "id": "A1.workflow.invoke",
        "source_architecture": "A1",
        "source_unit": "ARC-0003",
        "epoch": "workflow-invocation-time",
        "arrival": "a1_config",
        "effect": "invoke_static_workflow",
        "plane_checks": [],
        "live_role": "workflow-blueprints",
        "live_path": "command-center/phase3/A1/DESIGN.json",
    },
    {
        "id": "A1.dispatch.council-preset",
        "source_architecture": "A1",
        "source_unit": "ARC-0003",
        "epoch": "dispatch-time",
        "arrival": "a1_config",
        "effect": "invoke_council_preset",
        "plane_checks": [],
        "live_role": "council-presets",
        "live_path": "command-center/phase3/A1/DESIGN.json",
    },
    {
        "id": "A2.install.generate-marketplace-entry",
        "source_architecture": "A2",
        "source_unit": "ARC-0010",
        "epoch": "install-time",
        "arrival": "a2_generate",
        "effect": "land_generated_marketplace_entry",
        "plane_checks": ["typed_registry_validate"],
        "live_role": "marketplace-entries",
        "live_path": "command-center/phase3/A2/DESIGN.json",
    },
    {
        "id": "A2.install.generate-plugin",
        "source_architecture": "A2",
        "source_unit": "ARC-0010",
        "epoch": "install-time",
        "arrival": "a2_generate",
        "effect": "land_generated_plugin",
        "plane_checks": ["typed_registry_validate"],
        "live_role": "plugin-manifest",
        "live_path": "command-center/phase3/A2/DESIGN.json",
    },
    {
        "id": "A2.install.generate-skill",
        "source_architecture": "A2",
        "source_unit": "ARC-0010",
        "epoch": "install-time",
        "arrival": "a2_generate",
        "effect": "land_generated_skill",
        "plane_checks": ["typed_registry_validate"],
        "live_role": "skill-deployments",
        "live_path": "command-center/phase3/A2/DESIGN.json",
    },
    {
        "id": "A2.workflow.invoke-generated",
        "source_architecture": "A2",
        "source_unit": "ARC-0010",
        "epoch": "workflow-invocation-time",
        "arrival": "a2_generate",
        "effect": "invoke_generated_workflow",
        "plane_checks": ["typed_registry_validate"],
        "live_role": "workflow-catalog",
        "live_path": "command-center/phase3/A2/DESIGN.json",
    },
    {
        "id": "A5.workflow.dispatch-unit",
        "source_architecture": "A5",
        "source_unit": "ARC-0031",
        "epoch": "workflow-invocation-time",
        "arrival": "a5_ledger",
        "effect": "dispatch_work_unit",
        "plane_checks": ["append_only_ledger_claim"],
        "must_contain": ["ONE shared completion reducer"],
    },
)


def load_catalog() -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("catalog-unparseable")
    return data


def catalog_unit(data: dict[str, Any], uid: str) -> dict[str, Any]:
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise RuntimeError(f"catalog-missing:{uid}")


def _haystack(unit: dict[str, Any]) -> str:
    return " ".join(
        [
            str(unit.get("question_or_target") or ""),
            str(unit.get("title") or ""),
            " ".join(str(t) for t in (unit.get("tests_required") or [])),
        ]
    )


def _bind_catalog(spec: dict[str, Any], unit: dict[str, Any]) -> None:
    needles = spec.get("must_contain") or []
    hay = _haystack(unit)
    for needle in needles:
        if needle not in hay:
            raise RuntimeError(
                f"catalog-unbind:{spec['id']}:{spec['source_unit']}:{needle!r}"
            )


def _design_entry_ids(arch: str) -> list[str] | None:
    path = REPO / "command-center" / "phase3" / arch / "DESIGN.json"
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return None
    rows = doc.get("entry_paths") or doc.get("capability_entry_paths")
    if not isinstance(rows, list) or not rows:
        return None
    ids: list[str] = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            ids.append(row["id"])
        elif isinstance(row, str):
            ids.append(row)
    return ids or None


def _live_role_present(spec: dict[str, Any]) -> None:
    rel = spec.get("live_path")
    role = spec.get("live_role")
    if not rel or not role:
        return
    path = REPO / rel
    if not path.is_file():
        raise RuntimeError(f"live-dossier-missing:{rel}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    roles = [
        str(row.get("role") or "")
        for row in (doc.get("file_set") or [])
        if isinstance(row, dict)
    ]
    if role not in roles:
        raise RuntimeError(f"live-role-absent:{rel}:{role}")


def dossier_status() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arch in ("A3", "A4", "A6", "A7", "A9"):
        path = REPO / "command-center" / "phase3" / arch / "DESIGN.json"
        out[arch] = {
            "design_path": f"command-center/phase3/{arch}/DESIGN.json",
            "present": path.is_file(),
            "entry_path_ids": _design_entry_ids(arch),
        }
    return out


def source_dossier_paths() -> list[dict[str, Any]]:
    """A3/A4/A6/A7 path set used as the reconciliation minuend."""
    data = load_catalog()
    rows: list[dict[str, Any]] = []
    for spec in SOURCE_SPECS:
        unit = catalog_unit(data, str(spec["source_unit"]))
        _bind_catalog(spec, unit)
        row = dict(spec)
        row["binding"] = "catalog-question"
        row["source_design_present"] = (
            REPO / "command-center" / "phase3" / str(spec["source_architecture"]) / "DESIGN.json"
        ).is_file()
        rows.append(row)
    by_arch: dict[str, list[str]] = {}
    for spec in SOURCE_SPECS:
        by_arch.setdefault(str(spec["source_architecture"]), []).append(str(spec["id"]))
    for arch, bound_ids in by_arch.items():
        design_ids = _design_entry_ids(arch)
        if design_ids is None:
            continue
        missing = sorted(set(bound_ids) - set(design_ids))
        if missing:
            raise RuntimeError(f"design-gap:{arch}:{missing}")
    epochs = {r["epoch"] for r in rows}
    if not set(EPOCHS).issubset(epochs):
        raise RuntimeError(f"source-epochs-incomplete:{sorted(epochs)}")
    return rows


def live_interface_paths() -> list[dict[str, Any]]:
    data = load_catalog()
    rows: list[dict[str, Any]] = []
    for spec in LIVE_SPECS:
        if spec.get("must_contain"):
            unit = catalog_unit(data, str(spec["source_unit"]))
            _bind_catalog(spec, unit)
        if spec.get("live_path"):
            _live_role_present(spec)
        row = dict(spec)
        row["binding"] = "live-dossier" if spec.get("live_path") else "catalog-question"
        rows.append(row)
    return rows


def source_ids() -> list[str]:
    return [r["id"] for r in source_dossier_paths()]


def live_ids() -> list[str]:
    return [r["id"] for r in live_interface_paths()]
