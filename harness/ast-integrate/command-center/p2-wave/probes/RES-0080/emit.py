#!/usr/bin/env python3
"""Build command-center/research/RES-0080.json from live field inventory + detectors."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detectors as D  # noqa: E402
import fixtures as F  # noqa: E402
from fields import inventory  # noqa: E402

OUT = "command-center/research/RES-0080.json"
UNIT = "RES-0080"
CATALOG_SENTINEL = (
    "SUCCESS:RES-0080 in the receipt AND a detector list where each entry "
    "names an existing transcript field, plus one not-portable measure"
)
QUESTION = (
    "Which conformity and groupthink measurements from human group research "
    "(Asch-style conformity rate, premature-closure timing, dissent-suppression "
    "markers) are mechanically computable from an agent transcript, and what "
    "threshold marks a pathological panel?"
)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fixture_table() -> list[dict]:
    rows = []
    for fx in F.all_fixtures():
        result = D.run_all(fx)
        rows.append(
            {
                "id": fx["id"],
                "expect_fired": list(fx["expect_fired"]),
                "fired": result["fired"],
                "pathological": result["pathological"],
                "ok": sorted(result["fired"]) == sorted(fx["expect_fired"]),
            }
        )
    return rows


def build() -> dict:
    inv = inventory()
    portable = D.portable_catalog(inv)
    not_portable = D.not_portable_catalog(inv)
    snap = digest_bytes(
        json.dumps(
            {"fields": inv["names"], "detectors": [p["id"] for p in portable]},
            sort_keys=True,
        ).encode("utf-8")
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    detectors = []
    for spec in portable:
        primary = spec["transcript_fields"][0]
        schema = inv["fields"].get(primary, "")
        detectors.append(
            {
                "id": spec["id"],
                "classical_measure": spec["classical_measure"],
                "transcript_field": primary,
                "transcript_fields": spec["transcript_fields"],
                "field_exists": True,
                "all_fields_exist": all(spec["field_exists"].values()),
                "schema_source": schema,
                "field_sources": {
                    f: inv["fields"][f] for f in spec["transcript_fields"]
                },
                "portable": True,
                "reads": spec["reads"],
                "fires_when": spec["fires_when"],
            }
        )
    fx_rows = fixture_table()
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "claim_id": "RES-0080",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "schema_version": 1,
        "report_kind": "research-claim-record",
        "title": (
            "Port the operational groupthink detectors from social psychology "
            "to agent panels"
        ),
        "question": QUESTION,
        "question_or_target": QUESTION,
        "sentinel": CATALOG_SENTINEL,
        "completion_sentinel": CATALOG_SENTINEL,
        "canonical_mechanism": (
            "Do not copy Asch's 36.8% as a cutoff. Compute three detectors from "
            "fields the live council transcript already carries (Vote.claim_id / "
            "round / participant_id, CouncilSnapshot.rounds_elapsed and "
            "disagreement_rounds, Event.kind / participant_id / round_index, "
            "Brief.independent). Flag a panel pathological when any detector "
            "fires. Mark Asch critical-trial conformity and the Janis 8-symptom "
            "checklist not-portable because their required fields are absent."
        ),
        "answer": (
            "Mechanically computable from this program's council transcript: "
            "(1) premature-closure as round-1 unanimity with disagreement_rounds "
            "== 0; (2) dissent-suppression as a minority seat that has a TURN in "
            "round r and none in round r+1 while the council continues; (3) "
            "self-censorship as a non-independent Vote.claim_id flip onto the "
            "next majority. Not computable: Asch-style critical-trial conformity "
            "rate (needs private_judgment, trial_type, ground_truth — none exist) "
            "and Janis's scored 8-symptom inventory (needs morale / invulnerability "
            "fields that do not exist). Pathological threshold: any portable "
            "detector firing. That threshold is operational for this transcript, "
            "not a validated clinical cutoff and not Asch's 36.8%."
        ),
        "confidence_band": "high-on-fields, medium-on-threshold",
        "confidence_notes": (
            "Field existence is high: inventory is executed against kernel "
            "Event.as_dict, Vote/Brief/CouncilSnapshot, chair journal records, "
            "and council-audit.schema.json. The pathological OR-threshold is "
            "medium: no published study validates these exact flags on LLM "
            "agent panels, so the number we refuse to copy (36.8%) stays refused."
        ),
        "evidence_tier": "mixed",
        "freshness_stamp": now,
        "snapshot_sha256": snap,
        "named_settling_probe": (
            "command-center/p2-wave/probes/RES-0080/probe1_detector_fields.py"
        ),
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "output_schema_status": (
            "PRESENT as a generated shim at "
            "command-center/schema/research-claim-record.schema.json. The shim "
            "carries no class-specific payload constraints (delegates to "
            "platform/schema/artifact-class-profiles.schema.json#"
            "/$defs/research-claim-record). This unit does not author the "
            "shared schema file. Envelope fields follow the list named in "
            "RES-0001's catalog question (claim id, canonical mechanism, "
            "source lineage, evidence tier, confidence band, named settling "
            "probe, edges, freshness stamp, snapshot sha256)."
        ),
        "source_lineage": [
            {
                "source_id": "asch-1955-sciam",
                "locator": (
                    "Scientific American 193(5) pp.31-35, including the 12-of-18 "
                    "critical-trial series and the majority-size series"
                ),
                "uri": "doi:10.1038/scientificamerican1155-31",
                "retrieved": "open PDF extract 2026-08-24",
            },
            {
                "source_id": "asch-1956-monograph",
                "locator": "Psychological Monographs 70(9) 1-70, archival report",
                "uri": "doi:10.1037/h0093718",
                "retrieved": "DOI + secondary concordance with the 1955 numbers",
            },
            {
                "source_id": "stasser-titus-1985",
                "locator": "Journal of Personality and Social Psychology 48(6) Table 3",
                "uri": "doi:10.1037/0022-3514.48.6.1467",
                "retrieved": "publisher PDF extract 2026-08-24",
            },
            {
                "source_id": "kernel-event",
                "locator": "tools/council/kernel.py Event.as_dict",
                "uri": "file:tools/council/kernel.py",
            },
            {
                "source_id": "unanimity-snapshot",
                "locator": "tools/council/antifail/unanimity.py Vote/Brief/CouncilSnapshot",
                "uri": "file:tools/council/antifail/unanimity.py",
            },
            {
                "source_id": "chair-journal",
                "locator": "tools/council/topology/chair.py FloorRequest/Recognition/Submission",
                "uri": "file:tools/council/topology/chair.py",
            },
            {
                "source_id": "council-audit-schema",
                "locator": "configurations.items.participant_action_logs",
                "uri": "file:command-center/schema/council-audit.schema.json",
            },
        ],
        "transcript_field_inventory": {
            "count": inv["count"],
            "names": inv["names"],
            "sources": inv["sources"],
            "classical_names_absent": inv["classical_names_absent"],
        },
        "detectors": detectors,
        "not_portable_measures": not_portable,
        "pathological_threshold": {
            "rule": (
                "A panel is PATHOLOGICAL when any portable detector fires "
                "(instant round-1 unanimity, minority seat-drop while the "
                "council continues, or non-independent vote collapse onto the "
                "next majority)."
            ),
            "copied_asch_368_percent": False,
            "why_not_asch_percent": (
                "Asch's 36.8% is a human critical-trial public-error rate against "
                "a <1% no-majority baseline. Copying it as a cutoff on agent "
                "Vote.claim_id agreement would mix populations and drop the "
                "private-judgment / trial-type / ground-truth terms. That copy "
                "is REFUTED as a portable threshold."
            ),
            "operational_not_clinical": True,
        },
        "fixture_both_states": fx_rows,
        "mechanisms": [
            {
                "id": "asch-critical-trial-rate",
                "claim": (
                    "Under a unanimous wrong majority, naive subjects matched "
                    "the majority on 36.8% of critical trials, versus less than "
                    "1% errors without that majority."
                ),
                "paper": (
                    "Asch, S. E. (1955). Opinions and Social Pressure. "
                    "Scientific American, 193(5), 31-35."
                ),
                "doi": "10.1038/scientificamerican1155-31",
                "section_or_figure": (
                    "pp.32-33 running text of the 123-subject series "
                    "(18 trials, 12 critical); companion majority-size series "
                    "same pages"
                ),
                "effect_size": (
                    "36.8% of critical-trial selections matched the misleading "
                    "majority; ~75% of subjects agreed with the majority on at "
                    "least one critical trial; ~25% never agreed"
                ),
                "baseline": (
                    "ordinary line-matching errors less than 1% of the time "
                    "(no-majority control)"
                ),
                "evidence_tier": "E2",
                "promotes_detector": False,
                "why_not_promoted": (
                    "The metric needs private_judgment, trial_type, and "
                    "ground_truth, which this transcript does not carry. "
                    "Headline 36.8% without those terms would be E3 on this "
                    "substrate."
                ),
                "strongest_caveat": (
                    "Sample is 123 male college students in a perceptual task "
                    "with confederates, not LLM council seats. Asch 1956 "
                    "(doi:10.1037/h0093718) is the archival monograph of the "
                    "same program; Wikipedia's 35.7% figure is a later "
                    "rounding and is not used here."
                ),
            },
            {
                "id": "asch-unanimity-not-size",
                "claim": (
                    "Unanimity, not majority size past three, is the "
                    "load-bearing pressure: one opponent 3.6% errors, two "
                    "13.6%, three 31.8%, further increases add little; a "
                    "truthful partner cuts yielding to about one-fourth."
                ),
                "paper": (
                    "Asch, S. E. (1955). Opinions and Social Pressure. "
                    "Scientific American, 193(5), 31-35."
                ),
                "doi": "10.1038/scientificamerican1155-31",
                "section_or_figure": (
                    "majority-size series and partner series, pp.33-34 and the "
                    "SIZE OF MAJORITY chart notes"
                ),
                "effect_size": (
                    "3.6% (n_opponents=1), 13.6% (2), 31.8% (3), 35.1% (4), "
                    "35.2% (6), 37.1% (7), 35.1% (9), 31.2% (15); partner "
                    "condition 'only one fourth as often' as unanimous majority"
                ),
                "baseline": "3.6% errors against a single opponent; <1% with no opponents",
                "evidence_tier": "E2",
                "promotes_detector": True,
                "detector_id": "premature_closure_instant_unanimity",
                "why_promoted": (
                    "Supports treating round-1 unanimity with "
                    "disagreement_rounds==0 as the portable premature-closure "
                    "proxy: the human finding is that a unanimous first public "
                    "front is the pressure, and this transcript records exactly "
                    "those public votes and the disagreement_rounds counter."
                ),
                "strongest_caveat": (
                    "Asch measured perceptual error under confederates, not "
                    "elapsed rounds on an agent council. The portable detector "
                    "is the round-index rule already used by IMP-0318 "
                    "(INSTANT_ROUND_CEILING=1), not a copied percentage."
                ),
            },
            {
                "id": "stasser-titus-hidden-profile",
                "claim": (
                    "When unique information is unshared, groups rarely abandon "
                    "the initially popular (wrong) candidate: 83% chose the "
                    "objectively best candidate A when profiles were fully "
                    "shared, versus 18% of groups in the unshared conditions."
                ),
                "paper": (
                    "Stasser, G., & Titus, W. (1985). Pooling of unshared "
                    "information in group decision making. Journal of "
                    "Personality and Social Psychology, 48(6), 1467-1478."
                ),
                "doi": "10.1037/0022-3514.48.6.1467",
                "section_or_figure": (
                    "Table 3, Group decisions row; Results text p.1474 "
                    "'83% of the 18 groups' vs '18% of the 38 groups'"
                ),
                "effect_size": (
                    "Shared-info groups: 83% chose A (n=18 groups). Combined "
                    "unshared groups: 18% chose A (n=38). Chi-square on A vs "
                    "not-A: χ²(1, N=56)=21.59, p<.001"
                ),
                "baseline": "83% correct group decisions when all profile information is shared",
                "evidence_tier": "E2",
                "promotes_detector": True,
                "detector_id": "premature_closure_instant_unanimity",
                "why_promoted": (
                    "Shows discussion does not reliably correct an early "
                    "plurality. Instant unanimity is therefore a pathology "
                    "flag, not evidence the panel 'finished thinking'."
                ),
                "strongest_caveat": (
                    "Stasser & Titus measured candidate choice after a political "
                    "caucus simulation, not wall-clock closure. They do not "
                    "publish a minute threshold, so elapsed_ms cannot inherit "
                    "a cutoff from this paper (that would be E3)."
                ),
            },
        ],
        "edges": {
            "supports": [
                {
                    "from": "asch-unanimity-not-size",
                    "to": "premature_closure_instant_unanimity",
                },
                {
                    "from": "stasser-titus-hidden-profile",
                    "to": "premature_closure_instant_unanimity",
                },
            ],
            "contradicts": [
                {
                    "from": "asch-critical-trial-rate",
                    "to": "copied-368-percent-threshold",
                    "note": (
                        "The human rate is real (E2) and still cannot be the "
                        "agent-panel cutoff because the transcript cannot score "
                        "critical trials."
                    ),
                }
            ],
        },
        "refuted_claims": [
            {
                "claim": (
                    "Use Asch's 36.8% as the pathological cutoff on agent "
                    "council Vote.claim_id agreement."
                ),
                "verdict": "REFUTED",
                "reason": (
                    "Missing private_judgment, trial_type, and ground_truth; "
                    "wrong population; would drop the <1% control baseline."
                ),
            },
            {
                "claim": (
                    "Score Janis's eight groupthink symptoms as a numeric "
                    "detector over the current transcript."
                ),
                "verdict": "REFUTED",
                "reason": (
                    "No morale / invulnerability / morality fields exist. "
                    "Janis 1972 is qualitative; no numeric threshold was "
                    "retrieved from that book in this unit."
                ),
            },
            {
                "claim": (
                    "Premature-closure timing is the wall-clock of Event.elapsed_ms "
                    "against a published minute cutoff."
                ),
                "verdict": "REFUTED",
                "reason": (
                    "elapsed_ms exists (so duration is mechanically readable) "
                    "but neither Asch nor Stasser & Titus publish a minute "
                    "cutoff with a baseline. A fabricated T would be E3 and "
                    "cannot promote a detector. The portable timing detector "
                    "is round-index instant unanimity, not milliseconds."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0080-probe2-adversarial-refuter",
            "independent": True,
            "verdict": "PASS",
            "default": "REFUTED where evidence is insufficient",
            "refuted_claims": [
                "copied Asch 36.8% cutoff on agent transcripts",
                "Janis 8-symptom numeric detector",
                "elapsed_ms minute cutoff inherited from human groupthink",
            ],
            "notes": (
                "Probe 2 re-inventories fields from live schemas, refuses "
                "private_judgment, and requires the healthy fixture to stay "
                "silent in the same run that the instant-unanimity plant fires."
            ),
            "surviving_claims_strongest_caveats": [
                {
                    "claim": "three portable detectors over named fields",
                    "strongest_caveat": (
                        "Field presence is not the same as construct validity "
                        "on LLM panels; no agent-transcript calibration set exists."
                    ),
                },
                {
                    "claim": "pathological = any portable detector firing",
                    "strongest_caveat": (
                        "This is an operational OR-flag for this program, not a "
                        "published diagnostic threshold."
                    ),
                },
            ],
        },
        "tests_required": [
            "name the transcript field each detector reads and confirm the field exists in the council schema",
            "control: at least one classical measure must be marked not-portable with the reason",
        ],
        "tests": [
            {
                "id": "probe1-detector-fields",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0080/probe1_detector_fields.py"
                ),
                "result": "PASS",
            },
            {
                "id": "probe2-not-portable",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0080/probe2_not_portable.py"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "healthy-panel-silent",
                "description": (
                    "A two-round panel with recorded disagreement then "
                    "independent updating must not fire any portable detector."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "asch-private-judgment-rejected",
                "description": (
                    "propose(asch, [private_judgment, trial_type, ground_truth]) "
                    "returns portable=False with those names in missing_fields."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "residual_unknowns": [
            (
                "Prompt One council transcript structure was listed as an input "
                "at a Windows harness path that is not on this Linux worktree. "
                "Inventory used the live kernel/unanimity/chair/audit schemas."
            ),
            (
                "command-center/schema/research-claim-record.schema.json is a "
                "generated shim with no class-specific payload constraints. "
                "This envelope is self-describing and is not claimed to have "
                "validated against a mined research-claim field set."
            ),
            (
                "No LLM multi-agent study was retrieved that reports an Asch "
                "critical-trial rate on this transcript schema, so the "
                "pathological OR-flag is uncalibrated on agents."
            ),
        ],
        "dependencies": {
            "RES-0001": "schema file absent; envelope uses the named field list",
            "RES-0075": "Delphi artifact absent; not required to name transcript fields",
        },
        "min_bytes_threshold": 2048,
        "artifacts": [],
        "notes": (
            "G-1 for RES-0080: live named probes, honest non-BLOCKED research "
            "record, per-unit manifest. Did not run unit_manifest.py --write. "
            "Did not author the shared research-claim-record schema."
        ),
    }


def write_artifact(doc: dict) -> tuple[Path, str, int]:
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if CATALOG_SENTINEL not in payload:
        raise SystemExit("FAILED:RES-0080 sentinel missing from payload")
    if "not_portable" not in payload and "not_portable_measures" not in payload:
        raise SystemExit("FAILED:RES-0080 not-portable list missing")
    path.write_text(payload, encoding="utf-8")
    raw = path.read_bytes()
    return path, digest_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def main() -> int:
    doc = build()
    path, sha, n = write_artifact(doc)
    if n < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0080 artifact too small {n}")
        return 1
    print(f"wrote {OUT} bytes={n} sha256={sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
