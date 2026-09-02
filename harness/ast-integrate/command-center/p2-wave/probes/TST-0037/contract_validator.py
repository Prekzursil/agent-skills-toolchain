"""Independent contract validator for the TST-0037 workflow-DSL suite.

This is the suite written BEFORE broad implementation of the five constructs
the production closed set still rejects as unknown-node-type. Fan-out and
barrier reuse the production violation ids so both-states can be compared.
"""
from __future__ import annotations

from typing import Any

from constructs import canonical_type

CONTRACT_TYPES = frozenset(
    {
        "unit",
        "fan-out",
        "barrier",
        "loop-with-convergence",
        "human-checkpoint",
        "subworkflow",
        "retry",
        "resume",
        "pipeline",
        "repair-loop",
    }
)


def _v(vid: str, path: str, detail: str) -> dict[str, str]:
    return {"id": vid, "path": path, "detail": detail}


def _ids(nodes: list[Any]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("id"), str) and node["id"]:
            out[node["id"]] = node
    return out


def _cycle(parent_id: str, ref: str, library: dict, node_id: str) -> bool:
    if not ref:
        return False
    if ref == parent_id or ref == node_id:
        return True
    seen = {parent_id, node_id}
    stack = [ref]
    while stack:
        cur = stack.pop()
        if cur in seen:
            return True
        seen.add(cur)
        child = library.get(cur)
        if not isinstance(child, dict):
            continue
        for nested in child.get("nodes") or []:
            if not isinstance(nested, dict):
                continue
            if canonical_type(nested.get("type")) == "subworkflow":
                nxt = nested.get("workflow_ref")
                if isinstance(nxt, str) and nxt:
                    stack.append(nxt)
    return False


def validate(doc: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(doc, dict):
        return [_v("type-mismatch", "/", "workflow must be an object")]
    nodes = doc.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return [_v("empty-workflow", "/nodes", "workflow has no nodes")]
    by_id = _ids(nodes)
    known = set(by_id)
    parent_id = str(doc.get("id") or "root")
    library = doc.get("workflows") if isinstance(doc.get("workflows"), dict) else {}

    for index, node in enumerate(nodes):
        path = f"/nodes/{index}"
        if not isinstance(node, dict):
            out.append(_v("type-mismatch", path, "node must be an object"))
            continue
        nid = node.get("id")
        ntype = canonical_type(node.get("type"))
        if ntype not in CONTRACT_TYPES:
            out.append(
                _v(
                    "unknown-node-type",
                    f"{path}/type",
                    f"{node.get('type')!r} is outside the TST-0037 contract set",
                )
            )
            continue

        if ntype == "fan-out":
            members = node.get("members")
            if not isinstance(members, list):
                out.append(_v("type-mismatch", f"{path}/members", "members must be a list"))
            elif len(members) == 0:
                out.append(_v("fanout-empty", f"{path}/members", "FanOut.members is empty"))
            else:
                for member in members:
                    if member not in known:
                        out.append(
                            _v(
                                "fanout-unknown-member",
                                f"{path}/members",
                                f"FanOut member {member!r} does not exist",
                            )
                        )

        if ntype == "barrier":
            awaits = node.get("awaits")
            if not isinstance(awaits, list):
                out.append(_v("type-mismatch", f"{path}/awaits", "awaits must be a list"))
            elif len(awaits) == 0:
                out.append(
                    _v("barrier-empty-awaits", f"{path}/awaits", "Barrier.awaits is empty")
                )
            else:
                for awaited in awaits:
                    if awaited not in known:
                        out.append(
                            _v(
                                "barrier-awaits-unknown",
                                f"{path}/awaits",
                                f"Barrier awaits unknown node {awaited!r}",
                            )
                        )

        if ntype == "loop-with-convergence":
            expr = node.get("convergence_expr")
            bound = node.get("max_iterations")
            has_expr = isinstance(expr, str) and bool(expr.strip())
            has_bound = isinstance(bound, int) and not isinstance(bound, bool) and bound >= 1
            if not has_expr and not has_bound:
                out.append(
                    _v(
                        "loop-unbounded",
                        path,
                        "Loop has neither convergence_expr nor max_iterations >= 1",
                    )
                )
            body = node.get("body")
            if not isinstance(body, str) or not body.strip():
                out.append(_v("missing-required-field", path, "loop body is required"))

        if ntype == "human-checkpoint":
            prompt = node.get("prompt_ref")
            if not isinstance(prompt, str) or not prompt.strip():
                out.append(
                    _v(
                        "checkpoint-missing-prompt",
                        f"{path}/prompt_ref",
                        "HumanCheckpoint.prompt_ref is missing",
                    )
                )

        if ntype == "subworkflow":
            ref = node.get("workflow_ref")
            if not isinstance(ref, str) or not ref.strip():
                out.append(
                    _v("missing-required-field", path, "subworkflow workflow_ref is required")
                )
            else:
                if _cycle(parent_id, ref, library, str(nid or "")):
                    out.append(
                        _v(
                            "subworkflow-cycle",
                            f"{path}/workflow_ref",
                            f"subworkflow {ref!r} forms a reference cycle",
                        )
                    )
                elif ref not in library and ref not in known:
                    out.append(
                        _v(
                            "subworkflow-unknown-ref",
                            f"{path}/workflow_ref",
                            f"subworkflow {ref!r} is not in the library",
                        )
                    )
            ns = node.get("id_namespace")
            if not isinstance(ns, str) or not ns.strip():
                out.append(_v("missing-required-field", path, "id_namespace is required"))

        if ntype == "retry":
            attempts = node.get("max_attempts")
            if (
                not isinstance(attempts, int)
                or isinstance(attempts, bool)
                or attempts < 1
            ):
                out.append(
                    _v(
                        "retry-unbounded",
                        f"{path}/max_attempts",
                        "retry max_attempts must be an int >= 1",
                    )
                )
            target = node.get("target")
            if not isinstance(target, str) or target not in known:
                out.append(
                    _v("unknown-ref", f"{path}/target", f"retry target {target!r} is missing")
                )

        if ntype == "resume":
            token = node.get("from_token")
            if not isinstance(token, str) or not token.strip():
                out.append(
                    _v(
                        "resume-missing-token",
                        f"{path}/from_token",
                        "resume from_token is missing",
                    )
                )
            href = node.get("checkpoint_ref")
            if isinstance(href, str) and href and href not in known:
                out.append(
                    _v(
                        "unknown-ref",
                        f"{path}/checkpoint_ref",
                        f"resume checkpoint_ref {href!r} is missing",
                    )
                )

    return out


def ids_of(doc: Any) -> set[str]:
    return {row["id"] for row in validate(doc)}
