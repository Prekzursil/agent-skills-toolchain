#!/usr/bin/env python3
"""A9 maximal-hybrid kernel: singular control planes + provenance.

The composition is a partition of authority, not a union of A1-A8 control
planes. Stacking A1's static tree and A2's registry as two writers of skill
identity would be the duplicate-control-plane defect the spec forbids.
A1 and A2 therefore donate mechanisms into ONE identity plane. A3-A8 each
donate one mechanism that does not author identity.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

A1 = "command-center/phase3/A1/DESIGN.json"
A2 = "command-center/phase3/A2/DESIGN.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"

ARCH_DESIGN_UNITS = {
    "A1": "ARC-0003",
    "A2": "ARC-0010",
    "A3": "ARC-0017",
    "A4": "ARC-0024",
    "A5": "ARC-0031",
    "A6": "ARC-0038",
    "A7": "ARC-0045",
    "A8": "ARC-0052",
}

CONTROL_PLANES: list[dict[str, Any]] = [
    {
        "id": "CP-IDENTITY",
        "name": "capability identity and content SSOT",
        "component": "typed-registry-loader",
        "borrowed_from": ["A1", "A2"],
        "governs": [
            "skill",
            "hook",
            "rule",
            "workflow_blueprint",
            "council_protocol",
            "council_preset",
            "mcp_mount",
            "plugin_manifest",
            "marketplace_entry_identity",
            "docs",
            "workflow_catalog",
            "council_catalog",
            "owner_overlay_retarget",
        ],
        "must_never_govern": [
            "package_version_pin",
            "permission_evaluate",
            "activation",
            "error_message",
        ],
        "role": (
            "The only writer of capability id, kind, schema, and body. "
            "Generated deployments are projections, not a second SSOT. "
            "Owner overlay may retarget an already-loaded id; it may not "
            "introduce a new id (A1 precedence.new_id_in_overlay fused into "
            "this loader, not a second plane)."
        ),
    },
    {
        "id": "CP-PIN",
        "name": "lockfile-pinned package version",
        "component": "lockfile-state-machine",
        "borrowed_from": ["A3"],
        "governs": [
            "package_version_pin",
            "package_install_state",
            "package_rollback",
            "package_cache_invalidation",
        ],
        "must_never_govern": [
            "skill",
            "marketplace_entry_identity",
            "permission_evaluate",
        ],
        "role": (
            "Authority over which version of an already-identified package is "
            "installed, and over install/update/rollback plus cache "
            "invalidation. Does not author identity."
        ),
    },
    {
        "id": "CP-ACTIVATE",
        "name": "lazy activation and resident-set budget",
        "component": "gateway-lifecycle",
        "borrowed_from": ["A4"],
        "governs": [
            "capability_index",
            "activation",
            "deactivation",
            "session_budget",
            "resident_set",
        ],
        "must_never_govern": [
            "skill",
            "permission_evaluate",
            "package_version_pin",
        ],
        "role": (
            "Indexes (as a derived view of identity+pin) and materializes "
            "only the selected set. Deactivation is defined for every class "
            "this plane activates. Exhausted budget REFUSES, it does not warn. "
            "Does not author identity and does not evaluate permission."
        ),
    },
    {
        "id": "CP-DISPATCH",
        "name": "work-unit runtime and shared reducer",
        "component": "ledger-dispatcher",
        "borrowed_from": ["A5"],
        "governs": [
            "work_unit_lifecycle",
            "ledger",
            "dispatch_claim",
            "completion_reduce",
            "fan_out_barrier",
        ],
        "must_never_govern": ["skill", "permission_evaluate", "vendor_route"],
        "role": (
            "Append-only ledger, at-least-once delivery plus idempotent units, "
            "one shared completion reducer, duplicate-dispatch exactly one "
            "winner. Does not author capability identity."
        ),
    },
    {
        "id": "CP-VENDOR",
        "name": "cross-vendor contract tiers",
        "component": "vendor-adapter",
        "borrowed_from": ["A6"],
        "governs": [
            "vendor_tier_assignment",
            "vendor_route",
            "capability_negotiation",
            "silent_downgrade_refusal",
        ],
        "must_never_govern": [
            "work_unit_lifecycle",
            "permission_evaluate",
            "skill",
        ],
        "role": (
            "Every work-unit field is assigned to exactly one of guaranteed / "
            "best-effort / vendor-only. A unit declaring GUARANTEED against a "
            "vendor that lacks the capability FAIL-LOUDs; it is never silently "
            "downgraded."
        ),
    },
    {
        "id": "CP-PERMIT",
        "name": "single permission choke point",
        "component": "permission-choke",
        "borrowed_from": ["A7"],
        "governs": [
            "permission_grant",
            "permission_evaluate",
            "artifact_sign",
            "secret_policy",
            "injection_boundary",
        ],
        "must_never_govern": ["skill", "activation", "error_message"],
        "role": (
            "Every capability invocation crosses this choke point. Other "
            "planes may not grant or evaluate permission. Fail-closed on "
            "unknown path. Artifacts are signed and secret-free."
        ),
    },
    {
        "id": "CP-SURFACE",
        "name": "operator jobs-to-be-done and error contract",
        "component": "product-surface",
        "borrowed_from": ["A8"],
        "governs": [
            "operator_command",
            "cockpit",
            "naming_discovery_ux",
            "error_message",
        ],
        "must_never_govern": [
            "skill",
            "permission_evaluate",
            "package_version_pin",
        ],
        "role": (
            "One command, one cockpit, one catalog as entry surfaces. Every "
            "failure path satisfies: what happened, what it means, the exact "
            "next action. Presentation is not identity and not permission."
        ),
    },
]

BORROWED: list[dict[str, Any]] = [
    {
        "architecture_id": "A1",
        "mechanism": (
            "Whole-object replacement precedence with no field merge, no "
            "evaluator, FAIL-CLOSED duplicate-in-one-file, and overlay that "
            "may retarget an existing id but may not introduce a new id."
        ),
        "lands_in": "CP-IDENTITY",
        "source_path": A1,
        "source_section": "question",
        "also_cites": [
            {"path": CATALOG, "section": "work_units[id=ARC-0003].title"},
            {
                "path": CATALOG,
                "section": "work_units[id=ARC-0003].tests_required",
            },
            {"path": A1, "section": "architecture_id"},
        ],
        "dossier_on_this_tree": True,
        "absent_dossier": A1,
        "taken": True,
        "rejected": (
            "unlisted_file silent skip is REFUTED as min-risk by ARC-0009; "
            "the hybrid loader FAIL-CLOSES on an on-disk capability file that "
            "the manifest/registry does not name (A2 orphan class)."
        ),
        "rejected_cite": {
            "path": CATALOG,
            "section": "work_units[id=ARC-0009].question_or_target",
        },
    },
    {
        "architecture_id": "A2",
        "mechanism": (
            "Typed registry as the only SSOT; generate() is a pure function; "
            "hand-edit of a generated artifact is TAMPERED not drift; restore "
            "is regenerate. additionalProperties false; no opaque passthrough."
        ),
        "lands_in": "CP-IDENTITY",
        "source_path": A2,
        "source_section": "question",
        "also_cites": [
            {"path": CATALOG, "section": "work_units[id=ARC-0010].title"},
            {
                "path": CATALOG,
                "section": "work_units[id=ARC-0010].tests_required",
            },
            {"path": A2, "section": "architecture_id"},
        ],
        "dossier_on_this_tree": True,
        "absent_dossier": A2,
        "taken": True,
        "rejected": (
            "Generated files are never authority. Opaque passthrough / untyped "
            "blob is the first inexpressible construct named by ARC-0010/"
            "ARC-0016 and is the escape hatch that would reintroduce a second "
            "identity writer."
        ),
        "rejected_cite": {
            "path": CATALOG,
            "section": "work_units[id=ARC-0016].question_or_target",
        },
    },
    {
        "architecture_id": "A3",
        "mechanism": (
            "Lockfile-pinned package state, install/update/rollback state "
            "machine with every (state, event) pair defined or explicitly "
            "rejected, and cache invalidation that makes "
            "stale-cache-masks-a-fixed-package unreachable."
        ),
        "lands_in": "CP-PIN",
        "source_path": "command-center/phase3/A3/DESIGN.json",
        "source_section": "question",
        "also_cites": [
            {"path": CATALOG, "section": "work_units[id=ARC-0017].title"},
            {
                "path": CATALOG,
                "section": "work_units[id=ARC-0017].tests_required",
            },
            {"path": "command-center/phase3/A3/DESIGN.json", "section": "architecture_id"},
        ],
        "dossier_on_this_tree": True,
        "absent_dossier": "command-center/phase3/A3/DESIGN.json",
        "taken": True,
        "rejected": (
            "A3's 'canonical registry index IS the control plane' is not "
            "taken: that would be a second identity writer beside A2. "
            "Identity stays in CP-IDENTITY; A3 donates pin/lifecycle only."
        ),
        "rejected_cite": {
            "path": CATALOG,
            "section": "work_units[id=ARC-0017].question_or_target",
        },
    },
    {
        "architecture_id": "A4",
        "mechanism": (
            "One mediating entry that indexes all capabilities but "
            "materializes only what a task selects; explicit activation AND "
            "deactivation; per-session budget that REFUSES once exhausted; "
            "stated resident-set floor when nothing is selected."
        ),
        "lands_in": "CP-ACTIVATE",
        "source_path": "command-center/phase3/A4/DESIGN.json",
        "source_section": "question",
        "also_cites": [
            {"path": CATALOG, "section": "work_units[id=ARC-0024].title"},
            {
                "path": CATALOG,
                "section": "work_units[id=ARC-0024].tests_required",
            },
            {"path": "command-center/phase3/A4/DESIGN.json", "section": "architecture_id"},
        ],
        "dossier_on_this_tree": True,
        "absent_dossier": "command-center/phase3/A4/DESIGN.json",
        "taken": True,
        "rejected": (
            "Gateway as discovery SSOT would duplicate CP-IDENTITY. "
            "Permission checks at selection time would duplicate CP-PERMIT "
            "and reintroduce TOCTOU (A4 catalog failure class)."
        ),
        "rejected_cite": {
            "path": CATALOG,
            "section": "work_units[id=ARC-0024].question_or_target",
        },
    },
    {
        "architecture_id": "A5",
        "mechanism": (
            "Typed work-unit queue, append-only resumable ledger, dispatchers "
            "for local/worktree/cloud, barriers and fan-out, ONE shared "
            "completion reducer, at-least-once plus idempotent units, "
            "duplicate-dispatch exactly one winner."
        ),
        "lands_in": "CP-DISPATCH",
        "source_path": "command-center/phase3/A5/DESIGN.json",
        "source_section": "question",
        "also_cites": [
            {"path": CATALOG, "section": "work_units[id=ARC-0031].title"},
            {
                "path": CATALOG,
                "section": "work_units[id=ARC-0031].tests_required",
            },
            {"path": "command-center/phase3/A5/DESIGN.json", "section": "architecture_id"},
        ],
        "dossier_on_this_tree": True,
        "absent_dossier": "command-center/phase3/A5/DESIGN.json",
        "taken": True,
        "rejected": (
            "Exactly-once delivery is not claimed. Catalog requires stating "
            "the guarantee; the honest one on this estate is at-least-once "
            "plus idempotent units."
        ),
        "rejected_cite": {
            "path": CATALOG,
            "section": "work_units[id=ARC-0031].question_or_target",
        },
    },
    {
        "architecture_id": "A6",
        "mechanism": (
            "One work-unit/artifact contract with per-vendor adapters, "
            "explicit guaranteed / best-effort / vendor-only tiers, every "
            "contract field in exactly one tier, FAIL-LOUD on missing "
            "GUARANTEED capability (no silent downgrade)."
        ),
        "lands_in": "CP-VENDOR",
        "source_path": "command-center/phase3/A6/DESIGN.json",
        "source_section": "question",
        "also_cites": [
            {"path": CATALOG, "section": "work_units[id=ARC-0038].title"},
            {
                "path": CATALOG,
                "section": "work_units[id=ARC-0038].tests_required",
            },
            {"path": "command-center/phase3/A6/DESIGN.json", "section": "architecture_id"},
        ],
        "dossier_on_this_tree": True,
        "absent_dossier": "command-center/phase3/A6/DESIGN.json",
        "taken": True,
        "rejected": (
            "Vendor interchangeability of every work-unit class is not "
            "claimed. Units must declare the minimum tier they need."
        ),
        "rejected_cite": {
            "path": CATALOG,
            "section": "work_units[id=ARC-0038].question_or_target",
        },
    },
    {
        "architecture_id": "A7",
        "mechanism": (
            "Least-privilege grants, signed provenance-bearing artifacts, "
            "secret-free bundles, injection-resistant workflow/council "
            "boundaries, and a SINGLE permission choke point that every "
            "capability invocation crosses."
        ),
        "lands_in": "CP-PERMIT",
        "source_path": "command-center/phase3/A7/DESIGN.json",
        "source_section": "question",
        "also_cites": [
            {"path": CATALOG, "section": "work_units[id=ARC-0045].title"},
            {
                "path": CATALOG,
                "section": "work_units[id=ARC-0045].tests_required",
            },
            {"path": "command-center/phase3/A7/DESIGN.json", "section": "architecture_id"},
        ],
        "dossier_on_this_tree": True,
        "absent_dossier": "command-center/phase3/A7/DESIGN.json",
        "taken": True,
        "rejected": (
            "Fail-open gates and permission evaluation on CP-ACTIVATE or "
            "CP-VENDOR. Other planes may request a grant; only CP-PERMIT "
            "evaluates."
        ),
        "rejected_cite": {
            "path": CATALOG,
            "section": "work_units[id=ARC-0045].question_or_target",
        },
    },
    {
        "architecture_id": "A8",
        "mechanism": (
            "Product surface organized around owner jobs-to-be-done: one "
            "command, one cockpit, one catalog; naming/discovery for the "
            "workflow and preset catalogue; SINGLE error-message contract "
            "(what happened, what it means, exact next action)."
        ),
        "lands_in": "CP-SURFACE",
        "source_path": "command-center/phase3/A8/DESIGN.json",
        "source_section": "report.question",
        "also_cites": [
            {"path": CATALOG, "section": "work_units[id=ARC-0052].title"},
            {
                "path": CATALOG,
                "section": "work_units[id=ARC-0052].tests_required",
            },
            {"path": "command-center/phase3/A8/DESIGN.json", "section": "report.architecture_id"},
        ],
        "dossier_on_this_tree": True,
        "absent_dossier": "command-center/phase3/A8/DESIGN.json",
        "taken": True,
        "rejected": (
            "UX as a second identity or permission plane, and one-click "
            "install that bypasses CP-PERMIT."
        ),
        "rejected_cite": {
            "path": CATALOG,
            "section": "work_units[id=ARC-0052].question_or_target",
        },
    },
]

FIRST_INEXPRESSIBLE = {
    "construct": (
        "A3 marketplace index as identity SSOT composed with A2 typed "
        "registry as identity SSOT"
    ),
    "why": (
        "Both would write capability identity. That is a duplicate control "
        "plane, which the spec forbids and which a hybrid winner is allowed "
        "only if it avoids. Maximal-over-mechanisms stops here rather than "
        "union the two identity writers."
    ),
    "stopped": True,
}

ID_SEL = re.compile(r"^([A-Za-z0-9_]+)\[id=([A-Za-z0-9._-]+)\]$")


def table_from_planes(
    planes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    planes = planes if planes is not None else CONTROL_PLANES
    rows: list[dict[str, Any]] = []
    for plane in planes:
        pid = plane["id"]
        for cap in plane["governs"]:
            rows.append(
                {
                    "capability_class": cap,
                    "authority": pid,
                    "authorities": [pid],
                    "authority_count": 1,
                    "component": plane["component"],
                    "borrowed_from": list(plane["borrowed_from"]),
                }
            )
    rows.sort(key=lambda r: r["capability_class"])
    return rows


def planted_duplicate_table() -> list[dict[str, Any]]:
    """Negative control: skill governed by two planes (P0)."""
    rows = table_from_planes()
    out: list[dict[str, Any]] = []
    found = False
    for row in rows:
        if row["capability_class"] == "skill":
            planted = dict(row)
            planted["authority"] = ["CP-IDENTITY", "CP-PIN"]
            planted["authorities"] = ["CP-IDENTITY", "CP-PIN"]
            planted["authority_count"] = 2
            planted["planted"] = True
            out.append(planted)
            found = True
        else:
            out.append(row)
    if not found:
        raise RuntimeError("skill row missing in authority table")
    return out


def _authority_list(row: dict[str, Any]) -> list[str]:
    if "authorities" in row and row["authorities"] is not None:
        val = row["authorities"]
        if isinstance(val, list):
            return [str(x) for x in val]
        return [str(val)]
    auth = row.get("authority")
    if auth is None or auth == "":
        return []
    if isinstance(auth, list):
        return [str(x) for x in auth]
    if isinstance(auth, str) and "," in auth:
        return [p.strip() for p in auth.split(",") if p.strip()]
    return [str(auth)]


def check_singularity(
    rows: list[dict[str, Any]],
    planes: list[dict[str, Any]] | None = None,
) -> tuple[bool, list[str]]:
    """Independent singularity check. Does not trust authority_count."""
    planes = planes if planes is not None else CONTROL_PLANES
    plane_ids = {p["id"] for p in planes}
    defects: list[str] = []
    seen: dict[str, str] = {}
    for i, row in enumerate(rows):
        cap = row.get("capability_class")
        if not isinstance(cap, str) or not cap.strip():
            defects.append(f"row[{i}] missing capability_class")
            continue
        auths = _authority_list(row)
        if len(auths) != 1:
            defects.append(
                f"P0 duplicate-or-empty authority capability_class={cap} "
                f"authorities={auths}"
            )
            continue
        auth = auths[0]
        if auth not in plane_ids:
            defects.append(
                f"row {cap} authority {auth} is not a declared control plane"
            )
        if cap in seen and seen[cap] != auth:
            defects.append(
                f"P0 capability_class={cap} governed by {seen[cap]} and {auth}"
            )
        elif cap in seen:
            defects.append(f"duplicate row for capability_class={cap}")
        else:
            seen[cap] = auth

    derived: dict[str, str] = {}
    for plane in planes:
        pid = plane["id"]
        for cap in plane["governs"]:
            if cap in derived and derived[cap] != pid:
                defects.append(
                    f"control_planes overlap: {cap} in {derived[cap]} and {pid}"
                )
            derived[cap] = pid
        for forbidden in plane.get("must_never_govern") or []:
            if forbidden in plane["governs"]:
                defects.append(
                    f"{pid} governs {forbidden} which it must_never_govern"
                )

    if seen != derived:
        defects.append(
            "table vs control_planes.governs mismatch "
            f"table_only={sorted(set(seen) - set(derived))} "
            f"planes_only={sorted(set(derived) - set(seen))}"
        )
        for cap, auth in seen.items():
            if derived.get(cap) != auth:
                defects.append(
                    f"table[{cap}]={auth} planes[{cap}]={derived.get(cap)}"
                )

    for plane in planes:
        pid = plane["id"]
        for forbidden in plane.get("must_never_govern") or []:
            if seen.get(forbidden) == pid:
                defects.append(
                    f"{pid} is table authority for {forbidden} which it "
                    "must_never_govern"
                )

    return (len(defects) == 0), defects


def resolve_section(doc: Any, section: str) -> Any:
    cur = doc
    if not section:
        raise KeyError("empty section")
    for raw_part in section.split("."):
        m = ID_SEL.match(raw_part)
        if m:
            key, wanted = m.group(1), m.group(2)
            if not isinstance(cur, dict) or key not in cur:
                raise KeyError(raw_part)
            seq = cur[key]
            if not isinstance(seq, list):
                raise KeyError(raw_part)
            found = None
            for item in seq:
                if isinstance(item, dict) and item.get("id") == wanted:
                    found = item
                    break
            if found is None:
                raise KeyError(raw_part)
            cur = found
            continue
        if isinstance(cur, dict) and raw_part in cur:
            cur = cur[raw_part]
            continue
        raise KeyError(raw_part)
    return cur


def load_json(rel: str) -> Any:
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    return json.loads(path.read_text(encoding="utf-8"))


def check_one_cite(path: str, section: str) -> tuple[bool, str]:
    try:
        doc = load_json(path)
    except FileNotFoundError:
        return False, f"source_path absent: {path}"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, f"unparseable {path}: {type(exc).__name__}"
    try:
        val = resolve_section(doc, section)
    except KeyError:
        return False, f"section not found {path}#{section}"
    if val is None or val == "" or val == []:
        return False, f"empty section {path}#{section}"
    return True, "ok"


def check_provenance(
    borrowed: list[dict[str, Any]] | None = None,
) -> tuple[bool, list[str]]:
    borrowed = borrowed if borrowed is not None else BORROWED
    defects: list[str] = []
    seen_arch: list[str] = []
    plane_ids = {p["id"] for p in CONTROL_PLANES}
    for i, mech in enumerate(borrowed):
        arch = mech.get("architecture_id")
        if not isinstance(arch, str) or arch not in ARCH_DESIGN_UNITS:
            defects.append(f"borrowed[{i}] bad architecture_id={arch}")
            continue
        seen_arch.append(arch)
        for key in ("mechanism", "source_path", "source_section", "lands_in"):
            if not str(mech.get(key) or "").strip():
                defects.append(f"{arch} missing {key}")
        path = str(mech.get("source_path") or "")
        section = str(mech.get("source_section") or "")
        ok, why = check_one_cite(path, section)
        if not ok:
            defects.append(f"{arch} primary cite: {why}")
        for extra in mech.get("also_cites") or []:
            if not isinstance(extra, dict):
                defects.append(f"{arch} also_cites entry not object")
                continue
            ok, why = check_one_cite(
                str(extra.get("path")), str(extra.get("section"))
            )
            if not ok:
                defects.append(f"{arch} also_cites: {why}")
        rc = mech.get("rejected_cite") or {}
        if rc:
            ok, why = check_one_cite(str(rc.get("path")), str(rc.get("section")))
            if not ok:
                defects.append(f"{arch} rejected_cite: {why}")
        absent = mech.get("absent_dossier")
        on_tree = bool(mech.get("dossier_on_this_tree"))
        if absent:
            exists = (REPO / str(absent)).is_file()
            if on_tree and not exists:
                defects.append(
                    f"{arch} claimed dossier_on_this_tree but {absent} missing"
                )
            if not on_tree and exists:
                defects.append(
                    f"{arch} claimed dossier absent but {absent} is on disk; "
                    "cite it"
                )
            if path.replace("\\", "/") == str(absent).replace("\\", "/") and (
                not exists
            ):
                defects.append(
                    f"{arch} cites missing DESIGN.json {absent} (overclaim)"
                )
        if mech.get("lands_in") not in plane_ids:
            defects.append(
                f"{arch} lands_in {mech.get('lands_in')} not a control plane"
            )

    expected = [f"A{i}" for i in range(1, 9)]
    if seen_arch != expected:
        defects.append(f"borrowed architecture set {seen_arch} != {expected}")
    return (len(defects) == 0), defects


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def design_get(doc: dict[str, Any], key: str, default: Any = None) -> Any:
    """Read a dossier field from the document root or report payload."""
    if key in doc and doc[key] is not None:
        return doc[key]
    report = doc.get("report")
    if isinstance(report, dict) and key in report and report[key] is not None:
        return report[key]
    return default
