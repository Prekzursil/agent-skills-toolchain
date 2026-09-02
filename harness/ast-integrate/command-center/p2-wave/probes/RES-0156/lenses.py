#!/usr/bin/env python3
"""RES-0156 lens table: grounded vs ideation vs contested.

_USER-PROMPTS.md and rules/common/fan-out-contract.md section A9 are absent
on this worktree. The 12-lens set is reconstructed from catalog parentheticals
that quote those missing lines, plus the four research blueprints (evidence-map
through source-code-archaeology) that a gem-hunt fan-out uses to ask "is this
already in THIS estate?" versus "is this a vendor/external mechanism?".

Unnamed spec lines 10702/10703/10706/10709-10711 are recorded as ABSENT, not
invented. Confidence for those four slots is therefore likely, not
almost-certain.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
TAXONOMY = (
    "command-center/p2-wave/probes/IMP-0178/fixtures/spec_taxonomy.md"
)

# Catalog parentheticals that name a research mode (live file:line via locator).
MODE_NEEDLES = {
    "broad-landscape-scan": "_USER-PROMPTS.md:10704-10705 (broad landscape scan, targeted question answering)",
    "targeted-question-answering": "_USER-PROMPTS.md:10704-10705 (broad landscape scan, targeted question answering)",
    "contradiction-hunt": "_USER-PROMPTS.md:10707 (contradiction hunt)",
    "negative-result-hunt": "_USER-PROMPTS.md:10708 (negative-result hunt)",
    "gem-hunt": "_USER-PROMPTS.md:10712 (gem hunt)",
    "source-quality-audit": "_USER-PROMPTS.md:10713 (source-quality audit)",
    "freshness-revalidation-audit": "_USER-PROMPTS.md:10714 (freshness/revalidation audit)",
    "legal-license-review": "_USER-PROMPTS.md:10715 (legal and licence review)",
}

BLUEPRINT_NEEDLE = (
    "Target: implement 4 blueprints - evidence-map, fact-citation-audit, "
    "official-doc-audit, source-code-archaeology"
)

GROUNDED = "GROUNDED"
IDEATION = "IDEATION"
CONTESTED = "CONTESTED"
STANDARDS = (GROUNDED, IDEATION, CONTESTED)

# Why each standard is assigned. CONTESTED is the required negative control:
# the lens is not forced into GROUNDED or IDEATION by preference.
LENSES: list[dict] = [
    {
        "id": "broad-landscape-scan",
        "spec_ref": "10704",
        "standard": IDEATION,
        "must_cite": "external-url-or-doi",
        "forbidden": "repo-file-line-as-the-finding",
        "reason": (
            "Catalog names this as a research mode alongside targeted Q&A. "
            "A landscape scan's object is the outside world; citing this "
            "repository as the finding restates the briefing pack."
        ),
        "reconstruction": "catalog-parenthetical",
    },
    {
        "id": "targeted-question-answering",
        "spec_ref": "10705",
        "standard": CONTESTED,
        "must_cite": "bound-by-object-scope",
        "forbidden": "assigning-a-standard-by-preference",
        "reason": (
            "The same mode answers 'what does THIS catalog/code say' and "
            "'what does the literature say'. The object of inquiry is not "
            "implied by the lens name. Record CONTESTED until object_scope "
            "is bound by the deciding experiment."
        ),
        "reconstruction": "catalog-parenthetical",
        "deciding_experiment": "bind-object-scope",
    },
    {
        "id": "contradiction-hunt",
        "spec_ref": "10707",
        "standard": IDEATION,
        "must_cite": "external-url-or-doi",
        "forbidden": "repo-file-line-as-the-finding",
        "reason": (
            "Catalog pairs 10707 with 10700 (counterevidence to every major "
            "conclusion) on RES-0147, whose object is disconfirming search "
            "against claims, not re-reading catalog disagreements."
        ),
        "reconstruction": "catalog-parenthetical",
    },
    {
        "id": "negative-result-hunt",
        "spec_ref": "10708",
        "standard": IDEATION,
        "must_cite": "external-url-or-doi",
        "forbidden": "repo-file-line-as-the-finding",
        "reason": "Catalog requires retrieving real negative results from venues.",
        "reconstruction": "catalog-parenthetical",
    },
    {
        "id": "gem-hunt",
        "spec_ref": "10712",
        "standard": IDEATION,
        "must_cite": "external-url-or-doi",
        "forbidden": "repo-file-line-as-the-finding",
        "reason": (
            "A gem is a mechanism in another community/tool. Grounding in "
            "this repository produces duplicate reads of skills/catalog and "
            "zero novel external citations."
        ),
        "reconstruction": "catalog-parenthetical",
    },
    {
        "id": "source-quality-audit",
        "spec_ref": "10713",
        "standard": GROUNDED,
        "must_cite": "repo-file-line",
        "forbidden": "external-url-as-the-only-anchor",
        "reason": (
            "ADV-0079 audits THIS pipeline's scoring of a planted corpus. "
            "The claim is about files in this estate."
        ),
        "reconstruction": "catalog-parenthetical",
    },
    {
        "id": "freshness-revalidation-audit",
        "spec_ref": "10714",
        "standard": GROUNDED,
        "must_cite": "repo-file-line",
        "forbidden": "external-url-as-the-only-anchor",
        "reason": "Revalidation is of stored claims in THIS corpus.",
        "reconstruction": "catalog-parenthetical",
    },
    {
        "id": "legal-license-review",
        "spec_ref": "10715",
        "standard": IDEATION,
        "must_cite": "external-url-or-doi",
        "forbidden": "repo-file-line-as-the-finding",
        "reason": (
            "IMP-0156/RES-0135 extract licences of candidates/upstream, not "
            "this estate's own LICENSE as the finding. Repo policy prose is "
            "not a third-party licence."
        ),
        "reconstruction": "catalog-parenthetical",
    },
    {
        "id": "evidence-map",
        "spec_ref": "blueprint-5",
        "standard": GROUNDED,
        "must_cite": "repo-file-line",
        "forbidden": "external-url-as-the-only-anchor",
        "reason": "Maps THIS program's claims to their anchors.",
        "reconstruction": "catalog-blueprint-5-8",
    },
    {
        "id": "fact-citation-audit",
        "spec_ref": "blueprint-6",
        "standard": GROUNDED,
        "must_cite": "repo-file-line",
        "forbidden": "external-url-as-the-only-anchor",
        "reason": "Resolves citations that THIS corpus already made.",
        "reconstruction": "catalog-blueprint-5-8",
    },
    {
        "id": "official-doc-audit",
        "spec_ref": "blueprint-7",
        "standard": IDEATION,
        "must_cite": "external-url-or-doi",
        "forbidden": "repo-file-line-as-the-finding",
        "reason": "Audits vendor/official docs, not this repository's notes.",
        "reconstruction": "catalog-blueprint-5-8",
    },
    {
        "id": "source-code-archaeology",
        "spec_ref": "blueprint-8",
        "standard": GROUNDED,
        "must_cite": "repo-file-line",
        "forbidden": "external-url-as-the-only-anchor",
        "reason": (
            "In gem-hunt fan-out this lens answers 'is the mechanism already "
            "implemented HERE?'. Findings are file:line in this worktree."
        ),
        "reconstruction": "catalog-blueprint-5-8",
    },
]

LENS_BY_ID = {row["id"]: row for row in LENSES}

# Catalog assigned roles → default lens for scoring the prior corpus.
# Units whose role does not map stay UNMAPPED and are counted separately.
ROLE_TO_LENS = {
    "gem-hunter": "gem-hunt",
    "gem-hunt-lead": "gem-hunt",
    "contradiction-refuter": "contradiction-hunt",
    "legal-licence-reviewer": "legal-license-review",
    "citation-auditor": "fact-citation-audit",
    "blind-spot-auditor": "source-quality-audit",
    "deliberation-scientist": "broad-landscape-scan",
    "mechanism-extractor": "gem-hunt",
    "salvage-analyst": "gem-hunt",
    "salvage-archaeologist": "gem-hunt",
    "prior-art-analyst": "official-doc-audit",
    "security-researcher": "source-code-archaeology",
    "supply-chain-analyst": "source-code-archaeology",
    "researcher": "targeted-question-answering",
    "schema-author": "evidence-map",
    "teardown-analyst": "source-code-archaeology",
    "benchmark-analyst": "broad-landscape-scan",
    "measurement-engineer": "fact-citation-audit",
    "adversarial-refuter": "contradiction-hunt",
}


def locate_needle(needle: str, rel: str = CATALOG) -> str | None:
    path = REPO / rel
    if not path.is_file():
        return None
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return None


def lens_table_with_anchors() -> list[dict]:
    rows = []
    for item in LENSES:
        row = dict(item)
        if item["id"] in MODE_NEEDLES:
            row["catalog_anchor"] = locate_needle(MODE_NEEDLES[item["id"]])
        else:
            row["catalog_anchor"] = locate_needle(BLUEPRINT_NEEDLE)
        row["taxonomy_anchor"] = locate_needle(f"- {item['id']}", TAXONOMY)
        rows.append(row)
    return rows


def effective_standard(lens_id: str, object_scope: str | None) -> str:
    """Bind CONTESTED by object_scope; never by preference."""
    lens = LENS_BY_ID[lens_id]
    standard = str(lens["standard"])
    if standard != CONTESTED:
        return standard
    scope = (object_scope or "").strip().lower()
    if scope == "estate":
        return GROUNDED
    if scope == "external":
        return IDEATION
    return CONTESTED
