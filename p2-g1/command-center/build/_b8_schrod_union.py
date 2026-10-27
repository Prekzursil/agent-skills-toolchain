"""B8: UNION-MERGE schrodinger-maestro-driver/SKILL.md across a real three-way divergence.

MEASURED three-way state (line counts after LF-normalisation):
  skills/ (projection)      111 lines  67-tool surface, 2026-2 paths, agent-skills-toolchain
                                       server path -- and NO Multi-GPU/jobserverd section
  .agents/skills @HEAD       81 lines  12-tool surface, 2022-4, source/repos server path
  live skills.daily          89 lines  same stale 12-tool text PLUS a unique
                                       "## Multi-GPU pool on a cloud box (Linux)" section
                                       (grep: Multi-GPU=1 live / =1 canonical / =0 projection)

So neither side is a superset and a one-directional copy loses content EITHER way: taking live
would revert the 67-tool rewrite, taking the projection would drop the jobserverd gotcha that
"cost real re-runs".  The union is the newer projection body with the live-unique section
grafted in ahead of "## Common Mistakes", which is where it sits in the live file.

Written to BOTH roots so ci/check_skill_dual_write.py --strict-parity stays satisfied.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
LIVE = Path(
    r"C:/Users/Prekzursil/.claude/skills.daily/schrodinger-maestro-driver/SKILL.md"
)
PROJ = REPO / "skills" / "schrodinger-maestro-driver" / "SKILL.md"
CANON = REPO / ".agents" / "skills" / "schrodinger-maestro-driver" / "SKILL.md"

MARK = "## Multi-GPU pool on a cloud box"
ANCHOR = "## Common Mistakes"


def read(p: Path) -> list[str]:
    return p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8").split("\n")


def main() -> int:
    live, proj = read(LIVE), read(PROJ)
    if any(ln.startswith(MARK) for ln in proj):
        print("REFUSED: projection already carries the section; nothing to graft")
        return 1
    s = next(i for i, ln in enumerate(live) if ln.startswith(MARK))
    e = next(i for i, ln in enumerate(live) if i > s and ln.startswith(ANCHOR))
    block = live[s:e]
    a = next(i for i, ln in enumerate(proj) if ln.startswith(ANCHOR))
    merged = proj[:a] + block + proj[a:]
    print(f"grafting live[{s}:{e}] ({len(block)} lines) into projection at line {a}")
    print(f"  projection {len(proj)} -> union {len(merged)} lines")
    if "--apply" not in sys.argv:
        print("DRY RUN (pass --apply)")
        return 0
    text = "\n".join(merged)
    for dst in (PROJ, CANON):
        dst.write_bytes(text.encode("utf-8"))
        print("  wrote", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
