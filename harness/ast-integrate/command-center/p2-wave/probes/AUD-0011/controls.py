"""Both-states EOL control plus the first-line comparator that must NOT win."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from compare import census
from paths import LIVE_RULES, REPO, REPO_RULES

sys.path.insert(0, str(REPO / "tools" / "plugin"))
import eol_hash as EH  # noqa: E402


def first_line_digest(data: bytes) -> str:
    """Broken comparator: first normalised line only. Collapses the 28."""
    norm = EH.bytes_for_hash(data)
    line = norm.split(b"\n", 1)[0]
    return hashlib.sha256(line).hexdigest()


def eol_both_states() -> dict:
    snap = census(REPO_RULES, LIVE_RULES)
    c = snap["counts"]
    naive = 0
    first_line_diffs = 0
    for row in snap["rows"]:
        rp = REPO_RULES / row["path"]
        lp = LIVE_RULES / row["path"]
        rb, lb = rp.read_bytes(), lp.read_bytes()
        if rb != lb:
            naive += 1
        if first_line_digest(rb) != first_line_digest(lb):
            first_line_diffs += 1
    ok = (
        c["files"] == 88
        and c["identical"] == 5
        and c["identical_modulo_eol"] == 55
        and c["content_diverged"] == 28
        and c["live_superset"] == 3
        and c["repo_superset"] == 25
        and naive == 83
        and first_line_diffs == 0
    )
    return {
        "ok": ok,
        "files": c["files"],
        "identical": c["identical"],
        "identical_modulo_eol": c["identical_modulo_eol"],
        "content_diverged": c["content_diverged"],
        "live_superset": c["live_superset"],
        "repo_superset": c["repo_superset"],
        "naive_byte_diffs": naive,
        "first_line_diffs": first_line_diffs,
        "naive_would_report_content": naive,
        "broken_first_line_collapses_28": first_line_diffs == 0
        and c["content_diverged"] == 28,
        "good_comparator_keeps_28": c["content_diverged"] == 28,
        "eol_only_collapse_to_zero": c["identical_modulo_eol"] == 55,
    }
