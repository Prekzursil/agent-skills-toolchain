#!/usr/bin/env python3
"""Probe 2: reconstruct two workflows from IR alone; lint; both-states.

Does not call ir.parse_source. Reconstruction uses ir.from_ir on serialized
IR JSON. Source-side counts use an independent regex/brace walk. Probe 1's
self-scored round-trip is a different signal.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import ir as IR  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0044-workflow-ir-spec.json"
SCHEMA = HERE / "workflow_ir.schema.json"
HELD_OUT = ("design-gate.mjs", "codex-auth-research-fanout.mjs")
AGENT_RE = re.compile(r"(?<![A-Za-z0-9_$])agent\s*\(")
PHASE_RE = re.compile(r"(?<![A-Za-z0-9_$])phase\s*\(")
PARALLEL_RE = re.compile(r"(?<![A-Za-z0-9_$])parallel\s*\(")
LOOP_RE = re.compile(r"(?<![A-Za-z0-9_$])loop\s*\(")
STOP_RE = re.compile(r"(?<![A-Za-z0-9_$])stop\s*\(")
BARRIER_RE = re.compile(r"\.filter\s*\(\s*Boolean\s*\)")
CLOCK_RE = re.compile(r"\bDate\.now\s*\(\s*\)")


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0044-probe2 {msg}")
    return 1


def extract_balanced(text: str, open_idx: int) -> tuple[str, int]:
    open_ch = text[open_idx]
    close_ch = {"(": ")", "[": "]", "{": "}"}[open_ch]
    depth = 0
    i = open_idx
    in_str = None
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
    raise ValueError("unbalanced")


def syntax_counts(text: str) -> dict:
    """Independent of ir.parse_source: regex counts plus brace-matched prompts."""
    prompts = []
    i = 0
    while True:
        m = AGENT_RE.search(text, i)
        if not m:
            break
        inner, end = extract_balanced(text, m.end() - 1)
        s = inner.strip()
        if s.startswith('"') or s.startswith("'"):
            prompts.append(s[1:-1] if len(s) >= 2 else s)
        elif s.startswith("{"):
            try:
                obj, _ = extract_balanced(s, 0)
                data = json.loads("{" + obj + "}")
                prompts.append(data.get("prompt"))
            except (ValueError, json.JSONDecodeError):
                prompts.append(None)
        else:
            prompts.append(None)
        i = end
    return {
        "agent": len(AGENT_RE.findall(text)),
        "phase": len(PHASE_RE.findall(text)),
        "parallel": len(PARALLEL_RE.findall(text)),
        "loop": len(LOOP_RE.findall(text)),
        "stop": len(STOP_RE.findall(text)),
        "barrier": len(BARRIER_RE.findall(text)),
        "clock": len(CLOCK_RE.findall(text)),
        "prompts": prompts,
    }


def ir_counts(sem: dict) -> dict:
    kinds = [c["kind"] for c in sem["constructs"]]

    def agents_in(cons: dict) -> list[dict]:
        if cons.get("kind") == "agent":
            return [cons]
        out = []
        for ch in cons.get("children") or []:
            out.extend(agents_in(ch))
        return out

    agents = []
    for c in sem["constructs"]:
        agents.extend(agents_in(c))
    return {
        "agent": len(agents),
        "phase": kinds.count("stage"),
        "parallel": kinds.count("fanout"),
        "loop": kinds.count("loop"),
        "stop": kinds.count("stop"),
        "barrier": kinds.count("barrier"),
        "clock": sum(1 for c in sem["constructs"] if c.get("code") == IR.LOSSY_CLOCK),
        "prompts": [a.get("prompt") for a in agents],
    }


def probe2_imports_parse_source() -> bool:
    tree = ast.parse((HERE / "probe2_reconstruct.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ir":
            for alias in node.names:
                if alias.name == "parse_source":
                    return True
        if isinstance(node, ast.Attribute) and node.attr == "parse_source":
            return True
    return False


def main() -> int:
    if probe2_imports_parse_source():
        return fail("probe2 must not call parse_source; reconstruction is from IR JSON")

    lint = IR.lint_module_not_runtime(HERE / "ir.py")
    if not lint["ok"]:
        return fail(f"runtime-entrypoint {lint}")

    rows_by_name = {r["name"]: r for r in C.load_texts()}
    reconstructions = []
    for name in HELD_OUT:
        row = rows_by_name.get(name)
        if row is None:
            return fail(f"held-out {name} missing from corpus")
        # Author path (probe1) would parse source. This path serializes IR
        # produced earlier in emit; when artifact is absent we still build IR
        # via a helper that emit already used, loaded from a sidecar written
        # next to the fixture. Sidecar is IR JSON, not source.
        sidecar = HERE / "fixtures" / "ir-only" / (name + ".ir.json")
        if not sidecar.is_file():
            return fail(f"IR-only sidecar missing for {name}; emit must write it")
        ir_doc = json.loads(sidecar.read_text(encoding="utf-8"))
        reconstructed = IR.from_ir(ir_doc)
        syn = syntax_counts(row["text"])
        got = ir_counts(reconstructed)
        for key in ("agent", "phase", "parallel", "loop", "stop", "barrier", "clock"):
            if syn[key] != got[key]:
                return fail(
                    f"{name} independent count {key} syntax={syn[key]} ir={got[key]}"
                )
        if syn["prompts"] != got["prompts"]:
            return fail(f"{name} prompt reconstruction {got['prompts']} vs {syn['prompts']}")
        reconstructions.append({"name": name, "syntax": syn, "ir": got})

    # Both-states: strip one source_anchor -> validate_anchors must fire.
    sample_ir = json.loads(
        (HERE / "fixtures" / "ir-only" / (HELD_OUT[0] + ".ir.json")).read_text(
            encoding="utf-8"
        )
    )
    good_errs = IR.validate_anchors(sample_ir)
    if good_errs:
        return fail(f"good IR failed anchors {good_errs}")
    bad = json.loads(json.dumps(sample_ir))
    dropped = False
    for node in bad["nodes"]:
        if node.get("kind") == "agent":
            node.pop("source_anchor", None)
            dropped = True
            break
    if not dropped:
        return fail("no agent node to strip")
    bad_errs = IR.validate_anchors(bad)
    if not bad_errs:
        return fail("missing source_anchor was accepted")

    # Both-states lossy clock: clock file records Date.now; design-gate must not.
    clock_ir = json.loads(
        (HERE / "fixtures" / "ir-only" / "dialect-clock-and-background.js.ir.json").read_text(
            encoding="utf-8"
        )
    )
    gate_ir = sample_ir
    clock_sem = IR.from_ir(clock_ir)
    gate_sem = IR.from_ir(gate_ir)
    if IR.LOSSY_CLOCK not in IR.lossy_codes(clock_sem):
        return fail("clock file did not record Date.now in lossy ledger")
    if IR.LOSSY_CLOCK in IR.lossy_codes(gate_sem):
        return fail("design-gate fabricated a clock-lossy row")
    if IR.LOSSY_BACKGROUND not in IR.lossy_codes(clock_sem):
        return fail("background dispatch was normalised away")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0044" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("execution_semantics") != "none" or doc.get("not_a_runtime") is not True:
        return fail("IR claims execution semantics")
    node_errs = IR.validate_anchors({"nodes": doc.get("nodes") or []})
    if node_errs:
        return fail(f"artifact nodes {node_errs[:6]}")
    ledger = doc.get("lossy_field_ledger") or []
    codes = {str(r.get("code")) for r in ledger if isinstance(r, dict)}
    for needed in (IR.LOSSY_CLOCK, IR.LOSSY_ARGS_STRING, IR.LOSSY_BACKGROUND, IR.LOSSY_LIVE_BODY):
        if needed not in codes:
            return fail(f"ledger missing {needed}")

    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    ge = jsonschema.Draft202012Validator(schema).iter_errors(garbage)
    if not list(ge):
        return fail("schema accepted garbage")

    print(
        json.dumps(
            {
                "held_out": reconstructions,
                "anchor_mutant_errors": bad_errs,
                "lint": lint,
                "ledger_codes": sorted(codes),
            },
            sort_keys=True,
        )
    )
    print("reconstructed 2/2 from IR-only sidecars; syntax counts agree")
    print("SUCCESS:WFA-0044-probe2 independent reconstruction and runtime lint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
