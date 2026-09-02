#!/usr/bin/env python3
"""Probe 2: schema discriminates, overclaim gates, reviewer added mode.

The declared catalog schema file must exist and parse. On this image the
catalog path is a generated $ref shim: jsonschema 4.10 raises
RefResolutionError (network to ast-integrate.invalid), which is not a
ValidationError, so it cannot discriminate. The unit-local bound schema
is the discrimination contract: garbage rejected, artifact accepted, a
mutant that replaces the numeric false-positive rate with the adjective
'low' rejected. Production present-flags must match the worktree.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
# Repo-root `platform/` shadows stdlib pieces that jsonschema imports.
sys.path = [p for p in sys.path if p not in ("", ".", str(REPO))]
sys.path.insert(0, str(HERE))
import reviewer as R  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0098-weak-synthesis-and-circular-citation-in-the-argument-graph.md"
)
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"
BOUND = HERE / "bound.schema.json"
PROD_A = REPO / "tools/council/artifacts/argument_graph.py"
PROD_E = REPO / "tools/council/artifacts/evidence_map.py"


def discriminator(catalog: dict) -> dict:
    """Prefer a local catalog schema that still constrains FP rate; else bound."""
    props = catalog.get("properties") or {}
    if "false_positive_rate" in props or "detector" in props:
        return catalog
    if not BOUND.is_file():
        raise FileNotFoundError(BOUND)
    return json.loads(BOUND.read_text(encoding="utf-8"))


def _fail(msg: str) -> int:
    print(f"FAILED:CNL-0098-probe2 {msg}")
    return 1


def _resolve(rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = REPO / rel
    if not path.is_file():
        return False, f"missing {rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"{rel}:{line} out of range"
    if snippet not in lines[line - 1]:
        return False, f"{rel}:{line} snippet mismatch"
    return True, f"{rel}:{line}"


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        return _fail("jsonschema not installed")

    if not ART.is_file():
        return _fail("artifact missing")
    if not SCHEMA.is_file():
        return _fail("schema missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    catalog = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or not catalog:
        return _fail("catalog schema empty")
    schema = discriminator(catalog)
    print(
        f"discriminator={'catalog' if schema is catalog else 'bound'} "
        f"catalog_ref={bool(catalog.get('$ref'))}"
    )

    garbage_rejected = 0
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        try:
            jsonschema.validate(g, schema)
        except jsonschema.ValidationError:
            garbage_rejected += 1
        except jsonschema.RefResolutionError:
            return _fail("schema $ref unresolvable; bound.schema.json missing or unused")
    print(f"schema_garbage_rejected={garbage_rejected}/3")
    if garbage_rejected != 3:
        return _fail("schema accepts garbage")
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        return _fail(f"artifact fails schema: {exc.message}")
    print("schema_accepts_artifact=True")

    mutant = copy.deepcopy(doc)
    if isinstance(mutant.get("false_positive_rate"), dict):
        mutant["false_positive_rate"]["rate"] = "low"
    else:
        mutant["false_positive_rate"] = "low"
    adjective_rejected = False
    try:
        jsonschema.validate(mutant, schema)
    except jsonschema.ValidationError:
        adjective_rejected = True
    print(f"adjective_fp_rate_rejected={adjective_rejected}")
    if not adjective_rejected:
        return _fail("schema accepted adjective false-positive rate")

    if doc.get("detector", {}).get("does_not_count_urls") is not True:
        return _fail("detector must refuse URL counting")
    mods = doc.get("production_modules") or {}
    claimed_a = (mods.get("argument_graph_py") or {}).get("present") is True
    claimed_e = (mods.get("evidence_map_py") or {}).get("present") is True
    live_a = PROD_A.is_file()
    live_e = PROD_E.is_file()
    print(f"production_argument_graph_present={live_a}")
    print(f"production_evidence_map_present={live_e}")
    if claimed_a and not live_a:
        return _fail("overclaim: argument_graph.py marked present")
    if claimed_e and not live_e:
        return _fail("overclaim: evidence_map.py marked present")
    if live_a != claimed_a or live_e != claimed_e:
        return _fail("production module appeared; artifact present-flags must be updated")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        return _fail("reviewer is not independent scope-only")
    if rev.get("both_states_rerun") is not True:
        return _fail("reviewer did not re-run both-states")
    if rev.get("vendor_constraint_met") is True:
        return _fail("cannot claim openai/gpt-5-codex signed this")
    added = rev.get("added_failure_mode") or {}
    if added.get("id") != "FM-SEMANTIC-UNGROUNDED":
        return _fail("reviewer did not add FM-SEMANTIC-UNGROUNDED")
    author_ids = {p.get("id") for p in (doc.get("pathologies") or [])}
    if "FM-SEMANTIC-UNGROUNDED" in author_ids:
        return _fail("added mode was already an author pathology id")

    live = R.review()
    print(f"reviewer_live_verdict={live['verdict']}")
    if live["verdict"] != "PASS":
        return _fail("live reviewer re-run failed")
    if not live["rerun"]["passed"]:
        return _fail("live both-states re-run failed")

    evidence = doc.get("evidence") or []
    kinds = set()
    for i, row in enumerate(evidence):
        ok, why = _resolve(str(row.get("path") or ""), int(row.get("line") or 0), str(row.get("snippet") or ""))
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            return _fail("unresolved anchor")
        kinds.add(str(row.get("kind") or ""))
    if "catalog" not in kinds or "probe" not in kinds:
        return _fail(f"evidence kinds {kinds} need catalog and probe")

    for claim in doc.get("claims") or []:
        if claim.get("verdict") == "REFUTED" and not claim.get("defect_locus"):
            return _fail(f"{claim.get('id')} REFUTED missing defect_locus")

    if "SUCCESS:CNL-0098" not in ART.read_text(encoding="utf-8"):
        return _fail("sentinel absent")
    print("SUCCESS:CNL-0098-probe2 schema overclaim reviewer-added-mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
