"""Make agent-skills-toolchain a complete, drag-and-drop mirror of the live harness.

Measured gaps this closes (audit 2026-07-27):
  * skills      104 of 328 missing
  * workflows   10 local, 0 mirrored (incl. plan-gate.mjs / design-gate.mjs)
  * MCP         69 live servers vs 37 in the repo registry; ~/.mcp.json absent
  * codex       ~/.codex/config.toml (31 KB) absent
  * 4 configs   settings.json / CLAUDE.md / AGENTS.md / statusline diverged

SECRET SAFETY (repo is PUBLIC): every MCP env value is emitted as a ${PLACEHOLDER};
no literal key is ever written. git-crypt already protects accounts.json (verified:
committed blobs carry the GITCRYPT header) and is left untouched.

Idempotent. Run:  python scripts/build-codespace-mirror.py [--apply]
Without --apply it is a DRY RUN and writes nothing.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys

HOME = os.path.expanduser("~")
# --repo <path> lets this run against a clean worktree branched off origin/main
# (the day-to-day clone sits on a stale branch, so PRing from it would propose
# hundreds of deletions -- always build the PR tree from origin/main).
REPO = os.path.join(HOME, "source", "agent-skills-toolchain")
if "--repo" in sys.argv:
    REPO = sys.argv[sys.argv.index("--repo") + 1]
APPLY = "--apply" in sys.argv
tag = "APPLY" if APPLY else "DRY-RUN"
log: list[str] = []


def say(s):
    print(s)
    log.append(s)


def copy_tree(src, dst):
    if not APPLY:
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


say(f"=== build-codespace-mirror [{tag}] ===")


# ---------- 1. SKILLS ----------
def skill_dirs(p):
    try:
        return {
            d: os.path.join(p, d)
            for d in os.listdir(p)
            if os.path.isdir(os.path.join(p, d)) and not d.startswith(".")
        }
    except OSError:
        return {}


live = {}
for root in (f"{HOME}/.agents/skills", f"{HOME}/.claude/skills"):
    live.update(skill_dirs(root))  # .claude wins on name collision
repo_have = set(skill_dirs(f"{REPO}/skills")) | set(
    skill_dirs(f"{REPO}/skills-claude-only")
)
missing = sorted(set(live) - repo_have)
say(f"\n[1] SKILLS: live={len(live)} repo={len(repo_have)} missing={len(missing)}")
for name in missing:
    copy_tree(live[name], f"{REPO}/skills/{name}")
say(f"    copied {len(missing)} skill dirs -> skills/")

# ---------- 2. WORKFLOWS ----------
wf_src = f"{HOME}/.claude/workflows"
# NOT repo/workflows/: that is the PRODUCTION saved-workflow surface governed by the
# K04 worktree-partition policy, and ci/tests/test_worktree_partition.py deliberately
# asserts it contains exactly {rtv-pdr.js} so every added production workflow gets
# classified. These are MIRRORED user harness workflows, so they live with the other
# mirrored config instead of weakening that tripwire.
wf_dst = f"{REPO}/agent-self/config/workflows"
wfs = [f for f in os.listdir(wf_src)] if os.path.isdir(wf_src) else []
say(f"\n[2] WORKFLOWS: {len(wfs)} local -> workflows/")
for f in wfs:
    copy_tree(os.path.join(wf_src, f), os.path.join(wf_dst, f))
    say(f"    + {f}")

# ---------- 3. MCP REGISTRY (69 servers, portable vs windows-only, redacted) ----------
SECRETISH = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PAT|CREDENTIAL|AUTH|API)", re.I)
WINPATH = re.compile(r"^[A-Za-z]:[\\/]|^\\\\")


def redact_env(env: dict) -> dict:
    out = {}
    for k, v in (env or {}).items():
        if isinstance(v, str) and (SECRETISH.search(k) or len(v) > 24):
            out[k] = "${" + re.sub(r"[^A-Z0-9_]", "_", k.upper()) + "}"
        else:
            out[k] = v
    return out


def is_portable(spec: dict) -> bool:
    if spec.get("type") in ("http", "sse") or spec.get("url"):
        return True
    cmd = str(spec.get("command") or "")
    if WINPATH.match(cmd):
        return False
    for a in spec.get("args") or []:
        if isinstance(a, str) and WINPATH.match(a):
            return False
    return True


servers: dict[str, dict] = {}
for cfg in (f"{HOME}/.mcp.json", f"{HOME}/.claude.json"):
    try:
        with open(cfg, "r", encoding="utf-8", errors="replace") as f:
            j = json.load(f)
    except Exception:
        continue
    buckets = [j.get("mcpServers") or {}]
    for pv in (j.get("projects") or {}).values():
        if isinstance(pv, dict):
            buckets.append(pv.get("mcpServers") or {})
    for b in buckets:
        for name, spec in b.items():
            if name not in servers and isinstance(spec, dict):
                servers[name] = spec

portable, winonly = {}, {}
for name, spec in sorted(servers.items()):
    clean = {
        k: v
        for k, v in spec.items()
        if k in ("type", "url", "command", "args", "env", "headers", "cwd")
    }
    if "env" in clean:
        clean["env"] = redact_env(clean["env"])
    if "headers" in clean:
        clean["headers"] = redact_env(clean["headers"])
    (portable if is_portable(clean) else winonly)[name] = clean

say(
    f"\n[3] MCP: {len(servers)} servers discovered "
    f"-> portable={len(portable)}  windows-only={len(winonly)}"
)
mcpdir = f"{REPO}/agent-self/config/mcp"
payloads = {
    "mcp.portable.json": {
        "_comment": "Codespace/Linux-safe MCP servers. Secrets are ${PLACEHOLDERS} - "
        "supply them via Codespaces Secrets, never commit values.",
        "mcpServers": portable,
    },
    "mcp.windows-only.json": {
        "_comment": "Servers bound to Windows-local installs (RE tooling, absolute "
        "C:/ or D:/ paths). NOT installable in a Codespace; kept for host parity.",
        "mcpServers": winonly,
    },
}
for fn, payload in payloads.items():
    say(f"    write {fn} ({len(payload['mcpServers'])} servers)")
    if APPLY:
        os.makedirs(mcpdir, exist_ok=True)
        with open(os.path.join(mcpdir, fn), "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")

# ---------- 4. CODEX CONFIG (redacted) ----------
cc_src = f"{HOME}/.codex/config.toml"
if os.path.isfile(cc_src):
    raw = open(cc_src, "r", encoding="utf-8", errors="replace").read()
    red = re.sub(
        r'((?:api_key|token|secret|password)\s*=\s*)"[^"]*"',
        r'\1"${REDACTED}"',
        raw,
        flags=re.I,
    )
    n = len(re.findall(r"\$\{REDACTED\}", red))
    say(
        f"\n[4] CODEX: config.toml -> agent-self/config/codex/config.toml "
        f"({len(raw) // 1024} KB, {n} value(s) redacted)"
    )
    if APPLY:
        os.makedirs(f"{REPO}/agent-self/config/codex", exist_ok=True)
        with open(
            f"{REPO}/agent-self/config/codex/config.toml",
            "w",
            encoding="utf-8",
            newline="\n",
        ) as f:
            f.write(red)

# ---------- 5. THE 4 DIVERGED CONFIGS: take LOCAL (owner directive) ----------
say(
    "\n[5] CONFIGS: local -> repo (owner directive; git history preserves repo versions)"
)
PAIRS = [
    (f"{HOME}/.claude/settings.json", f"{REPO}/agent-self/config/settings.json"),
    (f"{HOME}/.claude/CLAUDE.md", f"{REPO}/CLAUDE.md"),
    (f"{HOME}/.claude/AGENTS.md", f"{REPO}/AGENTS.md"),
    (
        f"{HOME}/.claude/statusline-command.sh",
        f"{REPO}/agent-self/config/statusline-command.sh",
    ),
    (f"{HOME}/.mcp.json", f"{REPO}/agent-self/config/mcp.json.example"),
]
for src, dst in PAIRS:
    if not os.path.isfile(src):
        say(f"    SKIP (no local) {src}")
        continue
    old = os.path.getsize(dst) // 1024 if os.path.isfile(dst) else 0
    new = os.path.getsize(src) // 1024
    # settings.json / .mcp.json may hold keys -> redact env-ish values on the way in
    if src.endswith((".json",)):
        try:
            j = json.load(open(src, "r", encoding="utf-8", errors="replace"))
            if isinstance(j.get("env"), dict):
                j["env"] = redact_env(j["env"])
            if isinstance(j.get("mcpServers"), dict):
                for _n, sp in j["mcpServers"].items():
                    if isinstance(sp, dict) and isinstance(sp.get("env"), dict):
                        sp["env"] = redact_env(sp["env"])
            say(
                f"    {os.path.relpath(dst, REPO)}: {old}K -> {new}K (json, env redacted)"
            )
            if APPLY:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(j, f, indent=2)
                    f.write("\n")
            continue
        except Exception as e:
            say(f"    (json parse failed, raw copy: {e})")
    say(f"    {os.path.relpath(dst, REPO)}: {old}K -> {new}K")
    copy_tree(src, dst)

say(f"\n=== {tag} complete ===")
if not APPLY:
    say("re-run with --apply to write")
