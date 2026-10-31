"""Blueprints 11-12 of 12: BP-GEM-05 Executed-Corpus Archaeology Mine, BP-BRN-01 Two-Peer Fan-out."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(HERE))

import bp1_build as B  # noqa: E402

S = B.schema

# -------------------------------------------------------------- 11. BP-GEM-05

_G5_ALLOW = [
    "Read",
    "Grep",
    "Glob",
    "Bash:python",
    "Write(command-center/archaeology/**)",
]


def _gem05() -> dict[str, Any]:
    root = "command-center/archaeology/bp-gem-05"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-gem-05-executed-corpus-archaeology-mine",
            "name": "Executed-Corpus Archaeology Mine",
            "description": (
                "Recover PROVEN workflow topologies from the estate's own executed run history instead "
                "of inventing new ones, and arrest the corpus's ongoing decay. The defining rule is "
                "mechanical: classification is done by a SCRIPT with zero LLM in the classification "
                "path, because handing a mechanical comparison to model judgement measured 86 percent "
                "accurate with 100 percent of the errors pointing at data loss. Enumeration is done "
                "TWICE with mechanically different probes that must corroborate before the index is "
                "trusted, and a probe that returns a different POPULATION (per-agent artifacts rather "
                "than run records) is rejected outright rather than averaged in. A missing script is a "
                "first-class outcome, not an error - most of the corpus is already gone."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": [
                "data-science-knowledge-and-creative",
                "collective-intelligence-and-meta",
            ],
            "tags": ["deterministic-index", "two-probe-corroboration", "decay-arrest"],
            "flagship": True,
            "params": {
                "corpus_roots": {
                    "type": "array",
                    "required": True,
                    "min_items": 1,
                    "max_items": 20,
                    "items": {"type": "path"},
                    "description": "Roots holding the executed run records",
                },
                "topology_pattern": {
                    "type": "string",
                    "default": "",
                    "max_length": 200,
                    "description": "Optional mechanism regex to search the surviving scripts for",
                },
                "corroboration_tolerance_percent": {
                    "type": "number",
                    "default": 5.0,
                    "minimum": 0,
                    "maximum": 25,
                    "description": "How far the two enumeration probes may disagree before the index is rejected",
                },
                "wrong_population_probe": {
                    "type": "string",
                    "required": True,
                    "min_length": 3,
                    "description": (
                        "A probe KNOWN to enumerate a DIFFERENT population (per-agent artifacts, not "
                        "run records). Its count must be REJECTED, which is how the corroboration check "
                        "proves it can discriminate at all."
                    ),
                },
                "snapshot_survivors": {
                    "type": "boolean",
                    "default": True,
                    "description": "Copy surviving scripts into the repo to arrest decay",
                },
                "recover_dead_run_ledgers": {
                    "type": "boolean",
                    "default": False,
                    "description": "Optional S4b: rebuild a dead run's ledger from the per-agent journals",
                },
                "artifact_root": {
                    "type": "path",
                    "default": root,
                    "description": "Every write is confined here",
                },
            },
            "roles": {
                "mechanical-indexer": {
                    "description": (
                        "A SCRIPT, not an agent judgement. Enumerates, resolves and classifies with no "
                        "LLM in the classification path - the C4 rule this blueprint exists to honour"
                    ),
                    "vendor": "any",
                    "effort": "low",
                    "authority": "judge",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Glob",
                        "Bash:python",
                        "Write(command-center/archaeology/**)",
                    ],
                    "speaking_rights": "always",
                },
                "corroborating-prober": {
                    "description": "Runs the SECOND, mechanically different enumeration; its job is to disagree if the first probe is wrong",
                    "vendor": "any",
                    "effort": "low",
                    "authority": "veto",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Glob",
                        "Grep",
                        "Bash:python",
                        "Write(command-center/archaeology/**)",
                    ],
                    "speaking_rights": "always",
                },
                "topology-interpreter": {
                    "description": (
                        "The ONLY model in the pipeline, and only for the semantic question a script "
                        "cannot answer: does this recovered topology MATTER, and what does it mean"
                    ),
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "informed",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Write(command-center/archaeology/**)",
                    ],
                    "speaking_rights": "on-request",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_G5_ALLOW),
                "deny": [
                    "Bash",
                    "WebFetch",
                    "WebSearch",
                    "mcp__codex__codex",
                    "Write(platform/**)",
                ],
                "network": "none",
                "write_paths": ["command-center/archaeology/**"],
                "forbid_write_paths": [
                    "platform/**",
                    "command-center/WORK-UNIT-CATALOG.json",
                ],
                "source_policy": {
                    "offline_only": True,
                    "require_provenance": True,
                    "treat_fetched_content_as_data": True,
                    "paywalled": "record-as-not-checked",
                },
            },
            "model_routing": {
                "strategy": "capability",
                "default": {
                    "model": "none-deterministic-script",
                    "vendor": "mixed",
                    "effort": "low",
                },
                "routes": [
                    {
                        "when": "stage_role == 'topology-interpreter'",
                        "target": {
                            "model": "opus",
                            "vendor": "anthropic",
                            "effort": "high",
                        },
                        "reason": "reserve the model for what code cannot do: judging whether a recovered topology matters",
                    }
                ],
                "forbid_downgrade_below": "opus",
            },
            "gates": {
                "probes-corroborate": {
                    "predicate": "custom-expression",
                    "expression": (
                        "enumeration_probes_agree == true "
                        "AND wrong_population_probe_rejected == true "
                        "AND llm_calls_in_classification_path == 0"
                    ),
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
                "index-complete": {
                    "predicate": "completion-predicate-v1",
                    "predicate_ref": "platform/schema/completion-predicate-result.schema.json",
                    "conditions_required": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
            },
            "stages": [
                {
                    "id": "enumerate-probe-a",
                    "title": "Probe A: enumerate run records by structured glob",
                    "kind": "task",
                    "role": "mechanical-indexer",
                    "checkpoint": True,
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPG-0501",
                        title="Count and list the executed run records with a structured glob",
                        phase="2B",
                        target=(
                            "Enumerate the run records under the corpus roots with a structured glob and "
                            "emit the population: the count, the file list, and the exact glob used. This "
                            "is probe A and is not trusted on its own."
                        ),
                        inputs=["params.corpus_roots"],
                        deps=[],
                        role="mechanical-indexer",
                        tools=[
                            "Read",
                            "Glob",
                            "Bash:python",
                            "Write(command-center/archaeology/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/enumeration-probe-a.json",
                        out_schema=S("sampling-frame"),
                        evidence="the artifact records the exact glob pattern, the count, and the first and last paths, so the population is reproducible",
                        tests=[
                            "the glob must be recorded verbatim; a count without its producing pattern cannot be corroborated",
                            "a root that does not exist must be reported as such, not silently contribute zero",
                        ],
                        reviewer="probe B must independently agree within tolerance before the index is trusted",
                        postcondition="the probe-A population exists, parses, and carries its glob pattern and count",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="counting is exactly computable; the C4 rule forbids fanning a mechanical count to judgement",
                        retry="none: a deterministic enumeration over an unchanged tree cannot produce a different count",
                        failure_classes=["corpus-root-missing", "detector-truncation"],
                        mechanism="structured-glob-enumeration",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/enumeration-probe-a.json",
                            S("sampling-frame"),
                            sentinel="SUCCESS:BPG-0501",
                            consumers=["corroboration-check", "resolve-existence"],
                        )
                    ],
                },
                {
                    "id": "enumerate-probe-b",
                    "title": "Probe B: a mechanically DIFFERENT enumeration, plus the wrong-population control",
                    "kind": "task",
                    "role": "corroborating-prober",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPG-0502",
                        title="Enumerate the same population by a different mechanism and reject the known-wrong population",
                        phase="2B",
                        target=(
                            "Enumerate the SAME population by a different mechanism (directory walk over "
                            "run directories rather than a file glob), and separately run the "
                            "known-WRONG-population probe. Probe B must agree with probe A within "
                            "tolerance, and the wrong-population count must be REJECTED with its reason."
                        ),
                        inputs=["params.corpus_roots", "params.wrong_population_probe"],
                        deps=[],
                        role="corroborating-prober",
                        tools=[
                            "Read",
                            "Glob",
                            "Grep",
                            "Bash:python",
                            "Write(command-center/archaeology/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/enumeration-probe-b.json",
                        out_schema=S("detector-control"),
                        evidence="both counts (probe B and the wrong-population probe) with their producing commands, plus the stated reason the third count enumerates a different population",
                        tests=[
                            "MANDATORY detector control: the wrong-population probe's count must be REJECTED, not averaged in - a check that cannot discriminate two populations measures nothing",
                            "probe B must use a different MECHANISM from probe A; re-running probe A's glob is not corroboration",
                        ],
                        reviewer="the corroboration gate compares the two counts numerically; neither prober adjudicates its own agreement",
                        postcondition="probe B has a count with its command, and the wrong-population probe is recorded as rejected with a reason",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="an independent second measurement, not a re-run of the first",
                        retry="none: deterministic enumeration over an unchanged tree",
                        failure_classes=["corpus-root-missing", "detector-failure"],
                        mechanism="mechanically-different-second-enumeration",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/enumeration-probe-b.json",
                            S("detector-control"),
                            sentinel="SUCCESS:BPG-0502",
                            consumers=["corroboration-check"],
                        )
                    ],
                },
                {
                    "id": "corroboration-check",
                    "title": "Compare the two counts numerically and reject the wrong population",
                    "kind": "task",
                    "depends_on": ["enumerate-probe-a", "enumerate-probe-b"],
                    "role": "mechanical-indexer",
                    "timeout_seconds": 600,
                    "work_unit": B.wu(
                        uid="BPG-0503",
                        title="Compute the probe disagreement against the declared tolerance",
                        phase="2B",
                        target=(
                            "Compute the percentage disagreement between probe A and probe B and compare "
                            "it against the declared tolerance. Record the verdict, and record separately "
                            "that the wrong-population count was excluded rather than reconciled."
                        ),
                        inputs=[
                            f"{root}/enumeration-probe-a.json",
                            f"{root}/enumeration-probe-b.json",
                            "params.corroboration_tolerance_percent",
                        ],
                        deps=["BPG-0501", "BPG-0502"],
                        role="mechanical-indexer",
                        tools=[
                            "Read",
                            "Bash:python",
                            "Write(command-center/archaeology/**)",
                        ],
                        substrate="local-single",
                        timeout=600,
                        out_path=f"{root}/corroboration.json",
                        out_schema=S("agreement-statistic"),
                        evidence="both counts, the computed disagreement percentage, the tolerance, and the PASS/FAIL verdict - all arithmetic, no judgement",
                        tests=[
                            "two counts differing by more than the tolerance must FAIL, blocking the index",
                            "both-states: two counts inside the tolerance must PASS in the same harness",
                            "the wrong-population count must never enter the disagreement arithmetic",
                        ],
                        reviewer="the corroboration gate reads this verdict; the interpreter never sees an unindexed corpus",
                        postcondition="the disagreement percentage is computed and compared against the tolerance with an explicit verdict",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="a subtraction and a comparison",
                        retry="none: arithmetic over unchanged inputs",
                        failure_classes=["probe-disagreement", "schema-invalid"],
                        mechanism="numeric-probe-corroboration",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/corroboration.json",
                            S("agreement-statistic"),
                            sentinel="SUCCESS:BPG-0503",
                            consumers=["corroboration-gate"],
                        )
                    ],
                },
                {
                    "id": "corroboration-gate",
                    "title": "No index without two agreeing probes and zero LLM in the classification path",
                    "kind": "gate",
                    "depends_on": ["corroboration-check"],
                    "gate_ref": "probes-corroborate",
                },
                {
                    "id": "resolve-existence",
                    "title": "Resolve every recorded script path to exists / missing",
                    "kind": "task",
                    "depends_on": ["corroboration-gate"],
                    "role": "mechanical-indexer",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPG-0504",
                        title="Classify each recorded script as resolving or already gone, and quantify the decay",
                        phase="2B",
                        target=(
                            "For every run record, resolve its script path on disk and classify it exists "
                            "or missing. A missing script is a FIRST-CLASS OUTCOME, not an error: the "
                            "decay rate is one of this blueprint's two deliverables."
                        ),
                        inputs=[f"{root}/enumeration-probe-a.json"],
                        deps=["BPG-0501"],
                        role="mechanical-indexer",
                        tools=[
                            "Read",
                            "Glob",
                            "Bash:python",
                            "Write(command-center/archaeology/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/decay-report.json",
                        out_schema=S("decay-inventory"),
                        evidence="counts of resolving vs missing with total surviving bytes; every missing path is listed, not summarised away",
                        tests=[
                            "a record whose script is absent must be classified missing, never dropped from the index",
                            "the resolving plus missing counts must equal the record count exactly",
                        ],
                        reviewer="the snapshot stage acts only on resolving scripts; the missing list is the decay evidence",
                        postcondition="every record is classified, the two counts reconcile against the total, and the surviving byte count is recorded",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="filesystem existence is a fact",
                        retry="none: deterministic resolution over an unchanged tree",
                        failure_classes=["schema-invalid", "count-mismatch"],
                        mechanism="script-existence-decay-census",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/decay-report.json",
                            S("decay-inventory"),
                            sentinel="SUCCESS:BPG-0504",
                            consumers=["mechanism-scan", "snapshot-survivors"],
                        )
                    ],
                },
                {
                    "id": "mechanism-scan",
                    "title": "Scan the survivors for mechanism signatures by regex",
                    "kind": "task",
                    "depends_on": ["resolve-existence"],
                    "role": "mechanical-indexer",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPG-0505",
                        title="Detect each surviving script's mechanism set with regexes, and rank by agents times completion",
                        phase="2B",
                        target=(
                            "Scan each surviving script for mechanism signatures (parallel fan-out, "
                            "schema-typed fan-in, adversarial review, gates, resume, worktree isolation, "
                            "cross-vendor dispatch, synthesis) and rank the scripts by agent count times "
                            "completion rate. Regexes only - no model reads a script here."
                        ),
                        inputs=[f"{root}/decay-report.json", "params.topology_pattern"],
                        deps=["BPG-0504"],
                        role="mechanical-indexer",
                        tools=[
                            "Read",
                            "Grep",
                            "Bash:python",
                            "Write(command-center/archaeology/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/mechanism-index.json",
                        out_schema=S("capability-index"),
                        evidence="every mechanism hit records the regex and the matching line, so a false positive is inspectable; the rank formula is stated",
                        tests=[
                            "a script with a known mechanism must be detected by name (detector control on the regex set)",
                            "a comparison regex must not match a bare assignment: the pattern must distinguish a threshold from an initialiser",
                        ],
                        reviewer="the topology interpreter reads only the top-ranked scripts and may not re-classify a mechanism",
                        postcondition="every surviving script has a mechanism set with per-hit regex and line, and a rank",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="pattern matching is exactly computable and inspectable; an LLM classification here measured 86 percent accurate with every error pointing at data loss",
                        retry="none: deterministic scanning over unchanged inputs",
                        failure_classes=["regex-false-positive", "schema-invalid"],
                        mechanism="regex-mechanism-detection-and-rank",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/mechanism-index.json",
                            S("capability-index"),
                            min_bytes=512,
                            sentinel="SUCCESS:BPG-0505",
                            consumers=["interpret-topologies", "snapshot-survivors"],
                        )
                    ],
                },
                {
                    "id": "interpret-topologies",
                    "title": "The one model stage: does this recovered topology MATTER?",
                    "kind": "task",
                    "depends_on": ["mechanism-scan"],
                    "role": "topology-interpreter",
                    "timeout_seconds": 2400,
                    "work_unit": B.wu(
                        uid="BPG-0506",
                        title="Describe what each top-ranked topology does and whether it is worth reusing",
                        phase="2B",
                        target=(
                            "For the top-ranked surviving scripts, describe the topology in DSL terms "
                            "(stages, fan-out width, barrier mode, gates) and judge whether it is worth "
                            "reusing. Do not re-classify mechanisms: the script owns that."
                        ),
                        inputs=[f"{root}/mechanism-index.json"],
                        deps=["BPG-0505"],
                        role="topology-interpreter",
                        tools=["Read", "Grep", "Write(command-center/archaeology/**)"],
                        substrate="local-single",
                        timeout=2400,
                        out_path=f"{root}/recovered-topologies.json",
                        out_schema=S("foundry-artifact"),
                        evidence="each topology cites the script path and line ranges it was read from, and states which mechanism-index row it corresponds to",
                        tests=[
                            "a topology description that contradicts the mechanism index must be rejected: the script's classification wins over the model's reading",
                            "a topology with no citable line range must be dropped",
                        ],
                        reviewer="one independent reviewer checks no described topology is absent from the mechanism index",
                        postcondition="every described topology cites its script and lines and maps to a mechanism-index row",
                        retry="two strikes then pivot: after two failures emit the mechanism index alone - the index is the durable deliverable",
                        failure_classes=["overclaim", "partial-artifact"],
                        mechanism="semantic-topology-interpretation",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/recovered-topologies.json",
                            S("foundry-artifact"),
                            min_bytes=256,
                            sentinel="SUCCESS:BPG-0506",
                            consumers=["completion-gate"],
                        )
                    ],
                },
                {
                    "id": "snapshot-survivors",
                    "title": "Arrest the decay: snapshot the surviving scripts",
                    "kind": "task",
                    "depends_on": ["mechanism-scan"],
                    "when": "snapshot_survivors == true",
                    "role": "mechanical-indexer",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPG-0507",
                        title="Copy every surviving script under version control with a byte-parity check",
                        phase="2B",
                        target=(
                            "Copy each surviving script into the snapshot root and verify byte parity per "
                            "file. Snapshotting without a parity check is how a snapshot silently holds "
                            "truncated copies."
                        ),
                        inputs=[
                            f"{root}/decay-report.json",
                            f"{root}/mechanism-index.json",
                        ],
                        deps=["BPG-0504"],
                        role="mechanical-indexer",
                        tools=[
                            "Read",
                            "Glob",
                            "Bash:python",
                            "Write(command-center/archaeology/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/snapshot-manifest.json",
                        out_schema=S("byte-parity-report"),
                        evidence="per file: source path, destination path, byte count and hash on both sides; a mismatch is a FAILED row, never a silent copy",
                        tests=[
                            "a truncated copy must be reported as a parity failure - a snapshot without a parity check is the defect this test exists for",
                            "the snapshot count must equal the surviving-script count",
                        ],
                        reviewer="the completion gate checks the manifest count against the decay report's surviving count",
                        postcondition="every surviving script is copied and byte-parity verified, with counts reconciled",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="copy plus hash comparison is exactly verifiable",
                        retry="two strikes then pivot: after two parity failures on one file, record it FAILED and continue with the rest",
                        failure_classes=["parity-mismatch", "count-mismatch"],
                        mechanism="snapshot-with-byte-parity",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/snapshot-manifest.json",
                            S("byte-parity-report"),
                            min_bytes=256,
                            sentinel="SUCCESS:BPG-0507",
                            consumers=["completion-gate"],
                        )
                    ],
                },
                {
                    "id": "recover-dead-ledgers",
                    "title": "Optional S4b: rebuild a dead run's ledger from the per-agent journals",
                    "kind": "task",
                    "depends_on": ["snapshot-survivors"],
                    "when": "recover_dead_run_ledgers == true",
                    "role": "mechanical-indexer",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPG-0508",
                        title="Join the per-agent journals on the agent identifier to rebuild a lost ledger",
                        phase="2B",
                        target=(
                            "For runs whose orchestrator died, rebuild the ledger by joining the "
                            "per-agent journals on the AGENT IDENTIFIER. The journal key is a content "
                            "hash, not a label, so joining on the key produces nonsense - join on the id."
                        ),
                        inputs=[f"{root}/decay-report.json", "params.corpus_roots"],
                        deps=["BPG-0504"],
                        role="mechanical-indexer",
                        tools=[
                            "Read",
                            "Glob",
                            "Grep",
                            "Bash:python",
                            "Write(command-center/archaeology/**)",
                        ],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/recovered-ledgers.json",
                        out_schema=S("run-ledger"),
                        evidence="each recovered row names the journal file and the agent identifier it was joined on, and states that the content-hash key was NOT used as the join field",
                        tests=[
                            "joining on the content-hash key must produce a detectably wrong result, proving the id join is the correct one",
                            "a run with no surviving journals must be reported unrecoverable, not partially invented",
                        ],
                        reviewer="one independent reviewer spot-checks two recovered rows against their journal files",
                        postcondition="every attempted run is either recovered with its join field named or reported unrecoverable",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="a relational join on a declared key",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=["journal-missing", "join-key-wrong"],
                        mechanism="journal-join-ledger-recovery",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/recovered-ledgers.json",
                            S("run-ledger"),
                            min_bytes=128,
                            sentinel="SUCCESS:BPG-0508",
                            consumers=["completion-gate"],
                        )
                    ],
                },
                {
                    "id": "completion-gate",
                    "title": "The 12-condition completion predicate over the index deliverables",
                    "kind": "gate",
                    "depends_on": ["interpret-topologies", "recover-dead-ledgers"],
                    "gate_ref": "index-complete",
                },
            ],
            "stopping_rules": [
                {
                    "id": "index-built",
                    "expression": "records_without_classification == 0 AND enumeration_probes_agree == true",
                    "applies_to": "workflow",
                    "minimum_conditions": "records_enumerated >= 1",
                    "on_stop": "complete",
                },
                {
                    "id": "probes-disagree",
                    "expression": "enumeration_probes_agree == false",
                    "applies_to": "workflow",
                    "on_stop": "escalate",
                },
            ],
            "retry_policy": B.retry_none(),
            "failure_policy": B.failure(
                "fail-fast",
                [
                    "probe-disagreement",
                    "count-mismatch",
                    "parity-mismatch",
                    "corpus-root-missing",
                ],
                escalate_to="the caller",
                quarantine_path=f"{root}/quarantine",
            ),
            "resume": B.resume_block(
                f"{root}/checkpoints",
                granularity="stage",
                keys=["workflow_id", "workflow_version", "stage_id", "inputs_hash"],
            ),
            "replay": B.replay_deterministic(
                20260810, f"{root}/replay/journal.jsonl", verify="hash-equal"
            ),
            "cache": B.cache_block(
                f"{root}/cache",
                ["workflow_version", "stage_id", "inputs_hash"],
                ttl=2592000,
                scope="workflow",
            ),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                ["Bash:python", "Write(command-center/archaeology/**)"],
                emits=["plan", "estimate", "permission-report", "artifact-diff"],
            ),
            "estimate": B.estimate_block(
                wallclock=(300, 1200, 5400),
                tokens=(20000, 120000, 500000),
                tool_calls=(30, 250),
                cost=(0.1, 0.6, 2.5),
                risk="low",
                reversibility="reversible",
                blast_radius="read-only over the owner's own session history; the snapshot writes only under command-center/archaeology/** and the index is never egressed",
                confidence="likely",
            ),
            "portability": B.portability_block(
                "command-center/export/bp-gem-05.bundle.json",
                includes=[
                    "definition",
                    "tests",
                    "examples",
                    "lineage",
                    "replay-journal",
                ],
            ),
            "lineage": B.lineage_block(
                [
                    {
                        "source": "exec-corpus-itself",
                        "relation": "REBUILD-FROM-SPEC",
                        "license": "owner-proprietary",
                        "credit": "owner (the population: run records, distinct scripts, agents dispatched, decay)",
                    },
                    {
                        "source": "skills/recall-workflow-agent",
                        "relation": "EXTEND",
                        "license": "owner-proprietary",
                        "credit": "owner (the existing per-agent extractor)",
                    },
                    {
                        "source": "tool-harness-corpus",
                        "relation": "EXTEND",
                        "license": "owner-proprietary",
                        "credit": "owner (streaming, bounded-memory, fail-soft distillation pattern)",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-GEM-05",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ]
            ),
            "outputs": {
                "mechanism-index": B.artifact(
                    f"{root}/mechanism-index.json",
                    S("capability-index"),
                    min_bytes=512,
                    consumers=["command-center/DECISION-LOG.json"],
                ),
                "decay-report": B.artifact(
                    f"{root}/decay-report.json",
                    S("decay-inventory"),
                    min_bytes=256,
                    consumers=["snapshot-survivors"],
                ),
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-GEM-05", 646),
                "acquisition_route_from_card": "BUILD-NEW",
                "mechanism_signature": [
                    "structured-glob-enumeration",
                    "mechanically-different-second-enumeration",
                    "wrong-population-probe-rejected",
                    "zero-llm-in-the-classification-path",
                    "script-existence-decay-census",
                    "regex-mechanism-detection-and-rank",
                    "snapshot-with-byte-parity",
                ],
                "contraindications": [
                    "NOT a substitute for reading the one script you care about",
                    "NOT for provenance of THIRD-PARTY workflows",
                    "the per-agent artifact population is a DIFFERENT set from the run records; conflating them produces a nonsense count, which is exactly what the wrong-population probe exists to demonstrate",
                ],
                "the_c4_rule": (
                    "Classification is mechanical by mandate. Handing a byte/line/set-membership "
                    "comparison to LLM judgement measured 86 percent accurate with 100 PERCENT of the "
                    "errors in the data-loss direction. Error DIRECTION is the metric, not accuracy - "
                    "so the script classifies everything and the model only describes what the "
                    "divergent content MEANS."
                ),
                "unverified": [
                    "UNVERIFIED yield; settling experiment = mine for per-work-unit pipeline topologies "
                    "and count how many distinct PROVEN variants exist versus the one documented in the "
                    "authoring guidance.",
                ],
                "owner_decision": "Snapshot every surviving script into the repo now to stop the decay, or index-only?",
                "worked_example": {
                    "name": "index the executed corpus and snapshot the survivors",
                    "params": {
                        "corpus_roots": ["command-center/corpus/run-records"],
                        "topology_pattern": "per-work-unit|barrier|schema-typed-fan-in",
                        "corroboration_tolerance_percent": 5.0,
                        "wrong_population_probe": "glob every per-agent artifact under the subagents tree",
                        "snapshot_survivors": True,
                        "recover_dead_run_ledgers": False,
                    },
                    "expected_stage_order": [
                        "enumerate-probe-a",
                        "enumerate-probe-b",
                        "corroboration-check",
                        "corroboration-gate",
                        "resolve-existence",
                        "mechanism-scan",
                        "interpret-topologies",
                        "snapshot-survivors",
                        "recover-dead-ledgers",
                        "completion-gate",
                    ],
                    "expected_skipped": ["recover-dead-ledgers"],
                    "expected_max_parallel": 1,
                    "expected_gate_ids": ["corroboration-gate", "completion-gate"],
                    "acceptance": [
                        "the two enumeration probes agree within 5 percent",
                        "the wrong-population probe's count is REJECTED with its reason recorded",
                        "resolving plus missing equals the record count exactly",
                        "every snapshotted file passes byte parity",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "index-built",
                            "why": "the index may not be declared built while any record is unclassified or the probes disagree",
                            "fires_on": {
                                "records_without_classification": 0,
                                "enumeration_probes_agree": True,
                                "records_enumerated": 708,
                            },
                            "does_not_fire_on": {
                                "records_without_classification": 12,
                                "enumeration_probes_agree": True,
                                "records_enumerated": 708,
                            },
                        },
                        {
                            "rule": "probes-disagree",
                            "why": "disagreeing probes must escalate: a self-contradicting detector is a detector failure, never a finding",
                            "fires_on": {
                                "records_without_classification": 0,
                                "enumeration_probes_agree": False,
                                "records_enumerated": 708,
                            },
                            "does_not_fire_on": {
                                "records_without_classification": 0,
                                "enumeration_probes_agree": True,
                                "records_enumerated": 708,
                            },
                        },
                    ],
                },
            },
        }
    )


# -------------------------------------------------------------- 12. BP-BRN-01

_B1_ALLOW = [
    "Read",
    "Grep",
    "Bash:python",
    "Write(command-center/brainstorm/**)",
    "mcp__codex__codex",
]


def _brn01() -> dict[str, Any]:
    root = "command-center/brainstorm/bp-brn-01"
    return B.finalise(
        {
            "dsl_version": B.DSL_VERSION,
            "id": "bp-brn-01-two-peer-cross-vendor-idea-fanout",
            "name": "Two-Peer Cross-Vendor Idea Fan-out",
            "description": (
                "Generate ideas from two INDEPENDENT cross-vendor peers plus the host, then synthesise. "
                "Independence of failure modes is the point, not headcount: no peer ever sees another "
                "peer's output. The machinery that makes it work is a DISPATCH CONTRACT, because the "
                "measured failure was the adapter, not the vendor - three cross-vendor agents once "
                "produced zero artifacts while their coding quality was never exercised. So: the "
                "prompt travels BY FILE (an inline prompt blows the Windows command-line limit), the "
                "dispatch BLOCKS, and a result is accepted only on an AND-gate of exit code zero AND a "
                "non-empty output file AND a schema-valid parse. A result containing a background "
                "receipt string is rejected outright, and a repair loop retries an argument-limit "
                "failure exactly once with a scoped configuration before giving up terminally."
            ),
            "version": "1.0.0",
            "kind": "workflow",
            "categories": ["collective-intelligence-and-meta"],
            "tags": ["cross-vendor", "dispatch-contract", "and-gate"],
            "flagship": True,
            "params": {
                "prompt": {
                    "type": "string",
                    "required": True,
                    "min_length": 20,
                    "description": "The idea-generation prompt; written to a FILE before dispatch",
                },
                "n_peers": {
                    "type": "integer",
                    "default": 2,
                    "minimum": 2,
                    "maximum": 4,
                    "description": "At least two: one peer cannot be cross-checked for independence",
                },
                "peer_models": {
                    "type": "array",
                    "required": True,
                    "min_items": 2,
                    "max_items": 4,
                    "items": {"type": "string", "min_length": 3},
                    "description": "One entry per peer thread; distinct entries give model spread as well as vendor spread",
                },
                "output_schema_ref": {
                    "type": "path",
                    "default": "command-center/schema/synthesis-candidate.schema.json",
                    "description": "The schema each peer result must validate against for the AND-gate to pass",
                },
                "dispatch_timeout_seconds": {
                    "type": "integer",
                    "default": 1800,
                    "minimum": 300,
                    "maximum": 3600,
                    "description": "An explicit timeout is mandatory: the silent default is what a fire-and-forget dispatch was once rationalised to escape",
                },
                "artifact_root": {
                    "type": "path",
                    "default": root,
                    "description": "Every write is confined here",
                },
            },
            "roles": {
                "prompt-marshaller": {
                    "description": "Writes the prompt to a FILE and records its byte count; an inline prompt above the OS command-line limit fails the dispatch outright",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "medium",
                    "authority": "advisory",
                    "independence": "independent",
                    "tool_permissions": ["Read", "Write(command-center/brainstorm/**)"],
                    "speaking_rights": "always",
                },
                "cross-vendor-peer": {
                    "description": (
                        "One fresh-context peer thread. Blocking dispatch, prompt by file, and NO sight "
                        "of any sibling peer's output - that blindness is the independence being bought"
                    ),
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "effort": "high",
                    "authority": "advisory",
                    "independence": "independent",
                    "cross_vendor_required": True,
                    "tool_permissions": [
                        "mcp__codex__codex",
                        "Write(command-center/brainstorm/**)",
                    ],
                    "min_participants": 2,
                    "max_participants": 4,
                    "speaking_rights": "always",
                },
                "dispatch-auditor": {
                    "description": "Applies the AND-gate: exit code zero AND a non-empty output file AND a schema-valid parse. Exit zero alone is SEVERED, not success",
                    "vendor": "any",
                    "effort": "low",
                    "authority": "judge",
                    "independence": "independent",
                    "tool_permissions": [
                        "Read",
                        "Bash:python",
                        "Write(command-center/brainstorm/**)",
                    ],
                    "speaking_rights": "always",
                },
                "host-synthesiser": {
                    "description": "Merges the peer outputs and marks every idea that only ONE peer produced, because that is where the cross-vendor value shows up",
                    "model": "opus",
                    "vendor": "anthropic",
                    "effort": "max",
                    "authority": "chair",
                    "independence": "informed",
                    "tool_permissions": [
                        "Read",
                        "Grep",
                        "Write(command-center/brainstorm/**)",
                    ],
                    "speaking_rights": "always",
                },
            },
            "tool_policy": {
                "default": "deny",
                "allow": list(_B1_ALLOW),
                "deny": ["Bash", "WebFetch", "WebSearch", "Write(platform/**)"],
                "network": "none",
                "write_paths": ["command-center/brainstorm/**"],
                "forbid_write_paths": [
                    "platform/**",
                    "command-center/WORK-UNIT-CATALOG.json",
                ],
                "source_policy": {
                    "offline_only": True,
                    "require_provenance": True,
                    "treat_fetched_content_as_data": True,
                    "paywalled": "record-as-not-checked",
                },
            },
            "model_routing": {
                "strategy": "vendor-diverse",
                "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
                "routes": [
                    {
                        "when": "stage_role == 'cross-vendor-peer'",
                        "target": {
                            "model": "gpt-5-codex",
                            "vendor": "openai",
                            "effort": "high",
                        },
                        "reason": "the whole point is a vendor whose failure modes are not the host's",
                    }
                ],
                "escalation": {
                    "on": ["failure", "timeout"],
                    "target": {"model": "opus", "vendor": "anthropic", "effort": "max"},
                    "max_escalations": 1,
                },
                "forbid_downgrade_below": "opus",
            },
            "gates": {
                "dispatch-and-gate": {
                    "predicate": "custom-expression",
                    "expression": (
                        "peer_results_total > 0 "
                        "AND peer_results_exit_zero_and_nonempty_and_schema_valid == peer_results_total "
                        "AND receipt_string_results == 0"
                    ),
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "repair",
                },
                "independence-preserved": {
                    "predicate": "custom-expression",
                    "expression": "peers_that_saw_a_sibling_output == 0 AND peers_returning_terminal_state == peer_results_total",
                    "blocking": True,
                    "evidence_required": True,
                    "on_fail": "fail",
                },
            },
            "stages": [
                {
                    "id": "marshal-prompt",
                    "title": "Write the prompt to a FILE and record its byte count",
                    "kind": "task",
                    "role": "prompt-marshaller",
                    "checkpoint": True,
                    "timeout_seconds": 600,
                    "work_unit": B.wu(
                        uid="BPB-0101",
                        title="Marshal the prompt to a file, never inline, and record its size",
                        phase="2B",
                        target=(
                            "Write the prompt to a file under the artifact root and record its byte "
                            "count and hash. An inline prompt above the OS command-line limit produces a "
                            "hard argument-length error; the file route has no such ceiling."
                        ),
                        inputs=["params.prompt", "params.output_schema_ref"],
                        deps=[],
                        role="prompt-marshaller",
                        tools=["Read", "Write(command-center/brainstorm/**)"],
                        substrate="local-single",
                        timeout=600,
                        out_path=f"{root}/prompt-file.json",
                        out_schema=S("handoff-package"),
                        evidence="the record carries the prompt file path, byte count and hash, plus the schema reference each peer must satisfy",
                        tests=[
                            "a prompt larger than the OS command-line limit must be handled by the file route and succeed, not fail with an argument-length error",
                            "the recorded byte count must match the file on disk",
                        ],
                        reviewer="the dispatch auditor reads the recorded hash and confirms every peer received the same prompt",
                        postcondition="the prompt file exists, is non-empty, and its recorded hash matches the bytes on disk",
                        retry="fixed backoff, at most 2 attempts",
                        failure_classes=["prompt-unwritable", "win-arg-limit"],
                        mechanism="prompt-by-file-marshalling",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/prompt-file.json",
                            S("handoff-package"),
                            sentinel="SUCCESS:BPB-0101",
                            consumers=["dispatch-peers"],
                        )
                    ],
                },
                {
                    "id": "dispatch-peers",
                    "title": "Dispatch the peers in parallel, BLOCKING, each blind to the others",
                    "kind": "fanout",
                    "depends_on": ["marshal-prompt"],
                    "over": {
                        "source": "param",
                        "ref": "peer_models",
                        "item_var": "peer_model",
                        "key_field": "peer_model",
                    },
                    "max_concurrency": 4,
                    "arrival_stagger_ms": 0,
                    "max_items": 4,
                    "on_item_failure": "continue",
                    "body": [
                        {
                            "id": "dispatch-peer",
                            "title": "One blocking cross-vendor peer thread",
                            "kind": "task",
                            "role": "cross-vendor-peer",
                            "timeout_seconds": 3600,
                            "work_unit": B.wu(
                                uid="BPB-0102",
                                title="Run one fresh-context peer to completion and write its result to a file",
                                phase="2B",
                                target=(
                                    "Dispatch one peer with the prompt file, a scoped configuration and an "
                                    "explicit timeout, and BLOCK until it finishes. Never background the "
                                    "call, never return a job id, and never treat a progress stream as a "
                                    "result. Write the peer's output to its own file."
                                ),
                                inputs=[
                                    f"{root}/prompt-file.json",
                                    "params.dispatch_timeout_seconds",
                                ],
                                deps=["BPB-0101"],
                                role="cross-vendor-peer",
                                tools=[
                                    "mcp__codex__codex",
                                    "Write(command-center/brainstorm/**)",
                                ],
                                substrate="cross-vendor-codex",
                                timeout=3600,
                                out_path=f"{root}/peers/peer-result.json",
                                out_schema=S("synthesis-candidate"),
                                evidence="the dispatch record carries the exit code, the output file path, its byte count, and the elapsed wall-clock time - a turn count is not evidence a call blocked",
                                tests=[
                                    "MANDATORY: a killed peer must produce a terminal FAILED marker with the diagnostic tail, never silence and never a job id",
                                    "a result string containing a background receipt must be rejected by the auditor rather than parsed as ideas",
                                    "the recorded wall-clock time must be consistent with a blocking call",
                                ],
                                reviewer="the dispatch auditor applies the AND-gate; this peer never self-certifies",
                                postcondition="the peer wrote a non-empty output file AND exited zero, or a terminal FAILED marker exists with its diagnostic tail",
                                model="gpt-5-codex",
                                vendor="openai",
                                basis="a genuinely independent vendor: the value is uncorrelated failure modes, not extra headcount",
                                retry="two strikes then pivot: on an argument-limit failure retry ONCE with a scoped configuration, then fail terminally",
                                failure_classes=[
                                    "win-arg-limit",
                                    "severed-stream",
                                    "codex-exit-nonzero",
                                    "timeout",
                                ],
                                mechanism="blocking-file-prompt-peer-dispatch",
                            ),
                            "produces": [
                                B.artifact(
                                    f"{root}/peers/peer-result.json",
                                    S("synthesis-candidate"),
                                    min_bytes=128,
                                    sentinel="SUCCESS:BPB-0102",
                                    consumers=["audit-dispatch"],
                                )
                            ],
                        }
                    ],
                    "barrier": {
                        "mode": "all",
                        "on_partial": "proceed-degraded",
                        "require_stages": ["dispatch-peer"],
                        "reject_result_matching": [
                            "started in the background",
                            "Check /codex:status",
                            "task-[0-9a-f]{6,}",
                        ],
                        "verify_artifact_exists": True,
                    },
                },
                {
                    "id": "audit-dispatch",
                    "title": "AND-gate every peer result: exit zero AND non-empty file AND schema-valid",
                    "kind": "task",
                    "depends_on": ["dispatch-peers"],
                    "role": "dispatch-auditor",
                    "timeout_seconds": 600,
                    "tool_permissions": [
                        "Read",
                        "Bash:python",
                        "Write(command-center/brainstorm/**)",
                    ],
                    "work_unit": B.wu(
                        uid="BPB-0103",
                        title="Compute the three-signal AND-gate per peer and classify every failure",
                        phase="2B",
                        target=(
                            "For each peer compute all three signals: exit code zero, a non-empty output "
                            "file that exists, and a schema-valid parse. Only all three together are "
                            "SUCCESS. Exit zero with no parseable file is SEVERED. Classify each failure "
                            "into its taxonomy class."
                        ),
                        inputs=[
                            f"{root}/peers/peer-result.json",
                            "params.output_schema_ref",
                        ],
                        deps=["BPB-0102"],
                        role="dispatch-auditor",
                        tools=[
                            "Read",
                            "Bash:python",
                            "Write(command-center/brainstorm/**)",
                        ],
                        substrate="local-single",
                        timeout=600,
                        out_path=f"{root}/dispatch-audit.json",
                        out_schema=S("conformance-report"),
                        evidence="per peer: all three signal values individually plus the AND result and the failure class; an aggregate verdict without the three components is not the gate",
                        tests=[
                            "MANDATORY both-states: exit zero with an EMPTY output file must be SEVERED, and the same peer with a valid file must be SUCCESS",
                            "a result whose text matches a background-receipt pattern must be rejected outright",
                            "a schema-invalid but non-empty file must be schema-invalid, not SUCCESS",
                        ],
                        reviewer="the synthesiser consumes only peers this audit marked SUCCESS",
                        postcondition="every peer has all three signals recorded plus an AND verdict and, where failing, a taxonomy class",
                        model="none-deterministic-script",
                        vendor="mixed",
                        basis="three mechanical checks; a model opinion about whether a dispatch succeeded is what let a progress stream be reported as an answer",
                        retry="none: re-running a deterministic audit over unchanged files cannot change the verdict",
                        failure_classes=[
                            "severed-stream",
                            "schema-invalid",
                            "receipt-not-result",
                        ],
                        mechanism="three-signal-and-gate",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/dispatch-audit.json",
                            S("conformance-report"),
                            sentinel="SUCCESS:BPB-0103",
                            consumers=["and-gate", "repair-dispatch", "synthesise"],
                        )
                    ],
                },
                {
                    "id": "and-gate",
                    "title": "No peer result is accepted on exit code alone",
                    "kind": "gate",
                    "depends_on": ["audit-dispatch"],
                    "gate_ref": "dispatch-and-gate",
                },
                {
                    "id": "repair-dispatch",
                    "title": "Repair a failed dispatch once, with an INDEPENDENT verify",
                    "kind": "repair_loop",
                    "depends_on": ["and-gate"],
                    "target": ["dispatch-peers"],
                    "max_attempts": 2,
                    "classification_filter": [
                        "win-arg-limit",
                        "severed-stream",
                        "codex-exit-nonzero",
                        "timeout",
                    ],
                    "escalate_to": "synthesise",
                    "require_root_cause": True,
                    "diagnose": {
                        "id": "diagnose-dispatch",
                        "title": "Name the failure class from the audit, not from the stream",
                        "kind": "task",
                        "role": "dispatch-auditor",
                        "timeout_seconds": 600,
                        "work_unit": B.wu(
                            uid="BPB-0104",
                            title="Classify the dispatch failure from the recorded signals and state the root cause",
                            phase="2B",
                            target=(
                                "Read the audit and name the root cause per failed peer: an argument-limit "
                                "failure, a severed stream, a non-zero exit, or a timeout. The taxonomy "
                                "class determines the repair, so a guess here is a wasted retry."
                            ),
                            inputs=[f"{root}/dispatch-audit.json"],
                            deps=["BPB-0103"],
                            role="dispatch-auditor",
                            tools=[
                                "Read",
                                "Bash:python",
                                "Write(command-center/brainstorm/**)",
                            ],
                            substrate="local-single",
                            timeout=600,
                            out_path=f"{root}/dispatch-diagnosis.json",
                            out_schema=S("root-cause-graph"),
                            evidence="each diagnosis cites the recorded signal that established it (exit code, byte count, elapsed time, error text)",
                            tests=[
                                "an argument-limit failure must be distinguished from a severed stream: they take different repairs",
                                "a diagnosis with no citing signal must be rejected",
                            ],
                            reviewer="the verify gate is independent of this diagnosis and re-checks the AND-gate from scratch",
                            postcondition="every failed peer has a root cause citing the signal that established it",
                            model="none-deterministic-script",
                            vendor="mixed",
                            basis="classification from recorded signals",
                            retry="none: classification over unchanged records is deterministic",
                            failure_classes=["diagnosis-ambiguous"],
                            mechanism="signal-cited-failure-classification",
                        ),
                        "produces": [
                            B.artifact(
                                f"{root}/dispatch-diagnosis.json",
                                S("root-cause-graph"),
                                min_bytes=128,
                                sentinel="SUCCESS:BPB-0104",
                                consumers=["apply-scoped-retry"],
                            )
                        ],
                    },
                    "repair": {
                        "id": "apply-scoped-retry",
                        "title": "Retry ONCE with a scoped configuration, per the diagnosed class",
                        "kind": "task",
                        "role": "cross-vendor-peer",
                        "timeout_seconds": 3600,
                        "work_unit": B.wu(
                            uid="BPB-0105",
                            title="Re-dispatch the failed peer once with the repair its class prescribes",
                            phase="2B",
                            target=(
                                "Re-dispatch each failed peer exactly once with the class-specific repair: "
                                "an argument-limit failure gets a scoped configuration that drops the "
                                "ambient tool inventory; a severed stream gets a fresh thread. Two strikes "
                                "on the same fingerprint means stop, not try harder."
                            ),
                            inputs=[
                                f"{root}/dispatch-diagnosis.json",
                                f"{root}/prompt-file.json",
                            ],
                            deps=["BPB-0104"],
                            role="cross-vendor-peer",
                            tools=[
                                "mcp__codex__codex",
                                "Write(command-center/brainstorm/**)",
                            ],
                            substrate="cross-vendor-codex",
                            timeout=3600,
                            out_path=f"{root}/peers/peer-retry.json",
                            out_schema=S("synthesis-candidate"),
                            evidence="the retry records the repair applied, the new exit code, the new byte count and the elapsed time",
                            tests=[
                                "the retry must be attempted at most ONCE per peer - a third attempt on the same fingerprint is the anti-grind violation this bounds",
                                "a retry that fails again must produce a terminal FAILED marker, never silence",
                            ],
                            reviewer="the verify stage re-applies the full AND-gate; a retry does not self-certify",
                            postcondition="each failed peer has exactly one retry recorded, ending in SUCCESS or a terminal FAILED marker",
                            model="gpt-5-codex",
                            vendor="openai",
                            basis="the repair is class-specific; a blind retry is what two-strikes forbids",
                            retry="none at this level: the repair loop itself is the bounded retry, capped at two attempts",
                            failure_classes=[
                                "win-arg-limit",
                                "severed-stream",
                                "codex-exit-nonzero",
                                "timeout",
                            ],
                            mechanism="class-specific-single-retry",
                        ),
                        "produces": [
                            B.artifact(
                                f"{root}/peers/peer-retry.json",
                                S("synthesis-candidate"),
                                min_bytes=128,
                                sentinel="SUCCESS:BPB-0105",
                                consumers=["verify-dispatch"],
                            )
                        ],
                    },
                    "verify": {
                        "id": "verify-dispatch",
                        "title": "Independent verify: re-apply the AND-gate from scratch",
                        "kind": "gate",
                        "gate": {
                            "predicate": "custom-expression",
                            "expression": (
                                "retried_peers_exit_zero_and_nonempty_and_schema_valid == retried_peers_total "
                                "AND receipt_string_results == 0"
                            ),
                            "blocking": True,
                            "evidence_required": True,
                            "on_fail": "escalate-to-human",
                        },
                    },
                },
                {
                    "id": "independence-gate",
                    "title": "No peer saw a sibling's output; every peer ended in a terminal state",
                    "kind": "gate",
                    "depends_on": ["repair-dispatch"],
                    "gate_ref": "independence-preserved",
                },
                {
                    "id": "synthesise",
                    "title": "Merge the peer ideas and mark what only ONE peer produced",
                    "kind": "task",
                    "depends_on": ["independence-gate"],
                    "role": "host-synthesiser",
                    "timeout_seconds": 1800,
                    "work_unit": B.wu(
                        uid="BPB-0106",
                        title="Emit merged ideas, disagreements, and the novel-to-one-peer set",
                        phase="2B",
                        target=(
                            "Merge the SUCCESS peer outputs plus the host's own ideas into three explicit "
                            "sets: merged (more than one peer), disagreements, and novel-to-one-peer. The "
                            "third set is where cross-vendor independence pays, so it is never folded "
                            "into the first."
                        ),
                        inputs=[
                            f"{root}/peers/peer-result.json",
                            f"{root}/peers/peer-retry.json",
                            f"{root}/dispatch-audit.json",
                        ],
                        deps=["BPB-0102", "BPB-0103"],
                        role="host-synthesiser",
                        tools=["Read", "Grep", "Write(command-center/brainstorm/**)"],
                        substrate="local-single",
                        timeout=1800,
                        out_path=f"{root}/synthesis.json",
                        out_schema=S("synthesis-candidate"),
                        evidence="every idea names the peer or peers that produced it; the novel-to-one-peer set states which peer, so the independence value is measurable",
                        tests=[
                            "an idea produced by exactly one peer must appear in novel-to-one-peer, not in merged",
                            "if only one peer returned SUCCESS the synthesis must state the loss of independence explicitly rather than presenting one peer as consensus",
                        ],
                        reviewer="one independent reviewer checks no idea in merged is attributed to a single peer",
                        postcondition="the synthesis exists, parses, and every idea carries its peer attribution with the three sets kept separate",
                        retry="two strikes then pivot: after two failures emit the raw peer outputs plus the blocking reason",
                        failure_classes=[
                            "overclaim",
                            "partial-artifact",
                            "independence-lost",
                        ],
                        mechanism="novel-to-one-peer-synthesis",
                    ),
                    "produces": [
                        B.artifact(
                            f"{root}/synthesis.json",
                            S("synthesis-candidate"),
                            min_bytes=512,
                            sentinel="SUCCESS:BPB-0106",
                            consumers=["command-center/DECISION-LOG.json"],
                        )
                    ],
                },
            ],
            "stopping_rules": [
                {
                    "id": "all-peers-terminal",
                    "expression": "peers_returning_terminal_state == peer_results_total",
                    "applies_to": "workflow",
                    "minimum_conditions": "peer_results_total >= 2",
                    "on_stop": "complete",
                },
                {
                    "id": "independence-lost",
                    "expression": "peers_with_success_verdict <= 1",
                    "applies_to": "workflow",
                    "on_stop": "emit-partial",
                },
            ],
            "retry_policy": B.retry_two_strikes(
                2,
                escalate_to="synthesise",
                retry_on=["win-arg-limit", "severed-stream", "timeout"],
            ),
            "failure_policy": B.failure(
                "degrade-loudly",
                [
                    "win-arg-limit",
                    "severed-stream",
                    "codex-exit-nonzero",
                    "timeout",
                    "receipt-not-result",
                ],
                escalate_to="synthesise",
                quarantine_path=f"{root}/quarantine",
            ),
            "resume": B.resume_block(
                f"{root}/checkpoints",
                granularity="fanout-item",
                keys=[
                    "workflow_id",
                    "workflow_version",
                    "stage_id",
                    "item_key",
                    "inputs_hash",
                ],
            ),
            "replay": B.replay_not_deterministic(),
            "cache": B.cache_off(),
            "dry_run": B.dry_run_block(
                f"{root}/dry-run-plan.json",
                [
                    "mcp__codex__codex",
                    "Bash:python",
                    "Write(command-center/brainstorm/**)",
                ],
                emits=["plan", "estimate", "permission-report", "graph"],
            ),
            "estimate": B.estimate_block(
                wallclock=(300, 1500, 4200),
                tokens=(40000, 200000, 700000),
                tool_calls=(20, 120),
                cost=(0.3, 1.5, 5.0),
                risk="low",
                reversibility="reversible",
                blast_radius="writes only under command-center/brainstorm/bp-brn-01/**; peers run in their own vendor sandbox with an explicitly set policy",
                confidence="likely",
            ),
            "portability": B.portability_block(
                "command-center/export/bp-brn-01.bundle.json"
            ),
            "lineage": B.lineage_block(
                [
                    {
                        "source": "07f465f3:.agents/skills/codex-brainstorm",
                        "relation": "REPAIR",
                        "license": "owner-proprietary",
                        "credit": "owner (undeployed skill: the 2-peer fan-out and synthesis shape)",
                    },
                    {
                        "source": "07f465f3:.agents/skills/codex-invoke",
                        "relation": "COMPOSE",
                        "license": "owner-proprietary",
                        "credit": "owner (the canonical scoped dispatch that keeps the call inside the OS argument limit)",
                    },
                    {
                        "source": "rules/common/cross-vendor-dispatch.md",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "measured: three cross-vendor agents produced ZERO artifacts because of the ADAPTER, not the vendor",
                    },
                    {
                        "source": "09-WORKFLOW-BLUEPRINT-LIBRARY.md#BP-BRN-01",
                        "relation": "REBUILD-FROM-SPEC",
                        "credit": "program design corpus",
                    },
                ],
                rollback_to=["07f465f3:.agents/skills/codex-brainstorm"],
            ),
            "outputs": {
                "synthesis": B.artifact(
                    f"{root}/synthesis.json",
                    S("synthesis-candidate"),
                    min_bytes=512,
                    consumers=["command-center/DECISION-LOG.json"],
                ),
                "dispatch-audit": B.artifact(
                    f"{root}/dispatch-audit.json",
                    S("conformance-report"),
                    min_bytes=128,
                    consumers=["synthesise"],
                ),
            },
            "x_extensions": {
                "blueprint_source": B.card("BP-BRN-01", 693),
                "acquisition_route_from_card": "REPAIR",
                "mechanism_signature": [
                    "prompt-by-file-marshalling",
                    "blocking-dispatch-never-backgrounded",
                    "three-signal-and-gate",
                    "receipt-string-rejection",
                    "class-specific-single-retry-repair-loop",
                    "novel-to-one-peer-synthesis",
                ],
                "contraindications": [
                    "NOT when the answer needs repo grounding: the peers are fresh-context by design",
                    "NOT for a decision - that is a council",
                    "NOT when the question is already well-specified enough to just answer",
                ],
                "the_measured_adapter_failure": (
                    "Three cross-vendor agents once produced ZERO production artifacts against sixteen "
                    "files, and the vendor's coding quality was never actually exercised - the failure "
                    "was entirely in the ADAPTER. Hence: prompt by file (an inline prompt exceeded the "
                    "OS command-line limit and killed both real attempts), blocking dispatch (a "
                    "backgrounded job's result is unreachable because its record carries no session "
                    "id), and an AND-gate (one agent forwarded a progress stream as its terminal answer "
                    "while its own job record still read running)."
                ),
                "unverified": [
                    "UNVERIFIED post-repair; settling experiment = five dispatches requiring five "
                    "non-empty schema-valid output files, and one deliberately oversized prompt that "
                    "must succeed via the file route.",
                ],
                "worked_example": {
                    "name": "two-peer idea fan-out on a harness design question",
                    "params": {
                        "prompt": "Enumerate mechanisms that would make an agent completion claim falsifiable without adding a new runtime.",
                        "n_peers": 2,
                        "peer_models": ["gpt-5-codex", "gpt-5-codex-mini"],
                        "dispatch_timeout_seconds": 1800,
                    },
                    "expected_stage_order": [
                        "marshal-prompt",
                        "dispatch-peers",
                        "audit-dispatch",
                        "and-gate",
                        "repair-dispatch",
                        "independence-gate",
                        "synthesise",
                    ],
                    "expected_skipped": [],
                    "expected_max_parallel": 4,
                    "expected_gate_ids": [
                        "and-gate",
                        "verify-dispatch",
                        "independence-gate",
                    ],
                    "expected_repair_targets": ["dispatch-peers"],
                    "acceptance": [
                        "a prompt above the OS command-line limit succeeds via the file route",
                        "a killed peer produces a terminal FAILED marker, never silence",
                        "exit zero with an empty output file is SEVERED, not SUCCESS",
                        "an idea produced by exactly one peer lands in novel-to-one-peer",
                    ],
                    "stopping_rule_controls": [
                        {
                            "rule": "all-peers-terminal",
                            "why": "the floor keeps a single-peer run from reading as a completed two-peer fan-out",
                            "fires_on": {
                                "peers_returning_terminal_state": 2,
                                "peer_results_total": 2,
                                "peers_with_success_verdict": 2,
                            },
                            "does_not_fire_on": {
                                "peers_returning_terminal_state": 1,
                                "peer_results_total": 1,
                                "peers_with_success_verdict": 1,
                            },
                        },
                        {
                            "rule": "independence-lost",
                            "why": "one surviving peer is not consensus and the run must say so rather than present it as agreement",
                            "fires_on": {
                                "peers_returning_terminal_state": 2,
                                "peer_results_total": 2,
                                "peers_with_success_verdict": 1,
                            },
                            "does_not_fire_on": {
                                "peers_returning_terminal_state": 2,
                                "peer_results_total": 2,
                                "peers_with_success_verdict": 2,
                            },
                        },
                    ],
                },
            },
        }
    )


def blueprints() -> list[dict[str, Any]]:
    return [_gem05(), _brn01()]
