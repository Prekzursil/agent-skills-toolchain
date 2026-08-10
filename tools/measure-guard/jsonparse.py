"""Every tracked .json must parse -- except the ones that are deliberately ciphertext.

THE DEFECT CLASS, measured 2026-08-11 over 1,069 tracked .json files: 3 do not parse, and all three
were committed that way and never noticed because nothing checks.

    platform/marketplace/PROOF-e2e.json              Extra data: line 209
    command-center/_wave1audit_mutation_selfcheck.json   Extra data: line 155
    hooks/worktree-debug.json                        UTF-8 BOM

The first two share one cause: a probe prints its result document and its AGENTS.md-section-4
terminal marker to the SAME stdout (`probe_e2e_marketplace.py:330-331`), someone redirected stdout
to a .json file, and the marker landed after the closing brace. PROOF-e2e.json is not a curiosity --
it is the primary evidence anchor for register item R-A06, so a consumer that tries to parse the
proof of the marketplace end-to-end run fails on it today.

THE EXCLUSION IS THE LOAD-BEARING PART. `tools/mcp/cloud-hub/accounts.json` and
`tools/mcp/search-hub/accounts.json` also fail to decode -- because they are git-crypt CIPHERTEXT,
carrying the \\x00GITCRYPT\\x00 magic and `filter=git-crypt`. They are encrypted, not broken. A gate
that flagged them would produce two permanent false positives, and anyone "repairing" one would
destroy encrypted credential material. They are skipped on TWO independent signals -- the git filter
attribute and the magic bytes -- and the skip is COUNTED, because an uncounted exclusion is how a
gate quietly stops measuring.

Crucially the exclusion keys on git-crypt, NOT on "undecodable": a plain corrupt binary is still
reported. Without that discrimination the encrypted-file guard would swallow every real corruption.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: git-crypt writes this at the head of every encrypted blob.
GITCRYPT_MAGIC = b"\x00GITCRYPT\x00"

#: Below this, assume the walk broke rather than that the repo shrank. 1,069 observed 2026-08-11.
MIN_FILES = 800

#: Files above this are skipped unread; the catalog alone is 5 MB and parsing it here is redundant
#: with the gates that already own it.
MAX_BYTES = 20_000_000


def _tracked_json(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "*.json"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def _crypt_filtered(repo: Path, rels: list[str]) -> set[str]:
    """Paths whose git `filter` attribute is git-crypt. One batch call, not one per file."""
    if not rels:
        return set()
    proc = subprocess.run(
        ["git", "-C", str(repo), "check-attr", "--stdin", "filter", "-z"],
        input="\n".join(rels),
        capture_output=True,
        text=True,
        check=False,
    )
    fields = proc.stdout.split("\0")
    out: set[str] = set()
    # `-z` emits a flat NUL-separated stream of (path, attr, value) triples.
    for i in range(0, len(fields) - 2, 3):
        if fields[i + 1] == "filter" and fields[i + 2] == "git-crypt":
            out.add(fields[i])
    return out


def scan(repo: Path | None = None) -> dict[str, object]:
    root = repo or REPO
    rels = _tracked_json(root)
    if not rels:
        raise ValueError("git ls-files returned no .json files (fail closed)")

    by_attr = _crypt_filtered(root, rels)
    parsed = 0
    skipped_encrypted = 0
    skipped_large = 0
    unparseable: list[tuple[str, str]] = []

    for rel in sorted(rels):
        path = root / rel
        try:
            if not path.is_file():
                continue
            if path.stat().st_size > MAX_BYTES:
                skipped_large += 1
                continue
            raw = path.read_bytes()
        except OSError as exc:
            unparseable.append((rel, f"{type(exc).__name__}: {exc}"))
            continue

        # Two independent signals for "this is ciphertext, not data".
        if rel in by_attr or raw.startswith(GITCRYPT_MAGIC):
            skipped_encrypted += 1
            continue

        try:
            json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            unparseable.append((rel, str(exc)[:90]))
            continue
        parsed += 1

    return {
        "parsed": parsed,
        "encrypted_skipped": skipped_encrypted,
        "large_skipped": skipped_large,
        "unparseable": unparseable,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = scan()
    except ValueError as exc:
        print(f"FAILED:jsonparse {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, default=list))

    parsed = int(report["parsed"])
    bad = report["unparseable"]
    assert isinstance(bad, list)

    # Fail closed on a collapsed walk BEFORE reporting success.
    if parsed < MIN_FILES:
        print(
            f"FAILED:jsonparse parsed only {parsed} tracked .json files, below the floor of "
            f"{MIN_FILES}; the walk has probably broken rather than the repo shrunk"
        )
        return 1

    for rel, err in bad:
        print(f"  UNPARSEABLE {rel}\n              {err}")
    if bad:
        print(
            f"FAILED:jsonparse {len(bad)} of {parsed + len(bad)} tracked .json files do not parse"
        )
        return 1
    print(
        f"SUCCESS:jsonparse {parsed} tracked .json files parse "
        f"({report['encrypted_skipped']} git-crypt encrypted skipped, "
        f"{report['large_skipped']} oversized skipped)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main(sys.argv[1:]))
