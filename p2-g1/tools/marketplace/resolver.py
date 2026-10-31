"""Deterministic marketplace dependency resolver (IMP-0083)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from marketplace.version import compare, parse_version


def _caret_upper(ver: str) -> str:
    v = parse_version(ver)
    if v.major > 0:
        return f"{v.major + 1}.0.0"
    if v.minor > 0:
        return f"0.{v.minor + 1}.0"
    return f"0.0.{v.patch + 1}"


def range_ok(version: str, spec: str) -> bool:
    spec = str(spec or "*").strip()
    if spec in {"*", ""}:
        return True
    if spec.startswith("^"):
        base = spec[1:].strip()
        return compare(version, base) >= 0 and compare(version, _caret_upper(base)) < 0
    if spec.startswith("~"):
        v = parse_version(spec[1:].strip())
        upper = f"{v.major}.{v.minor + 1}.0"
        return compare(version, str(v)) >= 0 and compare(version, upper) < 0
    if spec.startswith(">="):
        return compare(version, spec[2:].strip()) >= 0
    if spec.startswith("<="):
        return compare(version, spec[2:].strip()) <= 0
    if spec.startswith(">"):
        return compare(version, spec[1:].strip()) > 0
    if spec.startswith("<"):
        return compare(version, spec[1:].strip()) < 0
    if spec.startswith("==") or spec.startswith("="):
        return compare(version, spec.lstrip("=").strip()) == 0
    return compare(version, spec) == 0


def _candidates(index: dict[str, list[dict[str, Any]]], name: str, rng: str) -> list[str]:
    rows = index.get(name) or []
    vers = [str(r["version"]) for r in rows if range_ok(str(r["version"]), rng)]
    vers.sort(key=lambda x: parse_version(x), reverse=True)
    return vers


def _deps_of(index: dict[str, list[dict[str, Any]]], name: str, ver: str) -> list[dict[str, str]]:
    for row in index.get(name) or []:
        if str(row["version"]) == ver:
            return list(row.get("deps") or [])
    return []


@dataclass
class ResolveResult:
    status: str
    solution: dict[str, str] = field(default_factory=dict)
    conflicting_pair: list[dict[str, str]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "solution": dict(self.solution),
            "conflicting_pair": list(self.conflicting_pair or []),
        }


def _solve(
    index: dict[str, list[dict[str, Any]]],
    request: list[dict[str, str]],
    *,
    pick: str = "latest",
) -> ResolveResult:
    chosen: dict[str, str] = {}
    constraints: dict[str, list[tuple[str, str]]] = {}

    def add_req(name: str, rng: str, source: str) -> str | None:
        constraints.setdefault(name, []).append((rng, source))
        cands = _candidates(index, name, rng)
        if name in chosen:
            if not range_ok(chosen[name], rng):
                return name
            return None
        if not cands:
            return name
        if pick == "first":
            chosen[name] = cands[-1] if False else (cands[0] if pick == "latest" else cands[-1])
        if pick == "latest":
            chosen[name] = cands[0]
        elif pick == "first-listed":
            listed = [str(r["version"]) for r in (index.get(name) or []) if range_ok(str(r["version"]), rng)]
            chosen[name] = listed[0] if listed else cands[0]
        else:
            chosen[name] = cands[0]
        for dep in _deps_of(index, name, chosen[name]):
            err = add_req(dep["name"], dep["range"], f"{name}@{chosen[name]}")
            if err:
                return err
        return None

    for req in request:
        err = add_req(req["name"], req["range"], "root")
        if err:
            # Build a pair.
            cons = constraints.get(err) or []
            if len(cons) >= 2:
                pair = [
                    {"package": err, "range": cons[0][0], "source": cons[0][1]},
                    {"package": err, "range": cons[1][0], "source": cons[1][1]},
                ]
            elif cons:
                pair = [
                    {"package": err, "range": cons[0][0], "source": cons[0][1]},
                    {
                        "package": err,
                        "range": "no-satisfying-version",
                        "source": "index",
                    },
                ]
            else:
                pair = [
                    {"package": err, "range": req.get("range", ""), "source": "root"},
                    {
                        "package": err,
                        "range": "no-satisfying-version",
                        "source": "index",
                    },
                ]
            return ResolveResult("UNSATISFIABLE", {}, pair)
    # Recheck all constraints against chosen.
    for name, cons in constraints.items():
        ver = chosen.get(name)
        if ver is None:
            return ResolveResult(
                "UNSATISFIABLE",
                {},
                [
                    {"package": name, "range": cons[0][0], "source": cons[0][1]},
                    {"package": name, "range": "no-satisfying-version", "source": "index"},
                ],
            )
        for rng, src in cons:
            if not range_ok(ver, rng):
                other = next((c for c in cons if c[1] != src), cons[-1])
                return ResolveResult(
                    "UNSATISFIABLE",
                    {},
                    [
                        {"package": name, "range": rng, "source": src},
                        {"package": name, "range": other[0], "source": other[1]},
                    ],
                )
    return ResolveResult("SAT", chosen, None)


def resolve(index: dict[str, list[dict[str, Any]]], request: list[dict[str, str]]) -> ResolveResult:
    return _solve(index, request, pick="latest")


def resolve_order_sensitive(index: dict[str, list[dict[str, Any]]], request: list[dict[str, str]]) -> ResolveResult:
    return _solve(index, request, pick="first-listed")


def resolve_set_iteration(index: dict[str, list[dict[str, Any]]], request: list[dict[str, str]]) -> ResolveResult:
    # Hash-order iteration over package names: not shuffle-stable.
    names = list({*index, *(r["name"] for r in request)})
    names = sorted(names, key=lambda n: hash(n) % 10_000)
    remapped = {k: index[k] for k in names if k in index}
    for k, v in index.items():
        remapped.setdefault(k, v)
    return _solve(remapped, request, pick="first-listed")


def solution_digest(result: ResolveResult) -> str:
    blob = json.dumps(result.solution, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def assert_solution_satisfies(index: dict[str, list[dict[str, Any]]], result: ResolveResult) -> None:
    if result.status != "SAT":
        raise AssertionError("not SAT")
    for name, ver in result.solution.items():
        for dep in _deps_of(index, name, ver):
            got = result.solution.get(dep["name"])
            if got is None or not range_ok(got, dep["range"]):
                raise AssertionError(f"{name}@{ver} dep {dep} unsatisfied ({got})")


def repeat_digests(index: dict, request: list, n: int = 100) -> list[str]:
    return [solution_digest(resolve(index, request)) for _ in range(n)]
