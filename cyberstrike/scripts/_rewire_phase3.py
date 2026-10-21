#!/usr/bin/env python3
"""Phase-3 deploy: rewire cyberstrike.json instructions[] + add plugin key (deploy-phase3.md steps 2-3)."""

import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/.config/cyberstrike")
CFG = REPO / "cyberstrike.json"

cfg = json.loads(CFG.read_text(encoding="utf-8"))
old_instr = cfg.get("instructions")
old_plugin = cfg.get("plugin")

cfg["instructions"] = ["{file:~/.config/cyberstrike/CONTEXT.md}"]
cfg["plugin"] = ["~/.config/cyberstrike/plugin/manifest-writer.ts"]

tmp = CFG.with_name("cyberstrike.json.tmp-rewire")
tmp.write_text(
    json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
)

# fail-closed round-trip validation before replacing the live file
rt = json.loads(tmp.read_text(encoding="utf-8"))
assert rt["instructions"] == ["{file:~/.config/cyberstrike/CONTEXT.md}"], (
    "instructions mismatch"
)
assert rt["plugin"] == ["~/.config/cyberstrike/plugin/manifest-writer.ts"], (
    "plugin mismatch"
)
assert rt.get("agent", {}).get("cyberstrike", {}).get("model") == "zai/glm-5.3", (
    "agent block clobbered"
)
assert len(rt.get("mcp", {})) == 34, "mcp block clobbered (expected 34 servers)"
tmp.replace(CFG)

print(f"SUCCESS:rewire instructions {old_instr} -> {cfg['instructions']}")
print(f"SUCCESS:rewire plugin {old_plugin} -> {cfg['plugin']}")
print(f"old instructions count={len(old_instr) if old_instr else 0} new=1")
sys.exit(0)
