#!/usr/bin/env python3
"""Candidate gem-hunt lenses and mechanism-level extractors.

Lenses are analytical viewpoints for a wide gem-hunt fan-out (catalog
RES-0137 kinds + RES-0108 rubric + a planted near-duplicate). Each
extractor is a required-phrase conjunction over the shared corpus blob.
"""
from __future__ import annotations

from typing import Any

from corpus import active_docs, blob_of, load_index

# Pre-registered unique-yield threshold. Merge when unique yield is below
# this AND the lens is an exact subset of another, or pairwise Jaccard is
# at/above that lens's seeded self-overlap noise floor.
UNIQUE_YIELD_THRESHOLD = 0.10

LENS_ORDER: tuple[str, ...] = (
    "orchestration",
    "orchestration-synonym",
    "verification",
    "provenance",
    "cost-leverage",
    "irreplaceability",
    "bus-fit",
    "failure-mode",
)

LENS_META: dict[str, dict[str, str]] = {
    "orchestration": {
        "kind": "grounded",
        "role": "extract scheduler, DAG, layer, and workflow-graph mechanisms",
    },
    "orchestration-synonym": {
        "kind": "grounded",
        "role": "planted near-duplicate of orchestration using synonym phrases",
    },
    "verification": {
        "kind": "grounded",
        "role": "extract hash, cache-hit, and output-reuse mechanisms",
    },
    "provenance": {
        "kind": "grounded",
        "role": "extract PROV/BagIt and Merkle lineage mechanisms",
    },
    "cost-leverage": {
        "kind": "ideation",
        "role": "extract high adaptation-cost / rewrite-surface mechanisms",
    },
    "irreplaceability": {
        "kind": "grounded",
        "role": "extract platform-bound or no-maintained-equivalent mechanisms",
    },
    "bus-fit": {
        "kind": "ideation",
        "role": "extract API-hook, process-runner, and scheduler-coupling fit",
    },
    "failure-mode": {
        "kind": "grounded",
        "role": "extract documented failure, fragility, and non-transfer surfaces",
    },
}

# mechanism_id -> (canonical description, required phrases)
# Phrases are matched case-insensitively against the concatenated corpus.
MECHANISMS: dict[str, dict[str, Any]] = {
    "MECH-NF-TASK-HASH-CACHE": {
        "canonical": (
            "Nextflow stores each executed task in a key-value task cache and "
            "recovers it on -resume when the hash hits and work-directory outputs "
            "are still present."
        ),
        "phrases": ("the task cache is a key-value store",),
    },
    "MECH-NF-CACHE-HIT": {
        "canonical": (
            "A Nextflow cache hit does not by itself resume the task; outputs "
            "must still be recovered from the work directory."
        ),
        "phrases": ("a cache hit does not guarantee",),
    },
    "MECH-NF-RESUME-FRAGILITY": {
        "canonical": (
            "Resume fails unless both the task cache and the work directory are "
            "preserved."
        ),
        "phrases": ("preserve both the task cache",),
    },
    "MECH-SMK-MERKLE-CACHE": {
        "canonical": (
            "Snakemake hashes a Merkle tree of upstream steps into "
            "SNAKEMAKE_OUTPUT_CACHE for reuse between workflows."
        ),
        "phrases": ("snakemake_output_cache", "merkle tree"),
    },
    "MECH-CWLPROV-BAGIT": {
        "canonical": (
            "CWLProv packages a run as a BagIt object whose "
            "primary.cwlprov.provn file is a W3C PROV-N trace."
        ),
        "phrases": ("primary.cwlprov.provn", "prov-n"),
    },
    "MECH-SLURM-AFTEROK": {
        "canonical": (
            "Slurm --dependency=afterok:<jobid> defers start until the "
            "predecessor exited successfully."
        ),
        "phrases": ("afterok:job_id",),
    },
    "MECH-HTCONDOR-DAGMAN": {
        "canonical": (
            "HTCondor DAGMan PARENT/CHILD declares success-edges between nodes."
        ),
        "phrases": ("parent/child relationships",),
    },
    "MECH-OPENCUE-LAYER-FRAME": {
        "canonical": (
            "OpenCue substitutes #IFRAME# in a layer command so each frame is "
            "one execution."
        ),
        "phrases": ("#iframe#", "token in commands gets replaced"),
    },
    "MECH-CWL-WORKFLOW": {
        "canonical": "CWL v1.2 documents declare cwlVersion: v1.2 on a Workflow class.",
        "phrases": ("cwlversion: v1.2",),
    },
    "MECH-MO2-USVFS": {
        "canonical": (
            "USVFS is a User Space Virtual File System that uses API hooking to "
            "fool Windows file-access functions."
        ),
        "phrases": ("user space virtual file system", "api hooking"),
    },
    "MECH-GHIDRA-HEADLESS": {
        "canonical": (
            "Ghidra analyzeHeadless is a batch import/process/script runner with "
            "an optional -processor language pin."
        ),
        "phrases": ("analyzeheadless", 'processor("-processor"'),
    },
    "MECH-GHIDRA-PASSWORD-ECHO": {
        "canonical": (
            "analyzeHeadless may echo password text instead of masking it — a "
            "documented failure mode of the headless path."
        ),
        "phrases": ("password text will be echoed",),
    },
    "MECH-XEDIT-AUTOCLEAN": {
        "canonical": (
            "xEdit Quick Auto Clean is a game-plugin cleaning tool with no "
            "agent-orchestration equivalent."
        ),
        "phrases": ("xedit quick auto clean",),
    },
    "MECH-WABBAJACK-REPRO-INSTALL": {
        "canonical": (
            "Wabbajack reproduces a modding setup on another machine without "
            "bundling assets."
        ),
        "phrases": ("automated modlist installer",),
    },
}

# Lens -> mechanism ids it is allowed to report (the question the lens asks).
# Phrase matching still has to fire.
LENS_TARGETS: dict[str, tuple[str, ...]] = {
    "orchestration": (
        "MECH-NF-TASK-HASH-CACHE",
        "MECH-SLURM-AFTEROK",
        "MECH-HTCONDOR-DAGMAN",
        "MECH-OPENCUE-LAYER-FRAME",
        "MECH-CWL-WORKFLOW",
    ),
    "orchestration-synonym": (
        "MECH-NF-TASK-HASH-CACHE",
        "MECH-SLURM-AFTEROK",
        "MECH-HTCONDOR-DAGMAN",
        "MECH-OPENCUE-LAYER-FRAME",
    ),
    "verification": (
        "MECH-NF-CACHE-HIT",
        "MECH-SMK-MERKLE-CACHE",
    ),
    "provenance": (
        "MECH-CWLPROV-BAGIT",
        "MECH-SMK-MERKLE-CACHE",
    ),
    "cost-leverage": (
        "MECH-MO2-USVFS",
        "MECH-GHIDRA-HEADLESS",
        "MECH-OPENCUE-LAYER-FRAME",
    ),
    "irreplaceability": (
        "MECH-MO2-USVFS",
        "MECH-XEDIT-AUTOCLEAN",
        "MECH-WABBAJACK-REPRO-INSTALL",
    ),
    "bus-fit": (
        "MECH-MO2-USVFS",
        "MECH-GHIDRA-HEADLESS",
        "MECH-SLURM-AFTEROK",
    ),
    "failure-mode": (
        "MECH-MO2-USVFS",
        "MECH-GHIDRA-PASSWORD-ECHO",
        "MECH-NF-RESUME-FRAGILITY",
    ),
}


def _fires(blob_lc: str, phrases: tuple[str, ...]) -> bool:
    return all(p.lower() in blob_lc for p in phrases)


def extract_lens(lens_id: str, seed: int | None = None, docs: list[dict] | None = None) -> set[str]:
    if lens_id not in LENS_TARGETS:
        raise KeyError(lens_id)
    rows = docs if docs is not None else load_index()
    blob = blob_of(active_docs(rows, seed)).lower()
    found: set[str] = set()
    for mid in LENS_TARGETS[lens_id]:
        spec = MECHANISMS[mid]
        if _fires(blob, spec["phrases"]):
            found.add(mid)
    return found


def extract_all(seed: int | None = None, docs: list[dict] | None = None) -> dict[str, list[str]]:
    rows = docs if docs is not None else load_index()
    out: dict[str, list[str]] = {}
    for lid in LENS_ORDER:
        found = sorted(extract_lens(lid, seed=seed, docs=rows))
        out[lid] = found
    return out
