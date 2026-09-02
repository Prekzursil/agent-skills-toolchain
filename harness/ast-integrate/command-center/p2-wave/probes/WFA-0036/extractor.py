#!/usr/bin/env python3
"""Declared-only stage extractor.

Turns a candidate native form into an ordered typed stage list
(name, inputs, outputs, gate, fan_out_degree). Returns HONEST-NULL when
the source declares no stages. Never infers a pipeline from prose,
hints, or verb sequences.
"""
from __future__ import annotations

import json
import re
from typing import Any

HONEST_NULL = "HONEST-NULL"
STAGE_KEYS = ("stages", "steps", "phases")
FANOUT_KEYS = ("fan_out", "fanout", "fan_out_degree", "fan-out", "parallelism")
NAME_KEYS = ("name", "id", "title")
INPUT_KEYS = ("inputs", "in", "input")
OUTPUT_KEYS = ("outputs", "out", "output")
GATE_KEYS = ("gate", "gate", "checkpoint")

PHASE_CALL_RE = re.compile(
    r"""\b(?P<kind>phase|step)\s*\(\s*(['"])(?P<name>[^'"]+)\2""",
    re.MULTILINE,
)
PARALLEL_CALL_RE = re.compile(r"""\bparallel\s*\(\s*\[(?P<body>.*?)\]""", re.DOTALL)
AGENT_CALL_RE = re.compile(r"""\bagent\s*\(\s*(['"])([^'"]+)\1""")
MD_HEADING_RE = re.compile(
    r"^(#{1,6})\s*Stage\s*:?\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)
PHASE_RE = PHASE_CALL_RE
PARALLEL_RE = PARALLEL_CALL_RE
AGENT_RE = AGENT_CALL_RE
MD_STAGE_RE = MD_HEADING_RE


def is_honest_null(value: Any) -> bool:
    return value == HONEST_NULL


def parse_fan_out(raw: Any) -> int | None:
    """Number or JSON null. Prose ('many workers') is null, never stored."""
    if raw is None or raw is False or raw is True:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
        return None
    return None


def _as_io(raw: Any) -> Any:
    if raw is None:
        return HONEST_NULL
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return HONEST_NULL
        if "," in text:
            return [p.strip() for p in text.split(",") if p.strip()]
        return [text]
    if isinstance(raw, (list, tuple)):
        out = [str(x).strip() for x in raw if str(x).strip()]
        return out if out else HONEST_NULL
    return HONEST_NULL


def _as_gate(raw: Any) -> Any:
    if raw is None:
        return HONEST_NULL
    if isinstance(raw, str):
        text = raw.strip()
        return text if text else HONEST_NULL
    return HONEST_NULL


def _as_name(raw: Any) -> Any:
    if raw is None:
        return HONEST_NULL
    text = str(raw).strip()
    return text if text else HONEST_NULL


def normalize_stage(raw: dict[str, Any], order: int) -> dict[str, Any]:
    name = HONEST_NULL
    for key in NAME_KEYS:
        if key in raw:
            name = _as_name(raw.get(key))
            break
    inputs = HONEST_NULL
    for key in INPUT_KEYS:
        if key in raw:
            inputs = _as_io(raw.get(key))
            break
    outputs = HONEST_NULL
    for key in OUTPUT_KEYS:
        if key in raw:
            outputs = _as_io(raw.get(key))
            break
    gate = HONEST_NULL
    for key in GATE_KEYS:
        if key in raw:
            gate = _as_gate(raw.get(key))
            break
    fan_raw = None
    fan_present = False
    for key in FANOUT_KEYS:
        if key in raw:
            fan_raw = raw.get(key)
            fan_present = True
            break
    return {
        "order": order,
        "name": name,
        "inputs": inputs,
        "outputs": outputs,
        "gate": gate,
        "fan_out_degree": parse_fan_out(fan_raw) if fan_present else None,
    }


def extract_from_mapping(obj: dict[str, Any]) -> Any:
    for key in STAGE_KEYS:
        if key not in obj:
            continue
        value = obj[key]
        if not isinstance(value, list):
            continue
        if len(value) == 0:
            return HONEST_NULL
        if all(isinstance(item, dict) for item in value):
            return [normalize_stage(item, i + 1) for i, item in enumerate(value)]
        return HONEST_NULL
    return None


def _object_after_phase(src: str, match: re.Match[str]) -> dict[str, Any]:
    tail = src[match.end() :].lstrip()
    if not tail.startswith(","):
        return {}
    tail = tail[1:].lstrip()
    if not tail.startswith("{"):
        return {}
    depth = 0
    end = None
    for i, ch in enumerate(tail):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return {}
    blob = tail[:end]
    out: dict[str, Any] = {}
    for field, keys in (
        ("inputs", INPUT_KEYS),
        ("outputs", OUTPUT_KEYS),
        ("gate", GATE_KEYS),
        ("fan_out", FANOUT_KEYS),
    ):
        for key in keys:
            arr = re.search(
                rf"""(?:["']?{re.escape(key)}["']?)\s*:\s*\[([^\]]*)\]""",
                blob,
            )
            if arr:
                items = [
                    p.strip().strip("'\"")
                    for p in arr.group(1).split(",")
                    if p.strip().strip("'\"")
                ]
                out[field] = items
                break
            sca = re.search(
                rf"""(?:["']?{re.escape(key)}["']?)\s*:\s*(['"])(.*?)\1""",
                blob,
            )
            if sca:
                out[field] = sca.group(2)
                break
            num = re.search(
                rf"""(?:["']?{re.escape(key)}["']?)\s*:\s*(-?\d+)""",
                blob,
            )
            if num and field == "fan_out":
                out[field] = int(num.group(1))
                break
    return out


def extract_from_js(src: str) -> Any:
    stages: list[dict[str, Any]] = []
    consumed: list[tuple[int, int]] = []

    for match in PHASE_CALL_RE.finditer(src):
        extra = _object_after_phase(src, match)
        depth = 1
        i = match.end()
        while i < len(src) and depth > 0:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
            i += 1
        call_rest = src[match.end() : i]
        par = PARALLEL_CALL_RE.search(call_rest)
        fan = extra.get("fan_out")
        if par is not None:
            agents = AGENT_CALL_RE.findall(par.group("body"))
            if agents:
                fan = len(agents)
                consumed.append((match.end() + par.start(), match.end() + par.end()))
        raw: dict[str, Any] = {"name": match.group("name")}
        if extra.get("inputs") is not None:
            raw["inputs"] = extra["inputs"]
        if extra.get("outputs") is not None:
            raw["outputs"] = extra["outputs"]
        if extra.get("gate") is not None:
            raw["gate"] = extra["gate"]
        if fan is not None:
            raw["fan_out"] = fan
        stages.append(normalize_stage(raw, len(stages) + 1))

    for match in PARALLEL_CALL_RE.finditer(src):
        span = (match.start(), match.end())
        if any(span[0] >= u[0] and span[1] <= u[1] for u in consumed):
            continue
        prefix = src[max(0, match.start() - 120) : match.start()]
        if re.search(r"""\b(?:phase|step)\s*\(\s*['"][^'"]+['"]\s*,\s*$""", prefix):
            continue
        agents = AGENT_CALL_RE.findall(match.group("body"))
        if not agents:
            continue
        stages.append(
            normalize_stage({"name": "parallel", "fan_out": len(agents)}, len(stages) + 1)
        )

    if not stages:
        return HONEST_NULL
    for i, stage in enumerate(stages, 1):
        stage["order"] = i
    return stages


def extract_from_markdown(src: str) -> Any:
    matches = list(MD_STAGE_RE.finditer(src))
    if not matches:
        return HONEST_NULL
    stages: list[dict[str, Any]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(src)
        block = src[start:end]
        raw: dict[str, Any] = {"name": match.group(2).strip()}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, _, rest = line.partition(":")
            key_n = key.strip().lower()
            rest = rest.strip()
            if key_n in ("inputs", "input", "in"):
                raw["inputs"] = rest
            elif key_n in ("outputs", "output", "out"):
                raw["outputs"] = rest
            elif key_n in ("gate", "gate", "checkpoint"):
                raw["gate"] = rest
            elif key_n in ("fan-out", "fan_out", "fanout", "parallelism"):
                raw["fan_out"] = rest
        stages.append(normalize_stage(raw, i + 1))
    return stages


def _maybe_json(text: str) -> Any:
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def extract(native: Any) -> Any:
    """Return HONEST-NULL or a list of typed stages. Never infers."""
    if native is None:
        return HONEST_NULL
    if isinstance(native, dict) and native.get("kind"):
        kind = str(native.get("kind") or "")
        body = native.get("source")
        if body is None:
            body = native.get("text")
        if body is None:
            body = native.get("body")
        if kind in {"js", "javascript", "mjs"} and isinstance(body, str):
            return extract_from_js(body)
        if kind in {"md", "markdown"} and isinstance(body, str):
            return extract_from_markdown(body)
        if kind in {"json", "json-text"} and isinstance(body, str):
            parsed = _maybe_json(body)
            if isinstance(parsed, dict):
                got = extract_from_mapping(parsed)
                return HONEST_NULL if got is None else got
            return HONEST_NULL
        if isinstance(body, dict):
            got = extract_from_mapping(body)
            return HONEST_NULL if got is None else got
        return HONEST_NULL
    if isinstance(native, dict):
        got = extract_from_mapping(native)
        if got is not None:
            return got
        return HONEST_NULL
    if isinstance(native, str):
        parsed = _maybe_json(native)
        if isinstance(parsed, dict):
            got = extract_from_mapping(parsed)
            return HONEST_NULL if got is None else got
        if PHASE_CALL_RE.search(native) or PARALLEL_CALL_RE.search(native):
            return extract_from_js(native)
        if MD_HEADING_RE.search(native):
            return extract_from_markdown(native)
        return HONEST_NULL
    return HONEST_NULL


def render_prose(stages: Any) -> str:
    if is_honest_null(stages):
        return "NO-DECLARED-STAGES"
    lines = []
    for stage in stages:
        fan = stage.get("fan_out_degree")
        fan_s = "NULL" if fan is None else str(fan)
        lines.append(
            "{order}. name={name}; inputs={inputs}; outputs={outputs}; "
            "gate={gate}; fan_out_degree={fan}".format(
                order=stage.get("order"),
                name=stage.get("name"),
                inputs=stage.get("inputs"),
                outputs=stage.get("outputs"),
                gate=stage.get("gate"),
                fan=fan_s,
            )
        )
    return "\n".join(lines)
