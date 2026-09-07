r"""P2 ralph batch: CC-0008, CC-0014, CC-0012.

Measure existing tooling honestly. Emit BLOCKED pending independent review.
Never SUCCESS without a real independent-review artifact.
No live catalog rewrite. No nest dumps.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(L.REPO / "platform" / "lib"))
import atomic_receipt as ar  # noqa: E402

STARTED = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
FLOOR = 2048


def _load_integrity():
    p = L.REPO / "command-center" / "_catalog_integrity.py"
    spec = importlib.util.spec_from_file_location("catalog_integrity", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _write(rel: str, text: str) -> Path:
    path = L.REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return path


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def probe_cc0008() -> dict:
    """Real probes for scale/merge/collision/allocation. Never writes live catalog."""
    mod = _load_integrity()
    slices = L.REPO / "command-center" / "catalog-slices"
    cat_path = L.REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    pg_path = L.REPO / "command-center" / "PHASE-GRAPH.json"

    # Probe A: read-back merged count OFF DISK (not merger belief)
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    wu = cat.get("work_units") or []
    meta = cat.get("work_units_meta") or {}
    readback = {
        "catalog_path": "command-center/WORK-UNIT-CATALOG.json",
        "work_units_read_back": len(wu),
        "items_preserved": len(cat.get("items") or []),
        "schema_version": cat.get("schema_version"),
        "meta_work_unit_count": meta.get("work_unit_count"),
        "meta_target": meta.get("target"),
        "meta_shortfall": meta.get("shortfall"),
        "meta_status": meta.get("status"),
        "slice_files_merged_meta": meta.get("slice_files_merged"),
        "floor": FLOOR,
        "meets_floor": len(wu) >= FLOOR,
        "shortfall_vs_floor": FLOOR - len(wu),
    }

    # Probe B: audit live slices (algorithmic)
    audit, units = mod.audit(str(slices))
    per_file = audit["unit_count_per_file"]
    prefix_counts: dict[str, int] = {}
    for u in units:
        m = re.match(r"^([A-Z]{2,4})-(\d{4})$", str(u.get("id")))
        if m:
            prefix_counts[m.group(1)] = prefix_counts.get(m.group(1), 0) + 1

    # Bucket field vs PHASE-GRAPH quotas
    pg = json.loads(pg_path.read_text(encoding="utf-8"))
    buckets = (pg.get("allocation_buckets") or {}).get("buckets") or []
    quota = {b["id"]: b["units"] for b in buckets}
    declared_bucket = {}
    missing_bucket = 0
    for u in units:
        b = u.get("bucket")
        if isinstance(b, str) and b in quota:
            declared_bucket[b] = declared_bucket.get(b, 0) + 1
        else:
            missing_bucket += 1

    # Allocation table artifact search
    alloc_candidates = [
        "command-center/ID-NAMESPACE-ALLOCATION.json",
        "command-center/id-namespace-allocation.json",
        "command-center/ALLOCATION-TABLE.json",
        "command-center/schema/option-id-namespace.schema.json",
    ]
    alloc_present = {p: (L.REPO / p).is_file() for p in alloc_candidates}
    # Inline BUCKET_QUOTA in integrity script is NOT the shipped allocation table
    # binding prefix -> bucket; measure that separately.
    has_prefix_to_bucket_table = False
    # PHASE-GRAPH has bucket quotas but not prefix bindings
    pg_has_prefix_bindings = any(
        isinstance(b, dict) and ("prefix" in b or "prefixes" in b or "id_prefix" in b)
        for b in buckets
    )

    # Probe C: collision control — plant CC-0007 in two list-shaped slices
    scratch = L.REPO / "command-center/p2-wave/probes/CC-0008/scratch-collision"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    cc = json.loads((slices / "CC-1.json").read_text(encoding="utf-8"))
    cc7 = next(u for u in cc if u.get("id") == "CC-0007")
    (scratch / "left.json").write_text(
        json.dumps([dict(cc7)], indent=1) + "\n", encoding="utf-8"
    )
    (scratch / "right.json").write_text(
        json.dumps([dict(cc7)], indent=1) + "\n", encoding="utf-8"
    )
    bad_audit, bad_units = mod.audit(str(scratch))
    dups = bad_audit["ids"]["duplicate_ids"]
    collision_detected = "CC-0007" in dups and len(dups["CC-0007"]) >= 2

    # Does do_merge REFUSE? Inspect source + simulate write path without touching live catalog
    src = (L.REPO / "command-center/_catalog_integrity.py").read_text(encoding="utf-8")
    # Parse do_merge AST for raise/SystemExit on duplicates
    tree = ast.parse(src)
    do_merge_fn = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "do_merge"
    )
    raises = [
        n
        for n in ast.walk(do_merge_fn)
        if isinstance(n, ast.Raise)
        or (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in {"SystemExit", "exit"}
        )
    ]
    # Simulate merge into temp file using the same algorithm body (copy of clean+sort+dump)
    # without calling do_merge (which mutates LIVE catalog).
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Build clean list the way do_merge does
        clean = []
        for u in bad_units:
            v = {k: val for k, val in u.items() if not k.startswith("__")}
            v["_source_slice_file"] = u["__file"]
            clean.append(v)
        clean.sort(key=lambda x: str(x.get("id")))
        # Collision gate as required: must FAIL with both source paths named.
        # Measured behavior of do_merge: it writes anyway and only records count in meta.
        would_write = True  # do_merge has no refuse branch
        both_paths_named = collision_detected and set(dups.get("CC-0007", [])) == {
            "left.json[0]",
            "right.json[0]",
        }
        # Order-independence of serialization on DISJOINT ids (collision case is separate).
        # Equal ids make stable-sort preserve input order and are not the order-independence claim.
        cc1 = next(u for u in cc if u.get("id") == "CC-0001")
        cc2 = next(u for u in cc if u.get("id") == "CC-0002")
        disjoint = []
        for label, unit in (("left", cc1), ("right", cc2)):
            v = {k: val for k, val in unit.items() if not str(k).startswith("__")}
            v["_source_slice_file"] = f"{label}.json"
            disjoint.append(v)
        order_a = json.dumps(
            {"work_units": sorted(disjoint, key=lambda x: str(x.get("id")))},
            ensure_ascii=False,
            indent=1,
            sort_keys=True,
        ).encode()
        order_b = json.dumps(
            {
                "work_units": sorted(
                    list(reversed(disjoint)), key=lambda x: str(x.get("id"))
                )
            },
            ensure_ascii=False,
            indent=1,
            sort_keys=True,
        ).encode()
        order_independent = order_a == order_b
        (td_path / "a.json").write_bytes(order_a)
        (td_path / "b.json").write_bytes(order_b)

    # Field-completeness vs CC-0001 armed gate (REQUIRED_20 incl bucket)
    missing_fields = {
        k: v for k, v in audit["fields"]["missing_absent_key_total"].items() if v
    }
    field_complete = not missing_fields

    # Idempotence note: re-merge would rewrite work_units from slices; meta records
    # known_defects but does not no-op. Measure by comparing slice-derived id set to catalog.
    slice_ids = sorted(str(u.get("id")) for u in units)
    cat_ids = sorted(str(u.get("id")) for u in wu)
    ids_match_slices = slice_ids == cat_ids

    raw = {
        "probe": "CC-0008 scale/merge/collision/allocation",
        "readback": readback,
        "slice_audit": {
            "unit_count_total": audit["unit_count_total"],
            "file_count": audit["file_count"],
            "unit_count_per_file": per_file,
            "sum_per_file": sum(per_file.values()),
            "duplicate_id_count": audit["ids"]["duplicate_id_count"],
            "shortfall_vs_target": audit["shortfall_vs_target"],
            "prefix_counts": dict(sorted(prefix_counts.items())),
            "missing_bucket_field": missing_bucket,
            "declared_bucket_counts": dict(sorted(declared_bucket.items())),
            "phase_graph_quota": quota,
            "phase_graph_measured_sum": (pg.get("allocation_buckets") or {}).get(
                "measured_sum"
            ),
            "missing_fields_nonzero": missing_fields,
            "field_complete_against_REQUIRED_20": field_complete,
        },
        "allocation_table": {
            "candidate_paths_present": alloc_present,
            "phase_graph_has_prefix_bindings": pg_has_prefix_bindings,
            "inline_BUCKET_QUOTA_in__catalog_integrity": True,
            "first_class_prefix_to_bucket_table_shipped": has_prefix_to_bucket_table
            or pg_has_prefix_bindings,
            "verdict": "ABSENT",
        },
        "merge_tool": {
            "path": "command-center/_catalog_integrity.py",
            "function": "do_merge",
            "sorts_by_id": "clean.sort(key=lambda x: str(x.get(\"id\")))" in src
            or "clean.sort(key=lambda x: str(x.get('id')))" in src
            or "key=lambda x: str(x.get(\"id\"))" in src
            or "key=lambda x: str(x.get('id'))" in src,
            "raise_nodes_in_do_merge": len(raises),
            "refuses_on_duplicate": False,
            "records_duplicate_count_in_meta_only": True,
        },
        "collision_control": {
            "planted_id": "CC-0007",
            "scratch": "command-center/p2-wave/probes/CC-0008/scratch-collision",
            "audit_duplicate_id_count": bad_audit["ids"]["duplicate_id_count"],
            "duplicate_ids": dups,
            "both_source_paths_named": both_paths_named,
            "detector_fires": collision_detected,
            "do_merge_would_refuse": False,
            "do_merge_would_write_anyway": would_write,
            "test_required_pass": False,
            "reason": (
                "check_ids detects the planted CC-0007 collision and names both "
                "source paths, but do_merge has no refuse branch and would write "
                "the colliding set into WORK-UNIT-CATALOG.json while only recording "
                "duplicate_id_count in work_units_meta.known_defects_at_merge."
            ),
        },
        "order_independence": {
            "byte_identical_after_permute_then_sort": order_independent,
            "sha256_a": _sha_bytes(order_a),
            "sha256_b": _sha_bytes(order_b),
            "pass": order_independent,
        },
        "idempotence": {
            "slice_ids_equal_catalog_work_units": ids_match_slices,
            "slice_id_count": len(slice_ids),
            "catalog_id_count": len(cat_ids),
            "note": (
                "Ids currently match. do_merge always rewrites work_units; "
                "true no-op idempotence (byte-identical file if already merged) "
                "is NOT implemented as a gate."
            ),
            "pass": False,
        },
        "tests_required_results": {
            "collision_control": "FAIL",
            "order_independence": "PASS" if order_independent else "FAIL",
            "field_completeness": "FAIL" if not field_complete else "PASS",
            "idempotence": "FAIL",
        },
        "verdict": "BLOCKED",
        "blocked_reason": (
            "Floor shortfall 41/2048; no first-class prefix→bucket allocation table; "
            "collision detector fires but merge does not refuse; field-completeness "
            "fails (1735 missing bucket); independent reviewer not run."
        ),
    }
    out = "command-center/p2-wave/probes/CC-0008/probe-results.json"
    _write(out, json.dumps(raw, indent=2, sort_keys=True))
    txt = "command-center/p2-wave/probes/CC-0008/probe-results.raw.txt"
    lines = [
        "PROBE=CC-0008",
        f"work_units_read_back={readback['work_units_read_back']}",
        f"floor={FLOOR}",
        f"shortfall={readback['shortfall_vs_floor']}",
        f"meets_floor={readback['meets_floor']}",
        f"slice_sum={sum(per_file.values())}",
        f"prefix_counts={json.dumps(dict(sorted(prefix_counts.items())), separators=(',', ':'))}",
        f"missing_bucket_field={missing_bucket}",
        f"allocation_table=ABSENT",
        f"collision_detector_fires={collision_detected}",
        f"collision_paths={json.dumps(dups)}",
        f"do_merge_refuses={False}",
        f"order_independent={order_independent}",
        f"field_complete={field_complete}",
        f"idempotence_gate={False}",
        f"verdict=BLOCKED",
        f"blocked_reason={raw['blocked_reason']}",
    ]
    _write(txt, "\n".join(lines))
    return raw


def probe_cc0014() -> dict:
    """Measure TEST-REGISTRY vs PROTECTING/UNPROVEN/mutation-record contract."""
    tr_path = L.REPO / "command-center/TEST-REGISTRY.json"
    cr_path = L.REPO / "command-center/CLAIM-REGISTRY.json"
    schema_path = L.REPO / "command-center/schema/test-registry-entry.schema.json"
    tr = json.loads(tr_path.read_text(encoding="utf-8"))
    cr = json.loads(cr_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # Structural scan for PROTECTING / UNPROVEN / mutation_record
    blob = json.dumps(tr)
    has_protecting = '"PROTECTING"' in blob or "'PROTECTING'" in blob
    has_unproven = '"UNPROVEN"' in blob
    has_mutation_record = "mutation_record" in blob or "mutation_diff" in blob
    has_status_field = any(
        isinstance(x, dict) and "status" in x
        for x in (tr.get("suites") or []) + (tr.get("invariants") or [])
    )

    suites = tr.get("suites") or []
    invariants = tr.get("invariants") or []
    claims = cr.get("claims") or []

    # Aggregation control: if we treat all entries without mutation as UNPROVEN,
    # protected claim count must be 0.
    protecting_count = 0
    unproven_count = 0
    hole_count = 0
    for suite in suites:
        # Narrative red_proof is not a mutation record
        if suite.get("red_proof") and has_mutation_record:
            protecting_count += 1
        else:
            unproven_count += 1
    for inv in invariants:
        if inv.get("mutation_record"):
            protecting_count += 1
        else:
            unproven_count += 1

    # Attempt to register a synthetic entry mentally: no mutation -> must be UNPROVEN
    synthetic_no_mut = {"id": "SYNTH-NO-MUT", "status": None, "mutation_record": None}
    # There is no registry API that assigns status; measure absence
    registry_api_paths = [
        "command-center/test_registry.py",
        "tools/command-center/test_registry_bind.py",
        "platform/lib/test_registry.py",
    ]
    api_present = {p: (L.REPO / p).is_file() for p in registry_api_paths}
    # tools/command-center/tests/test_registry.py exists — count-assert only
    count_test = L.REPO / "tools/command-center/tests/test_registry.py"
    count_test_text = count_test.read_text(encoding="utf-8") if count_test.is_file() else ""
    mentions_protecting = "PROTECTING" in count_test_text
    mentions_unproven = "UNPROVEN" in count_test_text

    coverage_if_all_unproven = {
        "entries_scanned": unproven_count + protecting_count,
        "protecting": protecting_count,
        "unproven_proxy": unproven_count,
        "protected_claims": 0 if protecting_count == 0 else "NONZERO",
        "aggregation_control_expected_protected_claims": 0,
        "aggregation_control_pass_if_no_false_100pct": protecting_count == 0,
    }

    raw = {
        "probe": "CC-0014 bind tests to claims to units",
        "test_registry": {
            "path": "command-center/TEST-REGISTRY.json",
            "schema_version": tr.get("schema_version"),
            "suite_count": len(suites),
            "invariant_count": len(invariants),
            "top_level_keys": sorted(tr.keys()),
            "suite_keys_sample": sorted(suites[0].keys()) if suites else [],
            "has_PROTECTING_token": has_protecting,
            "has_UNPROVEN_token": has_unproven,
            "has_mutation_record_field": has_mutation_record,
            "has_status_field_on_entries": has_status_field,
        },
        "claim_registry": {
            "path": "command-center/CLAIM-REGISTRY.json",
            "claim_count": len(claims),
            "claim_keys_sample": sorted(claims[0].keys()) if claims else [],
        },
        "output_schema_shim": {
            "path": "command-center/schema/test-registry-entry.schema.json",
            "is_generated_shim": "GENERATED SHIM" in (schema.get("$comment") or ""),
            "ref": schema.get("$ref"),
            "note": "Delegates to generic receipt profile; does not encode PROTECTING rules.",
        },
        "binding_api": {
            "candidate_paths_present": api_present,
            "count_assert_test_present": count_test.is_file(),
            "count_assert_mentions_PROTECTING": mentions_protecting,
            "count_assert_mentions_UNPROVEN": mentions_unproven,
        },
        "controls": {
            "register_without_mutation_must_be_UNPROVEN": {
                "synthetic": synthetic_no_mut,
                "result": "NOT-IMPLEMENTED",
                "pass": False,
            },
            "mutation_fail_to_PROTECTING": {"result": "NOT-IMPLEMENTED", "pass": False},
            "survived_mutation_surfaces_hole": {
                "hole_count_measured": hole_count,
                "result": "NOT-IMPLEMENTED",
                "pass": False,
            },
            "aggregation_all_UNPROVEN_reports_0_protected": coverage_if_all_unproven,
        },
        "tests_required_results": {
            "no_mutation_UNPROVEN": "FAIL",
            "mutation_fail_PROTECTING": "FAIL",
            "survived_mutation_hole": "FAIL",
            "aggregation_0_protected": (
                "PASS-PROXY"
                if coverage_if_all_unproven["aggregation_control_pass_if_no_false_100pct"]
                else "FAIL"
            ),
        },
        "verdict": "BLOCKED",
        "blocked_reason": (
            "TEST-REGISTRY.json exists with suite/invariant narrative red_proof but "
            "has no PROTECTING/UNPROVEN status machine, no mutation_record fields, and "
            "no binder API that refuses coverage credit without a failing mutation. "
            "Independent reviewer not run."
        ),
    }
    _write(
        "command-center/p2-wave/probes/CC-0014/probe-results.json",
        json.dumps(raw, indent=2, sort_keys=True),
    )
    _write(
        "command-center/p2-wave/probes/CC-0014/probe-results.raw.txt",
        "\n".join(
            [
                "PROBE=CC-0014",
                f"suites={len(suites)}",
                f"invariants={len(invariants)}",
                f"claims={len(claims)}",
                f"has_PROTECTING={has_protecting}",
                f"has_UNPROVEN={has_unproven}",
                f"has_mutation_record={has_mutation_record}",
                f"has_status_field={has_status_field}",
                f"protecting_count={protecting_count}",
                f"unproven_proxy={unproven_count}",
                f"verdict=BLOCKED",
                f"blocked_reason={raw['blocked_reason']}",
            ]
        ),
    )
    return raw


def probe_cc0012() -> dict:
    """Measure freeze flag / migration / gate presence without inventing activation."""
    schema_dir = L.REPO / "command-center/schema"
    freeze_marker_candidates = [
        "command-center/FREEZE.json",
        "command-center/SCHEMA-FREEZE.json",
        "command-center/freeze-flag.json",
        "command-center/LAUNCHER-FREEZE.json",
        "command-center/p2-wave/probes/AUD-0095/freeze-anchor.json",
    ]
    freeze_present = {p: (L.REPO / p).is_file() for p in freeze_marker_candidates}
    aud0095 = L.REPO / "command-center/audit/AUD-0095-freeze-inventory.json"
    aud = json.loads(aud0095.read_text(encoding="utf-8")) if aud0095.is_file() else None

    # freeze_check.py referenced by AUD-0095 but absent in this tree?
    freeze_check = L.REPO / "command-center/p2-wave/probes/AUD-0095/freeze_check.py"
    freeze_inventory_py = (
        L.REPO / "command-center/p2-wave/probes/AUD-0095/freeze_inventory.py"
    )

    # Migration contract search
    migration_dirs = [
        L.REPO / "command-center/migrations",
        L.REPO / "command-center/schema/migrations",
        L.REPO / "platform/schema/migrations",
    ]
    migration_dir_state = {
        str(p.relative_to(L.REPO)): {
            "exists": p.is_dir(),
            "file_count": len(list(p.glob("*"))) if p.is_dir() else 0,
        }
        for p in migration_dirs
    }

    # Gate scripts
    gate_candidates = [
        "command-center/p2-wave/probes/AUD-0095/freeze_check.py",
        "ci/check_schema_freeze.py",
        "platform/lib/schema_freeze_gate.py",
        "tools/command-center/freeze_gate.py",
    ]
    gate_present = {p: (L.REPO / p).is_file() for p in gate_candidates}

    # Catalog schema_version
    cat = json.loads(
        (L.REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    schema_files = sorted(p.name for p in schema_dir.glob("*.json"))

    # Simulate required tests conceptually against ABSENT gate
    tests = {
        "mutation_change_frozen_schema_without_bump": {
            "result": "NOT-RUN",
            "pass": False,
            "reason": "No freeze gate executable present to mutate against",
        },
        "positive_bump_plus_migration_roundtrip": {
            "result": "NOT-RUN",
            "pass": False,
            "reason": "No migration engine / round-trip harness present",
        },
        "roundtrip_forward_back_byte_identical": {
            "result": "NOT-RUN",
            "pass": False,
        },
        "both_states_silent_on_non_frozen": {
            "result": "NOT-RUN",
            "pass": False,
        },
    }

    activation = {
        "freeze_flag_present": any(freeze_present.values()),
        "activation_commit_sha": None,
        "activation_timestamp": None,
        "aud0095_state": aud.get("state") if aud else None,
        "aud0095_sentinel_prefix": (aud.get("sentinel") or "")[:120] if aud else None,
        "freeze_check_py_present": freeze_check.is_file(),
        "freeze_inventory_py_present": freeze_inventory_py.is_file(),
    }

    raw = {
        "probe": "CC-0012 freeze schemas/launchers + versioned migration",
        "catalog_schema_version": cat.get("schema_version"),
        "schema_dir_file_count": len(schema_files),
        "freeze_marker_candidates": freeze_present,
        "activation": activation,
        "migration_dirs": migration_dir_state,
        "gate_candidates": gate_present,
        "related_units": {
            "AUD-0095_inventory_present": aud0095.is_file(),
            "AUD-0095_state": aud.get("state") if aud else None,
            "IMP-0477_receipt_present": (
                L.REPO / "command-center/receipts/IMP-0477.json"
            ).is_file(),
            "TST-0026_receipt_present": (
                L.REPO / "command-center/receipts/TST-0026.json"
            ).is_file(),
        },
        "evidence_requirement": {
            "needs_activation_commit_sha": True,
            "found_activation_commit_sha": False,
            "needs_migration_executed_on_pre_freeze_data": True,
            "found_executed_migration_roundtrip": False,
        },
        "tests_required_results": tests,
        "verdict": "BLOCKED",
        "blocked_reason": (
            "No freeze flag with recorded activation commit; freeze_check.py and "
            "migration directories absent in this tree (AUD-0095 inventory references "
            "probes that are not present); IMP-0477/TST-0026 receipts absent; "
            "independent reviewer not run."
        ),
    }
    _write(
        "command-center/p2-wave/probes/CC-0012/probe-results.json",
        json.dumps(raw, indent=2, sort_keys=True),
    )
    _write(
        "command-center/p2-wave/probes/CC-0012/probe-results.raw.txt",
        "\n".join(
            [
                "PROBE=CC-0012",
                f"catalog_schema_version={cat.get('schema_version')}",
                f"schema_files={len(schema_files)}",
                f"freeze_flag_present={activation['freeze_flag_present']}",
                f"activation_commit_sha={activation['activation_commit_sha']}",
                f"freeze_check_present={activation['freeze_check_py_present']}",
                f"migration_dirs={json.dumps(migration_dir_state)}",
                f"gates_present={json.dumps(gate_present)}",
                f"AUD-0095_state={activation['aud0095_state']}",
                f"verdict=BLOCKED",
                f"blocked_reason={raw['blocked_reason']}",
            ]
        ),
    )
    return raw


def _base_receipt(
    unit: str,
    schema: str,
    title: str,
    probe_dir: str,
    probe_raw: dict,
    evidence: list,
    tests: list,
    controls: list,
    defects: list,
    min_bytes: int = 2048,
) -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sentinel = (
        f"FAILED:{unit} blocked-on-independent-review; measured={probe_raw.get('verdict')}; "
        f"{probe_raw.get('blocked_reason', '')[:180]}"
    )
    arts = [
        L.art(f"{probe_dir}/probe-results.json", "primary"),
        L.art(f"{probe_dir}/probe-results.raw.txt", "log"),
        L.art("command-center/p2-wave/_build_CC0008_CC0014_CC0012.py", "control"),
        L.art("command-center/p2-wave/_p2lib.py", "supporting"),
        L.art("platform/lib/atomic_receipt.py", "supporting"),
    ]
    # unit-specific primary inputs
    if unit == "CC-0008":
        arts = [
            L.art("command-center/WORK-UNIT-CATALOG.json", "primary"),
            L.art("command-center/_catalog_integrity.py", "supporting"),
            L.art("command-center/PHASE-GRAPH.json", "supporting"),
            L.art("command-center/CATALOG-INTEGRITY.json", "supporting"),
        ] + arts
    elif unit == "CC-0014":
        arts = [
            L.art("command-center/TEST-REGISTRY.json", "primary"),
            L.art("command-center/CLAIM-REGISTRY.json", "supporting"),
            L.art("command-center/schema/test-registry-entry.schema.json", "supporting"),
        ] + arts
    else:
        arts = [
            L.art("command-center/audit/AUD-0095-freeze-inventory.json", "supporting"),
            L.art("command-center/WORK-UNIT-CATALOG.json", "supporting"),
        ] + arts

    report_kind = {
        "CC-0008": "catalog_scale_report",
        "CC-0014": "test-registry-entry",
        "CC-0012": "freeze_migration_report",
    }[unit]

    doc = {
        "schema_version": 1,
        "unit_id": unit,
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": f"command-center/WORK-UNIT-CATALOG.json:{unit}",
        "min_bytes_threshold": min_bytes,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": evidence,
        "timestamps": {"started_at": STARTED, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; escalate collisions to slice author; "
                "never rename to resolve; never relax mutation requirement; "
                "narrow freeze path scope rather than loosening the rule."
            ),
        },
        "tests": tests,
        "negative_controls": controls,
        "defects": defects,
        "failure": {
            "classification": [
                "blocked-on-independent-review",
                "dependency-blocked",
                "detector-failure",
            ],
            "reason": probe_raw.get("blocked_reason") or "pending independent review",
            "blocked_on": (
                "Independent fresh-context reviewer must confirm the measured gaps "
                "(and any subsequent repair) before SUCCESS may be emitted."
            ),
        },
        "reviewer": {
            "reviewer_id": "NOT-REVIEWED:no-independent-reviewer-this-wave",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "notes": (
                "ANTI-FALSE-GREEN: SUCCESS withheld. Implementer measured real probes "
                "and emitted BLOCKED pending independent review."
            ),
        },
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": unit,
        },
        "downstream_consumers": [],
        "residual_unknowns": [
            {
                "claim": (
                    f"Whether an independent reviewer will accept the measured "
                    f"BLOCKED disposition for {unit} without further repair."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Fresh-context reviewer re-runs the unit's probes from disk "
                    "artifacts and records PASS/FAIL independently."
                ),
            }
        ],
        "extensions": {
            "stage": "measure",
            "title": title,
            "probe_verdict": probe_raw.get("verdict"),
            "anti_false_green": True,
            "independent_review_required_for_SUCCESS": True,
        },
        "report": {
            "kind": report_kind,
            "summary": probe_raw.get("blocked_reason"),
            "measurements": {
                k: probe_raw[k]
                for k in list(probe_raw.keys())
                if k
                not in {
                    "probe",
                    "verdict",
                    "blocked_reason",
                    "tests_required_results",
                }
            },
        },
    }
    if unit == "CC-0014":
        tr = probe_raw.get("test_registry") or {}
        doc["report"] = {
            "kind": "test-registry-entry",
            "observations": [
                {
                    "name": "suite_count",
                    "measured": int(tr.get("suite_count") or 0),
                    "method": "json.loads(TEST-REGISTRY.json)['suites'] length",
                    "anchor": "command-center/TEST-REGISTRY.json",
                },
                {
                    "name": "has_PROTECTING_token",
                    "measured": bool(tr.get("has_PROTECTING_token")),
                    "method": "token scan of TEST-REGISTRY.json",
                    "anchor": "command-center/TEST-REGISTRY.json",
                },
                {
                    "name": "has_UNPROVEN_token",
                    "measured": bool(tr.get("has_UNPROVEN_token")),
                    "method": "token scan of TEST-REGISTRY.json",
                    "anchor": "command-center/TEST-REGISTRY.json",
                },
                {
                    "name": "has_mutation_record_field",
                    "measured": bool(tr.get("has_mutation_record_field")),
                    "method": "token scan of TEST-REGISTRY.json",
                    "anchor": "command-center/TEST-REGISTRY.json",
                },
            ],
            "control_ids": ["NC-NO-MUTATION-CREDIT"],
        }
    return doc


def build_all() -> list[tuple[str, str, dict]]:
    p8 = probe_cc0008()
    p14 = probe_cc0014()
    p12 = probe_cc0012()

    # CC-0008 evidence
    raw8 = (L.REPO / "command-center/p2-wave/probes/CC-0008/probe-results.raw.txt").read_text(
        encoding="utf-8"
    )
    e8 = [
        L.evidence(
            (
                f"Merged catalog read-back off disk: {p8['readback']['work_units_read_back']} "
                f"work_units; floor {FLOOR}; shortfall "
                f"{p8['readback']['shortfall_vs_floor']}; meets_floor="
                f"{p8['readback']['meets_floor']}."
            ),
            "CONFIRMED",
            "command-center/WORK-UNIT-CATALOG.json",
            [
                L.probe(
                    "source",
                    "file-read",
                    "python3 read WORK-UNIT-CATALOG.json work_units length",
                    raw8,
                    0,
                ),
                L.probe(
                    "verifier",
                    "static-analysis",
                    "command-center/_catalog_integrity.py --audit-only catalog-slices",
                    json.dumps(
                        {
                            "unit_count_total": p8["slice_audit"]["unit_count_total"],
                            "sum_per_file": p8["slice_audit"]["sum_per_file"],
                            "shortfall_vs_target": p8["slice_audit"][
                                "shortfall_vs_target"
                            ],
                        }
                    ),
                    0,
                ),
            ],
            "almost-certain",
        ),
        L.evidence(
            (
                "Collision detector names both source paths for planted CC-0007, but "
                "do_merge does not refuse and would write anyway."
            ),
            "CONFIRMED",
            "command-center/p2-wave/probes/CC-0008/scratch-collision",
            [
                L.probe(
                    "source",
                    "test-run",
                    "plant CC-0007 in left.json+right.json; audit()",
                    json.dumps(p8["collision_control"], indent=2)[:8000],
                    1,
                ),
                L.probe(
                    "verifier",
                    "static-analysis",
                    "AST-inspect do_merge for refuse-on-duplicate",
                    json.dumps(p8["merge_tool"], indent=2),
                    0,
                ),
            ],
            "almost-certain",
        ),
        L.evidence(
            (
                "First-class id-namespace allocation table binding one prefix to each "
                "bucket B01-B13 is ABSENT (PHASE-GRAPH quotas exist; 1735 units lack "
                "bucket field)."
            ),
            "REFUTED",
            "command-center/PHASE-GRAPH.json#allocation_buckets",
            [
                L.probe(
                    "source",
                    "file-read",
                    "search ID-NAMESPACE-ALLOCATION / prefix bindings",
                    json.dumps(p8["allocation_table"], indent=2),
                    0,
                ),
                L.probe(
                    "verifier",
                    "static-analysis",
                    "count units missing bucket field",
                    f"missing_bucket_field={p8['slice_audit']['missing_bucket_field']}",
                    0,
                ),
            ],
            "almost-certain",
        ),
    ]
    t8 = [
        {
            "id": "T-COLLISION",
            "name": "Collision control: two slices both claiming CC-0007 must fail the merge with both source paths named.",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 2,
            "output_tail": "detector fires + paths named; do_merge refuses=False",
        },
        {
            "id": "T-ORDER",
            "name": "Order-independence: merging the same slice set in permuted order must produce byte-identical output.",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "PASS" if p8["order_independence"]["pass"] else "FAIL",
            "assertions": 1,
            "output_tail": f"sha_match={p8['order_independence']['pass']}",
        },
        {
            "id": "T-FIELDS",
            "name": "Field-completeness: every merged item must satisfy the CC-0001 armed gate.",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 1,
            "output_tail": f"missing_fields={p8['slice_audit']['missing_fields_nonzero']}",
        },
        {
            "id": "T-IDEM",
            "name": "Idempotence: re-merging an already-merged catalog must be a no-op, not a duplication.",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 1,
            "output_tail": "no-op gate not implemented",
        },
    ]
    c8 = [
        L.control(
            "NC-PLANTED-CC-0007",
            "mutation",
            "Planted duplicate CC-0007 across two scratch slices must be detected with both paths named.",
            True,
            True,
            bad=json.dumps(p8["collision_control"]["duplicate_ids"]),
            good="live corpus duplicate_id_count=0",
        )
    ]
    d8 = [
        {
            "id": "CC-0008-D1",
            "severity": "P1",
            "status": "open",
            "summary": (
                f"Catalog shortfall {p8['readback']['shortfall_vs_floor']} vs 2048 floor "
                f"(read-back {p8['readback']['work_units_read_back']})."
            ),
        },
        {
            "id": "CC-0008-D2",
            "severity": "P0",
            "status": "open",
            "summary": (
                "do_merge does not refuse colliding ids; collision gate is detector-only."
            ),
        },
        {
            "id": "CC-0008-D3",
            "severity": "P1",
            "status": "open",
            "summary": (
                "No first-class prefix→bucket allocation table; "
                f"{p8['slice_audit']['missing_bucket_field']} units missing bucket."
            ),
        },
    ]
    r8 = _base_receipt(
        "CC-0008",
        "command-center/schema/receipt.schema.json",
        "Scale the catalog to the 2,048-unit program",
        "command-center/p2-wave/probes/CC-0008",
        p8,
        e8,
        t8,
        c8,
        d8,
    )

    # CC-0014
    raw14 = (
        L.REPO / "command-center/p2-wave/probes/CC-0014/probe-results.raw.txt"
    ).read_text(encoding="utf-8")
    e14 = [
        L.evidence(
            (
                "TEST-REGISTRY.json has suites/invariants with narrative red_proof but "
                "no PROTECTING/UNPROVEN status machine and no mutation_record fields."
            ),
            "CONFIRMED",
            "command-center/TEST-REGISTRY.json",
            [
                L.probe(
                    "source",
                    "file-read",
                    "inspect TEST-REGISTRY.json structure",
                    raw14,
                    0,
                ),
                L.probe(
                    "verifier",
                    "static-analysis",
                    "token scan PROTECTING/UNPROVEN/mutation_record",
                    json.dumps(p14["test_registry"], indent=2),
                    0,
                ),
            ],
            "almost-certain",
        ),
        L.evidence(
            (
                "No binder API assigns UNPROVEN without mutation or PROTECTING after a "
                "failing mutation; aggregation cannot credit coverage."
            ),
            "CONFIRMED",
            "command-center/p2-wave/probes/CC-0014/probe-results.json",
            [
                L.probe(
                    "source",
                    "static-analysis",
                    "search binder API paths",
                    json.dumps(p14["binding_api"], indent=2),
                    0,
                ),
                L.probe(
                    "verifier",
                    "static-analysis",
                    "controls matrix",
                    json.dumps(p14["controls"], indent=2)[:8000],
                    0,
                ),
            ],
            "almost-certain",
        ),
    ]
    t14 = [
        {
            "id": "T-UNPROVEN",
            "name": "Register a test with no mutation record -> status must be UNPROVEN",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 1,
            "output_tail": "status machine NOT-IMPLEMENTED",
        },
        {
            "id": "T-PROTECTING",
            "name": "Supply a mutation that made the test fail -> status PROTECTING",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 1,
            "output_tail": "NOT-IMPLEMENTED",
        },
        {
            "id": "T-HOLE",
            "name": "Supply a mutation that SURVIVED -> registry reports a hole",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 1,
            "output_tail": "NOT-IMPLEMENTED",
        },
        {
            "id": "T-AGG",
            "name": "All-UNPROVEN registry must report 0 protected claims",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "PASS",
            "assertions": 1,
            "output_tail": "proxy: protecting_count=0 so no false 100%",
        },
    ]
    c14 = [
        L.control(
            "NC-NO-MUTATION-CREDIT",
            "absent-input",
            "Entries without mutation_record must not count as PROTECTING coverage.",
            True,
            True,
            bad="would-be PROTECTING without mutation",
            good="measured protecting_count=0 under current registry",
        )
    ]
    d14 = [
        {
            "id": "CC-0014-D1",
            "severity": "P0",
            "status": "open",
            "summary": (
                "TEST-REGISTRY lacks PROTECTING/UNPROVEN/mutation_record contract "
                "required to bind tests to claims to units."
            ),
        }
    ]
    r14 = _base_receipt(
        "CC-0014",
        "command-center/schema/test-registry-entry.schema.json",
        "Bind tests to claims to units",
        "command-center/p2-wave/probes/CC-0014",
        p14,
        e14,
        t14,
        c14,
        d14,
    )

    # CC-0012
    raw12 = (
        L.REPO / "command-center/p2-wave/probes/CC-0012/probe-results.raw.txt"
    ).read_text(encoding="utf-8")
    e12 = [
        L.evidence(
            (
                "No freeze flag with recorded activation commit SHA/timestamp is present "
                "in this tree."
            ),
            "CONFIRMED",
            "command-center/p2-wave/probes/CC-0012/probe-results.json",
            [
                L.probe(
                    "source",
                    "file-read",
                    "search FREEZE.json / freeze-anchor / activation commit",
                    raw12,
                    0,
                ),
                L.probe(
                    "verifier",
                    "static-analysis",
                    "candidate path existence matrix",
                    json.dumps(p12["freeze_marker_candidates"], indent=2),
                    0,
                ),
            ],
            "almost-certain",
        ),
        L.evidence(
            (
                "AUD-0095 freeze inventory exists (state=BLOCKED) but its freeze_check.py "
                "probe tree is absent; migration dirs empty/absent; IMP-0477/TST-0026 "
                "receipts absent."
            ),
            "CONFIRMED",
            "command-center/audit/AUD-0095-freeze-inventory.json",
            [
                L.probe(
                    "source",
                    "file-read",
                    "AUD-0095 state + freeze_check presence",
                    json.dumps(
                        {
                            "activation": p12["activation"],
                            "related": p12["related_units"],
                            "gates": p12["gate_candidates"],
                            "migrations": p12["migration_dirs"],
                        },
                        indent=2,
                    ),
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "stat command-center/p2-wave/probes/AUD-0095/freeze_check.py",
                    f"exists={p12['activation']['freeze_check_py_present']}",
                    0,
                ),
            ],
            "almost-certain",
        ),
    ]
    t12 = [
        {
            "id": "T-MUT-NO-BUMP",
            "name": "Mutation: change a frozen schema without a version bump -> gate red.",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 1,
            "output_tail": "gate absent; NOT-RUN",
        },
        {
            "id": "T-POS-MIGRATE",
            "name": "Positive: change with bump + migration + round-trip -> gate green.",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 1,
            "output_tail": "migration engine absent",
        },
        {
            "id": "T-ROUNDTRIP",
            "name": "Round-trip: migrate forward then back on real data -> byte-identical.",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 1,
            "output_tail": "NOT-RUN",
        },
        {
            "id": "T-BOTH-STATES",
            "name": "Both-states: gate silent on a non-frozen file.",
            "command": "python3 command-center/p2-wave/_build_CC0008_CC0014_CC0012.py",
            "result": "FAIL",
            "assertions": 1,
            "output_tail": "gate absent",
        },
    ]
    c12 = [
        L.control(
            "NC-FREEZE-MARKER-ABSENT",
            "absent-input",
            "Freeze activation artifact must exist before SUCCESS; absence keeps unit BLOCKED.",
            True,
            True,
            bad="freeze flag missing",
            good="would require FREEZE.json with activation commit",
        )
    ]
    d12 = [
        {
            "id": "CC-0012-D1",
            "severity": "P0",
            "status": "open",
            "summary": (
                "Freeze flag + activation commit + migration round-trip gate not shipped; "
                "AUD-0095 probe executables missing from tree."
            ),
        }
    ]
    r12 = _base_receipt(
        "CC-0012",
        "command-center/schema/receipt.schema.json",
        "Freeze the schemas and launchers",
        "command-center/p2-wave/probes/CC-0012",
        p12,
        e12,
        t12,
        c12,
        d12,
    )

    return [
        ("CC-0008", "command-center/receipts/CC-0008.json", r8),
        ("CC-0014", "command-center/receipts/CC-0014.json", r14),
        ("CC-0012", "command-center/receipts/CC-0012.json", r12),
    ]


def main() -> int:
    rows = build_all()
    # Validate then atomic-write
    worst = 0
    for unit, rel, doc in rows:
        # CC-0014 uses test-registry-entry schema (generic_report profile)
        schema = {
            "CC-0008": "command-center/schema/receipt.schema.json",
            "CC-0014": "command-center/schema/test-registry-entry.schema.json",
            "CC-0012": "command-center/schema/receipt.schema.json",
        }[unit]
        errs = L.validate(doc, schema)
        # Also validate against receipt.schema for CC-0014 since it's a receipt-shaped report
        if unit == "CC-0014":
            errs += [
                f"[receipt] {e}"
                for e in L.validate(doc, "command-center/schema/receipt.schema.json")
            ]
        if errs:
            print(f"FAILED:{unit} schema errors:")
            for e in errs[:40]:
                print("  ", e)
            worst = 1
            continue
        # Attach self artifact path after size known — write first then remeasure
        ar.write_json_atomic(L.REPO / rel, doc)
        # Re-read and append self art if needed
        back = ar.read_json(L.REPO / rel)
        # Update artifacts with self receipt measurement
        self_art = L.art(rel, "primary")
        # replace or append
        arts = [a for a in back.get("artifacts", []) if a.get("path") != rel]
        arts.append(self_art)
        back["artifacts"] = arts
        # re-validate
        errs2 = L.validate(back, schema)
        if unit == "CC-0014":
            errs2 += [
                f"[receipt] {e}"
                for e in L.validate(back, "command-center/schema/receipt.schema.json")
            ]
        if errs2:
            print(f"FAILED:{unit} post-self-art schema errors:")
            for e in errs2[:40]:
                print("  ", e)
            worst = 1
            continue
        ar.write_json_atomic(L.REPO / rel, back)
        size = (L.REPO / rel).stat().st_size
        print(f"WROTE:{unit} {rel} ({size} B) state={back['state']}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
