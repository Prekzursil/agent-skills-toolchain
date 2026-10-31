"""Write and verify the PHASE-2C council protocol blueprints P25-P36.

    python platform/lib/council_protocols/build.py build     # write the 12 JSON files
    python platform/lib/council_protocols/build.py verify    # validate + probe what is ON DISK
    python platform/lib/council_protocols/build.py all       # build then verify

`verify` re-reads every file from disk and runs, per file:

1. the sibling CouncilSpec validator (JSON Schema draft 2020-12 + SEM-001..SEM-012),
2. source_expression -> tree identity and unparse/parse tree-idempotency,
3. a BOTH-STATES control on the stopping rule and on every stage exit condition: a snapshot
   that satisfies it and a snapshot that does not, computed by exhaustive polarity search
   rather than assumed,
4. a leaf-necessity mutation: every leaf of a conjunctive rule must be load-bearing,
5. the lane's own content floors - >= 3 declared anti_failure controls, a non-empty
   fast_unanimity_response, a declared topology / speaking order / rounds / obligations /
   quotas / voting method,
6. drift between the on-disk bytes and a fresh regeneration.

Terminal state per AGENTS.md section 4: the last line is SUCCESS:<id> or FAILED:<id> <reason>.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLATFORM = os.path.dirname(_LIB)
_REPO = os.path.dirname(_PLATFORM)
if _LIB not in sys.path:  # so the package imports resolve when run as a plain script
    sys.path.insert(0, _LIB)

from council_protocols._shared import PRODUCERS, missing_producers  # noqa: E402
from council_protocols.analysis import all_trees, analyse  # noqa: E402
from council_protocols.protocols_25_30 import PROTOCOLS_25_30  # noqa: E402
from council_protocols.protocols_31_36 import PROTOCOLS_31_36  # noqa: E402
from councilspec.expression import parse, unparse  # noqa: E402
from councilspec.validate import validate_file  # noqa: E402

BUILDERS = PROTOCOLS_25_30 + PROTOCOLS_31_36
OUT_DIR = os.path.join(_PLATFORM, "council", "protocols")
REPORT = os.path.join(_PLATFORM, "council", "PROTOCOLS-25-36-VALIDATION.json")
EXPECTED = 12
MIN_ANTI_FAILURE_CONTROLS = 3

# The lane brief's control vocabulary. Every protocol must declare >= 3 of these.
# Kept byte-identical to the `mandated_controls` list the sibling lane build/proto-2 (P13-P24)
# wrote into platform/council/protocols/PROTOCOL-EXPECTATIONS.json, so the two lanes are scored
# against ONE vocabulary and can be merged mechanically. moderator_capture is that list's
# rendering of the brief's "sycophancy toward the chair".
BRIEF_CONTROLS = {
    "circular_debate",
    "echo_chamber",
    "endless_debate",
    "evidence_free_majority",
    "idea_count_gaming",
    "lost_dissent",
    "missing_expertise",
    "moderator_capture",
    "participant_dominance",
    "premature_convergence",
    "role_collapse",
    "silence",
    "strategic_voting",
    "sycophancy",
    "weak_synthesis",
}

# This lane owns exactly these ids in the shared protocols directory; P01-P24 and P37-P48
# belong to sibling lanes and must be reported as context, never as this lane's failure.
LANE_IDS = tuple(f"p{n}-" for n in range(25, 37))


def _spec_name(spec: Mapping[str, Any]) -> str:
    return f"{spec['council_id']}.councilspec.json"


def _dumps(spec: Mapping[str, Any]) -> str:
    return json.dumps(spec, indent=2, ensure_ascii=True) + "\n"


def do_build() -> List[str]:
    os.makedirs(OUT_DIR, exist_ok=True)
    written = []
    for builder in BUILDERS:
        spec = builder()
        path = os.path.join(OUT_DIR, _spec_name(spec))
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(_dumps(spec))
        written.append(path)
        print(f"wrote {os.path.relpath(path, _REPO)}")
    print(
        f"-- {len(written)} protocol files written to {os.path.relpath(OUT_DIR, _REPO)}"
    )
    return written


def _content_floors(spec: Mapping[str, Any]) -> Dict[str, Any]:
    protocol = spec.get("protocol") or {}
    anti = spec.get("anti_failure") or {}
    controls = list(anti.get("controls") or [])
    obligations = protocol.get("obligations") or {}
    quota_stages = [
        s.get("stage_id")
        for s in protocol.get("sequence") or []
        if isinstance(s, Mapping) and s.get("quotas")
    ]
    quota_keys = sorted(
        {
            k
            for s in protocol.get("sequence") or []
            if isinstance(s, Mapping)
            for k in (s.get("quotas") or {})
        }
    )
    targets = spec.get("targets") or {}
    fails = []
    brief_controls = sorted(set(controls) & BRIEF_CONTROLS)
    if len(brief_controls) < MIN_ANTI_FAILURE_CONTROLS:
        fails.append(
            f"only {len(brief_controls)} of the brief's named controls declared "
            f"(floor {MIN_ANTI_FAILURE_CONTROLS}): {brief_controls}"
        )
    if not anti.get("fast_unanimity_response"):
        fails.append(
            "no anti_failure.fast_unanimity_response - fast unanimity triggers nothing"
        )
    if not (spec.get("consensus") or {}).get("fast_unanimity_is_suspicious"):
        fails.append("consensus.fast_unanimity_is_suspicious is not true")
    if not (spec.get("topology") or {}).get("kind"):
        fails.append("no topology.kind")
    if not protocol.get("speaking_order"):
        fails.append("no protocol.speaking_order")
    if not protocol.get("rounds"):
        fails.append("no protocol.rounds")
    if not obligations:
        fails.append("no protocol.obligations (response obligations undeclared)")
    for key in ("steelman_before_rebuttal", "rebuttal_required", "cross_examination"):
        if key not in obligations:
            fails.append(
                f"obligations.{key} is undeclared (must be explicitly true or false)"
            )
    if not quota_stages:
        fails.append("no stage declares quotas (idea/novelty quotas undeclared)")
    if not any(
        k in quota_keys for k in ("ideas_per_participant", "novel_ideas_per_round")
    ):
        fails.append(f"no idea/novelty quota among stage quotas: {quota_keys}")
    if "novelty_ratio" not in targets or "dedup" not in targets:
        fails.append(
            "targets is missing novelty_ratio and/or dedup (novelty gaming ungated)"
        )
    if not (spec.get("voting") or {}).get("method"):
        fails.append("no voting.method")
    return {
        "ok": not fails,
        "failures": fails,
        "brief_controls_declared": brief_controls,
        "controls_total": len(controls),
        "fast_unanimity_response": list(anti.get("fast_unanimity_response") or []),
        "quota_stages": quota_stages,
        "quota_keys": quota_keys,
    }


def do_verify() -> Dict[str, Any]:
    on_disk = (
        sorted(f for f in os.listdir(OUT_DIR) if f.endswith(".json"))
        if os.path.isdir(OUT_DIR)
        else []
    )
    expected_names = [_spec_name(b()) for b in BUILDERS]
    missing = [n for n in expected_names if n not in on_disk]
    # Lane-scoped: a stray p25..p36 file this lane did not author is a real problem; a sibling
    # lane's P13-P24 / P37-P48 file in the shared directory is not.
    unexpected = [
        n for n in on_disk if n not in expected_names and n.lower().startswith(LANE_IDS)
    ]
    sibling_files = [
        n
        for n in on_disk
        if n not in expected_names and not n.lower().startswith(LANE_IDS)
    ]

    per_file: List[Dict[str, Any]] = []
    hard_fail: List[str] = []

    for builder in BUILDERS:
        regenerated = builder()
        name = _spec_name(regenerated)
        path = os.path.join(OUT_DIR, name)
        entry: Dict[str, Any] = {"file": f"platform/council/protocols/{name}"}
        if not os.path.isfile(path):
            entry.update({"exists": False, "schema_ok": False, "verdict": "MISSING"})
            per_file.append(entry)
            hard_fail.append(f"{name}: absent from disk")
            continue

        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        spec = json.loads(raw)
        res = validate_file(path)

        entry["exists"] = True
        entry["bytes"] = len(raw.encode("utf-8"))
        entry["council_id"] = spec.get("council_id")
        entry["title"] = (spec.get("metadata") or {}).get("title")
        entry["schema_ok"] = res["schema_ok"]
        entry["schema_errors"] = res["schema_errors"]
        entry["semantic_errors"] = res["semantic_errors"]
        entry["warnings"] = res["warnings"]
        entry["validator_ok"] = res["ok"]
        entry["drift_vs_regeneration"] = raw != _dumps(regenerated)

        # source_expression identity + tree idempotency
        stopping = spec.get("stopping") or {}
        src, tree = stopping.get("source_expression"), stopping.get("expression")
        rt: Dict[str, Any] = {"source_expression": src}
        if src and isinstance(tree, Mapping):
            rt["source_parses_to_expression"] = parse(src) == tree
            rt["unparse_parse_idempotent"] = parse(unparse(tree)) == tree
            rt["canonical_form"] = unparse(tree)
        entry["roundtrip"] = rt

        # both-states + leaf necessity, per tree
        trees = []
        for tpath, ttree in all_trees(spec):
            a = analyse(ttree)
            a["path"] = tpath
            a["expression"] = unparse(ttree)
            conjunctive = a["root"] == "all_of"
            a["all_leaves_load_bearing"] = (
                a["load_bearing"] == a["leaves"] if conjunctive else None
            )
            trees.append(a)
        entry["trees"] = trees
        entry["trees_checked"] = len(trees)
        entry["both_states_ok"] = all(
            t["satisfiable"] and t["falsifiable"] for t in trees
        )

        # SEM-012's substance without SEM-012's field: every custom metric must name what would
        # compute it. See _shared.expr for why the producer cannot live in the JSON leaf.
        uncovered: set = set()
        for _tpath, ttree in all_trees(spec):
            uncovered |= missing_producers(ttree)
        entry["custom_metrics_without_producer"] = sorted(uncovered)

        floors = _content_floors(spec)
        entry["content_floors"] = floors

        problems = []
        if not res["ok"]:
            problems.append("validator rejected")
        if rt.get("source_parses_to_expression") is False:
            problems.append("source_expression does not parse to expression")
        if rt.get("unparse_parse_idempotent") is False:
            problems.append("unparse/parse not tree-idempotent")
        if not entry["both_states_ok"]:
            problems.append(
                "a stopping/exit expression is not both satisfiable and falsifiable"
            )
        for t in trees:
            if t["duplicate_metrics"]:
                problems.append(
                    f"{t['path']} repeats metric(s) {t['duplicate_metrics']}"
                )
            if t["all_leaves_load_bearing"] is False:
                problems.append(
                    f"{t['path']} has decorative leaf/leaves (survivors {t['survivors']})"
                )
        problems.extend(floors["failures"])
        if uncovered:
            problems.append(f"custom metric(s) name no producer: {sorted(uncovered)}")
        if entry["drift_vs_regeneration"]:
            problems.append("on-disk bytes differ from a fresh regeneration")

        entry["problems"] = problems
        entry["verdict"] = "PASS" if not problems else "FAIL"
        if problems:
            hard_fail.append(f"{name}: {problems[0]}")
        per_file.append(entry)

        status = entry["verdict"]
        print(f"{status:4}  {name}")
        print(
            f"      schema_ok={entry['schema_ok']} semantic_errors={len(entry['semantic_errors'])} "
            f"warnings={len(entry['warnings'])} trees={entry['trees_checked']} "
            f"both_states={entry['both_states_ok']} "
            f"controls={len(floors['brief_controls_declared'])}/{floors['controls_total']}"
        )
        for t in trees:
            lb = t["load_bearing"]
            print(
                f"      [{t['root']}] {t['path']}: leaves={t['leaves']} load_bearing={lb} "
                f"sat={t['satisfiable']} unsat={t['falsifiable']}"
            )
        for msg in entry["schema_errors"] + entry["semantic_errors"]:
            print(f"      REJECT {msg}")
        for msg in problems:
            print(f"      PROBLEM {msg}")

    passed = sum(1 for e in per_file if e["verdict"] == "PASS")
    report = {
        "unit": "build/proto-3",
        "lane": "PHASE 2C - council protocol blueprints 25-36 of 48",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": "platform/schema/councilspec.schema.json",
        "validator": "platform/lib/councilspec/validate.py (JSON Schema 2020-12 + SEM-001..SEM-012)",
        "output_dir": "platform/council/protocols",
        "protocols_expected": EXPECTED,
        "protocols_on_disk": len(on_disk),
        "protocols_pass": passed,
        "protocols_fail": len(per_file) - passed,
        "missing_files": missing,
        "unexpected_lane_files": unexpected,
        "shared_dir_note": (
            f"{len(sibling_files)} file(s) in platform/council/protocols belong to sibling lanes "
            "(P01-P24, P37-P48 and their manifests). This lane neither validates nor touches them."
        ),
        "sibling_lane_files": sibling_files,
        "trees_checked": sum(e.get("trees_checked", 0) for e in per_file),
        "known_substrate_defect": (
            "Every unit's output_schema names command-center/schema/receipt.schema.json, which "
            "does not exist; these protocols point outputs.receipt_schema at the file this wave "
            "actually shipped, platform/schema/receipt.schema.json. No deploy mapping exists yet."
        ),
        "per_file": per_file,
        "status": "PASS"
        if not (hard_fail or missing) and passed == EXPECTED
        else "FAIL",
    }
    with open(REPORT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")

    _write_lane_manifest(per_file)

    print(
        f"-- {passed}/{EXPECTED} protocols pass; {report['trees_checked']} expression trees probed"
    )
    print(f"-- report: {os.path.relpath(REPORT, _REPO)}")
    print(
        f"-- {len(sibling_files)} sibling-lane file(s) in the shared dir, not this lane's to validate"
    )
    if missing:
        print(f"-- MISSING: {missing}")
    if unexpected:
        print(f"-- UNEXPECTED lane files: {unexpected}")
    return report


def _write_lane_manifest(per_file: List[Dict[str, Any]]) -> str:
    """Emit this lane's both-states manifest in the sibling lane's PROTOCOL-EXPECTATIONS shape.

    Written next to it rather than into it: build/proto-2 regenerates its own file, so editing
    theirs would either be clobbered or clobber them. Two lane-scoped manifests in one shape can
    be concatenated mechanically; one merged file written by two concurrent lanes cannot.
    """
    manifest = []
    for entry in per_file:
        if not entry.get("exists"):
            continue
        top = next(
            (t for t in entry.get("trees", []) if t["path"] == "stopping.expression"),
            None,
        )
        manifest.append(
            {
                "id": entry["council_id"].split("-", 1)[0].upper(),
                "council_id": entry["council_id"],
                "file": os.path.basename(entry["file"]),
                "expect": "pass",
                "controls_declared": entry["content_floors"]["brief_controls_declared"],
                "fast_unanimity_response": entry["content_floors"][
                    "fast_unanimity_response"
                ],
                "stopping_expression": (top or {}).get("expression"),
                "metrics_satisfying": (top or {}).get("satisfying"),
                "metrics_not_satisfying": (top or {}).get("not_satisfying"),
                "leaves_load_bearing": f"{(top or {}).get('load_bearing')}/{(top or {}).get('leaves')}",
            }
        )
    doc = {
        "purpose": (
            "Both-states controls for the P25-P36 stopping expressions. Each metrics_satisfying "
            "snapshot MUST evaluate True and each metrics_not_satisfying snapshot MUST evaluate "
            "False against the same tree; the not_satisfying snapshot is produced by flipping ONE "
            "leaf off the satisfying one, so a decorative conjunct is exposed by its own control "
            "refusing to fail. Snapshots are computed by exhaustive leaf-polarity search, not "
            "assumed, so a leaf under NOT or inside a WEIGHTED clause is handled correctly."
        ),
        "unit": "build/proto-3",
        "lane": "PHASE 2C - council protocol blueprints 25-36 of 48",
        "companion": "PROTOCOL-EXPECTATIONS.json (sibling lane build/proto-2, P13-P24) uses this shape",
        "mandated_controls": sorted(BRIEF_CONTROLS),
        "min_controls_per_protocol": MIN_ANTI_FAILURE_CONTROLS,
        "custom_metric_producers": {
            "why_not_in_the_leaf": (
                "SEM-001 requires parse(source_expression) == expression exactly and the parser "
                "cannot emit a producer key, so putting the producer in the leaf turns an advisory "
                "SEM-012 warning into a hard SEM-001 error. Measured: 11 SEM-001 errors and 11/12 "
                "files rejected. The map below carries the same information and build.py fails the "
                "lane if any custom metric is missing from it."
            ),
            "producers": dict(sorted(PRODUCERS.items())),
        },
        "manifest": manifest,
    }
    path = os.path.join(OUT_DIR, "PROTOCOL-EXPECTATIONS-25-36.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    print(f"-- lane manifest: {os.path.relpath(path, _REPO)} ({len(manifest)} entries)")
    return path


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="council_protocols.build")
    ap.add_argument("command", choices=["build", "verify", "all"])
    args = ap.parse_args(argv)

    if args.command in ("build", "all"):
        do_build()
    if args.command == "build":
        print("SUCCESS:proto-3-build 12 protocol files written")
        return 0

    report = do_verify()
    if report["status"] == "PASS":
        print(
            f"SUCCESS:proto-3 {report['protocols_pass']}/{EXPECTED} protocols validated"
        )
        return 0
    reasons = [e["problems"][0] for e in report["per_file"] if e.get("problems")]
    print(
        f"FAILED:proto-3 {report['protocols_fail']} protocol(s) rejected :: {reasons[:3]}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
