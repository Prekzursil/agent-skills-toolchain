#!/usr/bin/env python3
"""Extract a Workflow (ultracode) subagent's PROMPT + OUTPUT from its on-disk transcript.

Claude Code stores each Workflow subagent as:
  ~/.claude/projects/<project>/<session>/subagents/workflows/<wf_id>/agent-<agentId>.jsonl

GOTCHAS this tool absorbs so you don't have to:
  * <project> is the SESSION's project dir, which can DIFFER from where the workflow
    SCRIPT (.../workflows/scripts/<name>-<wf_id>.js) is stored. Never assume co-location.
  * The human-readable agent LABEL (e.g. 'synthesize:multiai-decision') is NOT in the
    transcript or journal.jsonl (journal stores a hashed `key`) — it lives only in the .js
    script. So you cannot grep the label; grep a PHRASE from the prompt (a lens name / the
    task text) or from the OUTPUT you saw in the UI.
  * A message's content is a string OR a list of {"type":"text","text":...} blocks.

Identify the agent by ANY of:
  --phrase "<distinctive text>"   the reliable locator (prompt or output text)
  --file   <agent-*.jsonl>        direct path
  --workflow <name-or-wf_id>      narrow to one workflow (combine with --phrase or --list)
  --list                          list every agent in the workflow with an output preview

Examples:
  extract_workflow_agent.py --phrase "Vaporware-filtered maturity table"
  extract_workflow_agent.py --workflow multiai-orchestration-research --list
  extract_workflow_agent.py --workflow multiai-orchestration-research --phrase "LENS: ultracode-for-codex"
"""

from __future__ import annotations
import argparse
import glob
import json
import os
import re
import sys

DEFAULT_PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")


def resolve_wf_tokens(projects: str, name: str) -> set[str]:
    """A workflow NAME -> the set of tokens (wf_id + name) that appear in transcript paths."""
    toks = {name}
    for js in glob.glob(
        os.path.join(projects, "**", "workflows", "scripts", "*.js"), recursive=True
    ):
        base = os.path.basename(js)
        if name in base:
            m = re.search(r"(wf_[0-9a-z\-]+)", base)
            if m:
                toks.add(m.group(1))
    return toks


def agent_files(projects: str, wf: str | None) -> list[str]:
    pat = os.path.join(projects, "**", "subagents", "workflows", "*", "agent-*.jsonl")
    files = glob.glob(pat, recursive=True)
    if wf:
        toks = resolve_wf_tokens(projects, wf) if not wf.startswith("wf_") else {wf}
        files = [f for f in files if any(t in f for t in toks)]
    return sorted(files)


def file_has(path: str, phrase: str) -> bool:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return any(phrase in line for line in f)
    except OSError:
        return False


def text_of(msg: dict) -> str:
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(
            b.get("text", "")
            for b in c
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def journal_result(agent_path: str) -> str:
    """The authoritative captured output = journal.jsonl `result` for this agentId.

    This is the agent's actual return value the workflow stored (what fed the next
    phase / the UI), so it is clean even for tool-using agents whose transcript
    interleaves narration between tool batches. Empty string if not found.
    """
    m = re.search(r"agent-([0-9a-f]+)\.jsonl$", os.path.basename(agent_path))
    if not m:
        return ""
    aid = m.group(1)
    jpath = os.path.join(os.path.dirname(agent_path), "journal.jsonl")
    if not os.path.exists(jpath):
        return ""
    with open(jpath, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "result" and d.get("agentId") == aid:
                r = d.get("result")
                if isinstance(r, str):
                    return r
                if r is not None:  # schema'd agent -> the validated object
                    return json.dumps(r, indent=2, ensure_ascii=False)
    return ""


def parse(path: str) -> tuple[str, str]:
    """(prompt, output): prompt = largest user message; output = journal `result`
    (authoritative), falling back to the final assistant message, then all of it."""
    users, assistants = [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            txt = text_of(d.get("message", {}) or {})
            if not txt.strip():
                continue
            if d.get("type") == "user":
                users.append(txt)
            elif d.get("type") == "assistant":
                assistants.append(txt)
    prompt = max(users, key=len) if users else ""
    output = (
        journal_result(path)
        or (assistants[-1] if assistants else "")
        or "\n\n".join(assistants)
    )
    return prompt, output


def preview(path: str) -> str:
    """A one-line identity hint for --list: the report's first markdown HEADING.

    Tool-using agents open their captured output with boilerplate narration
    ("All verification complete... compiling the final report"), so the literal
    first line is useless for picking. The first `#`-heading is the real title.
    """
    _, out = parse(path)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if not lines:
        return "(no output)"
    head = next((ln for ln in lines if ln.lstrip().startswith("#")), lines[0])
    return head.lstrip("# ").strip()[:110]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract a Workflow subagent's prompt + output."
    )
    ap.add_argument("--phrase")
    ap.add_argument("--file")
    ap.add_argument("--workflow")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--projects", default=DEFAULT_PROJECTS)
    ap.add_argument("--out", default=os.getcwd())
    ap.add_argument(
        "--slug", default="agent", help="basename for the saved PROMPT/OUTPUT files"
    )
    ap.add_argument(
        "--print",
        dest="do_print",
        action="store_true",
        help="print the output to stdout",
    )
    a = ap.parse_args()

    if a.list:
        files = agent_files(a.projects, a.workflow)
        print(f"{len(files)} agent(s) in workflow '{a.workflow}':")
        for i, f in enumerate(files):
            print(f"  [{i}] {os.path.basename(f)}  ::  {preview(f)}")
        return 0

    target = None
    if a.file:
        target = a.file
    elif a.phrase:
        matches = [
            f for f in agent_files(a.projects, a.workflow) if file_has(f, a.phrase)
        ]
        if not matches:
            print(
                f"NO MATCH for phrase {a.phrase!r} (workflow={a.workflow}). Widen the phrase or drop --workflow."
            )
            return 2
        if len(matches) > 1:
            print(
                f"{len(matches)} agents match {a.phrase!r} — narrow it (each shown with an output preview):"
            )
            for f in matches:
                print(f"  {f}  ::  {preview(f)}")
            return 3
        target = matches[0]
    else:
        ap.error("give one of --phrase / --file / (--workflow --list)")

    prompt, output = parse(target)
    os.makedirs(a.out, exist_ok=True)
    pp = os.path.join(a.out, f"{a.slug}-PROMPT.md")
    op = os.path.join(a.out, f"{a.slug}-OUTPUT.md")
    open(pp, "w", encoding="utf-8").write(prompt)
    open(op, "w", encoding="utf-8").write(output)
    print(f"agent file : {target}")
    print(
        f"PROMPT     : {prompt.count(chr(10)) + 1} lines, {len(prompt)} chars -> {pp}"
    )
    print(
        f"OUTPUT     : {output.count(chr(10)) + 1} lines, {len(output)} chars -> {op}"
    )
    if a.do_print:
        print("\n===== OUTPUT =====\n" + output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
