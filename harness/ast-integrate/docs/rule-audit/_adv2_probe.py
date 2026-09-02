"""ADVERSARIAL round-2 probe. Attacks the BUILD's r2_pathrefs sweep and re-derives the DoD numbers.

Independent of rule_audit.py: the frontmatter classifier here is hand-rolled so a bug in the
builder's parser cannot propagate into my agreement.

Sections
  M1  independent frontmatter classification of all three trees
  M2  independent always-on token totals
  M3  fence-balance audit -- an unbalanced ``` silently skips the rest of a file
  M4  how many pointer-shaped tokens the sweep SKIPS (fenced regions)
  M5  counterfactual: run the sweep with agent-self/config/rules added as a third tree
  M6  base attribution -- which of the five bases resolved each EXACT verdict
  M7  leading-./ tokens that become bare filenames and are dropped as "mentions"
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import sys
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parents[2]
TREES = {
    "repo": REPO / "rules",
    "agent-self": REPO / "agent-self" / "config" / "rules",
    "live": HOME / ".claude" / "rules",
}


def load(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_adv2_{name}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- M1 + M2
def classify_frontmatter(text: str) -> str:
    """Hand-rolled, line-oriented. always_on | lazy | fm_no_paths."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return "always_on"
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block = lines[1:i]
            break
    else:
        return "always_on"  # unterminated -- not real frontmatter
    for ln in block:
        if re.match(r"^\s*paths\s*:", ln):
            return "lazy"
    return "fm_no_paths"


def m1_m2(counter) -> dict[str, dict]:
    out = {}
    for name, root in TREES.items():
        files = sorted(p for p in root.rglob("*.md") if p.is_file())
        buckets = {"always_on": [], "lazy": [], "fm_no_paths": []}
        for p in files:
            txt = p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
            buckets[classify_frontmatter(txt)].append(p)
        tok = sum(
            counter.count(
                p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
            )
            for p in buckets["always_on"]
        )
        out[name] = {
            "files": len(files),
            "always_on": len(buckets["always_on"]),
            "lazy": len(buckets["lazy"]),
            "fm_no_paths": len(buckets["fm_no_paths"]),
            "always_on_tokens": tok,
            "always_on_names": sorted(
                p.relative_to(root).as_posix() for p in buckets["always_on"]
            ),
        }
        print(
            f"[{name:<10}] files={out[name]['files']:<4} always-on={out[name]['always_on']:<3} "
            f"lazy={out[name]['lazy']:<4} fm_no_paths={out[name]['fm_no_paths']:<3} "
            f"always_on_tokens={tok}"
        )
    print(f"GRAND TOTAL FILES = {sum(v['files'] for v in out.values())}")
    return out


# ---------------------------------------------------------------- M3 + M4 + M7
FENCE = re.compile(r"^\s*```")


def m3_m4_m7(pathrefs) -> dict:
    unbalanced: list[str] = []
    skipped_tokens = 0
    live_tokens = 0
    dot_slash_dropped: list[tuple[str, str, int, str]] = []
    scanned = 0
    for name, root in TREES.items():
        for p in sorted(root.rglob("*.md")):
            scanned += 1
            text = p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
            lines = text.split("\n")
            fences = sum(1 for ln in lines if FENCE.match(ln))
            if fences % 2:
                unbalanced.append(f"{name}:{p.relative_to(root).as_posix()} ({fences})")
            # count pointer tokens inside vs outside fenced regions
            fenced = False
            for lineno, ln in enumerate(lines, start=1):
                if FENCE.match(ln):
                    fenced = not fenced
                    continue
                toks = pathrefs.BACKTICK_RE.findall(ln) + pathrefs.LINK_RE.findall(ln)
                if fenced:
                    skipped_tokens += len(toks)
                else:
                    live_tokens += len(toks)
                    for t in toks:
                        if t.strip().startswith("./") and "/" not in t.strip()[2:]:
                            dot_slash_dropped.append(
                                (name, p.relative_to(root).as_posix(), lineno, t)
                            )
    print(f"files walked (3 trees): {scanned}")
    print(f"UNBALANCED-FENCE files: {len(unbalanced)}")
    for u in unbalanced:
        print(f"    {u}")
    print(f"pointer tokens OUTSIDE fences (scanned): {live_tokens}")
    print(f"pointer tokens INSIDE  fences (skipped): {skipped_tokens}")
    print(f"leading-./ bare tokens dropped as mentions: {len(dot_slash_dropped)}")
    for d in dot_slash_dropped[:12]:
        print(f"    {d}")
    return {
        "unbalanced": unbalanced,
        "skipped": skipped_tokens,
        "live": live_tokens,
        "dotslash": dot_slash_dropped,
    }


# ---------------------------------------------------------------- M5
def m5(pathrefs) -> tuple[int, str]:
    real = pathrefs.TREES
    pathrefs.TREES = {
        "live": HOME / ".claude" / "rules",
        "repo": REPO / "rules",
        "agent-self": REPO / "agent-self" / "config" / "rules",
    }
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = pathrefs.main()
    finally:
        pathrefs.TREES = real
    return rc, buf.getvalue()


# ---------------------------------------------------------------- M6
def m6(pathrefs) -> dict[str, int]:
    """For every EXACT verdict in the LIVE tree, record which base resolved it FIRST."""
    root = TREES["live"]
    tally: dict[str, int] = {}
    only_foreign: list[tuple[str, int, str]] = []
    for p in sorted(root.rglob("*.md")):
        text = p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
        for lineno, _kind, token in pathrefs.references(text):
            if token.split("/")[-1] in pathrefs.GENERIC and "/" not in token:
                continue
            tok = pathrefs.normalise_token(token)
            if not tok:
                continue
            hits = []
            for label, base in (
                ("REPO", REPO),
                ("~/.claude", HOME / ".claude"),
                ("~", HOME),
                ("tree_root", root),
                ("containing_dir", p.parent),
            ):
                try:
                    if (base / tok).exists():
                        hits.append(label)
                except OSError:
                    pass
            if not hits:
                continue
            tally[hits[0]] = tally.get(hits[0], 0) + 1
            if set(hits) <= {"REPO", "~"} and "/" in tok:
                only_foreign.append((p.relative_to(root).as_posix(), lineno, tok))
    print(f"live-tree EXACT resolutions by FIRST matching base: {tally}")
    print(
        f"positional tokens in the LIVE tree that resolve ONLY via the repo/home bases "
        f"(never under ~/.claude or the containing dir): {len(only_foreign)}"
    )
    for f in only_foreign[:25]:
        print(f"    {f}")
    return {"tally": tally, "only_foreign": only_foreign}


def main() -> int:
    print("=" * 78)
    print("M1/M2  independent frontmatter classification + always-on tokens")
    print("=" * 78)
    ra = load("rule_audit")
    counter = ra.Counter()
    print(
        f"encoder control: {counter.name} 'hello world'->{counter.count('hello world')}"
    )
    assert counter.name == "tiktoken/cl100k_base", (
        "encoder fell back -- numbers not comparable"
    )
    inv = m1_m2(counter)

    print()
    print("=" * 78)
    print("M3/M4/M7  fence balance, skipped tokens, dropped ./ tokens")
    print("=" * 78)
    pr = load("r2_pathrefs")
    fence = m3_m4_m7(pr)

    print()
    print("=" * 78)
    print("M5  COUNTERFACTUAL: add agent-self/config/rules as a third tree")
    print("=" * 78)
    rc, text = m5(pr)
    for line in text.splitlines():
        if line.startswith(
            ("  MISSING", "  BASENAME", "  WAIVED", "  STALE")
        ) or line.startswith(
            (
                "rule files",
                "non-EXACT",
                "  bare-filename",
                "  POSITIONAL",
                "SUCCESS",
                "FAILED",
            )
        ):
            print(line)
    print(f"THREE-TREE SWEEP rc={rc}")

    print()
    print("=" * 78)
    print("M6  base attribution for the LIVE tree")
    print("=" * 78)
    m6res = m6(pr)

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(
        f"files 3-tree={sum(v['files'] for v in inv.values())} "
        f"always-on repo/agent-self/live="
        f"{inv['repo']['always_on']}/{inv['agent-self']['always_on']}/{inv['live']['always_on']} "
        f"fm_no_paths total={sum(v['fm_no_paths'] for v in inv.values())}"
    )
    print(
        f"live always_on_tokens={inv['live']['always_on_tokens']} "
        f"repo={inv['repo']['always_on_tokens']} agent-self={inv['agent-self']['always_on_tokens']}"
    )
    print(
        f"fence: unbalanced={len(fence['unbalanced'])} skipped_tokens={fence['skipped']} "
        f"live_tokens={fence['live']} dotslash_dropped={len(fence['dotslash'])}"
    )
    print(f"three-tree sweep rc={rc}")
    print(
        f"live-only-foreign-resolution positional tokens={len(m6res['only_foreign'])}"
    )
    print("SUCCESS:_adv2_probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
