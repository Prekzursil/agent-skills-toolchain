"""Write the 29-artifact contract fixture corpus. Not a byte copy of Prompt One."""
from __future__ import annotations

import json
from pathlib import Path

from contract import CONTRACT_29, FIXTURE_CORPUS, UNIT

# (filename, material heading, mechanism body without trailing tag, verdict tag)
MD: list[tuple[str, str, str, str]] = [
    (
        "00-CURRENT-STATE-INVENTORY.md",
        "Inventory completeness",
        "The current-state inventory names live trees separately so a union count cannot hide a missing tree.",
        "CONFIRMED",
    ),
    (
        "01-BLOCKER-REPRODUCTION.md",
        "Reproducible failing fixture",
        "A blocker is closed only when a named failing fixture reproduces the fault on a live host.",
        "CONFIRMED",
    ),
    (
        "02-BLOCKER-ROOT-CAUSE.md",
        "Root-cause rests on a live host",
        "Root-cause work that cites only a vanished host is stale because the machine that failed has changed.",
        "PARTIAL",
    ),
    (
        "03-PLUGIN-LIFECYCLE-MAP.md",
        "Plugin enablement is a state machine",
        "Plugin lifecycle is a named state machine from install through enable, disable and uninstall, not a boolean flag.",
        "CONFIRMED",
    ),
    (
        "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
        "Frontier notes are evidence not options",
        "Ecosystem teardown notes are source evidence for option cards and must not be counted as extra platform options.",
        "CONFIRMED",
    ),
    (
        "06-PROGRAM-B-SCOPE-DOSSIER.md",
        "Program B workstreams need a machine twin",
        "Program B workstreams that live only in prose have no machine-readable twin until the JSON dossier exists.",
        "NOT-CHECKED",
    ),
    (
        "07-OPTION-UNIVERSE.md",
        "Option universe quota floor",
        "The option universe markdown twin carries two hundred eighty three platform option cards as a quota floor.",
        "CONFIRMED",
    ),
    (
        "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
        "Archaeology catalog is an input not an output",
        "Workflow archaeology catalogs source constructs that later registries must preserve, so a dropped mechanism is a defect.",
        "CONFIRMED",
    ),
    (
        "09-RECONCILED-BACKLOG.md",
        "Backlog rows need mandated fields",
        "A reconciled backlog prose table with four columns does not satisfy a thirty-three-field per-item contract.",
        "REFUTED",
    ),
    (
        "10-WORKFLOW-FORGE-SPEC.md",
        "Forge spec is a compiler contract",
        "The workflow forge spec is a compiler contract over typed blueprints, not a gallery of example pipelines.",
        "UNVERIFIED",
    ),
    (
        "11-COUNCIL-SPECIFICATION.md",
        "CouncilSpec is a typed envelope",
        "CouncilSpec is a typed envelope that supersedes an untyped council charter and names seats as first-class fields.",
        "CONFIRMED",
    ),
    (
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
        "Protocols and presets are disjoint",
        "Council protocols and presets are disjoint families whose heading counts must sum, never be collapsed by max().",
        "CONFIRMED",
    ),
    (
        "13-ARCHITECTURE-CANDIDATES.md",
        "Architecture roster is eleven candidates",
        "The architecture tournament roster names eleven candidates that later must map onto nine spec-mandated classes.",
        "CONFIRMED",
    ),
    (
        "14-NO-REGRESSION-CONTRACT.md",
        "No-regression is a written gate",
        "The no-regression contract is a written gate Program A must clear before any option is applied.",
        "CONFIRMED",
    ),
    (
        "15-IMPLEMENTATION-PRECONDITIONS.md",
        "Preconditions are executable checks",
        "Implementation preconditions are HARD or SCOPED gates each paired with an executable check, not a narrative wish list.",
        "CONFIRMED",
    ),
    (
        "15-PROMPT-TWO-SPEC.md",
        "Prompt Two consumes selected option ids",
        "Prompt Two is specified to consume a pasted selected-option-id list rather than rediscover the option universe.",
        "PARTIAL",
    ),
    (
        "16-GRILL-QUEUE.md",
        "Grill queue is an ordered work list",
        "The grill queue is an ordered list of unresolved probes, not a completed findings dump.",
        "NOT-CHECKED",
    ),
    (
        "17-DECISION-LOG.md",
        "Decision log can go stale versus later docs",
        "A decision-log blocker written in present tense is superseded when a later document shows the same object fixed.",
        "CONTESTED",
    ),
    (
        "18-OPEN-UNKNOWNS-AND-PROBES.md",
        "Unknowns require named probes",
        "An open unknown without a named runnable probe is an unsettled residue, not a parked decision.",
        "UNVERIFIED",
    ),
    (
        "19-SUBSTANCE-AUDIT-BLUEPRINTS.md",
        "Substance audits need blueprints",
        "Substance-audit blueprints name the measurements an audit lane must take rather than restating prior headlines.",
        "CONFIRMED",
    ),
    (
        "24-REPO-RECONCILE.md",
        "Repo reconcile is a two-tree diff",
        "Repo reconcile is a two-tree diff of live versus versioned artifacts, not a union inventory.",
        "CONFIRMED",
    ),
    (
        "31-LANE-foundry.md",
        "Foundry lane scope",
        "The foundry lane authors executable workflows and must not silently drop mechanisms present in numbered sources.",
        "CONFIRMED",
    ),
    (
        "32-OWNER-DECISIONS.md",
        "Owner decisions are file-line anchored",
        "An owner decision is OWNER-EXPLICIT only when a resolvable file:line names it; session paraphrase is OWNER-IMPLIED.",
        "CONFIRMED",
    ),
    (
        "33-INTEGRATION.md",
        "Integration names remaining joins",
        "Integration notes name remaining joins across lanes and must not treat an unread corpus as an empty corpus.",
        "CONFIRMED",
    ),
]

JSON: list[tuple[str, str, str, str]] = [
    (
        "07-OPTION-UNIVERSE.json",
        "Option-count floor as a mechanism",
        "The option universe JSON twin records two hundred eighty three platform option cards as a quota floor.",
        "CONFIRMED",
    ),
    (
        "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "Candidate registry cardinality",
        "The workflow candidate registry records two hundred eighty four candidates that later disk artifacts must cover.",
        "CONFIRMED",
    ),
    (
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "Blueprint library cardinality",
        "The workflow blueprint library records one hundred eight blueprints as a quota floor on this corpus.",
        "CONFIRMED",
    ),
    (
        "11-COUNCIL-SPECIFICATION.schema.json",
        "Council specification typed envelope",
        "The council specification schema is a typed envelope that supersedes an untyped council charter.",
        "CONFIRMED",
    ),
    (
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "Protocol and preset floors",
        "The protocols-and-presets JSON twin records fifty eight protocols and seventy two presets as disjoint floors.",
        "CONFIRMED",
    ),
]


def render_md(name: str, heading: str, body: str, tag: str) -> str:
    return (
        f"# {name}\n"
        "\n"
        "## Table of contents\n"
        "\n"
        f"- {heading}\n"
        "\n"
        f"## {heading}\n"
        "\n"
        f"{body.rstrip('.')} {tag}.\n"
        "\n"
        "Allowed tags are CONFIRMED, REFUTED, PARTIAL, NOT-CHECKED.\n"
    )


def render_json(name: str, heading: str, body: str, tag: str) -> str:
    doc = {
        "title": name,
        "section": "Table of contents",
        "heading": heading,
        "claim_body": f"{body.rstrip('.')} {tag}.",
        "vocab_mention": "Allowed tags are CONFIRMED, REFUTED, PARTIAL, NOT-CHECKED.",
        "not_a_byte_copy": (
            f"{UNIT} fixture stand-in because harness-restore-20260806 is absent "
            "on this Linux worktree"
        ),
    }
    return json.dumps(doc, indent=2, ensure_ascii=True) + "\n"


def ensure_corpus() -> list[str]:
    FIXTURE_CORPUS.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    by_name = {n: (h, b, t) for n, h, b, t in MD + JSON}
    missing = [n for n in CONTRACT_29 if n not in by_name]
    extra = [n for n in by_name if n not in CONTRACT_29]
    if missing or extra:
        raise SystemExit(f"fixture-spec mismatch missing={missing} extra={extra}")
    for name in CONTRACT_29:
        heading, body, tag = by_name[name]
        dest = FIXTURE_CORPUS / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith(".json"):
            dest.write_text(render_json(name, heading, body, tag), encoding="utf-8")
        else:
            dest.write_text(render_md(name, heading, body, tag), encoding="utf-8")
        written.append(name)
    return written


if __name__ == "__main__":
    names = ensure_corpus()
    print(f"wrote {len(names)} fixture artifacts under {FIXTURE_CORPUS}")
