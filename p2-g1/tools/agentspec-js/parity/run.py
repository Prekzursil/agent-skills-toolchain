#!/usr/bin/env python3
"""Python/JS violation-id set parity (IMP-0149)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "agentspec"))
sys.path.insert(0, str(HERE))
from compare_ids import compare  # noqa: E402
from cases import CASES  # noqa: E402


def _run(cmd: list[str]) -> tuple[int, str]:
    repo = HERE.parents[3]
    p = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def _json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def main() -> int:
    repo = HERE.parents[3]
    c1, t1 = _run([sys.executable, "-B", str(HERE / "emit_ids_py.py")])
    if c1 != 0:
        print(t1)
        print("FAILED:run emit_ids_py")
        return 1
    py = _json(t1)
    node = "node"
    c2, t2 = _run([node, str(HERE / "emit_ids_js.mjs")])
    if c2 != 0:
        print(t2)
        print("FAILED:run emit_ids_js")
        return 1
    js = _json(t2)
    fails = compare(py, js)
    corpus = repo / "tools" / "agentspec-js" / "fixtures" / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    for name in CASES:
        dest = corpus / name
        if not dest.is_file():
            dest.write_text("{}\n", encoding="utf-8", newline="\n")
    report = {
        "compared_as": "sets",
        "fixture_count": len(CASES),
        "failures": fails,
        "python": py,
        "js": js,
    }
    print(json.dumps(report, sort_keys=True))
    if fails:
        print("FAILED:parity set mismatch")
        return 1
    print("SUCCESS:parity sets identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
