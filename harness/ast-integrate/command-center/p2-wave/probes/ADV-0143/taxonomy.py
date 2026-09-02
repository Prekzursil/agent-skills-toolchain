"""Closed content-class taxonomy, path/body classifiers, and verdict policy.

Engineering risk assessment for the owner. Explicitly not legal advice.
"""
from __future__ import annotations

from pathlib import Path

VERDICTS = (
    "REDISTRIBUTABLE",
    "SUMMARISE-ONLY",
    "EXCLUDE",
    "NEEDS-OWNER-DECISION",
)

# 12 classes: 10 adjudicated in the stability control plus two residual
# bins so the 30-chunk sample has no unclassifiable remainder.
CLASS_IDS = (
    "quoted-vendor-documentation",
    "scraped-marketplace-or-forum-text",
    "vendor-registry-api-captures",
    "transcript-third-party-messages",
    "ai-generated-uncertain-provenance",
    "third-party-personal-data",
    "third-party-license-notice",
    "first-party-original-source",
    "first-party-program-records",
    "synthetic-probe-fixtures",
    "undecodable-or-binary",
    "empty-or-whitespace",
)

STABILITY_CLASS_IDS = CLASS_IDS[:10]

PERSONAL_MARKERS = ("Prekzursil", "C:/Users/", "C:\\Users\\")

POLICY = {
    "quoted-vendor-documentation": {
        "verdict": "SUMMARISE-ONLY",
        "legal_basis": {
            "kind": "copyright-quotation-fair-dealing",
            "citation": (
                "Vendor documentation captures under "
                "command-center/p2-wave/probes/RES-0038/captures/ are "
                "verbatim third-party literary works (MCP registry docs). "
                "PR-ONLY still publishes a PR diff and CI logs."
            ),
            "argument": (
                "A PR may cite a short attributed excerpt; shipping the "
                "captured files wholesale is redistribution of vendor prose. "
                "Summarise in first-party words; do not quote beyond a short "
                "attributed span the owner has reviewed."
            ),
        },
        "residual_risk": (
            "If a reviewer treats a long capture as fair dealing, the PR "
            "diff still copies the vendor's expression into a public Git "
            "host. Wrong-side risk: copyright complaint on the PR."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "scraped-marketplace-or-forum-text": {
        "verdict": "SUMMARISE-ONLY",
        "legal_basis": {
            "kind": "platform-terms-and-copyright",
            "citation": (
                "PulseMCP DNS TXT scrape and similar marketplace/forum "
                "captures are third-party publication, not first-party "
                "authorship."
            ),
            "argument": (
                "Marketplace and DNS attestation strings are other people's "
                "publication. Under PR-ONLY, summarise the operational fact "
                "(a TXT record existed) rather than republishing the scraped "
                "blob."
            ),
        },
        "residual_risk": (
            "If the scrape is treated as REDISTRIBUTABLE, platform terms or "
            "the publisher's copyright in the record text travel with the PR."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "vendor-registry-api-captures": {
        "verdict": "SUMMARISE-ONLY",
        "legal_basis": {
            "kind": "copyright-and-registry-terms",
            "citation": (
                "npm and MCP registry JSON/YAML captures (e.g. "
                "@brave/brave-search-mcp-server 2.1.3) are third-party "
                "database/API output."
            ),
            "argument": (
                "Structured registry dumps are still someone else's "
                "compilation. PR-ONLY does not license wholesale republication. "
                "Keep hashes, URLs and measured facts; do not re-host the dump."
            ),
        },
        "residual_risk": (
            "If a dump is committed as if it were first-party schema, the PR "
            "redistributes vendor compilation. Wrong-side risk: registry TOS."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "transcript-third-party-messages": {
        "verdict": "EXCLUDE",
        "legal_basis": {
            "kind": "data-protection-and-third-party-speech",
            "citation": (
                "Transcript excerpts that contain other seats' or other "
                "people's messages are third-party personal data / speech, "
                "even when the seats are labelled as fixtures."
            ),
            "argument": (
                "A PR that includes shared-transcript fields republishes "
                "other parties' words. Exclude from the publishable set; "
                "summarise process facts without message bodies."
            ),
        },
        "residual_risk": (
            "If EXCLUDE is ignored, CI logs reprint the messages. Residual: "
            "some fixtures are synthetic personas, so the privacy harm may "
            "be lower than for a real human transcript — still excluded."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "ai-generated-uncertain-provenance": {
        "verdict": "NEEDS-OWNER-DECISION",
        "legal_basis": {
            "kind": "vendor-terms-on-generated-output",
            "citation": (
                "RES-0125 asks what vendor terms and provenance norms require "
                "for model-generated blueprints. RES-0125.json is absent on "
                "this worktree, so terms were not re-measured here."
            ),
            "argument": (
                "Product blueprints may be model-generated. Without the "
                "obligation table, this unit will not guess a redistribute "
                "or exclude rule. Owner must decide after RES-0125 lands."
            ),
        },
        "residual_risk": (
            "If the owner treats them as first-party and they are not, "
            "vendor output terms and provenance labelling are missed. If "
            "the owner excludes them and they are ordinary first-party JSON, "
            "the PR is over-redacted."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "third-party-personal-data": {
        "verdict": "EXCLUDE",
        "legal_basis": {
            "kind": "data-protection",
            "citation": (
                "Owner/estate identifiers (Windows account name Prekzursil, "
                "C:/Users/… paths) are personal or estate-identifying data. "
                "PR-ONLY still publishes them in the diff."
            ),
            "argument": (
                "Strip or tokenise identifiers before a PR. A path that names "
                "a person is not first-party expression; it is personal data."
            ),
        },
        "residual_risk": (
            "If EXCLUDE is skipped, the PR maps the owner's machine identity "
            "to the public git host. Residual: some hits are documented "
            "historical paths rather than live PII, but they still identify."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "third-party-license-notice": {
        "verdict": "REDISTRIBUTABLE",
        "legal_basis": {
            "kind": "licence-term-required-notice",
            "citation": (
                "Permission-grant / MIT-style licence notices are third-party "
                "text whose licence typically requires the notice to travel "
                "with the software."
            ),
            "argument": (
                "Redistributing the notice is the usual condition of using "
                "the licensed work. Under PR-ONLY, keep the notice intact "
                "rather than summarising it away."
            ),
        },
        "residual_risk": (
            "If a notice is actually a different licence that forbids "
            "copying, REDISTRIBUTABLE is the wrong side. This tree has no "
            "fetched LICENSE corpus (RES-0121 absent); the plant is MIT grant "
            "language only."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "first-party-original-source": {
        "verdict": "REDISTRIBUTABLE",
        "legal_basis": {
            "kind": "first-party-authorship-plus-owner-release-mode",
            "citation": (
                "Binding owner decision: release mode is PR-ONLY. First-party "
                "source is the intended PR payload, independent of the code "
                "licence lattice (RES-0135 / IMP-0157 / WFA-0139)."
            ),
            "argument": (
                "Original tools/, platform/, and command-center code may leave "
                "the machine as a PR. This is not a licence-compatibility "
                "finding."
            ),
        },
        "residual_risk": (
            "Embedded third-party quotes inside source comments can ride "
            "along. Path-only review misses those; body review and the "
            "personal-data overlay exist to catch the high-severity cases."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "first-party-program-records": {
        "verdict": "REDISTRIBUTABLE",
        "legal_basis": {
            "kind": "first-party-authorship-plus-owner-release-mode",
            "citation": (
                "Schemas, receipts and the work-unit catalog are program "
                "records authored in this tree. PR-ONLY intends them to move."
            ),
            "argument": (
                "Redistribute as part of the PR. Rows that embed personal "
                "identifiers should be classified as personal-data at chunk "
                "granularity, not this class."
            ),
        },
        "residual_risk": (
            "WORK-UNIT-CATALOG.json contains historical Windows paths; those "
            "chunks classify as personal-data. A file-level REDISTRIBUTABLE "
            "verdict can still leak those spans in a full-file add."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "synthetic-probe-fixtures": {
        "verdict": "REDISTRIBUTABLE",
        "legal_basis": {
            "kind": "first-party-test-authorship",
            "citation": (
                "Probe fixtures invented for controls are first-party test "
                "harness text, except when they embed a marked third-party "
                "plant or a live identifier."
            ),
            "argument": (
                "Synthetic fixtures may leave the machine in a PR. Plants "
                "that are licence notices or vendor quotes are classified "
                "under those classes instead."
            ),
        },
        "residual_risk": (
            "A fixture that silently copies vendor prose without markers "
            "would be mis-labelled REDISTRIBUTABLE. The 30-chunk sample is "
            "the completeness check, not a proof that no such fixture exists."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "undecodable-or-binary": {
        "verdict": "EXCLUDE",
        "legal_basis": {
            "kind": "unread-content-cannot-be-adjudicated",
            "citation": (
                "A chunk that is not UTF-8 text cannot be classified as "
                "expression or personal data by this unit's text pipeline."
            ),
            "argument": (
                "Do not put unread blobs on the PR surface. If a binary must "
                "ship, that is an owner decision with a different review."
            ),
        },
        "residual_risk": (
            "A UTF-8 file mis-labelled as binary would be over-excluded. "
            "A binary that is actually a licence or vendor doc would be "
            "under-reviewed."
        ),
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
    "empty-or-whitespace": {
        "verdict": "REDISTRIBUTABLE",
        "legal_basis": {
            "kind": "no-expression",
            "citation": "Whitespace carries no third-party expression.",
            "argument": "Empty chunks are not a redistribution of content.",
        },
        "residual_risk": "None material at this class.",
        "side_of_line": "engineering-risk-assessment-not-legal-advice",
    },
}

EXEMPLARS = [
    {
        "class_id": "quoted-vendor-documentation",
        "path": "command-center/p2-wave/probes/RES-0038/captures/cli-commands.md",
    },
    {
        "class_id": "scraped-marketplace-or-forum-text",
        "path": "command-center/p2-wave/probes/RES-0038/captures/pulsemcp-dns-txt.txt",
    },
    {
        "class_id": "vendor-registry-api-captures",
        "path": "command-center/p2-wave/probes/RES-0038/captures/brave-npm-2.1.3.json",
    },
    {
        "class_id": "transcript-third-party-messages",
        "path": (
            "command-center/p2-wave/probes/CNF-0093/fixtures/"
            "leak-shared-transcript.json"
        ),
    },
    {
        "class_id": "ai-generated-uncertain-provenance",
        "path": "tools/blueprints/product/customer_council/blueprint.json",
    },
    {
        "class_id": "third-party-personal-data",
        "path": "command-center/p2-wave/probes/ARC-0067/identities.py",
    },
    {
        "class_id": "third-party-license-notice",
        "path": (
            "command-center/p2-wave/probes/ADV-0143/fixtures/"
            "third-party-license-plant.txt"
        ),
    },
    {
        "class_id": "first-party-original-source",
        "path": "tools/dispatch/quote_safe_marshaller.py",
    },
    {
        "class_id": "first-party-program-records",
        "path": "command-center/schema/redistribution-adjudication.schema.json",
    },
    {
        "class_id": "synthetic-probe-fixtures",
        "path": "command-center/p2-wave/probes/TST-0327/fixtures/registry.json",
    },
]


def _norm(rel: str) -> str:
    return rel.replace("\\", "/")


def has_personal_marker(text: str) -> bool:
    return any(m in text for m in PERSONAL_MARKERS)


def classify_path(rel: str) -> str | None:
    """Reviewer A: path and filename only. No file body."""
    p = _norm(rel)
    low = p.lower()
    name = p.rsplit("/", 1)[-1].lower()
    if name in {"identities.py", "current_index.json"} or "owners.md" in low:
        return "third-party-personal-data"
    if "third-party-license-plant" in name or "planted-quotation" in name:
        return "third-party-license-notice"
    if "/blueprints/product/" in low:
        return "ai-generated-uncertain-provenance"
    if "leak-shared-transcript" in low or "/transcript" in low:
        return "transcript-third-party-messages"
    if "/res-0038/captures/" in low:
        if name == "capture_index.json":
            return "first-party-program-records"
        if "pulsemcp-dns" in name:
            return "scraped-marketplace-or-forum-text"
        if name.endswith((".md", ".mdx")):
            return "quoted-vendor-documentation"
        if name.endswith((".json", ".yaml", ".yml")):
            return "vendor-registry-api-captures"
        if name.endswith(".txt"):
            return "scraped-marketplace-or-forum-text"
    if "/fixtures/" in low:
        return "synthetic-probe-fixtures"
    if name.endswith((".py", ".pyi")) or "/platform/" in low:
        return "first-party-original-source"
    if (
        "/schema/" in low
        or "/receipts/" in low
        or name == "work-unit-catalog.json"
        or name.endswith(".schema.json")
    ):
        return "first-party-program-records"
    if name.endswith((".json", ".md", ".yml", ".yaml", ".jsonl")):
        return "first-party-program-records"
    return None


def classify_body(text: str) -> str | None:
    """Reviewer B: file/chunk body only. No path."""
    if text is None:
        return "undecodable-or-binary"
    if not str(text).strip():
        return "empty-or-whitespace"
    t = text
    if has_personal_marker(t):
        return "third-party-personal-data"
    if "Permission is hereby granted, free of charge" in t:
        return "third-party-license-notice"
    if "shared_transcript" in t and "seat-a" in t:
        return "transcript-third-party-messages"
    if "Publisher CLI Commands" in t or "mcp-publisher init" in t:
        return "quoted-vendor-documentation"
    if "v=MCPv1" in t or "protonmail-verification=" in t:
        return "scraped-marketplace-or-forum-text"
    if "@brave/brave-search-mcp-server" in t or "registry.npmjs.org" in t:
        return "vendor-registry-api-captures"
    if "CouncilSpec" in t and (
        '"library_index"' in t
        or "council-consumer" in t
        or "customer-council" in t
    ):
        return "ai-generated-uncertain-provenance"
    if "TST-0327-fixture-registry" in t or '"negative_control"' in t:
        return "synthetic-probe-fixtures"
    if t.lstrip().startswith(('"""', "'''", "from __future__", "import ")):
        return "first-party-original-source"
    if '"$schema"' in t or '"additionalProperties"' in t:
        return "first-party-program-records"
    if '"schema_version"' in t or '"unit_id"' in t:
        return "first-party-program-records"
    return None


def classify_chunk(rel: str, text: str | None, *, binary: bool = False) -> str | None:
    """Production classifier used by the completeness sample and extents."""
    if binary or text is None:
        return "undecodable-or-binary"
    if not str(text).strip():
        return "empty-or-whitespace"
    body = classify_body(text)
    if body in {
        "third-party-personal-data",
        "third-party-license-notice",
        "transcript-third-party-messages",
        "quoted-vendor-documentation",
        "scraped-marketplace-or-forum-text",
        "vendor-registry-api-captures",
    }:
        return body
    path_c = classify_path(rel)
    if path_c:
        return path_c
    if body:
        return body
    return None


def verdict_for(class_id: str) -> str:
    row = POLICY[class_id]
    return str(row["verdict"])


def load_text(repo: Path, rel: str) -> tuple[str, int]:
    path = repo / rel
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    line = 1
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.strip():
            line = i
            break
    return text, line


def snippet_at(text: str, line: int, width: int = 160) -> str:
    lines = text.splitlines() or [text]
    idx = min(max(line - 1, 0), len(lines) - 1)
    s = lines[idx].strip()
    if len(s) > width:
        return s[:width]
    return s
