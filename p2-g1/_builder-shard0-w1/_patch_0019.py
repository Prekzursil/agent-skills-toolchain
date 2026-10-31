"""Patch ADV-0019 probe2: batch the POSIX/PowerShell resolvers (Windows runtime fix)."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0019/probe2_second_resolver.py"
src = p.read_text(encoding="utf-8")

old_bash = '''def bash_command_v(name: str) -> dict:
    if "/" in name or name.startswith("mcp__") or name == C.PLUGIN_NAME:
        return {"ok": False, "source": None, "method": "skipped-non-binary"}
    try:
        p = subprocess.run(
            ["bash", "-lc", "command -v " + shlex.quote(name)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "source": None, "method": "command -v", "error": str(exc)}
    src = (p.stdout or "").strip().splitlines()
    hit = src[0] if src else ""
    return {
        "ok": p.returncode == 0 and bool(hit),
        "source": hit or None,
        "method": "bash command -v",
        "exit_code": p.returncode,
    }'''

new_bash = '''def _eligible(name: str) -> bool:
    return not ("/" in name or name.startswith("mcp__") or name == C.PLUGIN_NAME)


def bash_command_v_batch(names: list) -> dict:
    """Resolve every eligible name with ONE bash invocation.

    Windows platform adaptation: the original per-name `bash -lc` spawn costs
    ~1.5s of profile load each, which put the whole probe past the measure
    timeout (84 tokens x 2 resolvers > 180s). Resolution semantics are
    unchanged: still `command -v` per name, still the same result dict shape.
    """
    eligible = [n for n in names if _eligible(n)]
    result = {
        n: {"ok": False, "source": None, "method": "skipped-non-binary"}
        for n in names
        if not _eligible(n)
    }
    if not eligible:
        return result
    script = (
        "for n in "
        + " ".join(shlex.quote(n) for n in eligible)
        + "; do loc=$(command -v -- \"$n\" 2>/dev/null) && printf '%s\\t%s\\n' \"$n\" \"$loc\"; done"
    )
    try:
        proc = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        for n in eligible:
            result[n] = {
                "ok": False,
                "source": None,
                "method": "command -v",
                "error": str(exc),
            }
        return result
    hits = {}
    for line in (proc.stdout or "").splitlines():
        parts = line.split("\\t", 1)
        if len(parts) == 2 and parts[0] in eligible:
            hits[parts[0]] = parts[1]
    for n in eligible:
        hit = hits.get(n, "")
        result[n] = {
            "ok": n in hits and bool(hit),
            "source": hit or None,
            "method": "bash command -v",
            "exit_code": 0 if n in hits else 1,
        }
    return result


def bash_command_v(name: str, batch=None) -> dict:
    if batch is not None:
        if _eligible(name):
            return batch.get(name) or {
                "ok": False,
                "source": None,
                "method": "command -v",
            }
        return {"ok": False, "source": None, "method": "skipped-non-binary"}
    if not _eligible(name):
        return {"ok": False, "source": None, "method": "skipped-non-binary"}
    one = bash_command_v_batch([name])
    return one.get(name) or {
        "ok": False,
        "source": None,
        "method": "command -v",
    }'''

assert old_bash in src, "bash fn anchor missing"
src = src.replace(old_bash, new_bash, 1)

old_ps = '''def powershell_get_command(name: str) -> dict:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        return {
            "ok": False,
            "available": False,
            "method": "Get-Command",
            "reason": "powershell-not-installed-on-this-linux-worktree",
        }'''

new_ps = '''def powershell_get_command_batch(names: list, exe: str) -> dict:
    """Resolve every eligible name with ONE PowerShell invocation.

    Windows platform adaptation: per-name pwsh spawn cost ~3s each (84 names
    = 250s+ alone) blew the measure timeout. Per-name resolution semantics
    are unchanged: still `Get-Command -Name <n> -ErrorAction SilentlyContinue`
    with the Source property.
    """
    result = {}
    eligible = [
        n for n in names if not (n.startswith("mcp__") or n == C.PLUGIN_NAME)
    ]
    for n in names:
        if n.startswith("mcp__") or n == C.PLUGIN_NAME:
            result[n] = {
                "ok": False,
                "available": True,
                "method": "Get-Command",
                "skipped": True,
            }
    if not eligible:
        return result
    quoted = ", ".join("'" + n.replace("'", "''") + "'" for n in eligible)
    ps_script = (
        "foreach ($n in @(" + quoted + ")) { "
        "$c = Get-Command -Name $n -ErrorAction SilentlyContinue; "
        "if ($c) { $s = ''; try { $s = [string]$c.Source } catch { $s = '' }; "
        "Write-Output ($n + \"`t\" + $s) } }"
    )
    try:
        proc = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        for n in eligible:
            result[n] = {
                "ok": False,
                "available": True,
                "method": "Get-Command",
                "error": str(exc),
            }
        return result
    hits = {}
    for line in (proc.stdout or "").splitlines():
        parts = line.split("\\t", 1)
        if len(parts) == 2 and parts[0] in eligible:
            hits[parts[0]] = parts[1]
    for n in eligible:
        result[n] = {
            "ok": n in hits,
            "available": True,
            "method": "Get-Command",
            "source": hits.get(n) or None,
            "exe": exe,
        }
    return result


def powershell_get_command(name: str, batch=None) -> dict:
    if batch is not None:
        if name.startswith("mcp__") or name == C.PLUGIN_NAME:
            return {
                "ok": False,
                "available": True,
                "method": "Get-Command",
                "skipped": True,
            }
        return batch.get(name) or {
            "ok": False,
            "available": True,
            "method": "Get-Command",
        }
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        return {
            "ok": False,
            "available": False,
            "method": "Get-Command",
            "reason": "powershell-not-installed-on-this-linux-worktree",
        }'''

assert old_ps in src, "pwsh fn anchor missing"
src = src.replace(old_ps, new_ps, 1)

old_loop = '''    for rec in corpus["tokens"]:
        name = rec["name"]
        posix = bash_command_v(name)
        ps = powershell_get_command(name)'''
new_loop = '''    bash_map = bash_command_v_batch([r["name"] for r in corpus["tokens"]])
    ps_map = (
        powershell_get_command_batch([r["name"] for r in corpus["tokens"]], pwsh)
        if pwsh
        else {}
    )
    for rec in corpus["tokens"]:
        name = rec["name"]
        posix = bash_command_v(name, batch=bash_map)
        ps = powershell_get_command(name, batch=ps_map)'''
assert old_loop in src, "loop anchor missing"
src = src.replace(old_loop, new_loop, 1)

p.write_text(src, encoding="utf-8")
print("probe2_second_resolver.py patched OK")
