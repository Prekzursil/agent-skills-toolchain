"""Frozen fixture corpus for BLD-0001 detector controls."""
from __future__ import annotations

from pathlib import Path

KNOWN_READ = "command-center/PROGRAM-CHARTER.md"
KNOWN_UNREAD = "command-center/NEVER-READ-SENTINEL.md"
BASH_READ = "src/app.py"
GREP_READ = "tools/command-center/unit_manifest.py"
SCHEMA_UNREAD = "command-center/schema/example.schema.json"
CI_UNREAD = ".github/workflows/ci.yml"
DOC_UNREAD = "docs/readme.md"
OVERSIZE_UNREAD = "docs/huge.md"
BINARY_UNREAD = "binary/blob.bin"
OOS_UNREAD = "out-of-scope/other.txt"
PLANTED_RECEIPT = "fixtures/receipts/planted-citation.json"

INVENTORY = [
    KNOWN_READ,
    KNOWN_UNREAD,
    BASH_READ,
    GREP_READ,
    SCHEMA_UNREAD,
    CI_UNREAD,
    DOC_UNREAD,
    OVERSIZE_UNREAD,
    BINARY_UNREAD,
    OOS_UNREAD,
]

FIXTURE_READ_CAP = 100
SCOPE_PREFIXES = (
    "command-center/",
    "tools/",
    "src/",
    ".github/",
    "docs/",
    "binary/",
)


def here() -> Path:
    return Path(__file__).resolve().parent


def write_inventory(path: Path) -> None:
    path.write_text("\n".join(INVENTORY) + "\n", encoding="utf-8")


def run_fixture_census(tree: Path) -> dict:
    import sys

    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    from extract_read_ledger import (  # noqa: WPS433
        census,
        citations_from_receipts,
        load_inventory,
    )

    materialize_tree(tree)
    inv_path = here / "fixtures" / "git-ls-files.txt"
    write_inventory(inv_path)
    inventory = load_inventory(inv_path)
    transcripts = [here / "fixtures" / "transcripts"]
    cited = citations_from_receipts(
        [here / "fixtures" / "receipts" / "planted-citation.json"]
    )
    extractor = here / "extract_read_ledger.py"
    return census(
        transcripts=transcripts,
        inventory=inventory,
        tree=tree,
        repo_root=tree,
        extractor_path=extractor,
        transcript_glob="command-center/p2-wave/probes/BLD-0001/fixtures/transcripts/*.jsonl",
        read_cap=FIXTURE_READ_CAP,
        scope_prefixes=SCOPE_PREFIXES,
        known_read=KNOWN_READ,
        known_unread=KNOWN_UNREAD,
        cited_paths=cited,
    )


def materialize_tree(root: Path) -> None:
    """Create the frozen git-ls-files tree with hostile classes for classification."""
    files = {
        KNOWN_READ: (
            "# PROGRAM-CHARTER\n"
            "Declared scope: command-center/, tools/, src/, .github/, docs/.\n"
        ),
        KNOWN_UNREAD: (
            "BLD-0001 known-unread sentinel. No transcript tool_use names this path.\n"
        ),
        BASH_READ: "print('app')\n",
        GREP_READ: "def derive(root):\n    return {}\n",
        SCHEMA_UNREAD: '{"$schema": "http://json-schema.org/draft-07/schema#"}\n',
        CI_UNREAD: "name: ci\non: [push]\njobs: {x: {runs-on: ubuntu-latest, steps: []}}\n",
        DOC_UNREAD: "fixture doc that must stay unread.\n",
        OVERSIZE_UNREAD: ("H" * 128) + "\n",
        BINARY_UNREAD: None,
        OOS_UNREAD: "outside declared scope\n",
    }
    for rel, text in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if rel == BINARY_UNREAD:
            dest.write_bytes(b"\x00\xff\xfe binary-not-utf8")
        else:
            dest.write_text(text, encoding="utf-8")
