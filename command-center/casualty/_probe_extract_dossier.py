r"""Extract a readable RECOVERY DOSSIER from one dead agent's transcript.

Writes three files per unit into command-center/casualty/recovered/:
  <UNIT>-spawn-prompt.txt   the verbatim contract the agent was given (signal: what DONE means)
  <UNIT>-worklog.md         ordered tool calls (name + the identifying arg) + every assistant text
  <UNIT>-scratch-index.json every file it wrote, with exists/size NOW

Why all three: the spawn prompt is the ONLY authoritative statement of the unit's contract
(the filename is not the contract); the worklog says what was already measured; the scratch
index says which of that measurement still exists on disk and can be re-read instead of re-run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SESSION = "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d"
WF_ROOT = (
    Path("C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil")
    / SESSION
    / "subagents"
    / "workflows"
)
OUT = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/casualty/recovered")


def load_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def blocks(rec: dict):
    msg = rec.get("message") if isinstance(rec.get("message"), dict) else rec
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict):
                yield b
    elif isinstance(content, str):
        yield {"type": "text", "text": content}


def role_of(rec: dict) -> str:
    m = rec.get("message")
    if isinstance(m, dict) and m.get("role"):
        return str(m["role"])
    return str(rec.get("role") or rec.get("type") or "?")


def ident_arg(name: str, inp: dict) -> str:
    if not isinstance(inp, dict):
        return ""
    for k in (
        "file_path",
        "notebook_path",
        "path",
        "command",
        "pattern",
        "query",
        "url",
    ):
        v = inp.get(k)
        if isinstance(v, str) and v:
            return v[:400].replace("\n", " ")
    return json.dumps(inp)[:300]


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("FAILED:dossier usage: <run> <UNIT> <agent-file.jsonl>")
        return 1
    run, unit, fname = argv[0], argv[1].upper(), argv[2]
    tpath = WF_ROOT / run / fname
    if not tpath.is_file():
        print(f"FAILED:dossier transcript missing {tpath}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    recs = load_jsonl(tpath)

    spawn = ""
    worklog: list[str] = []
    written: list[str] = []
    texts = 0
    tool_calls = 0
    for i, r in enumerate(recs):
        role = role_of(r)
        for b in blocks(r):
            t = b.get("type")
            if t == "text":
                txt = (b.get("text") or "").strip()
                if not txt:
                    continue
                if role == "user" and not spawn:
                    spawn = txt
                    continue
                if role == "assistant":
                    texts += 1
                    worklog.append(
                        f"\n### [rec {i}] assistant text #{texts}\n\n{txt}\n"
                    )
            elif t == "tool_use":
                tool_calls += 1
                name = b.get("name", "?")
                inp = b.get("input") or {}
                worklog.append(f"- [rec {i}] TOOL `{name}` :: {ident_arg(name, inp)}")
                if name in ("Write", "Edit", "NotebookEdit"):
                    fp = inp.get("file_path") or inp.get("notebook_path")
                    if fp:
                        written.append(str(fp))

    (OUT / f"{unit}-spawn-prompt.txt").write_text(
        spawn or "<<NO USER MESSAGE FOUND>>", encoding="utf-8"
    )
    (OUT / f"{unit}-worklog.md").write_text(
        f"# {unit} worklog (recovered from {fname})\n\n"
        f"records={len(recs)} tool_calls={tool_calls} assistant_texts={texts}\n\n"
        + "\n".join(worklog),
        encoding="utf-8",
    )
    idx = []
    for p in sorted(dict.fromkeys(written)):
        q = Path(p)
        idx.append(
            {
                "path": p,
                "exists": q.is_file(),
                "bytes": q.stat().st_size if q.is_file() else 0,
            }
        )
    (OUT / f"{unit}-scratch-index.json").write_text(
        json.dumps(idx, indent=2), encoding="utf-8"
    )

    alive = sum(1 for e in idx if e["exists"])
    print(
        f"SUCCESS:dossier {unit} records={len(recs)} tools={tool_calls} texts={texts} "
        f"spawn_chars={len(spawn)} wrote={len(idx)} still_on_disk={alive}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
