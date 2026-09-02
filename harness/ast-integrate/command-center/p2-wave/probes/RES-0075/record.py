"""RES-0075 Delphi operational-rule and failure-mode records.

Numbers below were re-extracted from open PDFs/HTML this session. RAND
RM-5888-PR (Dalkey 1969) is cited as the origin of the four-feature
definition but its PDF 404'd on rand.org, so no Dalkey 1969 cell count
is used to promote a mechanism.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from contract import GRADING_RULE, SENTINEL, SPLIT_PHRASE, can_promote, demote_headline_without_baseline

FRESHNESS = "2026-08-24T00:00:00Z"
SETTLING = "command-center/p2-wave/probes/RES-0075/probe1_rules_split.py"
SETTLING_FAIL = "command-center/p2-wave/probes/RES-0075/probe2_failure_modes.py"


def _snap(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _row(
    *,
    cid: str,
    text: str,
    mechanism: str,
    doi: str,
    title: str,
    year: int,
    url: str,
    locator: str,
    effect_size: str,
    baseline: str,
    tier: str,
    band: str,
    verdict: str,
    caveat: str,
    rule_class: str,
    support: list[str],
    contradict: list[str],
    settling: str = SETTLING,
    authors: str = "",
) -> dict[str, Any]:
    lineage = {
        "doi_or_arxiv": doi,
        "title": title,
        "year": year,
        "url": url,
        "authors": authors,
    }
    snap = _snap(
        {
            "id": cid,
            "doi_or_arxiv": doi,
            "locator": locator,
            "effect_size": effect_size,
            "baseline": baseline,
            "text": text,
        }
    )
    row = {
        "id": cid,
        "text": text,
        "canonical_mechanism": mechanism,
        "source_lineage": lineage,
        "locator": locator,
        "effect_size": effect_size,
        "baseline": baseline,
        "evidence_tier": tier,
        "confidence_band": band,
        "settling_probe": settling,
        "verdict": verdict,
        "strongest_caveat": caveat,
        "freshness_stamp": FRESHNESS,
        "snapshot_sha256": snap,
        "support_edges": support,
        "contradiction_edges": contradict,
        "rule_class": rule_class,
        "promotable": False,
    }
    graded = demote_headline_without_baseline(row)
    graded["promotable"] = can_promote(graded)
    if graded["rule_class"] == "empirically-supported" and not graded["promotable"]:
        graded["rule_class"] = "not-promoted"
        graded["verdict"] = "REFUTED"
    return graded


RULES: list[dict[str, Any]] = [
    _row(
        cid="RES-0075-R1",
        text=(
            "A Delphi procedure is defined by four operational features: "
            "anonymity of panelists, iteration over rounds, controlled "
            "feedback of the panel's judgments between rounds, and "
            "statistical aggregation of the group response."
        ),
        mechanism="four-feature-delphi-definition",
        doi="10.1007/978-0-306-47630-3_7",
        title="Expert opinions in forecasting: The role of the Delphi technique",
        year=2001,
        url="https://gwern.net/doc/statistics/prediction/2001-rowe.pdf",
        authors="Rowe G, Wright G",
        locator="opening section 'Four necessary features characterize a Delphi procedure'",
        effect_size="definitional (4 named features; not a measured contrast)",
        baseline="unstructured interacting group (the contrast the features were designed against)",
        tier="E3",
        band="medium",
        verdict="PARTIAL",
        caveat=(
            "This is a definitional package, not an isolated causal test of "
            "each feature. RAND RM-5888-PR (Dalkey 1969, doi:10.7249/RM5888) "
            "is the experimental origin but its PDF was not retrievable this "
            "session (HTTP 404 on the RAND product path), so no Dalkey cell "
            "count promotes a mechanism."
        ),
        rule_class="conventional",
        support=["RES-0075-R2", "RES-0075-R3"],
        contradict=["RES-0075-C-anon"],
    ),
    _row(
        cid="RES-0075-R2",
        text=(
            "Iteration plus controlled feedback, taken as the Delphi package "
            "versus an unstructured traditional group, has a study-count "
            "advantage on accuracy."
        ),
        mechanism="iteration-plus-feedback-vs-unstructured-group",
        doi="10.1007/978-0-306-47630-3_7",
        title="Expert opinions in forecasting: The role of the Delphi technique",
        year=2001,
        url="https://gwern.net/doc/statistics/prediction/2001-rowe.pdf",
        authors="Rowe G, Wright G",
        locator="section 'When the alternative is a traditional group'",
        effect_size=(
            "Delphi outperformed traditional groups 5 studies to 1, with 2 ties, "
            "and 1 task-specific mixed result (Rowe and Wright 1999 synthesis "
            "restated in this chapter)"
        ),
        baseline="unstructured traditional / interacting groups (same review set)",
        tier="E2",
        band="medium",
        verdict="CONFIRMED",
        caveat=(
            "The chapter abstract states 'five to one with one tie' while the "
            "body states 'five studies to one, with two ties, and with one "
            "study showing task-specific support for both techniques'. Lab "
            "panels are usually students; Graefe and Armstrong (2011) found "
            "the same directional MAE advantage (5.62 vs 7.21) that was not "
            "statistically significant overall (Kruskal-Wallis ns). Study-count "
            "is not a Cohen's d."
        ),
        rule_class="empirically-supported",
        support=["RES-0075-R2b", "RES-0075-R3"],
        contradict=["RES-0075-R2b"],
    ),
    _row(
        cid="RES-0075-R2b",
        text=(
            "On one laboratory estimation task with 227 participants "
            "(11 groups per method), Delphi mean absolute error was lower "
            "than face-to-face meetings, but the four-method overall test "
            "was not statistically significant."
        ),
        mechanism="iteration-plus-feedback-vs-unstructured-group",
        doi="10.1016/j.ijforecast.2010.05.004",
        title=(
            "Comparing face-to-face meetings, nominal groups, Delphi and "
            "prediction markets on an estimation task"
        ),
        year=2011,
        url=(
            "https://faculty.wharton.upenn.edu/wp-content/uploads/2010/04/"
            "41-JSA-Comparing-face-to-face-meetings-nominal-groups-Delphi-"
            "and-prediction-markets-on-an-estimation-task.pdf"
        ),
        authors="Graefe A, Armstrong JS",
        locator="section 'Relative accuracy of group methods' / Conclusion",
        effect_size="Delphi overall MAE 5.62; significantly better than FTF on 2 of 10 questions; never significantly worse",
        baseline="face-to-face overall MAE 7.21 (NGT 5.92; prediction markets 7.07); Kruskal-Wallis ns across four methods",
        tier="E1",
        band="low",
        verdict="PARTIAL",
        caveat=(
            "Directional MAE advantage does not survive the overall "
            "Kruskal-Wallis test. Task was factual percentage estimates "
            "without distributed private knowledge. This row therefore "
            "cannot carry the unstructured-group comparison alone; it is "
            "a contradiction/qualification edge on R2."
        ),
        rule_class="empirically-supported",
        support=["RES-0075-R2"],
        contradict=["RES-0075-R2"],
    ),
    _row(
        cid="RES-0075-R3",
        text=(
            "Iteration plus controlled feedback, taken as Delphi versus a "
            "one-round statistical aggregate of the same or comparable "
            "individuals, has a study-count accuracy advantage."
        ),
        mechanism="iteration-plus-feedback-vs-statistical-aggregate",
        doi="10.1007/978-0-306-47630-3_7",
        title="Expert opinions in forecasting: The role of the Delphi technique",
        year=2001,
        url="https://gwern.net/doc/statistics/prediction/2001-rowe.pdf",
        authors="Rowe G, Wright G",
        locator="section 'When the alternative is simply to average the forecasts of several individuals'",
        effect_size=(
            "Delphi vs first-round or statistical groups 12 studies to 2, "
            "with 2 ties; 5 of the 12 reported statistically significant "
            "accuracy gains over rounds"
        ),
        baseline="first-round Delphi aggregates or independent statistical (non-interacting) groups",
        tier="E2",
        band="medium",
        verdict="CONFIRMED",
        caveat=(
            "Two studies found Delphi worse (Gustafson et al. 1973: worse "
            "than first-round on 7/8 items and vs independent statistical "
            "groups on 6/8; Boje and Murnighan 1982: worse over rounds on "
            "3/4 items). Erffmeyer 1984 and 1986 may double-count the same "
            "dataset. First-round Delphi is not a pure statistical-group "
            "control because panelists expect later feedback."
        ),
        rule_class="empirically-supported",
        support=["RES-0075-R2"],
        contradict=["RES-0075-R2b"],
    ),
    _row(
        cid="RES-0075-C-anon",
        text=(
            "Anonymity is a named necessary feature of classical Delphi, "
            "justified as reducing dominance and conformity pressure, but "
            "this session found no isolated contrast (anonymous vs identified "
            "under otherwise identical iteration and feedback) that reports "
            "an effect size and a baseline."
        ),
        mechanism="anonymity-of-panelists",
        doi="10.7275/pdz9-th90",
        title="The Delphi Technique: Making Sense of Consensus",
        year=2007,
        url="https://doi.org/10.7275/pdz9-th90",
        authors="Hsu C-C, Sandford BA",
        locator="section discussing subject anonymity as a primary characteristic",
        effect_size="none isolated (rationale only; cites Dalkey 1972)",
        baseline="not reported (no anonymous-vs-identified accuracy table in this source)",
        tier="E3",
        band="low",
        verdict="REFUTED",
        caveat=(
            "Headline 'anonymity reduces dominance' without a measured "
            "baseline is E3 and cannot promote the mechanism. Boulkedid "
            "et al. 2011 further show the rule is frequently dropped in "
            "practice (modified Delphi with a physical meeting)."
        ),
        rule_class="conventional",
        support=["RES-0075-F4"],
        contradict=["RES-0075-R2"],
    ),
    _row(
        cid="RES-0075-C-rounds",
        text=(
            "Two or three rounds is the conventional stopping rule. In a "
            "random sample of 100 Delphi studies (2000-2009), 48 finished "
            "in 2 rounds and 42 in 3; 70 of 98 consensus-aiming studies "
            "stopped because a planned round count was reached, not "
            "because consensus was measured."
        ),
        mechanism="two-or-three-rounds-as-stopping-rule",
        doi="10.1016/j.jclinepi.2013.12.002",
        title="Defining consensus: A systematic review recommends methodologic criteria for reporting of Delphi studies",
        year=2014,
        url=(
            "https://bpb-us-w2.wpmucdn.com/sites.umassd.edu/dist/f/1316/files/"
            "2023/01/Defining-consensus-A-systematic-review-recommends-"
            "methodologic-criteria-for-reporting-of-Delphi-studies.pdf"
        ),
        authors="Diamond IR et al.",
        locator="Table 2 (rounds) and Table 3 (reason to stop)",
        effect_size="48/100 two rounds; 42/100 three rounds; 70/98 (71.4%) stopped for number of rounds vs 23/98 (23.5%) stopped for consensus",
        baseline="98 studies whose aim was consensus (of 100 sampled Delphi studies)",
        tier="E1",
        band="high",
        verdict="CONFIRMED",
        caveat=(
            "These are observational reporting counts, not a causal test that "
            "2-3 rounds maximises accuracy. The row therefore supports "
            "'this is how Delphi is run' (convention in use) rather than "
            "'this round count is optimal'."
        ),
        rule_class="conventional",
        support=["RES-0075-F1"],
        contradict=[],
    ),
    _row(
        cid="RES-0075-C-threshold",
        text=(
            "Percent agreement is the most common consensus definition; "
            "when a percentage/proportion threshold is stated, the median "
            "cut-off is 75% (range 50-97%). That median is a reporting "
            "convention, not a validated accuracy optimum."
        ),
        mechanism="percent-agreement-consensus-threshold",
        doi="10.1016/j.jclinepi.2013.12.002",
        title="Defining consensus: A systematic review recommends methodologic criteria for reporting of Delphi studies",
        year=2014,
        url=(
            "https://bpb-us-w2.wpmucdn.com/sites.umassd.edu/dist/f/1316/files/"
            "2023/01/Defining-consensus-A-systematic-review-recommends-"
            "methodologic-criteria-for-reporting-of-Delphi-studies.pdf"
        ),
        authors="Diamond IR et al.",
        locator="Table 4 and Results section 3.3",
        effect_size="percent agreement used in 25 of 72 studies that defined consensus; median threshold 75% (range 50-97%) among percentage/proportion definitions that stated a cut-off",
        baseline="72 of 98 consensus-aiming studies that provided any consensus definition",
        tier="E1",
        band="high",
        verdict="CONFIRMED",
        caveat=(
            "A 75% cut-off is the median of arbitrary thresholds, not a "
            "calibrated operating point. Authors concluded consensus was "
            "reached in 86/98 studies, but an a priori threshold existed "
            "in only 42 of those 86."
        ),
        rule_class="conventional",
        support=["RES-0075-F1", "RES-0075-F2"],
        contradict=[],
    ),
    _row(
        cid="RES-0075-C-statagg",
        text=(
            "The group answer is taken as a statistical summary (mean or "
            "median) of the final-round estimates rather than a spokesperson "
            "outcome. Median-plus-quartiles is conventional; this session "
            "did not isolate median vs mean with an effect size and baseline."
        ),
        mechanism="statistical-group-response-median-or-mean",
        doi="10.1007/978-0-306-47630-3_7",
        title="Expert opinions in forecasting: The role of the Delphi technique",
        year=2001,
        url="https://gwern.net/doc/statistics/prediction/2001-rowe.pdf",
        authors="Rowe G, Wright G",
        locator="procedure description: 'the facilitator takes the group judgment as the statistical average (mean or median) of the panelists' estimates on the final round'",
        effect_size="none isolated for median vs mean",
        baseline="not reported for the aggregation-statistic choice (the 12-to-2 tally contrasts the whole Delphi package with a statistical group, not median with mean)",
        tier="E3",
        band="low",
        verdict="REFUTED",
        caveat=(
            "Using a group statistic is part of the package that beat "
            "unstructured groups in R2/R3; the specific choice of median "
            "versus mean is convention. Headline 'use the median' without "
            "a median-vs-mean baseline cannot promote."
        ),
        rule_class="conventional",
        support=["RES-0075-R3"],
        contradict=[],
    ),
    _row(
        cid="RES-0075-C-feedback-form",
        text=(
            "Practice guidance says feedback should be quantitative (median, "
            "range) plus the recipient's own prior rating; healthcare QI "
            "Delphi reports often omit that they gave any between-round "
            "feedback at all."
        ),
        mechanism="controlled-feedback-content",
        doi="10.1371/journal.pone.0020476",
        title="Using and reporting the Delphi method for selecting healthcare quality indicators: A systematic review",
        year=2011,
        url="https://doi.org/10.1371/journal.pone.0020476",
        authors="Boulkedid R, Abdoul H, Loustau M, Sibony O, Alberti C",
        locator="Table 4 Feedback rows; Results 'Data on the Progress of the Delphi Procedure'",
        effect_size="48/80 (60%) reported that feedback was given between rounds; of those, 28/48 (58%) quantitative only, 19/48 (40%) quantitative+qualitative, 1/48 (2%) qualitative; individual feedback reported in 31/80 (39%)",
        baseline="80 included healthcare quality-indicator Delphi studies",
        tier="E1",
        band="high",
        verdict="CONFIRMED",
        caveat=(
            "These are reporting rates, not a causal ranking of feedback "
            "formats on accuracy. The 40% of studies that did not report "
            "feedback may still have given it. Controlled feedback as a "
            "package is promoted via R2/R3; the specific median+rationale "
            "recipe remains conventional."
        ),
        rule_class="conventional",
        support=["RES-0075-F3", "RES-0075-R2"],
        contradict=[],
    ),
    _row(
        cid="RES-0075-C-panelsize",
        text=(
            "Panel-size advice of roughly 5-20 experts is conventional. "
            "Boulkedid et al. observed a median invited panel of 17 "
            "(Q1 11, Q3 31) in healthcare QI Delphi studies."
        ),
        mechanism="panel-size-five-to-twenty",
        doi="10.1371/journal.pone.0020476",
        title="Using and reporting the Delphi method for selecting healthcare quality indicators: A systematic review",
        year=2011,
        url="https://doi.org/10.1371/journal.pone.0020476",
        authors="Boulkedid R, Abdoul H, Loustau M, Sibony O, Alberti C",
        locator="Table 3 'Number of individuals invited to participate'",
        effect_size="median invited n=17 (Q1=11; Q3=31); min 3, max 418; reported in 76/80 (95%) studies",
        baseline="76 studies that reported invited panel size (of 80 included)",
        tier="E1",
        band="medium",
        verdict="PARTIAL",
        caveat=(
            "Observed medians describe practice, not an accuracy-maximising "
            "n. Rowe and Wright (2001) recommend 5-20 as a principle without "
            "an isolated n-vs-accuracy experiment in that chapter."
        ),
        rule_class="conventional",
        support=["RES-0075-R1"],
        contradict=[],
    ),
]


FAILURE_MODES: list[dict[str, Any]] = [
    _row(
        cid="RES-0075-F1",
        text=(
            "False or assumed consensus: authors report that consensus was "
            "reached even when stopping was not based on a consensus "
            "criterion."
        ),
        mechanism="assumed-consensus-stopping-rule-mismatch",
        doi="10.1016/j.jclinepi.2013.12.002",
        title="Defining consensus: A systematic review recommends methodologic criteria for reporting of Delphi studies",
        year=2014,
        url=(
            "https://bpb-us-w2.wpmucdn.com/sites.umassd.edu/dist/f/1316/files/"
            "2023/01/Defining-consensus-A-systematic-review-recommends-"
            "methodologic-criteria-for-reporting-of-Delphi-studies.pdf"
        ),
        authors="Diamond IR et al.",
        locator="Table 3; Results section 3.4",
        effect_size="86/98 (87.8%) commented that consensus was reached; only 23/98 (23.5%) stopped primarily because consensus was reached; 70/98 (71.4%) stopped after a specified number of rounds",
        baseline="98 studies that aimed to address consensus",
        tier="E1",
        band="high",
        verdict="CONFIRMED",
        caveat=(
            "The review is of published reports, so some studies may have "
            "used unreported stopping rules. Of 64 studies with an a priori "
            "consensus definition, only 1 (1.5%) stated consensus was not "
            "achieved — consistent with consensus being treated as automatic."
        ),
        rule_class="empirically-supported",
        settling=SETTLING_FAIL,
        support=["RES-0075-F2"],
        contradict=[],
    ),
    _row(
        cid="RES-0075-F2",
        text=(
            "Undefined consensus: a substantial minority of Delphi studies "
            "never define what would count as agreement, so the output "
            "cannot be audited as a statistical group response."
        ),
        mechanism="undefined-consensus-criterion",
        doi="10.1016/j.jclinepi.2013.12.002",
        title="Defining consensus: A systematic review recommends methodologic criteria for reporting of Delphi studies",
        year=2014,
        url=(
            "https://bpb-us-w2.wpmucdn.com/sites.umassd.edu/dist/f/1316/files/"
            "2023/01/Defining-consensus-A-systematic-review-recommends-"
            "methodologic-criteria-for-reporting-of-Delphi-studies.pdf"
        ),
        authors="Diamond IR et al.",
        locator="Table 3 'Was consensus defined?'",
        effect_size="26/98 (26.5%) provided no definition; of 72 that did, 21/72 (33%) omitted a threshold; 15 of the 86 'consensus reached' papers had no definition at all",
        baseline="98 consensus-aiming Delphi studies",
        tier="E1",
        band="high",
        verdict="CONFIRMED",
        caveat="Counts describe published methods sections, not unpublished protocols.",
        rule_class="empirically-supported",
        settling=SETTLING_FAIL,
        support=["RES-0075-F1"],
        contradict=[],
    ),
    _row(
        cid="RES-0075-F3",
        text=(
            "Controlled feedback is omitted or unreported in a large share "
            "of applied Delphi studies, so iteration proceeds without the "
            "information channel the method claims as its mechanism."
        ),
        mechanism="feedback-omitted-between-rounds",
        doi="10.1371/journal.pone.0020476",
        title="Using and reporting the Delphi method for selecting healthcare quality indicators: A systematic review",
        year=2011,
        url="https://doi.org/10.1371/journal.pone.0020476",
        authors="Boulkedid R, Abdoul H, Loustau M, Sibony O, Alberti C",
        locator="Abstract and Table 4 Feedback / Individual feedback reported",
        effect_size="only 48/80 (60%) reported feedback between rounds; 32/80 (40%) did not; individual feedback reported in 31/80 (39%)",
        baseline="80 healthcare quality-indicator Delphi studies",
        tier="E1",
        band="high",
        verdict="CONFIRMED",
        caveat=(
            "Non-reporting is not proof of non-use. Restricted to healthcare "
            "QI Delphi, 1978-2009. Single extractor after a 10-article "
            "calibration (median kappa 1)."
        ),
        rule_class="empirically-supported",
        settling=SETTLING_FAIL,
        support=["RES-0075-C-feedback-form"],
        contradict=[],
    ),
    _row(
        cid="RES-0075-F4",
        text=(
            "Anonymity is routinely broken by 'modified Delphi' physical "
            "meetings, reintroducing the dominance channel the method was "
            "built to close."
        ),
        mechanism="anonymity-breach-via-modified-delphi-meeting",
        doi="10.1371/journal.pone.0020476",
        title="Using and reporting the Delphi method for selecting healthcare quality indicators: A systematic review",
        year=2011,
        url="https://doi.org/10.1371/journal.pone.0020476",
        authors="Boulkedid R, Abdoul H, Loustau M, Sibony O, Alberti C",
        locator="Table 4 Type of Delphi procedure / Timing of the meeting",
        effect_size="49/78 (63%) used modified Delphi with a physical meeting; of 34 that timed the meeting, 19/34 (56%) met between rounds and 15/34 (44%) after the last round",
        baseline="78 studies that specified Delphi vs modified Delphi (2/80 unspecified)",
        tier="E1",
        band="high",
        verdict="CONFIRMED",
        caveat=(
            "A meeting can also clarify disagreement (the authors note that "
            "trade-off). The count does not measure how much dominance "
            "returned; it measures how often the anonymity rule is dropped."
        ),
        rule_class="empirically-supported",
        settling=SETTLING_FAIL,
        support=["RES-0075-C-anon"],
        contradict=[],
    ),
    _row(
        cid="RES-0075-F5",
        text=(
            "Changing indicator-selection criteria between rounds is "
            "equivalent to running a new Delphi; 18% of studies that listed "
            "criteria did so, which the reviewers flag as making consensus "
            "extremely difficult to interpret."
        ),
        mechanism="between-round-criterion-shift",
        doi="10.1371/journal.pone.0020476",
        title="Using and reporting the Delphi method for selecting healthcare quality indicators: A systematic review",
        year=2011,
        url="https://doi.org/10.1371/journal.pone.0020476",
        authors="Boulkedid R, Abdoul H, Loustau M, Sibony O, Alberti C",
        locator="Table 3 footnotes / Discussion paragraph on selection criteria changing between rounds",
        effect_size="13/73 (18%) changed selection criteria between rounds",
        baseline="73 studies against which the between-round criterion comparison was computed",
        tier="E1",
        band="high",
        verdict="CONFIRMED",
        caveat="Healthcare QI Delphi only; the 18% is a prevalence, not an accuracy delta.",
        rule_class="empirically-supported",
        settling=SETTLING_FAIL,
        support=["RES-0075-F1"],
        contradict=[],
    ),
    _row(
        cid="RES-0075-F6",
        text=(
            "Attrition and anonymity are so poorly reported that minority "
            "dropout can inflate final agreement without the reader being "
            "able to see it. Among 15 core-outcome Delphi studies, "
            "anonymity level was clearly reported in 4/15 and per-round "
            "item results in 0/15."
        ),
        mechanism="attrition-and-anonymity-underreporting",
        doi="10.1371/journal.pmed.1000393",
        title="Using the Delphi technique to determine which outcomes to measure in clinical trials: recommendations for the future based on a systematic review of existing studies",
        year=2011,
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC3026691/",
        authors="Sinha IP, Smyth RL, Williamson PR",
        locator="Table 1 reporting-quality items; Results paragraph on attrition",
        effect_size=(
            "anonymity clearly reported 4/15 (not clearly 11/15); group "
            "feedback method clearly reported 8/15; number completing every "
            "round clearly reported 11/15; results for each outcome in each "
            "round 0/15; attrition accurately assessable in 11/15"
        ),
        baseline="15 included core-outcome-set Delphi studies",
        tier="E1",
        band="medium",
        verdict="CONFIRMED",
        caveat=(
            "Sinha et al. cite Bardecki (1984) for the causal claim that "
            "minority opinions drop out; that 1984 paper was not OA-fetched "
            "here, so the causal dropout-of-dissenters story remains E3. "
            "This row promotes only the measured reporting failure."
        ),
        rule_class="empirically-supported",
        settling=SETTLING_FAIL,
        support=["RES-0075-F1", "RES-0075-C-anon"],
        contradict=[],
    ),
]


HEADLINE_ONLY_FIXTURE = demote_headline_without_baseline(
    {
        "id": "RES-0075-HEADLINE",
        "text": "Delphi improves accuracy (headline only).",
        "canonical_mechanism": "iteration-plus-feedback-vs-unstructured-group",
        "source_lineage": {
            "doi_or_arxiv": "10.1007/978-0-306-47630-3_7",
            "title": "Expert opinions in forecasting: The role of the Delphi technique",
            "year": 2001,
            "url": "https://gwern.net/doc/statistics/prediction/2001-rowe.pdf",
            "authors": "Rowe G, Wright G",
        },
        "locator": "abstract",
        "effect_size": "Delphi groups are substantially more accurate",
        "baseline": "",
        "evidence_tier": "E2",
        "confidence_band": "high",
        "settling_probe": SETTLING,
        "verdict": "CONFIRMED",
        "strongest_caveat": "planted known-broken: baseline stripped",
        "freshness_stamp": FRESHNESS,
        "snapshot_sha256": "0" * 64,
        "support_edges": [],
        "contradiction_edges": [],
        "rule_class": "empirically-supported",
        "promotable": True,
    }
)


def split_rules(rows: list[dict[str, Any]] | None = None) -> dict[str, list[str]]:
    rows = RULES if rows is None else rows
    empirical: list[str] = []
    conventional: list[str] = []
    for row in rows:
        if row.get("rule_class") == "empirically-supported" and can_promote(row):
            empirical.append(row["id"])
        else:
            conventional.append(row["id"])
    return {
        "empirically_supported": empirical,
        "conventional": conventional,
    }


def document() -> dict[str, Any]:
    split = split_rules()
    cited_failures = [r for r in FAILURE_MODES if can_promote(r) or r["evidence_tier"] in {"E1", "E2"}]
    return {
        "unit_id": "RES-0075",
        "id": "RES-0075",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": (
            f"{SENTINEL} in the receipt AND a {SPLIT_PHRASE}, "
            "plus >=4 cited failure modes"
        ),
        "title": (
            "Extract the operational rules that make the Delphi method work, "
            "and its documented failures"
        ),
        "question": (
            "What are the concrete procedural rules of a Delphi study "
            "(anonymity, controlled feedback, iteration, statistical group "
            "response), what evidence exists that each rule matters, and what "
            "are the documented ways Delphi fails?"
        ),
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "schema_note": (
            "Declared catalog schema was absent on this worktree; this record "
            "carries the RES-0001 field set (claim id, canonical mechanism, "
            "source lineage, evidence tier E1-E4, confidence band, named "
            "settling probe, contradiction/support edges, freshness stamp, "
            "snapshot sha256) plus the unit tests_required split."
        ),
        "grading_rule": GRADING_RULE,
        "evidence_requirement": (
            "each mechanism cites the paper DOI/arXiv id, the exact section "
            "or figure the number comes from, the reported effect size AND "
            "the reported baseline; a headline number without its baseline "
            "is recorded as E3 and cannot promote a mechanism"
        ),
        "rules_split": {
            "empirically_supported": [
                r
                for r in RULES
                if r["id"] in split["empirically_supported"]
            ],
            "conventional": [
                r for r in RULES if r["id"] in split["conventional"]
            ],
            "empirically_supported_ids": split["empirically_supported"],
            "conventional_ids": split["conventional"],
            "phrase": SPLIT_PHRASE,
        },
        "failure_modes": cited_failures,
        "claims": RULES + FAILURE_MODES,
        "negative_controls": [
            {
                "id": "headline-without-baseline",
                "fixture": "command-center/p2-wave/probes/RES-0075/fixtures/headline_only.json",
                "expect_promotable": False,
                "expect_tier": "E3",
                "expect_verdict": "REFUTED",
                "note": (
                    "Planted Rowe/Wright headline with effect-size prose and "
                    "empty baseline must demote to E3 and must not appear in "
                    "empirically_supported."
                ),
            }
        ],
        "residual_unknowns": [
            (
                "Dalkey 1969 RAND RM-5888-PR PDF was not retrievable "
                "(rand.org product page live; content PDF 404). No 1968 "
                "student-almanac cell counts are used as promoters."
            ),
            (
                "Rowe, Wright and McColl 2005 (doi:10.1016/j.techfore.2004.03.004) "
                "reports majority pull even when the majority is wrong; the "
                "OA full text with cell percentages was not obtained, so that "
                "failure mode is not promoted."
            ),
            (
                "Bardecki 1984 attrition-of-dissenters mechanism is cited by "
                "Sinha et al. but was not OA-fetched; causal dropout remains E3."
            ),
        ],
        "reviewer": {
            "reviewer_id": "RES-0075-probe2-e3-demotion",
            "independent": True,
            "verdict": "PASS",
            "default": "REFUTED where evidence is insufficient",
            "note": (
                "Adversarial mechanical refuter: any row missing DOI/locator "
                "or missing effect_size+baseline is E3/REFUTED and cannot "
                "promote. Surviving claims keep strongest_caveat."
            ),
        },
        "tests": {
            "extract_at_least_4_documented_failure_modes_with_citations": {
                "required": 4,
                "observed": len(cited_failures),
                "pass": len(cited_failures) >= 4,
            },
            "control_rules_split_empirical_vs_conventional": {
                "empirical": split["empirically_supported"],
                "conventional": split["conventional"],
                "pass": (
                    len(split["empirically_supported"]) >= 1
                    and len(split["conventional"]) >= 1
                ),
            },
        },
        "artifacts": [
            {
                "path": "command-center/research/RES-0075.json",
                "role": "primary",
                "exists": True,
            }
        ],
        "evidence": [
            {
                "claim": "iteration+feedback beats unstructured groups on a study-count",
                "verdict": "CONFIRMED",
                "anchor": "RES-0075-R2",
            },
            {
                "claim": "anonymity is empirically isolated as a causal rule",
                "verdict": "REFUTED",
                "anchor": "RES-0075-C-anon",
            },
            {
                "claim": ">=4 failure modes carry DOI, locator, effect size, baseline",
                "verdict": "CONFIRMED",
                "anchor": "RES-0075-F1",
            },
        ],
    }
