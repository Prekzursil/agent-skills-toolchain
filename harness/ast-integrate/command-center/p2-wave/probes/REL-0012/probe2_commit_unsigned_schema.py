#!/usr/bin/env python3
"""Probe 2: independent commit cross-check, UNSIGNED locus, schema garbage."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    OUTPUT_REL,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)
from engine import run_verify, tamper_one_byte  # noqa: E402
from schema_local import domain, iter_errors, validate  # noqa: E402

GEN = HERE / "generated"
UNSIGNED_RE = re.compile(r"^UNSIGNED\b")
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def git_rev_parse(tree: Path) -> str:
    p = subprocess.run(
        ["git", "-C", str(tree), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"git rev-parse failed: {p.stderr or p.stdout}")
    return p.stdout.strip()


def unsigned_locus(path: Path) -> tuple[int, str]:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if UNSIGNED_RE.match(line.strip()):
            return i, line.strip()
    raise RuntimeError(f"UNSIGNED not found by probe2 scanner in {path}")


def main() -> int:
    art = REPO / OUTPUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:REL-0012-probe2 receipt missing")
        return 1
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:REL-0012-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:REL-0012-probe2 self-declared", doc.get("state"))
        return 1

    validate(doc, SCHEMA_REL)
    payload = domain(doc)
    rejected = 0
    for probe in GARBAGE:
        errs = iter_errors(probe, SCHEMA_REL)
        if not errs:
            print("FAILED:REL-0012-probe2 schema accepted garbage", probe)
            return 1
        rejected += 1
    if rejected != 3:
        print("FAILED:REL-0012-probe2 garbage reject count", rejected)
        return 1

    artifact = GEN / "artifact.zip"
    provenance = GEN / "provenance.json"
    tree = GEN / "build-tree"
    notes = GEN / "RELEASE-NOTES.md"
    for p in (artifact, provenance, tree, notes):
        if p.is_file() or p.is_dir():
            continue
        print("FAILED:REL-0012-probe2 missing generated", p)
        return 1

    live_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    want_sha = (payload.get("provenance") or doc.get("provenance") or {}).get(
        "subject_sha256"
    )
    if live_sha != want_sha:
        print("FAILED:REL-0012-probe2 subject sha mismatch", live_sha, want_sha)
        return 1
    stmt = json.loads(provenance.read_text(encoding="utf-8"))
    subj = ((stmt.get("subject") or [{}])[0].get("digest") or {}).get("sha256")
    if subj != live_sha:
        print("FAILED:REL-0012-probe2 provenance subject != live hashlib", subj, live_sha)
        return 1

    git_commit = git_rev_parse(tree)
    prov_commit = None
    for dep in (stmt.get("predicate") or {}).get("buildDefinition", {}).get(
        "resolvedDependencies", []
    ):
        digest = (dep or {}).get("digest") or {}
        if "gitCommit" in digest:
            prov_commit = digest["gitCommit"]
            break
    if not prov_commit or prov_commit != git_commit:
        print("FAILED:REL-0012-probe2 commit mismatch", prov_commit, git_commit)
        return 1
    source_commit = payload.get("source_commit") or doc.get("source_commit")
    if source_commit != git_commit:
        print("FAILED:REL-0012-probe2 receipt source_commit != git", source_commit)
        return 1

    line, u_text = unsigned_locus(notes)
    rec_u = payload.get("unsigned_declaration") or doc.get("unsigned_declaration") or {}
    if rec_u.get("line") != line:
        print("FAILED:REL-0012-probe2 UNSIGNED line mismatch", rec_u.get("line"), line)
        return 1
    if not str(rec_u.get("text") or "").startswith("UNSIGNED"):
        print("FAILED:REL-0012-probe2 receipt UNSIGNED text missing")
        return 1
    fixture_notes = HERE / "fixtures" / "RELEASE-NOTES.md"
    f_line, f_text = unsigned_locus(fixture_notes)
    if f_line != line or f_text != u_text:
        print("FAILED:REL-0012-probe2 fixture vs generated UNSIGNED drifted")
        return 1

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in ("T-commit-equals-git", "T-unsigned-declaration"):
        row = tests.get(tid)
        if not row or row.get("result") != "PASS":
            print(f"FAILED:REL-0012-probe2 test {tid} not PASS")
            return 1

    with tempfile.TemporaryDirectory(prefix="rel0012-p2-") as tmp_s:
        tmp = Path(tmp_s)
        mutant_prov = tmp / "provenance.bad-commit.json"
        mutant = json.loads(provenance.read_text(encoding="utf-8"))
        deps = mutant["predicate"]["buildDefinition"]["resolvedDependencies"]
        flipped = False
        for dep in deps:
            if "gitCommit" in (dep.get("digest") or {}):
                dep["digest"]["gitCommit"] = "0" * 40
                flipped = True
                break
        if not flipped:
            print("FAILED:REL-0012-probe2 could not mutate gitCommit")
            return 1
        mutant_prov.write_text(json.dumps(mutant), encoding="utf-8")
        m_code, _, m_out = run_verify(artifact, mutant_prov, tree, notes)
        if m_code == 0 or "COMMIT-MISMATCH" not in m_out:
            print("FAILED:REL-0012-probe2 mutated commit did not fail")
            print(m_out)
            return 1

        stripped = tmp / "RELEASE-NOTES.stripped.md"
        body = notes.read_text(encoding="utf-8")
        stripped.write_text(
            "\n".join(
                ln for ln in body.splitlines() if not UNSIGNED_RE.match(ln.strip())
            )
            + "\n",
            encoding="utf-8",
        )
        s_code, _, s_out = run_verify(artifact, provenance, tree, stripped)
        if s_code == 0 or "UNSIGNED-ABSENT" not in s_out:
            print("FAILED:REL-0012-probe2 stripped UNSIGNED did not fail")
            print(s_out)
            return 1

        # Independent tamper copy (does not use probe1's tmp) — both-states still hold.
        tampered = tmp / "independent.tampered.zip"
        tamper_one_byte(artifact, tampered)
        t_code, _, t_out = run_verify(tampered, provenance, tree, notes)
        if t_code == 0 or "DIGEST-MISMATCH" not in t_out:
            print("FAILED:REL-0012-probe2 independent tamper did not fail")
            print(t_out)
            return 1

        shutil.rmtree(tmp / "unused", ignore_errors=True)

    kp = payload.get("key_policy") or doc.get("key_policy") or {}
    if any(kp.get(k) for k in ("created_key", "used_key", "rotated_key", "printed_key")):
        print("FAILED:REL-0012-probe2 key_policy claims a key was touched")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-commit-unsigned-schema",
                "live_sha256": live_sha,
                "git_rev_parse": git_commit,
                "unsigned_line": line,
                "schema_garbage_rejected": rejected,
                "mutant_commit_fails": True,
                "stripped_unsigned_fails": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:REL-0012-probe2 independent recount schema-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
