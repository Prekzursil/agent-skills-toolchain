"""Seeded-identifier detector control (both-states) plus negative word-only file."""
from __future__ import annotations

import secrets
import tempfile
from pathlib import Path

from scan import REPO, scan_file, scan_text, scan_tree, seed_token

HERE = Path(__file__).resolve().parent
NEG = HERE / "fixtures" / "negative.users-word-only.txt"
NONCE_BYTES = 4


def _nonce() -> str:
    return secrets.token_hex(NONCE_BYTES)


def run_seeded_control(tree_summary: dict | None = None) -> dict:
    nonce = _nonce()
    token = seed_token(nonce)
    with tempfile.TemporaryDirectory(prefix="res0124-seed-") as tmp:
        scratch = Path(tmp) / "scratch.seed.txt"
        scratch.write_text("control-line " + token + "\n", encoding="utf-8")
        planted = scan_file(scratch, REPO)
        planted_n = sum(
            1
            for h in planted["content_hits"]
            if h["category"] == "seeded_identifier"
        )
        scratch.write_text("control-line removed\n", encoding="utf-8")
        removed = scan_file(scratch, REPO)
        removed_n = sum(
            1
            for h in removed["content_hits"]
            if h["category"] == "seeded_identifier"
        )
    tree = tree_summary if isinstance(tree_summary, dict) else scan_tree(REPO)
    tree_seed = int((tree.get("by_category") or {}).get("seeded_identifier") or 0)
    neg_hits = []
    if NEG.is_file():
        neg_hits = scan_text(NEG.read_text(encoding="utf-8"))
    neg_home = [h for h in neg_hits if h["category"] in {"windows_home_path", "unix_home_path"}]
    ok = (
        planted_n >= 1
        and removed_n == 0
        and tree_seed == 0
        and not neg_home
    )
    return {
        "seeded_found": planted_n >= 1,
        "seeded_absent_after_removal": removed_n == 0,
        "seed_value_reproduced": False,
        "negative_users_word_only_silent": not neg_home,
        "tree_seeded_identifier_count": tree_seed,
        "planted_hits": planted_n,
        "removed_hits": removed_n,
        "scratch_outside_tree": True,
        "pass": ok,
    }
