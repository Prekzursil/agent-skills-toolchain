#!/usr/bin/env python3
"""Probe 2: archive-as-blob lint + RELEASE-CHECKLIST recipe matches the gate.

Catalog tests:
  test_lint_flags_git_archive_used_as_a_blob_source
  test_release_checklist_recipe_matches_the_gate
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import archive_lint as L  # noqa: E402
import blob_gate as G  # noqa: E402
from harness_load import load_both_states  # noqa: E402

UNIT = "TST-0031"
CHECKLIST = REPO / "command-center" / "RELEASE-CHECKLIST.md"

BAD_MD = """# planted prescription

```bash
git archive HEAD -- sample.txt | tar -xO > /tmp/bytes
```
"""

MENTION_MD = """# documentary mention

Never use git archive | tar -x to read blob bytes; it returns CRLF
on export. Use git cat-file -p instead.
"""

PACKAGING_MD = """# legitimate packaging

```bash
git archive --format=tar.gz -o plugin.tar.gz HEAD
```
"""

BAD_SH = "git archive HEAD -- foo.py | tar -xO | sha256sum\n"
MENTION_SH = "# never git archive | tar -x as a blob source\ngit cat-file -p HEAD:foo.py | sha256sum\n"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    bs = load_both_states()
    if not CHECKLIST.is_file():
        return fail(f"missing {CHECKLIST}")
    text = CHECKLIST.read_text(encoding="utf-8")
    if G.AUTHORITATIVE_RECIPE.split(" <")[0] not in text and "git cat-file -p" not in text:
        return fail("RELEASE-CHECKLIST.md does not prescribe git cat-file -p")
    if "git show" not in text:
        return fail("RELEASE-CHECKLIST.md missing equivalent git show recipe")
    if G.AUTHORITATIVE_RECIPE not in text and "git cat-file -p" not in text:
        return fail("checklist recipe does not match the gate")
    cl_findings = L.scan_path(CHECKLIST, repo=REPO)
    cl_prov = [f for f in cl_findings if f["kind"] == "provenance"]
    if cl_prov:
        return fail(f"checklist still prescribes archive as blob source: {cl_prov}")
    # Gate module recipe strings must appear so the documents cannot drift apart.
    gate_src = (HERE / "blob_gate.py").read_text(encoding="utf-8")
    if "git cat-file" not in gate_src or "archive" not in gate_src:
        return fail("gate source lost cat-file / archive vocabulary")

    with tempfile.TemporaryDirectory(prefix="tst0031-p2-") as td:
        root = Path(td)
        (root / "bad.md").write_text(BAD_MD, encoding="utf-8")
        (root / "mention.md").write_text(MENTION_MD, encoding="utf-8")
        (root / "pack.md").write_text(PACKAGING_MD, encoding="utf-8")
        (root / "bad.sh").write_text(BAD_SH, encoding="utf-8")
        (root / "mention.sh").write_text(MENTION_SH, encoding="utf-8")

        def lint_fires(state: str) -> bool:
            path = root / state
            hits = [f for f in L.scan_path(path) if f["kind"] == "provenance"]
            return bool(hits)

        rec_md = bs.control(
            lint_fires,
            "mention.md",
            "bad.md",
            check_id="test_lint_flags_git_archive_used_as_a_blob_source",
            description="Lint fires on a fenced git-archive|tar blob recipe and is silent on a prose mention.",
        )
        if rec_md.verdict != bs.VALID:
            return fail(f"md both-states rejected: {rec_md.to_dict()}")
        rec_sh = bs.control(
            lint_fires,
            "mention.sh",
            "bad.sh",
            check_id="test_lint_shell_prescription",
            description="Lint fires on a shell archive|tar blob pipeline and is silent when it is only a comment.",
        )
        if rec_sh.verdict != bs.VALID:
            return fail(f"sh both-states rejected: {rec_sh.to_dict()}")

        pack_hits = [f for f in L.scan_path(root / "pack.md") if f["kind"] == "provenance"]
        if pack_hits:
            return fail(f"packaging archive flagged as provenance: {pack_hits}")
        pack_kinds = {f["kind"] for f in L.scan_path(root / "pack.md")}
        if "packaging" not in pack_kinds:
            return fail(f"packaging fence not classified: {pack_kinds}")

        mention_kinds = {f["kind"] for f in L.scan_path(root / "mention.md")}
        if "provenance" in mention_kinds:
            return fail("mention classified as provenance")
        if "mention" not in mention_kinds:
            return fail(f"mention.md not classified as mention: {mention_kinds}")

        print(
            f"both_states md={rec_md.verdict} sh={rec_sh.verdict} "
            f"checklist_provenance={len(cl_prov)} packaging_ok=True"
        )

    print("SUCCESS:TST-0031-probe2 archive lint and checklist recipe match the gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
