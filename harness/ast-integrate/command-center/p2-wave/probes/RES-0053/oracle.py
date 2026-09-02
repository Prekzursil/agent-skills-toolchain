#!/usr/bin/env python3
"""Probe-local installed-client oracle.

Derives whether each registry's revocation reaches an already-installed client
from capture phrases and API fields. Emit must not import this module.
"""
from __future__ import annotations

from facts import (
    contains,
    crates_futures_020,
    jetbrains_python,
    npm_event_stream,
    npm_flatmap,
    pypi_urllib3_yanked,
    vscode_material,
)

# Phrases that must be present in the named capture. Probe 2 fails closed if a
# capture no longer contains them (version-skew), rather than inventing policy.
PHRASES = {
    "npm-prose-unpublish-policy": "their builds will not break",
    "npm-prose-deprecate-cli": (
        "providing a deprecation warning to all who attempt to install it"
    ),
    "pypi-prose-pep592": "acts as if it had not been yanked",
    "crates-prose-cargo-yank": (
        "Existing lock files or direct downloads are not affected"
    ),
    "vscode-prose-runtime-security": "automatically uninstalled by VS Code",
    "jetbrains-prose-hidden-release": (
        "This won’t affect users who have already installed this version"
    ),
    "chrome-api-safe-browsing-help": (
        "If you have an abusive or malicious extension installed, Chrome disables it"
    ),
    "chrome-prose-disabled-extensions": "Chrome has turned off one or more of your extensions",
    "incident-npm-blog-event-stream": (
        "we recommend that you update to a later version as soon as possible"
    ),
}


def phrases_ok() -> list[str]:
    missing = []
    for cid, needle in PHRASES.items():
        if not contains(cid, needle):
            missing.append(f"{cid}:{needle[:40]}")
    return missing


def expected_rows() -> dict[str, dict]:
    """Independent expected table. Keys are registry ids used by the artifact."""
    flat = npm_flatmap()
    es = npm_event_stream()
    yanked = pypi_urllib3_yanked()
    fut = crates_futures_020()
    vs = vscode_material()
    jb = jetbrains_python()
    return {
        "npm": {
            "installed_client_reaches": False,
            "reach_channel": "none",
            "api_security_holder": bool(flat["latest_is_security_holder"]),
            "event_stream_3_3_6_installable": bool(es["has_3_3_6_in_versions"]),
            "require": (
                flat["latest_is_security_holder"]
                and not es["has_3_3_6_in_versions"]
                and es["time_3_3_6"]
            ),
        },
        "pypi": {
            "installed_client_reaches": False,
            "reach_channel": "none",
            "yanked_count": len(yanked),
            "require": len(yanked) >= 1,
        },
        "crates.io": {
            "installed_client_reaches": False,
            "reach_channel": "none",
            "futures_0_2_0_yanked": fut["yanked"] is True,
            "require": fut["yanked"] is True,
        },
        "vs-code-marketplace": {
            "installed_client_reaches": True,
            "reach_channel": "malware-blocklist-not-gallery-unpublish",
            "listing_still_public": bool(vs["public"]),
            "gallery_has_revoked_field": bool(vs["has_revoked_field"]),
            "require": vs["found"] and vs["public"] and not vs["has_revoked_field"],
        },
        "jetbrains-marketplace": {
            "installed_client_reaches": False,
            "reach_channel": "none",
            "api_has_hidden_and_blocked": jb["has_hidden_field"]
            and jb["has_blocked_field"],
            "require": jb["has_hidden_field"] and jb["has_blocked_field"],
        },
        "chrome-web-store": {
            "installed_client_reaches": True,
            "reach_channel": "safe-browsing-malware-disable-not-mere-unpublish",
            "require": True,
        },
    }
