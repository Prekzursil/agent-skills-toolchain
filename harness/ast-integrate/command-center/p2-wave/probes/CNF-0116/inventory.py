"""Credential-path inventory: filenames only, never contents.

The rotation-pool name is accounts.json (BLD-0051 / CNF-0116 tests_required).
Ignore rules are not consulted here; matching is by path shape alone.
"""
from __future__ import annotations

from pathlib import Path

ROTATION_POOL_BASENAME = "accounts.json"
KNOWN_PRESENT_REL = "plugin.json"
KNOWN_PRESENT_LIVE = "command-center/WORK-UNIT-CATALOG.json"

# Synthetic fixture body. Never a live credential. Never copied into the report.
FIXTURE_PLACEHOLDER = b"CNF-0116-filename-only-fixture\n"

INVENTORY_PATHS = (
    "accounts.json",
    "tools/mcp/cloud-hub/accounts.json",
    "tools/mcp/search-hub/accounts.json",
    "credentials.json",
    "secrets.json",
    "auth.json",
    ".env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_ed25519",
    "id_dsa",
    "id_ecdsa",
)

BASENAME_EXACT = {p.rsplit("/", 1)[-1].lower() for p in INVENTORY_PATHS}
BASENAME_EXACT.update(
    {
        "credentials.csv",
        "application_default_credentials.json",
        "service-account.json",
        "gcloud-service-account.json",
    }
)

SUFFIXES = (
    ".credentials.json",
    ".pem",
    ".p12",
    ".pfx",
    ".p8",
)


def posix(rel: str) -> str:
    s = str(rel).replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s.lstrip("/")


def match_rule(rel: str) -> str | None:
    """Return the inventory rule id if this path is credential-shaped. No I/O."""
    path = posix(rel)
    name = Path(path).name
    lower = name.lower()
    if lower == ROTATION_POOL_BASENAME:
        return "inventory:rotation-pool:accounts.json"
    if path.lower() in {p.lower() for p in INVENTORY_PATHS}:
        return f"inventory:path:{path}"
    if lower in BASENAME_EXACT:
        return f"inventory:basename:{name}"
    if lower.startswith(".env"):
        return "inventory:basename:.env*"
    if lower.endswith(SUFFIXES):
        for suf in SUFFIXES:
            if lower.endswith(suf):
                return f"inventory:suffix:{suf}"
    if lower in {"id_rsa", "id_ed25519", "id_dsa", "id_ecdsa"}:
        return f"inventory:ssh:{name}"
    return None


def hits_in(entries: list[str]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for rel in entries:
        path = posix(rel)
        if path in seen:
            continue
        rule = match_rule(path)
        if rule:
            seen.add(path)
            out.append({"path": path, "rule": rule, "contents": None})
    return out


def inventory_doc() -> dict:
    return {
        "kind": "filename-only",
        "never_print_contents": True,
        "rotation_pool_basename": ROTATION_POOL_BASENAME,
        "paths": list(INVENTORY_PATHS),
        "basename_exact": sorted(BASENAME_EXACT),
        "suffixes": list(SUFFIXES),
        "env_prefix": ".env",
        "note": "Filenames and path shapes only. Values are never read into the report.",
    }
