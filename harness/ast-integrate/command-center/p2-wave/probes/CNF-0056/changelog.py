"""Cross-reference surface deltas against changelog lines."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _hits(changelog: str, token: str) -> list[str]:
    token = token.strip()
    if not token:
        return []
    # Match the last path component or the full token as a word.
    short = token.split(".")[-1]
    pieces = [token, short]
    if " " in token:
        pieces.append(token.split()[-1])
    hits: list[str] = []
    for line in changelog.splitlines():
        for piece in pieces:
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(piece)}(?![A-Za-z0-9_])", line):
                hits.append(line.strip())
                break
    return hits


def classify_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    changelog_text: str,
) -> dict[str, Any]:
    def bag(surface: dict[str, Any], key: str, kind: str) -> dict[str, dict[str, str]]:
        return {name: {"name": name, "kind": kind} for name in surface.get(key) or []}

    kinds = (
        ("symbols", "symbol"),
        ("cli_commands", "cli"),
        ("entry_points", "entry_point"),
    )
    before_items: dict[str, dict[str, str]] = {}
    after_items: dict[str, dict[str, str]] = {}
    for key, kind in kinds:
        before_items.update(bag(before, key, kind))
        after_items.update(bag(after, key, kind))

    removed_names = sorted(set(before_items) - set(after_items))
    added_names = sorted(set(after_items) - set(before_items))

    renamed: list[dict[str, Any]] = []
    claimed_from: set[str] = set()
    claimed_to: set[str] = set()
    # Documented rename: changelog mentions both an added and a removed name on one line.
    for old in removed_names:
        old_short = old.split(".")[-1].split()[-1]
        for new in added_names:
            new_short = new.split(".")[-1].split()[-1]
            for line in changelog_text.splitlines():
                if old_short in line and new_short in line and (
                    "renam" in line.lower() or "->" in line or " to " in line.lower()
                ):
                    if old in claimed_from or new in claimed_to:
                        continue
                    if before_items[old]["kind"] != after_items[new]["kind"]:
                        continue
                    renamed.append(
                        {
                            "from": old,
                            "to": new,
                            "kind": before_items[old]["kind"],
                            "documented": True,
                        }
                    )
                    claimed_from.add(old)
                    claimed_to.add(new)
                    break

    still_removed = [n for n in removed_names if n not in claimed_from]
    still_added = [n for n in added_names if n not in claimed_to]

    documented_removals: list[dict[str, str]] = []
    undocumented_removals: list[dict[str, str]] = []
    xref: list[dict[str, Any]] = []
    for name in still_removed:
        item = before_items[name]
        hits = _hits(changelog_text, name)
        documented = bool(hits)
        row = dict(item)
        if documented:
            documented_removals.append(row)
        else:
            undocumented_removals.append(row)
        xref.append(
            {
                "item": name,
                "kind": f"removed:{item['kind']}",
                "documented": documented,
                "changelog_hits": hits,
            }
        )
    for rec in renamed:
        hits = _hits(changelog_text, rec["from"]) + _hits(changelog_text, rec["to"])
        xref.append(
            {
                "item": f"{rec['from']} -> {rec['to']}",
                "kind": f"renamed:{rec['kind']}",
                "documented": True,
                "changelog_hits": hits,
            }
        )
    for name in still_added:
        item = after_items[name]
        hits = _hits(changelog_text, name)
        xref.append(
            {
                "item": name,
                "kind": f"added:{item['kind']}",
                "documented": bool(hits),
                "changelog_hits": hits,
            }
        )

    return {
        "removed": [before_items[n] for n in still_removed],
        "added": [after_items[n] for n in still_added],
        "renamed": renamed,
        "undocumented_removals": undocumented_removals,
        "documented_removals": documented_removals,
        "changelog_cross_reference": xref,
    }
