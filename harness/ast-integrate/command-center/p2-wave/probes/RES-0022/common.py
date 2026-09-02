"""Shared paths and hashing for RES-0022."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURE_DIR = HERE / "captures"
INDEX_PATH = CAPTURE_DIR / "index.json"
PLUGIN_JSON = REPO / ".claude-plugin" / "plugin.json"
OUT_REL = "command-center/research/RES-0022.json"
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0022/probe1_blind_reproduce.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0022/probe2_false_alarm.py"
)
MEASURE = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0022/measure.py"
)
INDEX_PATH = INDEX_PATH
MEASURE = MEASURE

DOC_URLS = {
    "plugins-reference": "https://code.claude.com/docs/en/plugins-reference.md",
    "plugins": "https://code.claude.com/docs/en/plugins.md",
    "plugin-marketplaces": "https://code.claude.com/docs/en/plugin-marketplaces.md",
    "hooks": "https://code.claude.com/docs/en/hooks.md",
    "skills": "https://code.claude.com/docs/en/skills.md",
    "settings": "https://code.claude.com/docs/en/settings.md",
    "settings-reference": "https://code.claude.com/docs/en/settings-reference.md",
    "cli": "https://code.claude.com/docs/en/cli.md",
    "headless": "https://code.claude.com/docs/en/headless.md",
    "sub-agents": "https://code.claude.com/docs/en/sub-agents.md",
    "mcp": "https://code.claude.com/docs/en/mcp.md",
}

OLD_DOCS_URL = "https://docs.claude.com/en/docs/claude-code/hooks"

DOCUMENTED_PLUGIN_FIELDS = frozenset(
    {
        "name",
        "description",
        "version",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "$schema",
        "metadata",
        "commands",
        "agents",
        "skills",
        "hooks",
        "mcpServers",
        "outputStyles",
        "lspServers",
        "userConfig",
        "channels",
        "dependencies",
        "experimental",
        "defaultEnabled",
    }
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def load_index() -> dict:
    if not INDEX_PATH.is_file():
        return {}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def capture_body(doc_id: str) -> tuple[str, str, str]:
    """Return (url, sha256, text). Empty text if missing."""
    idx = load_index().get("docs") or {}
    rec = idx.get(doc_id) or {}
    path = CAPTURE_DIR / f"{doc_id}.body"
    url = str(rec.get("url") or DOC_URLS.get(doc_id) or "")
    if path.is_file():
        raw = path.read_bytes()
        return url, sha256_bytes(raw), raw.decode("utf-8", errors="replace")
    return url, "", ""


capture_body = capture_body
