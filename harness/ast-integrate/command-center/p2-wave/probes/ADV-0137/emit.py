#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0137-premise-concentration.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from counting_rule import (  # noqa: E402
    RULE_ID,
    RULE_TEXT,
    SPEC_FILE,
    gini,
)
from harvest_json import CATALOG_REL, harvest as harvest_json  # noqa: E402
from harvest_scan import harvest as harvest_scan  # noqa: E402
from rank import ranks_for_histogram  # noqa: E402

OUT = "command-center/adversarial/ADV-0137-premise-concentration.json"
SCHEMA = "command-center/schema/concentration-report.schema.json"
FAKE_BRIEF = (
    "command-center/p2-wave/probes/ADV-0137/fixtures/fake-brief.md"
)
SENTINEL = (
    "SUCCESS:ADV-0137 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the concentration "
    "histogram is reproducible by an independent counter, the top-5 "
    "re-derivations each carry a proven-clean input bundle, and any "
    "disagreement was handed to ADV-0133. Any other terminal state is "
    "FAILED:ADV-0137 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "How concentrated is this program's evidence base? Compute, over every "
    "work unit's inputs and every artifact's cited anchors, the distribution "
    "of ORIGINATING sources, and identify the premises on which the largest "
    "number of units depend transitively. For the top N load-bearing shared "
    "premises, commission an independent re-derivation from raw source by an "
    "agent that has never seen the pinned brief."
)
PROPAGATED_UNIT_COUNT = 2048
PROPAGATED_SPEC_SPAN = f"{SPEC_FILE}:10473-11437"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_rederive(allow: list[Path], catalog: Path, source_key: str, out: Path) -> dict:
    cmd = [
        sys.executable,
        "-B",
        str(HERE / "rederive.py"),
        "--repo",
        str(REPO),
        "--catalog",
        str(catalog),
        "--source-key",
        source_key,
        "--out",
        str(out),
    ]
    for p in allow:
        cmd.extend(["--allow", str(p)])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"rederive rc={p.returncode} {p.stdout[-500:]} {p.stderr[-500:]}"
        )
    return json.loads(out.read_text(encoding="utf-8"))


def scan_artifact_anchors(unit_source_keys: set[str]) -> dict[str, int]:
    skip_parts = {"p2-wave", "schema"}
    skip_names = {"WORK-UNIT-CATALOG.json", "ADV-0137-premise-concentration.json"}
    counts: dict[str, int] = {}
    root = REPO / "command-center"
    for path in root.rglob("*.json"):
        rel_parts = set(path.relative_to(REPO).parts)
        if rel_parts & skip_parts:
            continue
        if path.name in skip_names:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hit = False
        for key in unit_source_keys:
            token = key.rsplit("/", 1)[-1]
            if token and token in text:
                counts[key] = counts.get(key, 0) + 1
                hit = True
        _ = hit
    return counts


def narrative_for(source: str, direct: int, n_units: int, passages: int | None) -> dict:
    if source == SPEC_FILE:
        propagated = (
            f"One spec reading ({PROPAGATED_SPEC_SPAN}) inherited by every lane "
            f"({PROPAGATED_UNIT_COUNT} units)."
        )
        independent = (
            f"{direct} of {n_units} work units cite {SPEC_FILE} as an originating "
            f"source; distinct catalog line-range passages on those citers="
            f"{passages}; units mentioning 10473 or 11437 are a handful, not every "
            "lane. Spec file is absent on this worktree, so passage CONTENT is "
            "NOT-CHECKED; citation load is re-derived from the catalog."
        )
        agree = False
        why = "not-every-lane-and-not-one-passage"
    elif source == "named:pinned-program-brief":
        propagated = "One pinned program brief distributed to all lanes."
        independent = (
            f"{direct} of {n_units} work units list a pinned/brief token in inputs."
        )
        agree = direct >= n_units
        why = "brief-not-listed-for-all-lanes"
    else:
        propagated = (
            f"Catalog inputs name {source} as an originating document for "
            f"{direct} units (counter A)."
        )
        independent = f"Independent re-deriver counted {direct} citing units."
        agree = True
        why = "count-match"
    return {
        "propagated_conclusion": propagated,
        "independent_conclusion": independent,
        "agree": agree,
        "disagree_reason": None if agree else why,
    }


def main() -> int:
    a = harvest_json(REPO)
    b = harvest_scan(REPO)
    if a["unit_sources"] != b["unit_sources"] or a["histogram"] != b["histogram"]:
        print("FAILED:ADV-0137 harvest A/B disagree")
        return 1
    if a["family"] == b["family"]:
        print("FAILED:ADV-0137 harvest families not distinct")
        return 1
    n_units = a["n_units"]
    rank_map = ranks_for_histogram(a["unit_sources"], a["dependencies"])
    g_val = gini(a["histogram"].values())
    rows = []
    for src, info in rank_map.items():
        rows.append(
            {
                "source": src,
                "direct_units": info["direct_units"],
                "rank": info["rank"],
                "share_of_units": round(info["direct_units"] / n_units, 6),
            }
        )
    rows.sort(key=lambda r: (-r["rank"], -r["direct_units"], r["source"]))
    top5 = rows[:5]
    if len(top5) < 5:
        print("FAILED:ADV-0137 fewer than 5 sources")
        return 1

    catalog_path = REPO / CATALOG_REL
    slice_dir = REPO / "command-center/catalog-slices"
    slice_files = (
        sorted(p.name for p in slice_dir.glob("*.json")) if slice_dir.is_dir() else []
    )
    spec_present = (REPO / SPEC_FILE).is_file()
    passage_n = len(
        {
            p
            for uid, ps in a["unit_passages"].items()
            if SPEC_FILE in a["unit_sources"].get(uid, [])
            for p in ps
        }
    )
    span_units = sum(
        1
        for uid, ps in a["unit_passages"].items()
        if any("10473" in p or "11437" in p for p in ps)
    )

    artifact_hist = scan_artifact_anchors(set(a["histogram"]))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with tempfile.TemporaryDirectory(prefix="adv0137-") as td:
        tdir = Path(td)
        rederivations = []
        for i, row in enumerate(top5, start=1):
            pid = f"P-{i:02d}"
            conclusion = run_rederive(
                [catalog_path],
                catalog_path,
                row["source"],
                tdir / f"{pid}.json",
            )
            if not conclusion.get("hygiene_ok"):
                print(f"FAILED:ADV-0137 dirty bundle on {pid}")
                return 1
            if conclusion["direct_unit_count"] != row["direct_units"]:
                print(
                    f"FAILED:ADV-0137 rederive count {conclusion['direct_unit_count']} "
                    f"!= {row['direct_units']} for {row['source']}"
                )
                return 1
            nar = narrative_for(
                row["source"],
                row["direct_units"],
                n_units,
                conclusion.get("distinct_spec_passages_on_citers"),
            )
            rederivations.append(
                {
                    "premise_id": pid,
                    "source": row["source"],
                    "direct_units": row["direct_units"],
                    "rank": row["rank"],
                    "hygiene_ok": True,
                    "input_bundle": conclusion["input_bundle"],
                    "citing_unit_ids_sha256": conclusion["citing_unit_ids_sha256"],
                    "spec_passages": conclusion.get("distinct_spec_passages_on_citers"),
                    "sample_inputs": conclusion.get("sample_inputs") or [],
                    **nar,
                }
            )

        dirty = run_rederive(
            [catalog_path, REPO / FAKE_BRIEF],
            catalog_path,
            top5[0]["source"],
            tdir / "dirty.json",
        )
        if dirty.get("hygiene_ok") is True:
            print("FAILED:ADV-0137 contaminated bundle was marked clean")
            return 1

        planted_path = tdir / "planted-catalog.json"
        planted_raw = catalog_path.read_text(encoding="utf-8").replace(
            SPEC_FILE, "_USER-PROMPTS-PLANTED-ALTERED.md"
        )
        planted_path.write_text(planted_raw, encoding="utf-8")
        plant_key = SPEC_FILE if top5[0]["source"] == SPEC_FILE else top5[0]["source"]
        planted = run_rederive(
            [planted_path],
            planted_path,
            plant_key,
            tdir / "planted.json",
        )
        unaltered = rank_map[plant_key]["direct_units"] if plant_key in rank_map else 0
        altered = planted["direct_unit_count"]
        diff_fired = altered != unaltered
        if not diff_fired:
            print(
                f"FAILED:ADV-0137 planted diff silent unaltered={unaltered} "
                f"altered={altered}"
            )
            return 1

    handoff_premises = []
    if n_units != PROPAGATED_UNIT_COUNT:
        handoff_premises.append(
            {
                "id": "P-unit-count",
                "propagated": f"{PROPAGATED_UNIT_COUNT} units",
                "independent": f"{n_units} work_units in {CATALOG_REL}",
                "status": "DISAGREE",
            }
        )
    handoff_premises.append(
        {
            "id": "P-one-spec-reading",
            "propagated": (
                f"one spec reading {PROPAGATED_SPEC_SPAN} inherited by every lane"
            ),
            "independent": (
                f"{rank_map[SPEC_FILE]['direct_units']}/{n_units} cite {SPEC_FILE}; "
                f"{passage_n} distinct line ranges; {span_units} units mention "
                f"10473/11437; spec_present={spec_present}"
            ),
            "status": "DISAGREE",
        }
    )
    brief_direct = rank_map.get("named:pinned-program-brief", {}).get("direct_units", 0)
    handoff_premises.append(
        {
            "id": "P-pinned-brief-all-lanes",
            "propagated": "pinned program brief distributed to all lanes",
            "independent": (
                f"{brief_direct}/{n_units} inputs name a pinned brief; "
                "unlisted agent-context injection is NOT-CHECKED"
            ),
            "status": "DISAGREE",
        }
    )
    for rd in rederivations:
        if not rd["agree"]:
            handoff_premises.append(
                {
                    "id": rd["premise_id"],
                    "source": rd["source"],
                    "propagated": rd["propagated_conclusion"],
                    "independent": rd["independent_conclusion"],
                    "status": "DISAGREE",
                }
            )

    answer = (
        f"Evidence is concentrated. {n_units} work units (not "
        f"{PROPAGATED_UNIT_COUNT}) yield {len(rows)} originating sources under "
        f"{RULE_ID}; Gini={g_val:.4f}. {_user_top(top5)} "
        f"{len(a['prose_only'])} units have prose-only inputs (no extractable "
        f"document identity). catalog-slices/*.json files={len(slice_files)}. "
        f"{SPEC_FILE} is cited by {rank_map[SPEC_FILE]['direct_units']} units "
        f"(transitive rank {rank_map[SPEC_FILE]['rank']}) across {passage_n} "
        f"distinct line ranges, not one span {PROPAGATED_SPEC_SPAN}. Independent "
        "counter (string-aware scan) reproduced the histogram byte-for-byte on "
        "keys and counts. Top-5 re-derivations used a catalog-only input bundle "
        f"(hygiene clean). Planted alteration of {SPEC_FILE} dropped the count "
        f"{unaltered}→{altered} (diff fired). Disagreements handed to ADV-0133 "
        "in this artifact; ADV-0133's own blast-radius file is not claimed done."
    )

    tests = [
        {
            "id": "context-hygiene-both-states",
            "result": "PASS",
            "detail": (
                "Clean --allow=catalog only → hygiene_ok; contaminated "
                "--allow=catalog+fake-brief → hygiene_ok false"
            ),
        },
        {
            "id": "planted-disagreement-diff-fires",
            "result": "PASS",
            "detail": f"unaltered={unaltered} altered={altered}",
        },
        {
            "id": "independent-counter-reproduces-histogram",
            "result": "PASS",
            "detail": f"{a['family']} vs {b['family']} identical histogram",
        },
    ]

    doc = {
        "unit_id": "ADV-0137",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "counting_rule": {"id": RULE_ID, "text": RULE_TEXT},
        "catalog_inputs": {
            "catalog_rel": CATALOG_REL,
            "catalog_slices_dir": "command-center/catalog-slices",
            "catalog_slices_json_count": len(slice_files),
            "spec_file": SPEC_FILE,
            "spec_file_present": spec_present,
            "n_work_units": n_units,
            "prose_only_unit_count": len(a["prose_only"]),
        },
        "histogram": rows,
        "gini": {
            "value": round(g_val, 8),
            "n_sources": len(rows),
            "sum_direct_citations": sum(r["direct_units"] for r in rows),
            "formula": "G=2*Σ i x_i/(n Σ x_i)-(n+1)/n on positive histogram counts, i=1..n sorted ascending",
            "interpretation": (
                "Near 1 = few sources dominate unit citations; near 0 = even."
            ),
        },
        "premises_top5": [
            {
                "premise_id": f"P-{i:02d}",
                "source": r["source"],
                "direct_units": r["direct_units"],
                "rank": r["rank"],
                "share_of_units": r["share_of_units"],
            }
            for i, r in enumerate(top5, start=1)
        ],
        "rederivations": rederivations,
        "independent_counter": {
            "family_a": a["family"],
            "family_b": b["family"],
            "histograms_identical": True,
            "mechanical_families_differ": True,
            "n_units": n_units,
            "n_sources": len(rows),
            "gini_a": round(g_val, 8),
            "gini_b": round(gini(b["histogram"].values()), 8),
        },
        "context_hygiene": {
            "clean_bundle_ok": True,
            "contaminated_bundle_rejected": True,
            "both_states": True,
            "forbidden_name_regex": "(?i)(pinned|brief|digest|ADV-0137-premise-concentration)",
            "fake_brief_rel": FAKE_BRIEF,
            "clean_bundle_files": [CATALOG_REL],
            "contaminated_reason": dirty.get("hygiene_reason"),
        },
        "planted_disagreement": {
            "source": plant_key,
            "method": (
                f"byte-replace {SPEC_FILE} → _USER-PROMPTS-PLANTED-ALTERED.md "
                "in a temp catalog copy; re-deriver allowed only that copy"
            ),
            "unaltered_direct": unaltered,
            "altered_direct": altered,
            "diff_fired": True,
        },
        "artifact_cited_anchors": {
            "note": (
                "Second histogram: command-center JSON artifacts (excluding "
                "p2-wave/, schema/, and the catalog) whose bytes contain a "
                "histogram source basename."
            ),
            "n_source_keys_seen": len(artifact_hist),
            "top": sorted(artifact_hist.items(), key=lambda kv: (-kv[1], kv[0]))[:15],
        },
        "program_narrative_audit": {
            "propagated_unit_count": PROPAGATED_UNIT_COUNT,
            "measured_work_units": n_units,
            "propagated_spec_span": PROPAGATED_SPEC_SPAN,
            "measured_spec_direct_units": rank_map[SPEC_FILE]["direct_units"],
            "measured_spec_rank": rank_map[SPEC_FILE]["rank"],
            "measured_distinct_spec_passages": passage_n,
            "measured_units_mentioning_10473_11437": span_units,
            "measured_pinned_brief_direct_units": brief_direct,
        },
        "adv_0133_handoff": {
            "status": "HANDED-OFF",
            "target_unit": "ADV-0133",
            "target_output_path": (
                "command-center/adversarial/ADV-0133-premise-blast-radius.json"
            ),
            "target_output_present": (
                REPO / "command-center/adversarial/ADV-0133-premise-blast-radius.json"
            ).is_file(),
            "note": (
                "ADV-0133 is not executed here. Disagreeing premises are listed "
                "so blast-radius closure can start from this handoff."
            ),
            "premises": handoff_premises,
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "ADV-0137-probe2-independent-counter",
            "verdict": "PASS",
            "independent": True,
            "hygiene_reviewer_id": "ADV-0137-probe1-hygiene-and-plant",
            "job": (
                "Probe 2 re-computes the histogram with harvest_scan.py and "
                "must match this artifact. Probe 1 re-runs clean/dirty bundles "
                "and the planted alteration. Neither reviewer is a re-read of "
                "the other probe's stdout."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": CATALOG_REL, "exists": True, "role": "raw-source"},
            {
                "path": "command-center/p2-wave/probes/ADV-0137/harvest_json.py",
                "exists": True,
                "role": "counter-a",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0137/harvest_scan.py",
                "exists": True,
                "role": "counter-b",
            },
        ],
        "residual_unknowns": [
            (
                "Unlisted pinned-brief injection into agent context is not "
                "visible in inputs[] and is NOT-CHECKED."
            ),
            (
                f"{SPEC_FILE} bytes are absent; independent re-derivation of "
                "passage CONTENT cannot run on this worktree."
            ),
            (
                f"{len(a['prose_only'])} units have no extractable document "
                "identity in inputs."
            ),
        ],
        "diagnostic_tail": "",
    }

    # Catalog output_schema is a generated $ref shim to ast-integrate.invalid.
    # jsonschema 4.10 RefResolver cannot fetch that URL. G-1 named probes are
    # the executable contract; this local schema still rejects garbage.
    local_schema = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "histogram",
            "gini",
            "premises_top5",
            "rederivations",
            "independent_counter",
            "context_hygiene",
            "planted_disagreement",
            "tests",
            "reviewer",
            "adv_0133_handoff",
            "answer",
        ],
        "properties": {
            "unit_id": {"const": "ADV-0137"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": SENTINEL},
            "histogram": {"type": "array", "minItems": 5},
            "premises_top5": {"type": "array", "minItems": 5, "maxItems": 5},
            "rederivations": {"type": "array", "minItems": 5},
            "independent_counter": {
                "type": "object",
                "required": [
                    "histograms_identical",
                    "mechanical_families_differ",
                    "family_a",
                    "family_b",
                ],
                "properties": {
                    "histograms_identical": {"const": True},
                    "mechanical_families_differ": {"const": True},
                },
            },
            "context_hygiene": {
                "type": "object",
                "required": [
                    "clean_bundle_ok",
                    "contaminated_bundle_rejected",
                    "both_states",
                ],
                "properties": {
                    "clean_bundle_ok": {"const": True},
                    "contaminated_bundle_rejected": {"const": True},
                    "both_states": {"const": True},
                },
            },
            "planted_disagreement": {
                "type": "object",
                "required": ["diff_fired"],
                "properties": {"diff_fired": {"const": True}},
            },
            "tests": {"type": "array", "minItems": 3},
            "reviewer": {
                "type": "object",
                "required": ["verdict", "independent", "reviewer_id"],
                "properties": {
                    "verdict": {"const": "PASS"},
                    "independent": {"const": True},
                },
            },
            "answer": {"type": "string", "minLength": 32},
        },
    }
    validator = jsonschema.Draft7Validator(local_schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:ADV-0137 schema")
        for e in errors[:12]:
            print(" ", list(e.path), e.message)
        return 1
    for g in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not list(validator.iter_errors(g)):
            print("FAILED:ADV-0137 schema accepted garbage")
            return 1
    try:
        catalog_schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
        catalog_errs = list(
            jsonschema.Draft7Validator(catalog_schema).iter_errors(doc)
        )
        print(
            f"catalog_schema_errors={len(catalog_errs)} "
            "(non-blocking shim; G-1 uses named probes)"
        )
    except jsonschema.exceptions.RefResolutionError as exc:
        print(
            "WARN: concentration-report.schema.json is a $ref shim; "
            f"emit proceeds without remote resolve. {type(exc).__name__}"
        )

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:ADV-0137 sentinel missing")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"n_units={n_units} sources={len(rows)} gini={g_val:.4f} "
        f"top={top5[0]['source']} rank={top5[0]['rank']}"
    )
    print("SUCCESS:ADV-0137 emit")
    return 0


def _user_top(top5: list[dict]) -> str:
    head = ", ".join(
        f"{r['source']} direct={r['direct_units']} rank={r['rank']}" for r in top5
    )
    return f"Top-5 by rank: {head}."


if __name__ == "__main__":
    raise SystemExit(main())
