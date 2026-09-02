"""SYNTHESIS-REVIEW: blob-level ruff CI-parity over the .py blobs committed AFTER 39f30ab2.

The synthesis doc's blob check covered the 21 tracked .py files that landed after 4573b603
*as of 39f30ab2*. Its own commit 1ff5bbf8 then added four more .py blobs (the workflow_lint
fix + tests + their .agents twins) which were lint-checked in the WORKTREE only. Worktree-green
!= blob-green (windows-shell 8b), so this closes that gap.

Method: `git cat-file -p` (never `git archive`), config mirrored, relative path preserved,
plus a deliberately mis-formatted CONTROL that must FIRE.
"""
import json
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUFF = ["uvx", "ruff@0.15.17"]
out = {"method": "git cat-file -p (blob) + ruff.toml mirrored + control"}


def run(args, cwd=None):
    p = subprocess.run(args, cwd=cwd or ROOT, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


# which .py blobs landed after 39f30ab2?
rc, so, se = run(["git", "diff", "--name-only", "--diff-filter=AM", "39f30ab2..HEAD"])
targets = [f for f in so.split() if f.endswith(".py")]
out["targets"] = targets
if not targets:
    out["note"] = "no .py blobs after 39f30ab2"

tmp = tempfile.mkdtemp(prefix="synthrev_blob_")
out["tmp"] = tmp
try:
    # mirror config
    for cfg in ["ruff.toml", "pyproject.toml", ".ruff.toml"]:
        src = os.path.join(ROOT, cfg)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(tmp, cfg))
            out.setdefault("configs_mirrored", []).append(cfg)

    written = []
    for rel in targets:
        rc, blob, se = run(["git", "show", f"HEAD:{rel}"])
        if rc != 0:
            out.setdefault("errors", []).append(f"{rel}: git show rc={rc} {se[:120]}")
            continue
        dest = os.path.join(tmp, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        # binary-exact write: re-read via cat-file to avoid text-mode CRLF injection
        p = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True)
        with open(dest, "wb") as fh:
            fh.write(p.stdout)
        written.append((rel, len(p.stdout), p.stdout.count(b"\r\n")))
    out["written"] = [{"path": r, "bytes": b, "crlf": c} for r, b, c in written]

    # CONTROL: a deliberately mis-formatted file the checker MUST reject
    ctrl = os.path.join(tmp, "_control_badformat.py")
    with open(ctrl, "wb") as fh:
        fh.write(b"import os,sys\ndef  f( a ,b ):\n  x=[1,2,  3]\n  return   a+b\n")

    rc_all, so_all, se_all = run(RUFF + ["check", "."], cwd=tmp)
    out["ruff_check_all"] = {"rc": rc_all, "tail": (so_all or se_all).strip()[-1200:]}
    rc_fmt, so_fmt, se_fmt = run(RUFF + ["format", "--check", "."], cwd=tmp)
    out["ruff_format_all"] = {"rc": rc_fmt, "tail": (so_fmt or se_fmt).strip()[-1200:]}

    # control must fire on its own
    rc_c, so_c, se_c = run(RUFF + ["format", "--check", "_control_badformat.py"], cwd=tmp)
    out["control_format"] = {"rc": rc_c, "fires": rc_c != 0, "tail": (so_c or se_c).strip()[-400:]}
    rc_c2, so_c2, se_c2 = run(RUFF + ["check", "_control_badformat.py"], cwd=tmp)
    out["control_check"] = {"rc": rc_c2, "fires": rc_c2 != 0, "tail": (so_c2 or se_c2).strip()[-400:]}

    # targets alone (control excluded)
    if written:
        rels = [r for r, _, _ in written]
        rc_t, so_t, se_t = run(RUFF + ["check", *rels], cwd=tmp)
        out["ruff_check_targets"] = {"rc": rc_t, "tail": (so_t or se_t).strip()[-800:]}
        rc_tf, so_tf, se_tf = run(RUFF + ["format", "--check", *rels], cwd=tmp)
        out["ruff_format_targets"] = {"rc": rc_tf, "tail": (so_tf or se_tf).strip()[-800:]}

    ok = (
        out.get("control_format", {}).get("fires")
        and out.get("control_check", {}).get("fires")
        and out.get("ruff_check_targets", {}).get("rc") == 0
        and out.get("ruff_format_targets", {}).get("rc") == 0
        and all(w["crlf"] == 0 for w in out["written"])
    )
    out["verdict"] = (
        f"SUCCESS:synthrev-blobruff {len(written)} blob(s) CI-clean; control fired"
        if ok else "FAILED:synthrev-blobruff see fields"
    )
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(json.dumps(out, indent=1))
