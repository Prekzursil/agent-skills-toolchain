"""Check the AUDIT's two load-bearing executions, by a different route than the audit used.

(1) The audit exec'd the pre-fix blob to reproduce the defect. Re-do it, but read the blob with
    `git cat-file -p` via ls-files (the floor's blob recipe) rather than `git show`, so the
    measurement does not share the audit's plumbing.
(2) Three-route EOL check on a file NEITHER the builder nor the audit used, to test the standing
    claim that `git archive` returns CRLF while `git show` and `git cat-file -p` return the blob.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")


def run(args, **kw):
    return subprocess.run(args, cwd=REPO, capture_output=True, **kw)


print("--- 1. reproduce the defect against the REAL pre-fix blob, read via ls-files+cat-file ---")
rel = "command-center/ready_units.py"
ls = run(["git", "ls-files", "-s", "--", rel], text=True).stdout.split()
print(f"  worktree blob (HEAD index) sha: {ls[1][:12] if len(ls) > 1 else '?'}")
old_sha = run(["git", "rev-parse", f"b613c827^:{rel}"], text=True).stdout.strip()
new_sha = run(["git", "rev-parse", f"b613c827:{rel}"], text=True).stdout.strip()
old_src = run(["git", "cat-file", "-p", old_sha]).stdout
new_src = run(["git", "cat-file", "-p", new_sha]).stdout
print(f"  pre-fix blob {old_sha[:12]}  {len(old_src)} B  CR={old_src.count(b'CR'.replace(b'CR', bytes([13])))}")
print(f"  post-fix blob {new_sha[:12]} {len(new_src)} B  CR={new_src.count(bytes([13]))}")
print(f"  'contract_discriminates' in pre-fix : {b'contract_discriminates' in old_src}")
print(f"  'contract_discriminates' in post-fix: {b'contract_discriminates' in new_src}")

# exec the pre-fix module with __file__ pinned so REPO resolves correctly
tmpdir = Path(tempfile.mkdtemp(prefix="av2_"))
oldp = REPO / "command-center" / "_av2_prefix_ready_units.py"
oldp.write_bytes(old_src)
try:
    import importlib.util

    spec = importlib.util.spec_from_file_location("ru_old", oldp)
    ru_old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ru_old)
    spec2 = importlib.util.spec_from_file_location("ru_new", REPO / "command-center/ready_units.py")
    ru_new = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(ru_new)
    res_old = ru_old._load_resolver()
    res_new = ru_new._load_resolver()

    fixture = "command-center/p2-wave/fixtures/ready-units/IMP-0433-state-SUCCESS-mutant.json"
    catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = catalog["work_units"] if isinstance(catalog, dict) else catalog
    real = next(x for x in units if x["id"] == "IMP-0433")
    mut = dict(real, output_path=fixture)

    print("\n  unit/document                 OLD predicate            NEW predicate")
    for label, u in [("IMP-0433 mutant (state=SUCCESS)", mut), ("IMP-0433 real (state=BLOCKED)", real)]:
        o = ru_old.artifact_delivered(u, res_old)
        n = ru_new.artifact_delivered(u, res_new)
        print(f"  {label:31s} {str(o[0]):5s} {o[1][:20]:22s} {str(n[0]):5s} {n[1][:34]}")

    # fixture-not-inert control: exactly one field differs from the real receipt
    a = json.loads((REPO / real["output_path"]).read_text(encoding="utf-8"))
    b = json.loads((REPO / fixture).read_text(encoding="utf-8"))
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    print(f"  fixture-vs-source differing fields = {diff} (source state={a.get('state')!r})")
finally:
    oldp.unlink(missing_ok=True)

print("\n--- 2. three-route EOL on a file neither report used ---")
for rel in ["command-center/WORK-UNIT-CATALOG.json", "command-center/p2-wave/_av_probe1.py"]:
    sha = run(["git", "rev-parse", f"HEAD:{rel}"], text=True).stdout.strip()
    cat = run(["git", "cat-file", "-p", sha]).stdout
    show = run(["git", "show", f"HEAD:{rel}"]).stdout
    tar = tmpdir / "a.tar"
    with open(tar, "wb") as fh:
        fh.write(run(["git", "archive", "HEAD", "--", rel]).stdout)
    import tarfile

    with tarfile.open(tar) as tf:
        arch = tf.extractfile(tf.getnames()[0]).read()
    norm = lambda b: b.replace(b"\r\n", b"\n")  # noqa: E731
    print(
        f"  {rel.split('/')[-1]:28s} archive={len(arch):7d}B/CR{arch.count(bytes([13])):4d} "
        f"cat-file={len(cat):7d}B/CR{cat.count(bytes([13])):3d} "
        f"show={len(show):7d}B/CR{show.count(bytes([13])):3d} "
        f"LF-identical={norm(arch) == norm(cat) == norm(show)}"
    )
