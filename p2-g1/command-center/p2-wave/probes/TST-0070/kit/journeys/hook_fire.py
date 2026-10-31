#!/usr/bin/env python3
"""golden journey 1: load the kit hook and emit its fired result."""
import hashlib, json, sys
from pathlib import Path
kit = Path(sys.argv[1]); out = Path(sys.argv[2])
hook_raw = (kit / "hooks" / "hook.golden.json").read_bytes()
hook = json.loads(hook_raw)
plugin = json.loads((kit / "plugin.json").read_text(encoding="utf-8"))
out.write_text(json.dumps({"journey": "hook-fire", "kit": plugin.get("id"), "hook_id": hook["id"],
                           "event": hook["event"], "matcher": hook["matcher"], "action": hook["action"],
                           "fired": True, "hook_bytes": len(hook_raw),
                           "hook_sha256": hashlib.sha256(hook_raw).hexdigest(),
                           "kit_entry": plugin.get("entry")}, indent=1), encoding="utf-8")
print("HOOK-FIRED")
