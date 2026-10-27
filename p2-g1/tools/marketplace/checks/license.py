"""Rule spdx-license: declared license must be an SPDX identifier."""
from __future__ import annotations

SPDX = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "Unlicense",
    "CC0-1.0",
    "GPL-3.0-only",
    "LGPL-3.0-only",
}


def standalone_findings(root):
    import json
    from pathlib import Path

    root = Path(root)
    declared = None
    manifest_path = root / "plugin.json"
    if manifest_path.is_file():
        try:
            doc = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                declared = doc.get("license")
        except json.JSONDecodeError:
            declared = None
    if declared is None:
        lic = root / "LICENSE"
        if lic.is_file():
            head = lic.read_text(encoding="utf-8", errors="replace")[:80]
            if "MIT" in head:
                declared = "MIT"
    if declared is None or str(declared) not in SPDX:
        return [
            {
                "rule": "spdx-license",
                "detail": "license=%r is not an SPDX identifier" % (declared,),
            }
        ]
    return []
