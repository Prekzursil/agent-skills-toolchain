"""Both-states controls for IMP-0441 EOL policy.

Live .gitattributes must be green. Dropping `*.md eol=lf` must turn
eol_policy.py --check red. Dual-platform gates must exit 0 on LF and on
CRLF, and RAW CRLF hashes must disagree with recorded LF digests.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import eol_policy as eol  # noqa: E402


def _drop_md_rule(src: Path, dst: Path) -> None:
    lines = []
    dropped = False
    for line in src.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped.startswith("*.md") and "eol=lf" in stripped:
            dropped = True
            continue
        lines.append(line)
    if not dropped:
        raise RuntimeError("mutant did not drop *.md eol=lf")
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestEolPolicy(unittest.TestCase):
    def test_live_gitattributes_has_required_eol_lf(self) -> None:
        missing = eol.check_gitattributes()
        self.assertEqual(missing, [])
        self.assertEqual(eol.main(["--check"]), 0)

    def test_dropping_md_rule_turns_check_red(self) -> None:
        with tempfile.TemporaryDirectory(prefix="imp0441-md-") as raw:
            mutant = Path(raw) / "mutant.gitattributes"
            _drop_md_rule(eol.GITATTRIBUTES, mutant)
            missing = eol.check_gitattributes(mutant)
            self.assertIn("*.md", missing)
            self.assertEqual(
                eol.main(["--check", "--gitattributes", str(mutant)]), 1
            )

    def test_dual_platform_green_and_prefix_was_red(self) -> None:
        with tempfile.TemporaryDirectory(prefix="imp0441-dp-") as raw:
            tmp = Path(raw)
            report = eol.dual_platform(tmp)
            self.assertTrue(report["linux_green"], report["linux_lf"])
            self.assertTrue(
                report["windows_green_after"], report["windows_crlf_sim"]
            )
            prefix = eol.prefix_raw_hash_red(tmp / "crlf" / "command-center")
            self.assertTrue(prefix["both_prefix_red"], prefix)
            self.assertTrue(prefix["both_postfix_match"], prefix)
            self.assertGreater(prefix["register_crlf_count"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
