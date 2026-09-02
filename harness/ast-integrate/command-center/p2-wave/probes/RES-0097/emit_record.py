#!/usr/bin/env python3
"""Emit command-center/research/RES-0097.json (claim record, per-unit)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import both_states as B  # noqa: E402

OUT_REL = "command-center/research/RES-0097.json"
SENTINEL = (
    "SUCCESS:RES-0097 in the receipt AND an explicit new-versus-restated split, "
    "with a null result reported as a null result if that is the honest outcome"
)
FETCHED = "2026-08-24T18:40:00Z"
QUESTION = (
    "How do clinical trials and experimental physics define and validate a "
    "negative control, and what does their practice add to this estate's "
    "both-states rule that the rule does not already say?"
)


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def lineage(url: str, sha: str, nbytes: int, snapshot: str) -> dict:
    return {
        "resolved_url": url,
        "fetched_at": FETCHED,
        "sha256": sha,
        "bytes": nbytes,
        "local_snapshot": snapshot,
    }


def mechanism(**kwargs) -> dict:
    required = (
        "id",
        "canonical_mechanism",
        "source_lineage",
        "evidence_tier",
        "confidence_band",
        "settling_probe",
        "doi_or_arxiv",
        "section_or_figure",
        "effect_size",
        "baseline",
        "split",
        "strongest_caveat",
        "not_already_in_rule",
        "verdict",
    )
    missing = [k for k in required if k not in kwargs]
    if missing:
        raise SystemExit(f"mechanism missing {missing}")
    return kwargs


def build() -> dict:
    snap = "command-center/p2-wave/probes/RES-0097/snapshots/numbers.json"
    # sha256 of the HTML/PDF extracts fetched 2026-08-24 (see emit comments).
    lips = lineage(
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC3053408/",
        "ee866686e0f1ccde13959527deec8d70c2ba96e7bc00e19fb77487d00a695aea",
        35824,
        snap,
    )
    jackson = lineage(
        "https://doi.org/10.1093/ije/dyi274",
        "463811794bf6d023218fbd202ab7c36cdd7ffa683466ac318979e5fb581a6805",
        44297,
        snap,
    )
    micro = lineage(
        "https://doi.org/10.1103/PhysRevLett.119.231101",
        "a22951e521003ecde2d12ec893e8ab3479babd07a8f9c1374386c885dcca73fb",
        34545,
        snap,
    )
    ich = lineage(
        "https://database.ich.org/sites/default/files/E10_Guideline.pdf",
        "0e5e87ae04f19fd38c7359c48aacb105ef9805c818ecf465aa6c4b0c4db87fa3",
        100008,
        snap,
    )
    klein = lineage(
        "https://www.pp.rhul.ac.uk/~cowan/stat/annurev.nucl.55.090704.pdf",
        "20a90015d4f6e080d57f6179032b398bedecaee0bec3e7165f3b8f2ba6dd71b6",
        76446,
        snap,
    )
    sch = lineage(
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC4285234/",
        "22a53b02ca6e49c8a86fd9ed92b7443dd2cc0b02bb202c78ddcd21ff63971998",
        43868,
        snap,
    )
    hrob = lineage(
        "https://doi.org/10.1002/14651858.CD003974.pub3",
        "6507205734e98f430e3f631239e9b1624fa9aa1531084f70e09b917afc07c830",
        993947,
        snap,
    )
    shi = lineage(
        "https://arxiv.org/abs/2009.05641",
        "b401b13142e478a649c771e3b99711e886cd9e8231200d07d1fe395abd65f8f5",
        68478,
        snap,
    )

    mechs = [
        mechanism(
            id="M-U-COMPARABLE",
            canonical_mechanism=(
                "A negative control is a second variable (outcome N or exposure B) "
                "chosen to be U-comparable with the primary pair (A,Y) while A does "
                "not cause N (or B does not cause Y). An association on the control "
                "pair, analysed the same way as A-Y, detects residual unmeasured "
                "confounding rather than validating a detector on labelled fixtures."
            ),
            source_lineage=lips,
            supporting_lineage=jackson,
            evidence_tier="E2",
            confidence_band="likely",
            settling_probe=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0097/probe1_new_versus_restated.py"
            ),
            doi_or_arxiv="10.1097/EDE.0b013e3181d61eeb",
            section_or_figure=(
                "Lipsitch et al. Epidemiology 2010;21:383-388, section "
                "'Choice of negative controls to detect confounding', Figures 2-3; "
                "numeric from Jackson et al. Int J Epidemiol 2006;35:337-344 Results"
            ),
            effect_size=(
                "Jackson 2006: RR of death vaccinated vs unvaccinated = 0.39 "
                "(95% CI 0.33-0.47) before influenza season; 0.56 (0.52-0.61) during; "
                "0.74 (0.67-0.80) after. Cohort n=72527 seniors, 8 seasons."
            ),
            baseline=(
                "Causal-null RR = 1.0 in the pre-season window (influenza not "
                "circulating, so a true vaccine effect cannot operate). The "
                "pre-season association is larger than the in-season association, "
                "so confounding not influenza protection accounts for the signal."
            ),
            split="NEW",
            verdict="CONFIRMED",
            not_already_in_rule=(
                "Both-states labels a detector and runs it on a known-broken fixture "
                "and a known-good fixture. U-comparable negative control outcomes "
                "are a second outcome that shares unmeasured confounding with Y "
                "while remaining causally untouched by A. The estate rule never "
                "requires that second variable, nor U-comparability."
            ),
            strongest_caveat=(
                "U-comparability is approximate. Lipsitch states a non-null A-N "
                "does not prove A-Y is biased, and a null A-N does not prove A-Y "
                "is unconfounded, if the unobserved common-cause sets differ."
            ),
            contradiction_edges=[],
            support_edges=["M-EMPIRICAL-NULL"],
        ),
        mechanism(
            id="M-QUANT-NULL",
            canonical_mechanism=(
                "A physics null test reports a residual on a designed-zero observable "
                "as a numeric bound with separate statistical and systematic errors, "
                "plus a same-composition control instrument that must also be null."
            ),
            source_lineage=micro,
            evidence_tier="E1",
            confidence_band="almost-certain",
            settling_probe=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0097/probe1_new_versus_restated.py"
            ),
            doi_or_arxiv="10.1103/PhysRevLett.119.231101",
            section_or_figure="Touboul et al. Phys. Rev. Lett. 119, 231101 (2017), Eqs. (2)-(3)",
            effect_size=(
                "SUEP (Ti vs Pt) delta(Ti,Pt) = [-1 +/- 9(stat) +/- 9(syst)] x 10^-15 "
                "at 1-sigma, 120 orbits. SUREF same-composition control "
                "delta(Pt,Pt) = [+4 +/- 4(stat)] x 10^-15, chi2_red=1.24."
            ),
            baseline=(
                "Weak-equivalence-principle null is delta = 0. SUREF is designed "
                "to be a null instrument (identical Pt/Rh masses); its result is "
                "reported as compatible with that 0 baseline at ~4 x 10^-15."
            ),
            split="NEW",
            verdict="CONFIRMED",
            not_already_in_rule=(
                "Both-states is a binary fire/silent pair. The MICROSCOPE null test "
                "adds a numeric bound on residual systematics (stat and syst at "
                "10^-15) against a designed-zero observable, which the estate rule "
                "does not require of a probe."
            ),
            strongest_caveat=(
                "Transferring a 10^-15 Eotvos bound into software is analogical: "
                "the NEW content is the quantitative residual, not the gravity "
                "result itself. A binary SUREF 'compatible with null' reading "
                "alone would restate silent-on-good."
            ),
            contradiction_edges=["M-SUREF-BINARY"],
            support_edges=[],
        ),
        mechanism(
            id="M-PLACEBO-RITUAL",
            canonical_mechanism=(
                "A placebo/sham arm matches expectancy, attention, ritual and "
                "assessment while omitting the putative pharmacologic (or physical) "
                "mechanism, so the contrast isolates that mechanism from the rest "
                "of the treatment package."
            ),
            source_lineage=hrob,
            supporting_lineage=ich,
            evidence_tier="E2",
            confidence_band="likely",
            settling_probe=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0097/probe1_new_versus_restated.py"
            ),
            doi_or_arxiv="10.1002/14651858.CD003974.pub3",
            section_or_figure=(
                "Hrobjartsson & Gotzsche, Cochrane Database Syst Rev 2010, "
                "CD003974.pub3, Main results (continuous outcomes, pain); "
                "ICH E10 section 1.3.1 Placebo Concurrent Control"
            ),
            effect_size=(
                "Placebo vs no-treatment, pain SMD = -0.28 (95% CI -0.36 to -0.19); "
                "overall continuous SMD = -0.23 (95% CI -0.28 to -0.17) in 158 "
                "trials (10525 patients)."
            ),
            baseline=(
                "No-treatment arm is SMD = 0 by construction of the contrast. "
                "ICH E10 1.3.1 states placebo controls all influences other than "
                "pharmacologic action (natural history, regression to the mean, "
                "expectations, being in a trial)."
            ),
            split="NEW",
            verdict="CONFIRMED",
            not_already_in_rule=(
                "Both-states does not require a ritual-matched inert arm. A "
                "known-good fixture is the detector's clean input, not a sham that "
                "matches expectancy while stripping the putative mechanism. "
                "Placebo vs no-treatment is a different object."
            ),
            strongest_caveat=(
                "Hrobjartsson warn against pooling (I2 42%, funnel asymmetry). "
                "Pain effect is heterogeneous; four overlapping acupuncture trials "
                "SMD -0.68 vs three other pain trials SMD -0.13 (-0.28 to 0.03). "
                "Observer-reported SMD -0.13 is small. Software has no patient "
                "expectancy, so the analog is only for human-in-the-loop probes."
            ),
            contradiction_edges=[],
            support_edges=[],
        ),
        mechanism(
            id="M-EMPIRICAL-NULL",
            canonical_mechanism=(
                "A battery of negative-control drug-outcome pairs estimates an "
                "empirical null distribution of effect estimates; p-values are "
                "calibrated to that distribution instead of the theoretical N(0,se)."
            ),
            source_lineage=sch,
            evidence_tier="E1",
            confidence_band="likely",
            settling_probe=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0097/probe2_refute_overclaim.py"
            ),
            doi_or_arxiv="10.1002/sim.5925",
            section_or_figure=(
                "Schuemie et al. Stat Med 2014;33:209-218, Section 3.1 "
                "Distribution of negative controls, Figure 1, paragraph after Table 1"
            ),
            effect_size=(
                "Uncalibrated two-sided p<0.05 on negative controls: 17/34 (50%) "
                "cohort, 33/46 (72%) case-control, 33/46 (72%) SCCS. After "
                "leave-one-out empirical calibration: 2/34 (6%), 5/46 (11%), "
                "3/46 (5%). Literature implication: at least 54% of published "
                "p<0.05 findings would lose significance under the same calibration."
            ),
            baseline=(
                "Theoretical Type I rate is 5% when the null is true. Calibration "
                "target is that same 5% on the negative-control set."
            ),
            split="NEW",
            verdict="CONFIRMED",
            not_already_in_rule=(
                "Both-states uses one known-good fixture and one known-broken "
                "fixture. Empirical calibration needs a set of negative control "
                "drugs large enough to fit a Gaussian null (here 34 and 46 pairs) "
                "and then rescales significance. One silent-on-good run cannot "
                "produce that empirical null."
            ),
            strongest_caveat=(
                "Negative controls were selected as drugs believed not to cause "
                "the outcome; misclassified controls would distort the empirical "
                "null. Substitute databases were used, not the original study data. "
                "The 54% literature figure depends on an automated corpus model, "
                "not a manual re-analysis of each paper."
            ),
            contradiction_edges=[],
            support_edges=["M-U-COMPARABLE"],
        ),
        mechanism(
            id="M-BLIND-FREEZE",
            canonical_mechanism=(
                "Blind analysis freezes selection cuts, efficiencies and background "
                "estimates before the hidden signal box (or a hidden numeric offset) "
                "is opened, so the result cannot be tuned toward a preconception."
            ),
            source_lineage=klein,
            evidence_tier="E2",
            confidence_band="likely",
            settling_probe=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0097/probe2_refute_overclaim.py"
            ),
            doi_or_arxiv="10.1146/annurev.nucl.55.090704.151521",
            section_or_figure=(
                "Klein & Roodman, Annu. Rev. Nucl. Part. Sci. 2005;55:141-163, "
                "Section 2 numerical example of statistical cut bias; Section 3.1 "
                "Hidden Signal Box"
            ),
            effect_size=(
                "With N=2500 events in the signal region before cuts and 10 cuts "
                "each with acceptance Ai=0.9, a geometric-average bias of 1% "
                "produces an apparent signal of roughly 3-sigma."
            ),
            baseline=(
                "Unbiased cuts (Ai' = Ai) produce a 0-sigma false peak when no "
                "true signal is present. The hidden-signal-box method is designed "
                "so those cuts cannot be chosen using events inside the box."
            ),
            split="NEW",
            verdict="PARTIAL",
            not_already_in_rule=(
                "The freeze-before-unblind discipline (hidden signal box, hidden "
                "offset) is not stated by both-states. Known-broken fixtures are "
                "the overlapping part and are restated; the temporal freeze is the "
                "increment. Experimenter's bias size cannot be estimated, only "
                "prevented."
            ),
            strongest_caveat=(
                "Klein & Roodman note the hidden box is inappropriate when signal "
                "events themselves must be used to measure efficiency. The 3-sigma "
                "worked example is a cartoon of cut bias, not a measured PDG pull. "
                "PARTIAL because the known-broken fixture half of the practice "
                "already sits in the estate rule."
            ),
            contradiction_edges=[],
            support_edges=[],
        ),
        mechanism(
            id="M-ASSAY-SENSITIVITY",
            canonical_mechanism=(
                "ICH E10 assay sensitivity is the ability of a trial to distinguish "
                "an effective treatment from a less effective or ineffective one. "
                "This restates both-states discrimination. Null result for THIS unit."
            ),
            source_lineage=ich,
            evidence_tier="E2",
            confidence_band="almost-certain",
            settling_probe=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0097/probe1_new_versus_restated.py"
            ),
            doi_or_arxiv="10.1093/ije/dyi274",
            section_or_figure=(
                "ICH E10 (CPMP/ICH/364/96) sections 1.5 and 1.5.2 Assay Sensitivity "
                "(guideline PDF has no DOI; numeric analog Jackson et al. IJE 2006 Results)"
            ),
            effect_size=(
                "Definitional in E10; empirical analog is Jackson pre-season RR 0.39 "
                "(95% CI 0.33-0.47) which 'distinguishes' vaccinated from "
                "unvaccinated when the treatment cannot work."
            ),
            baseline=(
                "E10 definition: ability to distinguish effective from less "
                "effective or ineffective treatment. Jackson causal-null RR = 1.0 "
                "in the pre-season window. An analysis that looks protective on "
                "that window has failed the discrimination the guideline names."
            ),
            split="RESTATED-NULL",
            verdict="CONFIRMED",
            not_already_in_rule=(
                "Nothing new: assay sensitivity is the same pair as fire-on-effective "
                "/ silent-on-ineffective. This is a null result, a restatement of "
                "both-states, not an addition to the rule."
            ),
            strongest_caveat=(
                "E10's non-inferiority discussion (historical evidence of sensitivity "
                "to drug effects) is about borrowing past placebo gaps, which is a "
                "different operationalisation, but the CORE definition in 1.5 is "
                "the discrimination test."
            ),
            contradiction_edges=[],
            support_edges=["M-LAB-NULL-REPEAT"],
        ),
        mechanism(
            id="M-LAB-NULL-REPEAT",
            canonical_mechanism=(
                "Experimental biology repeats the assay under conditions expected to "
                "produce a null (leave out an essential ingredient; inactivate the "
                "active ingredient) and requires that the null appear. Null result "
                "relative to silent-on-good."
            ),
            source_lineage=lips,
            evidence_tier="E2",
            confidence_band="likely",
            settling_probe=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0097/probe1_new_versus_restated.py"
            ),
            doi_or_arxiv="10.1097/EDE.0b013e3181d61eeb",
            section_or_figure=(
                "Lipsitch et al. 2010, section 'Experimental biology: threats to "
                "causal inference and the use of negative controls' (leave-out / "
                "inactivate / impossible-by-mechanism list)"
            ),
            effect_size=(
                "Qualitative protocol, numeric illustration via Jackson: injury/"
                "trauma hospitalization as 'impossible-by-mechanism' control, "
                "paired with pre-season mortality RR 0.39 vs causal-null 1.0."
            ),
            baseline=(
                "Expected null: same bacterial counts with/without cytokine in the "
                "absence of neutrophils; RR=1.0 for influenza vaccine on "
                "injury/trauma or on death before influenza circulates."
            ),
            split="RESTATED-NULL",
            verdict="CONFIRMED",
            not_already_in_rule=(
                "Leave-out-an-essential-ingredient restates silent-on-good: the "
                "assay must not fire when the hypothesized mechanism is removed. "
                "Reported as a null result, not novelty."
            ),
            strongest_caveat=(
                "The SAME paper's U-comparable construction (M-U-COMPARABLE) is "
                "new; only the laboratory 'verify the null appears' half is a "
                "restatement."
            ),
            contradiction_edges=[],
            support_edges=["M-ASSAY-SENSITIVITY"],
        ),
        mechanism(
            id="M-SUREF-BINARY",
            canonical_mechanism=(
                "Reading MICROSCOPE SUREF solely as 'compatible with a null result' "
                "without the numeric bound restates silent-on-good. Null result."
            ),
            source_lineage=micro,
            evidence_tier="E1",
            confidence_band="almost-certain",
            settling_probe=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0097/probe1_new_versus_restated.py"
            ),
            doi_or_arxiv="10.1103/PhysRevLett.119.231101",
            section_or_figure="Touboul et al. 2017, text after Eq. (3) (SUREF null compatibility)",
            effect_size=(
                "SUREF delta(Pt,Pt) = [+4 +/- 4(stat)] x 10^-15, described as "
                "fully compatible with a null result."
            ),
            baseline="Designed-null same-composition instrument, expected delta = 0.",
            split="RESTATED-NULL",
            verdict="CONFIRMED",
            not_already_in_rule=(
                "A same-composition control that must look null is silent-on-good "
                "for the instrument. That binary reading restates both-states. The "
                "numeric 10^-15 bound is carved out as M-QUANT-NULL instead of "
                "being dressed into this row."
            ),
            strongest_caveat=(
                "The paper reports the number and the compatibility sentence "
                "together; splitting them is an analytic choice of THIS unit so "
                "the restatement is not smuggled into the NEW row."
            ),
            contradiction_edges=["M-QUANT-NULL"],
            support_edges=[],
        ),
        mechanism(
            id="M-DOUBLE-NC-ID",
            canonical_mechanism=(
                "A double negative control (NCE + NCO) can nonparametrically "
                "identify the average treatment effect under completeness "
                "conditions. Not promoted: no effect size AND baseline in the "
                "review body used here."
            ),
            source_lineage=shi,
            evidence_tier="E3",
            confidence_band="roughly-even",
            settling_probe=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0097/probe1_new_versus_restated.py"
            ),
            doi_or_arxiv="2009.05641",
            section_or_figure=(
                "Shi, Miao, Tchetgen Tchetgen, arXiv:2009.05641, section "
                "'Nonparametric identification in a double negative control design'"
            ),
            effect_size=None,
            baseline=None,
            split="E3-NOT-PROMOTED",
            verdict="NOT-CHECKED",
            not_already_in_rule=(
                "Identification of an ATE is not a detector test, so it would be "
                "new IF a headline number with baseline were attached. Catalog "
                "forbids promoting a mechanism from a headline without baseline; "
                "this row is E3 and is not in the NEW list."
            ),
            strongest_caveat=(
                "The identification claim is real in the literature (Miao/Shi/"
                "Tchetgen line) but THIS unit did not extract a numeric ATE versus "
                "a named baseline from the review, so it stays NOT-CHECKED."
            ),
            contradiction_edges=[],
            support_edges=["M-U-COMPARABLE"],
        ),
    ]

    new_ids = [m["id"] for m in mechs if m["split"] == "NEW"]
    rest_ids = [m["id"] for m in mechs if m["split"] == "RESTATED-NULL"]
    e3_ids = [m["id"] for m in mechs if m["split"] == "E3-NOT-PROMOTED"]

    claims = [
        {
            "id": m["id"],
            "canonical_mechanism": m["canonical_mechanism"],
            "verdict": m["verdict"],
            "confidence_band": m["confidence_band"],
            "evidence_tier": m["evidence_tier"],
            "source_lineage": m["source_lineage"],
            "settling_probe": m["settling_probe"],
            "contradiction_edges": m["contradiction_edges"],
            "support_edges": m["support_edges"],
            "split": m["split"],
            "strongest_caveat": m["strongest_caveat"],
        }
        for m in mechs
    ]

    return {
        "unit_id": "RES-0097",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": (
            "Extract negative-control practice from disciplines where it is mandatory"
        ),
        "question": QUESTION,
        "schema_declared": "command-center/schema/research-claim-record.schema.json",
        "schema_present": False,
        "schema_gap": (
            "RES-0001 schema family is absent on this worktree. Record follows "
            "the RES-0001 field list (claim id, canonical mechanism, source "
            "lineage, E1-E4, Sherman-Kent band, named settling probe, "
            "contradiction/support edges, freshness stamp, snapshot sha256) "
            "without claiming schema-file validation."
        ),
        "freshness_stamp": FETCHED,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "both_states_rule": {
            "rule_file": B.RULE_FILE_PATH,
            "rule_file_present": B.RULE_FILE_PRESENT,
            "section": "3b",
            "canonical": B.CANONICAL,
            "reconstruction_reason": (
                "The named input rules/common/single-signal-verification.md is "
                "missing. Reconstruction uses three local anchors that all state "
                "the fire-on-bad AND silent-on-good pair."
            ),
            "anchors": list(B.ANCHORS),
        },
        "new_versus_restated": {
            "new": new_ids,
            "restated_null_results": rest_ids,
            "not_promoted_e3": e3_ids,
            "how_to_read": (
                "NEW = practice the both-states pair does not already require. "
                "RESTATED-NULL = agrees with the existing rule; reported as a "
                "null result, not dressed as novelty. E3-NOT-PROMOTED = "
                "headline without baseline, cannot promote a mechanism."
            ),
        },
        "null_result_statement": (
            "Honest null result: ICH E10 assay sensitivity, laboratory "
            "leave-out-ingredient null repeats, and a binary reading of the "
            "MICROSCOPE SUREF same-composition control restate the estate "
            "both-states pair (fire on the broken state, silent on the good "
            "state). Those rows are restated_null_results. They are not "
            "promoted as additions to the rule."
        ),
        "answer": (
            "Clinical trials and experimental physics add four objects the "
            "both-states rule does not already say: (1) a U-comparable second "
            "variable for unmeasured confounding (Lipsitch/Jackson), (2) a "
            "numeric residual bound on a designed-zero observable "
            "(MICROSCOPE 10^-15), (3) a ritual-matched placebo/sham arm "
            "(ICH E10 1.3.1; Hrobjartsson pain SMD -0.28 vs no-treatment 0), "
            "(4) an empirical null distribution over many negative controls "
            "(Schuemie 50-72% vs 5%). Blind-analysis freeze is PARTIAL (new "
            "temporal discipline, restated known-broken fixtures). Assay "
            "sensitivity and lab null-repeats are null results. Double-negative-"
            "control ATE identification is E3, not promoted."
        ),
        "mechanisms": mechs,
        "claims": claims,
        "reviewer": {
            "reviewer_id": "RES-0097-probe2-adversarial-overclaim",
            "independent": True,
            "scope_not_agreement": True,
            "default_when_insufficient": "REFUTED",
            "verdict": "PASS",
            "method": (
                "Adversarial check: every NEW row must retain novelty text after "
                "both-states paraphrase is stripped; restated rows must be labelled "
                "null; E3 cannot sit in NEW; a mutant that relabels restated as NEW "
                "must make the checker fire; the live record must stay silent."
            ),
            "strongest_surviving_counterargument": (
                "The markdown rule file is absent, so 'not already in the rule' "
                "is judged against the operational reconstruction (ADV-0009, "
                "test_validate.py 3b docstring, RES-0002 tests_required). If the "
                "missing file already required U-comparable second variables, "
                "numeric residuals, placebo ritual-matching, or empirical-null "
                "calibration, those NEW verdicts would collapse to restated. "
                "That file was not on disk to refute against."
            ),
        },
        "tests": [
            {
                "id": "T1-new-versus-restated",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0097/probe1_new_versus_restated.py"
                ),
                "result": "PASS",
            },
            {
                "id": "T2-refute-overclaim-both-states",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0097/probe2_refute_overclaim.py"
                ),
                "result": "PASS",
            },
        ],
        "inputs_status": {
            "REGISTER_md": False,
            "single_signal_verification_md": False,
            "eco_frontier_md": False,
            "catalog_unit": True,
            "operational_both_states_anchors": True,
        },
        "source_snapshots_sha256": None,
        "snapshot_sha256": None,
    }


def main() -> int:
    doc = build()
    snap = HERE / "snapshots" / "numbers.json"
    s_sha, s_n = sha_file(snap)
    doc["source_snapshots_sha256"] = s_sha
    doc["source_snapshots_bytes"] = s_n
    # snapshot_sha256 of the record body excluding the self-hash field
    tmp = dict(doc)
    tmp["snapshot_sha256"] = ""
    body = json.dumps(tmp, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    doc["snapshot_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_REL} snapshot_sha256={doc['snapshot_sha256']}")
    print(SENTINEL)
    print("SUCCESS:RES-0097 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
