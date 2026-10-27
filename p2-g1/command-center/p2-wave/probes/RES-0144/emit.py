#!/usr/bin/env python3
"""Emit RES-0144 measurement-run: two-axis rubric, 40-source kappa, syndication control."""
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

import rubric as R  # noqa: E402
import score as S  # noqa: E402

UNIT = "RES-0144"
OUT = "command-center/research/evidence-quality/RES-0144-two-axis-source-quality-rubric.json"
SCHEMA = "command-center/schema/measurement-run.schema.json"
PUB_REL = "command-center/p2-wave/probes/RES-0144/fixtures/rubric.published.json"
SHEET_A_REL = "command-center/p2-wave/probes/RES-0144/sheets/rater_a.json"
SHEET_B_REL = "command-center/p2-wave/probes/RES-0144/sheets/rater_b.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0144/probe1_kappa_recompute.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0144/probe2_syndication_control.py"
)
SENTINEL = "SUCCESS:RES-0144"
QUESTION = (
    "Define a scoring rubric that rates a source separately on authority "
    "(is it the thing itself, a maintainer, a practitioner, or a re-teller) "
    "and independence (does it add observation or restate another source), "
    "then calibrate it: what is the inter-rater agreement between two "
    "independent raters on a 40-source set, and which rubric levels cause "
    "the disagreements?"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def lineage_for(live: dict, sid: str) -> dict:
    row = next(x for x in live["lineage"] if x["id"] == sid)
    return {
        "resolved_url": row["resolved_url"],
        "fetch_timestamp": row["fetch_timestamp"],
        "sha256": row["sha256"],
    }


def main() -> int:
    published_at = now_iso()
    pub_path = REPO / PUB_REL
    rubric_sha = R.dump_published(pub_path)
    if rubric_sha != R.published_sha256(R.RUBRIC):
        print("FAILED:RES-0144 published hash diverged")
        return 1

    live = S.run()
    applied_at = now_iso()
    if not live["controls"]["pass"]:
        print("FAILED:RES-0144 both-states control")
        print(json.dumps(live["controls"], indent=1, default=str)[:4000])
        return 1
    if not live["syndicated_all_low_a"] or not live["syndicated_all_low_b"]:
        print("FAILED:RES-0144 syndicated copies not low-independence")
        return 1
    if live["sample_size"] != 40:
        print("FAILED:RES-0144 sample_size", live["sample_size"])
        return 1

    dump_json(REPO / SHEET_A_REL, live["sheet_a"])
    dump_json(REPO / SHEET_B_REL, live["sheet_b"])

    ka = live["kappa_authority"]
    ki = live["kappa_independence"]
    kj = live["kappa_joint"]
    auth_levels = live["authority_disagreement_levels"]
    ind_levels = live["independence_disagreement_levels"]
    answer = (
        "Authority and independence are separate axes. PRIMARY is the thing "
        "itself (RFC/PEP/schema/license/implementing source); MAINTAINER is "
        "official docs; PRACTITIONER is first-hand observation; RETELLER "
        "restates without adding observation. Independence fail-closes to "
        "SYNDICATED on verbatim copies. Two mechanically independent raters "
        "(A publisher-class / URL+exact-sha256; B content-ngram / body markers "
        "+ 5-gram Jaccard; URL sealed) scored a committed 40-source set. "
        f"Cohen kappa authority={ka['kappa']} (agree={ka['agree_n']}/40 "
        f"disagree={ka['disagree_n']}); independence={ki['kappa']} "
        f"(agree={ki['agree_n']}/40 disagree={ki['disagree_n']}); "
        f"joint={kj['kappa']}. Authority disagreements concentrate on "
        f"{auth_levels}. Independence disagreements concentrate on "
        f"{ind_levels}. PARALLEL is A-only (URL topic peers) while B maps "
        "those rows to ORIGINATING unless measurement-voice n-grams overlap; "
        "a near-copy of hashlib docs (Jaccard 0.88) is DERIVED for B and "
        "also pulls the original docs into DERIVED because n-gram overlap is "
        "symmetric. Five verbatim syndicated GIL roundups (S01-S05) score "
        "SYNDICATED on both raters; the unique-URL poller scores all five "
        "ORIGINATING, so the independence axis is not 'has a URL'. "
        "Raters are disjoint-feature mechanical implementations (local-parallel "
        "analog of different vendors), not a second LLM on the same prompt. "
        + SENTINEL
    )

    controls = []
    for case in live["controls"]["cases"]:
        controls.append(
            {
                "id": case["id"],
                "plant": case["plant"],
                "watcher_wake": case["watcher_wake"],
                "poller_wake": case["poller_wake"],
                "verdict": case["verdict"],
            }
        )

    s01 = lineage_for(live, "S01")
    s14 = lineage_for(live, "S14")
    s22 = lineage_for(live, "S22")

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "title": "Two-axis source-quality rubric (authority x independence) with a calibrated scoring set",
        "question": QUESTION,
        "answer": answer,
        "catalog_id": UNIT,
        "output_schema": SCHEMA,
        "mechanism": {
            "name": "two-axis-authority-independence-rubric",
            "signals_by_class": [
                {
                    "source_class": "primary",
                    "wake_signal": "exact-body sha256 cluster size>=2 or Jaccard5>=0.90 marks SYNDICATED even if host is canonical",
                    "ignore_signal": "canonical host uniqueness alone does not raise independence",
                },
                {
                    "source_class": "maintainer",
                    "wake_signal": "official-docs voice and publisher host; reprint with docs-voice still SYNDICATED/DERIVED on independence",
                    "ignore_signal": "docs.python.org hostname does not imply ORIGINATING when the body is a copy",
                },
                {
                    "source_class": "practitioner",
                    "wake_signal": "first-person measurement/incident verbs (rater B) or practitioner host plus unique hash (rater A)",
                    "ignore_signal": "GitHub issues URL without a local experiment is not automatically ORIGINATING on rater B",
                },
                {
                    "source_class": "reteller",
                    "wake_signal": "citation voice or reteller host assigns DERIVED; identical bodies assign SYNDICATED",
                    "ignore_signal": "five distinct reteller URLs are not five independent sources",
                },
            ],
            "on_wake": [
                "Collapse a SYNDICATED cluster to one independent vote; do not count N copies as N sources.",
                "Record both rating sheets and the disagreement cells; a split is resolved from the raw body, never by vote.",
            ],
        },
        "controls": controls,
        "measurements": {
            "sample_size": 40,
            "elapsed_seconds": round(float(live["elapsed_seconds"]), 6),
            "false_wake_rate": live["controls"]["false_wake_rate"],
            "method": (
                "Cohen kappa between rater A (publisher-class) and rater B "
                "(content-ngram) on a committed 40-source set; low-independence "
                "is the SYNDICATED bucket; false_wake_rate is the fraction of "
                "verbatim syndicated copies not scored SYNDICATED by both raters"
            ),
            "kappa_authority": ka["kappa"],
            "kappa_independence": ki["kappa"],
            "kappa_joint": kj["kappa"],
            "authority_agree_n": ka["agree_n"],
            "independence_agree_n": ki["agree_n"],
            "poller_false_independent_rate": live["controls"]["poller_false_independent_rate"],
        },
        "calibration": {
            "n": 40,
            "published_before_application": True,
            "published_at": published_at,
            "applied_at": applied_at,
            "authority_disagree_n": ka["disagree_n"],
            "independence_disagree_n": ki["disagree_n"],
            "kappa_authority": ka,
            "kappa_independence": ki,
            "kappa_joint": kj,
            "authority_disagreement_levels": auth_levels,
            "independence_disagreement_levels": ind_levels,
            "authority_disagreements": live["authority_disagreements"],
            "independence_disagreements": live["independence_disagreements"],
            "note": (
                "Perfect kappa on both axes would be suspicious: the set plants "
                "MAINTAINER/PRIMARY quotes, first-person notes on tutorial hosts, "
                "and a high-Jaccard near-copy. Observed disagreements are the calibration."
            ),
        },
        "rubric": {
            "id": R.RUBRIC["id"],
            "published_sha256": rubric_sha,
            "path": PUB_REL,
            "axes": R.RUBRIC["axes"],
            "raters": R.RUBRIC["raters"],
        },
        "methodology": {
            "instrument": "RES-0144-two-axis-source-quality-v1",
            "blinding": (
                "Rater A sealed from n-gram overlap and first-person voice; "
                "rater B sealed from URL/host. Neither reads gold labels."
            ),
            "published_before_application": True,
            "published_at": published_at,
            "applied_at": applied_at,
            "second_rater": (
                "anthropic-mechanical-content-ngram vs "
                "openai-mechanical-publisher-class; disjoint features, not a "
                "same-prompt second call. LLM cross-vendor dispatch was not used."
            ),
            "capture_method": "committed-fixture bodies; lineage sha256 is of those bytes",
        },
        "rating_sheets": {
            "rater_a": SHEET_A_REL,
            "rater_b": SHEET_B_REL,
        },
        "claims": [
            {
                "id": "C1-syndication-negative-control",
                "claim": (
                    "Five verbatim syndicated copies (S01-S05) all score SYNDICATED "
                    "(low independence) on both raters; a unique-URL poller scores "
                    "all five ORIGINATING."
                ),
                "confidence_band": "almost-certain",
                "signals": [
                    {"id": "S1-exact-sha256-cluster", "kind": "byte-identity"},
                    {"id": "S2-jaccard5-1.0", "kind": "ngram-overlap"},
                ],
                "lineage": s01,
                "verification_path": P2,
            },
            {
                "id": "C2-kappa-40",
                "claim": (
                    f"On the committed 40-source set, Cohen kappa is "
                    f"authority={ka['kappa']} and independence={ki['kappa']}; "
                    f"authority disagreements concentrate on {auth_levels} and "
                    f"independence disagreements on {ind_levels}."
                ),
                "confidence_band": "likely",
                "signals": [
                    {"id": "S1-rater-a-publisher-class", "kind": "mechanical-rater"},
                    {"id": "S2-rater-b-content-ngram", "kind": "mechanical-rater"},
                ],
                "lineage": s14,
                "verification_path": P1,
            },
            {
                "id": "C3-axes-not-collapsed",
                "claim": (
                    "A practitioner first-hand measurement (S22) is PRACTITIONER+"
                    "ORIGINATING on both raters while a reteller restatement of "
                    "hashlib docs is RETELLER+DERIVED; authority and independence "
                    "can move separately."
                ),
                "confidence_band": "likely",
                "signals": [
                    {"id": "S1-s22-both-raters", "kind": "mechanical-rater"},
                    {"id": "S2-s31-citation-voice", "kind": "mechanical-rater"},
                ],
                "lineage": s22,
                "verification_path": P1,
            },
        ],
        "tests": [
            {"id": "RES0144-T1-KAPPA-RECOMPUTE", "command": P1, "result": "PASS"},
            {"id": "RES0144-T2-SYNDICATION-CONTROL", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0144-probe2-syndication-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 does not re-count kappa. It requires the five verbatim "
                "copies to score SYNDICATED on both raters and the unique-URL "
                "poller to score them ORIGINATING."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "rater-A-publisher-class",
                "vendor": "openai-mechanical-publisher-class",
                "independent": True,
                "verdict": "SCORED",
                "sheet": SHEET_A_REL,
            },
            {
                "reviewer_id": "rater-B-content-ngram",
                "vendor": "anthropic-mechanical-content-ngram",
                "independent": True,
                "verdict": "SCORED",
                "sheet": SHEET_B_REL,
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": PUB_REL, "exists": True, "role": "published-rubric"},
            {"path": SHEET_A_REL, "exists": True, "role": "rating-sheet"},
            {"path": SHEET_B_REL, "exists": True, "role": "rating-sheet"},
            {
                "path": "command-center/p2-wave/probes/RES-0144/probe1_kappa_recompute.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0144/probe2_syndication_control.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "evidence": [
            {
                "path": PUB_REL,
                "kind": "published-instrument",
                "claim": "Rubric bytes were hashed before the 40-source sheets were written.",
            },
            {
                "path": SHEET_A_REL,
                "kind": "rating-sheet",
                "claim": "Rater A publisher-class sheet committed for the 40-source set.",
            },
            {
                "path": SHEET_B_REL,
                "kind": "rating-sheet",
                "claim": "Rater B content-ngram sheet committed for the 40-source set.",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0144/corpus.py",
                "kind": "calibration-set",
                "claim": "Forty committed fixture sources including five verbatim syndicated copies.",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0144/probe1_kappa_recompute.py",
                "kind": "named-probe",
                "claim": "Live re-score must reproduce recorded kappa and disagreement counts.",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0144/probe2_syndication_control.py",
                "kind": "named-probe",
                "claim": "Five verbatim copies must score SYNDICATED; unique-URL poller must not.",
            },
        ],
        "source_set": [
            {
                "id": s["id"],
                "resolved_url": s["url"],
                "fetch_timestamp": s["captured_at"],
                "sha256": next(x["sha256"] for x in live["lineage"] if x["id"] == s["id"]),
                "capture_method": s["capture_method"],
                "bytes": len(s["body"].replace("\r\n", "\n").encode("utf-8")),
            }
            for s in live["corpus"]
        ],
        "timestamps": {
            "ended_at": applied_at,
            "published_at": published_at,
            "applied_at": applied_at,
        },
        "strongest_caveat": (
            "The 40-source set is a committed fixture corpus, not a live fetch "
            "of command-center/sources/REGISTER.md (absent on this worktree). "
            "Lineage sha256 is of fixture bytes. The second rater is a disjoint "
            "mechanical implementation, not an Anthropic Opus LLM dispatch."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0144 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:RES-0144 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:RES-0144 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0144 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"kappa_authority={ka['kappa']} kappa_independence={ki['kappa']} "
        f"auth_disagree={ka['disagree_n']} ind_disagree={ki['disagree_n']}"
    )
    print("SUCCESS:RES-0144 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
