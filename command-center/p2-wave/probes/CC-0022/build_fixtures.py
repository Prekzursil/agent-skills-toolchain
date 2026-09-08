#!/usr/bin/env python3
"""Build CC-0022 fixtures, apply the 2026-08-07 18:41 re-prefix, write the live log.

Linux Cloud / single-checkout: the 44 KB Prompt-One 17-DECISION-LOG.md is not
mounted. Reconstruct from the catalog pin (line 175 present-tense collision,
Queued as P2-09, zero MECH tokens, ~44 KB) and family-M / architecture slices
that reproduce F-B-02 arithmetic 31→0 after fb02.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

from decision_log_reconcile import ORIGINAL_SENTENCE, reconcile_text  # noqa: E402

OPTION_DIR = REPO / "command-center" / "option-id"
FIX = HERE / "fixtures"


def load_fb02():
    path = REPO / "command-center" / "lib" / "fb02_apply.py"
    spec = importlib.util.spec_from_file_location("fb02_apply", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def colliding_ids() -> list[str]:
    # 31 shared bare ids (family-M ∩ pre-fix architecture).
    return [f"M-{i:02d}" for i in range(1, 32)]


def option_only_ids() -> list[str]:
    # Universe-only: M-40 / M-41 → family-M census 33.
    return ["M-40", "M-41"]


def arch_only_ids() -> list[str]:
    # Doc-13-only stand-ins (7), disjoint from family-M universe-only.
    # With colliding headers → 38 MECH after fb02; substitution count
    # 31 (index) + 38*2 (header+id) = 107. Must not intersect option_only.
    return [f"M-{i:02d}" for i in range(50, 57)]


def write_option_slice() -> Path:
    OPTION_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 07-OPTION-UNIVERSE family M slice",
        "",
        "Family M option cards. These ids stay M-NN; they are not architecture candidates.",
        "",
    ]
    for mid in colliding_ids() + option_only_ids():
        lines.append(f"- {mid}: option card {mid}")
    path = OPTION_DIR / "07-OPTION-UNIVERSE.family-M-slice.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_arch_pre() -> Path:
    OPTION_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 13-ARCHITECTURE-CANDIDATES pre-fix slice",
        "",
        "Colliding index: " + " ".join(colliding_ids()),
        "",
    ]
    for mid in colliding_ids() + arch_only_ids():
        lines.append(f"## Architecture candidate {mid}")
        lines.append(f"id: {mid}")
        lines.append("")
    path = OPTION_DIR / "13-ARCHITECTURE-CANDIDATES.pre-fix-slice.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_before_log() -> str:
    lines = [
        "# 17 Decision Log",
        "",
        "Append-only program decision log. Retired claims stay on the page.",
        "",
        "## DL-0001 Option-universe family M census",
        "date: 2026-08-07",
        "status: CURRENT",
        "valid_as_of: 2026-08-07",
        "",
        "07-OPTION-UNIVERSE family M holds 33 ids (census date 2026-08-07).",
        "probe-assert: option_family_m_count == 33",
        "",
    ]
    header = [
        "## DL-0042 Option-id namespace collision",
        "date: 2026-08-05",
        "status: CURRENT",
        "valid_as_of: 2026-08-05",
        ORIGINAL_SENTENCE,
        "",
    ]
    while len(lines) < 170:
        n = len(lines) + 1
        lines.append(
            f"<!-- padding-{n:04d}: workflow-catalog historical note, no option-id claim. -->"
        )
    lines.extend(header)
    if lines[174] != ORIGINAL_SENTENCE:
        raise RuntimeError(f"line 175 is not the collision sentence: {lines[174]!r}")
    n = 100
    while True:
        text = "\n".join(lines) + "\n"
        if len(text.encode("utf-8")) >= 44000:
            break
        n += 1
        lines.extend(
            [
                f"## DL-{n:04d} Owner ruling on workflow catalog surface {n:04d}",
                "date: 2026-07-15",
                "status: CURRENT",
                "valid_as_of: 2026-07-15",
                "",
                f"Owner ruling {n}: keep workflow catalog entry WF-{n:04d} as the "
                "published path for this surface.",
                "",
            ]
        )
    text = "\n".join(lines) + "\n"
    if "MECH" in text:
        raise RuntimeError("before-log must contain zero MECH substrings")
    return text


def main() -> int:
    FIX.mkdir(parents=True, exist_ok=True)
    opt = write_option_slice()
    pre = write_arch_pre()
    fb02 = load_fb02()
    post = OPTION_DIR / "13-ARCHITECTURE-CANDIDATES.post-fix-slice.md"
    rec_path = OPTION_DIR / "FB02-SUBSTITUTION-RECORD.json"
    rec = fb02.apply(pre, post, rec_path)
    if rec["substitutions"] != 107:
        raise RuntimeError(f"expected 107 substitutions, got {rec['substitutions']}")
    before = build_before_log()
    after = reconcile_text(before)
    (FIX / "decision-log-before.md").write_text(before, encoding="utf-8")
    (FIX / "decision-log-after.md").write_text(after, encoding="utf-8")
    live = REPO / "17-DECISION-LOG.md"
    live.write_text(after, encoding="utf-8")
    before_lines = before.splitlines()
    meta = {
        "before_bytes": len(before.encode("utf-8")),
        "before_line_175": before_lines[174],
        "before_mech_substring": "MECH" in before,
        "after_mech_substring": "MECH" in after,
        "fb02_substitutions": rec["substitutions"],
        "option_slice": str(opt.relative_to(REPO)).replace("\\", "/"),
        "arch_pre": str(pre.relative_to(REPO)).replace("\\", "/"),
        "arch_post": str(post.relative_to(REPO)).replace("\\", "/"),
        "live_log": "17-DECISION-LOG.md",
        "source": "reconstructed-from-catalog-pin-on-linux-cloud-single-checkout",
    }
    (FIX / "build-meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    print("SUCCESS:CC-0022-fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
