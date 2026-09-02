#!/usr/bin/env python3
from pathlib import Path
log = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\_shard02_fail_remeasure.log")
text = log.read_text(encoding="utf-8", errors="replace")
blocks = text.split("==== ")
for block in blocks:
    if not block.strip():
        continue
    lines = block.splitlines()
    uid = lines[0].strip()
    if uid.startswith("SUMMARY"):
        print(uid)
        continue
    last = ""
    for ln in reversed(lines):
        if ln.startswith("FAILED:delivered") or ln.startswith("SUCCESS:delivered"):
            last = ln
            break
    probe = [ln.strip() for ln in lines if ln.strip().startswith("FAILED:") and "delivered" not in ln]
    err = [ln.strip() for ln in lines if any(s in ln for s in ("Error:", "Error ", "Exception", "ModuleNotFound", "ImportError", "AttributeError", "TypeError", "KeyError", "FileNotFound", "RuntimeError", "ValueError", "Handoff"))]
    print(f"{uid}\t{last}")
    if probe:
        print("  probe:", probe[-1][:220])
    elif err:
        print("  err:", err[-1][:220])
