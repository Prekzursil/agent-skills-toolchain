"""Registration surfaces the REL-0007 orphan sweep enumerates.

Every surface the catalog names appears here. Surfaces this runner cannot
honestly query are listed with status NOT-CHECKED and a reason. Omitting a
surface is an overclaim; folding NOT-CHECKED into a zero-orphan pass is too.
"""
from __future__ import annotations

PACKAGE_ID = "rel0007-canary"
DETECTOR_HOOK_ID = f"{PACKAGE_ID}.detector"
PACKAGE_HOOK_ID = f"{PACKAGE_ID}.pre-tool"
OWNER_HOOK_ID = "owner.pre-tool"
OWNER_MCP_ID = "owner-notes-mcp"
PACKAGE_MCP_ID = f"{PACKAGE_ID}-mcp"
OWNER_SETTING = "ownerTheme"
PACKAGE_SETTING = "rel0007Canary"
OWNER_SKILL = "skill.owner-notes"
PACKAGE_SKILL = f"skill.{PACKAGE_ID}"
OWNER_SHIM = "owner-tool"
PACKAGE_SHIM = PACKAGE_ID
OWNER_MIRROR = "owner-pack"
PACKAGE_MIRROR = PACKAGE_ID
OWNER_TASK = "Owner-Backup"
PACKAGE_TASK = "REL0007-Canary-Task"

# Must match the id= values emitted by sweep.query_checked.
CHECKED_SURFACE_IDS = (
    "hooks",
    "mcp",
    "settings",
    "live_skill_tree",
    "path_shim",
    "mirror",
    "scheduled_tasks_fixture",
)

# Surfaces named by the unit or adjacent OS registries that this Linux
# worktree cannot, or must not, query. Each MUST appear on the receipt.
NOT_CHECKED_SURFACES = (
    {
        "id": "windows_task_scheduler",
        "query": "schtasks /Query /FO LIST",
        "reason": "This runner is Linux; schtasks.exe is absent. Live Windows Task Scheduler is not queried.",
    },
    {
        "id": "windows_registry",
        "query": "winreg.QueryValue HKCU\\Software and App Paths",
        "reason": "No Windows registry on this Linux worktree; HKCU uninstall/App Paths keys are not queried.",
    },
    {
        "id": "live_user_settings_json",
        "query": "read ~/.claude/settings.json",
        "reason": "Wave floor forbids wholesale read of live settings.json (credentials in env). Disposable fixture profile used instead.",
    },
    {
        "id": "live_user_mcp_json",
        "query": "read ~/.mcp.json",
        "reason": "Live ~/.mcp.json may hold secrets; not opened. Fixture .mcp.json under the disposable profile is queried instead.",
    },
    {
        "id": "live_host_PATH",
        "query": "os.environ['PATH'] of this process",
        "reason": "Host PATH mixes runner tools with any real shims; the fixture path.env / bin/ is the PATH surface under test.",
    },
    {
        "id": "macos_launchd",
        "query": "launchctl list",
        "reason": "This runner is Linux, not macOS; launchd jobs are not queried.",
    },
    {
        "id": "live_systemd_user",
        "query": "systemctl --user list-units",
        "reason": "Host systemd is outside the disposable profile; observing it would mix machine state into a fixture drill.",
    },
    {
        "id": "production_packaged_uninstaller",
        "query": "python -m platform.plugin.cli uninstall --prefix <p> --retain-user-data",
        "reason": "platform/plugin/cli.py uninstall exists but removes a --prefix version tree and provenance-tracked live files. It does not register or deregister the catalog-named Claude surfaces (hooks.json, .mcp.json, settings keys, skill tree, PATH shim, mirror). Live-host uninstall is out of scope. This receipt does not claim production uninstall is clean of those surfaces.",
    },
)

# Input, not a registration surface. Sweep queries it when the file exists.
INPUT_SURFACES = (
    {
        "id": "rel0002_typed_inverses_on_disk",
        "query": "read command-center/receipts/REL-0002.json; require INV-PATH and INV-PREDATE",
        "reason": "REL-0002 receipt is absent from this worktree. Inverses are encoded locally from the catalog action inventory and the two hard invariants (never delete a path the installer did not create; never remove a pre-dated command, skill or setting).",
    },
)

REQUIRED_IDS = (
    tuple(CHECKED_SURFACE_IDS)
    + tuple(s["id"] for s in INPUT_SURFACES)
    + tuple(s["id"] for s in NOT_CHECKED_SURFACES)
)
