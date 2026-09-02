#!/usr/bin/env python3
"""Fifteen repaired-defect fixtures for WFA-0092.

Each defect has a repaired implementation and a reverted (broken) implementation.
The regression assertion observes behaviour, not the boolean flag itself.
Mutating one defect must turn only that assertion red.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

BACKGROUND_RECEIPT = "Background command started (shell_id=wfa-0092-hang)"
WIN_CMDLINE_LIMIT = 8191
BANNED_CLOCK = ("datetime.now", "time.time", "time.monotonic")
BANNED_RNG = ("random.random()", "random.randint(", "secrets.token_")
BANNED_ENV = ('os.environ[', "os.getenv(", "os.environ.get")

FIXED_CLOCK_SRC = "started_at = clock()  # injected clock, not wall time"
BROKEN_CLOCK_SRC = "started_at = datetime.now().isoformat()"
FIXED_RNG_SRC = "n = rng.randint(0, 10)  # rng = Random(seed) supplied by caller"
BROKEN_RNG_SRC = "n = random.random()"
FIXED_PATH_SRC = "path = root / 'out.json'"
BROKEN_PATH_SRC = 'path = os.environ["HOME"] + "/out.json"'


@dataclass(frozen=True)
class Defect:
    id: str
    repair_unit: str
    title: str
    run: Callable[[bool, Path], dict[str, Any]]
    check: Callable[[dict[str, Any]], bool]


def _under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def run_iso_shared_index(fixed: bool, tmp: Path) -> dict[str, Any]:
    """Two repairs must not share a git index (WFA-0087 isolation)."""
    wt_a = tmp / "wt-A"
    wt_b = tmp / "wt-B"
    wt_a.mkdir(parents=True, exist_ok=True)
    wt_b.mkdir(parents=True, exist_ok=True)
    if fixed:
        idx_a = wt_a / "index"
        idx_b = wt_b / "index"
    else:
        shared = tmp / "shared-index"
        idx_a = shared
        idx_b = shared
    idx_a.write_text("A", encoding="utf-8")
    idx_b.write_text("B", encoding="utf-8")
    same = idx_a.resolve() == idx_b.resolve()
    return {
        "index_a": idx_a.as_posix(),
        "index_b": idx_b.as_posix(),
        "shared_index": same,
        "a_bytes": idx_a.read_text(encoding="utf-8") if idx_a.is_file() else "",
        "b_bytes": idx_b.read_text(encoding="utf-8") if idx_b.is_file() else "",
    }


def check_iso_shared_index(r: dict[str, Any]) -> bool:
    return r["shared_index"] is False and r["a_bytes"] == "A" and r["b_bytes"] == "B"


def run_iso_out_of_scope(fixed: bool, tmp: Path) -> dict[str, Any]:
    declared = {"command-center/wfa/cand-B.json"}
    if fixed:
        changed = {"command-center/wfa/cand-B.json"}
    else:
        changed = {
            "command-center/wfa/cand-B.json",
            "skills/unrelated/SKILL.md",
        }
    extras = sorted(changed - declared)
    (tmp / "scope.json").write_text(
        json.dumps({"declared": sorted(declared), "changed": sorted(changed)}),
        encoding="utf-8",
    )
    return {
        "declared_scope": sorted(declared),
        "changed": sorted(changed),
        "extras": extras,
    }


def check_iso_out_of_scope(r: dict[str, Any]) -> bool:
    return r["extras"] == [] and set(r["changed"]) <= set(r["declared_scope"])


def run_iso_missing_worktree(fixed: bool, tmp: Path) -> dict[str, Any]:
    repo_index = tmp / "repo" / ".git" / "index"
    repo_index.parent.mkdir(parents=True, exist_ok=True)
    repo_index.write_text("repo-index", encoding="utf-8")
    if fixed:
        wt = tmp / "wt-c1"
        wt.mkdir(parents=True, exist_ok=True)
        index = wt / ".git" / "index"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text("wt-index", encoding="utf-8")
        worktree_id = "wt-c1"
    else:
        index = repo_index
        worktree_id = None
    return {
        "worktree_id": worktree_id,
        "index": index.as_posix(),
        "repo_index": repo_index.as_posix(),
        "uses_repo_index": index.resolve() == repo_index.resolve(),
    }


def check_iso_missing_worktree(r: dict[str, Any]) -> bool:
    return bool(r["worktree_id"]) and r["uses_repo_index"] is False


def run_fanout_hung_blocks(fixed: bool, tmp: Path) -> dict[str, Any]:
    """Discrete-event cohort: one hung agent must not block siblings."""
    agents = [
        {"id": "ok1", "work_ms": 100},
        {"id": "hung", "work_ms": 1_000_000},
        {"id": "ok2", "work_ms": 200},
    ]
    phase_deadline_ms = 5000
    if fixed:
        agent_deadline_ms = 1000
        outcomes = []
        for a in agents:
            if a["work_ms"] <= agent_deadline_ms:
                outcomes.append({**a, "status": "done", "elapsed_ms": a["work_ms"]})
            else:
                outcomes.append(
                    {**a, "status": "timeout", "elapsed_ms": agent_deadline_ms}
                )
        barrier_ms = max(o["elapsed_ms"] for o in outcomes)
    else:
        agent_deadline_ms = None
        barrier_ms = max(a["work_ms"] for a in agents)
        outcomes = [
            {**a, "status": "done", "elapsed_ms": a["work_ms"]} for a in agents
        ]
    hung = next(o for o in outcomes if o["id"] == "hung")
    siblings = [o for o in outcomes if o["id"] != "hung"]
    (tmp / "cohort.json").write_text(json.dumps(outcomes), encoding="utf-8")
    return {
        "outcomes": outcomes,
        "barrier_ms": barrier_ms,
        "phase_deadline_ms": phase_deadline_ms,
        "agent_deadline_ms": agent_deadline_ms,
        "hung_status": hung["status"],
        "siblings_done": all(s["status"] == "done" for s in siblings),
        "hung_did_not_block": barrier_ms < hung["work_ms"] and barrier_ms <= phase_deadline_ms,
    }


def check_fanout_hung_blocks(r: dict[str, Any]) -> bool:
    return (
        r["hung_status"] == "timeout"
        and r["siblings_done"] is True
        and r["hung_did_not_block"] is True
    )


def run_fanout_partial_memory(fixed: bool, tmp: Path) -> dict[str, Any]:
    partial = {"completed": ["ok1", "ok2"], "timed_out": ["hung"]}
    disk = tmp / "partial.json"
    if fixed:
        disk.write_text(json.dumps(partial, sort_keys=True), encoding="utf-8")
        memory = None
    else:
        memory = partial
    durable = disk.is_file() and disk.stat().st_size > 0
    parsed = None
    if durable:
        parsed = json.loads(disk.read_text(encoding="utf-8"))
    return {
        "disk": disk.as_posix() if durable else None,
        "memory_only": memory is not None,
        "durable": durable,
        "parsed": parsed,
    }


def check_fanout_partial_memory(r: dict[str, Any]) -> bool:
    return (
        r["durable"] is True
        and r["memory_only"] is False
        and (r["parsed"] or {}).get("timed_out") == ["hung"]
    )


def run_fanout_phase_deadline(fixed: bool, tmp: Path) -> dict[str, Any]:
    phase_deadline_ms = 5000
    if fixed:
        agents = [
            {"id": "a", "deadline_ms": 1000},
            {"id": "b", "deadline_ms": 1000},
        ]
    else:
        agents = [{"id": "a"}, {"id": "b"}]
    (tmp / "deadlines.json").write_text(json.dumps(agents), encoding="utf-8")
    return {
        "agents": agents,
        "phase_deadline_ms": phase_deadline_ms,
        "all_agents_have_deadline": all("deadline_ms" in a for a in agents),
    }


def check_fanout_phase_deadline(r: dict[str, Any]) -> bool:
    return r["all_agents_have_deadline"] is True and r["phase_deadline_ms"] > 0


def run_nondet_wall_clock(fixed: bool, tmp: Path) -> dict[str, Any]:
    src = FIXED_CLOCK_SRC if fixed else BROKEN_CLOCK_SRC
    hits = [p for p in BANNED_CLOCK if p in src]
    if fixed:
        clock = lambda: "T0"  # noqa: E731 — injected clock
        runs = [clock(), clock(), clock()]
    else:
        runs = ["T1", "T2", "T3"]
    (tmp / "clock-src.txt").write_text(src, encoding="utf-8")
    return {
        "source": src,
        "banned_hits": hits,
        "replay": runs,
        "identical": len(set(runs)) == 1,
    }


def check_nondet_wall_clock(r: dict[str, Any]) -> bool:
    return r["banned_hits"] == [] and r["identical"] is True


def run_nondet_unseeded_rng(fixed: bool, tmp: Path) -> dict[str, Any]:
    src = FIXED_RNG_SRC if fixed else BROKEN_RNG_SRC
    hits = [p for p in BANNED_RNG if p in src]
    if fixed:
        def once(seed: int) -> list[int]:
            rng = random.Random(seed)
            return [rng.randint(0, 10) for _ in range(5)]

        runs = [once(7), once(7), once(7)]
        identical = runs[0] == runs[1] == runs[2]
        seeded = True
    else:
        runs = [
            [random.Random(1).random() for _ in range(3)],
            [random.Random(2).random() for _ in range(3)],
            [random.Random(3).random() for _ in range(3)],
        ]
        identical = runs[0] == runs[1] == runs[2]
        seeded = False
    (tmp / "rng-src.txt").write_text(src, encoding="utf-8")
    return {
        "source": src,
        "banned_hits": hits,
        "runs": runs,
        "identical": identical,
        "seeded": seeded,
        "replay_count": 3,
    }


def check_nondet_unseeded_rng(r: dict[str, Any]) -> bool:
    return (
        r["banned_hits"] == []
        and r["seeded"] is True
        and r["identical"] is True
        and r["replay_count"] == 3
    )


def run_nondet_env_path(fixed: bool, tmp: Path) -> dict[str, Any]:
    src = FIXED_PATH_SRC if fixed else BROKEN_PATH_SRC
    hits = [p for p in BANNED_ENV if p in src]
    root = tmp / "root"
    root.mkdir(parents=True, exist_ok=True)
    if fixed:
        path = root / "out.json"
        assembled_from_env = False
    else:
        path = Path("/Users/someone") / "out.json"
        assembled_from_env = True
    return {
        "source": src,
        "banned_hits": hits,
        "path": path.as_posix(),
        "root": root.as_posix(),
        "assembled_from_env": assembled_from_env,
        "under_root": _under(path, root) if path.exists() or fixed else False,
    }


def check_nondet_env_path(r: dict[str, Any]) -> bool:
    return (
        r["banned_hits"] == []
        and r["assembled_from_env"] is False
        and r["under_root"] is True
    )


def run_dispatch_bg_receipt(fixed: bool, tmp: Path) -> dict[str, Any]:
    payload = BACKGROUND_RECEIPT
    (tmp / "payload.txt").write_text(payload, encoding="utf-8")
    phrase_present = "Background command started" in payload
    if fixed:
        rejected = phrase_present
        reason = "background-job-receipt-phrase" if rejected else None
    else:
        rejected = False
        reason = None
    return {
        "payload": payload,
        "phrase_present": phrase_present,
        "rejected": rejected,
        "reason": reason,
    }


def check_dispatch_bg_receipt(r: dict[str, Any]) -> bool:
    return r["phrase_present"] is True and r["rejected"] is True


def run_dispatch_oversized_inline(fixed: bool, tmp: Path) -> dict[str, Any]:
    prompt = "x" * (WIN_CMDLINE_LIMIT + 50)
    oversized = len(prompt) > WIN_CMDLINE_LIMIT
    if not oversized:
        raise RuntimeError("fixture prompt is not oversized")
    if fixed:
        prompt_file = tmp / "prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        return {
            "inline_rejected": True,
            "routed_to_file": True,
            "prompt_file_bytes": prompt_file.stat().st_size,
            "would_dispatch_inline": False,
            "cmdline_len": len(prompt),
            "limit": WIN_CMDLINE_LIMIT,
        }
    return {
        "inline_rejected": False,
        "routed_to_file": False,
        "prompt_file_bytes": 0,
        "would_dispatch_inline": True,
        "cmdline_len": len(prompt),
        "limit": WIN_CMDLINE_LIMIT,
    }


def check_dispatch_oversized_inline(r: dict[str, Any]) -> bool:
    return (
        r["inline_rejected"] is True
        and r["routed_to_file"] is True
        and r["prompt_file_bytes"] > WIN_CMDLINE_LIMIT
        and r["would_dispatch_inline"] is False
    )


def run_dispatch_exit0_no_file(fixed: bool, tmp: Path) -> dict[str, Any]:
    out = tmp / "contracted.json"
    exit_code = 0
    exists = out.is_file()
    size = out.stat().st_size if exists else 0
    parses = False
    if exists and size > 0:
        try:
            json.loads(out.read_text(encoding="utf-8"))
            parses = True
        except json.JSONDecodeError:
            parses = False
    if fixed:
        accepted = bool(exists and size > 0 and parses and exit_code == 0)
        terminal = "SUCCESS" if accepted else "SEVERED"
    else:
        accepted = exit_code == 0
        terminal = "SUCCESS" if accepted else "FAILED"
    return {
        "exit_code": exit_code,
        "exists": exists,
        "bytes": size,
        "parses": parses,
        "accepted": accepted,
        "terminal": terminal,
        "and_gate": "exists AND nonempty AND parses" if fixed else "exit-code-only",
    }


def check_dispatch_exit0_no_file(r: dict[str, Any]) -> bool:
    return (
        r["exists"] is False
        and r["accepted"] is False
        and r["terminal"] == "SEVERED"
        and r["exit_code"] == 0
    )


def run_fanin_digest_missing(fixed: bool, tmp: Path) -> dict[str, Any]:
    path = tmp / "missing-output.json"
    claimed = "a" * 64
    if path.exists():
        raise RuntimeError("planted missing file exists")
    if fixed:
        accepted = False
        reason = "digest-for-missing-file"
    else:
        accepted = True
        reason = "trusted-digest"
    return {
        "path": path.as_posix(),
        "path_exists": path.is_file(),
        "claimed_sha256": claimed,
        "accepted": accepted,
        "reason": reason,
    }


def check_fanin_digest_missing(r: dict[str, Any]) -> bool:
    return (
        r["path_exists"] is False
        and r["accepted"] is False
        and r["reason"] == "digest-for-missing-file"
    )


def run_fanin_silent_null(fixed: bool, tmp: Path) -> dict[str, Any]:
    incoming = [
        {"id": "U-valid", "value": {"ok": True}, "schema_ok": True},
        {"id": "U-null", "value": None, "schema_ok": None},
        {"id": "U-invalid", "value": {"not": "schema"}, "schema_ok": False},
    ]
    missing: list[str] = []
    invalid: list[str] = []
    kept: list[str] = []
    for item in incoming:
        if item["value"] is None:
            if fixed:
                missing.append(item["id"])
            continue
        if item["schema_ok"] is False:
            invalid.append(item["id"])
            continue
        kept.append(item["id"])
    (tmp / "fanin-null.json").write_text(
        json.dumps({"kept": kept, "missing": missing, "invalid": invalid}),
        encoding="utf-8",
    )
    return {
        "incoming_ids": [i["id"] for i in incoming],
        "kept": kept,
        "missing": missing,
        "invalid": invalid,
        "null_silently_dropped": "U-null" not in missing and "U-null" not in kept,
    }


def check_fanin_silent_null(r: dict[str, Any]) -> bool:
    return (
        "U-null" in r["missing"]
        and "U-null" not in r["kept"]
        and r["null_silently_dropped"] is False
        and "U-invalid" in r["invalid"]
    )


def run_fanin_unrecorded_wait(fixed: bool, tmp: Path) -> dict[str, Any]:
    waited_for = ["U-valid", "U-null", "U-invalid"]
    received = ["U-valid"]
    not_received = ["U-null", "U-invalid"]
    if fixed:
        record = {
            "waited_for": waited_for,
            "received": received,
            "not_received": not_received,
        }
        (tmp / "barrier-record.json").write_text(
            json.dumps(record, sort_keys=True), encoding="utf-8"
        )
    else:
        record = None
    return {
        "record": record,
        "recorded": record is not None,
    }


def check_fanin_unrecorded_wait(r: dict[str, Any]) -> bool:
    rec = r.get("record") or {}
    return (
        r["recorded"] is True
        and rec.get("waited_for") == ["U-valid", "U-null", "U-invalid"]
        and rec.get("not_received") == ["U-null", "U-invalid"]
        and rec.get("received") == ["U-valid"]
    )


def scanner_both_states() -> dict[str, Any]:
    """Detector must fire on a planted wall-clock and stay silent on injected clock."""
    planted = "started_at = datetime.now().isoformat()"
    clean = FIXED_CLOCK_SRC
    plant_hits = [p for p in BANNED_CLOCK if p in planted]
    clean_hits = [p for p in BANNED_CLOCK if p in clean]
    return {
        "planted_fires": bool(plant_hits),
        "clean_silent": clean_hits == [],
        "plant_hits": plant_hits,
        "clean_hits": clean_hits,
        "ok": bool(plant_hits) and clean_hits == [],
    }


DEFECTS: tuple[Defect, ...] = (
    Defect(
        "iso-shared-index",
        "WFA-0087",
        "Two repairs must not share a git index",
        run_iso_shared_index,
        check_iso_shared_index,
    ),
    Defect(
        "iso-out-of-scope",
        "WFA-0087",
        "Repair diff must stay inside declared scope",
        run_iso_out_of_scope,
        check_iso_out_of_scope,
    ),
    Defect(
        "iso-missing-worktree",
        "WFA-0087",
        "Each repair runs in its own worktree, not the repo index",
        run_iso_missing_worktree,
        check_iso_missing_worktree,
    ),
    Defect(
        "fanout-hung-blocks",
        "WFA-0088",
        "Per-agent timeout: hung unit must not block the cohort",
        run_fanout_hung_blocks,
        check_fanout_hung_blocks,
    ),
    Defect(
        "fanout-partial-memory",
        "WFA-0088",
        "Partial barrier results must be durable on disk",
        run_fanout_partial_memory,
        check_fanout_partial_memory,
    ),
    Defect(
        "fanout-phase-deadline",
        "WFA-0088",
        "Deadline must be per-agent, not only per-phase",
        run_fanout_phase_deadline,
        check_fanout_phase_deadline,
    ),
    Defect(
        "nondet-wall-clock",
        "WFA-0089",
        "Wall-clock reads are banned; injected clock replays identically",
        run_nondet_wall_clock,
        check_nondet_wall_clock,
    ),
    Defect(
        "nondet-unseeded-rng",
        "WFA-0089",
        "RNG must be seeded; three replays must match",
        run_nondet_unseeded_rng,
        check_nondet_unseeded_rng,
    ),
    Defect(
        "nondet-env-path",
        "WFA-0089",
        "Paths must be rooted, not assembled from the environment",
        run_nondet_env_path,
        check_nondet_env_path,
    ),
    Defect(
        "dispatch-bg-receipt",
        "WFA-0090",
        "Background-job receipt phrases are rejected",
        run_dispatch_bg_receipt,
        check_dispatch_bg_receipt,
    ),
    Defect(
        "dispatch-oversized-inline",
        "WFA-0090",
        "Oversized inline prompts route to a prompt file",
        run_dispatch_oversized_inline,
        check_dispatch_oversized_inline,
    ),
    Defect(
        "dispatch-exit0-no-file",
        "WFA-0090",
        "Exit 0 without a parseable output file is SEVERED",
        run_dispatch_exit0_no_file,
        check_dispatch_exit0_no_file,
    ),
    Defect(
        "fanin-digest-missing",
        "WFA-0091",
        "A digest for a missing file is rejected",
        run_fanin_digest_missing,
        check_fanin_digest_missing,
    ),
    Defect(
        "fanin-silent-null",
        "WFA-0091",
        "A null result is reported as missing, not dropped",
        run_fanin_silent_null,
        check_fanin_silent_null,
    ),
    Defect(
        "fanin-unrecorded-wait",
        "WFA-0091",
        "Barrier records waited-for versus not-received",
        run_fanin_unrecorded_wait,
        check_fanin_unrecorded_wait,
    ),
)


def by_id() -> dict[str, Defect]:
    return {d.id: d for d in DEFECTS}
