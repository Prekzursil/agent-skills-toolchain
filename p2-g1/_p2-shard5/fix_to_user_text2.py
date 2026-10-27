#!/usr/bin/env python3
"""Repair pass 2: match the ACTUAL broken bytes (lone-quote lines) left by
the mangled heredoc write, replace with the correct to_user_text."""
from pathlib import Path

P = Path(r"C:\Users\Prekzursil\p2-g1\release\platforms\windows\launch_adapter.py")
t = P.read_text(encoding="utf-8")

BROKEN = (
    "    def to_user_text(self) -> str:\n"
    "        action = self.ctx.get(\"action\") or \"add the tool directory to PATH and retry\"\n"
    "        return (\n"
    "            \"ERROR:\" + self.code + \" \" + self.message + \"\n"
    "\"\n"
    "            \"PATH=\" + (self.ctx.get(\"path\") or os.environ.get(\"PATH\", \"\")) + \"\n"
    "\"\n"
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
    raise SystemExit(f"FAILED:repair2 broken-block found {n} times (want 1)")
t = t.replace(BROKEN, GOOD)
P.write_text(t, encoding="utf-8")
import ast

ast.parse(t)
print("SUCCESS:repair2 to_user_text restored, syntax OK")
