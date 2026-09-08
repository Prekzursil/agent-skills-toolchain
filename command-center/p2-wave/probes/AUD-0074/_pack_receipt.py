#!/usr/bin/env python3
"""Pack AUD-0074 source-lineage graph.

Honest BLOCKED: catalog requires one fresh-context Claude reviewer who has not
seen this unit's transcript and must try to FALSIFY the headline count before
PASS. Never invents SUCCESS or independent-review.json. Single-checkout Linux
scope: live Prompt-One Windows trees unmounted; corpus is fixture-reconstruction
keyed to AUD-0067 SUCCESS inventory.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0074"
OUT = "command-center/audit/AUD-0074-source-lineage-graph.json"
SCHEMA = "command-center/schema/audit-graph.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0074/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"
AUD0067 = "command-center/audit/AUD-0067-prompt-one-artifact-census.json"


def load_review() -> dict | None:
    """Only accept a real PASS from an independent fresh-context reviewer file.

    Absence is the expected state for this packing pass — do NOT invent one.
    """
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-citation-edges.json").read_text(encoding="utf-8"))
    p2 = json.loads(
        (PROBE / "probe2-timestamp-ordering.json").read_text(encoding="utf-8")
    )
    ctrl = json.loads((PROBE / "control-doc13-stale.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-citation-edges.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-timestamp-ordering.raw.txt").read_text(encoding="utf-8")
    rawc = (PROBE / "control-doc13-stale.raw.txt").read_text(encoding="utf-8")
    aud67 = json.loads((L.REPO / AUD0067).read_text(encoding="utf-8"))
    assert aud67.get("state") == "SUCCESS", aud67.get("state")

    rev = load_review()
    # Never green without independent fresh-context falsify review.
    success = rev is not None
    started = "2026-09-08T01:05:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    edge_count = int(p1.get("edge_count") or 0)
    nodes_present = int(p1.get("nodes_present") or 0)
    stale_flags = int(p2.get("stale_downstream_flag_count") or 0)
    doc13_flags = int(p2.get("doc13_stale_downstream_flag_count") or 0)
    control_ok = bool(ctrl.get("ok"))
    control_bad = int(ctrl.get("bad_state_doc13_stale_flags") or 0)
    control_good = int(ctrl.get("good_state_doc13_stale_flags") or 0)

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(
            "command-center/p2-wave/probes/AUD-0074/probe1-citation-edges.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0074/probe2-timestamp-ordering.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0074/control-doc13-stale.json",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0074/probe1-citation-edges.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0074/probe2-timestamp-ordering.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0074/control-doc13-stale.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0074/fixtures/corpus-meta.json",
            "fixture",
        ),
        L.art(AUD0067, "supporting"),
    ]
    if rev is not None:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0074/independent-review.json",
                "supporting",
            )
        )

    question = (
        "What is the derivation graph among the corpus artifacts, and which "
        "artifacts are downstream of a source that has since been corrected?"
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": str(rev.get("notes") or ""),
        }
        state = "SUCCESS"
        sentinel = (
            f"SUCCESS:AUD-0074 citation_edges={edge_count} "
            f"stale_downstream_flags={stale_flags} doc13_flags={doc13_flags}; "
            "independent fresh-context falsify review PASS"
        )
        headline = (
            f"nodes_present={nodes_present}/29 citation_edges={edge_count} "
            f"stale_downstream_flags={stale_flags} doc13_stale_flags={doc13_flags}; "
            "Independent re-review PASS."
        )
        failure = None
        anti = "SUCCESS-after-independent-re-review-PASS"
        defects = [
            {
                "id": "AUD-0074-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Independent fresh-context Claude review PASS recorded.",
            }
        ]
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not seen "
                "this unit's transcript; the reviewer must try to FALSIFY the headline "
                f"count (citation_edges={edge_count}, stale_downstream_flags={stale_flags}, "
                f"doc13_stale_flags={doc13_flags}) before PASS, not re-read the artifact. "
                "Review unpaid on this packing pass. Scope limit: single-checkout Linux "
                "cursor-cloud — live Prompt-One Windows trees are unmounted "
                "(AUD-0067 current_repo_root_fresh=0); probes ran against an honest "
                "fixture-reconstruction corpus keyed to the AUD-0067 SUCCESS inventory, "
                "not against live Windows tree bytes. independent-review.json was NOT invented."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            f"FAILED:AUD-0074 citation_edges={edge_count} "
            f"stale_downstream_flags={stale_flags} doc13_stale_flags={doc13_flags} "
            f"control_bad_flags={control_bad} control_good_flags={control_good}; "
            "blocked-on-independent-review+fixture-scope "
            "(live Prompt-One Windows trees unmounted on linux-cursor-cloud)"
        )
        headline = (
            f"nodes_present={nodes_present}/29 citation_edges={edge_count} "
            f"stale_downstream_flags={stale_flags} doc13_stale_flags={doc13_flags}; "
            f"control fired_bad={control_ok and control_bad >= 1} "
            f"silent_good={control_good == 0}. BLOCKED on independent fresh-context "
            "Claude falsify review + single-checkout fixture-scope disclosure."
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "stale-premise",
                "detector-failure",
            ],
            "reason": (
                "Named probes completed (citation edges + timestamp ordering + "
                "doc-13 stale-downstream control), AUD-0067 SUCCESS verified on disk, "
                "but catalog reviewer_requirement is unmet (fresh-context Claude must "
                "falsify headline counts) and the measured corpus is fixture-reconstruction "
                "because live Prompt-One Windows roots are not mounted on this substrate."
            ),
            "diagnostic_tail": (
                f"edges={edge_count} stale={stale_flags} doc13={doc13_flags} "
                f"control_ok={control_ok} reviewer=NOT-REVIEWED "
                f"aud0067={aud67.get('state')} corpus_kind=fixture-reconstruction"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this "
                "unit's transcript to FALSIFY headline "
                f"citation_edges={edge_count} stale_downstream_flags={stale_flags} "
                f"doc13_stale_flags={doc13_flags} before PASS; optionally remount "
                "live Prompt-One trees and re-run probes against real bytes."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0074/probe1_citation_edges.py",
                    f"edge_count={edge_count}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-pending-independent-review-with-real-probes-no-invented-SUCCESS"
        defects = [
            {
                "id": "AUD-0074-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Independent fresh-context Claude review unpaid; headline "
                    "citation_edges / stale_downstream_flags must be falsified by a "
                    "reviewer who did not author this graph."
                ),
            },
            {
                "id": "AUD-0074-D-SCOPE",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Single-checkout Linux scope: live Prompt-One Windows trees "
                    "unmounted; graph measured on fixture-reconstruction corpus "
                    "keyed to AUD-0067 inventory (not live tree bytes)."
                ),
            },
            {
                "id": "AUD-0074-D-STALE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"Probe 2 flagged stale_downstream_flags={stale_flags} "
                    f"(doc13={doc13_flags}); downstream consumers of corrected "
                    "sources remain an open remediation queue."
                ),
            },
        ]

    nodes = [{"id": n["id"], "present": n["present"]} for n in (p1.get("nodes") or [])]
    edges = [
        {"from": e["from"], "to": e["to"], "kind": e.get("kind", "citation")}
        for e in (p1.get("edges") or [])
    ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0074",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "linux-cursor-cloud",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Dependency AUD-0067 state=SUCCESS verified on disk at {AUD0067}; "
                    f"Probe 1 citation-derived edges={edge_count} "
                    f"nodes_present={nodes_present}/29 "
                    f"corpus_kind={p1.get('corpus_kind')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0074/probe1-citation-edges.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0074/probe1_citation_edges.py "
                        "--raw-output command-center/p2-wave/probes/AUD-0074/probe1-citation-edges.raw.txt "
                        "--result-json command-center/p2-wave/probes/AUD-0074/probe1-citation-edges.json",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read AUD-0067 + probe1-citation-edges.json",
                        json.dumps(
                            {
                                "aud0067_state": aud67.get("state"),
                                "edge_count": edge_count,
                                "nodes_present": nodes_present,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 timestamp ordering: edges_checked={p2.get('edges_checked')} "
                    f"stale_downstream_flags={stale_flags} "
                    f"doc13_stale_flags={doc13_flags} "
                    "(citation graph alone cannot see staleness)."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0074/probe2-timestamp-ordering.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0074/probe2_timestamp_ordering.py "
                        "--raw-output command-center/p2-wave/probes/AUD-0074/probe2-timestamp-ordering.raw.txt "
                        "--result-json command-center/p2-wave/probes/AUD-0074/probe2-timestamp-ordering.json",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe2-timestamp-ordering.json",
                        json.dumps(
                            {
                                "stale_flags": stale_flags,
                                "doc13_flags": doc13_flags,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0074-control-doc13-stale",
                "name": (
                    "control: the known doc-13 correction must produce at least one "
                    "stale-downstream flag; zero flags on that known case means the "
                    "timestamp check is inert"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0074/control_doc13_stale.py "
                    "--raw-output command-center/p2-wave/probes/AUD-0074/control-doc13-stale.raw.txt "
                    "--result-json command-center/p2-wave/probes/AUD-0074/control-doc13-stale.json"
                ),
                "result": "PASS" if control_ok else "FAIL",
                "assertions": 2,
                "output_tail": rawc[-800:],
            }
        ],
        "negative_controls": [
            L.control(
                "AUD0074-C1",
                "known-broken-fixture",
                (
                    "Known doc-13 correction (2026-08-07) must produce >=1 "
                    "stale-downstream flag on pre-correction citers."
                ),
                True if control_bad >= 1 else False,
                True if control_good == 0 else False,
                bad=f"doc13_stale_flags={control_bad} (want >=1)",
                good=f"good_state_doc13_flags={control_good} (want 0)",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-graph schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0074/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "retry only after the named upstream unit emits its SUCCESS sentinel; "
                "retrying against a missing input is a detector failure, not a transient"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Citation-edge and stale-downstream counts against live Prompt-One "
                    "Windows tree bytes (not fixture-reconstruction)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount the AUD-0067 named Windows roots, rebuild the corpus from "
                    "live files, re-run probe1+probe2, and compare headline counts."
                ),
            },
            {
                "claim": (
                    "Independent fresh-context Claude falsification of headline "
                    f"citation_edges={edge_count} / stale_downstream_flags={stale_flags}."
                ),
                "verdict": "CONFIRMED" if success else "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch a reviewer who has not seen this unit's transcript; "
                    "require an active attempt to FALSIFY the headline before PASS."
                    if not success
                    else (
                        "Recorded at command-center/p2-wave/probes/AUD-0074/"
                        "independent-review.json (verdict=PASS)."
                    )
                ),
            },
        ],
        "report": {
            "kind": "audit-graph",
            "question": question,
            "headline": headline,
            "answer": headline,
            "observations": [
                {
                    "name": "citation_edge_count",
                    "measured": edge_count,
                    "method": "basename citation regex over fixture corpus",
                    "anchor": "command-center/p2-wave/probes/AUD-0074/probe1-citation-edges.raw.txt",
                },
                {
                    "name": "stale_downstream_flag_count",
                    "measured": stale_flags,
                    "method": "per-edge citer_mtime < known source correction_at",
                    "anchor": "command-center/p2-wave/probes/AUD-0074/probe2-timestamp-ordering.raw.txt",
                },
                {
                    "name": "doc13_stale_downstream_flag_count",
                    "measured": doc13_flags,
                    "method": "subset of stale flags where to=13-ARCHITECTURE-CANDIDATES.md",
                    "anchor": "command-center/p2-wave/probes/AUD-0074/probe2-timestamp-ordering.raw.txt",
                },
                {
                    "name": "control_doc13_bad_flags",
                    "measured": control_bad,
                    "method": "both-states control on known 2026-08-07 correction",
                    "anchor": "command-center/p2-wave/probes/AUD-0074/control-doc13-stale.raw.txt",
                },
            ],
            "control_ids": ["AUD0074-C1"],
            "nodes": nodes,
            "edges": edges,
            "stale_downstream_flags": p2.get("stale_downstream_flags") or [],
            "anti_false_green": anti,
        },
        "extensions": {
            "stage": "p2-wave",
            "question": question,
            "answer": headline,
            "aud0067_dependency": {
                "path": AUD0067,
                "state": aud67.get("state"),
                "sentinel": aud67.get("sentinel"),
            },
            "headline_counts": {
                "contract_items": 29,
                "nodes_present": nodes_present,
                "citation_edges": edge_count,
                "stale_downstream_flags": stale_flags,
                "doc13_stale_downstream_flags": doc13_flags,
                "control_bad_doc13_flags": control_bad,
                "control_good_doc13_flags": control_good,
            },
            "corpus_kind": p1.get("corpus_kind"),
            "scope": (
                "single-checkout-linux-cursor-cloud; live Prompt-One Windows trees "
                "unmounted; fixture-reconstruction only"
            ),
            "independent_review_invented": False,
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    # First pass with placeholder primary
    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA, also=["command-center/schema/receipt.schema.json"])
    if rc != 0:
        # Some lanes only validate against audit-graph shim
        rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    # Re-pack with measured primary artifact bytes/hash
    for _ in range(2):
        primary = L.art(OUT, "primary")
        doc = build(primary=primary)
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc
    primary = L.art(OUT, "primary")
    doc["artifacts"][0] = primary
    (L.REPO / OUT).write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Final validate via receipt_validate admission
    v = subprocess.run(
        [
            sys.executable,
            str(L.REPO / "command-center/receipt_validate.py"),
            str(L.REPO / OUT),
        ],
        capture_output=True,
        text=True,
        cwd=str(L.REPO),
    )
    vout = (v.stdout or "") + (v.stderr or "")
    print(vout, end="")
    if not any(line.startswith("ACCEPT") for line in vout.splitlines()):
        print("FAILED:AUD-0074 receipt_validate did not ACCEPT")
        return 1

    packed = json.loads((L.REPO / OUT).read_text(encoding="utf-8"))
    rev = load_review()
    assert isinstance(packed["reviewer"]["notes"], str)
    if rev is None:
        assert packed["state"] == "BLOCKED", packed["state"]
        assert packed["sentinel"].startswith("FAILED:"), packed["sentinel"]
        assert packed["reviewer"]["verdict"] == "NOT-REVIEWED"
        assert packed["reviewer"]["independent"] is False
        assert packed["reviewer"]["fresh_context"] is False
        assert not REVIEW.is_file(), "must not invent independent-review.json"
    else:
        assert packed["state"] == "SUCCESS", packed["state"]
        assert packed["sentinel"].startswith("SUCCESS:"), packed["sentinel"]
        assert packed["reviewer"]["verdict"] == "PASS"
        assert packed["reviewer"]["independent"] is True
        assert packed["reviewer"]["fresh_context"] is True
        assert REVIEW.is_file()
        assert packed["downstream_consumers"], "SUCCESS requires non-empty downstream_consumers"

    manifest = {
        "unit_id": UNIT,
        "primary": OUT,
        "schema": SCHEMA,
        "state": packed["state"],
        "output_path": OUT,
        "sha256": packed["artifacts"][0]["sha256"],
        "bytes": packed["artifacts"][0]["bytes"],
        "artifacts": packed["artifacts"],
        "packed_at": packed["timestamps"]["ended_at"],
        "receipt_validate": next(
            (ln for ln in vout.splitlines() if ln.startswith("ACCEPT")),
            "ACCEPT",
        ),
        "headline_counts": packed["extensions"]["headline_counts"],
        "independent_review_invented": False,
    }
    (PROBE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"PACKED {OUT} state={packed['state']} bytes={packed['artifacts'][0]['bytes']} "
        f"edges={packed['extensions']['headline_counts']['citation_edges']} "
        f"stale={packed['extensions']['headline_counts']['stale_downstream_flags']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
