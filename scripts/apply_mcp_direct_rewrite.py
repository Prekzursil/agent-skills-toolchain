#!/usr/bin/env python3
"""Rewrite `cmd /c npx -y <pkg>` MCP entries to a direct `node <global entry>` launch.

WHY (measured on the VM, 2026-09-25, openalex-mcp as the control):
    npx form    4 processes, 146.0 MB   (2x node + 2x cmd)
    direct form 1 process,    46.6 MB
    -> the npx SUPERVISOR (90.5 MB) is larger than the server it supervises (46.4 MB).
    The saving is wrapper overhead, so it generalises; the server's own footprint is
    unchanged (46.4 -> 46.6 MB).

WHY NOT the npx cache: %LOCALAPPDATA%\\npm-cache\\_npx\\<hash> is content-addressed, npm
may purge it, and it does not survive a machine move. `npm i -g` + the stable
%APPDATA%\\npm\\node_modules path is the migration-safe form.

SAFETY
  * Refuses to run while any claude.exe is alive. This is not paranoia: the live
    C:\\Users\\prekzursil\\.claude.json was observed moving 17:39 -> 17:50 during a
    single session, so a read-modify-write WOULD race a session's own write, and
    MCP enabled/disabled curation is load-bearing (standing instruction).
  * Touches ONLY mcpServers[<name>].command/args for the named servers. Everything
    else - disabledMcpServers, project history, env values - is passed through, and a
    structural diff PROVES it before the file is written.
  * Timestamped backup; dry-run is the default.

USAGE
    python apply_mcp_direct_rewrite.py              # dry run (default)
    python apply_mcp_direct_rewrite.py --apply      # write, only with no claude.exe
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONFIG = r"C:\Users\prekzursil\.claude.json"
PATCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "mcp-direct-rewrite.json")


def live_claude_sessions():
    """Return PIDs of running claude.exe - the interlock."""
    try:
        out = subprocess.run(
            ["pwsh", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\").ProcessId -join ','"],
            capture_output=True, text=True, timeout=60).stdout.strip()
        return [p for p in out.split(",") if p.strip()]
    except Exception as e:
        print(f"  WARN: could not check for live sessions ({e}) - treating as UNSAFE")
        return ["unknown"]


def structural_diff(old, new, path="$"):
    """Every leaf path that differs. The safety proof: this list must equal exactly
    the command/args paths we intended to change."""
    diffs = []
    if type(old) is not type(new):
        return [path]
    if isinstance(old, dict):
        for k in set(old) | set(new):
            if k not in old:
                diffs.append(f"{path}.{k} [ADDED]")
            elif k not in new:
                diffs.append(f"{path}.{k} [REMOVED]")
            else:
                diffs += structural_diff(old[k], new[k], f"{path}.{k}")
    elif isinstance(old, list):
        if old != new:
            diffs.append(path)
    elif old != new:
        diffs.append(path)
    return diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--patch", default=PATCH)
    a = ap.parse_args()

    patch = json.load(open(a.patch, encoding="utf-8"))
    with open(a.config, encoding="utf-8") as f:
        original_text = f.read()
    cfg = json.loads(original_text)
    srv = cfg.get("mcpServers") or {}

    print(f"config : {a.config}  ({len(original_text)} bytes, {len(srv)} servers)")
    print(f"patch  : {a.patch}  ({len(patch)} entries)\n")

    # --- preflight: every target must exist on disk, or we do not touch anything ---
    expected, blocked = [], []
    for name, spec in patch.items():
        cur = srv.get(name)
        if cur is None:
            blocked.append(f"{name}: not present in config")
            continue
        entry = spec["new"]["args"][0]
        if not os.path.isfile(entry):
            blocked.append(f"{name}: entrypoint missing -> {entry}")
            continue
        if cur.get("command") == spec["new"]["command"] and cur.get("args") == spec["new"]["args"]:
            print(f"  {name:<24} already rewritten - skipping")
            continue
        if cur.get("command") != spec["old"].get("command") or cur.get("args") != spec["old"].get("args"):
            blocked.append(f"{name}: current wiring does not match the recorded 'old' - "
                           f"config changed since the patch was built; rebuild it")
            continue
        expected.append(name)
        print(f"  {name:<24} npx -> node  {os.path.basename(entry)}")

    if blocked:
        print("\nBLOCKED - nothing written:")
        for b in blocked:
            print(f"  ! {b}")
        return 1
    if not expected:
        print("\nnothing to do.")
        return 0

    # --- build the new document ---
    new_cfg = json.loads(original_text)
    for name in expected:
        e = new_cfg["mcpServers"][name]
        e["command"] = patch[name]["new"]["command"]
        e["args"] = patch[name]["new"]["args"]

    # --- prove only the intended leaves moved ---
    diffs = structural_diff(cfg, new_cfg)
    allowed = set()
    for n in expected:
        allowed.add(f"$.mcpServers.{n}.command")
        allowed.add(f"$.mcpServers.{n}.args")
    unexpected = [d for d in diffs if d not in allowed]
    print(f"\nstructural diff: {len(diffs)} leaf change(s)")
    for d in sorted(diffs):
        print(f"    {d}")
    if unexpected:
        print("\nABORT - changes outside the intended scope:")
        for u in unexpected:
            print(f"  ! {u}")
        return 1
    print("  OK: every change is an intended command/args leaf.")
    print(f"  servers before={len(cfg.get('mcpServers') or {})} after={len(new_cfg.get('mcpServers') or {})}")
    print(f"  disabledMcpServers untouched: "
          f"{cfg.get('disabledMcpServers') == new_cfg.get('disabledMcpServers')}")

    if not a.apply:
        print("\nDRY RUN - nothing written. Re-run with --apply (requires no live claude.exe).")
        return 0

    pids = live_claude_sessions()
    if pids:
        print(f"\nREFUSING to write: {len(pids)} live claude.exe session(s): {', '.join(pids)}")
        print("  Close every Claude Code session first. A read-modify-write here races the")
        print("  session's own write to this file and can destroy MCP curation state.")
        return 2

    bak = f"{a.config}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(a.config, bak)
    tmp = a.config + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(new_cfg, f, indent=2, ensure_ascii=False)
    json.load(open(tmp, encoding="utf-8"))          # re-parse before swapping in
    os.replace(tmp, a.config)
    print(f"\nAPPLIED {len(expected)} rewrite(s).")
    print(f"  backup  : {bak}")
    print(f"  rollback: copy the backup back over {a.config}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
