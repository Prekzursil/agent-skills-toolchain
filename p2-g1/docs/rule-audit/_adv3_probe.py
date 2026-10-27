"""ADV-R3 independent probes. Read-only. Attacks the sweep's RESOLVER and the audit's CLASSIFIER.

Three questions neither the build nor the audit lane asked:

  A  OVER-RESOLUTION. ``r2_pathrefs.classify`` tries FIVE bases (REPO, ~/.claude, HOME,
     tree_root, containing_dir). A pointer that is wrong *in its own tree* can therefore read
     EXACT because the same relative path happens to exist under a DIFFERENT base. The shipped
     controls prove all three verdicts are REACHABLE; none proves the resolver is not silently
     satisfying a claim from the wrong tree. That is the same shape as the tenth contradiction
     (a pointer wrong for its own tree), so its sensitivity is load-bearing.
     Method: re-classify every token with TREE-LOCAL bases only (tree_root, containing_dir) and
     report tokens whose verdict CHANGES. Each is a candidate the shipped sweep cannot see.

  B  CLASSIFIER RE-DERIVATION. Re-implement always-on/lazy from raw bytes with a parser that
     shares no code with ``rule_audit`` (no yaml, no import of its helpers) and diff against the
     committed ``rule-audit.json``. A second enumerator is the only way a classifier claim stops
     being a single signal.

  C  MENTION-BUCKET COMPOSITION. The sweep declares 56 bare-filename references non-findings.
     How many of those name a file that exists NOWHERE (verdict MISSING)? A bare name that
     resolves nowhere is still not a positional claim, but the count bounds what the exemption
     is carrying, and the artifact never states it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import r2_pathrefs as rp  # noqa: E402
import rule_audit as ra  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
HOME = Path.home()


# --------------------------------------------------------------------------------------- A
def classify_local(token: str, tree_root: Path, containing_dir: Path) -> str:
    """Same three-way verdict, but ONLY the two bases that belong to the citing tree."""
    token = rp.normalise_token(token)
    if not token:
        return "EXACT"
    for base in (tree_root, containing_dir):
        try:
            if (base / token).exists():
                return "EXACT"
        except OSError:
            continue
    name = token.split("/")[-1]
    if rp.basename_index().get(name) or rp.in_claude_home(name):
        return "BASENAME-ONLY"
    return "MISSING"


def probe_a() -> int:
    print("== A: over-resolution (wide bases vs tree-local bases) ==")
    changed: list[tuple[str, str, int, str, str, str]] = []
    total_tokens = 0
    for tree_name, root in rp.TREES.items():
        for path in sorted(root.rglob("*.md")):
            text = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
            rel = path.relative_to(root).as_posix()
            for lineno, _kind, token in rp.references(text):
                if token.split("/")[-1] in rp.GENERIC and "/" not in token:
                    continue
                total_tokens += 1
                wide = rp.classify(token, root, path.parent)
                local = classify_local(token, root, path.parent)
                if wide != local:
                    changed.append((tree_name, rel, lineno, token, wide, local))
    print(f"tokens examined: {total_tokens}")
    print(f"verdict changes under tree-local resolution: {len(changed)}")
    positional = [c for c in changed if "/" in rp.normalise_token(c[3])]
    print(f"  of which POSITIONAL (carry a directory component): {len(positional)}")
    for tree_name, rel, lineno, token, wide, local in positional:
        print(f"  {tree_name}:{rel}:{lineno}  {token}   wide={wide} -> local={local}")
    return len(positional)


# --------------------------------------------------------------------------------------- B
def parse_frontmatter_raw(raw: bytes) -> tuple[bool, bool]:
    """(has_frontmatter, has_paths_key) from BYTES, hand-rolled, sharing nothing with rule_audit."""
    text = raw.replace(b"\r\n", b"\n").decode("utf-8", "replace")
    lines = text.split("\n")
    # a leading BOM must not defeat the delimiter check
    if lines and lines[0].startswith("﻿"):
        lines[0] = lines[0][1:]
    if not lines or lines[0].strip() != "---":
        return (False, False)
    body: list[str] = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        body.append(line)
    if not closed:
        return (False, False)
    has_paths = any(
        ln.split(":", 1)[0].strip() == "paths"
        for ln in body
        if ":" in ln and ln[:1] not in (" ", "\t", "#")
    )
    return (True, has_paths)


def probe_b() -> int:
    print("")
    print("== B: independent frontmatter re-derivation vs committed rule-audit.json ==")
    committed = json.loads((HERE / "rule-audit.json").read_text(encoding="utf-8"))
    disagreements = 0
    for tree_name, root in ra.TREES.items():
        mine_always: set[str] = set()
        mine_total = 0
        for path in sorted(root.rglob("*.md")):
            mine_total += 1
            rel = path.relative_to(root).as_posix()
            has_fm, has_paths = parse_frontmatter_raw(path.read_bytes())
            if not (has_fm and has_paths):
                mine_always.add(rel)
        block = committed["trees"][tree_name]
        theirs_always = {
            rel for rel, info in block.items() if info["load"] != "lazy_paths_scoped"
        }
        theirs_total = len(block)
        same_n = mine_total == theirs_total
        same_set = mine_always == theirs_always
        print(
            f"  {tree_name:<11} files mine={mine_total} theirs={theirs_total} "
            f"{'OK' if same_n else 'MISMATCH'} | always-on mine={len(mine_always)} "
            f"theirs={len(theirs_always)} {'OK' if same_set else 'MISMATCH'}"
        )
        if not same_n or not same_set:
            disagreements += 1
            print(f"     only-mine : {sorted(mine_always - theirs_always)}")
            print(f"     only-their: {sorted(theirs_always - mine_always)}")
    return disagreements


# --------------------------------------------------------------------------------------- C
def probe_c() -> None:
    print("")
    print("== C: composition of the 56-token MENTION exemption ==")
    buckets: dict[str, list[str]] = {"BASENAME-ONLY": [], "MISSING": []}
    for tree_name, root in rp.TREES.items():
        for path in sorted(root.rglob("*.md")):
            text = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
            rel = path.relative_to(root).as_posix()
            for lineno, _kind, token in rp.references(text):
                if token.split("/")[-1] in rp.GENERIC and "/" not in token:
                    continue
                if "/" in rp.normalise_token(token):
                    continue
                verdict = rp.classify(token, root, path.parent)
                if verdict != "EXACT":
                    buckets[verdict].append(f"{tree_name}:{rel}:{lineno} -> {token}")
    for verdict, items in buckets.items():
        print(f"  {verdict}: {len(items)}")
    for item in buckets["MISSING"]:
        print(f"    MISSING-everywhere: {item}")


def main() -> int:
    positional_hidden = probe_a()
    disagreements = probe_b()
    probe_c()
    print("")
    if disagreements:
        print(
            f"FAILED:adv3_probe classifier re-derivation disagrees on {disagreements} tree(s)"
        )
        return 1
    print(
        f"SUCCESS:adv3_probe classifier re-derivation agrees on all trees; "
        f"{positional_hidden} positional token(s) resolve only via a non-local base"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
