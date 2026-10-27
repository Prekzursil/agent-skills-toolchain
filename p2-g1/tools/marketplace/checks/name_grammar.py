"""Rule name-grammar: package name must be lowercase kebab, no confusables."""
from __future__ import annotations

CONFUSABLES = {"rn": "m", "vv": "w", "cl": "d"}


def standalone_findings(root):
    import json
    import re
    from pathlib import Path

    root = Path(root)
    name = None
    manifest_path = root / "plugin.json"
    if manifest_path.is_file():
        try:
            doc = json.loads(manifest_path.read_text(encoding="utf-8"))
            name = str(doc.get("name") or "") if isinstance(doc, dict) else None
        except json.JSONDecodeError:
            name = None
    if not name:
        return [{"rule": "name-grammar", "detail": "package name absent"}]
    findings = []
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        findings.append(
            {"rule": "name-grammar", "detail": "name %r is not lowercase kebab" % name}
        )
    for bad, good in CONFUSABLES.items():
        if bad in name:
            findings.append(
                {
                    "rule": "name-grammar",
                    "detail": "confusable %r reads as %r" % (bad, good),
                }
            )
    return findings
