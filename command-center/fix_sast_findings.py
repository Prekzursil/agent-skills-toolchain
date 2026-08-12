r"""Clear the 9 tracked SAST findings that turned gate-sast red, without breaking two things.

CONTEXT. Pushing the wave to main ran CI for the first time. gate-lint-format went GREEN (the ruff
sweep worked); gate-sast went RED with 12 findings, 9 of them on tracked files. The charter allows
exactly two remedies -- fix the code, or a reasoned inline `# nosemgrep: <rule-id> -- <reason>`. No
baseline file, no blanket disable.

THE TWO THINGS THIS MUST NOT BREAK:

1. PUBLISHED DIGESTS. _build_adv0022.py:57-58 compute P1_MD5/P2_MD5, which the casualty receipts
   publish and their verification re-derives. Adding usedforsecurity=False must not change the hash.
   PROVEN before editing, not assumed: identical hexdigest across 5 probes (empty, short, the literal
   payload shape, 4 KB, all 256 byte values), with a control showing md5 != sha1 so the equality is a
   reading rather than a tautology. The flag only gates FIPS availability; it does not touch the
   digest.

2. PROVENANCE-LOCKED BYTES. command-center/casualty/probes/adv0022_probe2.py:95 also trips the md5
   rule, and it is one of the five scripts BYTE-IDENTICAL to a dead agent's scratch original. That
   byte-match IS the evidence the work was recovered rather than re-authored. Editing it to satisfy a
   linter would destroy the evidence -- the same conflict the casualty lane hit with ruff, which it
   resolved by asking for a path exclusion in the root config rather than touching the file. Same
   answer here: the rule gets a paths.exclude, the file is not touched.

WHY usedforsecurity=False AND NOT sha256. Every one of these is content fingerprinting -- a digest of
"{method}|{command}", of a probe's raw output, of a file's bytes for a diff. None is a security
boundary. The rule's own message prescribes exactly this remedy for the non-security case. Switching
to sha256 would ALSO change the published digests, which is the one thing condition 1 forbids.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Content-fingerprint md5 call sites. NOT probes/adv0022_probe2.py -- see docstring point 2.
MD5_FILES = [
    "command-center/casualty/_build_adv0021.py",
    "command-center/casualty/_build_adv0022.py",
    "command-center/casualty/_r1_rerun_diff.py",
    "command-center/casualty/_r2_patch_receipts.py",
]
#: The Windows ANSI-enable no-op, present in both dual-write mirrors.
OS_SYSTEM_FILES = [
    ".agents/skills/claude-science-local/cs_monitor.py",
    "skills/claude-science-local/cs_monitor.py",
]
NOSEMGREP = "  # nosemgrep: quality.opengrep.python-os-system -- argument is a compile-time EMPTY literal, so there is no injectable surface; this is the documented Windows trick to enable VT/ANSI processing on a legacy console, not a command invocation"

MD5_CALL = re.compile(r"hashlib\.md5\((?![^()]*usedforsecurity)")


def prove_digest_unchanged() -> bool:
    probes = [b"", b"x", b"method|command", b"a" * 4096, bytes(range(256))]
    same = all(
        hashlib.md5(p).hexdigest() == hashlib.md5(p, usedforsecurity=False).hexdigest()
        for p in probes
    )
    # The control must be able to FAIL, or "same" proves nothing about the comparison working.
    control = hashlib.md5(b"x").hexdigest() != hashlib.sha1(b"x").hexdigest()
    print(
        f"  digest-preservation proof: identical={same} control_discriminates={control}"
    )
    return same and control


def patch_md5(rel: str) -> int:
    p = REPO / rel
    raw = p.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in raw else "\n"
    n = len(MD5_CALL.findall(raw))
    if not n:
        return 0
    out = MD5_CALL.sub("hashlib.md5(", raw)
    # Insert the kwarg at each call's closing paren is fragile; instead rewrite the known shapes.
    out = re.sub(
        r"hashlib\.md5\((?![^()]*usedforsecurity)([^()]*(?:\([^()]*\)[^()]*)*)\)",
        lambda m: f"hashlib.md5({m.group(1)}, usedforsecurity=False)",
        raw,
    )
    changed = sum(1 for a, b in zip(raw.split(eol), out.split(eol)) if a != b)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    return changed


def patch_os_system(rel: str) -> bool:
    p = REPO / rel
    raw = p.read_text(encoding="utf-8", newline="")
    if "nosemgrep" in raw:
        return False
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)
    hit = [i for i, ln in enumerate(lines) if 'os.system("")' in ln]
    if len(hit) != 1:
        print(f'  FAILED: {rel} has {len(hit)} os.system("") lines, expected 1')
        return False
    lines[hit[0]] = lines[hit[0]].rstrip() + NOSEMGREP
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(eol.join(lines))
    return True


def main() -> int:
    if not prove_digest_unchanged():
        print(
            "FAILED:sast-fix digest-preservation proof did not hold -- refusing to patch"
        )
        return 1

    total = 0
    for rel in MD5_FILES:
        n = patch_md5(rel)
        total += n
        print(f"  md5 usedforsecurity=False: {n} line(s) in {rel}")
    for rel in OS_SYSTEM_FILES:
        print(f"  nosemgrep on os.system: {patch_os_system(rel)}  {rel}")

    # Dual-write parity: the two cs_monitor mirrors must stay byte-identical.
    a = (REPO / OS_SYSTEM_FILES[0]).read_bytes()
    b = (REPO / OS_SYSTEM_FILES[1]).read_bytes()
    print(f"  cs_monitor mirrors byte-identical after edit: {a == b}")
    if a != b:
        print("FAILED:sast-fix dual-write mirrors diverged")
        return 1

    # The locked probe must be untouched.
    locked = REPO / "command-center/casualty/probes/adv0022_probe2.py"
    st = subprocess.run(
        ["git", "diff", "--name-only", "--", str(locked)],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    if st.stdout.strip():
        print("FAILED:sast-fix the provenance-locked probe was modified")
        return 1
    print("  provenance-locked probe untouched: True")
    print(f"\nSUCCESS:fix-sast {total} md5 call site(s) patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
