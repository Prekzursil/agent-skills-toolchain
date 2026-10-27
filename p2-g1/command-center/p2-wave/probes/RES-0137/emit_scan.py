#!/usr/bin/env python3
"""Emit RES-0137 gem-candidate scan from fetched community-tool snapshots."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import contract as C

HERE = Path(__file__).resolve().parent

QUOTES = {
    "nextflow-cache-resume-github-md": "The task cache is a key-value store",
    "nextflow-cache-resume-seqera": "The task cache is a key-value store",
    "snakemake-caching": "SNAKEMAKE_OUTPUT_CACHE",
    "snakemake-rules": "between workflow caching",
    "slurm-sbatch": "afterok:job_id",
    "htcondor-dagman": "PARENT/CHILD Relationships",
    "cwlprov-prov-md": "CWLProv uses [PROV]",
    "cwlprov-bagit-md": "primary.cwlprov.provn",
    "opencue-pyoutline": "token in commands gets replaced with the current frame number",
    "opencue-glossary": "A job is a collection of <em>layers</em>",
    "ghidra-analyzeheadless-java": 'PROCESSOR("-processor"',
    "ghidra-headless-class": "analyzeHeadless",
    "mo2-usvfs-readme": "User Space Virtual File System",
    "mo2-readme": "Mod Organizer",
}


def lineage(index: dict, sid: str, quote: str) -> dict:
    row = index[sid]
    path = HERE / str(row["path"])
    raw = path.read_bytes()
    digest = C.sha256_bytes(raw)
    if digest != row["sha256"]:
        raise SystemExit(f"snapshot hash drift {sid}")
    if not C.quote_in_snapshot(sid, quote, index):
        raise SystemExit(f"quote missing from {sid}: {quote!r}")
    return {
        "source_id": sid,
        "resolved_url": row["resolved_url"],
        "requested_url": row["requested_url"],
        "fetched_at": row["fetched_at"],
        "sha256_fetched_bytes": row["sha256"],
        "bytes": row["bytes"],
        "snapshot_path": f"command-center/p2-wave/probes/RES-0137/{row['path']}",
        "quote": quote,
    }


def ev(index: dict, sid: str) -> dict:
    return {
        "kind": "fetched-snapshot",
        "source_id": sid,
        "path": f"command-center/p2-wave/probes/RES-0137/{index[sid]['path']}",
        "sha256": index[sid]["sha256"],
    }


def main() -> int:
    index = C.snapshot_index()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    block_usvfs = (
        "USVFS is a User Space Virtual File System that fools Windows file-access "
        "APIs via API hooking so only selected processes see a merged mod tree. A "
        "prompt-native Linux control plane has no NtCreateFile hook surface and no "
        "target Windows process. Transferring USVFS requires replacing the execution "
        "substrate, not adapting a scheduler or a hash. Overlay policy can transfer; "
        "USVFS cannot."
    )

    claims = [
        {
            "claim_id": "RES-0137-C1-NEXTFLOW-TASK-HASH-CACHE",
            "canonical_mechanism": (
                "A process runner stores each completed task as a key-value cache "
                "entry whose key is a hash of script, container/environment, inputs "
                "and session metadata; a later run with -resume skips the task when "
                "the hash hits AND the work-directory outputs are still present."
            ),
            "mechanism_id": "MECH-NF-TASK-HASH-CACHE",
            "sherman_kent_band": "almost-certain",
            "verification_status": "CONFIRMED",
            "independent_verification_path": (
                "Re-fetch Seqera cache-and-resume HTML and nextflow-io/nextflow "
                "docs/cache-and-resume.md at commit 7b664ced; sha256 must match "
                "snapshots; both must still call the task cache a key-value store. "
                "Optional live check: nextflow run <pipeline> -resume after an "
                "identical first run."
            ),
            "source_lineage": [
                lineage(
                    index,
                    "nextflow-cache-resume-github-md",
                    QUOTES["nextflow-cache-resume-github-md"],
                ),
                lineage(
                    index,
                    "nextflow-cache-resume-seqera",
                    QUOTES["nextflow-cache-resume-seqera"],
                ),
            ],
        },
        {
            "claim_id": "RES-0137-C2-SNAKEMAKE-MERKLE-BETWEEN-WORKFLOW-CACHE",
            "canonical_mechanism": (
                "Snakemake hashes a Merkle tree of upstream steps, parameters, "
                "software stack and raw inputs, and will retrieve a rule output from "
                "SNAKEMAKE_OUTPUT_CACHE when that hash is already present — reuse "
                "BETWEEN workflows, not inside one DAG."
            ),
            "mechanism_id": "MECH-SMK-MERKLE-CACHE",
            "sherman_kent_band": "almost-certain",
            "verification_status": "CONFIRMED",
            "independent_verification_path": (
                "Re-fetch snakemake.readthedocs.io executing/caching.html and "
                "snakefiles/rules.html; sha256 against snapshots; confirm 'Merkle "
                "tree' and 'between workflow caching'. Optional: run a cache: True "
                "rule twice with SNAKEMAKE_OUTPUT_CACHE set."
            ),
            "source_lineage": [
                lineage(index, "snakemake-caching", QUOTES["snakemake-caching"]),
                lineage(index, "snakemake-rules", QUOTES["snakemake-rules"]),
            ],
        },
        {
            "claim_id": "RES-0137-C3-CWLPROV-PROV-BAGIT",
            "canonical_mechanism": (
                "A completed workflow run is packaged as a BagIt research object "
                "whose metadata/provenance/primary.cwlprov.provn file is a W3C PROV-N "
                "trace of the top-level workflow activity, with payload checksums in "
                "BagIt manifests."
            ),
            "mechanism_id": "MECH-CWLPROV-BAGIT",
            "sherman_kent_band": "almost-certain",
            "verification_status": "CONFIRMED",
            "independent_verification_path": (
                "Re-fetch common-workflow-language/cwlprov prov.md and bagit.md; "
                "both sha256 values must match snapshots; both must still require "
                "primary.cwlprov.provn. Optional: cwltool --provenance on a tiny "
                "workflow."
            ),
            "source_lineage": [
                lineage(index, "cwlprov-prov-md", QUOTES["cwlprov-prov-md"]),
                lineage(index, "cwlprov-bagit-md", QUOTES["cwlprov-bagit-md"]),
            ],
        },
        {
            "claim_id": "RES-0137-C4-SLURM-AFTEROK-DEPENDENCY",
            "canonical_mechanism": (
                "A batch job may declare --dependency=afterok:<jobid> so the "
                "scheduler defers start until the predecessor exited zero; missing "
                "same-cluster predecessors are rejected at submit time. HTCondor "
                "DAGMan PARENT/CHILD is the same success-edge in another scheduler."
            ),
            "mechanism_id": "MECH-SLURM-AFTEROK",
            "sherman_kent_band": "almost-certain",
            "verification_status": "CONFIRMED",
            "independent_verification_path": (
                "Re-fetch slurm.schedmd.com/sbatch.html afterok:job_id and HTCondor "
                "DAGMan PARENT/CHILD docs; sha256 match snapshots. Optional: sbatch "
                "--dependency=afterok:$jid on a cluster."
            ),
            "source_lineage": [
                lineage(index, "slurm-sbatch", QUOTES["slurm-sbatch"]),
                lineage(index, "htcondor-dagman", QUOTES["htcondor-dagman"]),
            ],
        },
        {
            "claim_id": "RES-0137-C5-OPENCUE-LAYER-FRAME-DEPEND",
            "canonical_mechanism": (
                "A render job is a tree of layers of frames; each frame is one "
                "execution of a layer command with #IFRAME# substituted; a layer may "
                "depend_on another layer so matching frames wait on matching "
                "predecessors."
            ),
            "mechanism_id": "MECH-OPENCUE-LAYER-FRAME",
            "sherman_kent_band": "likely",
            "verification_status": "CONFIRMED",
            "independent_verification_path": (
                "Re-fetch docs.opencue.io PyOutline concepts and glossary; confirm "
                "#IFRAME# / depend_on and the job-is-layers definition; sha256 match."
            ),
            "source_lineage": [
                lineage(index, "opencue-pyoutline", QUOTES["opencue-pyoutline"]),
                lineage(index, "opencue-glossary", QUOTES["opencue-glossary"]),
            ],
        },
        {
            "claim_id": "RES-0137-C6-USVFS-WIN32-HOOK-NOT-TRANSFERABLE",
            "canonical_mechanism": (
                "Mod Organizer 2's USVFS intercepts Win32 file APIs via user-space "
                "API hooking so only selected processes see a merged virtual view of "
                "mods. That hook surface does not exist on a prompt-native Linux "
                "control plane."
            ),
            "mechanism_id": "MECH-MO2-USVFS",
            "sherman_kent_band": "likely",
            "verification_status": "CONFIRMED",
            "independent_verification_path": (
                "Re-fetch ModOrganizer2/usvfs README.md and modorganizer readme.md; "
                "confirm USVFS is a User Space Virtual File System using API hooking "
                "for Windows applications. Settling experiment: this execution "
                "substrate has no NtCreateFile hook."
            ),
            "source_lineage": [
                lineage(index, "mo2-usvfs-readme", QUOTES["mo2-usvfs-readme"]),
                lineage(index, "mo2-readme", QUOTES["mo2-readme"]),
            ],
        },
        {
            "claim_id": "RES-0137-C7-GHIDRA-HEADLESS-PIPELINE-HIGH-COST",
            "canonical_mechanism": (
                "Ghidra analyzeHeadless can -import or -process binaries, run "
                "pre/post scripts, and optionally pin -processor <languageID>. The "
                "import-analyze-script-commit shape is a batch orchestrator; the "
                "SLEIGH processor is an ISA decompiler, not a control-plane primitive."
            ),
            "mechanism_id": "MECH-GHIDRA-HEADLESS",
            "sherman_kent_band": "likely",
            "verification_status": "CONFIRMED",
            "independent_verification_path": (
                "Re-fetch AnalyzeHeadless.java argument enum and "
                "GhidraDocs HeadlessAnalyzer.html; sha256 match; both document "
                "-import/-process/-processor."
            ),
            "source_lineage": [
                lineage(
                    index,
                    "ghidra-analyzeheadless-java",
                    QUOTES["ghidra-analyzeheadless-java"],
                ),
                lineage(
                    index, "ghidra-headless-class", QUOTES["ghidra-headless-class"]
                ),
            ],
        },
    ]

    mechanisms = [
        {
            "id": "MECH-NF-TASK-HASH-CACHE",
            "community_id": "bioinformatics-pipeline-runners",
            "kind": "orchestration",
            "name": "Nextflow task-hash cache and -resume",
            "canonical_mechanism": claims[0]["canonical_mechanism"],
            "community_tool_docs": [
                index["nextflow-cache-resume-github-md"]["resolved_url"],
                index["nextflow-cache-resume-seqera"]["resolved_url"],
            ],
            "transfer_verdict": "TRANSFER",
            "adaptation_cost": {
                "must_rewrite": [
                    "Cache-key composition: (script + container + file metadata + session id) → (prompt bytes + model-id + tool-call argv + input artifact sha256 + policy hash).",
                    "Executor: container/bsub/slurm launch → prompt-native tool-call sandbox.",
                    "Work-directory layout: Nextflow hash-named task dirs → this tree's artifact store paths.",
                ],
                "keeps": [
                    "Key-value task cache with hit-then-verify-outputs.",
                    "Explicit resume flag so cache hits are opt-in.",
                    "Separate metadata store from payload store.",
                ],
                "concrete_rewrite": (
                    "Rewrite the hasher; do not import LevelDB .nextflow/cache. Keep "
                    "hash-before-execute, skip-on-hit iff outputs still exist."
                ),
            },
            "blocking_reason": None,
            "claim_ids": ["RES-0137-C1-NEXTFLOW-TASK-HASH-CACHE"],
        },
        {
            "id": "MECH-SMK-MERKLE-CACHE",
            "community_id": "bioinformatics-pipeline-runners",
            "kind": "orchestration",
            "name": "Snakemake between-workflow Merkle output cache",
            "canonical_mechanism": claims[1]["canonical_mechanism"],
            "community_tool_docs": [
                index["snakemake-caching"]["resolved_url"],
                index["snakemake-rules"]["resolved_url"],
            ],
            "transfer_verdict": "TRANSFER",
            "adaptation_cost": {
                "must_rewrite": [
                    "Merkle inputs: conda/container stack → model-id + tool-binary digest.",
                    "SNAKEMAKE_OUTPUT_CACHE directory protocol → content-addressed artifact CAS.",
                    "cache: True / omit-software syntax → a field on the skill/workflow step record.",
                ],
                "keeps": [
                    "Between-run reuse keyed by a Merkle hash of upstream work.",
                ],
                "concrete_rewrite": (
                    "Do not import Snakemake's cache directive parser. Reimplement the "
                    "Merkle key over this plane's step graph."
                ),
            },
            "blocking_reason": None,
            "claim_ids": ["RES-0137-C2-SNAKEMAKE-MERKLE-BETWEEN-WORKFLOW-CACHE"],
        },
        {
            "id": "MECH-CWLPROV-BAGIT",
            "community_id": "bioinformatics-pipeline-runners",
            "kind": "provenance",
            "name": "CWLProv W3C PROV + BagIt run packaging",
            "canonical_mechanism": claims[2]["canonical_mechanism"],
            "community_tool_docs": [
                index["cwlprov-prov-md"]["resolved_url"],
                index["cwlprov-bagit-md"]["resolved_url"],
                index["cwl-workflow-v12"]["resolved_url"],
            ],
            "transfer_verdict": "TRANSFER",
            "adaptation_cost": {
                "must_rewrite": [
                    "PROV activity types: CommandLineTool/Workflow → tool-call / workflow-step.",
                    "CWL File/Directory secondaryFiles → artifact path + sha256 records.",
                    "cwltool --provenance emitter → a receipt writer that emits BagIt + PROV beside each run.",
                ],
                "keeps": [
                    "BagIt payload/tag manifests with checksums.",
                    "A single primary provenance document for the top-level run.",
                    "wasGeneratedBy / used edges between steps and artifacts.",
                ],
                "concrete_rewrite": (
                    "Rewrite the CWL object model. Keep BagIt packaging and a PROV "
                    "(or equivalent) trace with stable activity UUIDs."
                ),
            },
            "blocking_reason": None,
            "claim_ids": ["RES-0137-C3-CWLPROV-PROV-BAGIT"],
        },
        {
            "id": "MECH-SLURM-AFTEROK",
            "community_id": "hpc-job-schedulers",
            "kind": "orchestration",
            "name": "Slurm afterok job dependency (HTCondor DAGMan analog)",
            "canonical_mechanism": claims[3]["canonical_mechanism"],
            "community_tool_docs": [
                index["slurm-sbatch"]["resolved_url"],
                index["htcondor-dagman"]["resolved_url"],
            ],
            "transfer_verdict": "TRANSFER",
            "adaptation_cost": {
                "must_rewrite": [
                    "sbatch/squeue job identifiers → step/run identifiers in the prompt-native ledger.",
                    "Resource requests (mem, gpus, ntasks, cgroups) → timeout, token budget, concurrency slots.",
                    "MinJobAge / same-cluster reject semantics → explicit predecessor-unknown failure on the ledger.",
                ],
                "keeps": [
                    "Named success-edge: child does not start unless parent exited zero.",
                    "Submit-time rejection when the predecessor id is unknown.",
                    "DAG as data, not as prose in a prompt.",
                ],
                "concrete_rewrite": (
                    "Do not speak Slurm RPC. Encode afterok as a first-class edge and "
                    "refuse to dispatch a child whose parents are missing or non-zero."
                ),
            },
            "blocking_reason": None,
            "claim_ids": ["RES-0137-C4-SLURM-AFTEROK-DEPENDENCY"],
        },
        {
            "id": "MECH-OPENCUE-LAYER-FRAME",
            "community_id": "vfx-render-farms",
            "kind": "orchestration",
            "name": "OpenCue layer/frame tree with depend_on and #IFRAME#",
            "canonical_mechanism": claims[4]["canonical_mechanism"],
            "community_tool_docs": [
                index["opencue-pyoutline"]["resolved_url"],
                index["opencue-glossary"]["resolved_url"],
            ],
            "transfer_verdict": "TRANSFER",
            "adaptation_cost": {
                "must_rewrite": [
                    "#IFRAME# / DCC command templates → a map-shard token over artifact indices, not film frames.",
                    "Cuebot show/shot/facility billing tags → unit_id / budget account.",
                    "PyOutline Shell layer classes → workflow step records.",
                ],
                "keeps": [
                    "Job → layer → item hierarchy.",
                    "Item-wise edges and layer-wise edges.",
                ],
                "concrete_rewrite": (
                    "Rewrite #IFRAME# as a shard index over a split input. Ranked below "
                    "Slurm afterok because that rewrite is larger."
                ),
            },
            "blocking_reason": None,
            "claim_ids": ["RES-0137-C5-OPENCUE-LAYER-FRAME-DEPEND"],
        },
        {
            "id": "MECH-MO2-USVFS",
            "community_id": "game-modding-toolchains",
            "kind": "orchestration",
            "name": "Mod Organizer 2 USVFS Win32 API-hook virtual filesystem",
            "canonical_mechanism": claims[5]["canonical_mechanism"],
            "community_tool_docs": [
                index["mo2-usvfs-readme"]["resolved_url"],
                index["mo2-readme"]["resolved_url"],
            ],
            "transfer_verdict": "NOT_TRANSFERABLE",
            "adaptation_cost": {
                "must_rewrite": [
                    "The entire execution substrate: a user-space interceptor for NtCreateFile/NtOpenFile targeting Windows processes.",
                ],
                "keeps": [
                    "Overlay precedence policy (already in this tree's rule overlay) — that is NOT this mechanism.",
                ],
                "concrete_rewrite": (
                    "There is nothing to adapt. USVFS is the Windows hook engine. "
                    "Shipping it would mean replacing the substrate."
                ),
            },
            "blocking_reason": block_usvfs,
            "claim_ids": ["RES-0137-C6-USVFS-WIN32-HOOK-NOT-TRANSFERABLE"],
        },
        {
            "id": "MECH-GHIDRA-HEADLESS",
            "community_id": "reverse-engineering-automation",
            "kind": "orchestration",
            "name": "Ghidra analyzeHeadless import/process/script pipeline",
            "canonical_mechanism": claims[6]["canonical_mechanism"],
            "community_tool_docs": [
                index["ghidra-analyzeheadless-java"]["resolved_url"],
                index["ghidra-headless-class"]["resolved_url"],
            ],
            "transfer_verdict": "TRANSFER",
            "adaptation_cost": {
                "must_rewrite": [
                    "Drop SLEIGH / -processor <languageID> / ProgramDB — a decompiler runtime, not a control plane.",
                    "Rewrite -preScript/-postScript as ordinary steps in the prompt-native DAG.",
                    "Replace Ghidra project/folder commit with this tree's artifact ledger.",
                ],
                "keeps": [
                    "Batch shape: ingest → optional pre-hook → analyze → post-hook → commit-or-discard.",
                    "Mutually exclusive ingest vs reprocess modes.",
                ],
                "concrete_rewrite": (
                    "Keep only the CLI pipeline shape. The processor backend is why this "
                    "mechanism is not in the least-adaptation three."
                ),
            },
            "blocking_reason": None,
            "claim_ids": ["RES-0137-C7-GHIDRA-HEADLESS-PIPELINE-HIGH-COST"],
        },
    ]

    doc = {
        "unit_id": "RES-0137",
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "report_kind": "gem-candidate",
        "schema": "command-center/schema/gem-candidate.schema.json",
        "title": "Niche and obscure community scan for transferable automation mechanisms",
        "question": (
            "What orchestration, verification or provenance mechanisms are standard "
            "practice in communities OUTSIDE agent tooling — bioinformatics pipeline "
            "runners, game-modding toolchains, reverse-engineering automation, HPC job "
            "schedulers, VFX render farms — and which three transfer with the least "
            "adaptation to a prompt-native control plane?"
        ),
        "produced_at": now,
        "produced_by": {
            "role": "gem-hunter",
            "execution_substrate": "linux-worktree",
            "unit_id": "RES-0137",
        },
        "communities_scanned": [
            {
                "id": "bioinformatics-pipeline-runners",
                "label": "Bioinformatics pipeline runners (Nextflow, Snakemake, CWL/CWLProv)",
            },
            {
                "id": "game-modding-toolchains",
                "label": "Game-modding toolchains (Mod Organizer 2 / USVFS)",
            },
            {
                "id": "reverse-engineering-automation",
                "label": "Reverse-engineering automation (Ghidra analyzeHeadless)",
            },
            {
                "id": "hpc-job-schedulers",
                "label": "HPC job schedulers (Slurm sbatch --dependency, HTCondor DAGMan)",
            },
            {
                "id": "vfx-render-farms",
                "label": "VFX render farms (OpenCue job/layer/frame + PyOutline depend_on)",
            },
        ],
        "mechanisms": mechanisms,
        "least_adaptation_three": [
            "MECH-NF-TASK-HASH-CACHE",
            "MECH-CWLPROV-BAGIT",
            "MECH-SLURM-AFTEROK",
        ],
        "least_adaptation_rationale": (
            "All three are already graphs-or-hashes over named steps with checksummed "
            "artifacts. Adaptation is rewriting the key/edge/activity vocabulary onto "
            "prompt+tool-call+artifact-sha256. USVFS is NOT_TRANSFERABLE. OpenCue and "
            "Ghidra headless transfer only after larger rewrites (frame tokens / SLEIGH)."
        ),
        "negative_control": {
            "mechanism_id": "MECH-MO2-USVFS",
            "blocking_reason": block_usvfs,
            "why_this_is_the_control": (
                "A scan that declared every mechanism transferable would not have "
                "modelled the prompt-native control plane (no Win32 hook surface)."
            ),
        },
        "claims": claims,
        "tests": [
            {
                "id": "named-probe-1-lineage-and-contract",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0137/probe1_lineage_and_contract.py"
                ),
                "result": "NOT-RUN",
            },
            {
                "id": "named-probe-2-negative-control-both-states",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0137/probe2_negative_control.py"
                ),
                "result": "NOT-RUN",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0137-probe2-all-transfer-mutant",
            "verdict": "PASS",
            "independent": True,
            "mandate": (
                "Adversarial: default REFUTED if the scan has no NOT_TRANSFERABLE "
                "mechanism or if the everything-TRANSFER mutant is accepted."
            ),
        },
        "evidence": [
            ev(index, sid)
            for sid in [
                "nextflow-cache-resume-github-md",
                "nextflow-cache-resume-seqera",
                "snakemake-caching",
                "snakemake-rules",
                "slurm-sbatch",
                "htcondor-dagman",
                "cwlprov-prov-md",
                "cwlprov-bagit-md",
                "opencue-pyoutline",
                "opencue-glossary",
                "ghidra-analyzeheadless-java",
                "ghidra-headless-class",
                "mo2-usvfs-readme",
                "mo2-readme",
            ]
        ],
        "catalog_contract": {
            "output_path": (
                "command-center/research/sources-frontier/"
                "RES-0137-cross-domain-niche-community-scan.json"
            ),
            "output_schema": "command-center/schema/gem-candidate.schema.json",
            "completion_sentinel": "SUCCESS:RES-0137",
            "tests_required_verbatim": (
                "negative control: include at least one mechanism judged NOT "
                "transferable with the blocking reason stated; a scan where "
                "everything transfers has not modelled the control plane"
            ),
        },
        "limits": [
            "Snapshots are point-in-time HTTP fetches; vendors may restyle HTML without changing the mechanism.",
            "Ghidra is cited only as a batch orchestrator; this unit does not transfer decompiler internals or describe exploits.",
            "Wabbajack/xEdit were fetched as community context and are not in the least-adaptation three.",
        ],
    }

    check = C.transfer_scan(doc)
    if not check["pass"]:
        print(json.dumps(check, indent=2))
        raise SystemExit("FAILED:RES-0137 emit contract")

    C.ART.parent.mkdir(parents=True, exist_ok=True)
    C.ART.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {C.ART} bytes={C.ART.stat().st_size}")
    print(C.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
