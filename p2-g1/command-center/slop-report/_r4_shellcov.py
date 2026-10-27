"""Enumerate the 14 commands the SHELL extractor newly guards, with their citers.

"+14 commands" is a claim until the 14 are listed. This prints each one and which
document publishes it, so the coverage added is inspectable rather than asserted.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_published_commands as G  # noqa: E402


def main() -> int:
    root = G.repo_root()
    tracked = {p for p in G.git(root, "ls-files").splitlines() if p}
    corpus = sorted(p for p in tracked if G.in_corpus(p))
    rows = []
    for path in corpus:
        for lineno, line in enumerate(G.blob(root, path).splitlines(), 1):
            for m in G.SHELL.finditer(line):
                target = m.group(1)
                ok, resolved = G.resolve(target, path, tracked)
                rows.append(
                    {
                        "citer": f"{path}:{lineno}",
                        "target": target,
                        "resolves_tracked": ok,
                        "resolved": resolved,
                    }
                )
    out = {
        "rev": G.git(root, "rev-parse", "HEAD").strip(),
        "count": len(rows),
        "unresolved": [r for r in rows if not r["resolves_tracked"]],
        "distinct_citers": sorted({r["citer"].rsplit(":", 1)[0] for r in rows}),
        "distinct_targets": sorted({r["target"] for r in rows}),
        "rows": rows,
    }
    with open(
        os.path.join(root, "command-center/slop-report/_r4_shellcov.out.json"),
        "w",
        encoding="utf-8",
        newline="\n",
    ) as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    for r in rows:
        print(
            f"  {'OK ' if r['resolves_tracked'] else 'BAD'} {r['citer']:62s} {r['target']}"
        )
    print(
        f"count={out['count']} docs={len(out['distinct_citers'])} "
        f"targets={len(out['distinct_targets'])} unresolved={len(out['unresolved'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
