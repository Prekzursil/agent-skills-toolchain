#!/usr/bin/env python3
"""Harvest catalog: sources, declared protocol parameters, claim extractors.

Phrases are matched against snapshot bytes. A claim is emitted only when its
required phrase is present in the selected source body. Systematic dual-screen
also requires the paired Crossref JSON to contain structured_phrase.
"""
from __future__ import annotations

from typing import Any

UNIT = "RES-0192"
SENTINEL = "SUCCESS:RES-0192"

# Declared parameter vectors. These are the fingerprints IMP-0234 requires
# to differ: not prose labels, but computable fields.
RAPID_PARAMS: dict[str, Any] = {
    "id": "rapid",
    "databases": ["pubmed"],
    "grey_literature": False,
    "contradiction_search": False,
    "dual_screen": False,
    "max_records": 2,
    "sort": "year_desc",
    "year_min": None,
}

SYSTEMATIC_PARAMS: dict[str, Any] = {
    "id": "systematic",
    "databases": ["pubmed", "embase", "cochrane", "web"],
    "grey_literature": True,
    "contradiction_search": True,
    "dual_screen": True,
    "max_records": None,
    "sort": "year_desc",
    "year_min": None,
}

# Factor scale: 0=low, 1=medium, 2=high. Reversibility 0=irreversible, 2=fully reversible.
QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "Q1",
        "text": (
            "Does PRISMA 2020 specify a 27-item checklist for systematic "
            "review reporting?"
        ),
        "decision": (
            "Whether this program may cite PRISMA 2020 as a 27-item reporting "
            "instrument without a broader methods search."
        ),
        "factors": {
            "reversibility": 2,
            "blast": 0,
            "density": 0,
            "contradiction": 0,
        },
    },
    {
        "id": "Q2",
        "text": (
            "For an irreversible, high-blast decision, can a rapid review be "
            "treated as interchangeable with a systematic review?"
        ),
        "decision": (
            "Whether this program may substitute a rapid review for a "
            "systematic review when the call is irreversible and high-blast."
        ),
        "factors": {
            "reversibility": 0,
            "blast": 2,
            "density": 2,
            "contradiction": 2,
        },
    },
    {
        "id": "Q3",
        "text": (
            "Must a team considering a rapid review of intervention "
            "effectiveness first judge whether a rapid review (versus a "
            "systematic review) is appropriate?"
        ),
        "decision": (
            "Whether this program's rapid-review blueprint requires an "
            "appropriateness gate before streamlining methods."
        ),
        "factors": {
            "reversibility": 2,
            "blast": 1,
            "density": 1,
            "contradiction": 0,
        },
    },
]

# kind: prose-source | structured-api
SOURCES: list[dict[str, Any]] = [
    {
        "id": "prisma-2020-pmc",
        "kind": "prose-source",
        "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8005924/",
        "doi": "10.1136/bmj.n71",
        "year": 2021,
        "databases": ["pubmed", "web"],
        "grey": False,
        "dissenting": False,
        "questions": ["Q1"],
        "title": "The PRISMA 2020 statement: an updated guideline for reporting systematic reviews",
    },
    {
        "id": "prisma-2020-crossref",
        "kind": "structured-api",
        "url": "https://api.crossref.org/works/10.1136/bmj.n71",
        "doi": "10.1136/bmj.n71",
        "year": 2021,
        "databases": ["pubmed"],
        "grey": False,
        "dissenting": False,
        "questions": ["Q1"],
        "title": "Crossref work 10.1136/bmj.n71",
        "pairs_with": "prisma-2020-pmc",
    },
    {
        "id": "cochrane-rr-2024-crossref",
        "kind": "structured-api",
        "url": "https://api.crossref.org/works/10.1136/bmj-2023-076335",
        "doi": "10.1136/bmj-2023-076335",
        "year": 2024,
        "databases": ["pubmed"],
        "grey": False,
        "dissenting": False,
        "questions": ["Q2", "Q3"],
        "title": "Crossref work 10.1136/bmj-2023-076335",
        "pairs_with": "cochrane-rr-methods-web",
    },
    {
        "id": "garritty-2021-pmc",
        "kind": "prose-source",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7557165/",
        "doi": "10.1016/j.jclinepi.2020.10.007",
        "year": 2021,
        "databases": ["pubmed", "web"],
        "grey": False,
        "dissenting": False,
        "questions": ["Q2", "Q3"],
        "title": "Cochrane Rapid Reviews Methods Group interim guidance (JCE 2021)",
    },
    {
        "id": "garritty-2021-crossref",
        "kind": "structured-api",
        "url": "https://api.crossref.org/works/10.1016/j.jclinepi.2020.10.007",
        "doi": "10.1016/j.jclinepi.2020.10.007",
        "year": 2021,
        "databases": ["pubmed"],
        "grey": False,
        "dissenting": False,
        "questions": ["Q2", "Q3"],
        "title": "Crossref work 10.1016/j.jclinepi.2020.10.007",
        "pairs_with": "garritty-2021-pmc",
    },
    {
        "id": "tricco-2015-bmc",
        "kind": "prose-source",
        "url": "https://bmcmedicine.biomedcentral.com/articles/10.1186/s12916-015-0465-6",
        "doi": "10.1186/s12916-015-0465-6",
        "year": 2015,
        "databases": ["pubmed", "embase", "web"],
        "grey": False,
        "dissenting": True,
        "questions": ["Q2"],
        "title": "A scoping review of rapid review methods (Tricco 2015)",
    },
    {
        "id": "tricco-2015-crossref",
        "kind": "structured-api",
        "url": "https://api.crossref.org/works/10.1186/s12916-015-0465-6",
        "doi": "10.1186/s12916-015-0465-6",
        "year": 2015,
        "databases": ["pubmed", "embase"],
        "grey": False,
        "dissenting": True,
        "questions": ["Q2"],
        "title": "Crossref work 10.1186/s12916-015-0465-6",
        "pairs_with": "tricco-2015-bmc",
    },
    {
        "id": "ganann-2010-is",
        "kind": "prose-source",
        "url": "https://implementationscience.biomedcentral.com/articles/10.1186/1748-5908-5-56",
        "doi": "10.1186/1748-5908-5-56",
        "year": 2010,
        "databases": ["pubmed", "embase", "web"],
        "grey": False,
        "dissenting": True,
        "questions": ["Q2"],
        "title": "Rapid reviews versus systematic reviews (Ganann 2010)",
    },
    {
        "id": "ganann-2010-crossref",
        "kind": "structured-api",
        "url": "https://api.crossref.org/works/10.1186/1748-5908-5-56",
        "doi": "10.1186/1748-5908-5-56",
        "year": 2010,
        "databases": ["pubmed", "embase"],
        "grey": False,
        "dissenting": True,
        "questions": ["Q2"],
        "title": "Crossref work 10.1186/1748-5908-5-56",
        "pairs_with": "ganann-2010-is",
    },
    {
        "id": "cochrane-rr-methods-web",
        "kind": "prose-source",
        "url": "https://methods.cochrane.org/rapidreviews/cochrane-rr-methods",
        "doi": None,
        "year": 2024,
        "databases": ["cochrane", "web"],
        "grey": True,
        "dissenting": False,
        "questions": ["Q2", "Q3"],
        "title": "Cochrane Rapid Reviews Methods Group methods page",
    },
]

# Claim extractors. would_change_decision: if this claim is in systematic but
# not rapid, would the program's decision on that question change?
CLAIMS: list[dict[str, Any]] = [
    {
        "id": "C-PRISMA-27",
        "question_id": "Q1",
        "source_id": "prisma-2020-pmc",
        "structured_source_id": "prisma-2020-crossref",
        "phrase": "27-item checklist",
        "structured_phrase": "PRISMA 2020",
        "text": "PRISMA 2020 specifies a 27-item checklist for systematic review reporting.",
        "would_change_decision": True,
        "sherman_kent_band": "almost-certain",
    },
    {
        "id": "C-PRISMA-FLOW",
        "question_id": "Q1",
        "source_id": "prisma-2020-pmc",
        "structured_source_id": "prisma-2020-crossref",
        "phrase": "flow diagram",
        "structured_phrase": "systematic reviews",
        "text": "PRISMA 2020 also includes a flow diagram for study selection (not required to answer the 27-item count).",
        "would_change_decision": False,
        "sherman_kent_band": "almost-certain",
    },
    {
        "id": "C-RR-LESS-COMPREHENSIVE",
        "question_id": "Q2",
        "source_id": "tricco-2015-bmc",
        "structured_source_id": "tricco-2015-crossref",
        "phrase": "simplified or omitted",
        "structured_phrase": "rapid review methods",
        "text": (
            "Tricco 2015: rapid reviews simplify or omit systematic-review "
            "components, so they are not a drop-in replacement for a full review."
        ),
        "would_change_decision": True,
        "sherman_kent_band": "likely",
    },
    {
        "id": "C-RR-APPROPRIATENESS-Q2",
        "question_id": "Q2",
        "source_id": "garritty-2021-pmc",
        "structured_source_id": "garritty-2021-crossref",
        "phrase": "appropriateness of undertaking RRs",
        "structured_phrase": "rapid reviews",
        "text": (
            "Cochrane 2021 interim guidance flags the appropriateness of "
            "undertaking rapid reviews versus traditional systematic reviews."
        ),
        "would_change_decision": True,
        "sherman_kent_band": "likely",
    },
    {
        "id": "C-RR-26-INTERIM",
        "question_id": "Q2",
        "source_id": "garritty-2021-pmc",
        "structured_source_id": "garritty-2021-crossref",
        "phrase": "26 recommendations",
        "structured_phrase": "rapid reviews",
        "text": "Cochrane 2021 interim guidance listed 26 recommendations for rapid reviews.",
        "would_change_decision": False,
        "sherman_kent_band": "almost-certain",
    },
    {
        "id": "C-50-METHODS",
        "question_id": "Q2",
        "source_id": "tricco-2015-bmc",
        "structured_source_id": "tricco-2015-crossref",
        "phrase": "Fifty unique",
        "structured_phrase": "rapid review methods",
        "text": (
            "Tricco 2015 catalogued 50 unique rapid-review methods; 'rapid review' "
            "is not one interchangeable protocol."
        ),
        "would_change_decision": True,
        "sherman_kent_band": "likely",
    },
    {
        "id": "C-4-COMPARISON",
        "question_id": "Q2",
        "source_id": "tricco-2015-bmc",
        "structured_source_id": "tricco-2015-crossref",
        "phrase": "four comparison",
        "structured_phrase": "scoping review",
        "text": (
            "Tricco 2015 identified only four comparison papers of rapid versus "
            "systematic reviews; interchangeability is not established by a large "
            "head-to-head evidence base."
        ),
        "would_change_decision": True,
        "sherman_kent_band": "likely",
    },
    {
        "id": "C-RR-BIAS-RISK",
        "question_id": "Q2",
        "source_id": "tricco-2015-bmc",
        "structured_source_id": "tricco-2015-crossref",
        "phrase": "susceptible to biased results",
        "structured_phrase": "rapid reviews",
        "text": (
            "Tricco 2015 warns rapid reviews might be susceptible to biased "
            "results as a consequence of streamlining the systematic review process."
        ),
        "would_change_decision": True,
        "sherman_kent_band": "likely",
    },
    {
        "id": "C-GANANN-COMPARE",
        "question_id": "Q2",
        "source_id": "ganann-2010-is",
        "structured_source_id": "ganann-2010-crossref",
        "phrase": "rapid reviews",
        "structured_phrase": "Rapid reviews",
        "text": (
            "Ganann 2010 compares rapid-review methods against systematic reviews "
            "and treats rapid reviews as an emerging, abbreviated form rather than "
            "a drop-in replacement."
        ),
        "would_change_decision": True,
        "sherman_kent_band": "likely",
    },
    {
        "id": "C-RR-APPROPRIATENESS-Q3",
        "question_id": "Q3",
        "source_id": "garritty-2021-pmc",
        "structured_source_id": "garritty-2021-crossref",
        "phrase": "appropriateness of undertaking RRs",
        "structured_phrase": "rapid reviews",
        "text": (
            "Cochrane 2021 interim guidance says teams must consider the "
            "appropriateness of undertaking rapid reviews versus traditional SRs."
        ),
        "would_change_decision": True,
        "sherman_kent_band": "likely",
    },
    {
        "id": "C-RR-URGENT-PRIORITY",
        "question_id": "Q3",
        "source_id": "garritty-2021-pmc",
        "structured_source_id": "garritty-2021-crossref",
        "phrase": "urgent and high priority",
        "structured_phrase": "rapid reviews",
        "text": (
            "Cochrane 2021 interim guidance recommends Cochrane rapid reviews "
            "address urgent and high-priority questions requested by decision makers."
        ),
        "would_change_decision": False,
        "sherman_kent_band": "likely",
    },
    {
        "id": "C-RR-METHODS-PAGE",
        "question_id": "Q3",
        "source_id": "cochrane-rr-methods-web",
        "structured_source_id": "cochrane-rr-2024-crossref",
        "phrase": "updated guidance",
        "structured_phrase": "rapid reviews of effectiveness",
        "text": (
            "The Cochrane RRMG methods page points to updated 2024 guidance "
            "for rapid reviews of effectiveness."
        ),
        "would_change_decision": False,
        "sherman_kent_band": "likely",
    },
]


def source_by_id(sid: str) -> dict[str, Any]:
    for row in SOURCES:
        if row["id"] == sid:
            return row
    raise KeyError(sid)


def question_by_id(qid: str) -> dict[str, Any]:
    for row in QUESTIONS:
        if row["id"] == qid:
            return row
    raise KeyError(qid)
