r"""Precisely identify which workflow transcripts ARE build:ADV-0021 / build:ADV-0022.

recover_failed_agents.py matches by raw TEXT anywhere in the transcript, so it matched 42/42
(every sibling cross-references the unit ids). This script uses three MECHANICALLY DIFFERENT
signals and reports each separately so a disagreement is visible instead of averaged away:

  S1 OUTPUT-PATH WRITE : a Write/Edit tool_use whose file_path contains the unit id.
  S2 SPAWN-PROMPT      : the first user message (the spawn prompt) mentions the unit id.
  S3 JOURNAL LABEL     : journal.jsonl row for this agentId carries a label/name field.

Prints a compact table. No verdict is asserted here -- the caller reads the three columns.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SESSION = "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d"
WF_ROOT = (
    Path("C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil")
    / SESSION
    / "subagents"
    / "workflows"
)


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


def main(argv: list[str]) -> int:
    run = argv[0] if argv else "wf_9cb1a66a-36f"
    wanted = [a.upper() for a in argv[1:]] or ["ADV-0021", "ADV-0022"]
    root = WF_ROOT / run
    if not root.is_dir():
        print(f"FAILED:identify run dir missing {root}")
        return 1

    journal_rows: dict[str, dict] = {}
    jpath = root / "journal.jsonl"
    if jpath.is_file():
        for rec in load_jsonl(jpath):
            aid = rec.get("agentId")
            if aid:
                journal_rows[aid] = rec

    # Journal schema discovery -- print the key set once so the join is not a guess.
    if journal_rows:
        sample = next(iter(journal_rows.values()))
        print(f"journal row keys: {sorted(sample.keys())}")

    hits: dict[str, list] = {w: [] for w in wanted}
    total = 0
    for tpath in sorted(root.glob("agent-*.jsonl")):
        total += 1
        recs = load_jsonl(tpath)
        aid = tpath.stem.replace("agent-", "")
        # S2: first user-role message = spawn prompt
        spawn = ""
        for r in recs:
            role = (r.get("message") or {}).get("role") if isinstance(r.get("message"), dict) else r.get("role")
            if role == "user":
                spawn = " ".join(
                    b.get("text", "") for b in blocks(r) if b.get("type") == "text"
                )
                break
        written = []
        for r in recs:
            for b in blocks(r):
                if b.get("type") == "tool_use" and b.get("name") in ("Write", "Edit", "NotebookEdit"):
                    inp = b.get("input") or {}
                    fp = inp.get("file_path") or inp.get("notebook_path")
                    if fp:
                        written.append(str(fp))
        jrow = journal_rows.get(aid, {})
        jlabel = ""
        for k in ("label", "name", "agentLabel", "unit", "unitId", "task"):
            v = jrow.get(k)
            if isinstance(v, str) and v:
                jlabel = f"{k}={v}"
                break

        for w in wanted:
            s1 = [p for p in written if w.lower() in p.lower() or w.replace("-", "").lower() in p.lower()]
            # spawn prompt: require the id near a build/unit context word, not a bare mention
            s2 = bool(re.search(rf"(?:build|unit[_ -]?id|UNIT|you are)\D{{0,80}}{w}", spawn, re.I)) or spawn.upper().count(w) >= 3
            s3 = w.lower() in jlabel.lower()
            if s1 or s2 or s3:
                hits[w].append(
                    {
                        "file": tpath.name,
                        "aid": aid,
                        "S1_wrote": s1[:4],
                        "S2_spawn": s2,
                        "S3_label": jlabel,
                        "records": len(recs),
                        "bytes": tpath.stat().st_size,
                        "spawn_head": spawn[:200].replace("\n", " "),
                    }
                )

    print(f"scanned {total} transcripts in {run}")
    for w in wanted:
        print(f"\n##### {w}: {len(hits[w])} candidate(s)")
        for h in hits[w]:
            print(json.dumps(h, indent=2))
    print("SUCCESS:identify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
