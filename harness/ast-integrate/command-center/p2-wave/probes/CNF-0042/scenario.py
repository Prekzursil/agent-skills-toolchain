"""Disposable user-data fixture for CNF-0042.

Layout under a work root:

  profile/plugin/   version-owned projection (currently at N)
  profile/user/     user-owned files, custom commands, settings
  n1-backup/        N-1 bytes for version-owned paths only
  manifest.json     owned-path lists

The name-collision case is the same basename (status.md) in both the
shipped plugin commands tree and the user commands tree. Set-difference
rollback mutates only plugin/; wholesale snapshot restore wipes user/.
"""
from __future__ import annotations

import json
from pathlib import Path

PLUGIN = "plugin"
USER = "user"
N1_BACKUP = "n1-backup"

# Version-owned relative to plugin/
OWNED_N1 = (
    "plugin.json",
    "commands/help.md",
    "commands/status.md",
    "skills/core.md",
)
N_ONLY_REL = "commands/shipped-n-only.md"
OWNED_N = OWNED_N1 + (N_ONLY_REL,)

COLLISION_BASENAME = "status.md"
COLLISION_USER_REL = f"{USER}/commands/{COLLISION_BASENAME}"
COLLISION_SHIPPED_REL = f"{PLUGIN}/commands/{COLLISION_BASENAME}"

# Seeded items the user owned before the change. Rollback must keep
# each one present and byte-identical.
USER_ITEMS: tuple[tuple[str, bytes, str], ...] = (
    (
        f"{USER}/files/journal.md",
        b"CNF-0042 user journal\nkeep-me\n",
        "user-file",
    ),
    (
        f"{USER}/commands/my-custom.md",
        b"---\nname: my-custom\n---\nuser-authored custom command\n",
        "custom-command",
    ),
    (
        COLLISION_USER_REL,
        b"---\nname: status\n---\nUSER overlay status command (name collision)\n",
        "name-collision-custom-command",
    ),
    (
        f"{USER}/settings/settings.json",
        b'{"theme":"dark","owner":"cnf-0042-seed"}\n',
        "personal-settings",
    ),
)

N1_PLUGIN_BYTES: dict[str, bytes] = {
    "plugin.json": b'{"id":"demo-plugin","version":"N-1"}\n',
    "commands/help.md": b"# help (unchanged across versions)\n",
    "commands/status.md": b"# shipped status command N-1\n",
    "skills/core.md": b"# skill core N-1\n",
}

N_PLUGIN_BYTES: dict[str, bytes] = {
    "plugin.json": b'{"id":"demo-plugin","version":"N"}\n',
    "commands/help.md": b"# help (unchanged across versions)\n",
    "commands/status.md": b"# shipped status command N (upgraded)\n",
    "commands/shipped-n-only.md": b"# introduced in N; rollback MUST remove\n",
    "skills/core.md": b"# skill core N\n",
}


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build_work(work: Path) -> dict:
    """Populate a disposable work root. Returns the manifest dict."""
    work.mkdir(parents=True, exist_ok=True)
    profile = work / "profile"
    n1 = work / N1_BACKUP
    for rel, data in N_PLUGIN_BYTES.items():
        write_file(profile / PLUGIN / rel, data)
    for rel, data, _role in USER_ITEMS:
        write_file(profile / rel, data)
    for rel, data in N1_PLUGIN_BYTES.items():
        write_file(n1 / rel, data)
    man = {
        "unit_id": "CNF-0042",
        "engine_default": "set-difference",
        "profile": "profile",
        "n1_backup": N1_BACKUP,
        "owned_n": list(OWNED_N),
        "owned_n1": list(OWNED_N1),
        "n_only": N_ONLY_REL,
        "collision": {
            "basename": COLLISION_BASENAME,
            "user": COLLISION_USER_REL,
            "shipped": COLLISION_SHIPPED_REL,
        },
        "user_items": [
            {"path": rel, "role": role} for rel, _data, role in USER_ITEMS
        ],
    }
    (work / "manifest.json").write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8"
    )
    return man


def user_item_rels() -> list[str]:
    return [rel for rel, _data, _role in USER_ITEMS]
