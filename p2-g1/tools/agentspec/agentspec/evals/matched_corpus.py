"""IMP-0198: the matched benchmark case corpus with hash-determined difficulty
stratification and a development-access detector for the held-out slice.

Partition authority is HASH-ONLY: partition_of(case) is a pure function of
SHA-256(salt || canonical identity) mod 10. A `partition_cached` label on a
case is a CONVENTION, never consulted by partition_of, so relabelling it
cannot move a case between slices or hide a held-out touch.

Development code must not read held-out cases; the access-controlled readers
raise HeldOutTouchError and record the violation in the AccessLog. Evaluation
code may read the held-out slice.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parents[4] / "command-center" / "bench" / "cases" / "IMP-0198" / "corpus.json"
SALT = "IMP-0198.v1"
MOD = 10
HELD_OUT_RESIDUE = 0

HELD_OUT = "held-out"
VISIBLE = "visible"


class HeldOutTouchError(Exception):
    """Development code read a held-out case."""


def canonical_identity(case) -> str:
    if isinstance(case, dict):
        return str(case["id"])
    return str(case)


def partition_of(case, partition_cached: str | None = None) -> str:
    """Pure function of the identity hash. ``partition_cached`` is deliberately
    ignored: flipping or relabelling it must move zero cases."""
    del partition_cached
    digest = hashlib.sha256((SALT + canonical_identity(case)).encode("utf-8")).hexdigest()
    return HELD_OUT if int(digest, 16) % MOD == HELD_OUT_RESIDUE else VISIBLE


def independent_partition(identity: str) -> str:
    """A SECOND implementation used by the probe: different construction, same rule."""
    h = hashlib.new("sha256")
    h.update(SALT.encode("utf-8"))
    h.update(identity.encode("utf-8"))
    return HELD_OUT if int.from_bytes(h.digest(), "big") % MOD == HELD_OUT_RESIDUE else VISIBLE


def load_corpus(path=None) -> dict:
    loc = Path(path) if path else CORPUS_PATH
    return json.loads(loc.read_text(encoding="utf-8"))


def stratum_counts(corpus: dict) -> dict:
    out: dict[str, dict[str, int]] = {}
    for case in corpus["cases"]:
        diff = case["difficulty"]
        part = partition_of(case)
        out.setdefault(diff, {VISIBLE: 0, HELD_OUT: 0})
        out[diff][part] += 1
    return {k: out[k] for k in sorted(out)}


@dataclass
class AccessLog:
    entries: list = field(default_factory=list)
    violations: list = field(default_factory=list)

    def read(self, case, mode: str = "development") -> dict:
        """Mode-gated case read. Development may only touch visible cases."""
        part = partition_of(case)
        cid = canonical_identity(case)
        self.entries.append({"case": cid, "mode": mode, "partition": part})
        if mode == "development" and part == HELD_OUT:
            self.violations.append({"case": cid, "mode": mode, "partition": part})
            raise HeldOutTouchError(
                f"development touched held-out case {cid}")
        return case

    def evaluation_read(self, case) -> dict:
        return self.read(case, mode="evaluation")


def sampled_ids(corpus: dict, part: str) -> list:
    return [c["id"] for c in corpus["cases"] if partition_of(c) == part][:3]
