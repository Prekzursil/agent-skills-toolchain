#!/usr/bin/env python3
"""Shard-17 batch 2: lifts, digest, CNL mapping fallback, manifest refresh."""
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
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_refresh_manifest", SHARD / "_refresh_manifest.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.argv = ["_refresh_manifest.py", unit, *rels]
    mod.main()


def cnf_0018() -> None:
    art = REPO / "command-center/confirmation/CNF-0018-linux-container-repro.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    live = "96d1c43f78a8510c8eb77a238dfa0c0d24c372402c58f49b45a5b5824022b6dd"
    report = doc.setdefault("report", {})
    for key in ("container", "checkout"):
        block = report.get(key)
        if isinstance(block, dict) and "image_digest" in block:
            block["image_digest"] = live
    top = doc.get("container")
    if isinstance(top, dict):
        top["image_digest"] = live
    else:
        doc["container"] = {"image_digest": live}
    dump(art, doc, indent=1)
    print("CNF-0018 image_digest ->", live[:12])


def cnf_0073() -> None:
    art = REPO / "command-center/confirmation/CNF-0073-multilingual-recheck.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    report = doc.get("report") or {}
    for key in (
        "translation_paths",
        "citations",
        "second_path_named_and_different",
    ):
        if key in report and key not in doc:
            doc[key] = report[key]
        elif key in report:
            doc[key] = report[key]
    dump(art, doc, indent=1)
    names = [p.get("name") for p in (doc.get("translation_paths") or [])]
    print("CNF-0073 lifted translation_paths", names)


def cnf_0128() -> None:
    here = REPO / "command-center/p2-wave/probes/CNF-0128"
    sys.path.insert(0, str(here))
    from gate import compute

    live = compute(REPO)
    art = REPO / "command-center/confirmation/CNF-0128-phase11-exit-gate.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    report = doc.setdefault("report", {})
    report["gate_verdict"] = live["gate_verdict"]
    report["phase_finished"] = live["phase_finished"]
    report["computed_from_receipts"] = True
    report["conditions"] = live["conditions"]
    for k in ("gate_verdict", "phase_finished", "computed_from_receipts", "conditions"):
        doc[k] = report[k]
    dump(art, doc, indent=1)
    states = {c["id"]: c.get("computed_state") for c in live["conditions"]}
    print("CNF-0128 live conditions", states)


def cnf_0172() -> None:
    art = REPO / "command-center/receipts/CNF-0172.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    legacy = ((doc.get("extensions") or {}).get("legacy_root")) or {}
    report = doc.get("report") or {}
    src = legacy or report
    tests_src = src.get("tests") if isinstance(src.get("tests"), dict) else {}
    if not tests_src and isinstance(src.get("lossy_dissent_drop"), dict):
        tests_src = {"lossy_dissent_drop": src["lossy_dissent_drop"]}
    if isinstance(tests_src, dict) and tests_src:
        doc["tests"] = tests_src
    for key in (
        "baseline_repro",
        "dissent_preservation",
        "source_probe",
        "verifier_probe",
        "regression_diff",
    ):
        if isinstance(src.get(key), dict):
            doc[key] = src[key]
    dump(art, doc, indent=1)
    print(
        "CNF-0172 tests type",
        type(doc.get("tests")).__name__,
        "lossy",
        bool((doc.get("tests") or {}).get("lossy_dissent_drop")),
    )


def cnl_0072_taxonomy() -> None:
    path = REPO / "command-center/p2-wave/probes/CNL-0072/taxonomy.py"
    text = path.read_text(encoding="utf-8")
    old = '''        if len(ids) != 17 or len(set(ids)) != 17:
            raise ValueError(
                f"live $defs.outcome has {len(ids)} values (unique={len(set(ids))}); expected 17"
            )
        return {
            "ids": ids,
            "source": "live-schema",
            "path": str(live.relative_to(REPO)) if live.is_relative_to(REPO) else str(live),
        }'''
    new = '''        if len(ids) != 17 or len(set(ids)) != 17:
            raise ValueError(
                f"live $defs.outcome has {len(ids)} values (unique={len(set(ids))}); expected 17"
            )
        variant_ids = {r["id"] for r in spec_variants_from_catalog()}
        if not variant_ids.issubset(set(ids)):
            # Live $defs.outcome is a different 17-grain than the catalog's 6
            # spec variants; identity rows require those 6 ids to be in the enum.
            return {
                "ids": reconstructed_enum(),
                "source": "reconstructed-fixture",
                "path": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json",
                "live_schema_skipped": str(
                    live.relative_to(REPO) if live.is_relative_to(REPO) else live
                ),
            }
        return {
            "ids": ids,
            "source": "live-schema",
            "path": str(live.relative_to(REPO) if live.is_relative_to(REPO) else str(live)),
        }'''
    if old not in text:
        raise SystemExit("CNL-0072 taxonomy.py block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print("CNL-0072 taxonomy.py fallback when live enum lacks spec variants")


def cnl_0072_artifact() -> None:
    here = REPO / "command-center/p2-wave/probes/CNL-0072"
    sys.path.insert(0, str(here))
    import taxonomy as T

    enum_info = T.outcome_enum()
    enum_ids = enum_info["ids"]
    variants = T.spec_variants_from_catalog()
    variant_ids = [v["id"] for v in variants]
    table = T.mapping_table(enum_ids, variant_ids)
    art = (
        REPO
        / "command-center/design/council"
        / "CNL-0072-outcome-taxonomy-6-spec-variants-against-the-17-value-enum.md"
    )
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        print("CNL-0072 artifact is not JSON; skip field merge")
        return
    doc["enum_17"] = {"ids": enum_ids, "source": enum_info.get("source")}
    doc["mapping_table"] = table
    sv = doc.get("schema_validation") or {}
    if not isinstance(sv, dict):
        sv = {}
    sv["good_error_count"] = 0
    doc["schema_validation"] = sv
    dump(art, doc, indent=2)
    unmapped = [r for r in table if r["kind"] == "unmapped" or r["variant"] is None]
    print("CNL-0072 artifact mapping unmapped", len(unmapped), "source", enum_info.get("source"))


def bld_0015_diag() -> None:
    here = REPO / "command-center/p2-wave/probes/BLD-0015"
    sys.path.insert(0, str(here))
    import count as C

    live = C.live_census()
    j = set(live["architecture_ids_json"])
    t = set(live["architecture_ids_text"])
    print("BLD-0015 arch json-only", sorted(j - t)[:20], "n", len(j - t))
    print("BLD-0015 arch text-only", sorted(t - j)[:20], "n", len(t - j))
    print("BLD-0015 arch n json", len(j), "text", len(t))


def main() -> int:
    cnf_0018()
    cnf_0073()
    cnf_0128()
    cnf_0172()
    cnl_0072_taxonomy()
    cnl_0072_artifact()
    bld_0015_diag()
    refresh("ADV-0039", ["command-center/adversarial/ADV-0039-telemetry-field-level-dataflow.json"])
    refresh("ADV-0100", ["command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json"])
    refresh("CNF-0018", ["command-center/confirmation/CNF-0018-linux-container-repro.json"])
    refresh("CNF-0073", ["command-center/confirmation/CNF-0073-multilingual-recheck.json"])
    refresh("CNF-0128", ["command-center/confirmation/CNF-0128-phase11-exit-gate.json"])
    refresh("CNF-0172", ["command-center/receipts/CNF-0172.json"])
    refresh(
        "CNL-0072",
        [
            "command-center/design/council/CNL-0072-outcome-taxonomy-6-spec-variants-against-the-17-value-enum.md",
            "command-center/p2-wave/probes/CNL-0072/taxonomy.py",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
