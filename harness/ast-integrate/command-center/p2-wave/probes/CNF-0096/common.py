"""Shared constants for CNF-0096 clean-install Windows hook-load proof."""
from __future__ import annotations

UNIT_ID = "CNF-0096"
OUTPUT_REL = "command-center/confirmation/CNF-0096-clean-install-windows.json"
SCHEMA_REL = "command-center/schema/install-report.schema.json"
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0096 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every declared hook has "
    "an observed side effect or an explicit not-observed entry, and the "
    "removal control was detected. Any other terminal state is "
    "FAILED:CNF-0096 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "After a clean install on a fresh Windows profile, do the hooks actually "
    "LOAD? Prove it at process level - a hook must be observed executing and "
    "writing its side effect - rather than by reading the manifest. Question: "
    "which declared hooks never fire, and does the client report a healthy "
    "install while loading none of them?"
)
MARKER = "CNF-0096-SIDE-EFFECT"
POISON_KEY = "$schema"
REMOVED_HOOK_ID = "hook.post-tool"
PROFILE_USER = "CNF0096Fresh"
DECLARED_HOOKS = (
    {
        "id": "hook.pre-tool",
        "event": "PreToolUse",
        "script": "hooks/pre-tool.py",
        "descriptor": "hooks/hook.pre-tool.json",
    },
    {
        "id": "hook.post-tool",
        "event": "PostToolUse",
        "script": "hooks/post-tool.py",
        "descriptor": "hooks/hook.post-tool.json",
    },
    {
        "id": "hook.session-start",
        "event": "SessionStart",
        "script": "hooks/session-start.py",
        "descriptor": "hooks/hook.session-start.json",
    },
)
