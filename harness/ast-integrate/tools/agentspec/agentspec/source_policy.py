"""Owner-gated source classes for the research stage (IMP-0137)."""
from __future__ import annotations

OWNER_FLAG_PUBLIC_TOR = "owner-allow-public-tor"
TOR_CLASS = "public-tor"
SOURCE_CLASSES = frozenset(
    {
        "code",
        "web",
        "docs",
        "public-tor",
        "tor",
        "onion",
        "arxiv",
        "local",
    }
)

TOR_ALIASES = frozenset({"public-tor", "tor", "onion"})
