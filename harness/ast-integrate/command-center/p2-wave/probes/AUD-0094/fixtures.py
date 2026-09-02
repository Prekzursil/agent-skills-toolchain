"""Planted 5-tree DELETE-ALL estate used as the use-vs-mention / runtime control."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ESTATE = HERE / "fixtures" / "estate"
SURVIVING = ESTATE / "surviving"

CHANGELOG = """# CHANGELOG

## Owner-approved DELETE-ALL retirement

Removed aud0094-retired/tree-agentbridge/file-15.py as part of the retirement
(deleted; do not restore). This sentence is a mention of a deleted path, not a
runtime reference.

The same retirement also deleted aud0094-retired/tree-agentbridge/file-00.py;
that path is additionally opened by importer.py and must classify as USE there.
"""

IMPORTER = '''#!/usr/bin/env python3
"""Operational use of a retired path (must classify USE)."""
from pathlib import Path

DELETED = Path("aud0094-retired/tree-agentbridge/file-00.py")


def load_retired():
    return DELETED.read_text(encoding="utf-8")
'''

CI_YML = """name: retired-ci
on: [push]
jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - run: python3 aud0094-retired/tree-codex-stub/file-00.sh
"""

MANIFEST = """{
  "name": "legacy-entry",
  "entry": "aud0094-retired/tree-tools-b/file-00.mjs"
}
"""

CONSTRUCTED = '''#!/usr/bin/env python3
"""Path assembled from parts so a literal full-string search cannot see it."""
PREFIX = "aud0094-retired"
TREE = "tree-tools-a"
NAME = "file-01.py"


def retired_target():
    return "/".join([PREFIX, TREE, NAME])
'''

TEST_IMPORT = '''#!/usr/bin/env python3
"""CI collection target: importing a deleted module must error."""
import importlib

importlib.import_module("aud0094_retired_tree_harness_file_00")
'''

PYTEST_INI = """[pytest]
testpaths = surviving
"""


def ensure_fixtures() -> Path:
    SURVIVING.mkdir(parents=True, exist_ok=True)
    (SURVIVING / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    (SURVIVING / "importer.py").write_text(IMPORTER, encoding="utf-8")
    (SURVIVING / "ci.yml").write_text(CI_YML, encoding="utf-8")
    (SURVIVING / "manifest.json").write_text(MANIFEST, encoding="utf-8")
    (SURVIVING / "constructed.py").write_text(CONSTRUCTED, encoding="utf-8")
    (SURVIVING / "test_retired_import.py").write_text(TEST_IMPORT, encoding="utf-8")
    (ESTATE / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")
    # Deleted files must be absent.
    retired = ESTATE / "aud0094-retired"
    if retired.exists():
        raise RuntimeError("planted retired tree must stay deleted")
    return ESTATE
