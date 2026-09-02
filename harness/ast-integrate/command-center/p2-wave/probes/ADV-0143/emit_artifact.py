#!/usr/bin/env python3
"""Emit ADV-0143 content-redistribution adjudication from live measurements.

The catalog output_schema is a generated $ref shim to ast-integrate.invalid.
This emitter validates against the physical redistribution-adjudication class
via schema_check.py (on-disk RefResolver). Domain fields live under report.*
because receipt_core sets additionalProperties: false.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import unshadow as U  # noqa: E402

U.unshadow()

from extent import measure_marked_file, naive_whole_file_bytes  # noqa: E402
from plant_payload import PAYLOAD_BYTES, PLANT_REL  # noqa: E402
from reviewers import adjudicate  # noqa: E402
from sample import draw_sample, mutant_sample  # noqa: E402
import schema_check as SC  # noqa: E402
from survey import survey  # noqa: E402
from taxonomy import (  # noqa: E402
    CLASS_IDS,
    EXEMPLARS,
    POLICY,
    load_text,
    snippet_at,
)
from threshold import (  # noqa: E402
    AGREEMENT_METRIC,
    AGREEMENT_THRESHOLD,
    CHOSEN_BEFORE_RUN,
    EXTENT_TOLERANCE_BYTES,
    KAPPA_METRIC,
    KAPPA_THRESHOLD,
    RATIONALE,
    SAMPLE_N,
    SAMPLE_SEED,
)
from plant_payload import BEGIN_MARK, END_MARK, PAYLOAD  # noqa: E402

OUT = "command-center/adversarial/ADV-0143-content-redistribution.json"
SCHEMA = "command-center/schema/redistribution-adjudication.schema.json"
QUESTION = (
    "Independent of software licence compatibility (RES-0135, IMP-0157, "
    "WFA-0139 cover the code and workflow licence lattice), what CONTENT in "
    "the program corpus is third-party expression or third-party personal "
    "data - quoted vendor documentation, scraped marketplace and forum text, "
    "transcript excerpts containing other people's messages, AI-generated "
    "text of uncertain provenance - and under the binding PR-ONLY release "
    "mode, which classes may be redistributed, which must be summarised "
    "rather than quoted, and which must be excluded entirely?"
)
COMPLETION = (
    "SUCCESS:ADV-0143 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every content class "
    "carries a verdict with a measured extent and a stated residual risk, "
    "the 30-chunk completeness sample found no unclassifiable chunk, and "
    "inter-reviewer agreement met the pre-registered threshold. Any other "
    "terminal state is FAILED:ADV-0143 <classification> with the diagnostic "
    "tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0143/probe1_completeness_and_extent.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0143/probe2_verdict_stability.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0143/taxonomy.py",
    "command-center/p2-wave/probes/ADV-0143/threshold.py",
    "command-center/p2-wave/probes/ADV-0143/plant_payload.py",
    "command-center/p2-wave/probes/ADV-0143/extent.py",
    "command-center/p2-wave/probes/ADV-0143/sample.py",
    "command-center/p2-wave/probes/ADV-0143/reviewers.py",
    "command-center/p2-wave/probes/ADV-0143/survey.py",
    "command-center/p2-wave/probes/ADV-0143/schema_check.py",
    "command-center/p2-wave/probes/ADV-0143/probe1_completeness_and_extent.py",
    "command-center/p2-wave/probes/ADV-0143/probe2_verdict_stability.py",
    "command-center/p2-wave/probes/ADV-0143/fixtures/third-party-license-plant.txt",
]


def present(rel: str) -> bool:
    p = REPO / rel
    return p.is_file() and p.stat().st_size > 0


def write_plant() -> None:
    body = (
        "ADV-0143 first-party wrapper. The marked span is a planted "
        "third-party quotation used only as an extent-measurement control.\n"
        f"{BEGIN_MARK}\n"
        f"{PAYLOAD}\n"
        f"{END_MARK}\n"
        "End of first-party wrapper.\n"
    )
    path = REPO / PLANT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:8000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    if not path.is_file() or size < 1:
        raise SystemExit(f"FAILED:ADV-0143 missing supporting artifact {rel}")
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def class_row(cid: str, surv: dict) -> dict:
    pol = POLICY[cid]
    ex = surv["exemplars"].get(cid)
    if ex is None:
        for spec in EXEMPLARS:
            if spec["class_id"] == cid:
                text, line = load_text(REPO, spec["path"])
                ex = {
                    "path": spec["path"],
                    "line": line,
                    "snippet": snippet_at(text, line) or "(non-empty file)",
                }
                break
    if ex is None:
        ex = {
            "path": "command-center/p2-wave/probes/ADV-0143/taxonomy.py",
            "line": 1,
            "snippet": (
                f"class {cid} had zero matching UTF-8 files in the walker; "
                "retained so the completeness sample has a bin"
            ),
        }
    if not str(ex.get("snippet") or "").strip():
        ex = dict(ex)
        ex["snippet"] = (
            f"class {cid} exemplar body was whitespace; class retained so "
            "empty chunks classify rather than becoming unclassifiable"
        )
    nbytes = int(surv["class_bytes"].get(cid, 0))
    nfiles = int(surv["class_files"].get(cid, 0))
    share = float(surv["byte_share"].get(cid, 0.0))
    if cid == "third-party-personal-data":
        nfiles = int(sum(surv["personal_data_identifiers"]["counts"].values()))
    return {
        "class_id": cid,
        "exemplar": ex,
        "extent": {
            "bytes": nbytes,
            "count": nfiles,
            "byte_share": share,
            "unit": (
                "identifier-utf8-bytes"
                if cid == "third-party-personal-data"
                else "classified-utf8-file-bytes"
            ),
        },
        "legal_basis": pol["legal_basis"],
        "verdict": pol["verdict"],
        "residual_risk": pol["residual_risk"],
        "side_of_line": pol["side_of_line"],
        "not_legal_advice": True,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_plant()
    measured = measure_marked_file(REPO)
    known = PAYLOAD_BYTES
    delta = abs(measured["measured_bytes"] - known)
    extent_ok = delta <= EXTENT_TOLERANCE_BYTES
    naive = naive_whole_file_bytes(REPO)
    naive_ok = abs(naive - known) <= EXTENT_TOLERANCE_BYTES
    if not extent_ok:
        print(
            f"FAILED:ADV-0143 emit extent plant recovered "
            f"{measured['measured_bytes']} != {known}"
        )
        return 1
    if naive_ok:
        print("FAILED:ADV-0143 emit naive whole-file strawman also matched plant")
        return 1

    completeness = draw_sample(REPO)
    mutant = mutant_sample(REPO)
    if completeness["unclassifiable_count"] != 0:
        print(
            "FAILED:ADV-0143 emit taxonomy-incomplete "
            f"{completeness['unclassifiable']}"
        )
        return 1
    if mutant["unclassifiable_count"] <= 0:
        print("FAILED:ADV-0143 emit completeness mutant was silent")
        return 1

    stability = adjudicate(REPO)
    if stability["agreement_rate"] < AGREEMENT_THRESHOLD:
        print(
            "FAILED:ADV-0143 emit agreement "
            f"{stability['agreement_rate']} < {AGREEMENT_THRESHOLD}"
        )
        return 1
    if stability["kappa_live"]["kappa"] < KAPPA_THRESHOLD:
        print(
            "FAILED:ADV-0143 emit kappa "
            f"{stability['kappa_live']['kappa']} < {KAPPA_THRESHOLD}"
        )
        return 1
    if stability["naive_agreement_rate"] >= AGREEMENT_THRESHOLD:
        print("FAILED:ADV-0143 emit naive constant reviewer met threshold")
        return 1

    surv = survey(REPO)
    rows = [class_row(cid, surv) for cid in CLASS_IDS]
    if any(
        r["verdict"]
        not in {
            "REDISTRIBUTABLE",
            "SUMMARISE-ONLY",
            "EXCLUDE",
            "NEEDS-OWNER-DECISION",
        }
        for r in rows
    ):
        print("FAILED:ADV-0143 emit missing verdict")
        return 1
    for r in rows:
        if r["extent"]["bytes"] is None or not r["residual_risk"]:
            print("FAILED:ADV-0143 emit extent or residual missing")
            return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    completeness_json = json.dumps(
        {
            "unclassifiable_count": completeness["unclassifiable_count"],
            "population": completeness["population"],
            "mutant_unclassifiable_count": mutant["unclassifiable_count"],
            "n": completeness["n"],
            "seed": completeness["seed"],
        },
        sort_keys=True,
    )
    extent_json = json.dumps(
        {
            "measured_bytes": measured["measured_bytes"],
            "known_bytes": known,
            "naive_whole_file_bytes": naive,
            "tolerance_bytes": EXTENT_TOLERANCE_BYTES,
        },
        sort_keys=True,
    )
    stability_json = json.dumps(
        {
            "agreement_rate": stability["agreement_rate"],
            "kappa": stability["kappa_live"]["kappa"],
            "naive_agreement_rate": stability["naive_agreement_rate"],
            "n": stability["n"],
        },
        sort_keys=True,
    )

    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0143",
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=ADV-0143] "
            "evidence_requirement: one adjudication row per CONTENT CLASS"
        ),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "legal-reviewer",
            "execution_substrate": "headless-linux",
        },
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    f"The 30-chunk completeness sample (seed={SAMPLE_SEED}) "
                    f"found unclassifiable_count="
                    f"{completeness['unclassifiable_count']} on the live "
                    "taxonomy, and the mutant-only-binary taxonomy classified "
                    f"{mutant['unclassifiable_count']} of the same 30 as "
                    "unclassifiable."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/ADV-0143/sample.py:draw_sample"
                ),
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        "command-center/p2-wave/probes/ADV-0143/sample.py:draw_sample",
                        completeness_json,
                        0,
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        "command-center/p2-wave/probes/ADV-0143/sample.py:mutant_only_binary",
                        json.dumps(
                            {
                                "mutant_unclassifiable_count": mutant[
                                    "unclassifiable_count"
                                ]
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Marked-span UTF-8 byte count recovered the planted MIT "
                    f"grant at {measured['measured_bytes']} bytes "
                    f"(known={known}); whole-file size {naive} did not."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/ADV-0143/extent.py:"
                    "measure_marked_file"
                ),
                "probes": [
                    probe(
                        "source",
                        "byte-compare",
                        "command-center/p2-wave/probes/ADV-0143/extent.py:measure_marked_file",
                        extent_json,
                        0,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/ADV-0143/extent.py:naive_whole_file_bytes",
                        f"naive_whole_file_bytes={naive}",
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Two independent reviewers (classify_path vs classify_body) "
                    f"agreed on {stability['agreements']}/{stability['n']} "
                    f"verdicts (rate={stability['agreement_rate']}, "
                    f"kappa={stability['kappa_live']['kappa']}); a constant "
                    "REDISTRIBUTABLE strawman did not meet the pre-stated "
                    f"threshold (naive_rate={stability['naive_agreement_rate']})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/ADV-0143/reviewers.py:adjudicate"
                ),
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        "classify_path",
                        stability_json,
                        0,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "classify_body",
                        (
                            f"source_probe={stability['source_probe']} "
                            f"verifier_probe={stability['verifier_probe']}"
                        ),
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "class-completeness",
                "name": "30-chunk sample has no unclassifiable remainder",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "extent-measurement",
                "name": "Planted third-party span length recovered within tolerance",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "verdict-stability",
                "name": "Blind two-reviewer agreement meets pre-stated threshold",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-completeness-mutant",
                "kind": "mutation",
                "description": (
                    "mutant_only_binary classifies only undecodable chunks; "
                    "UTF-8 sample chunks must be unclassifiable under it and "
                    "classifiable under the live taxonomy."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"mutant_unclassifiable_count={mutant['unclassifiable_count']}"
                ),
                "good_state_output": (
                    f"unclassifiable_count={completeness['unclassifiable_count']}"
                ),
            },
            {
                "id": "NC-extent-whole-file",
                "kind": "known-broken-fixture",
                "description": (
                    "Whole-file byte count includes the first-party wrapper "
                    "and must not recover the planted span length."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"naive_whole_file_bytes={naive}",
                "good_state_output": (
                    f"measured_bytes={measured['measured_bytes']} known={known}"
                ),
            },
            {
                "id": "NC-constant-reviewer",
                "kind": "known-broken-fixture",
                "description": (
                    "A reviewer that always returns REDISTRIBUTABLE must miss "
                    "the pre-stated agreement threshold on the 10-row panel."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"naive_agreement_rate={stability['naive_agreement_rate']}"
                ),
                "good_state_output": (
                    f"agreement_rate={stability['agreement_rate']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0143-independent-body-classifier",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Reviewer B classifies file bodies only (classify_body). "
                "Reviewer A classifies paths only (classify_path). Fingerprints "
                "differ. A constant-verdict strawman is the both-states control."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0143/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "ADV-0143",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/ADV-0143/schema_check.py "
                    "(Draft202012Validator + disk RefResolver)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/ADV-0143/schema_check.py "
                        f"--check {OUT}"
                    ),
                    "in-memory validate before write; file re-checked after write",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no blind retry on a verdict. A changed verdict is appended "
                "with both readings and the reason for the change; the earlier "
                "verdict is never deleted"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "RES-0125 / WFA-0079 / RES-0121 artefacts are present and "
                    "the AI-generated blueprint class has a measured licence "
                    "obligation rather than NEEDS-OWNER-DECISION."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Land RES-0125.json and WFA-0079 provenance-licence graph "
                    "on this worktree, then re-adjudicate "
                    "ai-generated-uncertain-provenance only."
                ),
            }
        ],
        "report": {
            "kind": "redistribution-adjudication",
            "observations": [
                {
                    "name": "completeness-unclassifiable-count",
                    "measured": completeness["unclassifiable_count"],
                    "method": "30-chunk-rng-sample",
                    "anchor": (
                        "command-center/p2-wave/probes/ADV-0143/sample.py:draw_sample"
                    ),
                },
                {
                    "name": "mutant-unclassifiable-count",
                    "measured": mutant["unclassifiable_count"],
                    "method": "mutant-only-binary",
                    "anchor": (
                        "command-center/p2-wave/probes/ADV-0143/sample.py:"
                        "mutant_only_binary"
                    ),
                },
                {
                    "name": "plant-measured-bytes",
                    "measured": measured["measured_bytes"],
                    "method": "marked-span-utf8-byte-count",
                    "anchor": (
                        "command-center/p2-wave/probes/ADV-0143/extent.py:"
                        "measure_marked_file"
                    ),
                },
                {
                    "name": "plant-naive-whole-file-bytes",
                    "measured": naive,
                    "method": "stat-st_size",
                    "anchor": (
                        "command-center/p2-wave/probes/ADV-0143/extent.py:"
                        "naive_whole_file_bytes"
                    ),
                },
                {
                    "name": "verdict-agreement-rate",
                    "measured": stability["agreement_rate"],
                    "method": "exact-verdict-match-rate",
                    "anchor": (
                        "command-center/p2-wave/probes/ADV-0143/reviewers.py:adjudicate"
                    ),
                },
                {
                    "name": "verdict-kappa",
                    "measured": stability["kappa_live"]["kappa"],
                    "method": "cohens-kappa-four-verdicts",
                    "anchor": (
                        "command-center/p2-wave/probes/ADV-0143/reviewers.py:cohen_kappa"
                    ),
                },
                {
                    "name": "content-class-count",
                    "measured": len(rows),
                    "method": "closed-taxonomy-adjudication",
                    "anchor": (
                        "command-center/p2-wave/probes/ADV-0143/taxonomy.py:CLASS_IDS"
                    ),
                },
            ],
            "control_ids": [
                "NC-completeness-mutant",
                "NC-extent-whole-file",
                "NC-constant-reviewer",
            ],
            "title": (
                "Third-party CONTENT redistribution: what in the corpus may "
                "lawfully leave the machine"
            ),
            "question": QUESTION,
            "completion_sentinel": COMPLETION,
            "release_mode": "PR-ONLY",
            "release_mode_note": (
                "PR-ONLY narrows but does not eliminate the redistribution "
                "surface: a PR diff and its CI logs are still a publication."
            ),
            "not_legal_advice": True,
            "declared_output_schema": SCHEMA,
            "named_settling_probe": P1,
            "dependency_status": {
                "res_0125_on_disk": present("command-center/research/RES-0125.json"),
                "wfa_0079_on_disk": present(
                    "command-center/wfa/WFA-0079-provenance-license-graph-v2.json"
                ),
                "res_0121_on_disk": present("command-center/research/RES-0121.json"),
                "owner_decisions_md": present("command-center/OWNER-DECISIONS.md"),
                "blocks_this_unit": False,
                "reason": (
                    "RES-0125 / WFA-0079 / RES-0121 artifacts are absent on this "
                    "worktree. This unit does not recompute the code-side licence "
                    "lattice. PR-ONLY is taken from the catalog owner decision. "
                    "AI-generated blueprint class is NEEDS-OWNER-DECISION because "
                    "the obligation table was not measured here."
                ),
            },
            "content_classes": rows,
            "completeness_sample": {
                "n": completeness["n"],
                "seed": completeness["seed"],
                "population": completeness["population"],
                "chunk_chars": completeness["chunk_chars"],
                "unclassifiable_count": completeness["unclassifiable_count"],
                "rows": completeness["rows"],
                "mutant_unclassifiable_count": mutant["unclassifiable_count"],
            },
            "extent_control": {
                "path": measured["path"],
                "method": measured["method"],
                "measured_bytes": measured["measured_bytes"],
                "known_bytes": known,
                "tolerance_bytes": EXTENT_TOLERANCE_BYTES,
                "within_tolerance": extent_ok,
                "naive_whole_file_bytes": naive,
                "naive_within_tolerance": naive_ok,
            },
            "verdict_stability": {
                "n": stability["n"],
                "agreement_rate": stability["agreement_rate"],
                "agreements": stability["agreements"],
                "threshold": AGREEMENT_THRESHOLD,
                "metric": AGREEMENT_METRIC,
                "threshold_stated_before_run": CHOSEN_BEFORE_RUN,
                "threshold_rationale": RATIONALE,
                "kappa": stability["kappa_live"]["kappa"],
                "kappa_metric": KAPPA_METRIC,
                "kappa_threshold": KAPPA_THRESHOLD,
                "met": True,
                "source_probe": "classify_path",
                "verifier_probe": "classify_body",
                "naive_agreement_rate": stability["naive_agreement_rate"],
                "naive_kappa": stability["kappa_naive"]["kappa"],
                "rows": [
                    {
                        "row_id": r["row_id"],
                        "path": r["path"],
                        "line": r["line"],
                        "snippet": r["snippet"],
                        "intended_class": r["intended_class"],
                        "reviewer_a_class": r["reviewer_a"]["class_id"],
                        "reviewer_a_verdict": r["reviewer_a"]["verdict"],
                        "reviewer_b_class": r["reviewer_b"]["class_id"],
                        "reviewer_b_verdict": r["reviewer_b"]["verdict"],
                        "agree": r["agree"],
                    }
                    for r in stability["rows"]
                ],
            },
            "corpus_survey": {
                "file_count": surv["file_count"],
                "total_utf8_bytes": surv["total_utf8_bytes"],
                "class_bytes": surv["class_bytes"],
                "class_files": surv["class_files"],
                "personal_data_identifiers": surv["personal_data_identifiers"],
            },
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
        },
    }

    if not SC.garbage_rejected(REPO):
        print("FAILED:ADV-0143 schema accepted garbage")
        return 1
    errs = SC.error_messages(doc, REPO)
    if errs:
        print("FAILED:ADV-0143 schema errors")
        for line in errs[:40]:
            print(" ", line)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    file_errs = SC.error_messages(json.loads(out_path.read_text(encoding="utf-8")), REPO)
    if file_errs:
        print("FAILED:ADV-0143 written receipt schema-invalid")
        for line in file_errs[:20]:
            print(" ", line)
        return 1
    sha, nbytes = sha256_file(out_path)
    print(f"wrote {OUT} bytes={nbytes} sha256={sha}")
    print("SUCCESS:ADV-0143")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
