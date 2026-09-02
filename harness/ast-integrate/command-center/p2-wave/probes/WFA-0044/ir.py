"""Vendor-neutral workflow IR: parse, render, lint. Not an execution runtime.

Public operations are translation and validation only. There is no
execute/run/main/entrypoint. Adapters consume this IR; they do not import
a second workflow engine from this module.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

IR_VERSION = "wfa-ir-1"
RECORD_TYPE = "WorkflowIR"
REQUIRED_NODE_FIELDS = ("id", "kind", "source_anchor")
NODE_KINDS = (
    "workflow",
    "stage",
    "role",
    "gate",
    "tool_policy",
    "fanout",
    "barrier",
    "loop",
    "checkpoint",
    "retry",
    "resume",
    "stop",
    "lineage",
    "agent",
    "schema_fanin",
    "lossy",
)
BANNED_RUNTIME_FUNCS = frozenset(
    {"execute", "run", "run_workflow", "main", "entrypoint", "runtime_main"}
)
LOSSY_CLOCK = "Date.now"
LOSSY_ARGS_STRING = "args-as-string"
LOSSY_BACKGROUND = "fire-and-forget"
LOSSY_LIVE_BODY = "live-body-unavailable"
FILTER_BOOLEAN_RE = re.compile(r"\.filter\s*\(\s*Boolean\s*\)")
DATE_NOW_RE = re.compile(r"\bDate\.now\s*\(\s*\)")
IDENT_KEY_RE = re.compile(r"([\{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:")


def line_of(text: str, idx: int) -> int:
    return text[:idx].count("\n") + 1


def strip_line_comments(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    in_str: str | None = None
    escape = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == in_str:
                in_str = None
            i += 1
            continue
        if c in ('"', "'", "`"):
            in_str = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def extract_balanced(text: str, open_idx: int) -> tuple[str, int]:
    open_ch = text[open_idx]
    close_ch = {"(": ")", "[": "]", "{": "}"}[open_ch]
    depth = 0
    i = open_idx
    in_str: str | None = None
    escape = False
    while i < len(text):
        c = text[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == in_str:
                in_str = None
        else:
            if c in ('"', "'", "`"):
                in_str = c
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return text[open_idx + 1 : i], i + 1
        i += 1
    raise ValueError(f"unbalanced {open_ch} at {open_idx}")


def find_calls(text: str, name: str) -> list[tuple[int, int, str, int]]:
    out: list[tuple[int, int, str, int]] = []
    i = 0
    needle = name + "("
    while True:
        j = text.find(needle, i)
        if j < 0:
            break
        if j > 0 and (text[j - 1].isalnum() or text[j - 1] in "_$"):
            i = j + 1
            continue
        open_paren = j + len(name)
        inner, end = extract_balanced(text, open_paren)
        out.append((j, end, inner, line_of(text, j)))
        i = end
    return out


def _fix_trailing_commas(blob: str) -> str:
    return re.sub(r",(\s*[\]\}])", r"\1", blob)


def _quote_ident_keys(blob: str) -> str:
    return IDENT_KEY_RE.sub(r'\1"\2":', blob)


def parse_js_object(blob: str) -> dict[str, Any]:
    raw = blob.strip()
    if not raw:
        return {}
    if not raw.startswith("{"):
        raise ValueError("not an object")
    for candidate in (raw, _fix_trailing_commas(raw), _fix_trailing_commas(_quote_ident_keys(raw))):
        try:
            val = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(val, dict):
            return val
    raise ValueError(f"object is not JSON-subset: {raw[:120]}")


def parse_agent_inner(inner: str) -> dict[str, Any]:
    s = inner.strip()
    if s.startswith("{"):
        obj, _end = extract_balanced(s, 0)
        data = parse_js_object("{" + obj + "}")
        data["_form"] = "object"
        return data
    if s.startswith('"') or s.startswith("'"):
        quote = s[0]
        i = 1
        buf: list[str] = []
        escape = False
        while i < len(s):
            c = s[i]
            if escape:
                buf.append(c)
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                break
            else:
                buf.append(c)
            i += 1
        return {"_form": "string", "prompt": "".join(buf)}
    return {"_form": "opaque", "raw": s[:200]}


def parse_phase_inner(inner: str) -> tuple[str, str]:
    s = inner.strip()
    m = re.match(r"""^(['"])(.+?)\1\s*,""", s, re.S)
    if not m:
        raise ValueError("phase() first argument must be a string name")
    name = m.group(2)
    rest = s[m.end() :].strip()
    brace = rest.find("{")
    if brace < 0:
        return name, ""
    body, _ = extract_balanced(rest, brace)
    return name, body


def parse_loop_inner(inner: str) -> tuple[dict[str, Any], str]:
    s = inner.strip()
    if not s.startswith("{"):
        raise ValueError("loop() first argument must be an object")
    obj, end = extract_balanced(s, 0)
    cfg = parse_js_object("{" + obj + "}")
    rest = s[end:].lstrip()
    if rest.startswith(","):
        rest = rest[1:].lstrip()
    brace = rest.find("{")
    body = ""
    if brace >= 0:
        body, _ = extract_balanced(rest, brace)
    return cfg, body


def parse_stop_inner(inner: str) -> dict[str, Any]:
    s = inner.strip()
    if not s.startswith("{"):
        raise ValueError("stop() argument must be an object")
    obj, _ = extract_balanced(s, 0)
    return parse_js_object("{" + obj + "}")


def contained(start: int, end: int, outer_start: int, outer_end: int) -> bool:
    return start >= outer_start and end <= outer_end


def _stem(filename: str) -> str:
    p = Path(filename)
    return p.stem


def parse_source(text: str, filename: str) -> dict[str, Any]:
    """Parse the saved-workflow dialect subset into a semantic record."""
    cleaned = strip_line_comments(text)
    stem = _stem(filename)
    agents = find_calls(cleaned, "agent")
    parallels = find_calls(cleaned, "parallel")
    phases = find_calls(cleaned, "phase")
    loops = find_calls(cleaned, "loop")
    stops = find_calls(cleaned, "stop")
    barriers = [(m.start(), m.end(), m.group(0), line_of(cleaned, m.start())) for m in FILTER_BOOLEAN_RE.finditer(cleaned)]
    clocks = [(m.start(), m.end(), m.group(0), line_of(cleaned, m.start())) for m in DATE_NOW_RE.finditer(cleaned)]

    constructs: list[dict[str, Any]] = []
    claimed: set[tuple[str, int, int]] = set()

    def claim(kind: str, start: int, end: int) -> None:
        claimed.add((kind, start, end))

    def agent_record(start: int, end: int, inner: str, line: int, idx: int) -> dict[str, Any]:
        parsed = parse_agent_inner(inner)
        form = parsed.get("_form")
        rec: dict[str, Any] = {
            "kind": "agent",
            "id": f"{stem}:agent:{idx}",
            "source_anchor": f"{filename}:{line}",
            "prompt": parsed.get("prompt"),
            "role": parsed.get("role"),
            "tools": parsed.get("tools"),
            "schema": parsed.get("schema"),
            "gate": parsed.get("gate"),
            "retry": parsed.get("retry"),
            "checkpoint": parsed.get("checkpoint"),
            "resume": parsed.get("resume"),
            "lineage": parsed.get("lineage"),
            "background": parsed.get("background"),
            "form": form,
        }
        if form == "string":
            rec["lossy"] = LOSSY_ARGS_STRING
        if parsed.get("background") is True:
            rec["dispatch"] = "fire_and_forget"
            rec["lossy"] = LOSSY_BACKGROUND if form != "string" else rec.get("lossy")
            rec["lossy_extra"] = [LOSSY_BACKGROUND] if form == "string" else None
        return rec

    agent_recs: list[dict[str, Any]] = []
    for i, (start, end, inner, line) in enumerate(agents):
        rec = agent_record(start, end, inner, line, i)
        rec["_span"] = (start, end)
        agent_recs.append(rec)

    def agents_in_span(span_start: int, span_end: int) -> list[dict[str, Any]]:
        return [a for a in agent_recs if contained(a["_span"][0], a["_span"][1], span_start, span_end)]

    for i, (start, end, inner, line) in enumerate(parallels):
        kids = agents_in_span(start, end)
        for k in kids:
            claim("agent", k["_span"][0], k["_span"][1])
        fan = {
            "kind": "fanout",
            "id": f"{stem}:fanout:{i}",
            "source_anchor": f"{filename}:{line}",
            "width": len(kids),
            "children": [{kk: vv for kk, vv in k.items() if kk != "_span"} for k in kids],
        }
        schemas = [k.get("schema") for k in kids if k.get("schema")]
        if schemas:
            fan["schema_fanin"] = True
        constructs.append(fan)

    for i, (start, end, inner, line) in enumerate(phases):
        name, body = parse_phase_inner(inner)
        body_start = cleaned.find(body, start) if body else start
        body_end = body_start + len(body) if body else end
        kids = [
            a
            for a in agent_recs
            if contained(a["_span"][0], a["_span"][1], body_start, body_end)
            and ("agent", a["_span"][0], a["_span"][1]) not in claimed
        ]
        for k in kids:
            claim("agent", k["_span"][0], k["_span"][1])
        constructs.append(
            {
                "kind": "stage",
                "id": f"{stem}:stage:{i}",
                "source_anchor": f"{filename}:{line}",
                "name": name,
                "children": [{kk: vv for kk, vv in k.items() if kk != "_span"} for k in kids],
            }
        )

    for i, (start, end, inner, line) in enumerate(loops):
        cfg, body = parse_loop_inner(inner)
        body_start = cleaned.find(body, start) if body else start
        body_end = body_start + len(body) if body else end
        kids = [
            a
            for a in agent_recs
            if contained(a["_span"][0], a["_span"][1], body_start, body_end)
            and ("agent", a["_span"][0], a["_span"][1]) not in claimed
        ]
        for k in kids:
            claim("agent", k["_span"][0], k["_span"][1])
        constructs.append(
            {
                "kind": "loop",
                "id": f"{stem}:loop:{i}",
                "source_anchor": f"{filename}:{line}",
                "convergence": cfg.get("convergence") or cfg.get("until"),
                "max_iters": cfg.get("max_iters") or cfg.get("max"),
                "loop_id": cfg.get("id"),
                "children": [{kk: vv for kk, vv in k.items() if kk != "_span"} for k in kids],
            }
        )

    for a in agent_recs:
        if ("agent", a["_span"][0], a["_span"][1]) in claimed:
            continue
        constructs.append({kk: vv for kk, vv in a.items() if kk != "_span"})

    for i, (start, end, _raw, line) in enumerate(barriers):
        constructs.append(
            {
                "kind": "barrier",
                "id": f"{stem}:barrier:{i}",
                "source_anchor": f"{filename}:{line}",
                "join": "filter_boolean",
            }
        )

    for i, (_start, _end, inner, line) in enumerate(stops):
        cfg = parse_stop_inner(inner)
        constructs.append(
            {
                "kind": "stop",
                "id": f"{stem}:stop:{i}",
                "source_anchor": f"{filename}:{line}",
                "expr": cfg.get("expr"),
            }
        )

    for i, (_start, _end, _raw, line) in enumerate(clocks):
        constructs.append(
            {
                "kind": "lossy",
                "id": f"{stem}:lossy-clock:{i}",
                "source_anchor": f"{filename}:{line}",
                "code": LOSSY_CLOCK,
                "reason": "wall-clock is a banned non-determinism source; not an IR time primitive",
            }
        )

    def walk_agents(cons: dict[str, Any]) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if cons.get("kind") == "agent":
            found.append(cons)
        for child in cons.get("children") or []:
            found.extend(walk_agents(child))
        return found

    extra_lossy: list[dict[str, Any]] = []
    seen_lossy: set[str] = set()
    for rec in constructs:
        for agent in walk_agents(rec):
            if agent.get("form") == "string":
                lid = agent["id"] + ":lossy-args"
                if lid not in seen_lossy:
                    seen_lossy.add(lid)
                    extra_lossy.append(
                        {
                            "kind": "lossy",
                            "id": lid,
                            "source_anchor": agent["source_anchor"],
                            "code": LOSSY_ARGS_STRING,
                            "reason": "agent(string) is args-as-string; IR keeps the prompt and records the form",
                        }
                    )
            if agent.get("background") is True:
                lid = agent["id"] + ":lossy-bg"
                if lid not in seen_lossy:
                    seen_lossy.add(lid)
                    extra_lossy.append(
                        {
                            "kind": "lossy",
                            "id": lid,
                            "source_anchor": agent["source_anchor"],
                            "code": LOSSY_BACKGROUND,
                            "reason": "background dispatch is flagged, not normalised into a blocking agent",
                        }
                    )
    constructs.extend(extra_lossy)

    workflow = {
        "kind": "workflow",
        "id": f"{stem}:workflow:0",
        "source_anchor": f"{filename}:1",
        "filename": filename,
        "stem": stem,
    }
    return {
        "id": stem,
        "filename": filename,
        "workflow": workflow,
        "constructs": constructs,
    }


def _expand_agent_nodes(agent: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    base = {
        "id": agent["id"],
        "kind": "agent",
        "source_anchor": agent["source_anchor"],
        "prompt": agent.get("prompt"),
        "form": agent.get("form"),
        "dispatch": agent.get("dispatch") or "blocking",
        "background": agent.get("background"),
    }
    nodes.append(base)
    if agent.get("role"):
        nodes.append(
            {
                "id": agent["id"] + ":role",
                "kind": "role",
                "source_anchor": agent["source_anchor"],
                "name": agent["role"],
                "parent_id": agent["id"],
            }
        )
    if agent.get("tools"):
        nodes.append(
            {
                "id": agent["id"] + ":tools",
                "kind": "tool_policy",
                "source_anchor": agent["source_anchor"],
                "policy": agent["tools"],
                "parent_id": agent["id"],
            }
        )
    if agent.get("schema"):
        nodes.append(
            {
                "id": agent["id"] + ":schema",
                "kind": "schema_fanin",
                "source_anchor": agent["source_anchor"],
                "schema": agent["schema"],
                "parent_id": agent["id"],
            }
        )
    if agent.get("gate"):
        nodes.append(
            {
                "id": agent["id"] + ":gate",
                "kind": "gate",
                "source_anchor": agent["source_anchor"],
                "gate": agent["gate"],
                "parent_id": agent["id"],
                "blocking": bool((agent.get("gate") or {}).get("blocking", True)),
            }
        )
    if agent.get("retry"):
        nodes.append(
            {
                "id": agent["id"] + ":retry",
                "kind": "retry",
                "source_anchor": agent["source_anchor"],
                "retry": agent["retry"],
                "parent_id": agent["id"],
            }
        )
    if agent.get("checkpoint"):
        nodes.append(
            {
                "id": agent["id"] + ":checkpoint",
                "kind": "checkpoint",
                "source_anchor": agent["source_anchor"],
                "checkpoint": agent["checkpoint"],
                "parent_id": agent["id"],
            }
        )
    if agent.get("resume"):
        nodes.append(
            {
                "id": agent["id"] + ":resume",
                "kind": "resume",
                "source_anchor": agent["source_anchor"],
                "resume": agent["resume"],
                "parent_id": agent["id"],
            }
        )
    if agent.get("lineage"):
        nodes.append(
            {
                "id": agent["id"] + ":lineage",
                "kind": "lineage",
                "source_anchor": agent["source_anchor"],
                "lineage": agent["lineage"],
                "parent_id": agent["id"],
            }
        )
    return nodes


def to_ir(semantic: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [dict(semantic["workflow"])]
    edges: list[dict[str, str]] = []
    wf_id = semantic["workflow"]["id"]
    for cons in semantic["constructs"]:
        kind = cons["kind"]
        parent = wf_id
        if kind == "fanout":
            node = {
                "id": cons["id"],
                "kind": "fanout",
                "source_anchor": cons["source_anchor"],
                "width": cons["width"],
                "schema_fanin": bool(cons.get("schema_fanin")),
            }
            nodes.append(node)
            edges.append({"from": parent, "to": cons["id"], "rel": "contains"})
            for child in cons.get("children") or []:
                for n in _expand_agent_nodes(child):
                    if n["kind"] == "agent":
                        n["parent_id"] = cons["id"]
                    nodes.append(n)
                    edges.append({"from": cons["id"], "to": n["id"], "rel": "fanout-child"})
        elif kind == "stage":
            nodes.append(
                {
                    "id": cons["id"],
                    "kind": "stage",
                    "source_anchor": cons["source_anchor"],
                    "name": cons.get("name"),
                }
            )
            edges.append({"from": parent, "to": cons["id"], "rel": "contains"})
            for child in cons.get("children") or []:
                for n in _expand_agent_nodes(child):
                    if n["kind"] == "agent":
                        n["parent_id"] = cons["id"]
                    nodes.append(n)
                    edges.append({"from": cons["id"], "to": n["id"], "rel": "stage-child"})
        elif kind == "loop":
            nodes.append(
                {
                    "id": cons["id"],
                    "kind": "loop",
                    "source_anchor": cons["source_anchor"],
                    "convergence": cons.get("convergence"),
                    "max_iters": cons.get("max_iters"),
                    "loop_id": cons.get("loop_id"),
                }
            )
            edges.append({"from": parent, "to": cons["id"], "rel": "contains"})
            for child in cons.get("children") or []:
                for n in _expand_agent_nodes(child):
                    if n["kind"] == "agent":
                        n["parent_id"] = cons["id"]
                    nodes.append(n)
                    edges.append({"from": cons["id"], "to": n["id"], "rel": "loop-child"})
        elif kind == "agent":
            for n in _expand_agent_nodes(cons):
                nodes.append(n)
                edges.append({"from": parent, "to": n["id"], "rel": "contains"})
        else:
            node = {k: v for k, v in cons.items() if k != "children"}
            nodes.append(node)
            edges.append({"from": parent, "to": node["id"], "rel": "contains"})
    return {
        "record_type": RECORD_TYPE,
        "ir_version": IR_VERSION,
        "execution_semantics": "none",
        "id": semantic["id"],
        "filename": semantic["filename"],
        "nodes": nodes,
        "edges": edges,
    }


def _agent_from_nodes(nodes: list[dict[str, Any]], agent_id: str) -> dict[str, Any]:
    by_id = {n["id"]: n for n in nodes}
    agent = by_id[agent_id]
    rec: dict[str, Any] = {
        "kind": "agent",
        "id": agent["id"],
        "source_anchor": agent["source_anchor"],
        "prompt": agent.get("prompt"),
        "form": agent.get("form"),
        "background": agent.get("background"),
        "dispatch": agent.get("dispatch"),
    }
    for n in nodes:
        if n.get("parent_id") != agent_id:
            continue
        if n["kind"] == "role":
            rec["role"] = n.get("name")
        elif n["kind"] == "tool_policy":
            rec["tools"] = n.get("policy")
        elif n["kind"] == "schema_fanin":
            rec["schema"] = n.get("schema")
        elif n["kind"] == "gate":
            rec["gate"] = n.get("gate")
        elif n["kind"] == "retry":
            rec["retry"] = n.get("retry")
        elif n["kind"] == "checkpoint":
            rec["checkpoint"] = n.get("checkpoint")
        elif n["kind"] == "resume":
            rec["resume"] = n.get("resume")
        elif n["kind"] == "lineage":
            rec["lineage"] = n.get("lineage")
    return rec


def from_ir(ir: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a semantic record from IR nodes only. Does not read source text."""
    nodes = list(ir.get("nodes") or [])
    edges = list(ir.get("edges") or [])
    children_of: dict[str, list[str]] = {}
    for e in edges:
        children_of.setdefault(e["from"], []).append(e["to"])
    wf = next(n for n in nodes if n.get("kind") == "workflow")
    constructs: list[dict[str, Any]] = []
    seen_agents: set[str] = set()
    for n in nodes:
        kind = n.get("kind")
        if kind == "workflow":
            continue
        if kind == "fanout":
            kids = []
            for cid in children_of.get(n["id"], []):
                child = next((x for x in nodes if x["id"] == cid), None)
                if child and child.get("kind") == "agent":
                    kids.append(_agent_from_nodes(nodes, cid))
                    seen_agents.add(cid)
            constructs.append(
                {
                    "kind": "fanout",
                    "id": n["id"],
                    "source_anchor": n["source_anchor"],
                    "width": n.get("width", len(kids)),
                    "schema_fanin": n.get("schema_fanin"),
                    "children": kids,
                }
            )
        elif kind == "stage":
            kids = []
            for cid in children_of.get(n["id"], []):
                child = next((x for x in nodes if x["id"] == cid), None)
                if child and child.get("kind") == "agent":
                    kids.append(_agent_from_nodes(nodes, cid))
                    seen_agents.add(cid)
            constructs.append(
                {
                    "kind": "stage",
                    "id": n["id"],
                    "source_anchor": n["source_anchor"],
                    "name": n.get("name"),
                    "children": kids,
                }
            )
        elif kind == "loop":
            kids = []
            for cid in children_of.get(n["id"], []):
                child = next((x for x in nodes if x["id"] == cid), None)
                if child and child.get("kind") == "agent":
                    kids.append(_agent_from_nodes(nodes, cid))
                    seen_agents.add(cid)
            constructs.append(
                {
                    "kind": "loop",
                    "id": n["id"],
                    "source_anchor": n["source_anchor"],
                    "convergence": n.get("convergence"),
                    "max_iters": n.get("max_iters"),
                    "loop_id": n.get("loop_id"),
                    "children": kids,
                }
            )
        elif kind == "agent":
            if n["id"] in seen_agents:
                continue
            if n.get("parent_id") and n.get("parent_id") != wf["id"]:
                continue
            constructs.append(_agent_from_nodes(nodes, n["id"]))
            seen_agents.add(n["id"])
        elif kind in {"barrier", "stop", "lossy"}:
            constructs.append({k: v for k, v in n.items()})
    return {
        "id": ir.get("id") or wf["id"],
        "filename": ir.get("filename") or wf.get("filename"),
        "workflow": wf,
        "constructs": constructs,
    }


def _js_obj(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _render_agent(agent: dict[str, Any]) -> str:
    if agent.get("form") == "string":
        prompt = json.dumps(agent.get("prompt") or "", ensure_ascii=False)
        return f"agent({prompt})"
    payload: dict[str, Any] = {}
    for key in (
        "prompt",
        "role",
        "tools",
        "schema",
        "gate",
        "retry",
        "checkpoint",
        "resume",
        "lineage",
        "background",
    ):
        if agent.get(key) is not None:
            payload[key] = agent[key]
    return f"agent({_js_obj(payload)})"


def render_source(semantic: dict[str, Any]) -> str:
    """Canonical dialect render. Semantic equivalence, not original formatting."""
    lines = [
        f"// canonical-render id={semantic.get('id')}",
        "export async function workflow({ agent, parallel, phase, loop, stop }) {",
    ]
    for cons in semantic["constructs"]:
        kind = cons["kind"]
        if kind == "lossy" and cons.get("code") == LOSSY_CLOCK:
            lines.append("  const __clock = Date.now();")
        elif kind == "fanout":
            inner = ",\n    ".join(_render_agent(c) for c in cons.get("children") or [])
            lines.append("  const __fan = await parallel([")
            lines.append(f"    {inner}")
            lines.append("  ]);")
        elif kind == "barrier":
            lines.append("  const __joined = __fan.filter(Boolean);")
        elif kind == "stage":
            name = json.dumps(cons.get("name") or "unnamed")
            body = "\n".join(
                "    " + _render_agent(c) + ";" for c in cons.get("children") or []
            )
            lines.append(f"  await phase({name}, async () => {{")
            if body:
                lines.append(body)
            lines.append("  });")
        elif kind == "loop":
            cfg = {
                "id": cons.get("loop_id"),
                "convergence": cons.get("convergence"),
                "max_iters": cons.get("max_iters"),
            }
            body = "\n".join(
                "    " + _render_agent(c) + ";" for c in cons.get("children") or []
            )
            lines.append(f"  await loop({_js_obj(cfg)}, async () => {{")
            if body:
                lines.append(body)
            lines.append("  });")
        elif kind == "agent":
            lines.append(f"  await {_render_agent(cons)};")
        elif kind == "stop":
            lines.append(f"  stop({_js_obj({'expr': cons.get('expr')})});")
        elif kind == "lossy":
            continue
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _agent_proj(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "agent",
        "prompt": agent.get("prompt"),
        "role": agent.get("role"),
        "tools": agent.get("tools"),
        "schema": agent.get("schema"),
        "gate": agent.get("gate"),
        "retry": agent.get("retry"),
        "checkpoint": agent.get("checkpoint"),
        "resume": agent.get("resume"),
        "lineage": agent.get("lineage"),
        "background": agent.get("background"),
        "form": agent.get("form"),
        "dispatch": agent.get("dispatch") or ("fire_and_forget" if agent.get("background") is True else "blocking"),
    }


def projection(semantic: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cons in semantic["constructs"]:
        kind = cons["kind"]
        if kind == "agent":
            rows.append(_agent_proj(cons))
        elif kind == "fanout":
            rows.append(
                {
                    "kind": "fanout",
                    "width": cons.get("width"),
                    "schema_fanin": bool(cons.get("schema_fanin")),
                    "children": [_agent_proj(c) for c in cons.get("children") or []],
                }
            )
        elif kind == "stage":
            rows.append(
                {
                    "kind": "stage",
                    "name": cons.get("name"),
                    "children": [_agent_proj(c) for c in cons.get("children") or []],
                }
            )
        elif kind == "loop":
            rows.append(
                {
                    "kind": "loop",
                    "convergence": cons.get("convergence"),
                    "max_iters": cons.get("max_iters"),
                    "loop_id": cons.get("loop_id"),
                    "children": [_agent_proj(c) for c in cons.get("children") or []],
                }
            )
        elif kind == "barrier":
            rows.append({"kind": "barrier", "join": cons.get("join")})
        elif kind == "stop":
            rows.append({"kind": "stop", "expr": cons.get("expr")})
        elif kind == "lossy":
            rows.append({"kind": "lossy", "code": cons.get("code")})
    return rows


def field_by_field(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    a = projection(left)
    b = projection(right)
    mismatches: list[str] = []
    if len(a) != len(b):
        mismatches.append(f"construct_count {len(a)}!={len(b)}")
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            mismatches.append(f"construct[{i}] {x} != {y}")
    extra = abs(len(a) - len(b))
    if extra:
        mismatches.append(f"unpaired={extra}")
    return mismatches


def validate_anchors(ir: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = ir.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return ["nodes-missing"]
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"node[{i}] not object")
            continue
        for field in REQUIRED_NODE_FIELDS:
            val = node.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"node[{i}].{field} missing")
        kind = node.get("kind")
        if kind not in NODE_KINDS:
            errors.append(f"node[{i}].kind {kind!r} not in NODE_KINDS")
    return errors


def lint_module_not_runtime(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    funcs: list[str] = []
    main_guard = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node.name)
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
            ):
                main_guard = True
    banned = sorted(set(funcs) & BANNED_RUNTIME_FUNCS)
    return {
        "path": str(path),
        "main_guard": main_guard,
        "banned_funcs": banned,
        "ok": (not main_guard) and (not banned),
        "note": "IR library must not define a runtime entrypoint",
    }


def lossy_codes(semantic: dict[str, Any]) -> list[str]:
    return [
        str(c.get("code"))
        for c in semantic["constructs"]
        if c.get("kind") == "lossy" and c.get("code")
    ]


def all_nodes_anchored(semantic: dict[str, Any]) -> bool:
    ir = to_ir(semantic)
    return not validate_anchors(ir)
