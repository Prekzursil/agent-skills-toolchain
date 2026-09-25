#!/usr/bin/env python3
"""Prove an MCP stdio server actually WORKS, and measure what it costs.

The rung ladder - the answer to "how will you know it works if you can't test it":
  1 entrypoint exists            -> distinguishes `package-gone` from everything else
  2 process starts and stays up
  3 speaks MCP: initialize -> result.serverInfo   <- the decisive functional test
  4 (outside this script) a Claude Code session start reports it CONNECTED

Rung 1 is why this tool matters for the A-11 classification: a server can fail rungs 2-3
while its package is perfectly present, which is the signature of `backend-on-demand`
(the RE stack starts its backends from ~/.local/opt/re-harness). Deleting on reachability
alone would destroy that capability - see rules/common/mcp-process-hygiene.md DOCTRINE LOCK.

Measured 2026-09-25 (openalex-mcp control, both states):
    cmd /c npx -y <pkg>   4 procs / 146.0 MB   (the npx SUPERVISOR is 90.5 MB - LARGER
                                                than the 46.4 MB server it supervises)
    node <global entry>   1 proc  /  46.6 MB

USAGE
    python mcp_probe.py <exe> [args...]      # probe one command
    python mcp_probe.py --compare <pkg>      # npx form vs installed-global form
"""
import json
import os
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "mcp-probe", "version": "1.0"},
    },
}


def descendants(pid):
    """Size of the whole process subtree of pid - the real cost of one server."""
    ps = (
        "$all=Get-CimInstance Win32_Process|Select-Object ProcessId,ParentProcessId;"
        f"$seen=@{{}};$q=New-Object System.Collections.Queue;$q.Enqueue({pid});"
        "while($q.Count -gt 0){$c=$q.Dequeue();if($seen.ContainsKey($c)){continue};$seen[$c]=$true;"
        "foreach($p in $all){if($p.ParentProcessId -eq $c){$q.Enqueue([int]$p.ProcessId)}}};"
        "$seen.Count"
    )
    try:
        out = subprocess.run(["pwsh", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=90)
        return int((out.stdout or "0").strip() or 0)
    except Exception:
        return -1


def probe(label, exe, args, env=None, timeout=25):
    print(f"\n=== {label} ===")
    print(f"  cmd: {exe} {' '.join(args)}")
    entry = next((a for a in args if a.lower().endswith((".js", ".mjs", ".py"))), None)
    if entry:
        exists = os.path.isfile(entry)
        print(f"  rung1 entrypoint exists: {exists}")
        if not exists:
            print("  -> package-gone (rungs 2-3 not attempted)")
            return {"rung1": False, "mcp": False, "tree": 0}
    e = dict(os.environ)
    e.update({k: str(v) for k, v in (env or {}).items()})
    try:
        p = subprocess.Popen([exe] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                             errors="replace", env=e)
    except Exception as ex:
        print(f"  rung2 process starts   : FAIL ({ex})")
        return {"rung1": True, "mcp": False, "tree": 0}
    time.sleep(2.0)
    if p.poll() is not None:
        print(f"  rung2 process starts   : FAIL (exited rc={p.returncode})")
        return {"rung1": True, "mcp": False, "tree": 0}
    print("  rung2 process starts   : OK")
    n = descendants(p.pid)
    print(f"  process tree size      : {n}")

    res = {}

    def reader():
        try:
            for line in p.stdout:
                line = line.strip()
                if line.startswith("{"):
                    try:
                        m = json.loads(line)
                    except Exception:
                        continue
                    if m.get("id") == 1 and "result" in m:
                        res.update(m["result"].get("serverInfo") or {"name": "?"})
                        return
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:
        p.stdin.write(json.dumps(INIT) + "\n")
        p.stdin.flush()
    except Exception as ex:
        print(f"  rung3 speaks MCP       : FAIL (write: {ex})")
    t.join(timeout=timeout)
    ok = bool(res)
    if ok:
        print(f"  rung3 speaks MCP       : OK  serverInfo={res.get('name')} v{res.get('version')}")
    else:
        print(f"  rung3 speaks MCP       : FAIL (no initialize result in {timeout}s)")
        print("  -> entrypoint present but does not speak MCP: candidate backend-on-demand")
    try:
        p.kill()
    except Exception:
        pass
    return {"rung1": True, "mcp": ok, "tree": n, "server": res}


def global_entry(pkg):
    d = os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules", *pkg.split("/"))
    pj = os.path.join(d, "package.json")
    if not os.path.isfile(pj):
        return None
    meta = json.load(open(pj, encoding="utf-8", errors="replace"))
    b = meta.get("bin")
    rel = b if isinstance(b, str) else (
        (b.get(pkg.split("/")[-1]) or next(iter(b.values())))
        if isinstance(b, dict) and b else meta.get("main"))
    return os.path.normpath(os.path.join(d, rel)) if rel else None


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--compare":
        if len(argv) < 2:
            print("usage: mcp_probe.py --compare <pkg>")
            return 2
        pkg = argv[1]
        a = probe("A) npx form", "cmd", ["/c", "npx", "-y", pkg])
        entry = global_entry(pkg.split("@")[0] if not pkg.startswith("@") else "@" + pkg[1:].split("@")[0])
        if not entry:
            print(f"\n{pkg} is not installed globally - `npm i -g {pkg}` first")
            return 1
        b = probe("B) direct form", "node", [entry])
        print("\n=== VERDICT ===")
        print(f"  npx   : tree={a['tree']} mcp_ok={a['mcp']}")
        print(f"  direct: tree={b['tree']} mcp_ok={b['mcp']}")
        if a["mcp"] and b["mcp"]:
            print(f"  -> same functional result, {a['tree'] - b['tree']} fewer processes per server")
        return 0 if b["mcp"] else 1
    r = probe("probe", argv[0], argv[1:])
    print(f"\n{'SUCCESS' if r['mcp'] else 'FAILED'}:mcp_probe")
    return 0 if r["mcp"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
