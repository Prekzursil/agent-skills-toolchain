# -*- coding: utf-8 -*-
# READ-ONLY MCP wiring sweep, 2026-09-21. Classification only, NO repairs.
import json, os, re, socket, shutil, subprocess, sys, tomllib
from urllib.parse import urlparse
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOME = r"C:\Users\Prekzursil"
OUT = HOME + r"\.agents\MCP-SWEEP_2026-09-21.json"
SOCK_T = 2.0

RUNNERS_NPM = {"npx", "npx.cmd", "npx.exe", "bunx", "pnpm"}
RUNNERS_WHICH = {
    "node",
    "node.exe",
    "python",
    "python.exe",
    "python3",
    "uvx",
    "uvx.exe",
    "uv",
    "uv.exe",
    "gh-cli-mcp",
    "codex",
    "codex.exe",
    "gh",
    "gh.exe",
    "bun",
}
PAYLOAD_EXT = (".py", ".cmd", ".bat", ".jar", ".mjs", ".js", ".exe")
KNOWN_SKIP = {
    "tavily": "plugin-provided",
    "meta-tool": "claude-denied",
    "markitdown": "claude-denied",
}

_ep_cache = {}


def test_endpoint(url):
    try:
        p = urlparse(url)
        host = p.hostname or "127.0.0.1"
        port = p.port or (443 if p.scheme == "https" else 80)
    except Exception as e:
        return ("BROKEN(endpoint-dead)", "bad url: %s" % e)
    key = (host.lower(), port)
    if key in _ep_cache:
        st, d = _ep_cache[key]
        return (st, d + " (cached)")
    note = ""
    if 31100 <= port <= 31199 or 31400 <= port <= 31499:
        note = "estate-gateway-front"
    if host in ("127.0.0.1", "localhost") and port == 24680:
        note = "mcphub(under-repair-separately)"
    try:
        with socket.create_connection((host, port), timeout=SOCK_T):
            res = ("OK(endpoint-up)", note or "tcp connect ok")
    except Exception as e:
        res = (
            "BROKEN(endpoint-dead)",
            "%s: %s%s" % (type(e).__name__, e, (" [%s]" % note) if note else ""),
        )
    _ep_cache[key] = res
    return res


_docker = None


def docker_state():
    global _docker
    if _docker is None:
        try:
            r = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, timeout=5
            )
            _docker = (r.returncode == 0, (r.stdout or r.stderr or "").strip()[:60])
        except Exception as e:
            _docker = (False, "%s: %s" % (type(e).__name__, e))
    return _docker


def is_abs(p):
    return bool(re.match(r"^[A-Za-z]:[\\/]", p)) or p.startswith("\\\\")


def classify_stdio(cmd, args):
    args = [str(a) for a in (args or [])]
    c = str(cmd).strip().strip('"')
    if is_abs(c):
        if os.path.exists(c):
            for a in args:
                a0 = a.strip('"')
                if (
                    is_abs(a0)
                    and a0.lower().endswith(PAYLOAD_EXT)
                    and not os.path.exists(a0)
                ):
                    return (
                        "BROKEN(exe-missing)",
                        "payload missing: %s (runner present: %s)" % (a0, c),
                    )
            return ("OK(exe-present)", c)
        return ("BROKEN(exe-missing)", c)
    toks = [c] + args
    if c.lower() in ("cmd", "cmd.exe"):
        rest, skip = [], True
        for a in args:
            if skip and a.lower() in ("/c", "/k", "/s", "/d"):
                continue
            skip = False
            rest.append(a)
        toks = rest or args
    for i, t in enumerate(toks):
        tl = t.strip('"').lower()
        if tl in RUNNERS_NPM:
            pkg = ""
            for j in range(i + 1, len(toks)):
                if not toks[j].startswith("-"):
                    pkg = toks[j]
                    break
            return (
                "OK-RUNNER",
                "npx -> %s (resolves pkg at runtime; not network-tested)"
                % (pkg or "?"),
            )
        if tl in ("docker", "docker.exe"):
            ok, info = docker_state()
            return (
                ("OK(docker-runner)" if ok else "BROKEN(exe-missing)"),
                "docker --version: %s" % info,
            )
        if tl in RUNNERS_WHICH:
            w = shutil.which(t.strip('"'))
            if w:
                # also payload-check absolute script args after the runner
                for a in toks[i + 1 :]:
                    a0 = a.strip('"')
                    if (
                        is_abs(a0)
                        and a0.lower().endswith(PAYLOAD_EXT)
                        and not os.path.exists(a0)
                    ):
                        return (
                            "BROKEN(exe-missing)",
                            "payload missing: %s (runner %s -> %s)" % (a0, tl, w),
                        )
                return ("OK(exe-present)", "%s -> %s" % (tl, w))
            return ("BROKEN(exe-missing)", "runner '%s' not found on PATH" % tl)
    w = shutil.which(c)
    if w:
        return ("OK(exe-present)", "%s -> %s" % (c, w))
    return ("BROKEN(exe-missing)", "command not found on PATH: %s" % c)


def classify_entry(name, e):
    if name in KNOWN_SKIP:
        return ("SKIPPED-KNOWN", KNOWN_SKIP[name])
    if e.get("enabled") is False:
        return ("DISABLED-BY-CONFIG", "enabled:false in config; not tested")
    url = e.get("url")
    cmd = e.get("command")
    args = e.get("args") or []
    if isinstance(cmd, list):
        args = cmd[1:]
        cmd = cmd[0]
    if name.lower() == "everything" and not cmd:
        p = r"C:\Users\Prekzursil\AppData\Roaming\npm\mcp-server-everything.cmd"
        return (("OK(exe-present)" if os.path.exists(p) else "BROKEN(exe-missing)"), p)
    if url and not cmd:
        return test_endpoint(url)
    if cmd:
        return classify_stdio(cmd, args)
    if e.get("type") == "remote" and url:
        return test_endpoint(url)
    if not url and not cmd:
        return (
            "GATEWAY-NATIVE",
            "bare/enabled-only entry; provided by CyberStrike gateway",
        )
    return ("UNKNOWN", "unrecognized shape: %s" % sorted(e.keys()))


def load_configs():
    cfgs = []
    with open(HOME + r"\.claude.json", encoding="utf-8") as f:
        cfgs.append((".claude.json", json.load(f).get("mcpServers", {})))
    with open(HOME + r"\.codex\config.toml", "rb") as f:
        cfgs.append(("config.toml", tomllib.load(f).get("mcp_servers", {})))
    with open(HOME + r"\.config\cyberstrike\cyberstrike.json", encoding="utf-8") as f:
        cfgs.append(("cyberstrike.json", json.load(f).get("mcp", {})))
    with open(
        HOME + r"\AppData\Roaming\Claude\claude_desktop_config.json", encoding="utf-8"
    ) as f:
        cfgs.append(("claude_desktop_config.json", json.load(f).get("mcpServers", {})))
    with open(HOME + r"\.cursor\mcp.json", encoding="utf-8") as f:
        cfgs.append(("cursor_mcp.json", json.load(f).get("mcpServers", {})))
    return cfgs


def bucket(st):
    if st.startswith("OK"):
        return "OK"
    if st == "GATEWAY-NATIVE":
        return "GATEWAY"
    if st == "SKIPPED-KNOWN":
        return "SKIPPED"
    if st == "DISABLED-BY-CONFIG":
        return "DISABLED"
    if st.startswith("BROKEN"):
        return "BROKEN"
    return "UNKNOWN"


def main():
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "method": "read-only: exists/which checks + sequential TCP socket(2s); no repairs",
        "configs": {},
    }
    broken_rows = []
    for fname, servers in load_configs():
        entries = []
        counts = {
            "OK": 0,
            "GATEWAY": 0,
            "BROKEN": 0,
            "DISABLED": 0,
            "SKIPPED": 0,
            "UNKNOWN": 0,
        }
        for name in sorted(servers, key=str.lower):
            st, detail = classify_entry(name, servers[name] or {})
            counts[bucket(st)] += 1
            entries.append({"name": name, "status": st, "detail": detail})
            if st.startswith("BROKEN"):
                broken_rows.append((fname, name, st, detail))
        report["configs"][fname] = {
            "total": len(entries),
            "counts": counts,
            "entries": entries,
        }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    # summary
    print("MCP SWEEP 2026-09-21 (read-only) — BROKEN entries only:")
    print("%-28s %-22s %-24s %s" % ("config", "name", "status", "detail"))
    for r in broken_rows:
        print("%-28s %-22s %-24s %.90s" % r)
    if not broken_rows:
        print("(none)")
    print("")
    for fname, data in report["configs"].items():
        c = data["counts"]
        print(
            "%-28s total=%-3d OK=%-3d GATEWAY=%-2d BROKEN=%-2d DISABLED=%-2d SKIPPED=%-2d UNKNOWN=%d"
            % (
                fname,
                data["total"],
                c["OK"],
                c["GATEWAY"],
                c["BROKEN"],
                c["DISABLED"],
                c["SKIPPED"],
                c["UNKNOWN"],
            )
        )
    # artifact re-read verification
    chk = json.load(open(OUT, encoding="utf-8"))
    n = sum(d["total"] for d in chk["configs"].values())
    print("")
    print(
        "ARTIFACT-VERIFIED: %s (%d bytes, %d entries across %d configs, re-read OK)"
        % (OUT, os.path.getsize(OUT), n, len(chk["configs"]))
    )


if __name__ == "__main__":
    main()
