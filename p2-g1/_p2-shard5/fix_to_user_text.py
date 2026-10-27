#!/usr/bin/env python3
"""Repair launch_adapter.py: replace the broken to_user_text block written by
the mangled heredoc with the correct implementation. File-based patch (no
shell transport of backslash escapes)."""
from pathlib import Path

P = Path(r"C:\Users\Prekzursil\p2-g1\release\platforms\windows\launch_adapter.py")
t = P.read_text(encoding="utf-8")

BROKEN = (
    "    def to_user_text(self) -> str:\n"
    "        action = self.ctx.get(\"action\") or \"add the tool directory to PATH and retry\"\n"
    "        return (\n"
    "            \"ERROR:\" + self.code + \" \" + self.message + \"\n"
    "            \"PATH=\" + (self.ctx.get(\"path\") or os.environ.get(\"PATH\", \"\")) + \"\n"
    "            \"action: \" + action\n"
    "        )\n"
)
GOOD = (
    "    def to_user_text(self) -> str:\n"
    "        action = self.ctx.get(\"action\") or \"add the tool directory to PATH and retry\"\n"
    "        return (\n"
    "            \"ERROR:\" + self.code + \" \" + self.message + \"\\n\"\n"
    "            \"PATH=\" + (self.ctx.get(\"path\") or os.environ.get(\"PATH\", \"\")) + \"\\n\"\n"
    "            \"action: \" + action\n"
    "        )\n"
)

n = t.count(BROKEN)
if n != 1:
    raise SystemExit(f"FAILED:repair broken-block found {n} times (want 1)")
t = t.replace(BROKEN, GOOD)
P.write_text(t, encoding="utf-8")
import ast

ast.parse(t)
print("SUCCESS:repair to_user_text restored, syntax OK")
