"""CC-0005 independent reviewer measurement - recompute receipt hashes from git blobs.

Run from anywhere; all paths absolute. Reads ONLY (git cat-file, file reads).
"""

import hashlib
import subprocess

R = "C:/Users/Prekzursil/source/agent-skills-toolchain"
BASE = "75da713d3bc3eacb388a49b52ab6af78917509dc"


def blob(rev, path):
    p = subprocess.run(
        ["git", "-C", R, "cat-file", "-p", rev + ":" + path], capture_output=True
    )
    return p.stdout if p.returncode == 0 else None


def info(data):
    if data is None:
        return "MISSING"
    return "sha256=%s bytes=%d crlf=%d" % (
        hashlib.sha256(data).hexdigest(),
        len(data),
        data.count(b"\r\n"),
    )


print("== A. receipt-cited artifact hashes vs blob at unit base commit", BASE)
receipt = {
    "tools/command-center/validate.py": "68f06a32e70c6f17807ef434b05c38a5f7b6e5b41c8d6889d590a739e906b4e0",
    "tools/measure-guard/blobread.py": "a9f41cef63ded7ce58336bb58537e9e6bdfae76e0b7cce4a556b4e4d3671d49f",
    ".gitattributes": "e30af5b07d68121f142008199282f2130ef8c2c62e80bbf1ee733d6deba2e561",
}
for path, want in receipt.items():
    b = blob(BASE, path)
    got = hashlib.sha256(b).hexdigest() if b is not None else "MISSING"
    print(path)
    print("  receipt:", want)
    print("  blob@base:", got, "MATCH" if got == want else "DIFFERS")
    h = blob("HEAD", path)
    wt = open(R + "/" + path, "rb").read()
    print("  blob@HEAD:", info(h))
    print("  worktree :", info(wt))

print()
print("== B. both-states control candidates (worktree vs HEAD blob, same file)")
for path in [
    "command-center/sources/REGISTER.md",
    "scripts/sync_shared_state.ps1",
    "hooks/todo-surfacer/test_marker_discrimination.py",
    "README.md",
    "tools/command-center/seed.py",
    "tools/command-center/tests/test_reach6_blob_provenance.py",
]:
    h = blob("HEAD", path)
    try:
        wt = open(R + "/" + path, "rb").read()
    except OSError:
        print(path, ": worktree MISSING")
        continue
    same = h is not None and hashlib.sha256(h).digest() == hashlib.sha256(wt).digest()
    print(path, "worktree==blob:", same)
    print("  blob@HEAD:", info(h))
    print("  worktree :", info(wt))
    if h is not None and wt is not None and not same:
        ln_h = h.replace(b"\r\n", b"\n")
        ln_w = wt.replace(b"\r\n", b"\n")
        print(
            "  EOL-ONLY (identical after LF-normalisation):",
            ln_h == ln_w,
            "| byte delta:",
            len(wt) - len(h),
            "| line count(blob):",
            h.count(b"\n"),
        )
print("DONE:_measure")
