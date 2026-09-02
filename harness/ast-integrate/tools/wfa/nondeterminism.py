"""Repair wall-clock, unseeded RNG, interpolated args, env-path (WFA-0089)."""
from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

DECLARED_NONDETERMINISTIC_FIELDS = frozenset({"recorded_at"})

_WALL = re.compile(
    r"\bDate\.now\s*\(|\bnew\s+Date\s*\(|\btime\.time\s*\(|\bdatetime\.now\s*\("
)
_RAND = re.compile(r"\bMath\.random\s*\(|\brandom\.random\s*\(|\buuid\.uuid4\s*\(")
_INTERP = re.compile(r"agent\s*\(\s*[`'][^`']*\$\{|agent\s*\(\s*f['\"]")
_ENV = re.compile(
    r"process\.env\.HOME|os\.path\.expanduser|Path\.home\s*\(|os\.environ\["
)


@dataclass
class Finding:
    kind: str
    relpath: str
    line: int
    snippet: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "relpath": self.relpath,
            "line": self.line,
            "snippet": self.snippet,
        }


@dataclass
class FrozenClock:
    tick: int = 0

    def now(self) -> int:
        self.tick += 1
        return self.tick


@dataclass
class Executed:
    stages: list[dict[str, Any]]
    artifact: dict[str, Any]

    def comparable(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in self.artifact.items()
            if k not in DECLARED_NONDETERMINISTIC_FIELDS
        }


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def leaky_ir() -> dict[str, Any]:
    return {
        "id": "wf-saved-demo",
        "dialect": "saved-workflow-leaky-v0",
        "clock": "wall",
        "rng": {"kind": "unseeded"},
        "children": [f"child-{i:02d}" for i in range(16)],
        "sample_k": 6,
        "stages": [
            {"id": "plan", "kind": "agent", "args": "summarize ${HOME}"},
            {
                "id": "fanout",
                "kind": "parallel",
                "sample_k": 6,
                "shuffle_with": "unseeded",
                "children": [f"child-{i:02d}" for i in range(16)],
            },
            {"id": "barrier", "kind": "barrier", "join": "arrival-order"},
        ],
    }


def repair_ir(leaky: dict[str, Any] | None = None) -> dict[str, Any]:
    del leaky
    return {
        "children": [f"child-{i:02d}" for i in range(16)],
        "clock": "logical",
        "declared_nondeterministic_fields": sorted(DECLARED_NONDETERMINISTIC_FIELDS),
        "dialect": "saved-workflow-repaired-v1",
        "id": "wf-saved-demo",
        "rng": {"kind": "seeded", "seed_from": "inputs.seed"},
        "run_root_from": "inputs.run_root",
        "sample_k": 6,
        "stages": [
            {
                "args": {"op": "plan", "path": {"parts": ["work"]}},
                "id": "plan",
                "kind": "agent",
            },
            {
                "children": [f"child-{i:02d}" for i in range(16)],
                "id": "fanout",
                "kind": "parallel",
                "sample_k": 6,
                "shuffle_with": "seeded",
            },
            {"id": "barrier", "join": "child-id-order", "kind": "barrier"},
        ],
    }


def _execute_leaky(ir: dict[str, Any]) -> Executed:
    rng = random.Random()
    children = list(ir.get("children") or [])
    rng.shuffle(children)
    sampled = children[: int(ir.get("sample_k") or 6)]
    stages = [
        {"id": "plan", "stamp": rng.random()},
        {"id": "fanout", "sampled": sampled},
        {"id": "barrier", "order": list(sampled)},
    ]
    art = {
        "stages": stages,
        "sampled_children": sampled,
        "barrier_order": list(sampled),
        "recorded_at": rng.random(),
    }
    return Executed(stages=stages, artifact=art)


def execute_repaired(
    ir: dict[str, Any],
    seed: int,
    run_root: str,
    include_receipt_timestamp: bool = True,
) -> Executed:
    rng = random.Random(seed)
    clock = FrozenClock()
    children = list(ir.get("children") or [])
    k = int(ir.get("sample_k") or 6)
    # Seeded sample without mutating canonical child-id order.
    order = list(children)
    rng.shuffle(order)
    sampled = sorted(order[:k])
    stages = [
        {
            "id": "plan",
            "op": "plan",
            "tick": clock.now(),
            "root": run_root,
            "path": {"parts": ["work"]},
        },
        {"id": "fanout", "sampled": sampled, "tick": clock.now()},
        {"id": "barrier", "order": list(sampled), "join": "child-id-order"},
    ]
    art = {
        "stages": stages,
        "sampled_children": sampled,
        "barrier_order": list(sampled),
        "run_root": run_root,
        "seed": seed,
        "draw": rng.random(),
        "tick": clock.now(),
    }
    if include_receipt_timestamp:
        art["recorded_at"] = f"logical-{clock.now()}"
    return Executed(stages=stages, artifact=art)


def leaky_diverges(ir: dict[str, Any], attempts: int = 8) -> dict[str, Any]:
    hashes: list[str] = []
    for _ in range(attempts):
        executed = _execute_leaky(ir)
        hashes.append(sha256_hex(canonical_bytes(executed.stages)))
    distinct = sorted(set(hashes))
    return {
        "attempts": attempts,
        "diverges": len(distinct) > 1,
        "distinct_stage_hashes": len(distinct),
        "hashes": hashes,
    }


def replay_hashes(
    ir: dict[str, Any],
    seed: int,
    run_root: str,
    n: int = 3,
) -> dict[str, Any]:
    runs = [
        execute_repaired(ir, seed=seed, run_root=run_root, include_receipt_timestamp=True)
        for _ in range(n)
    ]
    stage_hashes = [sha256_hex(canonical_bytes(r.stages)) for r in runs]
    comparable_hashes = [sha256_hex(canonical_bytes(r.comparable())) for r in runs]
    raw_hashes = [sha256_hex(canonical_bytes(r.artifact)) for r in runs]
    keys = set().union(*(r.artifact.keys() for r in runs))
    varying: list[str] = []
    for key in sorted(keys):
        vals = [json.dumps(r.artifact.get(key), sort_keys=True) for r in runs]
        if len(set(vals)) > 1:
            varying.append(key)
    undeclared = [k for k in varying if k not in DECLARED_NONDETERMINISTIC_FIELDS]
    last = runs[-1]
    return {
        "n": n,
        "stage_sequences_identical": len(set(stage_hashes)) == 1,
        "comparable_identical": len(set(comparable_hashes)) == 1,
        "declared_fields": sorted(DECLARED_NONDETERMINISTIC_FIELDS),
        "varying_artifact_keys": varying,
        "undeclared_varying_keys": undeclared,
        "stage_sequence_sha256": stage_hashes,
        "comparable_sha256": comparable_hashes,
        "raw_artifact_sha256": raw_hashes,
        "sampled_children": last.artifact.get("sampled_children"),
        "barrier_order": last.artifact.get("barrier_order"),
    }


def _scan_text_body(text: str, relpath: str) -> list[Finding]:
    hits: list[Finding] = []
    for i, line in enumerate(text.splitlines(), 1):
        if _WALL.search(line):
            hits.append(Finding("wall-clock", relpath, i, line.strip()[:160]))
        if _RAND.search(line):
            hits.append(Finding("unseeded-random", relpath, i, line.strip()[:160]))
        if _INTERP.search(line):
            hits.append(Finding("interpolated-args", relpath, i, line.strip()[:160]))
        if _ENV.search(line):
            hits.append(Finding("env-path", relpath, i, line.strip()[:160]))
    return hits


def scan_text(text: str, relpath: str = "memory") -> list[Finding]:
    return _scan_text_body(text, relpath)


def scan_path(path: Path, repo: Path | None = None) -> list[Finding]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if repo is not None:
        try:
            rel = path.relative_to(repo).as_posix()
        except ValueError:
            rel = path.name
    else:
        rel = path.name
    return _scan_text_body(text, rel)


def scan_tree(root: Path, repo: Path | None = None) -> list[Finding]:
    root = Path(root)
    hits: list[Finding] = []
    if not root.exists():
        return hits
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".mjs", ".js", ".ts", ".py", ".jsx", ".tsx"}:
            continue
        hits.extend(scan_path(path, repo=repo or root))
    return hits


def finding_dicts(findings: Iterable[Finding]) -> list[dict[str, Any]]:
    return [f.as_dict() if isinstance(f, Finding) else dict(f) for f in findings]


def findings_by_kind(findings: Iterable[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in findings:
        kind = item.kind if isinstance(item, Finding) else str(item.get("kind") or "")
        counts[kind] = counts.get(kind, 0) + 1
    return counts
