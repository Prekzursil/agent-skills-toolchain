"""AUD-0079 constants. Names and lengths only — never secret bodies."""
from __future__ import annotations

UNIT_ID = "AUD-0079"
OUT_REL = "command-center/audit/AUD-0079-credential-consumer-audit.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
QUESTION = (
    "For every environment variable or credential file the codebase reads, "
    "does the consumer validate presence at startup and fail loudly, or does "
    "it silently degrade to a wrong-but-quiet behaviour?"
)
SENTINEL = (
    "SUCCESS:AUD-0079 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0079/probe1_static_enum.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0079/probe2_unset_and_wrong.py"
)

# Syntactically valid but wrong. Not a live credential.
WRONG_TOKEN = "sk-aud0079-syntactically-valid-wrong-token-aa11"
LOUD_TOKEN_NAME = "AUD0079_PROBE_TOKEN"
FILE_ENV_NAME = "AUD0079_CREDENTIAL_FILE"
EXPECTED_FIXTURE_TOKEN = "aud0079-ok-token-not-a-secret"

CREDENTIAL_NAME_MARKERS = (
    "API_KEY",
    "APIKEY",
    "ACCESS_TOKEN",
    "AUTH_TOKEN",
    "CLIENT_SECRET",
    "CLIENT_TOKEN",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "SECRET",
    "CREDENTIAL",
    "_TOKEN",
)
NOT_CREDENTIAL_NAMES = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "SHELL",
        "PWD",
        "OLDPWD",
        "TMPDIR",
        "TEMP",
        "TMP",
        "TZ",
        "HOSTNAME",
        "LOGNAME",
        "DISPLAY",
        "EDITOR",
        "VISUAL",
        "PATHEXT",
        "COMSPEC",
        "SYSTEMROOT",
        "WINDIR",
        "PROGRAMFILES",
        "CURSOR_AGENT_BIN",
        "MARKETPLACE_RELEASE_MODE",
        "BLD0024_DATA_DIR",
        "BLD0024_USE_NTPATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONPATH",
        "PYTHONIOENCODING",
        "PYTHONUNBUFFERED",
        "PYTHONHASHSEED",
        "INNER",
        "GITHUB_ACTIONS",
        "CI",
        "NODE_ENV",
        "VIRTUAL_ENV",
        "SHLVL",
        "PS1",
        "MAIL",
        "XDG_RUNTIME_DIR",
        "XDG_CONFIG_HOME",
        "SSH_AUTH_SOCK",
        "SSH_CONNECTION",
        "UNSAFE_TOKEN",
        "POISON_TOKEN",
        "STATUS_TOKENS",
        "CANARY",
        "PLANT_BODY",
    }
)
SKIP_DIR_PARTS = frozenset(
    {
        "__pycache__",
        ".git",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)
SCAN_ROOTS = (
    "tools",
    "command-center",
    "release",
)
SKIP_PROBE_PREFIX = "command-center/p2-wave/probes/"
KEEP_PROBE_PREFIX = "command-center/p2-wave/probes/AUD-0079/"
LIVE_ENTRYPOINTS = (
    {
        "id": "dispatch-cursor",
        "rel": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
        "vars": ["CURSOR_API_KEY"],
        "kind": "env",
        "needle": 'if not os.environ.get("CURSOR_API_KEY"):',
    },
    {
        "id": "bringup-cursor-fleet",
        "rel": "command-center/p2-wave/seed-stage/bringup_cursor_fleet.py",
        "vars": ["CURSOR_API_TOKEN", "CURSOR_API_KEY"],
        "kind": "env",
        "needle": "if not token:",
    },
)

# Aliases used by enumerator / executor / probes.
UNIT_ID = UNIT_ID
OUT_REL = OUT_REL
SCHEMA_REL = SCHEMA_REL
FILE_ENV_NAME = FILE_ENV_NAME
CREDENTIAL_NAME_MARKERS = CREDENTIAL_NAME_MARKERS
NOT_CREDENTIAL_NAMES = NOT_CREDENTIAL_NAMES
SKIP_DIR_PARTS = SKIP_DIR_PARTS
SKIP_PROBE_PREFIX = SKIP_PROBE_PREFIX
KEEP_PROBE_PREFIX = KEEP_PROBE_PREFIX
SCAN_ROOTS = SCAN_ROOTS
LIVE_ENTRYPOINTS = LIVE_ENTRYPOINTS
P1 = P1
P2 = P2
