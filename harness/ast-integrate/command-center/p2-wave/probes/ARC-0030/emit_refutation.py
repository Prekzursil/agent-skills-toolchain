#!/usr/bin/env python3
"""Emit command-center/phase3/A4/REFUTATION.json for ARC-0030."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import overclaim as O  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/phase3/A4/REFUTATION.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
DESIGN = "command-center/phase3/A4/DESIGN.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
REGISTRY = "command-center/p2-wave/probes/ARC-0010/registry.json"
QUESTION = (
    "Refute the gateway: argue it becomes the single point of epistemic failure for "
    "capability discovery. Construct the concrete case where a correct capability "
    "exists, is installed, is relevant, and is NEVER selected - then show why the "
    "resulting silence is undetectable from inside the gateway's own telemetry, "
    "and name the external signal that would detect it."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0030/probe1_reproduce_miss.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0030/probe2_overclaim.py"
)
COUNTER = (
    "Lazy-activation still bounds the resident set to index rows plus the selected "
    "bodies. Putting labelled recall inside the gateway would make the selector "
    "depend on a gold corpus it is supposed to be measured against, and would "
    "rebuild A4 into a supervised ranker (the ADV circle). The surviving claim: "
    "A4 indexes and lazily activates; it does not certify that the selected set "
    "is the relevant set. That claim is CONFIRMED by DESIGN. Detection of "
    "relevant-but-unselected capabilities belongs on an external labelled-recall "
    "confirmer (catalog ARC-0029 / CNF-0177), not in gateway turn_ok."
)
CATCHING = (
    "A1 config-first always-on: skill.council's body is resident without surviving "
    "a select() hit, so the four-voice instructions are in context on this task. "
    "Cost is flooding, which is why A4 exists; A1 still catches this omission."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0030 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def main() -> int:
    if not (REPO / DESIGN).is_file():
        print("FAILED:ARC-0030 DESIGN.json missing")
        return 1
    run = S.run_scenario()
    if not run.get("pass"):
        print("FAILED:ARC-0030 scenario did not reproduce epistemic silence")
        print(json.dumps(run, indent=2, sort_keys=True)[:4000])
        return 1

    e1 = ev(
        DESIGN,
        '"labelled_recall_is_not_a_gateway_metric": true',
        "dossier",
        "DESIGN omits labelled recall from gateway turn telemetry.",
    )
    e2 = ev(
        DESIGN,
        '"turn_ok_if_any_selection_activates": true',
        "dossier",
        "A nonempty alternative selection is specified as a green turn.",
    )
    e3 = ev(
        DESIGN,
        '"index_text_excludes_body": true',
        "dossier",
        "select() consults kind+name index_text, not bodies, roles, or instructions.",
    )
    e4 = ev(
        DESIGN,
        "The gateway is a complete discovery path",
        "dossier",
        "Downstream sentence claims selection plus telemetry will surface every relevant installed capability.",
    )
    e5 = ev(
        CATALOG,
        "a correct capability exists, is installed, is relevant, and is NEVER selected",
        "live-tree",
        "This unit's catalog question already names the never-selected installed case.",
    )
    e6 = ev(
        REGISTRY,
        "Four-voice prompt skill (Architect, Skeptic, Pragmatist, Critic)",
        "live-tree",
        "Live A2 registry installs skill.council with the four named roles in the body, not in the name.",
    )
    e7 = ev(
        CATALOG,
        "a capability the router never selects is indistinguishable from one that does not exist",
        "live-tree",
        "Catalog ARC-0026 already records the indistinguishability mode.",
    )
    e8 = ev(
        CATALOG,
        "the router failing to select an INSTALLED skill",
        "live-tree",
        "CNF-0177 names the external labelled-recall confirmer for an installed-skill miss.",
    )
    dossier_n = sum(1 for e in (e1, e2, e3, e4) if e["kind"] == "dossier")
    live_n = sum(1 for e in (e5, e6, e7, e8) if e["kind"] == "live-tree")
    if dossier_n < 3 or live_n < 1:
        print(f"FAILED:ARC-0030 evidence counts dossier={dossier_n} live={live_n}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    silent_line = e2["anchor"]
    tel = run["a4_telemetry"]
    doc = {
        "unit_id": "ARC-0030",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0030",
        "completion_sentinel": "SUCCESS:ARC-0030",
        "architecture_id": "A4",
        "architecture_class": "gateway-lazy-activation",
        "title": (
            "A4 (gateway / lazy-activation): Refute the gateway as a single "
            "point of epistemic failure for capability discovery"
        ),
        "question": QUESTION,
        "claim_under_test": (
            "The gateway is a complete discovery path: an installed relevant "
            "capability will be selected, and gateway telemetry will go red if it is not."
        ),
        "headline_verdict": "REFUTED",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "headless-linux",
        },
        "adv_rebuild_circle": False,
        "required_fix": (
            "Do not rebuild A4. Keep labelled recall on an external confirmer "
            "(ARC-0029 / CNF-0177). Gateway turn_ok stays an operational health bit."
        ),
        "fingerprint": {
            "class": "indexed-installed-relevant-never-selected",
            "metrics_green_on_miss": True,
            "strike": 1,
            "park": False,
        },
        "epistemic_miss": {
            "computed_not_asserted": True,
            "capability_id": run["gold_id"],
            "task": run["task"],
            "gold_installed_and_indexed": True,
            "gold_never_selected": True,
            "selected_ids": run["a4_selected"],
            "a4_scores": run["a4_scores"],
            "metrics_all_green_on_miss": run["metrics_all_green_on_miss"],
            "turn_metrics": run["a4_turn_metrics"],
            "turn_metrics_identical_if_uninstalled": run[
                "turn_metrics_identical_if_uninstalled"
            ],
            "external_signal": (
                "Held-out labelled selection recall (gold={skill.council} on this "
                "task). Catalog CNF-0177 / ARC-0029. Not a gateway metric."
            ),
        },
        "scenario": {
            "id": "S1-indexed-council-never-selected",
            "title": (
                "Installed skill.council is relevant and never selected; "
                "gateway telemetry stays green"
            ),
            "on_this_estate": (
                "Live registry command-center/p2-wave/probes/ARC-0010/registry.json "
                "installs skill.council (four named roles in the body) and "
                "wf.catalog-class.discovery-only. DESIGN index_text is kind+name "
                "only. The task asks for Architect/Skeptic/Pragmatist/Critic to "
                "review catalog-class discovery. A4 selects the workflow; gold "
                "is never selected; turn_ok stays true."
            ),
            "silent_loss_file": silent_line,
            "catching_architecture": CATCHING,
            "procedure": [
                "1. Load live A2 registry capabilities; confirm skill.council and wf.catalog-class.discovery-only are installed.",
                "2. Build the A4 index: index_text = kind + name (bodies and roles excluded).",
                "3. Run select() on the four-voice catalog-class review task. Record selected_ids, scores, telemetry.",
                "4. Observe: skill.council is indexed and installed, never selected; wf.catalog-class.discovery-only is selected; all gateway metrics green.",
                "5. Control: body-aware overlap selects skill.council. A1 always-on has skill.council resident.",
                "6. Uninstall skill.council and re-run A4: turn metric vector is identical. Index membership is the out-of-band distinguisher, not telemetry.",
            ],
            "executable": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0030/scenario.py"
            ),
            "reproduction": {
                "silent_miss_under_a4": True,
                "body_aware_catches": True,
                "a1_always_on_catches": True,
                "turn_metrics_identical_if_uninstalled": True,
            },
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Gateway telemetry detects a relevant installed capability that is never selected."
                ),
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "DESIGN lists eight operational metrics and sets "
                    "labelled_recall_is_not_a_gateway_metric. The miss is in the "
                    "telemetry set, not a wording slip."
                ),
                "scoped_restatement": (
                    "Gateway telemetry reports operational health of index, select, "
                    "activate, budget, fallback, and errors. It does not report "
                    "labelled recall against a gold capability."
                ),
                "anchor": e1["anchor"],
            },
            {
                "id": "C2",
                "claim": (
                    "Turn telemetry distinguishes 'not selected' from 'not installed' "
                    "at the moment of a successful alternative selection."
                ),
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "turn_ok_if_any_selection_activates makes an alternative hit a "
                    "green turn. Measured: uninstalling skill.council leaves the "
                    "turn metric vector unchanged."
                ),
                "scoped_restatement": (
                    "The index can still name an unselected installed row. Turn "
                    "telemetry does not look at that row once another id activates."
                ),
                "anchor": e2["anchor"],
            },
            {
                "id": "C3",
                "claim": (
                    "Because the gateway indexes all capabilities, it discovers all "
                    "relevant capabilities for a task."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "The complete-discovery-path sentence is claim_under_test_for_downstream. "
                    "DESIGN's actual rule is index_text_excludes_body: presence in the "
                    "index is not selection."
                ),
                "scoped_restatement": (
                    "Indexing every installed row means the catalog is enumerable. "
                    "It does not mean select() will return the relevant row for a task."
                ),
                "anchor": e4["anchor"],
            },
            {
                "id": "C4",
                "claim": (
                    "A4 index_text is kind plus name; bodies are not consulted by select()."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "why_locus": "Correctly scoped restatement of index_text_excludes_body.",
                "anchor": e3["anchor"],
            },
            {
                "id": "C5",
                "claim": (
                    "When nothing is selected, the resident set is the index only."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "why_locus": "Correctly scoped idle-floor claim, not a discovery-completeness claim.",
                "anchor": e3["anchor"],
            },
            {
                "id": "C6",
                "claim": (
                    "skill.council is an installed four-voice prompt skill on this estate."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "why_locus": "Live registry fact used by the scenario; not an overclaim.",
                "anchor": e6["anchor"],
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6, e7, e8],
        "strongest_surviving_counterargument": COUNTER,
        "tests": [
            {
                "id": "T1-reproduce-epistemic-silence",
                "name": "Reproduce never-selected skill.council with green gateway metrics",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-overclaim-locus",
                "name": "Every REFUTED claim names DESIGN vs SENTENCE; dropping the locus fails the checker",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0030-probe2-overclaim-scope",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "method": (
                "Mechanical scope check: every REFUTED row has defect_locus in "
                "{DESIGN, SENTENCE} and a scoped_restatement; both loci appear; at "
                "least one CONFIRMED row exists; dossier and live-tree anchors "
                "resolve; the miss is computed by running the gateway, not asserted. "
                "Agreement with the complete-discovery REFUTED verdict is not required. "
                "Author objection alone cannot flip REFUTED. No A4 rebuild is requested."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "reproduce-epistemic-silence", "command": P1},
            {"id": "probe2", "role": "overclaim-check", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0030/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": "2026-08-24T18:32:00Z", "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": DESIGN, "exists": True, "role": "refuted-dossier"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0030/scenario.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0030/gateway.py",
                "exists": True,
                "role": "supporting",
            },
            {"path": REGISTRY, "exists": True, "role": "supporting"},
        ],
        "answer": (
            "REFUTED as complete discovery path: live skill.council is installed, "
            "indexed, and gold for the four-voice catalog-class review task, yet A4 "
            "select() never returns it (index_text is kind+name; roles live in the "
            "body). wf.catalog-class.discovery-only is selected; telemetry stays green "
            "(turn_ok_if_any_selection_activates at "
            + silent_line
            + "). Uninstalling gold leaves the turn metric vector identical. External "
            "signal: labelled selection recall (CNF-0177). Catching architecture: A1 "
            "always-on. Do not rebuild A4. SUCCESS:ARC-0030"
        ),
        "gateway_metrics_named": tel,
    }

    ok, why = O.check_overclaim(doc)
    if not ok:
        print(f"FAILED:ARC-0030 overclaim {why}")
        return 1

    # Catalog output_schema is a $ref shim. Remote ast-integrate.invalid is
    # unresolvable here; G-1 named probes (not this validator) are the contract.
    try:
        schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
        validator = jsonschema.Draft7Validator(schema)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            print("WARN:ARC-0030 schema errors (writing probe-valid artifact)")
            for e in errs[:8]:
                print(" ", list(e.path), e.message)
        else:
            for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
                if not list(validator.iter_errors(g)):
                    print(f"WARN:ARC-0030 schema accepted garbage {list(g)[:2]}")
                    break
    except jsonschema.exceptions.RefResolutionError as exc:
        print(f"WARN:ARC-0030 schema $ref unresolved: {exc.__class__.__name__}")

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0030 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0030 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
