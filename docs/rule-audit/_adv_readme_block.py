"""ADVERSARIAL probe: mechanically diff the rules/README.md structure block against the tree.

Neither the BUILD nor the VERIFY lane asserted this mechanically. BUILD says "the accuracy
evidence is the measured directory listing"; VERIFY re-derived only the two COUNTS (20 common
files, 13 language dirs). A block can have the right counts and the wrong names.

DETECTOR CONTROL (both states): a synthetic block missing a real name and carrying an invented
one must be reported as one missing + one extra, before the real result is trusted.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
README = REPO / "rules" / "README.md"
RULES = REPO / "rules"

NAME_RE = re.compile(r"([A-Za-z0-9_-]+\.md)")
# Language dirs are rendered several-per-line ("cpp/  csharp/  dart/ ..."), so scan tokens,
# not whole lines. A line-anchored matcher misses them and manufactures a false finding.
DIR_RE = re.compile(r"(?<![A-Za-z0-9_.-])([a-z][a-z0-9+#_-]*)/")


def block_text() -> str:
    text = README.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    start = text.index("## Structure")
    end = text.index("## Load semantics")
    section = text[start:end]
    # Only the fenced tree diagram is the "block"; prose after it cites docs/ paths whose
    # segments would otherwise read as rule directories (a matcher artifact, not a finding).
    fence = section.split("```")
    return fence[1] if len(fence) > 2 else section


def compare(block: str, actual_files: set[str], actual_dirs: set[str]):
    named = set(NAME_RE.findall(block))
    dirs = set(DIR_RE.findall(block))
    dirs -= {"common", "rules", "docs", "scripts"}
    return (
        sorted(actual_files - named),
        sorted(named - actual_files),
        sorted(actual_dirs - dirs),
        sorted(dirs - actual_dirs),
    )


def main() -> int:
    actual_files = {p.name for p in (RULES / "common").glob("*.md")}
    actual_dirs = {p.name for p in RULES.iterdir() if p.is_dir() and p.name != "common"}
    if not actual_files or not actual_dirs:
        print("FAILED:adv_readme_block empty walk")
        return 1

    # --- CONTROL: a deliberately wrong block must be reported wrong -----------------------
    victim = sorted(actual_files)[0]
    fake = "\n".join(
        [f"| {n}" for n in sorted(actual_files) if n != victim]
        + ["| __invented__.md"]
        + ["  " + "  ".join(f"{d}/" for d in sorted(actual_dirs))]
    )
    miss, extra, dmiss, dextra = compare(fake, actual_files, actual_dirs)
    ok_ctrl = miss == [victim] and extra == ["__invented__.md"]
    print(f"CONTROL broken-block -> missing={miss} extra={extra}  (must fire)")
    if not ok_ctrl:
        print("FAILED:adv_readme_block control is inert")
        return 1
    print("")

    miss, extra, dmiss, dextra = compare(block_text(), actual_files, actual_dirs)
    print(
        f"common/*.md on disk: {len(actual_files)}   language dirs on disk: {len(actual_dirs)}"
    )
    print(f"in tree but NOT named in the block : {miss}")
    print(f"named in the block but NOT on disk : {extra}")
    print(f"dirs on disk but NOT in the block  : {dmiss}")
    print(f"dirs in the block but NOT on disk  : {dextra}")
    bad = len(miss) + len(extra) + len(dmiss) + len(dextra)
    print("")
    if bad:
        print(
            f"FAILED:adv_readme_block structure block disagrees with the tree in {bad} place(s)"
        )
        return 1
    print("SUCCESS:adv_readme_block structure block matches the tree exactly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
