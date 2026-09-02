#!/usr/bin/env python3
"""Hand-labelled 30-doc control corpus for IMP-0153 (constructed, labelled).

Gold is document-level harvest vs drop. USE+unimplemented -> harvest.
MENTION, or USE of an already-implemented id, -> drop.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "fixtures" / "corpus"
CONTROLS = HERE / "fixtures" / "controls"
LABELS = HERE / "fixtures" / "labels.json"
IMPLEMENTED = HERE / "fixtures" / "implemented-index.json"

IMPLEMENTED_IDS = [
    "catalog-class-discovery-only",
    "wf.catalog-class.discovery-only",
    "rtv-pdr",
    "rtv-pdr.js",
]


def use_rfc(wid: str, s1: str, s2: str, s3: str, accept: str) -> str:
    return (
        f"# RFC: {wid}\n\n"
        f"We propose a new workflow named {wid}.\n\n"
        f"Proposed workflow: {wid}\n\n"
        f"The system SHALL execute the following steps:\n"
        f"1. {s1}\n"
        f"2. {s2}\n"
        f"3. {s3}\n\n"
        f"Acceptance: {accept}\n\n"
        f"This is a missing capability. Ship this workflow.\n"
    )


def use_runbook(wid: str, s1: str, s2: str, s3: str) -> str:
    return (
        f"# Runbook: how to run {wid}\n\n"
        f"We need a workflow named {wid} to be implemented.\n\n"
        f"workflow id: {wid}\n\n"
        f"Steps:\n"
        f"1. {s1}\n"
        f"2. {s2}\n"
        f"3. {s3}\n\n"
        f"How to create the operator copy: check this runbook into docs/.\n"
    )


def use_ticket(wid: str, body: str, s1: str, s2: str) -> str:
    return (
        f"# Ticket: implement {wid}\n\n"
        f"Build the {wid} workflow.\n\n"
        f"{body}\n\n"
        f"Proposed workflow: {wid}\n\n"
        f"Steps:\n"
        f"1. {s1}\n"
        f"2. {s2}\n\n"
        f"Requirements: the ticket is not done until the workflow id {wid} exists.\n"
    )


def use_transcript(wid: str, s1: str, s2: str) -> str:
    return (
        f"# Session transcript excerpt\n\n"
        f"Operator: next we will implement a new workflow.\n\n"
        f"Proposed workflow: {wid}\n\n"
        f"The system shall invoke {wid} after each close.\n\n"
        f"Steps:\n"
        f"1. {s1}\n"
        f"2. {s2}\n\n"
        f"Acceptance: a planted row appears in the candidate list.\n"
        f"Ship this workflow.\n"
    )


def use_requirements(wid: str, s1: str, s2: str) -> str:
    return (
        f"# Requirements for {wid}\n\n"
        f"The system shall invoke the {wid} workflow after each measured close.\n"
        f"New workflow to implement: {wid}\n\n"
        f"We introduce {wid} as the missing capability for this lane.\n\n"
        f"Steps:\n"
        f"1. {s1}\n"
        f"2. {s2}\n"
    )


def mention_critique(wid: str) -> str:
    return (
        f"# Critique: the {wid} workflow\n\n"
        f"The {wid} workflow is an anti-pattern. We rejected this design.\n"
        f"We are not shipping it. Do not harvest this mention-only note.\n\n"
        f"> Proposed workflow: {wid}\n"
        f"> Steps: 1. example 2. example\n\n"
        f"A naive keyword matcher would treat the quoted block as a candidate.\n"
        f"This describes a workflow to criticize it.\n"
    )


def mention_history(wid: str) -> str:
    return (
        f"# Changelog: retired {wid}\n\n"
        f"Historically the {wid} workflow used to run at close. It is retired.\n"
        f"Do not re-add it from this mention. Not a candidate.\n\n"
        f"Previously used only as a footnote. Mention-only detector control.\n"
    )


def mention_quote(wid: str) -> str:
    return (
        f"# Review of a paper that quotes {wid}\n\n"
        f"The authors wrote a long quoted example of a {wid} workflow inside scare quotes "
        f"that a keyword matcher would overclaim on, which is exactly the false positive "
        f"this detector exists to refuse.\n\n"
        f"We are not adopting that design. Out of scope for this estate.\n"
        f"Quoted example only. Mention-only.\n"
    )


def mention_pedagogy() -> str:
    return (
        "# Pedagogy: students often write Proposed workflow\n\n"
        "Students often write \"Proposed workflow: toy-lab-example\" in essays without "
        "intending to ship one. This essay is about academic writing, not a missing "
        "capability. Mention-only. Do not harvest.\n"
    )


def mention_detector(wid: str) -> str:
    return (
        f"# Detector control: planted mention of {wid}\n\n"
        f"Planted mention of the {wid} workflow sits here so that a naive regex fires.\n"
        f"Must not harvest. Mention-only detector control.\n"
        f"A keyword matcher is the known false positive.\n"
    )


DOCS: list[dict] = [
    # 15 USE + unimplemented -> harvest
    {
        "id": "u01",
        "file": "u01-credential-redact.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "credential-redact",
        "text": use_rfc(
            "credential-redact",
            "Scan receipt JSON for secret-shaped strings",
            "Replace each hit with a placeholder",
            "Write the redacted copy beside the original",
            "a planted token does not survive in the output bytes",
        ),
    },
    {
        "id": "u02",
        "file": "u02-session-transcript-normalizer.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "session-transcript-normalizer",
        "text": use_runbook(
            "session-transcript-normalizer",
            "Load the raw transcript",
            "Strip tool XML and collapse duplicate turns",
            "Emit a canonical JSONL row per utterance",
        ),
    },
    {
        "id": "u03",
        "file": "u03-live-tree-freeze.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "live-tree-freeze",
        "text": use_ticket(
            "live-tree-freeze",
            "We need a workflow that freezes generated deploy copies after extract.",
            "Record sha256 of each generated path",
            "Reject later hand-edits of frozen paths",
        ),
    },
    {
        "id": "u04",
        "file": "u04-workflow-scout-meta.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "workflow-scout-meta",
        "text": use_rfc(
            "workflow-scout-meta",
            "Accept a goal string",
            "Query repo, live, marketplace, and prose adapters",
            "Return ranked adopt-or-adapt verdicts",
            "a planted incumbent is recovered on a known-answer goal",
        ),
    },
    {
        "id": "u05",
        "file": "u05-marketplace-sbom-publish.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "marketplace-sbom-publish",
        "text": use_requirements(
            "marketplace-sbom-publish",
            "Pack identity, version, licence, and SBOM fields",
            "Refuse .git, caches, transcripts, and credentials in the tarball",
        ),
    },
    {
        "id": "u06",
        "file": "u06-adapter-chain-run.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "adapter-chain-run",
        "text": use_transcript(
            "adapter-chain-run",
            "Run repo, live, marketplace, then prose adapters in order",
            "Union candidate rows keyed by workflow id and source",
        ),
    },
    {
        "id": "u07",
        "file": "u07-incident-isolate-snapshot.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "incident-isolate-snapshot",
        "text": use_runbook(
            "incident-isolate-snapshot",
            "Isolate the failing unit directory",
            "Snapshot probes and the catalog receipt",
            "Park with a named required_fix",
        ),
    },
    {
        "id": "u08",
        "file": "u08-receipt-schema-gate.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "receipt-schema-gate",
        "text": use_rfc(
            "receipt-schema-gate",
            "Load the declared output_schema",
            "Validate the receipt bytes",
            "Fail closed on garbage probes",
            "each of the three garbage documents is invalid under the schema",
        ),
    },
    {
        "id": "u09",
        "file": "u09-corpus-byte-diff.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "corpus-byte-diff",
        "text": use_ticket(
            "corpus-byte-diff",
            "Build the corpus-byte-diff workflow to compare two labelled trees.",
            "LF-normalise both trees",
            "Emit a per-path sha256 table",
        ),
    },
    {
        "id": "u10",
        "file": "u10-prose-span-mine.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "prose-span-mine",
        "text": use_requirements(
            "prose-span-mine",
            "Extract workflow-shaped spans from markdown",
            "Keep only USE speech-acts",
        ),
    },
    {
        "id": "u11",
        "file": "u11-owner-gate-pack.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "owner-gate-pack",
        "text": use_rfc(
            "owner-gate-pack",
            "Collect owner-gated unit ids",
            "Refuse silent auto-approval",
            "Emit a pack the owner can sign",
            "an ungated unit is not in the pack",
        ),
    },
    {
        "id": "u12",
        "file": "u12-dual-signal-refute.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "dual-signal-refute",
        "text": use_runbook(
            "dual-signal-refute",
            "Take two independent measurements of the same claim",
            "If they disagree, report BLOCKED rather than picking a winner",
            "Record both numbers on the receipt",
        ),
    },
    {
        "id": "u13",
        "file": "u13-worktree-access-record.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "worktree-access-record",
        "text": use_transcript(
            "worktree-access-record",
            "For each candidate path record the exact access method",
            "A ref-only path must store git show ref:path, not a bare path",
        ),
    },
    {
        "id": "u14",
        "file": "u14-hatch-catalog-replay.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "hatch-catalog-replay",
        "text": use_ticket(
            "hatch-catalog-replay",
            "We introduce hatch-catalog-replay as the missing capability for A2.",
            "Load the typed registry",
            "Replay generator 1.0.0 against the sample",
        ),
    },
    {
        "id": "u15",
        "file": "u15-licence-lattice-check.md",
        "gold_harvest": True,
        "speech_act": "use",
        "implemented": False,
        "workflow_id": "licence-lattice-check",
        "text": use_rfc(
            "licence-lattice-check",
            "Read licence fields from candidate packages",
            "Join them against the allowed lattice",
            "Drop incompatible rows before ranking",
            "a planted incompatible licence is dropped",
        ),
    },
    # 2 USE + already implemented -> drop
    {
        "id": "u16",
        "file": "u16-catalog-class-discovery-only.md",
        "gold_harvest": False,
        "speech_act": "use",
        "implemented": True,
        "workflow_id": "catalog-class-discovery-only",
        "text": use_rfc(
            "catalog-class-discovery-only",
            "Load the catalog-class registry",
            "Emit discovery-only hatch rows",
            "Skip mutation of live trees",
            "the known fixture wf.catalog-class.discovery-only is recovered",
        ),
    },
    {
        "id": "u17",
        "file": "u17-rtv-pdr.md",
        "gold_harvest": False,
        "speech_act": "use",
        "implemented": True,
        "workflow_id": "rtv-pdr",
        "text": (
            "# Spec: rtv-pdr (already live)\n\n"
            "We propose continuing to run the rtv-pdr workflow.\n\n"
            "Proposed workflow: rtv-pdr\n\n"
            "The system SHALL execute the following steps:\n"
            "1. Load workflows/rtv-pdr.js when present\n"
            "2. Emit a candidate row with content hash\n\n"
            "This is USE speech. The planted implemented index lists rtv-pdr.\n"
            "Ship this workflow only if the index does not already contain it.\n"
        ),
    },
    # 13 MENTION -> drop
    {
        "id": "m01",
        "file": "m01-critique-credential-redact.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "credential-redact",
        "text": mention_critique("credential-redact"),
    },
    {
        "id": "m02",
        "file": "m02-rejected-live-tree-freeze.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "live-tree-freeze",
        "text": (
            "# Rejected design: live-tree-freeze\n\n"
            "We rejected the live-tree-freeze workflow after a review.\n"
            "Do not implement it. Out of scope. Not a candidate.\n\n"
            "The live-tree-freeze workflow is discussed only as a counter-example.\n"
        ),
    },
    {
        "id": "m03",
        "file": "m03-quoted-hatch-catalog-replay.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "hatch-catalog-replay",
        "text": mention_quote("hatch-catalog-replay"),
    },
    {
        "id": "m04",
        "file": "m04-retired-manual-close.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "manual-close",
        "text": mention_history("manual-close"),
    },
    {
        "id": "m05",
        "file": "m05-detector-hygiene.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "receipt-schema-gate",
        "text": mention_detector("receipt-schema-gate"),
    },
    {
        "id": "m06",
        "file": "m06-counterexample-marketplace.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "marketplace-sbom-publish",
        "text": (
            "# Counter-example JSON for marketplace-sbom-publish\n\n"
            "The marketplace-sbom-publish workflow below is a counter-example of "
            "what not to do. We are not shipping it.\n\n"
            "```\n"
            '{"proposed workflow": "marketplace-sbom-publish", "steps": ["pack"]}\n'
            "```\n\n"
            "A naive keyword matcher would harvest the fenced block.\n"
            "Mention-only. Must not harvest.\n"
        ),
    },
    {
        "id": "m07",
        "file": "m07-licensing-essay.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "adapter-chain-run",
        "text": (
            "# Essay: SPDX strings are not workflows\n\n"
            "Unlike the adapter-chain-run workflow, discussed only in passing, "
            "this essay is about SPDX. Mention-only. Not a candidate.\n"
            "We are not adopting adapter-chain-run here.\n"
        ),
    },
    {
        "id": "m08",
        "file": "m08-do-not-implement-credential-print.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "credential-print",
        "text": (
            "# Do-not-implement: credential-print\n\n"
            "Do not implement the credential-print workflow. Never implement a "
            "path that prints secrets. The credential-print workflow is an "
            "anti-pattern. Mention-only. Must not harvest.\n"
        ),
    },
    {
        "id": "m09",
        "file": "m09-out-of-scope-ticket.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "marketplace-sbom-publish",
        "text": (
            "# Ticket review: marketplace-sbom-publish is out of scope\n\n"
            "Quoting the original ticket that asked to build the "
            "marketplace-sbom-publish workflow: we are not adopting it this "
            "cycle. Out of scope. Mention-only. Not a candidate.\n"
        ),
    },
    {
        "id": "m10",
        "file": "m10-pedagogy-proposed-workflow.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "toy-lab-example",
        "text": mention_pedagogy(),
    },
    {
        "id": "m11",
        "file": "m11-review-rejects-scout-meta.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "workflow-scout-meta",
        "text": (
            "# Review: the workflow-scout-meta RFC overclaims\n\n"
            "The so-called workflow-scout-meta workflow overclaims provenance.\n"
            "We rejected the RFC. We are not shipping it. Critique only.\n"
            "Mention-only detector control. Do not harvest.\n"
        ),
    },
    {
        "id": "m12",
        "file": "m12-changelog-removed-receipt-gate.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "receipt-schema-gate",
        "text": (
            "# Changelog: removed receipt-schema-gate\n\n"
            "Removed the receipt-schema-gate workflow from docs. It is retired.\n"
            "Do not re-add from this mention. Historically used, now obsolete.\n"
        ),
    },
    {
        "id": "m13",
        "file": "m13-footnote-alleged-receipt-gate.md",
        "gold_harvest": False,
        "speech_act": "mention",
        "implemented": False,
        "workflow_id": "receipt-schema-gate",
        "text": (
            "# Footnote: the alleged receipt-schema-gate workflow\n\n"
            "The alleged receipt-schema-gate workflow never existed on this tree.\n"
            "Purported designs are not candidates. Mention-only. Do not harvest.\n"
        ),
    },
]

MENTION_ONLY_CONTROL = (
    "# Critique: mention-only control for IMP-0153\n\n"
    "This document describes a workflow to criticize it. The so-called "
    "imp0153-alpha-normalizer workflow is an anti-pattern.\n"
    "We rejected the design. We are not shipping it. Mention-only.\n"
    "Must not harvest. A naive keyword matcher would fire on the next lines.\n\n"
    "The imp0153-alpha-normalizer workflow was quoted from a paper as a "
    "counter-example of what not to do.\n\n"
    "> Proposed workflow: imp0153-alpha-normalizer\n"
    "> Steps: 1. load 2. normalize 3. emit\n\n"
    "Planted mention. Detector control. Do not harvest.\n"
)

USE_CONTROL = (
    "# RFC: imp0153-alpha-normalizer\n\n"
    "We propose a new workflow named imp0153-alpha-normalizer.\n\n"
    "Proposed workflow: imp0153-alpha-normalizer\n\n"
    "The system SHALL execute the following steps:\n"
    "1. Load a session transcript\n"
    "2. Normalize speaker turns\n"
    "3. Emit JSONL\n\n"
    "Acceptance: a planted utterance survives as one row.\n\n"
    "This is a missing capability. Ship this workflow.\n"
)


def labelled_docs() -> list[dict]:
    rows = []
    for d in DOCS:
        rows.append(
            {
                "id": d["id"],
                "path": f"fixtures/corpus/{d['file']}",
                "gold_harvest": d["gold_harvest"],
                "speech_act": d["speech_act"],
                "implemented": d["implemented"],
                "workflow_id": d["workflow_id"],
                "text": d["text"],
            }
        )
    return rows


def materialize() -> dict:
    CORPUS.mkdir(parents=True, exist_ok=True)
    CONTROLS.mkdir(parents=True, exist_ok=True)
    for d in DOCS:
        (CORPUS / d["file"]).write_text(d["text"], encoding="utf-8")
    (CONTROLS / "mention-only.md").write_text(MENTION_ONLY_CONTROL, encoding="utf-8")
    (CONTROLS / "use.md").write_text(USE_CONTROL, encoding="utf-8")
    labels = {
        "unit_id": "IMP-0153",
        "n_docs": len(DOCS),
        "n_gold_harvest": sum(1 for d in DOCS if d["gold_harvest"]),
        "n_gold_drop": sum(1 for d in DOCS if not d["gold_harvest"]),
        "constructed": True,
        "construction_note": (
            "Hand-labelled constructed control set: USE docs carry proposal/"
            "spec speech-act cues; MENTION docs carry critique/quote/rejection "
            "cues. Precision/recall are computed on this labelled set, not on "
            "an unlabelled live corpus."
        ),
        "implemented_ids": IMPLEMENTED_IDS,
        "docs": [
            {
                "id": d["id"],
                "path": f"fixtures/corpus/{d['file']}",
                "gold_harvest": d["gold_harvest"],
                "speech_act": d["speech_act"],
                "implemented": d["implemented"],
                "workflow_id": d["workflow_id"],
            }
            for d in DOCS
        ],
    }
    LABELS.write_text(json.dumps(labels, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    IMPLEMENTED.write_text(
        json.dumps({"ids": IMPLEMENTED_IDS}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return labels


if __name__ == "__main__":
    info = materialize()
    print(json.dumps({"n_docs": info["n_docs"], "n_gold_harvest": info["n_gold_harvest"]}))
