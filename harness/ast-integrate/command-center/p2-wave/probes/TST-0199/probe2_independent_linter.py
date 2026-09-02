#!/usr/bin/env python3
"""Probe 2: independent byte-linter over the same file set.

Signal (b): portability_linter must name the same 40 members the publisher
rejects, stay silent on the portable set, and not import filename_gate.
A reserved-device-name-only stub must stay silent on this corpus (negative
control) so a vacuous detector cannot green the unit.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
MARKET = TOOLS / "marketplace"
LINTER = TOOLS / "plugin" / "portability_linter.py"
GATE = MARKET / "filename_gate.py"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(MARKET) not in sys.path:
    sys.path.insert(0, str(MARKET))

from filename_gate import load_corpus  # noqa: E402
from plugin.portability_linter import lint_names, reserved_device_stub  # noqa: E402
from publishing import pack  # noqa: E402

PR_ONLY_CFG = MARKET / "fixtures" / "release-mode.pr-only.json"


def _imports_filename_gate(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "filename_gate" in alias.name:
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "filename_gate" in mod:
                return True
            for alias in node.names:
                if "filename_gate" in alias.name:
                    return True
    return False


def main() -> int:
    fail: list[str] = []
    src = LINTER.read_text(encoding="utf-8")
    if _imports_filename_gate(src):
        fail.append("linter-imports-publisher")
    if not GATE.is_file():
        fail.append("publisher-missing")

    doc = load_corpus()
    portable = [str(x) for x in doc["portable"]]
    unportable = [str(r["name"]) for r in doc["unportable"]]
    expected_rule = {str(r["name"]): str(r["rule"]) for r in doc["unportable"]}

    lint_bad = lint_names(unportable)
    lint_good = lint_names(portable)
    if not lint_bad.get("rejected"):
        fail.append("linter-silent-on-corpus")
    if lint_good.get("rejected"):
        fail.append("linter-fired-on-portable")

    lint_named = set(lint_bad.get("rejected_names") or [])
    missing_lint = [n for n in unportable if n not in lint_named]
    if missing_lint:
        fail.append(f"linter-unnamed:{len(missing_lint)}")

    packed = pack({"files": unportable}, config_path=str(PR_ONLY_CFG))
    pub_named = {str(r.get("name")) for r in (packed.get("rejections") or [])}
    only_pub = sorted(pub_named - lint_named)
    only_lint = sorted(lint_named - pub_named)
    if only_pub or only_lint:
        fail.append(f"disagreement:pub_only={only_pub[:4]} lint_only={only_lint[:4]}")

    by_name: dict[str, set[str]] = {}
    for row in lint_bad.get("findings") or []:
        by_name.setdefault(str(row.get("name")), set()).add(str(row.get("rule")))
    rule_miss = [
        n for n, rule in expected_rule.items() if rule not in by_name.get(n, set())
    ]
    if rule_miss:
        fail.append(f"linter-rule-miss:{len(rule_miss)}")

    stub = reserved_device_stub(unportable)
    if stub:
        fail.append(f"reserved-stub-false-positive:{stub[:4]}")

    report = {
        "probe": "probe2-independent-linter",
        "unit_id": "TST-0199",
        "pass": not fail,
        "fail": fail,
        "linter_engine": lint_bad.get("engine"),
        "independent_of": lint_bad.get("independent_of"),
        "corpus_size": len(unportable),
        "linter_named": len(lint_named),
        "publisher_named": len(pub_named),
        "agreement": not only_pub and not only_lint and not missing_lint,
        "portable_silent": not lint_good.get("rejected"),
        "reserved_stub_hits": stub,
        "reviewer_nfc_not_required": True,
        "windows_second_shell": "NOT-CHECKED",
        "windows_second_shell_note": (
            "Name-level rules are host-independent; this Linux worktree has "
            "no second Windows shell (pwsh7 / Git Bash). Divergence across "
            "those shells is residual, not a pass."
        ),
    }
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    if fail:
        print(f"FAILED:TST-0199-probe2 {fail}")
        return 1
    print(
        "SUCCESS:TST-0199-probe2 independent byte-linter agrees with "
        "publisher; reserved-name stub silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
