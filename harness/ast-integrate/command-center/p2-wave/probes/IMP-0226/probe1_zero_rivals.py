"""Probe 1: AST sweep — seven fan-in sites call judge; zero local predicates.

Mechanically: import-graph resolution of agentspec.oracle.judge at every
FANIN_ROLE module, plus a live both-states call through consider() that
must match judge() and must reject exit-zero-with-missing-artifact.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.fanin import CONSIDER_FNS, EXPECTED_ROLES  # noqa: E402
from agentspec.oracle import digest_bytes, judge  # noqa: E402
from agentspec.rival_scan import scan_tree  # noqa: E402

SCAN_ROOT = REPO / "tools" / "agentspec"
UNIT = "IMP-0226"


def _write_receipt(root: Path, *, good: bool) -> Path:
    art = root / "artifacts" / "U1.json"
    art.parent.mkdir(parents=True, exist_ok=True)
    payload = b'{"unit_id":"U1","ok":true}\n'
    if good:
        art.write_bytes(payload)
        sha = digest_bytes(payload)
        rel = "artifacts/U1.json"
    else:
        sha = digest_bytes(payload)
        rel = "artifacts/missing.json"
    receipt = {
        "unit_id": "U1",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:U1",
        "exit_code": 0,
        "artifacts": [{"path": rel, "sha256": sha}],
    }
    path = root / "receipts" / "U1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    scan = scan_tree(SCAN_ROOT)
    sites = [s for s in scan["call_sites"] if s["role"] in EXPECTED_ROLES]
    roles = {s["role"] for s in sites}
    alias = next((s for s in sites if s["role"] == "cloud-dispatcher"), None)
    relative = next((s for s in sites if s["role"] == "harvester"), None)
    attr = next((s for s in sites if s["role"] == "monitor"), None)
    parent = next((s for s in sites if s["role"] == "workflow-fan-in"), None)

    with tempfile.TemporaryDirectory(prefix="imp0226-p1-") as tmp:
        root = Path(tmp)
        good_path = _write_receipt(root, good=True)
        bad_root = root / "bad"
        bad_path = _write_receipt(bad_root, good=False)
        good_v = judge(good_path, root=root)
        bad_v = judge(bad_path, root=bad_root)
        live = []
        for fn in CONSIDER_FNS:
            g = fn(good_path, root=root)
            b = fn(bad_path, root=bad_root)
            live.append(
                {
                    "fn": getattr(fn, "__module__", "?"),
                    "good_ok": bool(g.ok),
                    "bad_ok": bool(b.ok),
                    "matches_judge_good": bool(g.ok) == bool(good_v.ok),
                    "matches_judge_bad": bool(b.ok) == bool(bad_v.ok),
                    "bad_reason": b.reason,
                }
            )

    mention_as_site = any("completion_notes" in s["path"] for s in sites)
    checks = [
        ("method_is_ast", scan.get("method") == "ast-import-graph"),
        ("used_grep_false", scan.get("used_grep") is False),
        ("canonical_present", scan.get("canonical_present") is True),
        ("seven_fan_in_sites", len(sites) == 7),
        ("roles_complete", roles == EXPECTED_ROLES),
        ("every_site_imports_judge", all(s["imports_shared_judge"] for s in sites)),
        (
            "every_site_resolves_module",
            all(s["resolved_module"] == "agentspec.oracle" for s in sites),
        ),
        ("every_site_has_call", all(s["call_linenos"] for s in sites)),
        ("missing_imports_empty", not scan["missing_imports"]),
        ("zero_rivals", scan["zero_duplicates"] is True),
        ("mention_only_not_a_call_site", not mention_as_site),
        (
            "mention_listed_as_prose",
            any("completion_notes" in p for p in scan.get("mention_only_files", [])),
        ),
        ("alias_bound_name_is_rc", bool(alias and alias["bound_name"] == "rc")),
        (
            "relative_import_kind",
            bool(relative and relative["import_kind"] == "from-import"),
        ),
        (
            "relative_import_level_resolved",
            bool(relative and relative["resolved_module"] == "agentspec.oracle"),
        ),
        ("module_attribute_call", bool(attr and attr["import_kind"] == "import")),
        ("from_parent_import", bool(parent and parent["import_kind"] == "from-parent")),
        ("graph_has_edges", len(scan["import_graph_edges"]) >= 7),
        ("judge_accepts_good", good_v.ok is True),
        ("judge_rejects_exit0_missing", bad_v.ok is False),
        ("seven_consider_fns", len(CONSIDER_FNS) == 7),
        ("all_consider_match_good", all(row["matches_judge_good"] for row in live)),
        ("all_consider_match_bad", all(row["matches_judge_bad"] for row in live)),
        ("all_consider_reject_bad", all(row["bad_ok"] is False for row in live)),
    ]
    payload = {
        "probe": "probe1-zero-rivals",
        "unit_id": UNIT,
        "method": scan.get("method"),
        "fan_in_count": len(sites),
        "roles": sorted(roles),
        "second_implementations": scan.get("second_implementations"),
        "mention_only_files": scan.get("mention_only_files"),
        "live_consider": live,
        "good_reason": good_v.reason,
        "bad_reason": bad_v.reason,
        "checks": {name: bool(ok) for name, ok in checks},
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:{UNIT}-probe1 {name}")
            return 1
    print("SUCCESS:IMP-0226-probe1 zero rivals; seven fan-in sites call judge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
