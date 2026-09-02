"""47 seeded regression failure classes.

Catalog TST-0295.inputs cites _USER-PROMPTS.md:11298-11347. That file is not
on this worktree. Names below are reconstructed from
command-center/p2-wave/probes/ARC-0005/seeded_classes.py (spec lines
11301-11347). SOURCE_STATUS is ABSENT — do not certify this list against
the original prompt file.
"""
from __future__ import annotations

SOURCE_STATUS = "ABSENT"
SOURCE_CITATION = (
    "command-center/WORK-UNIT-CATALOG.json TST-0295.inputs cites "
    "_USER-PROMPTS.md:11298-11347; that file is not on this worktree"
)

CLASSES: list[dict] = [
    {"spec": 11301, "id": "FC-11301", "name": "dual-writable config trees (live tree and repo tree both treated as source)", "stratum": "medium"},
    {"spec": 11302, "id": "FC-11302", "name": "strict parser rejects unknown fields", "stratum": "easy"},
    {"spec": 11303, "id": "FC-11303", "name": "plugin appears installed but hooks are unloaded", "stratum": "medium"},
    {"spec": 11304, "id": "FC-11304", "name": "bare .sh invocation on Windows", "stratum": "easy"},
    {"spec": 11305, "id": "FC-11305", "name": "repository copy differs from live deployed copy", "stratum": "medium"},
    {"spec": 11306, "id": "FC-11306", "name": "stale cache masks a fixed package", "stratum": "medium"},
    {"spec": 11307, "id": "FC-11307", "name": "package accidentally includes .git or huge unrelated files", "stratum": "easy"},
    {"spec": 11308, "id": "FC-11308", "name": "path-casing mismatch across filesystems", "stratum": "easy"},
    {"spec": 11309, "id": "FC-11309", "name": "PowerShell/Git Bash path rewriting", "stratum": "easy"},
    {"spec": 11310, "id": "FC-11310", "name": "case-insensitive parser collision", "stratum": "medium"},
    {"spec": 11311, "id": "FC-11311", "name": "command-line length overflow", "stratum": "easy"},
    {"spec": 11312, "id": "FC-11312", "name": "exit-zero with missing artifact", "stratum": "medium"},
    {"spec": 11313, "id": "FC-11313", "name": "partial artifact without sentinel", "stratum": "medium"},
    {"spec": 11314, "id": "FC-11314", "name": "two completion predicates disagree", "stratum": "hard"},
    {"spec": 11315, "id": "FC-11315", "name": "stall detection from mtimes alone is impossible / orchestrator death", "stratum": "hard"},
    {"spec": 11316, "id": "FC-11316", "name": "long-path / mtime stall coupling", "stratum": "medium"},
    {"spec": 11317, "id": "FC-11317", "name": "one hung unit blocks a large batch", "stratum": "medium"},
    {"spec": 11318, "id": "FC-11318", "name": "429 arrival-rate storm / self-throttling", "stratum": "medium"},
    {"spec": 11319, "id": "FC-11319", "name": "remote harvest silently does nothing", "stratum": "medium"},
    {"spec": 11320, "id": "FC-11320", "name": "permission-boundary / colliding catalog merge", "stratum": "hard"},
    {"spec": 11321, "id": "FC-11321", "name": "worktree points to the wrong repository", "stratum": "easy"},
    {"spec": 11322, "id": "FC-11322", "name": "stale branch would revert newer work", "stratum": "medium"},
    {"spec": 11323, "id": "FC-11323", "name": "false-positive prose and fixture detectors", "stratum": "hard"},
    {"spec": 11324, "id": "FC-11324", "name": "detector silent in both broken and fixed states", "stratum": "hard"},
    {"spec": 11325, "id": "FC-11325", "name": "mutation survives the test suite", "stratum": "hard"},
    {"spec": 11326, "id": "FC-11326", "name": "eager per-session MCP process multiplication", "stratum": "medium"},
    {"spec": 11327, "id": "FC-11327", "name": "commit exhaustion freezes process creation", "stratum": "medium"},
    {"spec": 11328, "id": "FC-11328", "name": "kill-based memory guard terminates a live shared service", "stratum": "hard"},
    {"spec": 11329, "id": "FC-11329", "name": "skill exists in repo but not in live skill directory", "stratum": "medium"},
    {"spec": 11330, "id": "FC-11330", "name": "router fails to select an installed skill", "stratum": "medium"},
    {"spec": 11331, "id": "FC-11331", "name": "ignoring an existing superior workflow", "stratum": "medium"},
    {"spec": 11332, "id": "FC-11332", "name": "workflow fusion loses a source capability", "stratum": "hard"},
    {"spec": 11333, "id": "FC-11333", "name": "fused workflow performs worse than every source", "stratum": "hard"},
    {"spec": 11334, "id": "FC-11334", "name": "fusion accepted because it has more stages", "stratum": "hard"},
    {"spec": 11335, "id": "FC-11335", "name": "council/self-improvement loop class", "stratum": "hard"},
    {"spec": 11336, "id": "FC-11336", "name": "trigger mandated, threshold unspecified", "stratum": "medium"},
    {"spec": 11337, "id": "FC-11337", "name": "council deliberation under-specified stop", "stratum": "medium"},
    {"spec": 11338, "id": "FC-11338", "name": "council stops before minimum deliberation conditions", "stratum": "medium"},
    {"spec": 11339, "id": "FC-11339", "name": "100-idea brainstorm satisfies the count with trivial wording variants", "stratum": "hard"},
    {"spec": 11340, "id": "FC-11340", "name": "dissent/minority report is dropped", "stratum": "hard"},
    {"spec": 11341, "id": "FC-11341", "name": "minority report unattributed in final synthesis", "stratum": "hard"},
    {"spec": 11342, "id": "FC-11342", "name": "corruption threshold unspecified", "stratum": "medium"},
    {"spec": 11343, "id": "FC-11343", "name": "nested councils disagree on completion", "stratum": "hard"},
    {"spec": 11344, "id": "FC-11344", "name": "transcript injects instructions into later stages", "stratum": "hard"},
    {"spec": 11345, "id": "FC-11345", "name": "credentials or decrypted secrets enter an artifact bundle", "stratum": "medium"},
    {"spec": 11346, "id": "FC-11346", "name": "marketplace package has malicious or excessive permissions", "stratum": "medium"},
    {"spec": 11347, "id": "FC-11347", "name": "rollback destroys user-owned files/commands/settings", "stratum": "hard"},
]


def assert_complete() -> None:
    specs = [c["spec"] for c in CLASSES]
    if specs != list(range(11301, 11348)):
        raise SystemExit(f"seeded class specs incomplete n={len(specs)}")
    ids = [c["id"] for c in CLASSES]
    if len(set(ids)) != 47:
        raise SystemExit("seeded class ids not unique")
