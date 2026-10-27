"""Rule permission-declaration: every capability used must be declared."""
from __future__ import annotations

KNOWN_PERMISSIONS = {
    "net",
    "fs-read",
    "fs-write",
    "exec",
    "env",
    "clipboard",
}


def standalone_findings(root):
    import json
    from pathlib import Path

    root = Path(root)
    findings = []
    manifest_path = root / "plugin.json"
    declared = set()
    if manifest_path.is_file():
        try:
            doc = json.loads(manifest_path.read_text(encoding="utf-8"))
            declared = set(doc.get("permissions") or [])
        except json.JSONDecodeError:
            declared = set()
    for perm in sorted(declared):
        if perm not in KNOWN_PERMISSIONS:
            findings.append(
                {
                    "rule": "permission-declaration",
                    "detail": "unknown permission declared: %s" % perm,
                }
            )
    # A package touching settings/config without declaring fs-read undeclared use.
    for marker in ("config-overrides.json", "settings.json"):
        if (root / marker).is_file() and "fs-read" not in declared:
            findings.append(
                {
                    "rule": "permission-declaration",
                    "detail": "reads %s without declaring fs-read" % marker,
                }
            )
    return findings
