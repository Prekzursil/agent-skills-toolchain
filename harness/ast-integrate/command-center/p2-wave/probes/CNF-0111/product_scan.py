"""Static scan: is there a product call-time enforcer, or only metadata?"""
from __future__ import annotations

from pathlib import Path

# IMP-0059 interceptor. Catalog tests_required names this path. Absent here.
CALL_TIME_INTERCEPTOR = "tools/plugin/permission_enforcement.py"

# Adjacent files that are NOT a plugin call-time interceptor for declared
# tool permissions (filesystem write / spawn / network / credential-read).
ADJACENT = (
    (
        "tools/plugin/tests/test_permission_enforcement.py",
        "interceptor-test",
    ),
    (
        "platform/marketplace/mkt/permissions.py",
        "linter-installer-subsumption",
    ),
    (
        "tools/marketplace/schema/permissions.schema.json",
        "schema-metadata",
    ),
    (
        ".claude-plugin/plugin.schema.json",
        "schema-metadata",
    ),
    (
        "tools/lib/workspace.mjs",
        "workspace-root-helper",
    ),
    (
        "tools/lib/net-allowlist.mjs",
        "loopback-allowlist",
    ),
)

HIT_NEEDLES = (
    "PermissionDenied",
    "check_permission",
    "enforce_permissions",
    "allowedTools",
    "disallowedTools",
)


def scan(repo: Path) -> dict:
    rows = [
        {
            "path": CALL_TIME_INTERCEPTOR,
            "present": (repo / CALL_TIME_INTERCEPTOR).is_file(),
            "kind": "call-time-interceptor",
        }
    ]
    for rel, kind in ADJACENT:
        rows.append(
            {"path": rel, "present": (repo / rel).is_file(), "kind": kind}
        )
    hits: list[dict] = []
    search_roots = [
        repo / "tools",
        repo / "command-center" / "p2-wave" / "seed-stage",
    ]
    skip = {
        "WORK-UNIT-CATALOG.json",
        "CNF-0111",
    }
    for root in search_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".mjs", ".js", ".ts"}:
                continue
            if "CNF-0111" in path.parts:
                continue
            if path.name in skip:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            found = [n for n in HIT_NEEDLES if n in text]
            if found:
                rel = path.relative_to(repo).as_posix()
                hits.append({"path": rel, "needles": found})
    call_time = any(
        r["present"] and r["kind"] == "call-time-interceptor" for r in rows
    )
    return {
        "enforcement_module_present": call_time,
        "paths_probed": rows,
        "static_hits": hits,
        "call_time_enforcer_found": call_time,
        "metadata_only": not call_time,
        "method": (
            "Path existence for IMP-0059 interceptor "
            f"({CALL_TIME_INTERCEPTOR}); adjacent schema/linter/allowlist "
            "files are recorded but are not call-time enforcement. Needle "
            "scan of tools/ and seed-stage. CNF-0111 probe sources excluded."
        ),
    }
