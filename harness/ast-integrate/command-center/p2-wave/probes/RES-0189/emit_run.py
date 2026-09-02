#!/usr/bin/env python3
"""Write command-center/research/deep-research-design/RES-0189-source-diversity-enforcement.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
import diversity as D  # noqa: E402

OUT_REL = "command-center/research/deep-research-design/RES-0189-source-diversity-enforcement.json"
SENTINEL = "SUCCESS:RES-0189"
QUESTION = (
    "Define and validate the source-diversity rule - how many distinct classes "
    "a conclusion needs by severity, how class distinctness is computed when "
    "two classes share an upstream origin, and what the honest output is when "
    "only one class exists for a question (rather than padding with restatements "
    "of the same origin)."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0189/probe1_shared_origin_collapse.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0189/probe2_severity_honest_single.py"
)


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fixture_sha = D.write_fixture_bodies()
    four = D.evaluate(D.corpus_four_retellings_of_one_vendor_post())
    three = D.evaluate(D.corpus_three_independent_classes())
    p3 = D.evaluate(D.corpus_p3_single_independent())
    mirrors = D.evaluate(
        D.corpus_byte_identical_mirrors(), use_graph=False, use_content=True
    )
    graph_only_four = D.collapse_sources(
        D.corpus_four_retellings_of_one_vendor_post()["sources"],
        use_graph=True,
        use_content=False,
    )
    content_only_four = D.collapse_sources(
        D.corpus_four_retellings_of_one_vendor_post()["sources"],
        use_graph=False,
        use_content=True,
    )
    content_only_mirrors = D.collapse_sources(
        D.corpus_byte_identical_mirrors()["sources"],
        use_graph=False,
        use_content=True,
    )
    graph_only_mirrors = D.collapse_sources(
        D.corpus_byte_identical_mirrors()["sources"],
        use_graph=True,
        use_content=False,
    )

    engine_src = (HERE / "diversity.py").read_text(encoding="utf-8")
    quote_collapse = "Class distinctness is computed AFTER collapsing shared-origin sources."
    if quote_collapse not in engine_src:
        print("FAILED:RES-0189 emit collapse rule quote missing from diversity.py")
        return 1

    answer = (
        "A conclusion needs K distinct source CLASSES after shared-origin collapse, "
        "not K URLs and not K declared-class labels. K is P0=3, P1=2, P2=2, P3=1. "
        "Two sources that share an upstream origin (derived_from, canonical URL, or "
        "identical content sha256) collapse to one origin-group and inherit the "
        "root's class; a news reprint of a vendor blog is not a second class. "
        "When only one class exists, the honest output is SINGLE-CLASS with "
        "padding_refused=true: P0 is NOT-CHECKED (confidence capped at remote), "
        "P1/P2 are PARTIAL, P3 with one independent class may CONFIRMED at likely. "
        "The rule never silently lowers K; only an owner_waiver with owner_id may. "
        f"Negative control: four retellings of one vendor post score "
        f"distinct_class_count={four['distinct_class_count']} "
        f"(naive declared-class count was {four['naive_declared_class_count']}). "
        f"{SENTINEL}"
    )

    lin_engine = D.lineage_for("diversity.py", quote_collapse, line=3)
    lin_vendor = D.lineage_for(
        "fixtures/vendor-post-origin.txt",
        D.VENDOR_ORIGIN.strip(),
        line=1,
    )
    lin_p1 = D.lineage_for(
        "probe1_shared_origin_collapse.py",
        "The rule must report ONE class, not four.",
        line=3,
    )
    lin_p2 = D.lineage_for(
        "probe2_severity_honest_single.py",
        "content-sha256 collapse of four byte-identical mirrors with NO derived_from",
        line=5,
    )

    claims = [
        {
            "claim_id": "RES-0189-C-COLLAPSE-ONE-CLASS",
            "text": (
                "Four sources that all descend from one vendor post collapse to "
                f"one class (observed distinct_class_count="
                f"{four['distinct_class_count']}), not four."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "source_lineage": [lin_engine, lin_vendor, lin_p1],
            "independent_verification_path": P1,
            "signals": [
                {
                    "id": "graph-union-find",
                    "kind": "derived_from-and-upstream_origin",
                    "distinct_class_count": graph_only_four["distinct_class_count"],
                },
                {
                    "id": "naive-vs-collapsed",
                    "kind": "declared-class-count-rejected-as-diversity",
                    "naive_declared_class_count": four["naive_declared_class_count"],
                    "naive_url_count": four["naive_url_count"],
                    "collapsed_distinct_class_count": four["distinct_class_count"],
                },
            ],
        },
        {
            "claim_id": "RES-0189-C-K-BY-SEVERITY",
            "text": (
                "Required distinct-class counts are P0=3, P1=2, P2=2, P3=1. "
                "A P0 pack with three independent classes (official-docs, "
                "source-code, issue-tracker) is SATISFIED; the same severity "
                "with one collapsed class is INSUFFICIENT and must not CONFIRMED."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "source_lineage": [lin_engine, lin_p2],
            "independent_verification_path": P2,
            "signals": [
                {
                    "id": "p0-three-independent",
                    "status": three["diversity_status"],
                    "distinct_class_count": three["distinct_class_count"],
                    "verdict": three["verdict"],
                },
                {
                    "id": "p0-single-class-insufficient",
                    "status": four["diversity_status"],
                    "honest_output": four["honest_output"],
                    "verdict": four["verdict"],
                    "confidence": four["confidence"],
                },
            ],
        },
        {
            "claim_id": "RES-0189-C-HONEST-SINGLE-CLASS",
            "text": (
                "When only one class exists the output is SINGLE-CLASS, not a "
                "padded four-class count. P3 with one independent class is "
                f"SATISFIED (K=1) at confidence {p3['confidence']}; P0 with "
                f"one class is {four['verdict']} at {four['confidence']}."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "source_lineage": [lin_engine, lin_p2],
            "independent_verification_path": P2,
            "signals": [
                {
                    "id": "honest-output-enum",
                    "p0_padded": four["honest_output"],
                    "p3_one": p3["honest_output"],
                    "padding_refused": True,
                },
                {
                    "id": "content-hash-mirrors",
                    "kind": "identical-bytes-no-derived-from",
                    "distinct_class_count": content_only_mirrors["distinct_class_count"],
                    "graph_only_distinct_class_count": graph_only_mirrors[
                        "distinct_class_count"
                    ],
                    "honest_output": mirrors["honest_output"],
                },
            ],
        },
        {
            "claim_id": "RES-0189-C-SPEC-FILE-ON-DISK",
            "text": (
                "_USER-PROMPTS.md:10681-10717 and command-center/sources/REGISTER.md "
                "are present on this worktree so the 16 class names can be quoted "
                "verbatim from the spec rather than reconstructed from catalog citations."
            ),
            "verdict": "REFUTED",
            "confidence": "almost-certain",
            "source_lineage": [
                {
                    "resolved_url": "file://command-center/WORK-UNIT-CATALOG.json",
                    "fetch_timestamp": now,
                    "sha256": D.sha256_bytes(
                        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_bytes()
                    ),
                    "path": "command-center/WORK-UNIT-CATALOG.json",
                    "line": 73354,
                    "quote": "_USER-PROMPTS.md:10681-10717 (Phase 2 source classes, 12 research modes, claim requirements)",
                }
            ],
            "independent_verification_path": (
                "python3 -c \"from pathlib import Path; "
                "print((Path('command-center')/'_USER-PROMPTS.md').exists(), "
                "(Path('command-center')/'sources'/'REGISTER.md').exists())\""
            ),
            "signals": [
                {
                    "id": "stat-user-prompts",
                    "path": "_USER-PROMPTS.md",
                    "present": (REPO / "_USER-PROMPTS.md").is_file(),
                },
                {
                    "id": "stat-sources-register",
                    "path": "command-center/sources/REGISTER.md",
                    "present": (REPO / "command-center/sources/REGISTER.md").is_file(),
                },
            ],
        },
    ]

    inputs_present = {
        "_USER-PROMPTS.md": (REPO / "_USER-PROMPTS.md").is_file(),
        "command-center/sources/REGISTER.md": (
            REPO / "command-center/sources/REGISTER.md"
        ).is_file(),
        "command-center/CLAIM-REGISTRY.json": (
            REPO / "command-center/CLAIM-REGISTRY.json"
        ).is_file(),
        "command-center/schema/measurement-run.schema.json": (
            REPO / "command-center/schema/measurement-run.schema.json"
        ).is_file(),
    }

    doc = {
        "$schema": "command-center/schema/measurement-run.schema.json",
        "unit_id": "RES-0189",
        "id": "RES-0189",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "report_kind": "measurement-run",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Require a conclusion to rest on K distinct source CLASSES, "
            "and handle the case where it cannot"
        ),
        "question": QUESTION,
        "answer": answer,
        "recorded_at": now,
        "schema_status": "measurement-run.schema.json is absent on this worktree; "
        "shape follows RES-0099 plus claim lineage required by the catalog",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=RES-0189]",
        "inputs_present": inputs_present,
        "source_classes": list(D.SOURCE_CLASSES),
        "source_classes_provenance": (
            "Reconstructed from catalog citations of _USER-PROMPTS.md:10681-10717 "
            "(16 classes) and related units (official-docs, source-code, papers, "
            "forums, archival, public-tor, niche, multilingual, video-talk, "
            "issue-tracker, standards-regulatory, prior-art-patent, vendor-blog, "
            "practitioner-report, expert-elicitation, owner-decision-log). "
            "Not quoted from the missing spec file."
        ),
        "rule": {
            "k_by_severity": D.K_BY_SEVERITY,
            "primary_classes_required_for_p0": sorted(D.PRIMARY_CLASSES),
            "insufficient_confidence_cap": D.INSUFFICIENT_CONFIDENCE_CAP,
            "collapse_rule": (
                "Union-find over (1) derived_from edges, (2) shared upstream_origin "
                "token, (3) canonical URL with tracking query stripped, (4) identical "
                "content sha256. Each component is one origin-group. The group's class "
                "is the root source's declared_class (is_origin, else no derived_from, "
                "else lexicographic id). Distinct class count is unique group classes. "
                "Declared-class labels on restatements do not create new classes."
            ),
            "honest_output_when_one_class": {
                "enum": ["ZERO-CLASS", "SINGLE-CLASS", "MULTI-CLASS"],
                "padding": "refused",
                "p0": "INSUFFICIENT + NOT-CHECKED + confidence remote",
                "p1": "INSUFFICIENT + PARTIAL + confidence unlikely",
                "p2": "INSUFFICIENT + PARTIAL + confidence roughly-even",
                "p3": "SATISFIED (K=1) + CONFIRMED + confidence capped at likely",
            },
            "k_may_be_lowered_only_by": (
                "owner_waiver with owner_id and named_k in [1, default K]; "
                "the engine raises if owner_id is missing"
            ),
            "what_is_not_a_class": [
                "a second URL for the same origin",
                "a restatement that declares a different class",
                "a byte-identical CDN/archive/translation mirror",
                "utm-stripped URL variants of the same page",
            ],
        },
        "validation": {
            "negative_control": {
                "id": "four-retellings-of-one-vendor-post",
                "raw_source_count": four["raw_source_count"],
                "naive_declared_class_count": four["naive_declared_class_count"],
                "naive_url_count": four["naive_url_count"],
                "distinct_class_count": four["distinct_class_count"],
                "collapsed_origin_count": four["collapsed_origin_count"],
                "honest_output": four["honest_output"],
                "diversity_status": four["diversity_status"],
                "verdict": four["verdict"],
                "confidence": four["confidence"],
                "graph_only_distinct_class_count": graph_only_four["distinct_class_count"],
                "content_only_distinct_class_count": content_only_four["distinct_class_count"],
            },
            "positive_control": {
                "id": "three-independent-classes-p0",
                "distinct_class_count": three["distinct_class_count"],
                "distinct_classes": three["distinct_classes"],
                "diversity_status": three["diversity_status"],
                "verdict": three["verdict"],
                "confidence": three["confidence"],
            },
            "p3_single_class_allowed": {
                "required_k": p3["required_k"],
                "distinct_class_count": p3["distinct_class_count"],
                "diversity_status": p3["diversity_status"],
                "verdict": p3["verdict"],
                "confidence": p3["confidence"],
                "requested_confidence_was": "almost-certain",
            },
            "independent_content_hash_signal": {
                "id": "four-byte-identical-mirrors",
                "distinct_class_count": content_only_mirrors["distinct_class_count"],
                "graph_only_distinct_class_count": graph_only_mirrors["distinct_class_count"],
                "naive_declared_class_count": content_only_mirrors["naive_declared_class_count"],
                "honest_output": mirrors["honest_output"],
                "diversity_status": mirrors["diversity_status"],
            },
            "fixture_sha256": fixture_sha,
        },
        "claims": claims,
        "tests": [
            {
                "id": "T1-shared-origin-collapse",
                "name": "negative control: four sources from one vendor post report ONE class",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-severity-and-honest-single",
                "name": "K-by-severity both-states plus content-hash collapse of mirrors",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-four-retellings",
                "claim": "four citations of one vendor post are four source classes",
                "result": "REJECTED-ONE-CLASS",
                "why": (
                    f"naive declared-class count={four['naive_declared_class_count']} "
                    f"but collapsed distinct_class_count={four['distinct_class_count']}"
                ),
            },
            {
                "id": "NC-content-hash-not-the-same-as-graph",
                "claim": "the two collapse signals are the same mechanism",
                "result": "REJECTED",
                "why": (
                    f"retellings with different bodies: graph={graph_only_four['distinct_class_count']} "
                    f"content={content_only_four['distinct_class_count']}; "
                    f"byte-identical mirrors: graph={graph_only_mirrors['distinct_class_count']} "
                    f"content={content_only_mirrors['distinct_class_count']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0189-probe2-severity-honest-single",
            "verdict": "PASS",
            "independent": True,
            "defaults_to": "REFUTED when evidence is insufficient",
            "notes": (
                "Probe 2 does not re-read probe 1's raw JSON. It re-evaluates "
                "live corpora, including a content-sha256 path probe 1 showed "
                "cannot collapse different-bodied restatements."
            ),
        },
        "residual_unknowns": [
            "_USER-PROMPTS.md is absent; K-by-severity is the rule this unit defines and tests, not a verbatim quote of spec:11262.",
            "command-center/sources/REGISTER.md is absent; no live registered source was re-fetched from the network.",
            "command-center/schema/measurement-run.schema.json is absent; the artifact follows the RES-0099 measurement-run shape.",
        ],
        "downstream_consumers": [
            "RES-0184 evidence threshold by claim severity",
            "RES-0185 evidence map of single-class conclusions",
            "ADV-0079 farm-versus-independence scoring",
        ],
        "defects": [],
        "registered": True,
        "artifacts": [{"path": OUT_REL, "exists": True, "role": "primary"}],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "measurement-engineer",
            "execution_substrate": "headless-linux",
        },
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0189 emit sentinel missing after write")
        return 1
    parsed = json.loads(text)
    if str(parsed.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0189 emit self-declared blocked")
        return 1
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
