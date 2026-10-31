#!/usr/bin/env python3
"""probe2 for TST-0031: the three-route byte/CRLF table, re-run LIVE.

Throwaway fixture repo (LF blob, CRLF worktree via gitattributes eol=crlf):
  1. git archive | tar -x            -> measured bytes + CRLF count
  2. git cat-file -p HEAD:sample.txt -> measured bytes + CRLF count (true blob)
  3. git show HEAD:sample.txt        -> measured bytes + CRLF count
Asserts cat-file equals show, the blob is the LF form, LF normalisation makes
archive and blob identical, and the live gate + lint hold both states.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
UID = "TST-0031"
C10 = chr(10)
C13 = chr(13)
SAMPLE = ("The quick brown fox jumps over the lazy dog." + C10) * 10


def crlf_count(data: bytes) -> int:
    return data.count((C13 + C10).encode("utf-8"))


def main() -> int:
    checks: dict[str, object] = {}
    table: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "fixture-repo"
        repo.mkdir()
        crlf_sample = SAMPLE.replace(C10, C13 + C10).encode("utf-8")
        (repo / "sample.txt").write_bytes(crlf_sample)
        (repo / ".gitattributes").write_bytes(("* text eol=crlf" + C10).encode("utf-8"))

        def git(*args, inp=None):
            return subprocess.run(["git", *args], capture_output=True, cwd=str(repo), input=inp)

        assert git("init", "-q", ".").returncode == 0
        git("add", ".")
        assert git("-c", "user.email=p@p", "-c", "user.name=p", "commit", "-qm", "fixture").returncode == 0

        arch = git("archive", "HEAD")
        archive_bytes = None
        if arch.returncode == 0:
            with tarfile.open(fileobj=io.BytesIO(arch.stdout)) as tf:
                m = tf.extractfile("sample.txt")
                archive_bytes = m.read() if m else None
        catf = git("cat-file", "-p", "HEAD:sample.txt")
        blob = catf.stdout
        show = git("show", "HEAD:sample.txt")
        show_b = show.stdout

        lf = C10.encode()
        crlf = (C13 + C10).encode()
        checks["catfile_rc0"] = catf.returncode == 0
        checks["catfile_equals_show"] = blob == show_b
        checks["blob_is_lf"] = crlf_count(blob) == 0
        checks["archive_extracts"] = archive_bytes is not None
        checks["identical_after_lf_normalisation"] = (
            archive_bytes is not None
            and archive_bytes.replace(crlf, lf) == blob.replace(crlf, lf)
        )
        archive_crlf = crlf_count(archive_bytes) if archive_bytes else None
        table["git archive | tar -x"] = {"bytes": len(archive_bytes) if archive_bytes else None, "crlf": archive_crlf}
        table["git cat-file -p"] = {"bytes": len(blob), "crlf": crlf_count(blob), "sha256": hashlib.sha256(blob).hexdigest()}
        table["git show HEAD:path"] = {"bytes": len(show_b), "crlf": crlf_count(show_b)}

        gate = subprocess.run(
            [sys.executable, "-I", "-B", str(HERE / "blob_gate.py"),
             "--repo", str(repo), "--rev", "HEAD", "--path", "sample.txt"],
            capture_output=True, text=True, cwd=str(repo),
        )
        checks["blob_gate_rc0"] = gate.returncode == 0
        rep = json.loads(gate.stdout or "{}")
        checks["gate_hashes_blob_not_worktree"] = rep.get("blob_sha256") == hashlib.sha256(blob).hexdigest()

        bad = HERE / "fixture_bad_recipe.py"
        bad.write_text("subprocess.run('git archive HEAD | tar -x -C out', shell=True)" + C10,
                       encoding="utf-8", newline=C10)
        good = HERE / "fixture_good_recipe.py"
        good.write_text("subprocess.run(['git', 'cat-file', '-p', 'HEAD:sample.txt'])" + C10,
                        encoding="utf-8", newline=C10)
        lint_bad = subprocess.run([sys.executable, "-I", "-B", str(HERE / "archive_lint.py"), str(bad)],
                                  capture_output=True, text=True)
        lint_good = subprocess.run([sys.executable, "-I", "-B", str(HERE / "archive_lint.py"), str(good)],
                                   capture_output=True, text=True)
        checks["lint_fires_on_archive_recipe"] = lint_bad.returncode == 1 and "cat-file" in lint_bad.stdout
        checks["lint_silent_on_catfile_recipe"] = lint_good.returncode == 0
        bad.unlink(missing_ok=True)
        good.unlink(missing_ok=True)
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe2-three-route-live", "pass": ok, "table": table, "checks": checks}))
    if ok:
        print(f"SUCCESS:{UID}-probe2 live table: cat-file==show ({len(blob)}B, 0 CRLF); archive differs only in EOL, LF-normalised identical; gate hashes the blob; lint fires on git archive, silent on cat-file")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
