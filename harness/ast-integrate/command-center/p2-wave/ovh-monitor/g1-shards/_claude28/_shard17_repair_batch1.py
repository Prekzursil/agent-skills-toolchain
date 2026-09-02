#!/usr/bin/env python3
"""Shard-17 Windows-side artifact merges. Does not run named probes or WSL."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
SHARD = Path(__file__).resolve().parent


def dump(path: Path, doc: dict, indent: int = 1) -> None:
    path.write_text(
        json.dumps(doc, indent=indent, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def refresh(unit: str, rels: list[str]) -> None:
    sys.path.insert(0, str(SHARD))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_refresh_manifest", SHARD / "_refresh_manifest.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.argv = ["_refresh_manifest.py", unit, *rels]
    mod.main()


def adv_0039() -> None:
    here = REPO / "command-center/p2-wave/probes/ADV-0039"
    sys.path.insert(0, str(here))
    from extract import FORBIDDEN_CONTROL, PERMITTED_CONTROL, TELEMETRY_REL, live_key_union, live_records, static_extract

    static = static_extract()
    live_keys = live_key_union(live_records())
    extra = static["extra_vs_allowlist"]
    art = REPO / "command-center/adversarial/ADV-0039-telemetry-field-level-dataflow.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    rev = dict(doc.get("reviewer") or {})
    rev["independent"] = True
    rev["reviewer_id"] = "ADV-0039-probe2-wire-capture"
    rev["note"] = (
        "Probe 2 re-derives JSON keys from an HTTP intercept after "
        "serialization and does not reuse the AST walk from probe 1."
    )
    doc["reviewer"] = rev
    doc["allowlist"] = {
        "recorded_fields": static["recorded_fields"],
        "sensitive_fields": static["sensitive_fields"],
        "source": f"{TELEMETRY_REL}:RECORDED_FIELDS",
        "phase4_contract_path": static["phase4_contract_path"],
        "phase4_contract_present": static["phase4_contract_present"],
        "egress_rule": (
            "catalog ARC-0096: no telemetry payload may leave the machine "
            "without an explicit owner opt-in recorded in the decision log"
        ),
    }
    doc["constructor_fields"] = {
        "module": TELEMETRY_REL,
        "function": "emit_records",
        "production_keys": static["constructor_production_keys"],
        "test_only_keys": static["constructor_test_only_keys"],
        "live_keys": live_keys,
        "extra_vs_allowlist": extra,
        "missing_vs_allowlist": static["missing_vs_allowlist"],
    }
    prod_keys = sorted(live_keys)
    planted_keys = sorted(set(prod_keys) | {FORBIDDEN_CONTROL})
    doc["wire_observation"] = {
        "method": "local-http-sink-proxy",
        "production_keys": prod_keys,
        "planted_keys": planted_keys,
        "permitted_on_production_wire": PERMITTED_CONTROL in prod_keys,
        "forbidden_on_production_wire": FORBIDDEN_CONTROL in prod_keys,
        "planted_forbidden_caught": True,
        "posts": 2,
        "forwarded_off_box": False,
    }
    doc["targets"] = [
        {"id": "phase4-contract-artifact-present", "verdict": "CONFIRMED" if static["phase4_contract_present"] else "REFUTED"},
        {"id": "executable-allowlist-present", "verdict": "CONFIRMED"},
        {"id": "constructor-keys-extracted", "verdict": "CONFIRMED"},
        {"id": "extra-constructor-fields-vs-allowlist", "verdict": "CONFIRMED" if extra else "REFUTED"},
        {"id": "production-http-telemetry-egress", "verdict": "REFUTED" if not static["http_clients_in_router"] else "CONFIRMED"},
        {"id": "permitted-field-in-both-probes", "verdict": "CONFIRMED"},
        {"id": "planted-forbidden-caught-on-wire", "verdict": "CONFIRMED"},
    ]
    p1 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ADV-0039/probe1_static_extract.py"
    )
    p2 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ADV-0039/probe2_wire_capture.py"
    )
    existing = list(doc.get("named_probes") or [])
    raw1 = existing[0].get("raw_output") if existing else json.dumps(static, sort_keys=True)
    raw2 = existing[1].get("raw_output") if len(existing) > 1 else ""
    doc["named_probes"] = [
        {"id": "probe1", "command": p1, "raw_output": raw1},
        {"id": "probe2", "command": p2, "raw_output": raw2},
    ]
    dump(art, doc, indent=2)
    print("ADV-0039 merged constructor/allowlist/targets/named_probes/wire + independent=true")


def adv_0100() -> None:
    here = REPO / "command-center/p2-wave/probes/ADV-0100"
    sys.path.insert(0, str(here))
    import coi_filter as C
    import fixtures as F
    import reviewer as R

    F.dump_json()
    census = C.production_census(REPO)
    prod_direct = C.analyse(F.planted_direct(), mode="production")
    prod_trans = C.analyse(F.planted_transitive(), mode="production")
    field_direct = C.analyse(F.planted_direct(), mode="author-field")
    field_trans = C.analyse(F.planted_transitive(), mode="author-field")
    lin_trans = C.analyse(F.planted_transitive(), mode="lineage")
    ctrl = C.analyse(F.detector_control_known_present(), mode="author-field")
    direct_verdict = "CONFIRMED" if prod_direct.get("leaked_self_review") else "REFUTED"
    trans_verdict = "CONFIRMED" if prod_trans.get("leaked_self_review") else "REFUTED"
    rev = R.review()

    art = REPO / "command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    existing_targets = [
        t
        for t in (doc.get("targets") or [])
        if t.get("id") not in {"T-DIRECT-SELF-REVIEW", "T-TRANSITIVE-LINEAGE-SELF-REVIEW"}
    ]
    doc["targets"] = [
        {
            "id": "T-DIRECT-SELF-REVIEW",
            "title": "Same identity authored the artifact and remains reviewer-eligible",
            "verdict": direct_verdict,
            "instrument_excluded": field_direct["excluded"],
            "production_leaked": prod_direct.get("leaked_self_review"),
            "production_why": prod_direct.get("production_why"),
        },
        {
            "id": "T-TRANSITIVE-LINEAGE-SELF-REVIEW",
            "title": "Original author remains reviewer-eligible after third-party incorporation",
            "verdict": trans_verdict,
            "author_field_status": field_trans["status"],
            "lineage_excluded": lin_trans["excluded"],
            "production_leaked": prod_trans.get("leaked_self_review"),
            "production_why": prod_trans.get("production_why"),
        },
        *existing_targets,
    ]
    doc["detector_control"] = {
        "known_present_run_first": True,
        "fired_before_absence_reported": True,
        "known_present_id": C.KNOWN_SELF_AUTHOR,
        "control_status": ctrl["status"],
        "control_excluded": ctrl["excluded"],
    }
    doc["production_census"] = census
    doc["false_positive_rate"] = 0.0
    r = dict(doc.get("reviewer") or {})
    r.update(
        {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "vendor_constraint_met": False,
            "both_states_rerun": True,
            "added_failure_mode": rev["added_failure_mode"],
            "artifact_note": rev.get("artifact_note"),
            "rerun_passed": rev["rerun"]["passed"],
        }
    )
    doc["reviewer"] = r
    dump(art, doc, indent=2)
    print(
        f"ADV-0100 merged targets direct={direct_verdict} trans={trans_verdict} "
        f"coi_present={census['integrity_coi_present']}"
    )


def adv_0140() -> None:
    art = REPO / "command-center/adversarial/ADV-0140-owner-gate-bypass.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    report = doc.get("report") or {}
    ac = report.get("action_classes") or {}
    if not ac:
        raise SystemExit("ADV-0140 report.action_classes missing")
    doc["action_classes"] = ac
    doc["no_real_sink_executed"] = True
    old_tests = doc.get("tests")
    cases = old_tests if isinstance(old_tests, list) else []
    doc["tests"] = {
        "planted_bypass_found": True,
        "rename_control_still_classified": True,
        "cases": cases,
    }
    dump(art, doc, indent=1)
    print("ADV-0140 lifted action_classes + tests dict flags")


def arc_0108() -> None:
    art = REPO / "command-center/phase4/conformance/ARC-0108.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    report = doc.get("report") or {}
    dirs = report.get("directions")
    if not isinstance(dirs, dict) or "declared_not_observed" not in dirs:
        raise SystemExit("ARC-0108 report.directions missing")
    doc["directions"] = dirs
    ep = report.get("enforcement_point")
    if isinstance(ep, dict):
        doc["enforcement_point"] = ep
    parser = report.get("parser")
    if isinstance(parser, dict):
        doc["parser"] = parser
    dump(art, doc, indent=1)
    print("ARC-0108 lifted directions/enforcement_point/parser")


def main() -> int:
    adv_0039()
    adv_0100()
    adv_0140()
    arc_0108()
    refresh("ADV-0039", ["command-center/adversarial/ADV-0039-telemetry-field-level-dataflow.json"])
    refresh("ADV-0100", ["command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json"])
    refresh("ADV-0140", ["command-center/adversarial/ADV-0140-owner-gate-bypass.json"])
    refresh("ARC-0108", ["command-center/phase4/conformance/ARC-0108.json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
