"""IMP-0116 tests: scaffolds lint clean on first generation + pass conformance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from marketplace.scaffolder import KINDS, scaffold  # noqa: E402
from marketplace.name_linter import lint_candidate  # noqa: E402
from marketplace.conformance import check_conformance  # noqa: E402

NAMES = {
    "skill": "quill-narrate-demo",
    "hook": "quill-trigger-demo",
    "plugin": "quill-bundle-demo",
    "command": "quill-command-demo",
}


def _lint_generated(kind: str, root: Path) -> list:
    findings = []
    manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
    # structural manifest contract
    for key in ("id", "name", "kind", "version", "license"):
        assert manifest.get(key), (kind, key)
    assert manifest["kind"] == kind
    assert manifest["id"] == manifest["name"]
    # name linter: zero confusion flags against the installed skill set
    installed = []
    for base in (REPO / ".claude" / "skills", REPO / ".agents" / "skills"):
        if base.is_dir():
            installed += sorted(d.name for d in base.iterdir() if d.is_dir())
    findings += lint_candidate(manifest["name"], installed)
    # per-kind required file
    required = {
        "skill": root / "SKILL.md",
        "hook": root / "hooks.json",
        "plugin": root / "plugin.json",
        "command": root / "command.md",
    }[kind]
    assert required.is_file(), required
    if kind == "hook":
        json.loads((root / "hooks.json").read_text(encoding="utf-8"))
    # SPDX-known license
    assert manifest["license"] in {"MIT", "Apache-2.0", "BSD-3-Clause"}
    return findings


def test_each_scaffold_type_generates_and_lints_zero_findings(tmp_path: Path) -> None:
    for kind in KINDS:
        root = scaffold(kind, NAMES[kind], tmp_path)
        findings = _lint_generated(kind, root)
        assert findings == [], (kind, findings)


def test_generated_artifact_passes_conformance(tmp_path: Path) -> None:
    for kind in KINDS:
        root = scaffold(kind, NAMES[kind], tmp_path)
        report = check_conformance(root)
        assert report.ok, [(v.check, v.detail) for v in report.violations]


def test_negative_control_broken_template_goes_red(tmp_path: Path) -> None:
    from marketplace import scaffolder as S

    original_readme = S._README
    S._README = "# {name}\n"  # drops the Usage section conformance requires
    try:
        root = scaffold("skill", "quill-broken-demo", tmp_path)
        report = check_conformance(root)
        assert not report.ok, "broken template unexpectedly passed conformance"
        assert any(v.check == "readme-usage" for v in report.violations)
    finally:
        S._README = original_readme
    # and the restored template heals it
    root2 = scaffold("skill", "quill-healed-demo", tmp_path)
    assert check_conformance(root2).ok
