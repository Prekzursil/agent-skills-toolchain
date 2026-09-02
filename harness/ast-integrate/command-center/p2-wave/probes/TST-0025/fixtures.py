"""Deterministic nonempty input sets for TST-0025 baseline capture.

Same seed ⇒ same queries, hook subjects, and input fingerprint.
An empty list is a valid *control* input and must not be used as a measured set.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SEED = 25
N_QUERIES = 24
N_HOOK = 16
ALLOWED_ROOT = HERE / "work" / "allowed"
DENIED_ROOT = HERE / "work" / "denied"

QUERY_STEMS = (
    "please lint this with ruff",
    "run pytest on the targeted unit tests",
    "ruff check the changed files",
    "write a unit test with pytest",
    "unrelated cooking recipe with no matching skill",
    "format then lint using ruff",
    "pytest the semantic router eval",
    "document how to pull an embedding model",
)


def make_queries(seed: int = SEED, n: int = N_QUERIES) -> list[str]:
    rng = random.Random(seed)
    out: list[str] = []
    for i in range(n):
        stem = QUERY_STEMS[i % len(QUERY_STEMS)]
        out.append(f"{stem} #{i} nonce={rng.randint(1, 1_000_000)}")
    return out


def make_hook_subjects(seed: int = SEED, n: int = N_HOOK) -> list[dict]:
    """Mix of allowlisted and denied spawn/write/connect subjects."""
    rng = random.Random(seed + 1)
    ALLOWED_ROOT.mkdir(parents=True, exist_ok=True)
    DENIED_ROOT.mkdir(parents=True, exist_ok=True)
    exe = sys.executable
    kinds = ("spawn-allow", "spawn-deny", "write-allow", "write-deny", "net-deny")
    out: list[dict] = []
    for i in range(n):
        kind = kinds[i % len(kinds)]
        token = rng.randint(1, 1_000_000)
        if kind == "spawn-allow":
            out.append({"kind": "spawn", "argv": [exe, "-c", "pass"], "expect": "allow"})
        elif kind == "spawn-deny":
            out.append(
                {
                    "kind": "spawn",
                    "argv": ["/bin/false", f"tst0025-{token}"],
                    "expect": "deny",
                }
            )
        elif kind == "write-allow":
            path = ALLOWED_ROOT / f"ok-{i}-{token}.txt"
            out.append({"kind": "write", "path": str(path), "expect": "allow"})
        elif kind == "write-deny":
            path = DENIED_ROOT / f"no-{i}-{token}.txt"
            out.append({"kind": "write", "path": str(path), "expect": "deny"})
        else:
            out.append(
                {
                    "kind": "net",
                    "host": "127.0.0.1",
                    "port": 1 + (token % 16),
                    "expect": "deny",
                }
            )
    return out


def input_fingerprint(queries: list[str], hooks: list[dict]) -> str:
    blob = json.dumps(
        {"queries": queries, "hooks": hooks},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
