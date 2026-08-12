r"""Replace the WRONG blob-verification recipe in both workflow-authoring mirrors.

THE DEFECT. governed-run-orchestrator.md:1145 says "On Windows verify LF committed bytes, not only a
CRLF working tree" and then prescribes `git archive <final-sha> | tar -x -C <fresh-temp>`. On Windows
git archive applies export-time EOL conversion and hands back CRLF -- the OPPOSITE of the stored blob.
A rule that tells you to verify against the wrong bytes is worse than no rule: it manufactures
confidence in exactly the check meant to catch this class.

FOUR INDEPENDENT MEASUREMENTS AGREE, which is why this is applied rather than debated:
  1. rules/common/windows-shell.md 8b (prior, on a 3.8 KB file)
  2. the fleet-audit quality lens (24,400 B / 0 CRLF)
  3. the SKILLS build lane (7,487 B / 0 CRLF vs git archive 7,627 B / 140 CRLF)
  4. here, on this very file: git show HEAD:path = git cat-file -p = 160,503 B / 0 CRLF, while the
     working tree is 163,401 B / 2,898 CRLF, and all three are byte-identical after LF-normalisation
     -- so the delta is purely EOL, which is the control that makes the numbers mean anything.

The program ground floor I wrote for two workflows stated the opposite ("git archive AND git show
return CRLF worktree bytes"), so ~66 agents were told to avoid a correct recipe. That is corrected in
the running wave's research block and corrected at the source here.

WHAT IS DELIBERATELY NOT TOUCHED: the second `git archive` at ~:2173 BUILDS a cohort tarball
(--format=tar.gz --output=...). That use is correct and must stay -- EOL conversion is irrelevant when
you are packaging, and only matters when you are comparing bytes. Replacing it would break packaging
to fix a verification bug. The script therefore anchors on the exact one-line recipe, asserts it
matches EXACTLY ONCE per file, and fails closed otherwise.

DUAL-WRITE: .agents/skills/ and skills/ are byte-identical mirrors under a parity test (D-001). Both
are edited in the same pass and re-compared afterwards, because fixing one mirror is precisely how the
[csmon] cross-lane RED happened an hour ago.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REL = "workflow-authoring/templates/governed-run-orchestrator.md"
ROOTS = (REPO / ".agents" / "skills", REPO / "skills")

OLD = "git archive <final-sha> | tar -x -C <fresh-temp>"
NEW = "git show <final-sha>:<path>          # NOT git archive: it applies export-time EOL\n" \
      "                                     # conversion and returns CRLF on Windows, i.e. the\n" \
      "                                     # opposite of the stored blob. git cat-file -p is\n" \
      "                                     # equivalent; both measured 0 CRLF against a\n" \
      "                                     # working tree carrying 2,898."
#: The packaging use that must survive untouched.
KEEP = "git archive --format=tar.gz"


def main() -> int:
    targets = [r / REL for r in ROOTS]
    for p in targets:
        if not p.is_file():
            print(f"FAILED:blob-recipe missing {p}")
            return 1

    # Parity precondition: if the mirrors already differ, a blind two-sided edit could widen the gap.
    a, b = (p.read_bytes() for p in targets)
    if a != b:
        print("FAILED:blob-recipe mirrors already differ before the edit -- reconcile first")
        return 1

    for p in targets:
        raw = p.read_text(encoding="utf-8", newline="")
        n = raw.count(OLD)
        if n != 1:
            print(f"FAILED:blob-recipe anchor appears {n} times in {p} (expected exactly 1)")
            return 1
        keep_before = raw.count(KEEP)
        out = raw.replace(OLD, NEW)
        if out.count(KEEP) != keep_before or keep_before < 1:
            print(f"FAILED:blob-recipe the packaging git archive was disturbed in {p}")
            return 1
        # newline='' on BOTH read and write: without it Windows re-inserts CRLF on every line and
        # the diff becomes the whole file instead of five lines.
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(out)
        print(f"  patched {p.relative_to(REPO)} (packaging git archive preserved: {keep_before})")

    a, b = (p.read_bytes() for p in targets)
    if a != b:
        print("FAILED:blob-recipe mirrors DIVERGED after the edit -- D-001 parity broken")
        return 1
    print("  mirrors byte-identical after edit: True")

    for p in targets:
        txt = p.read_text(encoding="utf-8", newline="")
        assert OLD not in txt, p
        assert "git show <final-sha>:<path>" in txt, p
    print("\nSUCCESS:fix-blob-recipe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
