"""Canonical LF payloads for each parser family BLD-0008 exercises."""

from __future__ import annotations

JSON_OBJECT = '{\n  "ok": true,\n  "n": 1\n}\n'

JSONL = '{"id": "R-M01", "verb": "close"}\n{"id": "R-M02", "verb": "note"}\n'

YAML_DOC = "name: probe\ncount: 1\nitems:\n  - a\n  - b\n"

TOML_DOC = 'name = "probe"\ncount = 1\n'

FRONTMATTER = """---
name: skill
description: byte-form probe
---
# Body
"""

ENV_FILE = "FOO=bar\nBAZ=1\n"

MANIFEST = """{
  "unit_id": "BLD-0008",
  "artifacts": [
    {"path": "command-center/receipts/BLD-0008.json", "role": "primary"}
  ]
}
"""

RECEIPT = """{
  "kind": "receipt",
  "unit_id": "BLD-0008",
  "state": "SUCCESS"
}
"""

REGISTER = """# Register

## 1. OUTSTANDING

### 1A. Program A - toolchain / Prompt Two (32)

| id | title |
| --- | --- |
| R-A01 | First outstanding toolchain row |
| R-A02 | Second outstanding toolchain row |

## 2. DELIBERATELY-SKIPPED

### leftover

| D-A01 | skipped on purpose |
"""

PAYLOADS = {
    "json-catalog": JSON_OBJECT,
    "jsonl-events": JSONL,
    "yaml": YAML_DOC,
    "toml": TOML_DOC,
    "md-frontmatter": FRONTMATTER,
    "env-file": ENV_FILE,
    "manifest-json": MANIFEST,
    "receipt-oracle": RECEIPT,
    "register-md": REGISTER,
}
