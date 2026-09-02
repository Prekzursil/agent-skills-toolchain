#!/usr/bin/env python3
"""Contract excerpt for a placeholder module: every probe line that defines what it must do.

Usage: python3 _g1_contract_excerpt.py <dotted.module> [<dotted.module> ...] [--units ID,ID]
For each module: the placeholder file (path + the names it fabricates), every probe file that
imports it (by `import x.y`, `from x.y import a, b`, or `from x import y`), and for each such
file the import lines plus every line mentioning one of the imported names, with 1 line of
context. Also lists the units' current verdict (latest overlay row) so the writer knows which
importers are OK today (regression set) and which fail (target set).

Read-only. Output is plain text for a human/agent writer.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import WIN, latest_rows  # noqa: E402

PROBES = WIN / "command-center" / "p2-wave" / "probes"
MARKER = "# g1-surface: " + "generated"
ROOTS = [WIN, WIN / "tools", WIN / "platform" / "lib", WIN / "tools" / "agentspec"]


def resolve_file(dotted: str) -> Path | None:
    rel = Path(*dotted.split("."))
    parts = dotted.split(".")
    # honour the repo-root shims: <pkg>.* lives under tools/<pkg>
    if parts[0] in {"marketplace", "plugin", "workflow_foundry", "council", "router", "bench"}:
        cands = [WIN / "tools" / rel, WIN / rel]
    else:
        cands = [root / rel for root in ROOTS]
    for cand in cands:
        if (cand / "__init__.py").is_file():
            return cand / "__init__.py"
        if Path(str(cand) + ".py").is_file():
            return Path(str(cand) + ".py")
    return None


def import_patterns(dotted: str) -> list[re.Pattern]:
    """Match imports of the module, of any submodule below it, and `from parent import leaf`."""
    parent, _, leaf = dotted.rpartition(".")
    d = re.escape(dotted)
    pats = [
        re.compile(rf"^\s*import\s+{d}(?:\.\w+)*\b"),
        re.compile(rf"^\s*from\s+{d}(?:\.\w+)*\s+import\b"),
    ]
    if parent:
        pats.append(re.compile(rf"^\s*from\s+{re.escape(parent)}\s+import\b.*\b{re.escape(leaf)}\b"))
    # `tools.` prefix twins
    if not dotted.startswith("tools.") and dotted.split(".")[0] in {"council", "marketplace", "plugin", "router", "bench", "workflow_foundry"}:
        pats += import_patterns("tools." + dotted)
    return pats


def imported_names(lines: list[str], dotted: str) -> set[str]:
    names: set[str] = set()
    parent, _, leaf = dotted.rpartition(".")
    for ln in lines:
        m = re.match(rf"^\s*from\s+(?:tools\.)?{re.escape(dotted)}((?:\.\w+)*)\s+import\s+\(?(.*)$", ln)
        if m:
            if m.group(1):
                names.add(m.group(1).split(".")[1])  # submodule name
            for tok in re.split(r"[,\s()]+", m.group(2)):
                tok = tok.strip()
                if tok and tok != "as" and tok.isidentifier():
                    names.add(tok)
        m2 = re.match(rf"^\s*import\s+(?:tools\.)?{re.escape(dotted)}((?:\.\w+)*)\b", ln)
        if m2:
            names.add(leaf)
            if m2.group(1):
                names.add(m2.group(1).split(".")[1])
        if parent and re.match(rf"^\s*from\s+(?:tools\.)?{re.escape(parent)}\s+import\b.*\b{re.escape(leaf)}\b", ln):
            names.add(leaf)
    return names


def main() -> int:
    args = sys.argv[1:]
    only_units: set[str] = set()
    if "--units" in args:
        i = args.index("--units")
        only_units = set(args[i + 1].split(","))
        del args[i : i + 2]
    rows = latest_rows()
    for dotted in args:
        print("=" * 100)
        f = resolve_file(dotted)
        print(f"MODULE {dotted}\n  file: {f.relative_to(WIN).as_posix() if f else 'UNRESOLVED'}")
        if f:
            text = f.read_text(encoding="utf-8", errors="replace")
            print(f"  placeholder: {MARKER in text}  lines: {len(text.splitlines())}")
            m = re.search(r"__all__ = (\[.*?\])", text, re.S)
            if m:
                print(f"  fabricated names: {m.group(1)[:600]}")
        pats = import_patterns(dotted)
        hits = 0
        scan: list[tuple[str, Path]] = [(p.name, p) for p in sorted(PROBES.iterdir()) if p.is_dir()]
        # real code that imports the module carries contract too (transitive dependents)
        scan += [("(code)", WIN / d) for d in ("tools", "platform", "lib", "council", "router", "marketplace", "plugin", "workflow_foundry", "command-center/p2-wave/seed-stage") if (WIN / d).is_dir()]
        for uid, probe_dir in scan:
            if only_units and uid not in only_units and uid != "(code)":
                continue
            for py in sorted(probe_dir.rglob("*.py")):
                if uid == "(code)" and (f and py.resolve() == f.resolve() or "/probes/" in py.as_posix() or MARKER in py.read_text(encoding="utf-8", errors="replace")[:1200]):
                    continue
                try:
                    lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                # collapse multi-line `from x import (\n a,\n b)` into one logical line for matching
                joined: list[str] = []
                buf = ""
                for ln in lines:
                    if buf:
                        buf += " " + ln.strip()
                        if ")" in ln:
                            joined.append(buf)
                            buf = ""
                        continue
                    if re.match(r"^\s*from\s+\S+\s+import\s+\($", ln.rstrip()) or (
                        re.match(r"^\s*from\s+\S+\s+import\s+\(", ln) and ")" not in ln
                    ):
                        buf = ln.rstrip()
                        continue
                    joined.append(ln)
                if not any(p.search(ln) for ln in joined for p in pats):
                    continue
                hits += 1
                rec = rows.get(uid) or {}
                verdict = "code" if uid == "(code)" else ("OK" if rec.get("ok") else ("FAIL " + str(rec.get("line", ""))[:70] if rec else "unmeasured"))
                print(f"\n--- {py.relative_to(WIN).as_posix()}   [unit {uid}: {verdict}]")
                names = imported_names(joined, dotted)
                print(f"    imports: {sorted(names)}")
                name_re = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b") if names else None
                for i, ln in enumerate(lines):
                    show = any(p.search(ln) for p in pats) or (name_re and name_re.search(ln))
                    if show:
                        lo, hi = max(0, i - 1), min(len(lines), i + 2)
                        for j in range(lo, hi):
                            mark = ">>" if j == i else "  "
                            print(f"  {mark}{j + 1:5d}: {lines[j][:160]}")
                        print("  ..")
        print(f"\n  importing probe files: {hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
