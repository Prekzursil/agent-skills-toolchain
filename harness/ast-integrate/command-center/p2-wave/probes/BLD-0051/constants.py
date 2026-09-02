"""BLD-0051 shared constants. The canary is synthetic, not a credential."""
from __future__ import annotations

UNIT_ID = "BLD-0051"
SENTINEL = "SUCCESS:BLD-0051"
OUT_REL = "command-center/receipts/BLD-0051.json"
SCHEMA_REL = "command-center/schema/secret-egress-map.schema.json"
REDACTOR_REL = "tools/command-center/secret_redact.py"
CANARY = "BLD0051_SYNTHETIC_CANARY_NOT_A_CREDENTIAL_9f3c2a1b7e44"
CANARY_ID = "BLD0051-CANARY-A"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0051/probe1_scratch_redaction.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0051/probe2_live_reviewer.py"
)
ENV_NAMES = (
    "CURSOR_API_KEY",
    "CURSOR_API_TOKEN",
    "CURSOR_API_KEY",
    "CURSOR_API_TOKEN",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
    "CODEX_AUTH_JSON",
    "CODEX_RUNNER_PAT",
)
FILE_CANDIDATES = (
    "tools/mcp/cloud-hub/accounts.json",
    "tools/mcp/search-hub/accounts.json",
    "auth.json",
    ".credentials.json",
    "mcp.json",
    ".cursor/mcp.json",
)
