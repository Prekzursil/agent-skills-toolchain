"""Call the live production workflow validator without mutating it.

Production ``validate_workflow`` accepts a typed ``Workflow`` or a mapping.
The mapping path only inspects ``repair-loop`` nodes and ignores every other
kind, so feeding our dict fixtures straight in would silently miss fan-out
and barrier. This adapter:

* builds a typed ``Workflow`` for closed node kinds (unit, fanout, barrier,
  pipeline, repair-loop);
* reports ``unknown-node-type`` when a fixture node is outside that closed
  set (loop-with-convergence, human-checkpoint, subworkflow, retry, resume).
  Production has no such id; the adapter name is the measured gap so the
  suite can tell "no validator" from "validator accepted the input".
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from constructs import canonical_type

CLOSED_FIXTURE_TYPES = frozenset(
    {"unit", "fanout", "fan-out", "barrier", "pipeline", "repair-loop"}
)


def _mod(repo: Path):
    root = repo / "tools" / "agentspec"
    path = str(root)
    if path not in sys.path:
        sys.path.insert(0, path)
    import agentspec.validate as validate

    return importlib.reload(validate)


def _spec(repo: Path):
    root = repo / "tools" / "agentspec"
    path = str(root)
    if path not in sys.path:
        sys.path.insert(0, path)
    import agentspec.spec as spec

    return importlib.reload(spec)


def _agentspec(repo: Path):
    root = repo / "tools" / "agentspec"
    path = str(root)
    if path not in sys.path:
        sys.path.insert(0, path)
    import agentspec as pkg

    return importlib.reload(pkg)


def available(repo: Path) -> bool:
    return (repo / "tools" / "agentspec" / "agentspec" / "validate.py").is_file()


def _work_unit(spec, node: dict[str, Any]):
    nid = str(node.get("id") or "u")
    body = node.get("body")
    if isinstance(body, dict):
        prompt = str(body.get("run") or nid)
    elif isinstance(body, str) and body.strip():
        prompt = body
    else:
        prompt = nid
    if not prompt.strip():
        prompt = nid
    return spec.WorkUnit(
        id=nid,
        prompt=prompt,
        timeout_s=1800,
        receipt=spec.ReceiptSpec(fmt="json", required_fields=("status",)),
    )


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value)


def _typed_node(spec, node: dict[str, Any], ntype: str):
    nid = str(node.get("id") or "n")
    if ntype in {"fanout", "fan-out"}:
        members = node.get("members")
        if members is None:
            members = node.get("units")
        return spec.FanOut(id=nid, units=_str_tuple(members))
    if ntype == "barrier":
        return spec.Barrier(id=nid, awaits=_str_tuple(node.get("awaits")))
    if ntype == "pipeline":
        stages = node.get("stages")
        if stages is None:
            stages = node.get("members")
        return spec.Pipeline(id=nid, stages=_str_tuple(stages))
    if ntype == "repair-loop":
        attempts = node.get("max_attempts")
        if type(attempts) is not int:
            attempts = 0
        return spec.RepairLoop(
            id=nid,
            body=str(node.get("body") or nid),
            review=str(node.get("review") or "review"),
            max_attempts=attempts if attempts >= 1 else 1,
        )
    raise TypeError(ntype)


def _as_workflow(repo: Path, doc: dict[str, Any]):
    spec = _spec(repo)
    pkg = _agentspec(repo)
    units = []
    nodes = []
    unknown: list[str] = []
    for node in doc.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        ntype = canonical_type(node.get("type"))
        if ntype == "unit" or ntype == "":
            units.append(_work_unit(spec, node))
            continue
        if ntype not in CLOSED_FIXTURE_TYPES:
            unknown.append(ntype or str(node.get("type")))
            continue
        if ntype == "unit":
            continue
        try:
            nodes.append(_typed_node(spec, node, ntype))
        except Exception:
            unknown.append(ntype)
    if not units:
        units.append(
            spec.WorkUnit(
                id="u1",
                prompt="placeholder",
                timeout_s=1800,
                receipt=spec.ReceiptSpec(fmt="json", required_fields=("status",)),
            )
        )
    wf = spec.Workflow(
        id=str(doc.get("id") or "wf"),
        spec_version=str(getattr(pkg, "SPEC_VERSION", "1")),
        units=tuple(units),
        nodes=tuple(nodes),
        budget_micro=100,
    )
    return wf, unknown


def validate(repo: Path, doc: Any) -> list[dict[str, str]]:
    if not available(repo):
        return [{"id": "validator-absent", "path": "/", "detail": "validate.py missing"}]
    if not isinstance(doc, dict):
        return [{"id": "type-mismatch", "path": "/", "detail": "workflow must be an object"}]
    try:
        wf, unknown = _as_workflow(repo, doc)
        out: list[dict[str, str]] = []
        if unknown:
            out.append(
                {
                    "id": "unknown-node-type",
                    "path": "/nodes",
                    "detail": "production Node union has no " + ",".join(sorted(set(unknown))),
                }
            )
        if not unknown:
            rows = _mod(repo).validate_workflow(wf)
            for row in rows:
                if isinstance(row, dict):
                    out.append(
                        {
                            "id": str(row.get("id") or ""),
                            "path": str(row.get("path") or ""),
                            "detail": str(row.get("detail") or ""),
                        }
                    )
                else:
                    out.append({"id": str(row), "path": "", "detail": ""})
    except Exception as exc:
        return [{"id": "validator-crash", "path": "/", "detail": f"{type(exc).__name__}: {exc}"}]
    return out


def ids_of(repo: Path, doc: Any) -> set[str]:
    return {row["id"] for row in validate(repo, doc) if row.get("id")}
