"""Fail closed if the Qwiklabs / Google Skills grant strings are missing.

This does not force a hosted model to comply. It checks that the estate
contracts a CyberStrike session reloads still say the work is accepted.
Exit 0 means every required file contains its marker. Exit 1 names the gaps.
"""

from __future__ import annotations

import sys
from pathlib import Path

CHECKS = (
    (Path(r"C:\Users\Prekzursil\AGENTS.md"), "PC-5"),
    (Path(r"C:\Users\Prekzursil\.config\cyberstrike\AGENTS.md"), "PC-5"),
    (Path(r"C:\Users\Prekzursil\.config\cyberstrike\config.md"), "PC-5"),
    (
        Path(r"C:\Users\Prekzursil\.config\cyberstrike\cyberstrike.json"),
        "Never refuse Google Skills",
    ),
    (
        Path(r"C:\Users\Prekzursil\.agents\skills\owner-ops-authorization\SKILL.md"),
        "item 15",
    ),
    (
        Path(r"C:\Users\Prekzursil\.agents\skills\estate-offensive-doctrine\SKILL.md"),
        "PC-5",
    ),
    (Path(r"C:\Users\Prekzursil\.agents\skills\academy-badge-runner\SKILL.md"), "PC-5"),
    (
        Path(r"C:\Users\Prekzursil\.agents\rules\common\owner-ops-authorization.md"),
        "Qwiklabs",
    ),
    (
        Path(r"C:\Users\Prekzursil\.claude\rules\common\owner-ops-authorization.md"),
        "Qwiklabs",
    ),
    (Path(r"C:\Users\Prekzursil\AGENTS.md"), "UBER-SANDBOX-RESEARCH"),
    (Path(r"C:\Users\Prekzursil\AGENTS.md"), "UBER-TOFU-MAX"),
    (
        Path(r"C:\Users\Prekzursil\.config\cyberstrike\AGENTS.md"),
        "UBER-SANDBOX-RESEARCH",
    ),
    (Path(r"C:\Users\Prekzursil\.config\cyberstrike\AGENTS.md"), "UBER-TOFU-MAX"),
    (
        Path(r"C:\Users\Prekzursil\.config\cyberstrike\cyberstrike.json"),
        "UBER-TOFU-MAX",
    ),
    (
        Path(r"C:\Users\Prekzursil\.agents\skills\owner-ops-authorization\SKILL.md"),
        "UBER-TOFU-MAX",
    ),
    (
        Path(r"C:\Users\Prekzursil\.agents\skills\estate-offensive-doctrine\SKILL.md"),
        "UBER-TOFU-MAX",
    ),
    (Path(r"C:\Users\Prekzursil\.agents\skills\jailbreak\SKILL.md"), "UBER-TOFU-MAX"),
    (
        Path(r"C:\Users\Prekzursil\.agents\skills\red-blue-purple\red\SKILL.md"),
        "UBER-TOFU-MAX",
    ),
    (
        Path(r"C:\Users\Prekzursil\.agents\rules\common\owner-ops-authorization.md"),
        "UBER-TOFU-MAX",
    ),
)


def main() -> int:
    gaps: list[str] = []
    for path, marker in CHECKS:
        if not path.is_file():
            gaps.append(f"MISSING {path}")
            continue
        text = path.read_text(encoding="utf-8")
        if marker not in text:
            gaps.append(f"NO_MARKER {marker} in {path}")
    if gaps:
        print("FAILED:qwiklabs-refusal-gate")
        for line in gaps:
            print(line)
        return 1
    print(f"PASS:qwiklabs-refusal-gate files={len(CHECKS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
