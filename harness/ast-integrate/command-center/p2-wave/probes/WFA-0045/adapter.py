#!/usr/bin/env python3
"""Semantic adapter: saved-Workflow dialect -> local workflow IR.

Walks the JS AST with dialect meaning (phase nesting, agent options,
schema fan-in, filter(Boolean) barriers, isolation flags). Refuses a
file on a malformed phase rather than emitting a partial IR. Surfaces
args-as-string, Date.now(), and background/fire-and-forget without
normalising the last into a blocking call.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jsparse import ParseError, callee_name, is_filter_boolean, parse_js, walk


class DialectReject(Exception):
    def __init__(self, reason: str, loc: dict[str, int] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.loc = loc or {"line": 0, "column": 0}


def _lit_str(node: dict[str, Any] | None) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Literal" and isinstance(node.get("value"), str):
        return node["value"]
    return None


def _ident(node: dict[str, Any] | None) -> str | None:
    if isinstance(node, dict) and node.get("type") == "Identifier":
        return str(node.get("name") or "")
    return None


def _obj_props(node: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(node, dict) or node.get("type") != "ObjectExpression":
        return {}
    out: dict[str, dict[str, Any]] = {}
    for prop in node.get("properties") or []:
        if not isinstance(prop, dict):
            continue
        key = prop.get("key") or {}
        name = key.get("name") if key.get("type") == "Identifier" else key.get("value")
        if isinstance(name, str):
            out[name] = prop.get("value") or {}
    return out


def _bool(node: dict[str, Any] | None) -> bool | None:
    if isinstance(node, dict) and node.get("type") == "Literal" and isinstance(node.get("value"), bool):
        return bool(node["value"])
    return None


def _anchor(node: dict[str, Any], file: str) -> dict[str, Any]:
    loc = node.get("loc") or {"line": 0, "column": 0}
    return {"file": file, "line": int(loc.get("line") or 0), "column": int(loc.get("column") or 0)}


def _is_fn(node: dict[str, Any] | None) -> bool:
    if not isinstance(node, dict):
        return False
    return node.get("type") in {
        "ArrowFunctionExpression",
        "FunctionExpression",
        "FunctionDeclaration",
    }


def _children(node: dict[str, Any]) -> list[Any]:
    skip = {"type", "loc", "file", "raw", "operator", "kind", "name", "value"}
    out: list[Any] = []
    for key, val in node.items():
        if key in skip:
            continue
        out.append(val)
    return out


class SemanticExtractor:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.nodes: list[dict[str, Any]] = []
        self.defects: list[dict[str, Any]] = []
        self.uncarried: list[dict[str, Any]] = []
        self.counts = {"agent": 0, "phase": 0, "schema": 0, "barrier": 0}
        self._ids = 0
        self._phase_stack: list[str] = []
        self.rejected: str | None = None
        self.reject_loc: dict[str, int] | None = None

    def nid(self, prefix: str) -> str:
        self._ids += 1
        return f"{prefix}-{self._ids}"

    def reject(self, reason: str, node: dict[str, Any]) -> None:
        self.rejected = reason
        self.reject_loc = node.get("loc") or {"line": 0, "column": 0}
        raise DialectReject(reason, self.reject_loc)

    def emit(self, kind: str, node: dict[str, Any], **fields: Any) -> dict[str, Any]:
        ir = {
            "id": self.nid(kind),
            "kind": kind,
            "source_anchor": _anchor(node, self.filename),
            "phase": list(self._phase_stack),
        }
        ir.update(fields)
        if not ir.get("source_anchor") or not ir["source_anchor"].get("file"):
            self.reject("ir-node-missing-source-anchor", node)
        self.nodes.append(ir)
        return ir

    def note_defect(self, code: str, node: dict[str, Any], detail: str) -> None:
        self.defects.append(
            {
                "code": code,
                "detail": detail,
                "source_anchor": _anchor(node, self.filename),
            }
        )

    def note_uncarried(self, construct: str, node: dict[str, Any], detail: str) -> None:
        self.uncarried.append(
            {
                "construct": construct,
                "detail": detail,
                "source_anchor": _anchor(node, self.filename),
                "ledger": "lossy-field",
            }
        )

    def extract(self, node: Any) -> None:
        if self.rejected:
            return
        if isinstance(node, list):
            for item in node:
                self.extract(item)
            return
        if not isinstance(node, dict) or "type" not in node:
            return
        typ = node.get("type")
        if typ == "CallExpression":
            self._call(node)
            return
        if typ == "MemberExpression":
            self._member_maybe_date(node)
        for child in _children(node):
            self.extract(child)

    def _member_maybe_date(self, node: dict[str, Any]) -> None:
        name = callee_name(node)
        if name == "Date.now":
            # counted when called; here we only see the member
            return

    def _call(self, node: dict[str, Any]) -> None:
        name = callee_name(node.get("callee"))
        if name == "phase":
            self._phase(node)
            return
        if name == "agent":
            self._agent(node)
            return
        if name == "parallel":
            self._parallel(node)
            return
        if name == "schema":
            self._schema(node)
            return
        if is_filter_boolean(node):
            self._barrier(node)
            return
        if name == "Date.now":
            self.note_defect(
                "NONDETERMINISTIC_DATE_NOW",
                node,
                "Date.now() is a known runtime non-determinism defect and cannot be a deterministic IR input",
            )
            self.note_uncarried(
                "Date.now",
                node,
                "wall-clock source has no lossless IR field; recorded rather than dropped",
            )
            return
        for child in _children(node):
            self.extract(child)

    def _phase(self, node: dict[str, Any]) -> None:
        args = node.get("arguments") or []
        if len(args) < 2:
            self.reject("malformed-phase:missing-name-or-body", node)
        name = _lit_str(args[0])
        body = args[1]
        if not name:
            self.reject("malformed-phase:name-not-string-literal", node)
        if not _is_fn(body):
            self.reject("malformed-phase:body-not-function", node)
        self.counts["phase"] += 1
        ir = self.emit("stage", node, name=name, role="phase")
        self._phase_stack.append(name)
        try:
            self.extract(body)
        finally:
            self._phase_stack.pop()
        extra = args[2:]
        if extra:
            self.note_uncarried(
                "phase-extra-args",
                node,
                f"phase {name!r} has {len(extra)} extra args the IR does not carry",
            )
        return ir

    def _agent(self, node: dict[str, Any]) -> None:
        self.counts["agent"] += 1
        args = node.get("arguments") or []
        blocking = True
        prompt = None
        isolation: dict[str, Any] = {}
        fire_forget = False
        if args and _lit_str(args[0]) is not None:
            prompt = _lit_str(args[0])
            self.note_defect(
                "ARGS_AS_STRING",
                node,
                "agent() received a string argument; known runtime defect vs options object",
            )
        elif args:
            props = _obj_props(args[0])
            prompt = _lit_str(props.get("prompt")) or _lit_str(props.get("args"))
            if "args" in props and _lit_str(props.get("args")) is not None:
                self.note_defect(
                    "ARGS_AS_STRING",
                    node,
                    "agent({args: string}) is the args-as-string defect",
                )
            iso = props.get("isolation") or {}
            iso_props = _obj_props(iso) if iso else {}
            wt = _bool(iso_props.get("worktree"))
            if wt is True:
                isolation["worktree"] = True
            bg = _bool(props.get("background"))
            ff = _bool(props.get("fireAndForget")) or _bool(props.get("fire_and_forget"))
            run_bg = _bool(props.get("runInBackground"))
            if bg is True or ff is True or run_bg is True:
                fire_forget = True
                blocking = False
                self.note_defect(
                    "BACKGROUND_DISPATCH",
                    node,
                    "background/fire-and-forget dispatch flagged; not normalised to a blocking call",
                )
            for key in props:
                if key not in {
                    "prompt",
                    "args",
                    "isolation",
                    "background",
                    "fireAndForget",
                    "fire_and_forget",
                    "runInBackground",
                    "schema",
                    "timeout",
                    "model",
                }:
                    self.note_uncarried(
                        f"agent-option:{key}",
                        node,
                        f"agent option {key!r} has no IR field",
                    )
        else:
            self.note_uncarried("agent-empty", node, "agent() with no arguments")
        kind = "dispatch"
        self.emit(
            kind,
            node,
            prompt=prompt,
            blocking=blocking,
            fire_and_forget=fire_forget,
            isolation=isolation,
            role="agent",
        )
        for arg in args:
            # still walk nested expressions inside options (Date.now in prompt concat etc.)
            if _lit_str(arg) is None:
                self.extract(arg)

    def _parallel(self, node: dict[str, Any]) -> None:
        args = node.get("arguments") or []
        ir = self.emit(
            "fanout",
            node,
            degree=len(args),
            role="parallel",
            blocking=True,
        )
        for arg in args:
            self.extract(arg)
        return ir

    def _schema(self, node: dict[str, Any]) -> None:
        self.counts["schema"] += 1
        args = node.get("arguments") or []
        props = _obj_props(args[0]) if args else {}
        fields = sorted(k for k in props if k != "type")
        self.emit("schema_fanin", node, fields=fields, role="schema")
        for arg in args:
            self.extract(arg)

    def _barrier(self, node: dict[str, Any]) -> None:
        self.counts["barrier"] += 1
        self.emit(
            "barrier",
            node,
            predicate="Boolean",
            form="filter(Boolean)",
            role="fan-in-barrier",
            blocking=True,
        )
        callee = node.get("callee") or {}
        self.extract(callee.get("object"))


def adapt_source(src: str, filename: str) -> dict[str, Any]:
    try:
        ast = parse_js(src, filename)
    except ParseError as exc:
        return {
            "ok": False,
            "filename": filename,
            "error": f"js-parse:{exc}",
            "ir": None,
            "counts": {"agent": 0, "phase": 0, "schema": 0, "barrier": 0},
            "defects": [],
            "uncarried": [],
            "partial": False,
        }
    ext = SemanticExtractor(filename)
    try:
        ext.extract(ast)
    except DialectReject as exc:
        return {
            "ok": False,
            "filename": filename,
            "error": exc.reason,
            "ir": None,
            "counts": {"agent": 0, "phase": 0, "schema": 0, "barrier": 0},
            "defects": [],
            "uncarried": [],
            "partial": False,
            "reject_loc": exc.loc,
        }
    return {
        "ok": True,
        "filename": filename,
        "error": None,
        "ir": {
            "kind": "workflow-ir",
            "source": filename,
            "nodes": ext.nodes,
            "execution_entrypoint": None,
        },
        "counts": ext.counts,
        "defects": ext.defects,
        "uncarried": ext.uncarried,
        "partial": False,
    }


def adapt_file(path: Path) -> dict[str, Any]:
    return adapt_source(path.read_text(encoding="utf-8"), path.name)


def has_runtime_entrypoint(ir: dict[str, Any] | None) -> bool:
    if not ir:
        return False
    if ir.get("execution_entrypoint"):
        return True
    for node in ir.get("nodes") or []:
        if node.get("runtime") or node.get("entrypoint"):
            return True
    return False


def date_now_sites(src: str, filename: str) -> int:
    ast = parse_js(src, filename)
    n = 0
    for node in walk(ast):
        if node.get("type") == "CallExpression" and callee_name(node.get("callee")) == "Date.now":
            n += 1
    return n
