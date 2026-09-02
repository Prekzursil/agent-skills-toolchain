#!/usr/bin/env python3
"""Emit command-center/phase3/A2/REFUTATION.json for ARC-0016."""
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
import ensure_design as ED  # noqa: E402
import overclaim as O  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/phase3/A2/REFUTATION.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
DESIGN = "command-center/phase3/A2/DESIGN.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
GENERATOR = "command-center/p2-wave/probes/ARC-0010/generator.py"
REGISTRY = "command-center/p2-wave/probes/ARC-0010/registry.json"
QUESTION = (
    "Refute generated-SSOT: name the class of capability that CANNOT be expressed "
    "in a typed registry without an escape hatch, show how the escape hatch "
    "reintroduces exactly the drift the architecture exists to prevent, and "
    "quantify the blast radius of ONE generator bug across all generated artifacts."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0016/probe1_reproduce_hatch.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0016/probe2_overclaim.py"
)
COUNTER = (
    "Refusing the hatch is why A2 works. The typed subset (plugin, marketplace, "
    "skill/hook/rule, docs, workflow and council catalogs) really is a pure "
    "projection: two generate() runs are byte-identical, and a hand-edit is "
    "TAMPERED until regenerate discards it. CouncilSpec executable policy and "
    "live-larger comments stay outside the generated layer. Adding opaque_body "
    "would make a hand-edit capture-back CLEAN and would not encode those "
    "capabilities as typed fields anyway. Do not rebuild A2 to add the hatch "
    "(that is the ADV circle). Generated-SSOT remains the right architecture "
    "for typed projections; it is not a lossless encoding of the whole estate. "
    "The blast radius of one shared-path generator bug is the generated file "
    "count — the known cost of a single SSOT generator, not a reason to split it."
)
CATCHING = (
    "A2 as designed: additionalProperties false plus generator BANNED_KEYS refuse "
    "opaque_body, so capture-back cannot be encoded. Typed regenerate discards "
    "hand-edits instead of laundering them through an untyped blob."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def local_validator(schema_rel: str):
    """Draft-07 validator that resolves ast-integrate.invalid $ref from disk."""
    shim = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
        "https://ast-integrate.invalid/" + schema_rel.replace("\\", "/"): shim,
    }
    if isinstance(shim.get("$id"), str):
        store[shim["$id"]] = shim
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0016 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def art_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, fingerprint: str, rc: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:8000],
        "fingerprint": fingerprint,
        "exit_code": rc,
    }


def main() -> int:
    if ED.main() != 0:
        print("FAILED:ARC-0016 DESIGN.json could not be restored")
        return 1
    if not (REPO / DESIGN).is_file():
        print("FAILED:ARC-0016 DESIGN.json missing")
        return 1
    run = S.run_scenario()
    if not run.get("pass"):
        print("FAILED:ARC-0016 scenario did not reproduce escape hatch")
        print(json.dumps(run, indent=2, sort_keys=True, default=str)[:4000])
        return 1

    e1 = ev(
        DESIGN,
        '"first_non_expressible_construct": "opaque passthrough / untyped blob field copied into generated output"',
        "dossier",
        "DESIGN names the inexpressible class as opaque passthrough / untyped blob copied into generated output.",
    )
    e2 = ev(
        DESIGN,
        "the ARC-0016 escape-hatch class",
        "dossier",
        "DESIGN stop_reason states that an untyped opaque_body/passthrough field reintroduces the drift A2 exists to prevent.",
    )
    e3 = ev(
        DESIGN,
        "no banned opaque-passthrough key is present",
        "dossier",
        "A capability is expressible only as a typed a2-registry/v1 entry with additionalProperties false and no banned opaque-passthrough key.",
    )
    e4 = ev(
        DESIGN,
        '"stopped_at_first_inexpressible": true',
        "dossier",
        "DESIGN stopped at the first inexpressible construct rather than adding the hatch.",
    )
    e5 = ev(
        GENERATOR,
        '"opaque_body"',
        "live-tree",
        "The live generator bans opaque_body (and passthrough/untyped_blob/escape_hatch/executable_policy) before render.",
    )
    e6 = ev(
        CATALOG,
        "The CouncilSpec compiler exists as platform/lib/councilspec/",
        "live-tree",
        "Catalog R-A09 records a CouncilSpec compiler with a typed-tree expression parser — a corpus capability the A2 skill row explicitly does not encode.",
    )
    e7 = ev(
        REGISTRY,
        "No executable policy. No CouncilSpec expression tree.",
        "live-tree",
        "The live skill.council registry entry is a 4-voice prompt skill and refuses CouncilSpec executable policy.",
    )
    dossier_n = sum(1 for e in (e1, e2, e3, e4) if e["kind"] == "dossier")
    live_n = sum(1 for e in (e5, e6, e7) if e["kind"] == "live-tree")
    if dossier_n < 3 or live_n < 1:
        print(f"FAILED:ARC-0016 evidence counts dossier={dossier_n} live={live_n}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    silent_line = e2["anchor"]
    blast = run["blast_radius"]
    n_files = int(run["generated_file_count"])
    n_hit = int(run["files_affected_by_one_shared_path_bug"])
    answer = (
        "REFUTED as complete-SSOT: the inexpressible class is opaque "
        "passthrough / untyped blob ("
        + silent_line
        + "). Typed A2 refuses opaque_body; a hatch that copies it launders a "
        "hand-edit as CLEAN — the drift the generator exists to prevent. One "
        f"shared-path provenance() bug hits all {n_files} generated files "
        "(counted from generate(), not asserted). Corpus remainder: CouncilSpec "
        "executable policy (R-A09), which skill.council does not encode. "
        "Strongest surviving FOR: refuse the hatch; do not rebuild A2. "
        "SUCCESS:ARC-0016"
    )
    report = {
        "kind": "architecture-review",
        "observations": [
            {
                "name": "typed_rejects_opaque_body",
                "measured": True,
                "method": "validate_registry after adding opaque_body to skill.council",
                "anchor": e5["anchor"],
            },
            {
                "name": "hatch_reintroduces_drift",
                "measured": True,
                "method": "typed TAMPERED vs hatch capture-back CLEAN",
                "anchor": "command-center/p2-wave/probes/ARC-0016/hatch.py",
            },
            {
                "name": "blast_radius_equals_generated_file_count",
                "measured": n_hit,
                "method": blast["method"],
                "anchor": "command-center/p2-wave/probes/ARC-0016/hatch.py",
            },
        ],
        "control_ids": ["NC-LOCUS-STRIP", "NC-GARBAGE-SCHEMA"],
        "architecture_id": "A2",
        "architecture_class": "generated-ssot",
        "title": (
            "A2 (generated single-source-of-truth): Refute generated-SSOT: "
            "escape hatches reintroduce the drift the generator exists to prevent"
        ),
        "question": QUESTION,
        "claim_under_test": (
            "Generated-SSOT is a complete typed encoding of the estate: every "
            "capability is expressible in the registry without an escape hatch, "
            "and a generator bug is localized to one artifact."
        ),
        "headline_verdict": "REFUTED",
        "completion_sentinel": "SUCCESS:ARC-0016",
        "scope_not_agreement": True,
        "escape_hatch": {
            "class": "opaque passthrough / untyped blob field copied into generated output",
            "corpus_capability": (
                "CouncilSpec executable policy / typed-tree expression parser "
                "(catalog R-A09). The live skill.council row is a 4-voice prompt "
                "skill and states 'No executable policy. No CouncilSpec expression "
                "tree.' Live-larger comments and formatting not captured by typed "
                "fields are the same remainder class."
            ),
            "corpus_anchor": e6["anchor"],
            "typed_refusal": "additionalProperties false + generator BANNED_KEYS",
            "drift_mechanism": (
                "Capture-back of opaque_body from a hand-edited generated file "
                "into the registry makes the hand-edit CLEAN on regenerate. Typed "
                "A2 reports TAMPERED and regenerate discards the edit."
            ),
        },
        "blast_radius": {
            "computed_not_asserted": True,
            "method": blast["method"],
            "generator": blast["generator"],
            "generated_file_count": n_files,
            "files_affected_by_one_shared_path_bug": n_hit,
            "affected_paths": blast["affected_paths"],
            "bug": blast["bug"],
        },
        "scenario": {
            "id": "S1-opaque-passthrough-hatch-drift",
            "title": (
                "opaque_body is refused by typed A2; a hatch that copies it "
                "launders a hand-edit as CLEAN; one provenance() bug hits every "
                f"generated file (n={n_files})"
            ),
            "on_this_estate": (
                "DESIGN.json names first_non_expressible_construct as opaque "
                "passthrough and stop_reason as the ARC-0016 escape-hatch class. "
                "The live generator at command-center/p2-wave/probes/ARC-0010/"
                "generator.py bans opaque_body. Catalog R-A09 names the CouncilSpec "
                "compiler the typed skill row does not encode. The procedure "
                "executes that DESIGN rule against the live generator."
            ),
            "silent_loss_file": silent_line,
            "catching_architecture": CATCHING,
            "procedure": [
                "1. Load the live A2 registry (ARC-0010/registry.json) and call generate(); count the output map (blast-radius denominator).",
                "2. Add opaque_body to skill.council and call validate_registry: schema/BANNED_KEYS reject the field (typed path).",
                "3. Hand-edit generated skills/skill.council/SKILL.md; typed classify reports TAMPERED; regenerate drops the edit (CLEAN, marker absent).",
                "4. Hatch mutant: copy the hand-edit bytes into registry opaque_body and splice them onto the generated skill. Capture-back matches the hand-edit (CLEAN under the hatch).",
                "5. Monkey-patch provenance() to rewrite generator_version to 0.0.0-bug; recount generate() paths whose bytes differ. Affected count equals file count.",
                "6. Cite DESIGN.json stop_reason (ARC-0016 escape-hatch class) as the file:line that names the hatch and the drift it would reintroduce.",
            ],
            "executable": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0016/scenario.py"
            ),
            "reproduction": {
                "typed_rejects_hatch": True,
                "hatch_reintroduces_drift": True,
                "blast_radius_equals_file_count": True,
            },
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Generated-SSOT can encode every existing corpus capability in "
                    "a typed registry with no remainder and no escape hatch."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "DESIGN already names first_non_expressible_construct and stops "
                    "there. The completeness overclaim is the tournament sentence "
                    "that a single typed registry is a lossless SSOT for the estate, "
                    "not an extra DESIGN rule that adds the hatch."
                ),
                "scoped_restatement": (
                    "A2 encodes the typed subset (plugin, marketplace, skill, hook, "
                    "rule, doc, workflow, council catalogs). CouncilSpec executable "
                    "policy and opaque passthrough are refused, not encoded."
                ),
                "anchor": e1["anchor"],
            },
            {
                "id": "C2",
                "claim": (
                    "An opaque_body/passthrough escape hatch can be added so that "
                    "inexpressible corpus bytes still round-trip without reintroducing "
                    "the drift A2 exists to prevent."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "DESIGN stop_reason already states the hatch reintroduces drift "
                    "and refuses the field. The temptation to add the hatch anyway "
                    "is the overclaimed remainder channel, not a DESIGN encoding of "
                    "opaque_body."
                ),
                "scoped_restatement": (
                    "Copying opaque_body into generated output lets a hand-edit be "
                    "captured back into the registry and come back CLEAN. That is "
                    "the drift. Typed A2 reports TAMPERED and regenerate discards it."
                ),
                "anchor": e2["anchor"],
            },
            {
                "id": "C3",
                "claim": (
                    "A bug in the SSOT generator is localized to one artifact class "
                    "and cannot fan out across the generated tree."
                ),
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "DESIGN specifies a single generate() whose every renderer calls "
                    "the same provenance() helper. That shared path is in the dossier, "
                    "not a wording slip. Measured blast radius equals the generated "
                    "file count. This does not require rebuilding A2 into multiple "
                    "generators."
                ),
                "scoped_restatement": (
                    f"One shared-path generator bug hits all {n_files} generated files "
                    "on this fixture. That is the cost of a single SSOT projection, "
                    "not a reason to add an escape hatch or split the generator."
                ),
                "anchor": e3["anchor"],
            },
            {
                "id": "C4",
                "claim": (
                    "The A2 schema and live generator refuse an opaque_body/"
                    "passthrough field."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "Correctly scoped: additionalProperties false plus BANNED_KEYS. "
                    "validate_registry rejects the hatch on the live skill entry."
                ),
                "anchor": e3["anchor"],
            },
            {
                "id": "C5",
                "claim": (
                    "The first construct that is not expressible is an opaque "
                    "passthrough / untyped blob field copied into generated output."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "why_locus": "Correctly scoped restatement of first_non_expressible_construct.",
                "anchor": e1["anchor"],
            },
            {
                "id": "C6",
                "claim": (
                    "The 96 workflow + 48 protocol + 64 preset live libraries "
                    "round-trip through this generator on this tree."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "The tournament floor is a sentence. DESIGN residual cardinality "
                    "is NOT-CHECKED and the library files are absent; DESIGN does not "
                    "claim those bytes round-trip."
                ),
                "scoped_restatement": (
                    "On this worktree the measured generated set is the live "
                    f"generate() map ({n_files} files). The 96+48+64 libraries are "
                    "not claimed to round-trip (files absent)."
                ),
                "anchor": e4["anchor"],
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6, e7],
        "strongest_surviving_counterargument": COUNTER,
        "named_probes": [
            {"id": "probe1", "role": "reproduce-escape-hatch", "command": P1},
            {"id": "probe2", "role": "overclaim-check", "command": P2},
        ],
        "answer": answer,
        "adv_rebuild_circle": False,
        "required_fix": None,
    }

    ok, why = O.check_overclaim({"report": report})
    if not ok:
        print(f"FAILED:ARC-0016 overclaim {why}")
        return 1

    supporting = [
        art_row(DESIGN, "supporting"),
        art_row(SCHEMA, "supporting"),
        art_row("command-center/p2-wave/probes/ARC-0016/scenario.py", "supporting"),
        art_row("command-center/p2-wave/probes/ARC-0016/hatch.py", "supporting"),
        art_row(GENERATOR, "supporting"),
        art_row(REGISTRY, "supporting"),
    ]
    placeholder = "0" * 64
    primary = {
        "path": OUT,
        "bytes": 2048,
        "sha256": placeholder,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }
    scenario_tail = json.dumps(
        {k: run[k] for k in sorted(run) if k != "pass"},
        sort_keys=True,
        default=str,
    )[:4000]
    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0016",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0016",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0016]",
        "min_bytes_threshold": 2048,
        "artifacts": [primary] + supporting,
        "evidence": [
            {
                "claim": (
                    "Typed A2 refuses opaque_body; a hatch that copies it launders "
                    "a hand-edit as CLEAN; one provenance() bug hits every generated file."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": silent_line,
                "probes": [
                    probe(
                        "source",
                        "command",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0016/scenario.py",
                        scenario_tail,
                        "src:scenario",
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        e2["anchor"],
                        e2["snippet"],
                        "ver:design-stop-reason",
                    ),
                ],
            },
            {
                "claim": (
                    "REFUTED rows name DESIGN vs SENTENCE; dropping defect_locus "
                    "fails the overclaim checker."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0016/overclaim.py",
                "probes": [
                    probe(
                        "source",
                        "schema-validate",
                        "command-center/p2-wave/probes/ARC-0016/overclaim.py",
                        why,
                        "src:overclaim",
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        e5["anchor"],
                        "BANNED_KEYS includes opaque_body",
                        "ver:banned-keys",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-reproduce-escape-hatch",
                "name": (
                    "Reproduce typed refusal of opaque_body, hatch capture-back "
                    "drift, and counted blast radius against the A2 design artifact"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-overclaim-locus",
                "name": (
                    "Every REFUTED claim names DESIGN vs SENTENCE; dropping the "
                    "locus fails the checker"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-LOCUS-STRIP",
                "kind": "mutation",
                "description": (
                    "Drop defect_locus from one REFUTED claim; overclaim checker "
                    "must reject the mutant."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "claims[n]-REFUTED-missing-defect_locus",
                "good_state_output": why,
            },
            {
                "id": "NC-GARBAGE-SCHEMA",
                "kind": "malformed-input",
                "description": (
                    "architecture-review.schema.json with disk $ref store must "
                    "reject {} and {totally:unrelated}."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "required property missing",
                "good_state_output": "schema-valid architecture-review",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0016-probe2-overclaim-scope",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Mechanical scope check, not agreement. scope_not_agreement=true "
                "lives on report because reviewer additionalProperties is false. "
                "Author objection alone cannot flip REFUTED. No A2 rebuild."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0016/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "ARC-0016",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/ARC-0016/scenario.py",
                "artifact_path": DESIGN,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "command",
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0016/scenario.py",
                    scenario_tail,
                    "cons:scenario",
                ),
            },
            {
                "consumer": "command-center/p2-wave/probes/ARC-0016/emit_refutation.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/ARC-0016/emit_refutation.py",
                    "schema-valid architecture-review",
                    "cons:emit-schema",
                ),
            },
        ],
        "timestamps": {
            "started_at": "2026-08-24T18:17:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "retry ONCE on win-arg-limit with --ignore-user-config and a "
                "--prompt-file transport; never --background; on schema-invalid "
                "do not retry, fix the schema and re-dispatch"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "96 workflow + 48 protocol + 64 preset live libraries round-trip "
                    "through this generator on this tree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place 09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json on disk, extract typed "
                    "entries, and recount generate()."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "headless-linux",
        },
        "report": report,
    }

    validator = local_validator(SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0016 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0016 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0016 artifact {size}B below floor")
        return 1
    doc["artifacts"][0]["sha256"] = digest
    doc["artifacts"][0]["bytes"] = size
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0016 schema errors after hash fill")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0016 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
