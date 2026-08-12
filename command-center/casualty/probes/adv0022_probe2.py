#!/usr/bin/env python3
"""ADV-0022 Probe 2: static audit of the enforcement point.

Determines whether a component's declared tool_permissions are enforced at CALL
TIME or merely recorded in metadata. Pure filesystem/regex scan (no ripgrep
dependency) so the result is deterministic and reproducible.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")


def scan(dirs, pattern):
    rx = re.compile(pattern)
    hits = []
    for d in dirs:
        root = REPO / d
        if not root.exists():
            continue
        for dp, _, fns in os.walk(root):
            for fn in fns:
                if not fn.endswith((".py", ".json", ".md")):
                    continue
                p = Path(dp) / fn
                try:
                    txt = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for i, line in enumerate(txt.splitlines(), 1):
                    if rx.search(line):
                        rel = p.relative_to(REPO).as_posix()
                        hits.append(f"{rel}:{i}:{line.strip()[:100]}")
    return sorted(hits)


checks = {}

# C1: runtime/PreToolUse consumers of the work-unit authorization function.
checks["runtime_consumers_in_hooks"] = scan(
    ["hooks"], r"check_work_unit_authorization")

# C2: any file under hooks/ that references a component's tool_permissions at all.
checks["hooks_reference_tool_permissions"] = scan(
    ["hooks"], r"tool_permissions")

# C3: ALL callers of the enforcement function repo-wide (to classify static vs runtime).
checks["all_callers_repo_wide"] = [
    h for h in scan(
        ["platform", "command-center", "tools", "hooks"],
        r"check_work_unit_authorization\(")
    if "def check_work_unit_authorization" not in h
]

# C4: do the two REAL runtime PreToolUse gates read a component manifest?
checks["file_scope_reads_manifest"] = scan(
    ["hooks/file-scope"], r"tool_permissions|SKILL\.md|work_unit|catalog|manifest")
checks["deny_cred_reads_manifest"] = scan(
    ["hooks/deny-credential-reads"], r"tool_permissions|SKILL\.md|work_unit|catalog|manifest")

# C5: does skill-router / semantic-router read tool_permissions to gate a skill?
checks["skill_router_reads_tool_permissions"] = scan(
    ["hooks/skill-router", "hooks/semantic-router"], r"tool_permissions")

# ---- both-states DETECTOR CONTROL for THIS static scanner --------------------
# Known-GOOD: the scanner MUST find the static CI callers (proves it can find a
# real caller when one exists). Known-BAD direction is the runtime-hooks scan
# above returning empty. If the scanner found nothing anywhere, it is broken.
control_known_present = scan(
    ["platform/lib/wfdsl"], r"check_work_unit_authorization")
checks["_control_scanner_finds_known_present_callers"] = control_known_present

summary = {
    "runtime_consumers_in_hooks_COUNT": len(checks["runtime_consumers_in_hooks"]),
    "hooks_reference_tool_permissions_COUNT": len(checks["hooks_reference_tool_permissions"]),
    "all_callers_repo_wide_COUNT": len(checks["all_callers_repo_wide"]),
    "file_scope_reads_manifest_COUNT": len(checks["file_scope_reads_manifest"]),
    "deny_cred_reads_manifest_COUNT": len(checks["deny_cred_reads_manifest"]),
    "skill_router_reads_tool_permissions_COUNT": len(checks["skill_router_reads_tool_permissions"]),
    "scanner_control_found_known_present_COUNT": len(control_known_present),
    "scanner_discriminates": len(control_known_present) > 0
    and len(checks["runtime_consumers_in_hooks"]) == 0,
}

out = {"checks": checks, "summary": summary}
blob = json.dumps(out, indent=2, sort_keys=True)
print("ADV0022_P2_BEGIN")
print(blob)
print("ADV0022_P2_END")
print("P2_FINGERPRINT_MD5=" + hashlib.md5(blob.encode("utf-8")).hexdigest())
