#!/usr/bin/env python3
"""Drive the live catalog SUT tools/lib/codex-invocation.mjs from Python."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import marshaller as M  # noqa: E402

CHILD = HERE / "child_echo.py"
JS_PLAN = HERE / "js_plan.mjs"
LIVE_MJS = REPO / "tools" / "lib" / "codex-invocation.mjs"


def original_inline_argv(cwd: str, payload: str) -> list[str]:
    """Origin defect: prompt pushed onto argv (codex.mjs:91-92)."""
    return ["codex", "exec", "--json", "-C", cwd, payload]


def run_live_js(payload: str) -> dict:
    if not LIVE_MJS.is_file():
        raise FileNotFoundError(str(LIVE_MJS))
    tmp = Path(tempfile.mkdtemp(prefix="tst0187-js-"))
    prompt_in = tmp / "payload.txt"
    out_dir = tmp / "out"
    try:
        prompt_in.write_text(payload, encoding="utf-8", newline="\n")
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [
                "node",
                str(JS_PLAN),
                "--prompt-file",
                str(prompt_in),
                "--dir",
                str(out_dir),
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"js_plan rc={proc.returncode} stderr={proc.stderr[-800:]}"
            )
        line = (proc.stdout or "").strip().splitlines()[-1]
        plan = json.loads(line)
        argv = [str(plan["command"]), *[str(a) for a in plan["args"]]]
        prompt_file = Path(plan["promptFile"])
        on_disk = prompt_file.read_text(encoding="utf-8")
        child = subprocess.run(
            [sys.executable, "-B", str(CHILD), "--stdin"],
            cwd=str(REPO),
            input=on_disk,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if child.returncode != 0:
            raise RuntimeError(
                f"js child rc={child.returncode} stderr={child.stderr[-400:]}"
            )
        child_doc = json.loads((child.stdout or "").strip().splitlines()[-1])
        orig = original_inline_argv(str(REPO), payload)
        want_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        leaked = any(payload and payload in a for a in argv)
        return {
            "argv": argv,
            "argv_utf8_bytes": M.argv_utf8_bytes(argv),
            "child_payload_len": child_doc.get("payload_len"),
            "child_payload_sha256": child_doc.get("payload_sha256"),
            "child_source": child_doc.get("source"),
            "live_mjs": str(LIVE_MJS.relative_to(REPO).as_posix()),
            "original_win_chars": M.win_cmdline_chars(orig),
            "original_would_exceed": M.would_hit_windows_ceiling(orig),
            "payload_in_argv": leaked,
            "payload_len": len(payload),
            "payload_sha256": want_sha,
            "plan_stdin": plan.get("stdin"),
            "prompt_file_len": len(on_disk),
            "prompt_file_sha256": hashlib.sha256(
                on_disk.encode("utf-8")
            ).hexdigest(),
            "prompt_file_matches": on_disk == payload,
            "win_cmdline_chars_at_spawn": M.win_cmdline_chars(argv),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def mjs_static() -> dict:
    text = LIVE_MJS.read_text(encoding="utf-8")
    stripped = []
    in_block = False
    for line in text.splitlines():
        s = line
        if in_block:
            end = s.find("*/")
            if end >= 0:
                s = s[end + 2 :]
                in_block = False
            else:
                continue
        while True:
            start = s.find("/*")
            line_comment = s.find("//")
            if start >= 0 and (line_comment < 0 or start < line_comment):
                end = s.find("*/", start + 2)
                if end < 0:
                    s = s[:start]
                    in_block = True
                    break
                s = s[:start] + s[end + 2 :]
                continue
            if line_comment >= 0:
                s = s[:line_comment]
            break
        stripped.append(s)
    code = "\n".join(stripped)
    return {
        "has_create_plan": "export async function createCodexExecPlan" in text,
        "has_prompt_from_stdin": "PROMPT_FROM_STDIN" in text,
        "never_push_prompt": "args.push(String(prompt" not in code,
        "pushes_stdin_token": "args.push(PROMPT_FROM_STDIN)" in code,
        "writes_prompt_file": "export async function writePromptFile" in text,
        "stdin_token_dash": "export const PROMPT_FROM_STDIN = '-'" in text
        or 'export const PROMPT_FROM_STDIN = "-"' in text,
        "path": "tools/lib/codex-invocation.mjs",
        "bytes": LIVE_MJS.stat().st_size,
    }
