#!/usr/bin/env python3
"""IMP-0022 independent review: discriminating casefold-vs-lower and NFC tests.

Fresh-context reviewer (Claude, Windows/NTFS substrate, 2026-09-19). Proves by
BEHAVIORAL DISCRIMINATION -- not by code reading -- that the unit's normalisation
is NFC+casefold and not lower().

Every discriminating pair below is one where lower() and casefold() DISAGREE, or
where NFC-present and NFC-absent disagree, so a wrong implementation fails
visibly instead of passing vacuously:

  D1  sharp-s pair 'STRASSE.md' vs 'Straße.md': casefold('ß') = 'ss'
      collides; lower() keeps them distinct and MISSES the collision.
  D2  final-sigma pair 'file-σ.md' vs 'file-ς.md': casefold('ς')
      = 'σ' collides; lower() keeps them distinct and MISSES.
  D3  NFD/NFC pair 'Café.md' (decomposed) vs 'café.md' (composed):
      keys are equal only if NFC is applied at all.
  D4  U+1E9B family 'ẛ.md' vs 'ẛ.md': keys equal only when NFC is applied
      (observed on CPython 3.14: fold(U+1E9B) = U+1E61 and fold('ſ'+dot) = 's'
      +dot, so a no-NFC key keeps them distinct; lower() differs too).
      NOTE ON ORDER: strict NFC-BEFORE-casefold order is NOT behaviorally
      observable on this build -- full case folding commutes with canonical
      composition for this pair (both orders yield U+1E61, verified in the
      premise block). Order is therefore anchored in code: casefold_paths.py
      nfc_path() at :88-90 is applied first and .casefold() at :93-95 second.
      No behavioral claim of order is made beyond that.
  C1  negative control: an exact-duplicate path is deduped, NOT a collision
      (README.md x2 + readme.md => group of exactly 2 paths).
  C2  clean set stays silent (0 groups).
  P1  packer pre-emit refusal on NTFS: both members cannot coexist on disk on a
      case-insensitive FS, so the colliding TREE is built via hash-object +
      update-index --cacheinfo + commit-tree; pack() must raise PackError.

Run: python -B command-center/p2-wave/reviews/IMP-0022/casefold_nfc_discrimination.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import casefold_paths as cf  # noqa: E402
import pack as pack_mod  # noqa: E402

RAW = Path(__file__).resolve().parent / "casefold-nfc-discrimination.raw.txt"

lines: list[str] = []
failures: int = 0


def emit(s: str = "") -> None:
    lines.append(s)


def check(name: str, cond: bool, detail: str) -> bool:
    global failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        failures += 1
    emit(f"[{status}] {name} :: {detail}")
    return cond


def py(s: str) -> str:
    """ASCII-safe rendering (raw file keeps exact codepoints via escapes)."""
    return ascii(s)[1:-1]


def first_group(rep: cf.CasefoldReport) -> str:
    """Detail string for the first collision group, safe when empty."""
    if not rep.collisions:
        return "none"
    return (
        f"key={py(rep.collisions[0].key)} "
        f"paths={[py(p) for p in rep.collisions[0].paths]}"
    )


def main() -> int:
    import platform

    emit(
        "IMP-0022 INDEPENDENT REVIEW: CASEFOLD/NFC DISCRIMINATION "
        "(fresh-context reviewer)"
    )
    emit("REVIEW-BEGIN:IMP-0022")
    emit(f"reviewer_vendor=claude host_platform={platform.system().lower()}")
    emit(f"python_version={platform.python_version()}")
    emit(f"unit_under_review={PLUGIN / 'casefold_paths.py'}")
    emit(
        "catalog_requirement=normalisation is casefold, not lower(); "
        "Unicode NFC applied first"
    )
    emit("")

    # Load-bearing inputs as explicit escapes so no transport layer can
    # silently normalise them. d3a is deliberately NFD (e + U+0301).
    d1a, d1b = "STRASSE.md", "Straße.md"
    d2a, d2b = "file-σ.md", "file-ς.md"
    d3a, d3b = "Café.md", "café.md"
    d4a, d4b = "ẛ.md", "ẛ.md"

    emit(
        "-- premise controls: prove each pair actually discriminates in "
        "Python semantics --"
    )
    check(
        "premise D1 lower() MISSES the sharp-s pair",
        d1a.lower() != d1b.lower(),
        f"lower: {py(d1a.lower())} != {py(d1b.lower())}",
    )
    check(
        "premise D1 casefold() catches the sharp-s pair",
        d1a.casefold() == d1b.casefold() == "strasse.md",
        f"casefold: {py(d1a.casefold())} == {py(d1b.casefold())}",
    )
    check(
        "premise D2 lower() MISSES the final-sigma pair",
        d2a.lower() != d2b.lower(),
        f"lower: {py(d2a.lower())} != {py(d2b.lower())}",
    )
    check(
        "premise D2 casefold() catches the final-sigma pair",
        d2a.casefold() == d2b.casefold() == "file-σ.md",
        f"casefold: {py(d2a.casefold())} == {py(d2b.casefold())}",
    )
    check(
        "premise D3 d3a is really NFD and NFC-composes to capital-C 'Café.md'",
        not unicodedata.is_normalized("NFC", d3a)
        and unicodedata.normalize("NFC", d3a) == "Café.md",
        f"NFC({py(d3a)}) == {py(unicodedata.normalize('NFC', d3a))}",
    )
    check(
        "premise D4 NFC('ſ'+dot) == 'ẛ' (canonical composition)",
        unicodedata.normalize("NFC", "ẛ") == "ẛ",
        "U+017F+U+0307 composes to U+1E9B",
    )
    check(
        "premise D4 casefold('ẛ') == 'ṡ' (observed on this CPython build)",
        "ẛ".casefold() == "ṡ",
        f"full fold of U+1E9B is {py('ẛ'.casefold())}",
    )
    check(
        "premise D4 casefold('ſ') == 's' (full folding)",
        "ſ".casefold() == "s",
        "U+017F full-folds to ASCII s",
    )
    check(
        "premise D4 NFC(casefold(d4b)) == casefold(NFC(d4b)) -- full folding "
        "COMMUTES with NFC composition on this build, so strict order is "
        "anchored in code (casefold_paths.py:88-95), not behavior",
        unicodedata.normalize("NFC", d4b.casefold())
        == unicodedata.normalize("NFC", d4b).casefold(),
        f"both orders give {py(unicodedata.normalize('NFC', d4b.casefold()))}",
    )
    check(
        "premise D4 no-NFC fold of the two D4 forms DIFFERS (pair discriminates)",
        d4a.casefold() != d4b.casefold() and d4a.lower() != d4b.lower(),
        f"casefold: {py(d4a.casefold())} != {py(d4b.casefold())}; "
        f"lower: {py(d4a.lower())} != {py(d4b.lower())}",
    )
    emit("")

    # D1: implementation must report the sharp-s collision (lower key would not).
    rep1 = cf.find_casefold_collisions(["LICENSE", d1a, d1b, "bin/tool.py"])
    k1a, k1b = cf.casefold_key(d1a), cf.casefold_key(d1b)
    check(
        "D1 impl keys are the CASEFOLD ('strasse.md' for both; lower would be "
        "'straß.md' for one)",
        k1a == "strasse.md" and k1b == "strasse.md",
        f"key({py(d1a)})={py(k1a)} key({py(d1b)})={py(k1b)}",
    )
    check(
        "D1 impl reports collision group for the sharp-s pair (lower() would MISS)",
        rep1.collision_count == 1 and set(rep1.collisions[0].paths) == {d1a, d1b},
        f"groups={rep1.collision_count} {first_group(rep1)}",
    )
    emit("")

    # D2: second lower-miss pair, different script.
    rep2 = cf.find_casefold_collisions([d2a, d2b])
    check(
        "D2 impl reports collision group for sigma vs final sigma (lower() would MISS)",
        rep2.collision_count == 1 and set(rep2.collisions[0].paths) == {d2a, d2b},
        f"groups={rep2.collision_count} {first_group(rep2)}",
    )
    emit("")

    # D3: NFC presence -- decomposed vs composed accent must share a key.
    rep3 = cf.find_casefold_collisions([d3a, d3b])
    check(
        "D3 impl keys equal for NFD vs NFC accent (NFC absent -> keys differ)",
        cf.casefold_key(d3a) == cf.casefold_key(d3b) == "café.md",
        f"key({py(d3a)})={py(cf.casefold_key(d3a))} "
        f"key({py(d3b)})={py(cf.casefold_key(d3b))}",
    )
    check(
        "D3 impl reports mixed-case NFD/NFC collision group (group paths are "
        "the NFC-normalised exacts)",
        rep3.collision_count == 1
        and set(rep3.collisions[0].paths) == {cf.nfc_path(d3a), cf.nfc_path(d3b)},
        f"groups={rep3.collision_count} {first_group(rep3)}",
    )
    emit("")

    # D4: NFC presence, third shape (U+1E9B family).
    rep4 = cf.find_casefold_collisions([d4a, d4b])
    check(
        "D4 impl key('ẛ.md') == 'ṡ.md' (observed fold of U+1E9B)",
        cf.casefold_key(d4a) == "ṡ.md",
        f"key={py(cf.casefold_key(d4a))}",
    )
    check(
        "D4 impl key('ẛ.md') == 'ṡ.md' -- NFC composed BEFORE "
        "casefold; a no-NFC key folds to 's'+dot and DIFFERS; lower() differs too",
        cf.casefold_key(d4b) == "ṡ.md",
        f"key={py(cf.casefold_key(d4b))}; no-NFC alternative would be "
        f"{py(d4b.casefold())}",
    )
    check(
        "D4 NFC PRESENCE: keys of both forms are EQUAL -- no-NFC and lower() "
        "both give DIFFERENT keys on this pair",
        cf.casefold_key(d4a) == cf.casefold_key(d4b) == "ṡ.md"
        and d4a.casefold() != d4b.casefold()
        and d4a.lower() != d4b.lower(),
        f"key({py(d4a)})={py(cf.casefold_key(d4a))} "
        f"key({py(d4b)})={py(cf.casefold_key(d4b))}",
    )
    check(
        "D4 documented consequence: post-NFC the pair is an EXACT duplicate, so "
        "the dedupe absorbs it (paths=1, groups=0) -- recorded as a macOS/APFS "
        "residual, not a Windows one (NTFS compares case only; these two names "
        "never collide there)",
        len(rep4.paths) == 1 and rep4.collision_count == 0,
        f"paths_after_dedupe={len(rep4.paths)} groups={rep4.collision_count} "
        f"deduped_to={py(rep4.paths[0])}",
    )
    emit("")

    # C1: exact-duplicate dedupe negative control.
    repc1 = cf.find_casefold_collisions(["README.md", "README.md", "readme.md"])
    check(
        "C1 negative control: exact duplicate deduped; group holds exactly 2 paths",
        repc1.collision_count == 1 and len(repc1.collisions[0].paths) == 2,
        f"groups={repc1.collision_count} {first_group(repc1)}",
    )
    # C2: clean set silent.
    repc2 = cf.find_casefold_collisions(["LICENSE", "README.md", "bin/tool.py"])
    check(
        "C2 negative control: clean disjoint set reports 0 groups",
        repc2.collision_count == 0,
        f"groups={repc2.collision_count}",
    )
    emit("")

    # P1: packer pre-emit refusal on NTFS via index-built colliding tree.
    with tempfile.TemporaryDirectory(prefix="imp0022-p1-") as td:
        repo = Path(td) / "r"
        repo.mkdir()
        al = Path(td) / "payload-allowlist.json"
        al.write_text(
            json.dumps(
                {
                    "artifact": "payload-allowlist",
                    "policy": "deny-by-default",
                    "rules": [
                        {"glob": "README.md", "reason": "docs"},
                        {"glob": "readme.md", "reason": "planted"},
                        {"glob": "LICENSE", "reason": "license"},
                    ],
                    "budget": {"max_bytes": 100000, "max_files": 50},
                    "forbidden_classes": {"vcs": [".git", ".git/*"]},
                }
            ),
            encoding="utf-8",
        )

        def g(*args: str, stdin: str | None = None) -> str:
            proc = subprocess.run(
                ["git", "-C", str(repo), *args],
                input=stdin,
                capture_output=True,
                text=True,
                check=True,
            )
            return proc.stdout.strip()

        g("init")
        g("config", "user.email", "imp0022-review@test.invalid")
        g("config", "user.name", "IMP-0022-review")
        # Blobs for the two case-variant names -- never materialised on disk.
        h_up = g("hash-object", "-w", "--stdin", stdin="# Upper\n")
        h_lo = g("hash-object", "-w", "--stdin", stdin="# lower\n")
        g("update-index", "--add", "--cacheinfo", f"100644,{h_up},README.md")
        g("update-index", "--add", "--cacheinfo", f"100644,{h_lo},readme.md")
        tree = g("write-tree")
        commit = g("commit-tree", tree, "-m", "collide")
        listed = subprocess.run(
            ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", commit],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        check(
            "P1 fixture: git tree holds BOTH case-variant names (impossible on "
            "NTFS disk)",
            sorted(listed) == ["README.md", "readme.md"],
            f"ls-tree={sorted(listed)}",
        )
        out = Path(td) / "should-not-exist.zip"
        try:
            pack_mod.pack(repo=repo, rev=commit, allowlist=al, out=out)
            check(
                "P1 packer refuses colliding members before archive emit",
                False,
                "PackError was NOT raised",
            )
        except pack_mod.PackError as exc:
            msg = str(exc)
            check(
                "P1 packer refuses colliding members before archive emit",
                "README.md" in msg and "readme.md" in msg and not out.exists(),
                f"PackError names both paths; out.exists()={out.exists()}; "
                f"tail={py(msg.splitlines()[-1])}",
            )
        emit("")

    verdict = failures == 0
    emit(f"discriminating_checks_failed={failures}")
    emit(f"independent_review_casefold_nfc={'PASS' if verdict else 'FAIL'}")
    emit("REVIEW-COMPLETE:IMP-0022")
    emit(
        "SUCCESS:IMP-0022-review-discrimination"
        if verdict
        else "FAILED:IMP-0022-review-discrimination"
    )

    text = "\n".join(lines) + "\n"
    RAW.write_text(text, encoding="utf-8")
    # Console stays ASCII-safe (Windows codepage-proof); raw file has the same text.
    print(text.encode("ascii", "backslashreplace").decode("ascii"), end="")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
