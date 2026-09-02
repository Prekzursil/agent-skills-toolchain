"""Locate the installed client on this box. Never print secrets."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

CLIENT_NAMES = ("claude", "cursor-agent", "agent", "cursor")
ENV_NEEDLES = (
    b"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH",
    b"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS",
    b"Concurrent subagent limit reached",
)


def _run(cmd: list[str], timeout: int = 8) -> dict:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {"ok": False, "reason": "not-found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout"}
    out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
    # Strip anything that looks like a token just in case --help dumps env.
    lines = []
    for line in out.splitlines():
        low = line.lower()
        if "api_key" in low or "apikey" in low or "authorization" in low:
            lines.append("<redacted-credential-shaped-line>")
        else:
            lines.append(line)
    return {
        "ok": p.returncode == 0,
        "exit_code": p.returncode,
        "text": "\n".join(lines)[:4000],
    }


def _strings_needles(path: Path) -> dict:
    found = []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {"readable": False, "error": type(exc).__name__, "needles": []}
    # Follow one symlink hop for node wrappers.
    target = path
    try:
        if path.is_symlink():
            target = path.resolve()
            raw = target.read_bytes()
    except OSError:
        pass
    blob = raw
    # node shebang wrappers are tiny; search nearby .js if present.
    search_blobs = [blob]
    if len(blob) < 4096 and b"node" in blob[:80].lower():
        sibling = target.with_suffix(".js")
        if sibling.is_file():
            try:
                search_blobs.append(sibling.read_bytes())
            except OSError:
                pass
        # npm global layout: ../lib/node_modules/@anthropic-ai/claude-code
        for cand in (
            target.parent / "lib" / "node_modules" / "@anthropic-ai" / "claude-code",
            target.parent.parent / "lib" / "node_modules" / "@anthropic-ai" / "claude-code",
        ):
            if cand.is_dir():
                for js in cand.rglob("*.js"):
                    try:
                        b = js.read_bytes()
                    except OSError:
                        continue
                    if any(n in b for n in ENV_NEEDLES):
                        search_blobs.append(b)
                        break
    hay = b"\n".join(search_blobs)
    for needle in ENV_NEEDLES:
        found.append({"needle": needle.decode("ascii"), "present": needle in hay})
    return {
        "readable": True,
        "resolved": str(target),
        "bytes": len(blob),
        "needles": found,
    }


def discover() -> dict:
    clients = []
    for name in CLIENT_NAMES:
        path = shutil.which(name)
        row = {"name": name, "which": path, "installed": bool(path)}
        if path:
            row["version"] = _run([path, "--version"])
            row["help_head"] = _run([path, "--help"])
            row["binary"] = _strings_needles(Path(path))
        clients.append(row)
    installed = [c for c in clients if c["installed"]]
    claude = next((c for c in clients if c["name"] == "claude"), None)
    return {
        "installed_count": len(installed),
        "installed_names": [c["name"] for c in installed],
        "claude_installed": bool(claude and claude["installed"]),
        "live_llm_spawn": "NOT-CHECKED",
        "live_llm_spawn_reason": (
            "G-1 probes must re-run inside 180s without rotating keys. "
            "This unit measures the published Agent-tool contract plus any "
            "binary-string needles; it does not pay for a nested LLM tree."
        ),
        "clients": clients,
    }
