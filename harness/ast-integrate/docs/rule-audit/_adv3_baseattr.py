"""Which BASE satisfies each positional citation? Adjudicates probe A's 70 candidates as a class.

Probe A showed 70 positional tokens read EXACT only because ``classify`` tries bases beyond the
citing tree. That is a finding ONLY if some of them resolve via a base that has no business
satisfying them. If essentially all resolve via the REPO ROOT, the explanation is the dominant
citation idiom in these rules -- a repo-root-relative path -- and the permissive resolver is
correct by design, not a hole. Attribute each one and let the distribution decide.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import r2_pathrefs as rp  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
HOME = Path.home()

BASES = [
    ("REPO-root", REPO),
    ("claude-home", HOME / ".claude"),
    ("HOME", HOME),
]


def main() -> int:
    counts: dict[str, int] = {}
    oddities: list[str] = []
    for tree_name, root in rp.TREES.items():
        for path in sorted(root.rglob("*.md")):
            text = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
            rel = path.relative_to(root).as_posix()
            for lineno, _kind, token in rp.references(text):
                tok = rp.normalise_token(token)
                if "/" not in tok:
                    continue
                if token.split("/")[-1] in rp.GENERIC and "/" not in token:
                    continue
                # tree-local first: if it resolves there, it is not a probe-A candidate
                if (root / tok).exists() or (path.parent / tok).exists():
                    continue
                if rp.classify(token, root, path.parent) != "EXACT":
                    continue
                who = "none"
                for name, base in BASES:
                    try:
                        if (base / tok).exists():
                            who = name
                            break
                    except OSError:
                        continue
                counts[who] = counts.get(who, 0) + 1
                if who != "REPO-root":
                    oddities.append(f"{who:<12} {tree_name}:{rel}:{lineno} -> {token}")

    total = sum(counts.values())
    print(f"probe-A positional candidates attributed: {total}")
    for who, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  satisfied by {who:<12} {n}")
    print("")
    print("non-REPO-root resolutions (the only ones that could be a cross-tree leak):")
    for line in oddities or ["  (none)"]:
        print(f"  {line}")
    print("")
    if total == 0:
        print(
            "FAILED:adv3_baseattr attributed zero candidates -- probe A and this disagree, fix the instrument"
        )
        return 1
    print(
        f"SUCCESS:adv3_baseattr {counts.get('REPO-root', 0)}/{total} resolve via the repo root "
        f"(repo-root-relative citation idiom), {len(oddities)} other"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
