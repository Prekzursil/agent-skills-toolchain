"""Rule manifest-schema: package manifest must exist and carry required keys."""
from __future__ import annotations

REQUIRED_KEYS = ("name", "version", "license")


def standalone_findings(root):
    root = __import__("pathlib").Path(root)
    manifest_path = root / "plugin.json"
    findings = []
    if not manifest_path.is_file():
        findings.append({"rule": "manifest-schema", "detail": "plugin.json absent"})
        return findings
    import json

    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append({"rule": "manifest-schema", "detail": "unparseable: %s" % exc})
        return findings
    if not isinstance(doc, dict):
        findings.append({"rule": "manifest-schema", "detail": "manifest is not an object"})
        return findings
    for key in REQUIRED_KEYS:
        if not doc.get(key):
            findings.append({"rule": "manifest-schema", "detail": "missing key: %s" % key})
    return findings
