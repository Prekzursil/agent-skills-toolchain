#!/usr/bin/env python3
"""ADV-0036 Probe 1 (REAL Windows): icacls every deployed execution-influencing
path on THIS host and classify writers into owner / administrators / SYSTEM /
broad groups.

This is the upgrade of the G-1 modeled-ACL probe: on this full Windows
checkout the harness is actually deployed under the user profile, so the real
`icacls.exe` output is measured instead of a modeled SecurityDescriptor.
No ACL is modified by this probe (icacls read mode only).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = HERE / "probe1-icacls-real.raw.json"
UNIT = "ADV-0036"

HOME = Path.home()

# Deployed paths that influence execution (hooks, settings, MCP configs,
# launchers) - the real user-profile deployment surface on this host.
def deployed_paths() -> list[tuple[str, str, str]]:
    cand = [
        ("claude-settings", HOME / ".claude" / "settings.json"),
        ("claude-agents-md", HOME / ".claude" / "AGENTS.md"),
        ("claude-claude-md", HOME / ".claude" / "CLAUDE.md"),
        ("claude-json", HOME / ".claude.json"),
        ("codex-config", HOME / ".codex" / "config.toml"),
        ("mcp-json", HOME / ".mcp.json"),
        ("claude-hooks-dir", HOME / ".claude" / "hooks"),
        ("claude-skills-dir", HOME / ".claude" / "skills"),
        ("zcode-settings", HOME / ".zcode" / "settings.json"),
        ("zcode-agents-md", HOME / ".zcode" / "AGENTS.md"),
        # repo-side execution-influencing files (checked out tree)
        ("repo-orchestration", REPO / "ORCHESTRATION.md"),
        ("repo-agent-contract", REPO / "agent_contract.md"),
    ]
    hooks_dir = HOME / ".claude" / "hooks"
    if hooks_dir.is_dir():
        for h in sorted(hooks_dir.rglob("*")):
            if h.is_file() and len(h.relative_to(hooks_dir).parts) <= 2:
                cand.append(("claude-hook:" + h.name, h))
    return [(cid, p) for cid, p in cand if p.exists()]


# Controls: a path known to be owner-writable (this probe's own scratch dir)
# and the Windows/System32 tree which a non-elevated user cannot write.
CONTROL_PROTECTED = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
CONTROL_USER_OWNED = HERE / "controls"


def icacls(path: Path) -> str:
    cp = subprocess.run(
        ["icacls", str(path)], capture_output=True, text=True, timeout=30
    )
    return (cp.stdout + cp.stderr).strip()


WELLKNOWN_BROAD = {
    "BUILTIN\\Users": "broad",
    "BUILTIN\\Everyone": "broad",
    "Everyone": "broad",
    "NT AUTHORITY\\Authenticated Users": "broad",
    "Authenticated Users": "broad",
    "BUILTIN\\Authenticated Users": "broad",
}
WELLKNOWN_ADMIN = {
    "BUILTIN\\Administrators": "admin",
    "NT AUTHORITY\\SYSTEM": "system",
    "BUILTIN\\Admins": "admin",
    "CREATOR OWNER": "owner",
}
WRITE_PERMS = ("W", "M", "F", "APPEND", "AD", "WDAC", "WO", "DC")


def _bucket(sid: str, host: str, user: str) -> str:
    b = WELLKNOWN_BROAD.get(sid) or WELLKNOWN_ADMIN.get(sid)
    if b:
        return b
    if sid.startswith("S-1-"):
        return "foreign-sid"  # unresolved SID: not owner, not a known admin principal
    if "\\" in sid:
        dom, name = sid.split("\\", 1)
        if name.lower() == user.lower():
            return "owner"
        if dom.lower() == host.lower() or dom.lower() == "computername":
            return "broad-local-group"  # machine-local group other than the user
    return "other-principal"


def classify(text: str, user: str) -> dict:
    import re

    host = os.environ.get("COMPUTERNAME", "")
    aces: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("Successfully") or line.startswith("Failed"):
            continue
        # ACE shape: SID:(I)(DENY)(perms) - 1..3 paren groups, path prefix on
        # the first icacls line; continuation lines carry further ACEs.
        for m in re.finditer(r"([^\s:]+(?:\\[^\s:]+)?)\s*:\s*((?:\([^)]*\)\s*)+)", line):
            sid = m.group(1)
            groups = re.findall(r"\(([^)]*)\)", m.group(2))
            if not groups:
                continue
            flags = " ".join(g for g in groups[:-1]) if len(groups) > 1 else ""
            perms = groups[-1]
            deny = "DENY" in flags.upper()
            bucket = _bucket(sid, host, user)
            grants = [p.strip() for p in perms.split(",")]
            writable = any(any(g.startswith(w) for w in WRITE_PERMS) for g in grants)
            aces.append({"sid": sid, "flags": flags, "perms": perms, "deny": deny, "bucket": bucket, "writable_perms": writable})
    allow_broad = [a for a in aces if not a["deny"] and a["writable_perms"] and a["bucket"] in ("broad", "broad-local-group", "foreign-sid")]
    deny_write = [a for a in aces if a["deny"] and a["writable_perms"]]
    owner_write = [a for a in aces if not a["deny"] and a["writable_perms"] and a["bucket"] == "owner"]
    return {"aces": aces, "broad_write_aces": allow_broad, "deny_write_aces": deny_write, "owner_write": bool(owner_write)}


def main() -> int:
    CONTROL_USER_OWNED.mkdir(exist_ok=True)
    (CONTROL_USER_OWNED / "user-owned.txt").write_text("control\n", encoding="utf-8")
    # Both-states classifier control: a scratch dir granted Everyone write
    # (bad state) must FIRE the classifier; an owner-only scratch dir (good
    # state) must stay silent. Scratch ACLs are this probe's own files - no
    # DEPLOYED path's ACL is touched.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="adv36-ctl-") as td:
        bad = Path(td) / "bad"
        good = Path(td) / "good"
        bad.mkdir()
        good.mkdir()
        subprocess.run(["icacls", str(bad), "/grant", "Everyone:(W)"], capture_output=True, timeout=30)
        bad_text = icacls(bad)
        good_text = icacls(good)
        user = os.environ.get("USERNAME", "user")
        ctl_bad = classify(bad_text, user)
        ctl_good = classify(good_text, user)
        control = {
            "fired_on_bad_state": bool(ctl_bad["broad_write_aces"]),
            "silent_on_good_state": not ctl_good["broad_write_aces"],
            "bad_icacls": bad_text,
            "good_icacls": good_text,
        }
    rows = []
    for cid, path in deployed_paths():
        text = icacls(path)
        cls = classify(text, os.environ.get("USERNAME", "user"))
        rows.append(
            {
                "id": cid,
                "path": str(path),
                "exists": True,
                "icacls_text": text,
                "broad_write_aces": cls["broad_write_aces"],
                "deny_write_aces": cls["deny_write_aces"],
                "owner_write": cls["owner_write"],
                "ace_buckets": sorted({a["bucket"] for a in cls["aces"]}),
            }
        )
    # controls: protected + user-owned
    prot_text = icacls(CONTROL_PROTECTED)
    prot_cls = classify(prot_text, os.environ.get("USERNAME", "user"))
    user_text = icacls(CONTROL_USER_OWNED / "user-owned.txt")
    user_cls = classify(user_text, os.environ.get("USERNAME", "user"))
    user_buckets = sorted({a["bucket"] for a in user_cls["aces"]})
    # host facts that bound the empirical limb (probe 2)
    import winreg

    try:
        lua = winreg.QueryValueEx(
            winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"),
            "EnableLUA",
        )[0]
    except OSError:
        lua = None
    report = {
        "unit_id": UNIT,
        "probe": "probe1_icacls_real",
        "host": {"os": os.name, "user": os.environ.get("USERNAME"), "elevated": _is_elevated(), "enable_lua": lua},
        "classifier_control": control,
        "targets": rows,
        "controls": {
            "protected_system32": {"icacls_text": prot_text, "broad_write_aces": prot_cls["broad_write_aces"]},
            "user_owned": {"icacls_text": user_text, "buckets": user_buckets},
        },
        "no_deployed_acl_modified": True,
    }
    OUT.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("unit_id", "probe", "host")}, indent=1))
    for r in rows:
        print(f"{r['id']}: broad_write={[a['sid'] + ':' + a['perms'] for a in r['broad_write_aces']]} deny={[a['sid'] for a in r['deny_write_aces']]} buckets={r['ace_buckets']}")
    print("CLASSIFIER-CONTROL fired_on_bad:", control["fired_on_bad_state"], "silent_on_good:", control["silent_on_good_state"])
    print("CONTROL protected System32 broad_write:", len(report["controls"]["protected_system32"]["broad_write_aces"]))
    print("CONTROL user-owned buckets:", report["controls"]["user_owned"]["buckets"])
    ok = control["fired_on_bad_state"] and control["silent_on_good_state"]
    print("PROBE1_REAL_STATUS=" + ("OK" if ok else "DEGRADED"))
    return 0 if ok else 1


def _is_elevated() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    raise SystemExit(main())
