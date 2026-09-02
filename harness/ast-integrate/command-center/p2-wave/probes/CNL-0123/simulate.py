"""Run every CNL-0123 fixture through honest fan-in and the vote-count control."""
from __future__ import annotations

import hashlib
from pathlib import Path

from fanin import DISAGREEMENT, PASS, fan_in, recount, vote_count_parent
from scenario import ALL_PASS, MISSING, SPLIT, load_fixture, repo_read

HERE = Path(__file__).resolve().parent

NEGATIVE_CONTROL_VERBATIM = (
    "NEGATIVE CONTROL (evidence-blind parent): On the vote-counting parent that "
    "hashes only child verdict labels, perturbing child EVIDENCE while holding "
    "the three verdicts fixed (2 PASS, 1 REFUTED) leaves the parent digest "
    "unchanged and the parent still emits PASS (majority of labels). The check "
    "is meant to reject that parent: it MUST report evidence_blind=true and "
    "must NOT treat majority-PASS as the declared outcome. Observed on the "
    "planted vote-counter: digest_moved=false, parent_verdict=PASS."
)

PERTURBED_GAMMA = HERE / "fixtures/perturbed_split/evidence/gamma.json"


def overlay_read(overrides: dict[str, bytes]):
    def read(rel: str) -> bytes | None:
        key = str(rel).replace("\\", "/")
        if key in overrides:
            return overrides[key]
        return repo_read(rel)

    return read


def run_all() -> dict:
    split = load_fixture(SPLIT)
    all_pass = load_fixture(ALL_PASS)
    missing = load_fixture(MISSING)

    gamma_rel = next(
        str(c["evidence_path"]).replace("\\", "/")
        for c in split["children"]
        if c["id"] == "child-gamma"
    )
    perturbed_raw = PERTURBED_GAMMA.read_bytes()
    perturbed_digest = hashlib.sha256(perturbed_raw.replace(b"\r\n", b"\n")).hexdigest()

    pert_children = []
    for child in split["children"]:
        row = dict(child)
        if row["id"] == "child-gamma":
            row["digest"] = perturbed_digest
        pert_children.append(row)

    split_parent = fan_in(split["children"], repo_read, parent_id="parent")
    all_parent = fan_in(all_pass["children"], repo_read, parent_id="parent")
    miss_parent = fan_in(missing["children"], repo_read, parent_id="parent")
    pert_parent = fan_in(
        pert_children,
        overlay_read({gamma_rel: perturbed_raw}),
        parent_id="parent",
    )
    vote_split = vote_count_parent(split["children"], parent_id="vote-counter")
    vote_pert = vote_count_parent(pert_children, parent_id="vote-counter")

    split_labels = [c["verdict"] for c in split["children"]]
    pert_labels = [c["verdict"] for c in pert_children]
    honest_moved = split_parent["parent_digest"] != pert_parent["parent_digest"]
    vote_moved = vote_split["parent_digest"] != vote_pert["parent_digest"]
    evidence_blind = (not vote_moved) and vote_split["verdict"] == PASS

    split_paths = [c["evidence_path"] for c in split["children"]]
    pert_paths = [c["evidence_path"] for c in pert_children]

    return {
        "split_fixture_id": split["id"],
        "split_labels": split_labels,
        "perturbed_labels": pert_labels,
        "labels_held_fixed": split_labels == pert_labels,
        "paths_held_fixed": split_paths == pert_paths,
        "split": split_parent,
        "all_pass": all_parent,
        "missing": miss_parent,
        "perturbed": pert_parent,
        "vote_split": vote_split,
        "vote_perturbed": vote_pert,
        "split_recount": recount(split_parent),
        "honest_digest_moved": honest_moved,
        "vote_digest_moved": vote_moved,
        "evidence_blind_control_fired": evidence_blind,
        "majority_of_split_labels": split_parent["majority_of_labels"],
        "negative_control_verbatim": NEGATIVE_CONTROL_VERBATIM,
        "declared_parent_verdict": DISAGREEMENT,
        "rejected_parent_verdict": PASS,
    }
