"""ADVERSARIAL probe: classify the three rule trees WITHOUT importing rule_audit.

Mechanically independent second signal for the BUILD lane's classification:
a hand-rolled frontmatter reader (line-based, not the builder's parser) over the
same three roots. If the two disagree on any file, one of them is wrong.

DETECTOR CONTROL (both states): a synthetic bare file must classify always_on and a
synthetic paths-scoped file must classify lazy, before any real count is trusted.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parents[2]

TREES = {
    "repo": REPO / "rules",
    "agent-self": REPO / "agent-self" / "config" / "rules",
    "live": HOME / ".claude" / "rules",
}


def classify(path: Path) -> str:
    """always_on | lazy | fm_no_paths, read line-by-line on LF-normalised text."""
    text = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return "always_on"
    body: list[str] = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        body.append(line)
    if not closed:
        return "always_on"
    for line in body:
        if line.split(":")[0].strip() == "paths":
            return "lazy"
    return "fm_no_paths"


def control() -> bool:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "bare.md").write_text("# no frontmatter\n", encoding="utf-8")
        (d / "scoped.md").write_text(
            '---\npaths:\n  - "**/*.py"\n---\n# x\n', encoding="utf-8"
        )
        (d / "fm.md").write_text("---\ndescription: x\n---\n# y\n", encoding="utf-8")
        got = (
            classify(d / "bare.md"),
            classify(d / "scoped.md"),
            classify(d / "fm.md"),
        )
    want = ("always_on", "lazy", "fm_no_paths")
    print(f"CONTROL got={got} want={want}")
    return got == want


def main() -> int:
    if not control():
        print("FAILED:adv_indep_classify detector cannot distinguish the buckets")
        return 1
    print("")
    out: dict[str, dict[str, str]] = {}
    for name, root in TREES.items():
        if not root.is_dir():
            print(f"FAILED:adv_indep_classify tree missing: {name} {root}")
            return 1
        per = {
            str(p.relative_to(root)).replace("\\", "/"): classify(p)
            for p in sorted(root.rglob("*.md"))
        }
        if not per:
            print(f"FAILED:adv_indep_classify empty walk for {name}")
            return 1
        out[name] = per
        n_always = sum(1 for v in per.values() if v == "always_on")
        n_fm = sum(1 for v in per.values() if v == "fm_no_paths")
        n_lazy = sum(1 for v in per.values() if v == "lazy")
        print(
            f"{name:<11} files={len(per):>3} always_on={n_always:>2} "
            f"fm_no_paths={n_fm:>2} lazy={n_lazy:>3}"
        )
        if n_always:
            for k, v in per.items():
                if v == "always_on":
                    print(f"    ALWAYS-ON  {k}")
    print("")
    # cross-check against the builder's own JSON, if present
    import json

    jf = Path(__file__).resolve().parent / "rule-audit.json"
    if jf.is_file():
        data = json.loads(jf.read_text(encoding="utf-8"))
        mism = 0
        compared = 0
        for name, per in out.items():
            theirs = data.get("trees", {}).get(name) or {}
            if not theirs:
                print(f"FAILED:adv_indep_classify builder JSON has no map for {name}")
                return 1
            for k, v in per.items():
                t = theirs.get(k)
                if t is None:
                    mism += 1
                    print(f"  MISSING-IN-THEIRS {name}:{k}")
                    continue
                tv = t.get("load") if isinstance(t, dict) else t
                mine = {
                    "always_on": "always_on_no_frontmatter",
                    "lazy": "lazy_paths_scoped",
                    "fm_no_paths": "frontmatter_without_paths",
                }[v]
                compared += 1
                if tv != mine:
                    mism += 1
                    print(f"  MISMATCH {name}:{k} mine={mine} theirs={tv}")
        # A zero-comparison cross-check is vacuous: fail closed rather than report parity.
        if compared != sum(len(p) for p in out.values()):
            print(
                f"FAILED:adv_indep_classify only {compared} of "
                f"{sum(len(p) for p in out.values())} files were actually compared"
            )
            return 1
        print(f"cross-check: compared={compared} mismatches={mism}")
        if mism:
            return 1
    print("SUCCESS:adv_indep_classify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
