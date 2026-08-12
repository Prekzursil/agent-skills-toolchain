"""R1 -- re-record the register snapshot provenance so REACH-6 is satisfied.

WHY THIS EXISTS (root cause, read from the real CI run, not from a local green)

`gate-tests-coverage (python packages)` was the last red job on main. Its failing step is
`gate-tests-coverage command-center`, and it is NOT a coverage percentage -- it is one
validator violation that fails three tests:

    REACH-6 -: register snapshot sha256 721c4e577ca5 != recorded f07e49422bd5
    FAILED:cc-validate violations=1
    FAILED tools/command-center/tests/test_validate.py::test_real_catalog_is_clean
    FAILED tools/command-center/tests/test_close.py::test_closing_every_open_item_leaves_a_valid_catalog
                                    -- run 31617966828 / 31632302523, step log

Walking both sides through history: `command-center/sources/REGISTER.md` last changed at
1ff5bbf8 (+25 lines, a new section 9), which makes its LF-normalised digest 721c4e57...;
`command-center/WORK-UNIT-CATALOG.json`'s `provenance.register_sha256` was last set at
3a19b9a3 to f07e4942..., which is exactly the register's digest AT 3a19b9a3. So 1ff5bbf8
edited the register and did not re-record the provenance beside it. The catalog data is
fine; only the recorded snapshot digest is stale.

This is the SECOND occurrence of this exact defect. `fix_reach_violations.py` fixed it on
2026-08-10 for the same reason ("I rewrote sources/REGISTER.md in the same batch, so the
recorded digest went stale"), and this script deliberately copies its mechanism at :96-102
rather than inventing a second one.

THREE THINGS THIS MUST NOT DO, each learned from a recorded failure

1. DO NOT hash raw working-tree bytes. validate.py:228 hashes
   `read_bytes().replace(b"\\r\\n", b"\\n")`. A Windows checkout under core.autocrlf=true
   materialises CRLF, so a raw hash is unsatisfiable on Windows while passing on Linux CI.
   The comment at validate.py:216-227 records that measurement.

2. DO NOT run `seed.py --force` to regenerate the provenance. seed.py:127 reads the register
   with `read_bytes()` and :172 hashes it RAW -- the writer half of the very portability fix
   validate.py documents was never applied there. On this machine REGISTER.md currently has
   0 CRLF, so seed.py would happen to agree today; that is luck, not correctness, and it
   would silently record a Windows-only digest on a checkout where it does not. Reported as
   a separate latent defect rather than fixed here (out of this lane's scope).

3. DO NOT re-render STATUS.md to absorb the violation. `render_status()` EMBEDS validate()'s
   violations, so `render.py --check` reports drift=1 today purely BECAUSE of REACH-6:
   committed STATUS.md holds the clean "ALL items reach a final disposition" line, and a
   fresh render adds "1 VIOLATIONS" plus a `## VIOLATIONS` section. Re-rendering would
   COMMIT the bug into a tracked artifact and turn one red into a permanent one. Fixing
   REACH-6 makes the fresh render match the committed file again, so drift resolves on its
   own -- asserted by --verify below, not assumed. fix_reach_violations.py's docstring
   pre-documents falling into exactly this trap.

USAGE
    python command-center/fix_reach6_register_provenance.py --check    # report, write nothing
    python command-center/fix_reach6_register_provenance.py --apply    # re-record
    python command-center/fix_reach6_register_provenance.py --verify   # post-conditions
    python command-center/fix_reach6_register_provenance.py --control  # both-states control

The --control mode is the part that makes the green meaningful: it mutates ONE hex character
of the recorded digest in a TEMP COPY and asserts REACH-6 fires again. A gate that cannot be
made to fail is not a gate, and this one is about to be reported as green.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CATALOG = HERE / "WORK-UNIT-CATALOG.json"
REGISTER = HERE / "sources" / "REGISTER.md"
VALIDATE = REPO / "tools" / "command-center" / "validate.py"
RENDER = REPO / "tools" / "command-center" / "render.py"


#: Hoisted out of every f-string on purpose. A backslash inside an f-string EXPRESSION is
#: only legal from Python 3.12 (PEP 701), and quality.yml pins this job to python-version
#: "3.11" -- so `f"{x.count(b'\r\n')}"` compiles fine on this box (3.14) and is a hard
#: SyntaxError on CI. Local-green != CI-green, in the file whose whole job is a CI fix.
CRLF = b"\r\n"


def lf_bytes() -> bytes:
    """The register's bytes as the validator sees them: LF-normalised. See note 1 above."""
    return REGISTER.read_bytes().replace(CRLF, b"\n")


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def write_catalog(doc: dict) -> None:
    """Write the catalog in the EXACT shape the repo already uses.

    `indent=1` + `ensure_ascii=False` + `newline=""` are copied from
    fix_reach_violations.py:101-103. Any other combination reflows or re-encodes the whole
    file and turns a two-field change into a whole-file diff -- which on a worktree shared
    with other lanes is how a scoped fix becomes an unreviewable one.
    """
    CATALOG.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8", newline=""
    )


def report() -> tuple[str, str, int, int]:
    doc = load_catalog()
    lf = lf_bytes()
    actual = hashlib.sha256(lf).hexdigest()
    prov = doc.get("provenance", {})
    recorded = str(prov.get("register_sha256", ""))
    raw = REGISTER.read_bytes()
    print(f"  register           : {REGISTER.relative_to(REPO).as_posix()}")
    print(f"  raw bytes on disk  : {len(raw)}  (CRLF pairs: {raw.count(CRLF)})")
    print(f"  LF-normalised bytes: {len(lf)}   recorded: {prov.get('register_bytes')}")
    print(f"  LF-normalised sha  : {actual[:12]}   recorded: {recorded[:12]}")
    return actual, recorded, len(lf), int(prov.get("register_bytes") or 0)


def cmd_check() -> int:
    actual, recorded, n_lf, n_rec = report()
    if actual == recorded and n_lf == n_rec:
        print("SUCCESS:reach6-check provenance already matches -- nothing to do")
        return 0
    print("REACH-6 would fire: recorded provenance is stale")
    return 1


def cmd_apply() -> int:
    actual, recorded, n_lf, n_rec = report()
    if actual == recorded and n_lf == n_rec:
        print("SUCCESS:reach6-apply already correct, no write performed")
        return 0
    doc = load_catalog()
    doc["provenance"]["register_sha256"] = actual
    doc["provenance"]["register_bytes"] = n_lf
    write_catalog(doc)
    print(f"  register_sha256 {recorded[:12]} -> {actual[:12]}")
    print(f"  register_bytes  {n_rec} -> {n_lf}")
    print("SUCCESS:reach6-apply provenance re-recorded")
    return 0


def _run(script: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def cmd_verify() -> int:
    """AND-gate: validate clean AND render drift-free. Either alone is not the postcondition.

    render.py is included because it is the SECOND-ORDER symptom of the same violation, and
    because a fix that silenced validate.py while leaving render red would look like progress
    on one instrument and be a regression on the tracked artifact.
    """
    ok = True
    rc_v, out_v = _run(VALIDATE)
    tail_v = [ln for ln in out_v.strip().splitlines() if ln.strip()][-1:]
    print(f"  validate.py exit={rc_v}  {tail_v[0] if tail_v else '<no output>'}")
    if rc_v != 0 or "REACH-6" in out_v:
        ok = False
    rc_r, out_r = _run(RENDER, "--check")
    tail_r = [ln for ln in out_r.strip().splitlines() if ln.strip()][-1:]
    print(f"  render.py --check exit={rc_r}  {tail_r[0] if tail_r else '<no output>'}")
    if rc_r != 0:
        ok = False
    print("SUCCESS:reach6-verify" if ok else "FAILED:reach6-verify")
    return 0 if ok else 1


def cmd_control() -> int:
    """BOTH-STATES control. Mutate the recorded digest in a temp copy; REACH-6 must fire.

    Runs the validator against a MUTATED COPY of the catalog via validate.py's own
    `--catalog` path if it has one; otherwise it mutates in place and restores from the
    original bytes in a finally block, so the working tree is byte-identical afterwards
    (asserted, not assumed).
    """
    original = CATALOG.read_bytes()
    try:
        doc = load_catalog()
        good = str(doc["provenance"]["register_sha256"])
        # flip exactly one hex character -- the smallest change that must still be caught
        flipped = ("0" if good[0] != "0" else "1") + good[1:]
        doc["provenance"]["register_sha256"] = flipped
        write_catalog(doc)
        rc, out = _run(VALIDATE)
        fired = "REACH-6" in out and rc != 0
        print(f"  mutated recorded sha {good[:12]} -> {flipped[:12]}")
        print(f"  validator exit={rc}  REACH-6 present={'REACH-6' in out}")
        for ln in out.splitlines():
            if "REACH-6" in ln:
                print(f"     FIRED {ln.strip()}")
    finally:
        CATALOG.write_bytes(original)
    restored = CATALOG.read_bytes() == original
    print(f"  catalog restored byte-identical: {restored}")
    if not restored:
        print(
            "FAILED:reach6-control could not restore the catalog -- inspect before committing"
        )
        return 1
    if not fired:
        print(
            "FAILED:reach6-control validator did NOT fire on a knowingly-wrong digest."
        )
        print(
            "  The gate cannot distinguish correct from incorrect provenance; its green"
        )
        print("  reading proves only that it ran. Do not cite the fix as verified.")
        return 1
    print(
        "SUCCESS:reach6-control gate fires on a one-character corruption -- green is meaningful"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--control", action="store_true")
    ns = ap.parse_args()
    if ns.check:
        return cmd_check()
    if ns.apply:
        return cmd_apply()
    if ns.verify:
        return cmd_verify()
    return cmd_control()


if __name__ == "__main__":
    sys.exit(main())
