#!/usr/bin/env python3
"""Syntactic classifier for GitHub Actions `uses:` refs and permissions blocks."""
from __future__ import annotations

import re
from typing import Any

SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
SHA_ABBREV = re.compile(r"^[0-9a-fA-F]{7,39}$")
VERSION_TAG = re.compile(r"^v?\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.]+)?$")
BRANCH_HINTS = frozenset(
    {
        "main",
        "master",
        "develop",
        "dev",
        "trunk",
        "head",
        "latest",
        "release",
        "default",
    }
)
HIGHEST = "critical"

# GitHub-owned action namespaces still count as third-party to *this* repo:
# they are not first-party until the action lives under ./.
LOCAL_PREFIXES = ("./", "../")


def strip_quotes(value: str) -> str:
    s = value.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {"'", '"'}:
        return s[1:-1].strip()
    return s


def split_uses(raw: str) -> dict[str, Any]:
    s = strip_quotes(raw or "")
    if s.startswith("docker://"):
        image = s[len("docker://") :]
        image, _, tag = image.partition(":")
        return {
            "kind": "docker",
            "action": image or s,
            "ref": tag or "",
            "raw": s,
            "local": False,
        }
    if s.startswith(LOCAL_PREFIXES) or s.startswith(".github/"):
        action, _, ref = s.partition("@")
        return {
            "kind": "local",
            "action": action,
            "ref": ref,
            "raw": s,
            "local": True,
        }
    if "@" not in s:
        return {
            "kind": "remote",
            "action": s,
            "ref": "",
            "raw": s,
            "local": False,
        }
    action, ref = s.rsplit("@", 1)
    return {
        "kind": "remote",
        "action": action,
        "ref": ref,
        "raw": s,
        "local": False,
    }


def classify_ref(ref: str) -> str:
    r = (ref or "").strip()
    if not r:
        return "unpinned"
    if SHA40.match(r):
        return "sha-pinned"
    if VERSION_TAG.match(r):
        return "tag-pinned"
    if SHA_ABBREV.match(r):
        return "sha-abbreviated"
    low = r.lower()
    if low in BRANCH_HINTS or "/" in r or r.endswith("-latest"):
        return "branch-pinned"
    return "branch-pinned"


def pin_severity(pin_class: str, local: bool) -> str:
    if local:
        return "none"
    return {
        "sha-pinned": "none",
        "tag-pinned": "high",
        "sha-abbreviated": "high",
        "branch-pinned": HIGHEST,
        "unpinned": HIGHEST,
    }.get(pin_class, "medium")


def classify_uses(raw: str) -> dict[str, Any]:
    parts = split_uses(raw)
    pin_class = classify_ref(parts["ref"]) if not parts["local"] else "local"
    if parts["kind"] == "docker":
        pin_class = "docker-tag" if parts["ref"] else "docker-unpinned"
    sev = pin_severity(
        "unpinned"
        if pin_class in {"docker-unpinned"}
        else ("tag-pinned" if pin_class == "docker-tag" else pin_class),
        parts["local"],
    )
    if parts["kind"] == "docker":
        sev = "medium" if parts["ref"] else HIGHEST
    flagged = sev in {HIGHEST, "high"}
    return {
        **parts,
        "pin_class": pin_class,
        "severity": sev,
        "flagged": flagged,
        "highest_severity": sev == HIGHEST,
        "third_party": (not parts["local"]) and parts["kind"] != "docker",
    }


def github_repo(action: str) -> str | None:
    parts = [p for p in (action or "").split("/") if p]
    if len(parts) < 2:
        return None
    if parts[0] in {".", ".."}:
        return None
    return f"{parts[0]}/{parts[1]}"


def permissions_scope(perms: Any) -> dict[str, Any]:
    """Classify a workflow- or job-level permissions value."""
    if perms is None:
        return {
            "present": False,
            "form": "missing",
            "least_privilege": False,
            "severity": "high",
            "flagged": True,
            "reason": "inherits default GITHUB_TOKEN scope",
        }
    if perms == "read-all":
        return {
            "present": True,
            "form": "read-all",
            "least_privilege": True,
            "severity": "none",
            "flagged": False,
            "reason": "explicit read-all",
        }
    if perms == "write-all":
        return {
            "present": True,
            "form": "write-all",
            "least_privilege": False,
            "severity": HIGHEST,
            "flagged": True,
            "reason": "write-all is the opposite of least privilege",
        }
    if isinstance(perms, dict):
        if not perms:
            return {
                "present": True,
                "form": "empty-map",
                "least_privilege": True,
                "severity": "none",
                "flagged": False,
                "reason": "permissions: {} grants nothing",
            }
        writes = [
            k
            for k, v in perms.items()
            if str(v).lower() in {"write", "write-all"}
        ]
        if writes:
            return {
                "present": True,
                "form": "map",
                "least_privilege": False,
                "severity": "medium",
                "flagged": True,
                "reason": f"write grants: {writes}",
                "grants": perms,
            }
        return {
            "present": True,
            "form": "map",
            "least_privilege": True,
            "severity": "none",
            "flagged": False,
            "reason": "explicit non-write grants",
            "grants": perms,
        }
    return {
        "present": True,
        "form": "unknown",
        "least_privilege": False,
        "severity": "medium",
        "flagged": True,
        "reason": f"unparsed permissions value {type(perms).__name__}",
    }
