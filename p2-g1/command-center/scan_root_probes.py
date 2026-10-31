r"""Decide whether the six untracked root-level probe scripts are safe and worth committing.

WHY THEY ARE IN QUESTION. `.gitignore:70` ignores `command-center/_*.py`, but these sit at the REPO
ROOT, so they are untracked AND un-ignored -- the fragile middle state. Tracked artifacts
(`WAVE3-FLOOR-AUDIT.{json,md}`) name all six, so a fresh clone gets an audit citing files it does
not have.

USE-VS-MENTION, applied to my own discriminator. The rule of thumb "untracked + referenced by
tracked content = deliverable" is too coarse: the audit lists these six under a heading
`**Elsewhere (6):**`, which is an INVENTORY, not a runtime dependency. Nothing imports or executes
them. So they are not deliverables in the sense that something breaks without them -- they are the
EVIDENCE behind a tracked count, the same category as lane D1's `.out.json` payloads, which were
committed for exactly this reason.

Written as a file, not a heredoc: a bash heredoc strips the backslashes out of a character class
like `[/\\]` even under quoted-delimiter form, which is windows-shell rule 8c and cost two attempts.
"""

from __future__ import annotations

import pathlib
import re

FILES = (
    "_f7_syncskills_probe.py",
    "_refute_f1_codex_stubs.py",
    "_refute_f4_atomicity.py",
    "_refute_f6_probe.py",
    "_refute_f6_probe2.py",
    "_refute_f6_probe3.py",
)

REPO = pathlib.Path(__file__).resolve().parents[1]

SECRET = re.compile(
    r"sk-[A-Za-z0-9]{10}|ghp_[A-Za-z0-9]{6}|hf_[A-Za-z0-9]{10}"
    r"|password\s*=\s*['\"]|token\s*=\s*['\"][A-Za-z0-9]",
    re.I,
)
ABSPATH = re.compile(r"C:[/\\]+Users[/\\]+Prekzursil", re.I)


def main() -> int:
    # Controls first: the pattern must fire on a known-bad string and stay silent on a benign one.
    # A scanner that cannot tell those apart is not evidence of anything.
    if not SECRET.search('token = "ghp_abcdef"'):
        print("FAILED:scan-root-probes control 1 (known-bad) did not fire")
        return 1
    if SECRET.search("token = os.environ['GH_TOKEN']"):
        print("FAILED:scan-root-probes control 2 (benign) false-positived")
        return 1
    print("  controls PASS (known-bad fires, env-var lookup does not)\n")

    total_secrets = 0
    for name in FILES:
        path = REPO / name
        if not path.exists():
            print(f"  {name:<30} ABSENT")
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        secrets = SECRET.findall(body)
        total_secrets += len(secrets)
        print(
            f"  {name:<30} {path.stat().st_size:>6} B  "
            f"secrets={len(secrets)}  hardcoded-abs-paths={len(ABSPATH.findall(body))}"
        )

    print()
    if total_secrets:
        print(
            f"FAILED:scan-root-probes {total_secrets} possible secret(s) -- do NOT commit"
        )
        return 1
    print("SUCCESS:scan-root-probes no secret-shaped literal in any of the six")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
