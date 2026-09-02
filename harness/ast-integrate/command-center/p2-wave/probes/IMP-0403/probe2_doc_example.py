#!/usr/bin/env python3
"""Probe 2: documentation command test.

An independent reviewer running only the documented help examples (nothing
else) must see exit 0 and structured stdout, including one no-fit query.
Bodies/canaries must be absent — the CLI does not inject.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CANARY = "CANARY-IMP-0403-BODY"
EXAMPLE_RE = re.compile(r"^python3 tools/ast\.py route\b")


def load_cli():
    path = REPO / "tools" / "ast.py"
    spec = importlib.util.spec_from_file_location("imp0403_ast_cli", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def route_help(mod) -> str:
    parser = mod.build_parser()
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            parser.parse_args(["route", "--help"])
    except SystemExit as exc:
        if int(exc.code or 0) != 0:
            raise AssertionError(f"route --help exited {exc.code}") from exc
    return buf.getvalue()


def examples_from_help(text: str) -> list[str]:
    found: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if EXAMPLE_RE.match(s):
            found.append(s)
    return found


def run_example(cmd: str) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, p.stdout or "", p.stderr or ""


def main() -> int:
    mod = load_cli()
    help_text = route_help(mod)
    examples = examples_from_help(help_text)
    if len(examples) < 3:
        print("FAILED:IMP-0403-probe2 expected >=3 documented examples, got", examples)
        return 1
    # Reviewer requirement: run ONLY the documented examples.
    transcripts = []
    verdicts = []
    for cmd in examples:
        code, out, err = run_example(cmd)
        blob = out + err
        if code != 0:
            print("FAILED:IMP-0403-probe2 documented example exit", code, "cmd=", cmd)
            print(blob[-2000:])
            return 1
        if CANARY in blob:
            print("FAILED:IMP-0403-probe2 canary/body leaked for", cmd)
            return 1
        try:
            doc = json.loads(out)
        except json.JSONDecodeError as exc:
            print("FAILED:IMP-0403-probe2 stdout is not JSON for", cmd, exc)
            print(out[:2000])
            return 1
        if not isinstance(doc, dict):
            print("FAILED:IMP-0403-probe2 JSON is not an object")
            return 1
        if doc.get("injection_performed") is not False or doc.get("injected") != []:
            print("FAILED:IMP-0403-probe2 injection occurred", doc.get("injected"))
            return 1
        if doc.get("session_started") is not False:
            print("FAILED:IMP-0403-probe2 session started")
            return 1
        if doc.get("terminal") is not True:
            print("FAILED:IMP-0403-probe2 non-terminal verdict")
            return 1
        if "body" in doc or "CANARY-IMP-0403-BODY" in json.dumps(doc):
            print("FAILED:IMP-0403-probe2 body key leaked")
            return 1
        if "near_misses" not in doc:
            print("FAILED:IMP-0403-probe2 near_misses omitted")
            return 1
        if "explanation" not in doc or not isinstance(doc["explanation"], dict):
            print("FAILED:IMP-0403-probe2 explanation omitted")
            return 1
        if not doc["explanation"].get("near_misses"):
            # no-fit and selected both disclose closest rejected / runners-up
            print("FAILED:IMP-0403-probe2 explanation omits near-misses")
            return 1
        verdict = str(doc.get("verdict") or "")
        verdicts.append(verdict)
        transcripts.append(
            {
                "command": cmd,
                "exit_code": code,
                "verdict": verdict,
                "selected": doc.get("selected"),
                "confidence": doc.get("confidence"),
                "near_miss_ids": [
                    n.get("capability_id") for n in (doc.get("near_misses") or [])
                ],
                "stdout_bytes": len(out.encode("utf-8")),
            }
        )

    if "NO-CAPABILITY-FITS" not in verdicts:
        print("FAILED:IMP-0403-probe2 no no-fit example among documented commands", verdicts)
        return 1
    if "SELECTED" not in verdicts:
        print("FAILED:IMP-0403-probe2 no SELECTED example among documented commands", verdicts)
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-doc-example",
                "unit_id": "IMP-0403",
                "examples_executed": examples,
                "transcripts": transcripts,
                "verdicts": verdicts,
                "reviewer_ran_only_documented_examples": True,
            },
            sort_keys=True,
        )
    )
    print(
        "examples="
        + str(len(examples))
        + " verdicts="
        + ",".join(verdicts)
        + " canary_absent=True injection_performed=False"
    )
    print("SUCCESS:IMP-0403-probe2 documented examples executed verbatim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
