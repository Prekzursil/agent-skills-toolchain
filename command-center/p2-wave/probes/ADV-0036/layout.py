#!/usr/bin/env python3
"""Modeled Windows deploy layout plus packaging census for ADV-0036.

The worktree has no Windows installer that sets ACLs. Nodes below are the
post-install shapes a clean copy would inherit, plus planted controls.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from lib_acl import ACE, SecurityDescriptor

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ACL_CMD_RE = re.compile(
    r"\b(icacls(?:\.exe)?|cacls(?:\.exe)?|Set-Acl|"
    r"FileSystemAccessRule|SetAccessRule)\b",
    re.IGNORECASE,
)
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    "ADV-0036",
}
SKIP_FILE_NAMES = {
    "WORK-UNIT-CATALOG.json",
}
WATCH_RELS = (
    "tools/plugin/cli.py",
    "tools/plugin/cache_ownership.py",
    "tools/router/inject.py",
    "command-center/schema/threat-model.schema.json",
    "command-center/WORK-UNIT-CATALOG.json",
)


def A(*args, **kwargs) -> ACE:
    return ACE(*args, **kwargs)


def _win(*parts: str) -> str:
    return "C:\\" + "\\".join(p for p in parts if p)


def _pf(*parts: str) -> str:
    return _win("Program Files", "Harness", *parts)


def _pd(*parts: str) -> str:
    return _win("ProgramData", "Harness", *parts)


def _ad(*parts: str) -> str:
    return _win("Users", "nonadmin", "AppData", "Roaming", "Harness", *parts)


def dacl_program_files() -> list[ACE]:
    return [
        A("ALLOW", "SY", "F"),
        A("ALLOW", "BA", "F"),
        A("ALLOW", "BU", "RX", inherited=True),
    ]


def dacl_appdata() -> list[ACE]:
    return [
        A("ALLOW", "SY", "F"),
        A("ALLOW", "BA", "F"),
        A("ALLOW", "OW", "F"),
    ]


def dacl_protected() -> list[ACE]:
    return [A("ALLOW", "SY", "F"), A("ALLOW", "BA", "F")]


def dacl_programdata_users_modify() -> list[ACE]:
    return [
        A("ALLOW", "SY", "F"),
        A("ALLOW", "BA", "F"),
        A("ALLOW", "AU", "M", inherited=True),
    ]


def parent_program_files() -> list[ACE]:
    return [
        A("ALLOW", "SY", "F"),
        A("ALLOW", "BA", "F"),
        A("ALLOW", "BU", "RX"),
    ]


def parent_users_modify() -> list[ACE]:
    return [
        A("ALLOW", "SY", "F"),
        A("ALLOW", "BA", "F"),
        A("ALLOW", "BU", "M"),
    ]


@dataclass
class Node:
    node_id: str
    role: str
    source_rel: str
    sd: SecurityDescriptor
    control: str | None = None
    note: str = ""


def deployed_nodes() -> list[Node]:
    """Execution-influencing paths after a modeled Windows install."""
    pf_parent = parent_program_files()
    ad_parent = dacl_appdata()
    pd_parent = dacl_programdata_users_modify()
    nodes = [
        Node(
            "launcher-programfiles",
            "launcher",
            "tools/plugin/cli.py",
            SecurityDescriptor(
                path=_pf("bin", "launcher.py"),
                owner="BA",
                dacl=dacl_program_files(),
                parent_path=_pf("bin"),
                parent_owner="BA",
                parent_dacl=pf_parent,
            ),
            note="Default Program Files ACL: Users RX only.",
        ),
        Node(
            "hooks-programfiles",
            "hooks",
            "tools/router/inject.py",
            SecurityDescriptor(
                path=_pf("hooks", "hooks.json"),
                owner="BA",
                dacl=dacl_program_files(),
                parent_path=_pf("hooks"),
                parent_owner="BA",
                parent_dacl=pf_parent,
            ),
            note="Machine-wide hooks inherit Users RX.",
        ),
        Node(
            "mcp-programfiles",
            "mcp",
            "tools/router/capability-index.json",
            SecurityDescriptor(
                path=_pf("mcp", "mcp.json"),
                owner="BA",
                dacl=dacl_program_files(),
                parent_path=_pf("mcp"),
                parent_owner="BA",
                parent_dacl=pf_parent,
            ),
            note="Machine-wide MCP config, Users RX.",
        ),
        Node(
            "settings-programfiles",
            "settings",
            "tools/plugin/cache_ownership.py",
            SecurityDescriptor(
                path=_pf("settings", "defaults.json"),
                owner="BA",
                dacl=dacl_program_files(),
                parent_path=_pf("settings"),
                parent_owner="BA",
                parent_dacl=pf_parent,
            ),
            note="Machine-wide defaults, Users RX.",
        ),
        Node(
            "hooks-appdata",
            "hooks",
            "tools/router/inject.py",
            SecurityDescriptor(
                path=_ad("hooks", "hooks.json"),
                owner="USER",
                dacl=dacl_appdata(),
                parent_path=_ad("hooks"),
                parent_owner="USER",
                parent_dacl=ad_parent,
            ),
            note="Per-user hooks: owner Full, non-elevated write.",
        ),
        Node(
            "settings-appdata",
            "settings",
            "tools/plugin/cache_ownership.py",
            SecurityDescriptor(
                path=_ad("settings.json"),
                owner="USER",
                dacl=dacl_appdata(),
                parent_path=_ad(),
                parent_owner="USER",
                parent_dacl=ad_parent,
            ),
            note="Per-user settings: owner Full.",
        ),
        Node(
            "mcp-appdata",
            "mcp",
            "tools/router/capability-index.json",
            SecurityDescriptor(
                path=_ad("mcp.json"),
                owner="USER",
                dacl=dacl_appdata(),
                parent_path=_ad(),
                parent_owner="USER",
                parent_dacl=ad_parent,
            ),
            note="Per-user MCP config: owner Full.",
        ),
        Node(
            "mcp-programdata-broad",
            "mcp",
            "tools/router/capability-index.json",
            SecurityDescriptor(
                path=_pd("mcp", "mcp.json"),
                owner="BA",
                dacl=dacl_programdata_users_modify(),
                parent_path=_pd("mcp"),
                parent_owner="BA",
                parent_dacl=pd_parent,
            ),
            note="ProgramData Authenticated Users (M) inherited: non-elevated write.",
        ),
        Node(
            "hooks-everyone",
            "hooks",
            "tools/router/inject.py",
            SecurityDescriptor(
                path=_pf("hooks", "everyone-writable.json"),
                owner="BA",
                dacl=[
                    A("ALLOW", "SY", "F"),
                    A("ALLOW", "BA", "F"),
                    A("ALLOW", "WD", "F"),
                ],
                parent_path=_pf("hooks"),
                parent_owner="BA",
                parent_dacl=pf_parent,
            ),
            control="planted-everyone-write",
            note="Planted Everyone(F) on a hook file.",
        ),
        Node(
            "hooks-inherited-deny-trap",
            "hooks",
            "tools/router/inject.py",
            SecurityDescriptor(
                path=_pf("hooks", "inherited-deny-trap.json"),
                owner="BA",
                dacl=[
                    A("ALLOW", "SY", "F"),
                    A("ALLOW", "BA", "F"),
                    A("DENY", "BU", "W", inherited=True),
                    A("ALLOW", "BU", "M", inherited=True),
                ],
                parent_path=_pf("hooks"),
                parent_owner="BA",
                parent_dacl=pf_parent,
            ),
            control="inherited-deny-trap",
            note="Inherited Users deny(W) plus inherited Users(M): textual writer, empirical deny.",
        ),
        Node(
            "settings-explicit-over-inherited-deny",
            "settings",
            "tools/plugin/cache_ownership.py",
            SecurityDescriptor(
                path=_pf("settings", "explicit-allow-over-deny.json"),
                owner="BA",
                dacl=[
                    A("ALLOW", "AU", "W"),
                    A("DENY", "AU", "W", inherited=True),
                    A("ALLOW", "SY", "F"),
                    A("ALLOW", "BA", "F"),
                ],
                parent_path=_pf("settings"),
                parent_owner="BA",
                parent_dacl=pf_parent,
            ),
            control="explicit-allow-over-inherited-deny",
            note="Explicit Authenticated Users(W) beats inherited deny.",
        ),
        Node(
            "hooks-replace-via-parent",
            "hooks",
            "tools/router/inject.py",
            SecurityDescriptor(
                path=_pf("writable-parent", "hooks.json"),
                owner="BA",
                dacl=dacl_protected(),
                parent_path=_pf("writable-parent"),
                parent_owner="BA",
                parent_dacl=parent_users_modify(),
            ),
            control="replace-via-parent",
            note="File DACL is SY+BA only; parent Users(M) allows delete-and-replace.",
        ),
        Node(
            "control-protected",
            "control",
            "tools/plugin/cli.py",
            SecurityDescriptor(
                path=r"C:\ProgramData\ssh\administrators_authorized_keys",
                owner="BA",
                dacl=dacl_protected(),
                parent_path=r"C:\ProgramData\ssh",
                parent_owner="BA",
                parent_dacl=dacl_protected(),
            ),
            control="protected",
            note="Known-protected: SYSTEM+Administrators only. Must reject non-elevated write.",
        ),
        Node(
            "control-user-owned",
            "control",
            "tools/plugin/cli.py",
            SecurityDescriptor(
                path=_ad("user-owned.txt"),
                owner="USER",
                dacl=dacl_appdata(),
                parent_path=_ad(),
                parent_owner="USER",
                parent_dacl=ad_parent,
            ),
            control="user-owned",
            note="Known user-owned: must accept non-elevated write.",
        ),
    ]
    return nodes


def packaging_census(repo: Path | None = None) -> dict:
    """Scan the worktree for installer ACL commands. Does not change files."""
    root = repo or REPO
    hits: list[dict] = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel_dir.startswith("command-center/p2-wave/probes/ADV-0036"):
            continue
        for name in filenames:
            if name in SKIP_FILE_NAMES:
                continue
            if not name.lower().endswith(
                (".py", ".ps1", ".bat", ".cmd", ".json", ".md", ".yml", ".yaml",
                 ".xml", ".nsi", ".wxs", ".iss", ".sh")
            ):
                continue
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not ACL_CMD_RE.search(text):
                continue
            hits.append({"path": rel, "kind": "acl-command-mention"})
    installer_hits = [
        h
        for h in hits
        if not h["path"].startswith("command-center/WORK-UNIT-CATALOG")
        and "/WORK-UNIT-CATALOG.json" not in h["path"]
    ]
    # Catalog names icacls as this unit's probe. That is spec, not packaging.
    # An ACL mention only counts as PACKAGING when it sits on an actual
    # installer/packaging surface (installer script formats, or a path that
    # names an install/setup/packaging/deploy step). Estate skills, rules
    # docs and test corpora mention icacls without being this product's
    # installer; they are still recorded in `mentions` above.
    packaging_tokens = (
        "install",
        "setup",
        "packag",
        "deploy",
        "msi",
        "wix",
        "nsis",
        "inno",
    )
    installer_exts = (".nsi", ".wxs", ".iss")
    packaging_hits = [
        h
        for h in installer_hits
        if not h["path"].startswith("command-center/")
        and (
            h["path"].lower().endswith(installer_exts)
            or any(tok in h["path"].lower() for tok in packaging_tokens)
        )
    ]
    return {
        "files_scanned": scanned,
        "mentions": hits,
        "packaging_mentions": packaging_hits,
        "installer_sets_acl": bool(packaging_hits),
        "icacls_binary": shutil.which("icacls") or shutil.which("icacls.exe"),
        "live_windows": os.name == "nt",
        "platform": os.name,
    }


def product_stat_snapshot(repo: Path | None = None) -> dict[str, dict]:
    root = repo or REPO
    out: dict[str, dict] = {}
    for rel in WATCH_RELS:
        path = root / rel
        if not path.is_file():
            out[rel] = {"present": False}
            continue
        st = path.stat()
        out[rel] = {
            "present": True,
            "mode": st.st_mode,
            "uid": st.st_uid,
            "gid": st.st_gid,
            "mtime_ns": st.st_mtime_ns,
            "size": st.st_size,
        }
    return out
