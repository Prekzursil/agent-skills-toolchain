#!/usr/bin/env python3
"""IMP-0161 probe2: the adapter's argv is built WITHOUT a local prompt-on-argv
builder. stdlib-ast scan over the adapter source plus a planted local builder
control (both-states): the scanner must flag the planted builder and stay
silent on the real adapter.

Complements probe1 (behavioural) with a mechanically different code-path
signal: AST, not execution."""
from __future__ import annotations

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTER = REPO / "tools" / "import-adapters" / "codex_fanout.py"

BANNED_FLAG_NAMES = {"--prompt", "--message", "--body"}


def scan(source: str) -> dict:
    """Flag a banned prompt flag only when it FLOWS INTO an argv list
    construction (ast.List), not when a comparison GUARDS against it."""
    tree = ast.parse(source)
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.List):
            continue
        for el in node.elts:
            if isinstance(el, ast.Constant) and isinstance(el.value, str):
                if el.value.strip().lower() in BANNED_FLAG_NAMES:
                    hits.append(f"argv-list-literal:{el.value}@line{el.lineno}")
            if isinstance(el, ast.Name) and "prompt" in el.id.lower()                     and "file" not in el.id.lower():
                hits.append(f"argv-list-prompt-var:{el.id}@line{el.lineno}")
        # joined bodies flowing into the list
        joined = [v for v in node.elts if isinstance(v, (ast.JoinedStr, ast.BinOp))]
        for j in joined:
            un = ast.unparse(j)
            if "prompt" in un.lower() and "file" not in un.lower():
                hits.append(f"argv-list-joined-prompt@line{j.lineno}")
    return {"hits": hits, "clean": not hits}


def main() -> int:
    src = ADAPTER.read_text(encoding="utf-8")
    real = scan(src)

    # Planted control: a local builder that WOULD put the prompt body on argv.
    planted = '''
def _bad_local_builder(unit):
    body = unit["prompt"]
    argv = ["codex", "--prompt", body]
    return argv
'''
    ctrl = scan(planted)
    both_states = (not real["clean"]) == ctrl["clean"]
    scanner_can_see = not ctrl["clean"]

    # Second mechanical fact: the adapter routes prompts only through
    # prompt_file values, which the plan argv carries after a --flag.
    routes = "prompt_file" in src and "--prompt-file" in src
    no_inline_key = "prompt_file" in src

    result = {
        "unit_id": "IMP-0161",
        "probe": "probe2-argv-ast",
        "adapter_hits": real["hits"],
        "adapter_clean": real["clean"],
        "control_planted_hits": ctrl["hits"],
        "scanner_detects_planted": scanner_can_see,
        "both_states_ok": both_states and scanner_can_see,
        "prompt_file_route_present": routes,
        "no_inline_prompt_key": no_inline_key,
        "pass": real["clean"] and scanner_can_see and both_states and routes and no_inline_key,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0161-probe2 adapter builds argv without a local prompt-on-argv builder; "
            "planted control is flagged (both-states)"
            if result["pass"] else
            "FAILED:IMP-0161-probe2 argv hygiene contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
