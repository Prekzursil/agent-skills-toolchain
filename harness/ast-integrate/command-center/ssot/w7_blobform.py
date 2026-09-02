"""Does W7 behave on the bytes CI actually checks out?

This working tree is CRLF; the Linux runner checks out the LF blob. A gate verified only
against the working copy has been verified against the wrong bytes -- the estate has a
measured case where a formatter said "already formatted" locally and "would reformat" in CI
for the same commit. So the data files here come from `git show <rev>:<path>`, which returns
the stored blob (`git archive` is the one that applies EOL conversion and hands back CRLF on
Windows -- do not substitute it).

The checker module itself is taken from the WORKING COPY on purpose: the point is to run the
code under review against the bytes CI will feed it.

Both states, as always: green on the LF tree proves nothing until the same LF tree, with one
number perturbed, goes red.

Exit 0 = behaved; 1 = did not; 2 = could not set up.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import ssot_wiring_check as wiring  # noqa: E402

DATA_PATHS = (
    "CLAUDE.md",
    "docs/ssot/SSOT-CLONE-INVENTORY.md",
    "command-center/ssot/ssot_drift_gate.py",
    "command-center/ssot/apply_severed_resolution.py",
    "command-center/ssot/redproof_severed.py",
    "command-center/ssot/population-classified.json",
    ".github/workflows/skill-dual-write.yml",
)
# W3 resolves paths named in the block, and the block names the checker. Supplied from the
# working copy because it is the code under review.
WORKING_COPY_PATHS = ("command-center/ssot/ssot_wiring_check.py",)


def _blob(rev: str, rel: str) -> bytes | None:
    p = subprocess.run(
        ["git", "show", f"{rev}:{rel}"], cwd=ROOT, capture_output=True, timeout=120
    )
    return p.stdout if p.returncode == 0 else None


def _build(rev: str, dest: pathlib.Path) -> tuple[pathlib.Path, int, int]:
    root = dest / "repo"
    total_crlf = 0
    written = 0
    for rel in DATA_PATHS:
        data = _blob(rev, rel)
        if data is None:
            raise SystemExit(f"cannot read {rev}:{rel}")
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)  # raw bytes: no newline translation on the way in
        total_crlf += data.count(b"\r\n")
        written += 1
    for rel in WORKING_COPY_PATHS:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((ROOT / rel).read_bytes())
        written += 1
    return root, total_crlf, written


def main() -> int:
    rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    ok = True
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        root, crlf, written = _build(rev, tmp)

        # CONTROL 1: we really are looking at LF bytes. If this were non-zero the whole
        # probe would be re-measuring the working tree under another name.
        lf_ok = crlf == 0 and written == len(DATA_PATHS) + len(WORKING_COPY_PATHS)
        ok &= lf_ok
        print(
            f"  [{'OK ' if lf_ok else 'BAD'}] blob-form control       "
            f"files={written} CRLF={crlf} (expect 0)"
        )

        # CONTROL 2: the gate is green over those bytes.
        codes = {c for c, _ in wiring.run(root)}
        green = codes == set()
        ok &= green
        print(
            f"  [{'OK ' if green else 'BAD'}] gate on LF blobs        "
            f"codes={sorted(codes) or '[] (all wires intact)'}"
        )

        # CONTROL 3: and it is not inert on them. Same LF tree, one number moved.
        cm = root / "CLAUDE.md"
        text = cm.read_bytes().decode("utf-8")
        anchor = "**178 checkouts across 168 object stores**"
        if anchor not in text:
            print("  [BAD] inertness control        anchor absent in the LF CLAUDE.md")
            return 2
        cm.write_bytes(
            text.replace(
                anchor, "**179 checkouts across 168 object stores**", 1
            ).encode("utf-8")
        )
        after = {c for c, _ in wiring.run(root)}
        fires = after == {"W7-count-drift"}
        ok &= fires
        print(
            f"  [{'OK ' if fires else 'BAD'}] inertness control       "
            f"perturbed LF tree -> codes={sorted(after)}"
        )

    payload = {
        "rev": rev,
        "files": written,
        "crlf_in_extracted_blobs": crlf,
        "green_on_lf": green,
        "fires_on_perturbed_lf": fires,
        "all_pass": ok,
    }
    with open(HERE / "w7-blobform.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2)

    if not ok:
        print("FAILED:w7-blobform the gate does not behave on the bytes CI checks out")
        return 1
    print(f"SUCCESS:w7-blobform rev={rev} LF-clean green-then-red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
