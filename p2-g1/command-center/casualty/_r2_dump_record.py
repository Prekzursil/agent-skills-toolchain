"""Dump one transcript record (and the tool_use that produced it) in full."""

import json
import sys
from pathlib import Path

SESSION = Path(
    "C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil"
    "/30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/subagents"
)


def texts(rec):
    msg = rec.get("message") or {}
    content = msg.get("content")
    out = []
    if isinstance(content, str):
        out.append(("text", content))
    elif isinstance(content, list):
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                out.append(
                    (
                        "tool_use:" + str(c.get("name")),
                        json.dumps(c.get("input"))[:3000],
                    )
                )
            elif c.get("type") == "tool_result":
                cc = c.get("content")
                if isinstance(cc, str):
                    out.append(("tool_result", cc))
                elif isinstance(cc, list):
                    for x in cc:
                        if isinstance(x, dict) and isinstance(x.get("text"), str):
                            out.append(("tool_result", x["text"]))
            elif isinstance(c.get("text"), str):
                out.append(("text", c["text"]))
    return out


rel, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(SESSION / rel, "r", encoding="utf-8", errors="replace") as fh:
    for i, line in enumerate(fh, 1):
        if not (lo <= i <= hi):
            continue
        try:
            rec = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        for kind, t in texts(rec):
            print(f"\n----- line {i} [{kind}] -----")
            print(t[:4000])
