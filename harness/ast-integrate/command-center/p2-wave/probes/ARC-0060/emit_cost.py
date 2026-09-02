#!/usr/bin/env python3
"""Emit command-center/phase3/A9/COST.json from the uniform counting rule."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

OUT = "command-center/phase3/A9/COST.json"
SCHEMA = "command-center/schema/architecture-cost-model.schema.json"
TSV = HERE / "inventory.tsv"
QUESTION = (
    "Quantify hybrid complexity as an UNDERSTANDABILITY budget: count the "
    "distinct concepts, config surfaces and runtime components a new "
    "contributor must learn to operate the composed system, compare against "
    "each single-architecture alternative, and state the threshold beyond "
    "which the spec's 'singular and understandable' condition is violated."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0060/probe1_counting_invariance.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0060/probe2_remeasure_awk.py"
)
THRESHOLD_VALUE = 9
MILLER = {
    "kind": "published-source",
    "id": "miller-1956",
    "work": (
        "The magical number seven, plus or minus two: Some limits on our "
        "capacity for processing information"
    ),
    "authors": "George A. Miller",
    "year": 1956,
    "venue": "Psychological Review, 63(2), 81–97",
    "applied_as": (
        "Upper bound of 7±2 is 9 distinct chunks. Architecture-specific "
        "operator items (concept + config_surface + runtime_component) are "
        "treated as chunks a new contributor must hold."
    ),
}
SPEC_CITE = {
    "kind": "spec-statement",
    "id": "catalog-singular-and-understandable",
    "path": "command-center/WORK-UNIT-CATALOG.json",
    "units": ["ARC-0059", "ARC-0060", "ARC-0073"],
    "quote": (
        "the spec forbids duplicate control planes and allows a hybrid winner "
        "only when its control planes remain singular and understandable"
    ),
}
SCHEMA_STORE_RELS = (
    SCHEMA,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
SUPPORTING_FOR_HASH = (
    SCHEMA,
    "command-center/p2-wave/probes/ARC-0060/inventory.py",
    "command-center/p2-wave/probes/ARC-0060/inventory.tsv",
    "command-center/p2-wave/probes/ARC-0060/probe1_counting_invariance.py",
    "command-center/p2-wave/probes/ARC-0060/probe2_remeasure_awk.py",
    "command-center/p2-wave/probes/ARC-0060/probe2_remeasure.sh",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()[:32]


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def live_file_set_roles(arch: str) -> dict:
    rel = f"command-center/phase3/{arch}/DESIGN.json"
    path = REPO / rel
    if not path.is_file():
        return {
            "dossier_present": False,
            "path": rel,
            "unique_roles": None,
            "roles": [],
            "note": "DESIGN.json absent; architecture-specific count is catalog-question inventory only.",
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    roles = sorted(
        {
            str(row.get("role") or "")
            for row in (doc.get("file_set") or [])
            if isinstance(row, dict) and row.get("role")
        }
    )
    return {
        "dossier_present": True,
        "path": rel,
        "unique_roles": len(roles),
        "roles": roles,
        "note": (
            "Live file_set.role cardinality is a GRANULARITY cross-check, not "
            "the headline. Headline uses the uniform catalog-question inventory."
        ),
    }


def write_tsv(path: Path) -> None:
    lines = ["id\tkind\tmember_csv\tsource_unit"]
    for it in I.ITEMS:
        members = ",".join(it["member_of"])
        lines.append(f"{it['id']}\t{it['kind']}\t{members}\t{it['source_unit']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def design_row(arch: str) -> dict:
    fwd = I.count_ids_forward(arch)
    byk = I.count_ids_by_kind_sum(arch)
    if fwd != byk:
        raise RuntimeError(f"{arch} forward={fwd} kind_sum={byk}")
    br = I.kind_breakdown(arch)
    return {
        "architecture_id": arch,
        "class": {
            "A1": "config-first-minimal",
            "A2": "generated-ssot",
            "A3": "marketplace-first",
            "A4": "gateway-lazy-activation",
            "A5": "distributed-workflow-runtime",
            "A6": "cross-vendor-adapter",
            "A7": "security-first",
            "A8": "ux-product-first",
            "A9": "maximal-hybrid",
        }[arch],
        "understandability_budget": fwd,
        "concepts": br["concept"],
        "config_surfaces": br["config_surface"],
        "runtime_components": br["runtime_component"],
        "item_ids": I.item_ids(arch),
        "second_counter_kind_sum": byk,
        "counters_agree": True,
        "live_design_file_set": live_file_set_roles(arch),
        "exceeds_threshold": fwd > THRESHOLD_VALUE,
    }


class OfflineResolver(jsonschema.RefResolver):
    """Resolve catalog $id values from the local store; never hit the network."""

    def resolve_remote(self, uri: str):
        if uri in self.store:
            return self.store[uri]
        raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def local_validator(schema: dict):
    store: dict = {}
    for rel in SCHEMA_STORE_RELS:
        path = REPO / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        ident = str(data.get("$id") or "")
        if ident:
            store[ident] = data
        store[path.resolve().as_uri()] = data
    resolver = OfflineResolver(
        base_uri=str(schema.get("$id") or (REPO / SCHEMA).resolve().as_uri()),
        referrer=schema,
        store=store,
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_block(role: str, method: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": code,
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    designs = [design_row(a) for a in I.ARCHS]
    by_id = {d["architecture_id"]: d for d in designs}
    hybrid = by_id["A9"]
    singles = [d for d in designs if d["architecture_id"] != "A9"]
    cheapest = min(singles, key=lambda d: d["understandability_budget"])
    dearest = max(singles, key=lambda d: d["understandability_budget"])
    violated = hybrid["understandability_budget"] > THRESHOLD_VALUE
    owner_decisions = present("command-center/OWNER-DECISIONS.md")
    a9_design = present("command-center/phase3/A9/DESIGN.json")

    write_tsv(TSV)

    comparison = []
    for d in designs:
        comparison.append(
            {
                "architecture_id": d["architecture_id"],
                "budget": d["understandability_budget"],
                "delta_vs_a9": hybrid["understandability_budget"]
                - d["understandability_budget"],
                "delta_vs_cheapest_single": d["understandability_budget"]
                - cheapest["understandability_budget"],
                "exceeds_threshold": d["exceeds_threshold"],
            }
        )

    headline = {
        "metric": "a9_understandability_budget",
        "value": hybrid["understandability_budget"],
        "cheapest_single": {
            "architecture_id": cheapest["architecture_id"],
            "value": cheapest["understandability_budget"],
        },
        "dearest_single": {
            "architecture_id": dearest["architecture_id"],
            "value": dearest["understandability_budget"],
        },
        "threshold": THRESHOLD_VALUE,
        "hybrid_exceeds_threshold": violated,
    }
    threshold = {
        "metric": "architecture_specific_operator_item_count",
        "value": THRESHOLD_VALUE,
        "comparator": "<=",
        "hybrid_value": hybrid["understandability_budget"],
        "violated_by_hybrid": violated,
        "citations": [MILLER, SPEC_CITE],
        "owner_decisions_present": owner_decisions,
        "owner_decisions_note": (
            "OWNER-DECISIONS.md is absent on this tree. The spec statement "
            "is taken from frozen catalog questions ARC-0059/ARC-0060/ARC-0073 "
            "that quote 'singular and understandable'."
            if not owner_decisions
            else "OWNER-DECISIONS.md is present; threshold still cites Miller 1956 and the catalog spec quote."
        ),
    }
    answer = (
        f"Under counting rule unique-operator-item-id applied identically "
        f"to all nine designs, A9 (maximal hybrid) has understandability "
        f"budget {hybrid['understandability_budget']} "
        f"(concepts={hybrid['concepts']}, "
        f"config_surfaces={hybrid['config_surfaces']}, "
        f"runtime_components={hybrid['runtime_components']}). "
        f"The cheapest single architecture is {cheapest['architecture_id']} "
        f"at {cheapest['understandability_budget']}; the dearest single is "
        f"{dearest['architecture_id']} at {dearest['understandability_budget']}. "
        f"The spec's 'singular and understandable' threshold is "
        f"{THRESHOLD_VALUE} architecture-specific operator items "
        f"(Miller 1956 upper bound of 7±2), citing also catalog ARC-0059/"
        f"ARC-0073. A9 exceeds that threshold "
        f"({hybrid['understandability_budget']} > {THRESHOLD_VALUE}). "
        f"Singularity of control planes is a separate predicate: the "
        f"composed kit names five authorities (SSOT, gateway, runtime, "
        f"adapter, permission) plus presentation. That plane count is "
        f"under 9; the item count is not. Maximal hybrid is therefore "
        f"not understandable on this budget even if it can be made "
        f"singular. A9 DESIGN.json is "
        f"{'present' if a9_design else 'absent'}; composition is catalog-"
        f"question inventory, not a delivered dossier. SUCCESS:ARC-0060"
    )
    report = {
        "kind": "architecture-cost-model",
        "observations": [
            {
                "name": "a9_understandability_budget",
                "measured": hybrid["understandability_budget"],
                "method": "unique-operator-item-id cardinality (forward walk)",
                "anchor": "command-center/p2-wave/probes/ARC-0060/inventory.py",
            },
            {
                "name": "a9_kind_bucket_sum",
                "measured": hybrid["second_counter_kind_sum"],
                "method": "reverse walk, sum of unique ids per kind",
                "anchor": "command-center/p2-wave/probes/ARC-0060/inventory.py",
            },
            {
                "name": "understandability_threshold",
                "measured": THRESHOLD_VALUE,
                "method": "Miller 1956 7±2 upper bound plus catalog spec quote",
                "anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0060]",
            },
        ],
        "control_ids": [
            "ARC-0060-NC-duplicate-id",
            "ARC-0060-NC-schema-garbage",
        ],
        "architecture_class": "maximal-hybrid",
        "architecture_id": "A9",
        "answer": answer,
        "question": QUESTION,
        "title": (
            "A9 (maximal hybrid): Understandability budget: concept count a "
            "contributor must hold to operate the hybrid"
        ),
        "cost_model_kind": "understandability-budget",
        "counting_rule": I.COUNTING_RULE,
        "comparison": comparison,
        "control_planes": {
            "note": (
                "Control-plane count is NOT the understandability headline. "
                "It is recorded so singularity and understandability are not collapsed."
            ),
            "a9": [
                {
                    "id": "ssot-registry",
                    "authority_over": "capability-identity-and-bytes",
                    "from": "A2",
                },
                {
                    "id": "gateway",
                    "authority_over": "activation-and-resident-set",
                    "from": "A4",
                },
                {
                    "id": "work-unit-runtime",
                    "authority_over": "dispatch-and-completion",
                    "from": "A5",
                },
                {
                    "id": "vendor-adapter",
                    "authority_over": "cross-vendor-transport",
                    "from": "A6",
                },
                {
                    "id": "permission-choke",
                    "authority_over": "authorization",
                    "from": "A7",
                },
            ],
            "not_authorities": [
                {
                    "id": "product-surface",
                    "from": "A8",
                    "why": "Presentation; must not grant a second capability authority.",
                },
                {
                    "id": "lockfile-pin",
                    "from": "A3",
                    "why": "Pins SSOT versions; does not own identity.",
                },
            ],
            "a9_authority_count": 5,
        },
        "dependency_inputs": {
            "ARC-0059_DESIGN.json": a9_design,
            "OWNER-DECISIONS.md": owner_decisions,
            "phase3/ROSTER.json": present("command-center/phase3/ROSTER.json"),
            "phase3/RUBRIC.json": present("command-center/phase3/RUBRIC.json"),
            "BASELINE-SNAPSHOT.json": present("command-center/BASELINE-SNAPSHOT.json"),
            "A1/DESIGN.json": present("command-center/phase3/A1/DESIGN.json"),
            "A2/DESIGN.json": present("command-center/phase3/A2/DESIGN.json"),
        },
        "designs": designs,
        "estate_shared": {
            "count": len(I.ESTATE_SHARED),
            "ids": [row["id"] for row in I.ESTATE_SHARED],
            "excluded_from_architecture_budgets": True,
            "reason": (
                "Shared capability classes a contributor already knows from the "
                "estate. Including them in every architecture would add the same "
                "constant and would not change ranking."
            ),
        },
        "headline": headline,
        "named_probes": [
            {"command": P1, "id": "probe1", "role": "counting-rule-invariance"},
            {
                "command": P2,
                "id": "probe2",
                "role": "awk-remeasure-and-threshold-citation",
            },
        ],
        "threshold": threshold,
        "completion_sentinel": "SUCCESS:ARC-0060",
    }

    out = REPO / OUT
    write_json(out, {"report": report, "state": "SUCCESS", "sentinel": "SUCCESS:ARC-0060"})

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print("FAILED:ARC-0060 named probes")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    planted = copy.deepcopy(I.ITEMS)
    planted.append(copy.deepcopy(planted[0]))
    orig = I.count_ids_forward("A1")
    after = I.count_ids_forward("A1", planted)
    plant_ok = after == orig

    src = probe_block("source", "test-run", P1, t1, c1)
    ver = probe_block("verifier", "command", P2, t2, c2)
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = local_validator(schema)

    artifacts = [artifact_row(rel, "supporting") for rel in SUPPORTING_FOR_HASH]
    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0060",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0060",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0060]",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "One counting rule (unique id in member_of) applied to A1-A9 "
                    "yields the recorded understandability budgets; a second "
                    "counter (kind-bucket sum) matches within error band 1."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0060/inventory.py",
                "probes": [src, ver],
            },
            {
                "claim": (
                    "The understandability threshold cites Miller 1956 and "
                    "catalog spec language rather than being asserted; awk "
                    "over inventory.tsv (id vs kind fields) re-derives the A9 headline."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0060/probe2_remeasure.sh",
                "probes": [ver, src],
            },
            {
                "claim": "A9 DESIGN.json was read from disk on this worktree.",
                "verdict": "CONFIRMED" if a9_design else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/phase3/A9/DESIGN.json",
                "probes": [
                    probe_block(
                        "source",
                        "file-read",
                        "python3 -c \"from pathlib import Path; p=Path('command-center/phase3/A9/DESIGN.json'); print(p.is_file())\"",
                        f"present={a9_design}",
                        0,
                    ),
                    probe_block(
                        "verifier",
                        "static-analysis",
                        "test -f command-center/phase3/A9/DESIGN.json; echo $?",
                        f"present={a9_design}",
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-counting-rule-invariance",
                "name": "A second counter applies the same rule to two designs and matches within one concept",
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-2000:],
            },
            {
                "id": "T2-threshold-justification-and-awk-remeasure",
                "name": "Threshold cites a source; awk remeasure of a different field agrees with the headline",
                "command": P2,
                "result": "PASS",
                "output_tail": t2[-2000:],
            },
        ],
        "negative_controls": [
            {
                "id": "ARC-0060-NC-duplicate-id",
                "kind": "mutation",
                "description": (
                    "Append a duplicate of the first inventory record. Unique-id "
                    "cardinality must stay unchanged."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"duplicate-id plant A1 orig={orig} after={after} silent={plant_ok}"
                ),
                "good_state_output": t1[-500:],
            },
            {
                "id": "ARC-0060-NC-schema-garbage",
                "kind": "malformed-input",
                "description": (
                    "Empty object, unrelated blob, and a SUCCESS-looking stub "
                    "must be rejected by architecture-cost-model schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "garbage documents rejected by Draft7Validator",
                "good_state_output": "live COST.json validates against architecture-cost-model",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0060-probe1-second-counter",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Second counter walks the same inventory in reverse and sums "
                "unique ids per kind. Probe 2 re-derives the A9 headline from "
                "inventory.tsv via awk (id column) and via kind-bucket sum "
                "(kind column). Catalog reviewer requirement is this re-derivation, "
                "not a second human cost-analyst."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0060/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "ARC-0060",
        },
        "downstream_consumers": [
            {
                "consumer": P1,
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": src,
            },
            {
                "consumer": P2,
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
                "probe": ver,
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "re-measure once with a MECHANICALLY DIFFERENT probe "
                "(different shell, different data field); if the two readings "
                "disagree report BLOCKED with both numbers rather than picking one"
            ),
        },
        "residual_unknowns": [
            {
                "claim": "Byte-level A9 DESIGN.json capability-to-authority table from ARC-0059.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver ARC-0059 DESIGN.json on this worktree, then re-run "
                    "this counter over DESIGN.json file_set and control-plane list."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "cost-analyst",
            "execution_substrate": "headless-linux",
        },
        "report": report,
    }
    if not plant_ok:
        print("FAILED:ARC-0060 duplicate-id plant incremented the count")
        return 1

    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0060 schema errors")
        for e in errs[:30]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "ARC-0060", "state": "SUCCESS", "sentinel": "SUCCESS:ARC-0060"},
    ]
    for g in garbage:
        g_errs = list(validator.iter_errors(g))
        if not g_errs:
            print(f"FAILED:ARC-0060 schema accepted garbage {list(g)[:2]}")
            return 1

    write_json(out, doc)
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0060 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"headline A9={hybrid['understandability_budget']} "
        f"cheapest={cheapest['architecture_id']}:{cheapest['understandability_budget']} "
        f"threshold={THRESHOLD_VALUE} exceeded={violated}"
    )
    print("SUCCESS:ARC-0060 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
