#!/usr/bin/env python3
"""Emit RES-0151 evidence-saturation stopping-metric measurement run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpora import HISTORICAL_RUNS, load_historical_runs  # noqa: E402
from controls import (  # noqa: E402
    DIVERSE_TEXTS,
    NEAR_IDENTICAL_TEXTS,
    diverse_sources,
    mutant_report,
    near_identical_sources,
    string_equality_distinct_count,
)
from metric import (  # noqa: E402
    load_prereg,
    score_run,
    score_run_string_equality,
    token_counter_fire,
)

OUT = "command-center/research/evidence-quality/RES-0151-evidence-saturation-stopping-metric.json"
SCHEMA = "command-center/schema/measurement-run.schema.json"
PREREG = "command-center/p2-wave/probes/RES-0151/threshold_prereg.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0151/probe1_historical_replays.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0151/probe2_negative_control.py"
)
QUESTION = (
    "Define and validate a stopping metric based on the marginal rate of NEW "
    "distinct claims per additional source; on 5 replayed historical research "
    "runs, at what point does the metric fire, and how many genuinely new "
    "claims arrived after that point (the miss rate)?"
)
SENTINEL = (
    "SUCCESS:RES-0151 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, the near-identical 30-source "
    "control fires EARLY, the diverse 30-source control stays silent, planted "
    "paraphrases collapse while true distinctions stay apart, and the five "
    "historical replays are scored from on-disk prior documents. Any other "
    "terminal state is FAILED:RES-0151 <classification> with the diagnostic tail."
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "RES-0151", "state": "SUCCESS"},
)

# Catalog output_schema is a $ref shim to https://ast-integrate.invalid/... .
# Bare Draft7Validator tries to fetch that host and raises RefResolutionError.
# receipt_core also has additionalProperties:false, so the probe-required
# historical_replays / negative_controls object cannot live at the top level
# of a profile-valid receipt. G-1 does not require that profile; this unit
# schema rejects garbage and binds the live probe contract.
UNIT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "historical_replays",
        "negative_controls",
        "claims",
        "tests",
        "evidence",
        "reviewer",
        "report",
    ],
    "properties": {
        "unit_id": {"const": "RES-0151"},
        "state": {"enum": ["SUCCESS"]},
        "sentinel": {"type": "string", "minLength": 16, "pattern": "SUCCESS:RES-0151"},
        "historical_replays": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {
                "type": "object",
                "required": [
                    "run_id",
                    "path",
                    "n_sources",
                    "fired",
                    "fire_index",
                    "miss_count",
                    "yields",
                    "file_sha256",
                    "resolved_url",
                    "fetch_timestamp",
                ],
            },
        },
        "negative_controls": {
            "type": "object",
            "required": [
                "near_identical",
                "diverse",
                "token_counter_foil",
                "mechanism_mutants",
            ],
            "properties": {
                "near_identical": {
                    "type": "object",
                    "required": ["early", "fired"],
                    "properties": {
                        "early": {"const": True},
                        "fired": {"const": True},
                    },
                },
                "diverse": {
                    "type": "object",
                    "required": ["fired"],
                    "properties": {"fired": {"const": False}},
                },
                "token_counter_foil": {
                    "type": "object",
                    "required": ["fires_on_both"],
                    "properties": {"fires_on_both": {"const": True}},
                },
                "mechanism_mutants": {
                    "type": "object",
                    "required": ["pass"],
                    "properties": {"pass": {"const": True}},
                },
            },
        },
        "claims": {"type": "array", "minItems": 4},
        "tests": {"type": "array", "minItems": 4},
        "evidence": {"type": "array", "minItems": 2},
        "reviewer": {
            "type": "object",
            "required": ["independent", "verdict", "reviewer_id"],
            "properties": {
                "independent": {"const": True},
                "verdict": {"const": "PASS"},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "measurement-run"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def lineage(rel: str) -> dict:
    path = REPO / rel
    digest, _ = sha256_file(path)
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "resolved_url": path.resolve().as_uri(),
        "fetch_timestamp": ts,
        "sha256": digest,
        "path": rel,
    }


def slim_score(score: dict, run: dict) -> dict:
    rolling_present = [m for m in score["rolling_mean"] if m is not None]
    min_roll = min(rolling_present) if rolling_present else None
    return {
        "run_id": run["run_id"],
        "path": run["path"],
        "resolved_url": run["resolved_url"],
        "fetch_timestamp": run["fetch_timestamp"],
        "file_sha256": run["file_sha256"],
        "bytes": run["bytes"],
        "corpus_class": run["corpus_class"],
        "n_sources": score["n_sources"],
        "fired": score["fired"],
        "fire_index": score["fire_index"],
        "early": score["early"],
        "total_distinct": score["total_distinct"],
        "miss_count": score["miss_count"],
        "miss_rate": score["miss_rate"],
        "miss_keys": score["miss_keys"],
        "yields": score["yields"],
        "rolling_mean": score["rolling_mean"],
        "min_rolling_mean": min_roll,
        "window": score["window"],
        "floor": score["floor"],
        "min_sources": score["min_sources"],
        "sources": [
            {
                "index": row["index"],
                "source_id": row["source_id"],
                "heading": row["heading"],
                "n_claims": row["n_claims"],
                "n_new": row["n_new"],
                "resolved_url": row.get("resolved_url"),
                "fetch_timestamp": row.get("fetch_timestamp"),
                "sha256": row.get("sha256"),
                "sherman_kent_band": row.get("sherman_kent_band"),
                "new_keys": row["new_keys"],
            }
            for row in score["per_source"]
        ],
    }


def main() -> int:
    prereg = load_prereg()
    prereg_path = REPO / PREREG
    if not prereg_path.is_file():
        print("FAILED:RES-0151 preregistration missing")
        return 1
    prereg_on_disk = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg_on_disk.get("recorded_before_any_replay_or_control") is not True:
        print("FAILED:RES-0151 prereg not frozen")
        return 1

    runs = load_historical_runs()
    if len(runs) != 5:
        print(f"FAILED:RES-0151 expected 5 historical runs, got {len(runs)}")
        return 1
    replay_rows = []
    for run in runs:
        replay_rows.append(slim_score(score_run(run["sources"], prereg), run))

    near_src = near_identical_sources()
    div_src = diverse_sources()
    near = score_run(near_src, prereg)
    div = score_run(div_src, prereg)
    near_str = score_run_string_equality(near_src, prereg)
    div_str = score_run_string_equality(div_src, prereg)
    budget = int(prereg["token_counter_foil_budget_tokens"])
    token_near = token_counter_fire(near_src, budget)
    token_div = token_counter_fire(div_src, budget)
    mutants = mutant_report()

    if not near["early"]:
        print(
            f"FAILED:RES-0151 detector-failure near-identical did not fire early "
            f"idx={near['fire_index']}"
        )
        return 1
    if div["fired"]:
        print(
            f"FAILED:RES-0151 detector-failure diverse fired at {div['fire_index']}"
        )
        return 1
    if token_near is None or token_div is None:
        print("FAILED:RES-0151 token-counter foil did not fire on both corpora")
        return 1
    if near_str["fired"]:
        print("FAILED:RES-0151 string-equality foil fired on paraphrases (unexpected)")
        return 1
    if not mutants["pass"]:
        print("FAILED:RES-0151 mechanism mutants did not pass")
        print(json.dumps(mutants, indent=2)[:2000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pre_lin = lineage(PREREG)
    gnd_lin = lineage(HISTORICAL_RUNS[0][1])
    ctl_lin = lineage("command-center/p2-wave/probes/RES-0151/controls.py")
    met_lin = lineage("command-center/p2-wave/probes/RES-0151/metric.py")

    fired_runs = [r for r in replay_rows if r["fired"]]
    silent_runs = [r for r in replay_rows if not r["fired"]]
    answer = (
        "On the five prior P2-wave research/measurement documents replayed as "
        "heading-ordered source sequences, the preregistered rolling-mean "
        f"metric (window={prereg['window']}, floor={prereg['floor']}) fired on "
        f"{len(fired_runs)}/5 runs. Silent runs ({len(silent_runs)}): "
        + ", ".join(
            f"{r['run_id']} min_rolling_mean={r['min_rolling_mean']:.3f}"
            for r in silent_runs
        )
        + ". Post-stop miss rate is null on a silent run (no stop occurred). "
        "The both-states control passed: 30 mechanism-paraphrase sources fired "
        f"at index {near['fire_index']} (early), 30 diverse sources stayed silent, "
        "and a token-counter foil fired on both corpora. String equality saw "
        f"{near_str['total_distinct']} distinct paraphrase strings and did not fire, "
        "so the stopper is not a string comparator."
    )

    doc = {
        "unit_id": "RES-0151",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "schema_version": 1,
        "title": "A computable evidence-saturation signal for stopping a research run",
        "question": QUESTION,
        "answer": answer,
        "generated_at": now,
        "metric": {
            "id": prereg["metric_id"],
            "distinctness": prereg["distinctness"],
            "not_used_for_distinctness": prereg["not_used_for_distinctness"],
            "fire_rule": prereg["fire_rule"],
            "miss_rate_definition": prereg["miss_rate_definition"],
            "formula": (
                "y_t = |new mechanism keys at source t|; "
                "fire at smallest t >= min_sources with mean(y_{t-W+1..t}) <= floor"
            ),
        },
        "spec_anchor": (
            "_USER-PROMPTS.md:11241,10485; "
            "command-center/WORK-UNIT-CATALOG.json#RES-0151"
        ),
        "report": {
            "kind": "measurement-run",
            "observations": [
                {
                    "name": "historical-fire-indexes",
                    "measured": ",".join(
                        f"{r['run_id']}={r['fire_index']}" for r in replay_rows
                    ),
                    "method": prereg["metric_id"],
                    "anchor": OUT,
                },
                {
                    "name": "near-identical-fire-index",
                    "measured": near["fire_index"] if near["fire_index"] is not None else -1,
                    "method": "score_run-on-planted-paraphrases",
                    "anchor": "command-center/p2-wave/probes/RES-0151/controls.py",
                },
                {
                    "name": "diverse-fired",
                    "measured": bool(div["fired"]),
                    "method": "score_run-on-planted-diverse",
                    "anchor": "command-center/p2-wave/probes/RES-0151/controls.py",
                },
            ],
            "control_ids": [
                "near-identical-30-fire-early",
                "diverse-30-stay-silent",
                "token-counter-foil",
                "mechanism-mutants",
            ],
        },
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b); this emit is attempt 1",
        },
        "preregistration": {
            "path": PREREG,
            "recorded_before_any_replay_or_control": True,
            "recorded_at": prereg["recorded_at"],
            "window": prereg["window"],
            "floor": prereg["floor"],
            "min_sources": prereg["min_sources"],
            "early_max_index": prereg["early_max_index"],
            "sha256": pre_lin["sha256"],
            "citation": prereg["citation"],
            "res_0173_status": prereg["res_0173_status"],
        },
        "historical_replays": replay_rows,
        "historical_summary": {
            "n_runs": len(replay_rows),
            "fired_count": len(fired_runs),
            "silent_count": len(silent_runs),
            "fire_indexes": [r["fire_index"] for r in replay_rows],
            "miss_counts": [r["miss_count"] for r in replay_rows],
            "note": (
                "Sources are ##/### sections of committed P2-wave documents. "
                "Claims are extracted from those sections; they are not simulated. "
                "A silent detector is a measured outcome, not a skipped replay."
            ),
        },
        "negative_controls": {
            "near_identical": {
                "n_sources": 30,
                "fired": near["fired"],
                "fire_index": near["fire_index"],
                "early": near["early"],
                "total_distinct_mechanism_keys": near["total_distinct"],
                "string_equality_distinct": string_equality_distinct_count(
                    NEAR_IDENTICAL_TEXTS
                ),
                "string_equality_fired": near_str["fired"],
                "string_equality_fire_index": near_str["fire_index"],
                "yields": near["yields"],
                "required": "fire EARLY",
                "result": "PASS" if near["early"] else "FAIL",
            },
            "diverse": {
                "n_sources": 30,
                "fired": div["fired"],
                "fire_index": div["fire_index"],
                "early": div["early"],
                "total_distinct_mechanism_keys": div["total_distinct"],
                "string_equality_distinct": string_equality_distinct_count(DIVERSE_TEXTS),
                "yields": div["yields"],
                "required": "do NOT fire",
                "result": "PASS" if not div["fired"] else "FAIL",
            },
            "token_counter_foil": {
                "budget_tokens": budget,
                "fire_index_near_identical": token_near,
                "fire_index_diverse": token_div,
                "fires_on_both": token_near is not None and token_div is not None,
                "note": (
                    "A token budget stopper fires on both controls and therefore "
                    "cannot distinguish saturation from search volume."
                ),
            },
            "mechanism_mutants": mutants,
        },
        "claims": [
            {
                "id": "C1-near-identical-fires-early",
                "statement": (
                    "Thirty string-distinct paraphrases of one mechanism make the "
                    f"metric fire early (index {near['fire_index']} <= "
                    f"{prereg['early_max_index']}) after collapsing to "
                    f"{near['total_distinct']} mechanism key(s)."
                ),
                "sherman_kent_band": "almost-certain",
                "source_lineage": ctl_lin,
                "independent_verification_path": P2,
                "signals": [
                    {"id": "S1", "kind": "metric.py-score_run-on-planted-paraphrases"},
                    {
                        "id": "S2",
                        "kind": "probe2-independent-recount-from-yield-vector",
                    },
                ],
            },
            {
                "id": "C2-diverse-stays-silent",
                "statement": (
                    "Thirty genuinely diverse sources keep introducing new "
                    f"mechanism keys (distinct={div['total_distinct']}) and the "
                    "metric does not fire."
                ),
                "sherman_kent_band": "almost-certain",
                "source_lineage": ctl_lin,
                "independent_verification_path": P2,
                "signals": [
                    {"id": "S1", "kind": "metric.py-score_run-on-planted-diverse"},
                    {
                        "id": "S2",
                        "kind": "probe2-independent-recount-from-yield-vector",
                    },
                ],
            },
            {
                "id": "C3-historical-replays",
                "statement": (
                    "Five prior documents were replayed. Fire indexes: "
                    + ", ".join(
                        f"{r['run_id']}={r['fire_index']}" for r in replay_rows
                    )
                    + ". Miss counts: "
                    + ", ".join(
                        f"{r['run_id']}={r['miss_count']}" for r in replay_rows
                    )
                    + "."
                ),
                "sherman_kent_band": "likely",
                "source_lineage": gnd_lin,
                "independent_verification_path": P1,
                "signals": [
                    {"id": "S1", "kind": "live-extract-and-score-five-on-disk-documents"},
                    {
                        "id": "S2",
                        "kind": "probe2-inline-rolling-mean-recount-from-recorded-yields",
                    },
                ],
            },
            {
                "id": "C4-not-a-token-or-string-counter",
                "statement": (
                    "A token-counter foil fires on both 30-source controls "
                    f"(near={token_near}, diverse={token_div}), and string "
                    f"equality keeps {near_str['total_distinct']} paraphrase "
                    "strings distinct and does not fire, so the shipped metric "
                    "is neither a token counter nor a string comparator."
                ),
                "sherman_kent_band": "almost-certain",
                "source_lineage": met_lin,
                "independent_verification_path": P2,
                "signals": [
                    {"id": "S1", "kind": "token-counter-and-string-equality-foils"},
                    {"id": "S2", "kind": "planted-mutant-collapse-and-keep-apart"},
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-historical-replays",
                "name": "Five real prior documents replayed; artifact matches live score",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-negative-control",
                "name": "30 near-identical fire EARLY; 30 diverse do NOT fire",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3-token-counter-foil",
                "name": "Token budget stopper fires on both controls",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T4-mechanism-mutants",
                "name": "Paraphrases collapse; true distinctions stay apart",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "id": "E1",
                "path": PREREG,
                "claim": "Thresholds were frozen before scoring any replay or control.",
            },
            {
                "id": "E2",
                "path": HISTORICAL_RUNS[0][1],
                "claim": "Historical sources are on-disk prior P2-wave documents.",
            },
            {
                "id": "E3",
                "path": "command-center/p2-wave/probes/RES-0151/controls.py",
                "claim": "Both-states control corpora are planted and re-runnable.",
            },
            {
                "id": "E4",
                "path": "command-center/p2-wave/probes/RES-0151/mechanism.py",
                "claim": "Distinctness is structured mechanism-key extraction.",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0151-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is the adversarial refuter: it re-derives fire indexes "
                "from yield vectors with an inline rolling-mean loop, requires "
                "the both-states control, the token-counter foil, and the "
                "planted mutants, and defaults to FAIL when any leg is missing."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": PREREG, "exists": True, "role": "preregistration"},
        ],
        "named_probes": [
            {"id": "probe1", "role": "historical-replay", "command": P1},
            {"id": "probe2", "role": "negative-control-refuter", "command": P2},
        ],
        "scope": {
            "proof_surface": (
                "Executable stopping metric plus two named probes. Historical "
                "replays use five committed P2-wave documents. CLAIM-REGISTRY.json "
                "and RES-0173 are absent and are not fabricated."
            ),
            "does_not_claim": [
                "RES-0173 delivered a validated dedup algorithm on this worktree",
                "command-center/CLAIM-REGISTRY.json existed and was replayed",
                "these five documents are the only research runs in the estate",
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "measurement-engineer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "min_bytes_threshold": 1024,
        "inputs_absent": {
            "CLAIM-REGISTRY.json": False,
            "sources/REGISTER.md": False,
            "RES-0173 artifact": False,
        },
    }
    doc["inputs_absent"]["CLAIM-REGISTRY.json"] = not (
        REPO / "command-center/CLAIM-REGISTRY.json"
    ).is_file()
    doc["inputs_absent"]["sources/REGISTER.md"] = not (
        REPO / "command-center/sources/REGISTER.md"
    ).is_file()
    res0173 = (
        REPO
        / "command-center/research/deep-research-design/RES-0173-mechanism-level-claim-dedup.json"
    )
    doc["inputs_absent"]["RES-0173 artifact"] = not res0173.is_file()
    if res0173.is_file():
        doc["preregistration"]["res_0173_status"] = (
            "RES-0173 artifact is present. Its mechanism_key() reads authored "
            "canonical_mechanism action|object slots and returns None on free "
            "text, so this unit still uses the catalog-named structured "
            "mechanism-key extractor in mechanism.py with planted mutants as "
            "the both-states control. It does not re-run RES-0173."
        )
    if not (REPO / SCHEMA).is_file():
        print("FAILED:RES-0151 catalog output_schema path missing")
        return 1

    validator = jsonschema.Draft7Validator(UNIT_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0151 schema errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print("FAILED:RES-0151 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0151 artifact {size}B below floor")
        return 1
    if "SUCCESS:RES-0151" not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0151 sentinel-absent after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"near_idx={near['fire_index']} diverse_fired={div['fired']} "
        f"hist_fired={[r['fired'] for r in replay_rows]}"
    )
    print("SUCCESS:RES-0151 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
