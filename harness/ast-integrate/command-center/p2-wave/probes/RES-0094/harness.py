#!/usr/bin/env python3
"""Local agent-run simulator for RES-0094 nondeterminism census.

This is a harness-layer agent (tool loop + sampling + transcript), not a
hosted LLM API. Factors named in the catalog are each a controllable pin.
A tree mutating under the runner is recorded as its own variance source and
is isolated out of the pinned transcript.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import secrets
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TASK_PATH = HERE / "fixtures" / "task.json"
SCRATCH = HERE / "scratch"
N_DEFAULT = 7
FROZEN_CLOCK = 1_700_000_000
PINNED_SEED = 94
PINNED_MODEL = "local-sim-res0094-1.0"
TOKEN_N = 8

MODES = ("pinned", "unpin-sampling", "unpin-clock", "unpin-tools", "unpin-siblings")


def _task() -> dict[str, Any]:
    return json.loads(TASK_PATH.read_text(encoding="utf-8"))


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    raw = text.replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sample_variance(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean = sum(xs) / n
    return sum((x - mean) ** 2 for x in xs) / (n - 1)


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _tool_names(task: dict[str, Any], order: str) -> list[str]:
    names = list(task["tools"])
    if order == "sorted":
        return sorted(names)
    rng = random.Random(secrets.randbits(64))
    rng.shuffle(names)
    return names


def _tokens(seed: int | None) -> list[int]:
    if seed is None:
        rng = random.SystemRandom()
        return [int(rng.randrange(0, 1000)) for _ in range(TOKEN_N)]
    rng = random.Random(seed)
    return [rng.randrange(0, 1000) for _ in range(TOKEN_N)]


def _sibling_payload(isolated: bool, index: int) -> str:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    path = SCRATCH / ("isolated.txt" if isolated else "shared.txt")
    if isolated:
        path.write_text("isolated-sibling-fixture\n", encoding="utf-8")
        return path.read_text(encoding="utf-8")
    # Unpinned: a concurrent sibling (this series) mutates shared state.
    prev = path.read_text(encoding="utf-8") if path.is_file() else ""
    path.write_text(prev + f"sib-{index}-{time.time_ns()}\n", encoding="utf-8")
    return path.read_text(encoding="utf-8")


def run_one(mode: str, index: int = 0) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode}")
    task = _task()
    pin_sampling = mode != "unpin-sampling"
    pin_clock = mode != "unpin-clock"
    pin_tools = mode != "unpin-tools"
    pin_siblings = mode != "unpin-siblings"

    tokens = _tokens(PINNED_SEED if pin_sampling else None)
    tools = _tool_names(task, "sorted" if pin_tools else "shuffled")
    payload = str(task["payload"])
    sibling = _sibling_payload(isolated=pin_siblings, index=index)
    calls = []
    for name in tools:
        if name == "echo":
            result = payload
        elif name == "digest":
            result = _digest(payload)
        elif name == "roster":
            result = ",".join(tools)
        else:
            result = "unknown"
        calls.append({"tool": name, "result": result})

    clock: int | str
    if pin_clock:
        clock = FROZEN_CLOCK
    else:
        time.sleep(0.002)
        clock = time.time_ns()

    transcript = {
        "clock": clock,
        "index_ignored_when_pinned": True,
        "model_id": PINNED_MODEL,
        "network": "fixture",
        "payload_digest": _digest(payload),
        "sibling_sha256": sha256_text(sibling),
        "task_id": task["task_id"],
        "token_sum": int(sum(tokens)),
        "tokens": tokens,
        "tool_calls": calls,
        "tool_order": tools,
    }
    text = canonical_dumps(transcript) + "\n"
    return {
        "mode": mode,
        "sha256": sha256_text(text),
        "text": text,
        "token_sum": int(sum(tokens)),
        "transcript": transcript,
    }


def run_series(mode: str, n: int = N_DEFAULT) -> dict[str, Any]:
    if n < 2:
        raise ValueError("n must be >= 2")
    rows = [run_one(mode, index=i) for i in range(n)]
    hashes = [r["sha256"] for r in rows]
    sums = [float(r["token_sum"]) for r in rows]
    unique = sorted(set(hashes))
    return {
        "hashes": hashes,
        "mode": mode,
        "n": n,
        "sample_variance_token_sum": sample_variance(sums),
        "token_sums": [int(s) for s in sums],
        "unique_count": len(unique),
        "unique_hashes": unique,
    }


def tree_sample() -> dict[str, Any]:
    """Fingerprint of this probe tree. A live worktree mutating under the
    runner is a variance source; this sample is labelled SAMPLE not FROZEN.
    """
    paths = [
        HERE / "harness.py",
        TASK_PATH,
    ]
    files = []
    blob = []
    for path in paths:
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        digest = hashlib.sha256(raw).hexdigest()
        rel = path.relative_to(REPO).as_posix()
        files.append({"path": rel, "sha256": digest, "bytes": len(raw)})
        blob.append(f"{digest}  {rel}".encode("utf-8"))
    return {
        "files": files,
        "label": "SAMPLE",
        "note": (
            "A tree mutating under the runner is itself a variance source. "
            "Pinned agent transcripts read an isolated scratch fixture, not "
            "the live worktree. This fingerprint is a timestamped sample of "
            "the probe files, not a FROZEN baseline."
        ),
        "sha256": hashlib.sha256(b"\n".join(blob) + b"\n").hexdigest(),
    }


def measure(n: int = N_DEFAULT) -> dict[str, Any]:
    start = tree_sample()
    pinned = run_series("pinned", n=n)
    unpinned = run_series("unpin-sampling", n=n)
    clock = run_series("unpin-clock", n=n)
    end = tree_sample()
    increased = unpinned["unique_count"] > pinned["unique_count"]
    var_increased = (
        unpinned["sample_variance_token_sum"] > pinned["sample_variance_token_sum"]
    )
    return {
        "n": n,
        "pinned": pinned,
        "tree_end": end,
        "tree_mutated_during_measure": start["sha256"] != end["sha256"],
        "tree_start": start,
        "unpin_clock": clock,
        "unpin_sampling": unpinned,
        "variance_increased": bool(increased and var_increased),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="RES-0094 agent-run harness")
    sub = p.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--mode", choices=MODES, default="pinned")
    run_p.add_argument("--index", type=int, default=0)
    ser_p = sub.add_parser("series")
    ser_p.add_argument("--mode", choices=MODES, default="pinned")
    ser_p.add_argument("--n", type=int, default=N_DEFAULT)
    sub.add_parser("measure")
    args = p.parse_args(argv)
    if args.cmd == "run":
        sys.stdout.write(run_one(args.mode, index=args.index)["text"])
        return 0
    if args.cmd == "series":
        print(canonical_dumps(run_series(args.mode, n=args.n)))
        return 0
    print(canonical_dumps(measure()))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.environ.setdefault("TZ", "UTC")
    raise SystemExit(main())
