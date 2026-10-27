"""IMP-0126 casefold collision fixtures. Distinct payload bytes."""
from __future__ import annotations

PKG_ALPHA = {
    "id": "pkg-alpha",
    "payload": {
        "skills/shared/README.md": b"alpha-shared-readme-unique-bytes-AAAA\n",
        "skills/alpha/SKILL.md": b"name: alpha\nunique-alpha-skill-body\n",
    },
}
PKG_BETA_CASEFOLD = {
    "id": "pkg-beta",
    "payload": {
        "skills/shared/readme.md": b"beta-shared-readme-unique-bytes-BBBB\n",
    },
}
PKG_DELTA_EXACT = {
    "id": "pkg-delta",
    "payload": {
        "skills/shared/README.md": b"delta-exact-readme-unique-bytes-DDDD\n",
    },
}
PKG_GAMMA_DISJOINT = {
    "id": "pkg-gamma",
    "payload": {
        "skills/gamma/SKILL.md": b"name: gamma\nunique-gamma-skill-body\n",
        "hooks/gamma.json": b'{"id":"gamma-hook"}\n',
    },
}

CONFLICT_LIVE_REL = ".claude/skills/shared/README.md"
ALPHA_UNIQUE = ".claude/skills/alpha/SKILL.md"
GAMMA_SKILL = ".claude/skills/gamma/SKILL.md"
GAMMA_HOOK = ".claude/hooks/gamma.json"
