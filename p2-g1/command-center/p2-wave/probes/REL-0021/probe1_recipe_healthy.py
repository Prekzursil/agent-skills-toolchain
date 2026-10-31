#!/usr/bin/env python3
# REL-0021 probe1: blob recipe evidence + healthy PROMOTE (resume 2026-10-25).
# Seeds a fixture git repo whose known.txt blob is pure LF, then MEASURES the
# recipe delta the receipt records: git cat-file -p returns the blob with 0
# CRLF (23 bytes) while the rejected git archive export carries 4 CRLF (27
# bytes). Builds a healthy three-copy fixture (git == package == deployed)
# and requires verdict PROMOTE with identical=3.
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("rel0021_parity", HERE / "parity.py")
P = importlib.util.module_from_spec(spec)
sys.modules["rel0021_parity"] = P
spec.loader.exec_module(P)
CONTENT = b"alpha\nbeta\ngamma\ndelta\n"  # 23 bytes, 4 lines, LF only
SECOND = b"second file" + chr(10).encode()


def fail(msg):
    print("FAILED:REL-0021-probe1 " + str(msg))
    return 1


def seed_repo(repo: Path, extra_attrs=""):
    repo.mkdir(parents=True)
    r = lambda *a, **k: subprocess.run(a, cwd=str(repo), capture_output=True, text=True, timeout=120, check=True, **k)
    subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True, timeout=120)
    subprocess.run(["git", "config", "user.email", "rel0021@fixture"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "rel0021-fixture"], cwd=str(repo), capture_output=True)
    (repo / ".gitattributes").write_text("shipped/known.txt text eol=crlf\n" + extra_attrs,
                                         encoding="utf-8", newline="\n")
    shipped = repo / "shipped"
    shipped.mkdir()
    (shipped / "known.txt").write_bytes(CONTENT)
    (shipped / "second.txt").write_bytes(SECOND)
    (repo / "README.md").write_text("fixture\n", encoding="utf-8", newline="\n")
    r("git", "add", "-A")
    r("git", "commit", "-q", "-m", "seed")


def build_case(tmp, name, deployed_mutator=None, pkg_mutator=None):
    root = tmp / name
    repo = root / "repo"
    seed_repo(repo)
    pkg = root / "package.zip"
    with zipfile.ZipFile(pkg, "w") as z:
        z.writestr("shipped/known.txt", CONTENT)
        z.writestr("shipped/second.txt", "second file" + chr(10))
        z.writestr("README.md", "fixture\n")
        if pkg_mutator:
            pkg_mutator(z)
    dep = root / "deployed"
    (dep / "shipped").mkdir(parents=True)
    (dep / "shipped" / "known.txt").write_bytes(CONTENT)
    (dep / "README.md").write_bytes(b"fixture" + chr(10).encode())
    (dep / "shipped" / "second.txt").write_bytes(b"second file" + chr(10).encode())
    if deployed_mutator:
        deployed_mutator(dep)
    return repo, pkg, dep


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rel0021-p1-"))
    try:
        # recipe evidence: cat-file vs archive
        repo, _, _ = build_case(tmp, "recipe")
        cat = P.git_bytes(repo, "HEAD:shipped/known.txt")
        arch = P.git_archive_bytes(repo, "HEAD:shipped/known.txt")
        cat_crlf, arch_crlf = P.crlf_count(cat), P.crlf_count(arch)
        print("recipe: cat-file bytes=%d CRLF=%d | archive bytes=%d CRLF=%d | difference=%d"
              % (len(cat), cat_crlf, len(arch), arch_crlf, arch_crlf - cat_crlf))
        if len(cat) != 23 or cat_crlf != 0:
            return fail("cat-file-not-blob:" + str(len(cat)) + "/" + str(cat_crlf))
        if arch_crlf - cat_crlf != 4 or len(arch) != 27:
            return fail("archive-delta-not-measured:" + str(arch_crlf) + "/" + str(len(arch)))
        # healthy three-copy fixture
        repo, pkg, dep = build_case(tmp, "healthy")
        rep = P.three_way_report(repo, pkg, dep, ["shipped/known.txt", "shipped/second.txt",
                                                  "README.md"])
        print("healthy four_way=" + json.dumps(rep["four_way"]) + " verdict=" + rep["verdict"])
        if rep["verdict"] != "PROMOTE" or rep["four_way"]["identical"] != 3:
            return fail("healthy-verdict:" + rep["verdict"])
        identical = [f for f in rep["files"] if f["class"] == "identical"]
        for f in identical:
            if not (f["git_lf_sha256"] == f["package_lf_sha256"] == f["deployed_lf_sha256"]):
                return fail("identical-sha-drift:" + f["path"])
        rec = json.loads((REPO / "command-center/receipts/REL-0021.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        if "SUCCESS:REL-0021" not in json.dumps(rec):
            return fail("sentinel-absent")
        br = rec.get("blob_recipe") or {}
        if br.get("chosen_recipe") != "git cat-file -p" or br.get("crlf_count_difference") != 4:
            return fail("receipt-recipe-drift")
        if "git cat-file" not in str(br.get("retrieval_command")):
            return fail("receipt-recipe-command-drift")
        print("receipt blob_recipe: " + str(br.get("retrieval_command"))
              + " (rejected: " + str(br.get("rejected_alternative"))[:60] + ")")
        print("SUCCESS:REL-0021-probe1 recipe-and-healthy")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
