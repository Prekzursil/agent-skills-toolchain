"""Replace `Path.read_text/write_text(..., newline=...)` with an explicit `open()` call.

WHY. `newline=` on `Path.read_text` / `Path.write_text` was added in **Python 3.13**. CI runs
3.11.15, this box runs 3.14, so every one of these call sites works here and raises
`TypeError: Path.read_text() got an unexpected keyword argument 'newline'` there. That is a
RUNTIME error, not a syntax error, which is why `py -3.11 -m py_compile` -- the detector that
caught the f-string skew -- is completely blind to it. Two different version-skew mechanisms,
two different detectors needed.

SCOPE. Deliberately limited to `ci/`, the tree CI executes. 58 files repo-wide use these kwargs;
the rest are one-shot probes that nothing runs under 3.11, and rewriting evidence scripts to fix a
problem they do not have would be churn. The exposure is reported rather than silently swept.

EQUIVALENCE. `open(p, encoding=..., newline=...)` is exactly what `read_text`/`write_text` do
internally, so the newline semantics are preserved -- which is the whole point, since these call
sites use `newline=""`/`newline="\\n"` specifically to control CRLF translation.
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

CI = Path(__file__).resolve().parent

#: Files this fixer must NOT touch, with the reason it was measured rather than assumed.
#:
#: test_cs_wiring.py -- its two call sites are NEVER EXECUTED under 3.11, so it had no defect to
#: fix: at HEAD it passes 21/21 under `py -3.11 -m pytest`. Rewriting them anyway broke
#: `test_mutation_turns_the_gate_red[duplicate-csmon-stanza]` (21 passed -> 1 failed), because the
#: mutation fixture depends on the exact write path. Measured both states before reverting. The
#: lesson generalises: "uses a 3.13-only kwarg" is not the same as "breaks on 3.11" -- only an
#: EXECUTED call site breaks, and a blanket rewrite trades a latent non-problem for a real one.
SKIP = {"test_cs_wiring.py"}

READ = re.compile(
    r"(?P<recv>[A-Za-z_][\w.]*|\([^()]*\))\.read_text\(\s*encoding=(?P<enc>[^,)]+),\s*newline=(?P<nl>[^)]+)\)"
)
WRITE = re.compile(
    r"(?P<recv>[A-Za-z_][\w.]*)\.write_text\(\s*(?P<val>[^,]+),\s*encoding=(?P<enc>[^,)]+),\s*newline=(?P<nl>[^)]+)\)"
)


def fix(text: str) -> tuple[str, int]:
    n = 0

    def rd(m: re.Match[str]) -> str:
        nonlocal n
        n += 1
        return f"io.open({m['recv']}, encoding={m['enc']}, newline={m['nl']}).read()"

    def wr(m: re.Match[str]) -> str:
        nonlocal n
        n += 1
        return (
            f"io.open({m['recv']}, 'w', encoding={m['enc']}, newline={m['nl']})"
            f".write({m['val']})"
        )

    text = READ.sub(rd, text)
    text = WRITE.sub(wr, text)
    return text, n


def main() -> int:
    total = 0
    touched: list[str] = []
    for p in sorted(CI.rglob("*.py")):
        if p.name == Path(__file__).name or p.name in SKIP:
            continue
        src = io.open(p, encoding="utf-8", newline="").read()
        out, n = fix(src)
        if not n:
            continue
        if "\nimport io\n" not in out and not out.startswith("import io\n"):
            # Insert `import io` after the last stdlib import line so ruff/isort stays happy.
            lines = out.split("\n")
            idx = max(
                (i for i, ln in enumerate(lines) if re.match(r"^import \w", ln)),
                default=-1,
            )
            if idx >= 0:
                lines.insert(idx + 1, "import io")
                out = "\n".join(lines)
        io.open(p, "w", encoding="utf-8", newline="").write(out)
        touched.append(f"{p.relative_to(CI.parent)} ({n})")
        total += n

    for t in touched:
        print(f"  patched {t}")
    print(
        f"\n{'SUCCESS' if total else 'FAILED'}:py313-newline {total} call site(s) in {len(touched)} file(s)"
    )
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
