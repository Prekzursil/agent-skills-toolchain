r"""Recover what a DIED workflow agent actually produced, from its on-disk transcript.

WHY THIS EXISTS. Two build agents (ADV-0021, ADV-0022) died mid-run during a driver update after
burning 275.4k and 250.5k output tokens over 1h03m and 53m58s. A died agent returns null to the
script, so the workflow's own result set says nothing about it -- but the transcript on disk records
every tool call it made, including every file it wrote. Re-running from zero would discard ~2 hours of
real work; the measured lesson is "teammates DIE on session cut -> recover from disk".

WHAT IT REPORTS, per agent: its label, its terminal state, the files it WROTE or EDITED (with whether
each still exists and its current size), and the tail of its own last assistant text. That last field
matters most -- a write-as-you-go agent leaves an honest partial artifact, and reading it tells you
whether the remaining work is 5 minutes or the whole unit.

DETECTOR DISCIPLINE. The journal's `key` is a CONTENT HASH, not a label, so joining on it silently
matches nothing; the join field is `agentId`. The payload field is `result`, not `value`. Both were
learned the hard way. If the join produces zero rows this script says so and exits non-zero rather
than printing an empty table that reads as "nothing to recover".
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

#: A file this large is a real artifact, not a stub. Purely for the report's eye-scan.
SUBSTANTIAL = 2_000


def load_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a torn last line is expected when a run is killed
    return out


def agent_facts(path: Path) -> dict:
    """Pull label, written paths and last text out of one agent transcript."""
    recs = load_jsonl(path)
    label, written, last_text, ended = "", [], "", False
    for r in recs:
        if not label:
            for k in ("label", "agentLabel", "name"):
                if isinstance(r.get(k), str) and r[k]:
                    label = r[k]
                    break
        msg = r.get("message") if isinstance(r.get("message"), dict) else r
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name = block.get("name", "")
                    inp = block.get("input") or {}
                    if name in ("Write", "Edit", "NotebookEdit") and isinstance(inp, dict):
                        fp = inp.get("file_path") or inp.get("notebook_path")
                        if fp:
                            written.append(str(fp))
                elif block.get("type") == "text" and block.get("text", "").strip():
                    last_text = block["text"]
        elif isinstance(content, str) and content.strip():
            last_text = content
        if r.get("type") in ("result", "summary") or r.get("subtype") == "success":
            ended = True
    return {
        "label": label or path.stem,
        "written": sorted(dict.fromkeys(written)),
        "last_text": last_text,
        "ended": ended,
        "records": len(recs),
        "bytes": path.stat().st_size,
    }


def main(argv: list[str]) -> int:
    run = argv[0] if argv else "wf_9cb1a66a-36f"
    wanted = [a.upper() for a in argv[1:]] or ["ADV-0021", "ADV-0022"]
    root = WF_ROOT / run
    if not root.is_dir():
        print(f"FAILED:recover run dir not found: {root}")
        return 1

    transcripts = sorted(root.glob("agent-*.jsonl"))
    if not transcripts:
        print(f"FAILED:recover no agent transcripts under {root}")
        return 1

    journal = root / "journal.jsonl"
    returned: dict[str, object] = {}
    if journal.is_file():
        for rec in load_jsonl(journal):
            aid = rec.get("agentId")
            if aid:
                # The payload key is `result`; `value` does not exist and reads as None.
                returned[aid] = rec.get("result")
    print(f"  run {run}: {len(transcripts)} transcripts, {len(returned)} journal results")

    matched = 0
    for tpath in transcripts:
        raw = tpath.read_text(encoding="utf-8", errors="replace")
        if not any(w in raw.upper() for w in wanted):
            continue
        matched += 1
        f = agent_facts(tpath)
        aid = tpath.stem.replace("agent-", "")
        got = returned.get(aid, "<<no journal row>>")
        print(f"\n=== {f['label']}  [{tpath.name}]")
        print(
            f"    records={f['records']} transcript={f['bytes']:,}B "
            f"terminal_record={f['ended']} journal_result="
            f"{'present' if got not in (None, '<<no journal row>>') else got}"
        )
        if not f["written"]:
            print("    WROTE NOTHING -- total loss for this agent, re-run from scratch.")
        for p in f["written"]:
            q = Path(p)
            if q.is_file():
                size = q.stat().st_size
                tag = "SUBSTANTIAL" if size >= SUBSTANTIAL else "stub"
                print(f"    [on disk {tag:11}] {size:>9,}B  {p}")
            else:
                print(f"    [GONE          ] {p}")
        tail = (f["last_text"] or "").strip().replace("\r", "")
        if tail:
            print("    --- last assistant text (tail) ---")
            for line in tail.splitlines()[-14:]:
                print(f"    | {line[:150]}")

    if not matched:
        print(f"FAILED:recover detector matched 0 of {len(transcripts)} transcripts for {wanted}")
        return 1
    print(f"\nSUCCESS:recover matched={matched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
