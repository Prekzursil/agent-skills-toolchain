from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
OWNED = [
    REPO / "ci" / "check_skill_vendor_substitution.py",
    REPO / "ci" / "skill-vendor-substitution-exemptions.txt",
    REPO / "ci" / "tests" / "test_check_skill_vendor_substitution.py",
]
TOKENS = (
    "source-command-skill-health",
    "source-command-skill-create",
    "shrink-only",
    "SHRINK-ONLY",
)
MARKERS = (
    "Codex / Codex",
    "Codex + Codex",
    "by:Codex",
    "`Codex` | `codex`",
    "Codex-reflect",
    "current Codex model",
    ".Codex/",
    "Codex Workflow",
    "everything-Codex",
    "Everything Codex",
)


def main() -> int:
    print("PROBE_START")
    for path in OWNED:
        data = path.read_bytes()
        text = data.decode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        print(
            f"OWNED {path.relative_to(REPO).as_posix()} exists={path.is_file()} "
            f"bytes={len(data)} crlf={data.count(b'\\r\\n')} sha256={digest}"
        )
        for token in TOKENS:
            print(f"OWNED_TOKEN {path.name} {token}={token in text}")
    for rel in (
        "writing-skills/SKILL.md",
        "systematic-debugging/SKILL.md",
        "source-command-skill-health/SKILL.md",
        "source-command-skill-create/SKILL.md",
        "source-command-resume-session/SKILL.md",
        "source-command-save-session/SKILL.md",
        "SKILLS-MANIFEST.md",
    ):
        for root in (REPO / ".agents" / "skills", REPO / "skills"):
            path = root / rel
            label = f"{root.name if root.name != 'skills' else 'skills'}/{rel}"
            if root.name == ".agents":
                label = f".agents/skills/{rel}"
            else:
                label = f"skills/{rel}"
            if not path.is_file():
                print(f"MISSING {label}")
                continue
            counts = {}
            for marker in MARKERS:
                n = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if marker in line)
                if n:
                    counts[marker] = n
            print(f"COUNTS {label} {counts if counts else 0}")
    print("PROBE_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
