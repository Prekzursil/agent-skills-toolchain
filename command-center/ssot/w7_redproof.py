"""Red-proof for W7 -- the wire that binds the CLAUDE.md counts to the measured artifact.

WHAT THIS ANSWERS. Running the gate on a healthy tree and seeing `all intact` proves
nothing: a checker that matched zero claims and compared zero numbers would print exactly
the same line. Before W7's silence may be read as "the counts agree", three things have to
be true, and this file measures each of them.

  1. POSITIVE CONTROL -- on the real tree W7 is silent AND it actually compared a
     plausible number of values. Fails CLOSED below a floor, so a regex that quietly stops
     matching cannot masquerade as agreement.
  2. TREATMENT -- perturb one number, or the artifact, and W7 must fire.
  3. DISCRIMINATION AGAINST THE PRE-W7 GATE -- the decisive one. The same broken tree is
     ALSO handed to the checker as it existed at HEAD, reconstructed with `git show`. State
     the two hypotheses first: H1 "W7 detects count drift" vs H2 "any checker goes red on a
     tree somebody edited". Under H2 the old checker would fire too. It must stay GREEN --
     that silence is what makes the new red attributable to W7 rather than to the edit.

Point 3 is the shape this estate keeps getting wrong: a control that passes under both
hypotheses is not a control, it only proves the instrument ran.

Exit 0 = every case behaved; 1 = a case did not; 2 = the proof could not be set up.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import ssot_wiring_check as wiring  # noqa: E402

CHECKER_REL = "command-center/ssot/ssot_wiring_check.py"

# Everything the checker reads. Copied file-by-file: a recursive copy on Windows aborts on
# a reserved device name and would drag in whatever a sibling lane is mid-write on.
COPY_PATHS = (
    "CLAUDE.md",
    "docs/ssot/SSOT-CLONE-INVENTORY.md",
    "command-center/ssot/ssot_drift_gate.py",
    "command-center/ssot/ssot_wiring_check.py",
    "command-center/ssot/apply_severed_resolution.py",
    "command-center/ssot/redproof_severed.py",
    "command-center/ssot/population-classified.json",
    ".github/workflows/skill-dual-write.yml",
)

# The floor for the positive control. The block carries 7 claim sentences holding 12
# numbers between them; anything at or below this means a pattern stopped matching.
MIN_COMPARISONS = 12


def _scratch(dest: pathlib.Path) -> pathlib.Path:
    root = dest / "repo"
    for rel in COPY_PATHS:
        src = ROOT / rel
        if not src.exists():
            raise SystemExit(f"cannot build the proof: {rel} is absent")
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return root


def _sub(path: pathlib.Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"mutation anchor absent in {path.name}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _w7(root: pathlib.Path) -> list[str]:
    return [d for c, d in wiring.run(root) if c.startswith("W7")]


def _all_codes(root: pathlib.Path) -> set[str]:
    return {c for c, _ in wiring.run(root)}


def _comparisons(root: pathlib.Path) -> int:
    """How many (claimed, measured) pairs W7 actually compared.

    A COUNT of the thing being compared, not a re-read of the verdict: the estate's
    measured cure for a control that reports parity because it is looking one level above
    the collection it believes it is reading.
    """
    body = wiring._block((root / "CLAUDE.md").read_text(encoding="utf-8")) or ""
    prose = wiring._live_prose(body)
    n = 0
    for _label, pattern, keys in wiring.COUNT_CLAIMS:
        for m in re.finditer(pattern, prose):
            n += len(list(zip(m.groups(), keys)))
    return n


def _old_checker(dest: pathlib.Path) -> pathlib.Path | None:
    """The checker as committed at HEAD -- i.e. WITHOUT W7, if W7 is not yet committed."""
    p = subprocess.run(
        ["git", "show", f"HEAD:{CHECKER_REL}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if p.returncode != 0:
        return None
    out = dest / "ssot_wiring_check_at_head.py"
    out.write_text(p.stdout, encoding="utf-8", newline="\n")
    return out


def _run_old(old: pathlib.Path, root: pathlib.Path) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, str(old), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    import tempfile

    results: list[dict] = []
    ok = True

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)

        # --- 1. POSITIVE CONTROL --------------------------------------------------
        healthy = _scratch(tmp / "healthy")
        h_details = _w7(healthy)
        n_cmp = _comparisons(healthy)
        pos_ok = not h_details and n_cmp >= MIN_COMPARISONS
        ok &= pos_ok
        results.append(
            {
                "case": "positive-control",
                "w7_fired": bool(h_details),
                "comparisons": n_cmp,
                "floor": MIN_COMPARISONS,
                "expect": "silent AND comparisons >= floor",
                "pass": pos_ok,
            }
        )
        print(
            f"  [{'OK ' if pos_ok else 'BAD'}] positive-control        "
            f"W7 silent={not h_details}  comparisons={n_cmp} (floor {MIN_COMPARISONS})"
        )

        # --- 2. TREATMENTS --------------------------------------------------------
        # Each perturbs exactly one thing and must fire W7 and ONLY W7. Exclusivity
        # matters: a mutation that also trips W2/W3 would leave it unproven that W7
        # is what noticed.
        cases: list[tuple[str, object]] = [
            (
                "population-drift",
                lambda r: _sub(
                    r / "CLAUDE.md",
                    "**178 checkouts across 168 object stores**",
                    "**179 checkouts across 168 object stores**",
                ),
            ),
            (
                "arithmetic-does-not-close",
                lambda r: _sub(
                    r / "CLAUDE.md", "9 + 168 + 1 = 178", "9 + 168 + 1 = 177"
                ),
            ),
            (
                "uncommitted-surface-drift",
                lambda r: _sub(r / "CLAUDE.md", "**132 of them", "**131 of them"),
            ),
            (
                "claim-sentence-deleted",
                lambda r: _sub(
                    r / "CLAUDE.md",
                    "5 have no remote at all.**",
                    "some have no remote.**",
                ),
            ),
            (
                "artifact-absent",
                lambda r: (
                    r / "command-center/ssot/population-classified.json"
                ).unlink(),
            ),
            (
                "artifact-disagrees-with-itself",
                lambda r: _bend_json(r),
            ),
        ]

        for name, mutate in cases:
            root = _scratch(tmp / name)
            mutate(root)
            codes = _all_codes(root)
            fired = any(c.startswith("W7") for c in codes)
            exclusive = codes == {"W7-count-drift"}
            case_ok = fired and exclusive
            ok &= case_ok
            results.append(
                {
                    "case": name,
                    "codes": sorted(codes),
                    "w7_fired": fired,
                    "exclusive": exclusive,
                    "expect": "W7 fires, and no other wire",
                    "pass": case_ok,
                }
            )
            print(
                f"  [{'OK ' if case_ok else 'BAD'}] {name:24s} "
                f"fired={fired} exclusive={exclusive} codes={sorted(codes)}"
            )

        # --- 3. DISCRIMINATION AGAINST THE PRE-W7 GATE ----------------------------
        old = _old_checker(tmp)
        if old is None:
            print("  [BAD] discrimination           cannot read the checker at HEAD")
            return 2
        broken = _scratch(tmp / "discrim")
        _sub(
            broken / "CLAUDE.md",
            "**178 checkouts across 168 object stores**",
            "**179 checkouts across 168 object stores**",
        )
        old_rc, old_out = _run_old(old, broken)
        new_fired = any(c.startswith("W7") for c in _all_codes(broken))
        # The old gate must be GREEN on the very tree the new gate rejects.
        discriminates = old_rc == 0 and new_fired
        ok &= discriminates
        results.append(
            {
                "case": "discrimination-vs-pre-W7-gate",
                "old_gate_exit": old_rc,
                "old_gate_verdict": old_out.strip().splitlines()[-1]
                if old_out.strip()
                else "",
                "new_gate_fires_W7": new_fired,
                "expect": "old gate exit 0 (blind), new gate fires",
                "pass": discriminates,
            }
        )
        print(
            f"  [{'OK ' if discriminates else 'BAD'}] discrimination           "
            f"pre-W7 gate exit={old_rc} ({old_out.strip().splitlines()[-1] if old_out.strip() else '-'})"
            f" | W7 fires={new_fired}"
        )

    payload = {"floor": MIN_COMPARISONS, "cases": results, "all_pass": ok}
    outp = HERE / "w7-redproof.json"
    with open(outp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2)

    if not ok:
        print(f"FAILED:w7-redproof cases={len(results)} not all behaved")
        return 1
    print(f"SUCCESS:w7-redproof cases={len(results)} all behaved")
    return 0


def _bend_json(root: pathlib.Path) -> None:
    """Break the artifact's INTERNAL accounting without touching any prose.

    Reproduces round 4's actual defect shape: a kind split that no longer adds up to the
    population. Nobody added it up then; W7 does.
    """
    p = root / "command-center/ssot/population-classified.json"
    pc = json.loads(p.read_text(encoding="utf-8"))
    pc["kind_arithmetic"]["severed_worktrees"] = 0
    pc["kind_arithmetic"]["sum"] = 177
    pc["kind_arithmetic"]["closes"] = False
    p.write_text(json.dumps(pc, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
