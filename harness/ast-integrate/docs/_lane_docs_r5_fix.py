"""LANE DOCS round 5 -- apply the G2 fix to commands/sessions.md and its byte-identical mirror.

The defect: the Operator Notes bullet states a bare `scripts/hooks/cost-tracker.js`, a path that
does not exist in this repo. Every OTHER reference to that tree in the same document is wrapped
in a runtime resolver that tries ${CLAUDE_PLUGIN_ROOT}, then ~/.claude/, then the ECC plugin
cache. So the bullet is under-qualified relative to its own document.

FIX DOC, not FIX CODE: the capability is real (the hook is deployed and does emit the metrics --
27 files measured under ~/.claude/scripts/hooks/), and the tree is third-party (the file's own
SessionStart command hunts for `everything-claude-code` plugin roots). Importing 27 files of
another plugin to satisfy one sentence would be the wrong scope entirely.

Both files are byte-identical (sha ea7eaf0eb3d4) and must stay that way.
Read/written with newline="" so the CRLF bytes are preserved and the diff stays one line.
"""

from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TARGETS = [
    REPO / "commands" / "sessions.md",
    REPO / "agent-self" / "config" / "commands" / "sessions.md",
]

OLD = (
    "- For command-center style monitoring, combine `/sessions info`, `git diff --stat`, "
    "and the cost metrics emitted by `scripts/hooks/cost-tracker.js`."
)
NEW = (
    "- For command-center style monitoring, combine `/sessions info`, `git diff --stat`, "
    "and the cost metrics emitted by the `cost-tracker` stop hook. That hook ships with the "
    "deployed harness rather than this repo, so -- exactly like the `scripts/lib/*` requires "
    "above -- it resolves at runtime as `${CLAUDE_PLUGIN_ROOT}/scripts/hooks/cost-tracker.js`, "
    "falling back to `~/.claude/`."
)


def main() -> int:
    changed: list[str] = []
    for path in TARGETS:
        text = io.open(path, encoding="utf-8", newline="").read()
        count = text.count(OLD)
        if count != 1:
            print(
                f"FAILED:docs-r5-fix {path.name} expected exactly 1 occurrence, found {count}",
                file=sys.stderr,
            )
            return 1
        before_crlf = text.count("\r\n")
        new_text = text.replace(OLD, NEW, 1)
        io.open(path, "w", encoding="utf-8", newline="").write(new_text)
        after = io.open(path, encoding="utf-8", newline="").read()
        after_crlf = after.count("\r\n")
        if after_crlf != before_crlf:
            print(
                f"FAILED:docs-r5-fix {path.name} CRLF count changed "
                f"{before_crlf} -> {after_crlf} (whole-file rewrite)",
                file=sys.stderr,
            )
            return 1
        changed.append(f"{path.relative_to(REPO).as_posix()} crlf={after_crlf}")

    shas = {hashlib.sha256(p.read_bytes()).hexdigest()[:12] for p in TARGETS}
    if len(shas) != 1:
        print(f"FAILED:docs-r5-fix mirror diverged: {shas}", file=sys.stderr)
        return 1

    for c in changed:
        print("  patched", c)
    print(
        f"SUCCESS:docs-r5-fix files={len(changed)} mirror_sha={shas.pop()} identical=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
