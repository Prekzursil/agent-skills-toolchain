#!/usr/bin/env python3
"""Probe 2: independent recount + coverage-only refutation + schema control.

Does NOT call measure.score. Occupancy is len(list-of-ids) per category.
Coverage is |set(labels) intersect T| / |T|. Disagreement with the
artifact numbers blocks the unit. Schema must reject garbage.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0054-category-taxonomy-coverage-and-diversity-as-one-measuremen.md"
)
SCHEMA = HERE / "artifact.schema.json"


def occ(ideas: list[dict], ids: list[str]) -> tuple[dict[str, int], list[str]]:
    bags = {c: [] for c in ids}
    extra: list[str] = []
    for idea in ideas:
        cat = str(idea.get("category") or "")
        if cat in bags:
            bags[cat].append(str(idea.get("id")))
        else:
            extra.append(str(idea.get("id") or cat))
    return {c: len(bags[c]) for c in ids}, extra


def coverage_set(ideas: list[dict], ids: list[str]) -> float:
    hit = {str(i.get("category") or "") for i in ideas} & set(ids)
    return len(hit) / float(len(ids))


def joint_from_lists(counts: dict[str, int], ids: list[str]) -> float:
    n = sum(counts[c] for c in ids)
    if n <= 0:
        return 0.0
    h = 0.0
    for c in ids:
        k = counts[c]
        if k <= 0:
            continue
        p = k / n
        h -= p * math.log(p)
    return h / math.log(len(ids))


def main() -> int:
    F.assert_counts()
    tax = json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))
    ids = [row["id"] for row in tax["categories"]]
    thr = float(tax["joint_score"]["threshold_reject_below"])

    bags = {
        "clustered": F.clustered(),
        "spread": F.spread(),
        "token_coverage": F.token_coverage(),
    }
    live = {}
    for name, ideas in bags.items():
        counts, extra = occ(ideas, ids)
        if extra:
            print(f"FAILED:CNL-0054-probe2 unexpected invalid in {name}: {extra}")
            return 1
        cov_set = coverage_set(ideas, ids)
        cov_len = sum(1 for c in ids if counts[c] >= 1) / float(len(ids))
        if abs(cov_set - cov_len) > 1e-15:
            print(f"FAILED:CNL-0054-probe2 coverage mechanisms disagree on {name}")
            return 1
        joint = joint_from_lists(counts, ids)
        live[name] = {
            "n": sum(counts.values()),
            "coverage": cov_set,
            "joint": joint,
            "fires": joint < thr,
            "occupancy": counts,
        }
        print(
            f"recount {name}: n={live[name]['n']} coverage={cov_set:.12f} "
            f"joint={joint:.12f} fires={live[name]['fires']}"
        )

    if not (live["clustered"]["joint"] < live["spread"]["joint"]):
        print("FAILED:CNL-0054-probe2 clustered not lower than spread")
        return 1
    if live["clustered"]["n"] != live["spread"]["n"]:
        print("FAILED:CNL-0054-probe2 raw count mismatch")
        return 1
    if live["token_coverage"]["coverage"] != live["spread"]["coverage"]:
        print("FAILED:CNL-0054-probe2 coverage-only distinguished token from spread")
        return 1
    if live["token_coverage"]["coverage"] != 1.0:
        print("FAILED:CNL-0054-probe2 token coverage is not 1.0")
        return 1
    if not (
        live["token_coverage"]["joint"] < live["spread"]["joint"]
        and live["token_coverage"]["fires"]
        and not live["spread"]["fires"]
        and live["clustered"]["fires"]
    ):
        print("FAILED:CNL-0054-probe2 joint gate both-states failed on recount")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0054-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNL-0054" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0054-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0054-probe2 self-declared {doc.get('state')}")
        return 1

    scores = doc.get("fixture_scores") or {}
    for name in ("clustered", "spread", "token_coverage"):
        rec = scores.get(name) or {}
        for field in ("coverage", "joint"):
            if abs(float(rec[field]) - float(live[name][field])) > 1e-12:
                print(
                    f"FAILED:CNL-0054-probe2 disagreement {name}.{field} "
                    f"artifact={rec[field]} recount={live[name][field]}"
                )
                return 1
        if bool(rec.get("fires")) != bool(live[name]["fires"]):
            print(f"FAILED:CNL-0054-probe2 disagreement {name}.fires")
            return 1

    answers = doc.get("answers")
    claims = doc.get("claims")
    if not isinstance(answers, dict) or len(answers) < 3:
        print("FAILED:CNL-0054-probe2 answers missing or fewer than 3 keys")
        return 1
    if not isinstance(claims, list) or len(claims) < 2:
        print("FAILED:CNL-0054-probe2 claims missing or fewer than 2 items")
        return 1

    if not SCHEMA.is_file():
        print("FAILED:CNL-0054-probe2 local artifact.schema.json missing")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = schema.get("required") or []
    if len(required) < 8:
        print("FAILED:CNL-0054-probe2 local schema is vacuous")
        return 1
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        path = "/".join(str(p) for p in errs[0].path)
        print(f"FAILED:CNL-0054-probe2 schema-invalid path={path} msg={errs[0].message}")
        return 1
    rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0054", "state": "SUCCESS"},
    ):
        if list(validator.iter_errors(garbage)):
            rejected += 1
            continue
        print(f"FAILED:CNL-0054-probe2 schema accepted garbage {garbage}")
        return 1
    if rejected != 3:
        print(f"FAILED:CNL-0054-probe2 garbage rejected {rejected}/3")
        return 1

    print(
        "coverage-only: token_coverage.coverage == spread.coverage == 1.0; "
        "joint token < joint spread (coverage does not distinguish genuine spread)"
    )
    print("schema garbage rejected 3/3")
    print("SUCCESS:CNL-0054-probe2 independent recount schema-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
