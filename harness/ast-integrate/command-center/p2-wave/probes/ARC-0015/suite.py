#!/usr/bin/env python3
"""Executable A2 determinism + CRLF-stable round-trip suite (ARC-0015).

Uses the live ARC-0010 generator. Does not rebuild A2.
Evidence for the CRLF dimension is git cat-file -p versus working-tree bytes.
git archive is never invoked.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GEN_DIR = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010"
VALIDATE = "tools/command-center/validate.py"
GENERATOR = "command-center/p2-wave/probes/ARC-0010/generator.py"
REGISTRY = "command-center/p2-wave/probes/ARC-0010/registry.json"
SKILL_REL = "skills/skill.council/SKILL.md"

if str(GEN_DIR) not in sys.path:
    sys.path.insert(0, str(GEN_DIR))
import generator as G  # noqa: E402


def lf(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(lf(raw)).hexdigest()


@contextmanager
def patched(**attrs: Any) -> Iterator[None]:
    saved = {name: getattr(G, name) for name in attrs}
    try:
        for name, value in attrs.items():
            setattr(G, name, value)
        yield
    finally:
        for name, value in saved.items():
            setattr(G, name, value)


def load_registry() -> dict[str, Any]:
    return G.load_default_registry()


def two_run(registry: dict[str, Any]) -> tuple[bool, int, dict[str, bytes]]:
    a = G.generate(registry)
    b = G.generate(registry)
    return a == b, len(a), a


def clean_determinism(registry: dict[str, Any]) -> dict[str, Any]:
    identical, n, files = two_run(registry)
    helper_ok, helper_n = G.two_run_identical(registry)
    return {
        "id": "T-TWO-RUN",
        "pass": bool(identical and helper_ok and n >= 8),
        "two_run_byte_identical": identical,
        "helper_two_run_identical": helper_ok,
        "generated_files": n,
        "helper_files": helper_n,
        "paths": sorted(files),
    }


def timestamp_mutant(registry: dict[str, Any]) -> dict[str, Any]:
    """Inject datetime.now() into provenance (every generated template)."""
    orig = G.provenance

    def leaky(entry: dict[str, Any]) -> dict[str, str]:
        p = orig(entry)
        p["generated_at"] = datetime.now().isoformat()
        return p

    with patched(provenance=leaky):
        a = G.generate(registry)
        time.sleep(0.02)
        b = G.generate(registry)
        identical = a == b
        sample = next(iter(a.values()))
        leaked = b"generated_at" in sample
    return {
        "id": "MUT-DATETIME-NOW",
        "injection": "datetime.now().isoformat() written into provenance()",
        "identical": identical,
        "goes_red": not identical,
        "pass": (not identical) and leaked,
        "leaked_into_output": leaked,
        "generated_files": len(a),
    }


def dict_order_mutant(registry: dict[str, Any]) -> dict[str, Any]:
    """Leak dict iteration order: drop sort_keys and reverse keys on run 2."""
    orig_canon = G.canonical_json_bytes
    orig_generate = G.generate
    run = {"n": 0}

    def wrapped_generate(reg: dict[str, Any]) -> dict[str, bytes]:
        run["n"] += 1
        return orig_generate(reg)

    def leaky_canon(obj: Any) -> bytes:
        if not isinstance(obj, dict):
            return orig_canon(obj)
        keys = list(obj.keys())
        if run["n"] % 2 == 0:
            keys = list(reversed(keys))
        rebuilt = {k: obj[k] for k in keys}
        return (
            json.dumps(rebuilt, sort_keys=False, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")

    with patched(canonical_json_bytes=leaky_canon, generate=wrapped_generate):
        a = G.generate(registry)
        b = G.generate(registry)
        identical = a == b
        json_paths = [p for p, raw in a.items() if raw.lstrip().startswith(b"{")]
        differed = [p for p in json_paths if a[p] != b[p]]
    return {
        "id": "MUT-DICT-ORDER",
        "injection": (
            "canonical_json_bytes without sort_keys; key order reversed on the "
            "second generate() invocation"
        ),
        "identical": identical,
        "goes_red": not identical,
        "pass": (not identical) and bool(differed),
        "json_files": len(json_paths),
        "json_files_that_differed": differed,
    }


def import_time_uuid_stays_green(registry: dict[str, Any]) -> dict[str, Any]:
    """Reviewer mutation: process-lifetime id. Same-process two-run stays green."""
    orig = G.provenance
    fixed = str(uuid.uuid4())

    def leaky(entry: dict[str, Any]) -> dict[str, str]:
        p = orig(entry)
        p["run_id"] = fixed
        return p

    with patched(provenance=leaky):
        identical, n, files = two_run(registry)
        leaked = all(b"run_id" in raw for raw in files.values())
    return {
        "id": "MUT-IMPORT-TIME-UUID",
        "identical": identical,
        "stays_green": identical,
        "leaked_into_output": leaked,
        "generated_files": n,
        "uuid": fixed,
        "note": (
            "The UUID is assigned once per process and reused. two_run_identical "
            "stays True. A second process would differ. The catalog mutation "
            "control does not catch this."
        ),
    }


def _git(git_dir: Path, args: list[str], input_bytes: bytes | None = None) -> bytes:
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["HOME"] = str(git_dir)
    env["GIT_AUTHOR_NAME"] = "arc-0015"
    env["GIT_AUTHOR_EMAIL"] = "arc-0015@local"
    env["GIT_COMMITTER_NAME"] = "arc-0015"
    env["GIT_COMMITTER_EMAIL"] = "arc-0015@local"
    cmd = ["git", "--git-dir", str(git_dir), *args]
    proc = subprocess.run(
        cmd,
        input=input_bytes,
        capture_output=True,
        env=env,
        cwd=str(git_dir),
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git {args} failed rc={proc.returncode}: {err[-800:]}")
    return proc.stdout


def blob_vs_worktree(lf_bytes: bytes, rel: str) -> dict[str, Any]:
    """LF blob via git cat-file -p versus a CRLF working-tree file.

    The worktree git is not touched: a bare temp GIT_DIR is used. Objects are
    written with hash-object -w (not add/commit/checkout). git archive is not
    invoked.
    """
    if not lf_bytes or b"\r\n" in lf_bytes:
        raise ValueError("source must be non-empty LF bytes")
    crlf_bytes = lf_bytes.replace(b"\n", b"\r\n")
    with tempfile.TemporaryDirectory(prefix="arc0015-git-") as td:
        git_dir = Path(td) / "objects.git"
        git_dir.mkdir()
        _git(git_dir, ["init", "--bare", "--quiet"])
        oid = _git(git_dir, ["hash-object", "-w", "--stdin"], lf_bytes).decode().strip()
        blob = _git(git_dir, ["cat-file", "-p", oid])
        wt_path = Path(td) / "worktree" / rel.replace("/", "_")
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        wt_path.write_bytes(crlf_bytes)
        worktree = wt_path.read_bytes()

    naive_blob_match = blob == lf_bytes
    naive_wt_match = worktree == lf_bytes
    norm_blob_match = lf(blob) == lf_bytes
    norm_wt_match = lf(worktree) == lf_bytes
    verdict_blob = "PASS" if norm_blob_match else "FAIL"
    verdict_wt = "PASS" if norm_wt_match else "FAIL"
    naive_verdict_blob = "PASS" if naive_blob_match else "FAIL"
    naive_verdict_wt = "PASS" if naive_wt_match else "FAIL"
    return {
        "path": rel,
        "evidence_route": "git cat-file -p",
        "git_archive_used": False,
        "git_add_commit_checkout_used": False,
        "blob_oid": oid,
        "blob_bytes": len(blob),
        "blob_crlf_count": blob.count(b"\r\n"),
        "blob_sha256_raw": hashlib.sha256(blob).hexdigest(),
        "blob_sha256_lf": sha256_bytes(blob),
        "worktree_bytes": len(worktree),
        "worktree_crlf_count": worktree.count(b"\r\n"),
        "worktree_sha256_raw": hashlib.sha256(worktree).hexdigest(),
        "worktree_sha256_lf": sha256_bytes(worktree),
        "source_sha256_lf": sha256_bytes(lf_bytes),
        "raw_blob_equals_source": naive_blob_match,
        "raw_worktree_equals_blob": worktree == blob,
        "raw_worktree_equals_source": naive_wt_match,
        "lf_blob_equals_source": norm_blob_match,
        "lf_worktree_equals_source": norm_wt_match,
        "verdict_on_lf_blob": verdict_blob,
        "verdict_on_crlf_worktree": verdict_wt,
        "verdicts_identical_after_lf_norm": verdict_blob == verdict_wt,
        "naive_verdict_on_lf_blob": naive_verdict_blob,
        "naive_verdict_on_crlf_worktree": naive_verdict_wt,
        "naive_verdicts_identical": naive_verdict_blob == naive_verdict_wt,
        "platform_dependent_without_lf_norm": naive_verdict_blob != naive_verdict_wt,
        "host": "linux",
        "note": (
            "This Linux box has no worktree .git. The LF blob is obtained with "
            "git cat-file -p from a throwaway bare GIT_DIR (hash-object -w, no "
            "add/commit/checkout). The CRLF working-tree form is written beside "
            "it. git archive is not used (catalog: it returns CRLF on the "
            "Windows box that measured the gap). On Linux, archive would likely "
            "agree with the blob; that is not this probe's evidence route."
        ),
    }


def classify_tree_lf_stable(
    root: Path, registry: dict[str, Any]
) -> list[dict[str, Any]]:
    """Classify after LF-normalising bytes so markdown provenance headers parse.

    Live parse_provenance HEADER_RE requires a bare ``\\n`` after the HTML
    comment. A CRLF checkout of the same blob therefore reports
    MISSING_PROVENANCE on ``.md`` files even though classify()'s byte compare
    already LF-normalises. The suite wraps parse_provenance; that is the
    platform-dependent detector being fixed, not an A2 rebuild.
    """
    orig = G.parse_provenance

    def parse(raw: bytes) -> dict[str, str] | None:
        return orig(lf(raw) if raw else raw)

    with patched(parse_provenance=parse):
        return G.classify_tree(root, registry)


def crlf_roundtrip_classify(registry: dict[str, Any]) -> dict[str, Any]:
    """Round-trip fidelity: classify a CRLF checkout of generated LF bytes.

    Naive classify() is platform-dependent on markdown (HEADER_RE). The suite
    LF-normalises before provenance parse so CRLF and LF trees share verdicts:
    CLEAN when bytes match regeneration, TAMPERED when content is mutated.
    """
    files = G.generate(registry)
    skill = files[SKILL_REL]
    with tempfile.TemporaryDirectory(prefix="arc0015-rt-") as td:
        lf_root = Path(td) / "lf"
        crlf_root = Path(td) / "crlf"
        G.write_tree(files, lf_root)
        crlf_root.mkdir()
        for rel, raw in files.items():
            dest = crlf_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(
                raw.replace(b"\n", b"\r\n") if b"\r\n" not in raw else raw
            )
        naive_lf = {r["path"]: r["status"] for r in G.classify_tree(lf_root, registry)}
        naive_crlf = {
            r["path"]: r["status"] for r in G.classify_tree(crlf_root, registry)
        }
        lf_rows = {
            r["path"]: r["status"] for r in classify_tree_lf_stable(lf_root, registry)
        }
        crlf_rows = {
            r["path"]: r["status"]
            for r in classify_tree_lf_stable(crlf_root, registry)
        }
        mutated = crlf_root / SKILL_REL
        mutated.write_bytes(mutated.read_bytes() + b"CONTENT-MUTANT\r\n")
        bad_crlf = {
            r["path"]: r["status"]
            for r in classify_tree_lf_stable(crlf_root, registry)
        }
        lf_skill = lf_root / SKILL_REL
        lf_skill.write_bytes(skill + b"CONTENT-MUTANT\n")
        bad_lf = {
            r["path"]: r["status"] for r in classify_tree_lf_stable(lf_root, registry)
        }

    naive_md_missing = sorted(
        p
        for p, st in naive_crlf.items()
        if st == "MISSING_PROVENANCE" and p.endswith(".md")
    )
    lf_clean = set(lf_rows.values()) == {"CLEAN"}
    crlf_clean = set(crlf_rows.values()) == {"CLEAN"}
    naive_lf_clean = set(naive_lf.values()) == {"CLEAN"}
    naive_crlf_clean = set(naive_crlf.values()) == {"CLEAN"}
    crlf_skill_tampered = bad_crlf.get(SKILL_REL) == "TAMPERED"
    lf_skill_tampered = bad_lf.get(SKILL_REL) == "TAMPERED"
    clean_verdicts_match = lf_clean == crlf_clean
    mutant_verdicts_match = crlf_skill_tampered == lf_skill_tampered
    naive_platform_dependent = naive_lf_clean and (not naive_crlf_clean)
    return {
        "id": "T-CRLF-ROUNDTRIP",
        "pass": (
            lf_clean
            and crlf_clean
            and crlf_skill_tampered
            and lf_skill_tampered
            and clean_verdicts_match
            and mutant_verdicts_match
            and naive_platform_dependent
            and len(naive_md_missing) >= 1
        ),
        "lf_tree_all_clean": lf_clean,
        "crlf_tree_all_clean": crlf_clean,
        "naive_lf_tree_all_clean": naive_lf_clean,
        "naive_crlf_tree_all_clean": naive_crlf_clean,
        "naive_crlf_markdown_missing_provenance": naive_md_missing,
        "naive_classify_platform_dependent": naive_platform_dependent,
        "clean_verdicts_identical": clean_verdicts_match,
        "content_mutant_lf": bad_lf.get(SKILL_REL),
        "content_mutant_crlf": bad_crlf.get(SKILL_REL),
        "mutant_verdicts_identical": mutant_verdicts_match,
        "files": len(files),
        "suite_lf_normalises_before_parse": True,
        "live_header_re_requires_bare_lf": True,
        "anchor": f"{GENERATOR}:52",
    }


def gitattributes_gap() -> dict[str, Any]:
    ga = REPO / ".gitattributes"
    present = ga.is_file()
    text = ga.read_text(encoding="utf-8") if present else ""
    md_eol_lf = bool(
        re.search(r"(?m)^\s*\*\.md\b.*\beol=lf\b", text)
    )
    py_eol_lf = bool(
        re.search(r"(?m)^\s*\*\.py\b.*\beol=lf\b", text)
    )
    validate = REPO / VALIDATE
    vtext = validate.read_text(encoding="utf-8") if validate.is_file() else ""
    mentions_autocrlf = "core.autocrlf" in vtext and "CRLF" in vtext
    lf_norm_in_reach6 = 'replace(b"\\r\\n", b"\\n")' in vtext
    git_present = (REPO / ".git").exists()
    return {
        "gitattributes_present": present,
        "gitattributes_md_eol_lf_rule": md_eol_lf,
        "gitattributes_py_eol_lf_rule": py_eol_lf,
        "worktree_is_git_repo": git_present,
        "attributes_can_pin_checkout_here": bool(present and md_eol_lf and git_present),
        "validate_py_present": validate.is_file(),
        "validate_mentions_windows_autocrlf_gap": mentions_autocrlf,
        "validate_reach6_now_lf_normalises": lf_norm_in_reach6,
        "anchor": f"{VALIDATE}:217",
        "note": (
            (
                ".gitattributes is present and pins *.md eol=lf, but this "
                "worktree has no .git directory so the rule cannot affect a "
                "checkout here. "
                if present and md_eol_lf and not git_present
                else (
                    "No .gitattributes on this worktree (so no '*.md eol=lf' pin). "
                    if not present
                    else ".gitattributes present; md eol=lf "
                    f"rule={md_eol_lf}; git checkout={git_present}. "
                )
            )
            + "validate.py REACH-6 originally hashed raw working-tree bytes "
            "and was unrunnable on Windows autocrlf checkouts; it now "
            "LF-normalises before hashing. The suite still requires identical "
            "verdicts on CRLF worktree vs LF blob; a naive raw compare is "
            "recorded as platform-dependent."
        ),
    }


def measure() -> dict[str, Any]:
    registry = load_registry()
    clean = clean_determinism(registry)
    ts = timestamp_mutant(registry)
    order = dict_order_mutant(registry)
    uncaught = import_time_uuid_stays_green(registry)
    files = G.generate(registry)
    skill = files[SKILL_REL]
    eol = blob_vs_worktree(skill, SKILL_REL)
    roundtrip = crlf_roundtrip_classify(registry)
    gap = gitattributes_gap()
    ok = (
        clean["pass"]
        and ts["pass"]
        and order["pass"]
        and uncaught["stays_green"]
        and eol["verdicts_identical_after_lf_norm"]
        and eol["platform_dependent_without_lf_norm"]
        and not eol["git_archive_used"]
        and eol["evidence_route"] == "git cat-file -p"
        and roundtrip["pass"]
    )
    return {
        "pass": ok,
        "generated_files": clean["generated_files"],
        "clean": clean,
        "timestamp_mutant": ts,
        "dict_order_mutant": order,
        "uncaught_import_time_uuid": uncaught,
        "eol": eol,
        "roundtrip": roundtrip,
        "gitattributes_gap": gap,
        "generator": GENERATOR,
        "registry": REGISTRY,
    }


def main() -> int:
    report = measure()
    print(json.dumps({k: report[k] for k in ("pass", "generated_files")}, sort_keys=True))
    eol = report["eol"]
    print(
        f"clean={report['clean']['pass']} ts_red={report['timestamp_mutant']['goes_red']} "
        f"order_red={report['dict_order_mutant']['goes_red']} "
        f"uncaught_green={report['uncaught_import_time_uuid']['stays_green']}"
    )
    print(
        f"eol route={eol['evidence_route']} archive={eol['git_archive_used']} "
        f"blob_crlf={eol['blob_crlf_count']} wt_crlf={eol['worktree_crlf_count']} "
        f"verdicts={eol['verdict_on_lf_blob']}/{eol['verdict_on_crlf_worktree']} "
        f"naive_platform_dependent={eol['platform_dependent_without_lf_norm']}"
    )
    print(f"roundtrip={report['roundtrip']['pass']} gap_ga={report['gitattributes_gap']['gitattributes_present']}")
    if not report["pass"]:
        print("FAILED:ARC-0015 suite")
        return 1
    print("SUCCESS:ARC-0015-suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
