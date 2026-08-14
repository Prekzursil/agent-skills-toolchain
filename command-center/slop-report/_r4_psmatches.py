"""Dump every `sh`/`ps` match, not only the violations.

A class reporting "0 violations" is worthless until you can see WHAT it matched.
Zero violations out of zero real commands is an inert regex; zero violations out of
15 real commands is coverage. This prints the matched line so the difference is
visible rather than asserted.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _r4_promise import PATTERNS  # noqa: E402
from check_published_commands import blob, git, in_corpus, repo_root, resolve  # noqa: E402


def main() -> int:
    root = repo_root()
    tracked = set(git(root, "ls-files").split("\n")) - {""}
    corpus = sorted(p for p in tracked if in_corpus(p))
    rows = []
    for cls in ("sh", "ps"):
        pat = PATTERNS[cls]
        for path in corpus:
            for lineno, line in enumerate(blob(root, path).splitlines(), 1):
                for m in pat.finditer(line):
                    target = m.group(1).replace("\\", "/")
                    ok, resolved = resolve(target, path, tracked)
                    rows.append(
                        {
                            "cls": cls,
                            "citer": f"{path}:{lineno}",
                            "target": target,
                            "resolved": resolved,
                            "ok": ok,
                            "line": line.strip()[:110],
                        }
                    )
    dest = os.path.join(root, "command-center/slop-report/_r4_psmatches.out.json")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"rows": rows, "count": len(rows)}, fh, indent=1, sort_keys=True)
    for r in rows:
        print(f"[{r['cls']}] {'OK ' if r['ok'] else 'BAD'} {r['citer']}")
        print(f"      target={r['target']}  resolved={r['resolved']}")
        print(f"      line: {r['line']}")
    print("total:", len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
