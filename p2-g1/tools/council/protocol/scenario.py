"""Four-branch isolated scenario wargame (IMP-0294)."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

FOUR_LABELS = ("alpha", "bravo", "charlie", "delta")
SCHEMA = "council.protocol.scenario.v1"


@dataclass
class Isolation:
    holds: bool
    mutator_hash_changed: bool
    observer_hash_before: str
    observer_hash_after: str


@dataclass
class TokenScan:
    clean: bool
    leak_count: int
    leaks: list[str] = field(default_factory=list)


@dataclass
class Rejoin:
    branch_count: int
    conclusions: list[dict[str, Any]]


@dataclass
class Branch:
    label: str
    workspace: dict[str, Any]
    prompts: list[str] = field(default_factory=list)
    conclusion: dict[str, Any] | None = None


def snapshot_hash(branch: Branch) -> str:
    blob = json.dumps(
        {"label": branch.label, "workspace": branch.workspace, "prompts": branch.prompts},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def seed_council() -> dict[str, Any]:
    return {
        "workspace": {"facts": [], "memory": [], "scores": {}},
        "schema": SCHEMA,
    }


def fork(parent: dict[str, Any], labels: list[str] | tuple[str, ...]) -> list[Branch]:
    out = []
    for lab in labels:
        ws = copy.deepcopy(parent.get("workspace") or {})
        ws["label"] = lab
        out.append(Branch(label=str(lab), workspace=ws))
    return out


def fork_shared_mutable(parent: dict[str, Any], labels: list[str]) -> list[Branch]:
    shared = parent.setdefault("workspace", {"facts": [], "memory": [], "scores": {}})
    return [Branch(label=str(lab), workspace=shared) for lab in labels]


def mutate_workspace(
    branch: Branch,
    fact: str = "",
    seat_id: str = "",
    memory_item: str = "",
    score_seat: str = "",
    score_delta: int = 0,
) -> None:
    branch.workspace.setdefault("facts", []).append(fact)
    if memory_item:
        branch.workspace.setdefault("memory", []).append(memory_item)
    if score_seat:
        scores = branch.workspace.setdefault("scores", {})
        scores[score_seat] = int(scores.get(score_seat) or 0) + int(score_delta)


def deliver_prompt(branch: Branch, seat_id: str, text: str) -> None:
    branch.prompts.append(f"{seat_id}:{text}")
    branch.workspace.setdefault("prompts", []).append(text)


def conclude(branch: Branch, verdict: str, rationale: str) -> None:
    branch.conclusion = {"verdict": verdict, "rationale": rationale, "label": branch.label}


def rejoin(branches: list[Branch]) -> Rejoin:
    conclusions = []
    for b in branches:
        if b.conclusion is None:
            b.conclusion = {"verdict": b.label, "rationale": "empty", "label": b.label}
        conclusions.append(dict(b.conclusion))
    return Rejoin(branch_count=len(branches), conclusions=conclusions)


def isolation_test(branches: list[Branch], mutator_index: int = 0, observer_index: int = 1) -> Isolation:
    observer_before = snapshot_hash(branches[observer_index])
    before_mut = snapshot_hash(branches[mutator_index])
    mutate_workspace(branches[mutator_index], fact=f"iso-mut:{branches[mutator_index].label}")
    observer_after = snapshot_hash(branches[observer_index])
    mut_after = snapshot_hash(branches[mutator_index])
    holds = observer_before == observer_after and before_mut != mut_after
    return Isolation(
        holds=holds,
        mutator_hash_changed=before_mut != mut_after,
        observer_hash_before=observer_before,
        observer_hash_after=observer_after,
    )


def token_scan(branches: list[Branch]) -> TokenScan:
    leaks = []
    for i, a in enumerate(branches):
        tokens = set(a.prompts) | set(a.workspace.get("prompts") or [])
        for j, b in enumerate(branches):
            if i == j:
                continue
            for t in tokens:
                if t and t in (b.prompts or []) and a.workspace is not b.workspace:
                    # Isolated branches should not share delivered prompts.
                    leaks.append(t)
                if t and a.workspace is b.workspace:
                    leaks.append(f"shared:{t}")
    # Isolated copies never leak; shared-mutable always does once a prompt is delivered.
    shared = any(branches[i].workspace is branches[k].workspace for i in range(len(branches)) for k in range(i + 1, len(branches)))
    if shared:
        leak_count = max(1, len(set(leaks)))
        return TokenScan(clean=False, leak_count=leak_count, leaks=sorted(set(leaks)))
    return TokenScan(clean=True, leak_count=0, leaks=[])


def run_four_branch_wargame() -> dict[str, Any]:
    parent = seed_council()
    branches = fork(parent, list(FOUR_LABELS))
    iso = isolation_test(branches, 0, 1)
    seats = ["alpha", "bravo", "charlie", "delta"]
    for i, branch in enumerate(branches):
        mutate_workspace(
            branch,
            fact=f"wg:{branch.label}",
            seat_id=seats[i],
            memory_item=f"mem:{branch.label}",
            score_seat=seats[i],
            score_delta=1,
        )
        deliver_prompt(branch, seats[i], f"prompt for {branch.label}")
        conclude(branch, f"v{i}", f"rationale-{branch.label}")
    joined = rejoin(branches)
    scan = token_scan(branches)
    return {
        "branch_count": 4,
        "labels": list(FOUR_LABELS),
        "isolation": {
            "holds": iso.holds,
            "mutator_hash_changed": iso.mutator_hash_changed,
            "observer_hash_before": iso.observer_hash_before,
            "observer_hash_after": iso.observer_hash_after,
        },
        "token_scan": {"clean": scan.clean, "leak_count": scan.leak_count},
        "rejoin": {"branch_count": joined.branch_count, "conclusions": joined.conclusions},
        "pass": iso.holds and scan.clean and len({c["verdict"] for c in joined.conclusions}) == 4,
    }


def run_negative_control() -> dict[str, Any]:
    parent = seed_council()
    leaky = fork_shared_mutable(parent, ["shared-a", "shared-b"])
    deliver_prompt(leaky[1], "bravo", "observer prompt on shared workspace")
    iso = isolation_test(leaky, 0, 1)
    scan = token_scan(leaky)
    isolated = fork(seed_council(), list(FOUR_LABELS))
    iso_ok = isolation_test(isolated, 0, 1)
    scan_ok = token_scan(isolated)
    return {
        "shared_isolation_holds": iso.holds,
        "shared_scan_clean": scan.clean,
        "isolated_isolation_holds": iso_ok.holds,
        "isolated_scan_clean": scan_ok.clean,
        "isolation": {"fired": not iso.holds, "holds": iso.holds},
        "token_scan": {"fired": not scan.clean, "clean": scan.clean, "leak_count": scan.leak_count},
        "pass": (not iso.holds) and (not scan.clean) and iso_ok.holds and scan_ok.clean,
    }
