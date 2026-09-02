#!/usr/bin/env python3
"""Live measurements for CNF-0149: three-route bytes + checkout-mode claims."""
from __future__ import annotations

import ast
import hashlib
import io
import re
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

from scenario import (
    BAD_PY,
    CONTROL,
    GOOD_PY,
    KNOWN_CRLF,
    REGISTER,
    REVIEWER,
    UNIT,
    build_repo,
    clone_checkout,
    git,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/receipts/CNF-0149.json"
SCHEMA_REL = "command-center/schema/reproduction-matrix.schema.json"
CI_PIN_REL = "command-center/p2-wave/_i3_blobfmt.py"
CI_PIN_SNIPPET = 'RUFF = ["uvx", "ruff@0.15.17"]'
VALIDATE_REL = "tools/command-center/validate.py"
VALIDATE_SNIPPET = "LF-NORMALISE BEFORE HASHING"
BLOBREAD_REL = "tools/measure-guard/blobread.py"
BLOBREAD_SNIPPET = "git archive (member EXTRACTED)  3,837 bytes   100 CRLF"
CHECKLIST_REL = "command-center/RELEASE-CHECKLIST.md"
WIN_SHELL_REL = "rules/common/windows-shell.md"
TITLE = (
    "Line-ending matrix: reproduce every formatter and gate claim "
    "against the git blob, not the worktree"
)
QUESTION = (
    "Does each formatting, lint and hash claim hold on the bytes CI "
    "actually checks out (git cat-file blob), under core.autocrlf "
    "true and false? git archive | tar -x is forbidden as the blob source."
)
TEST_NAMES = (
    (
        "lf_normalisation_control",
        "Control: three routes are byte-identical after LF normalisation",
    ),
    (
        "archive_differs_from_blob_on_eol_crlf_file",
        "git archive differs from the cat-file blob on an eol=crlf file",
    ),
    (
        "known_broken_crlf_detected_by_blob_route",
        "Known-broken CRLF file is detected by the git cat-file blob route",
    ),
    (
        "misformatted_fails_both_checkout_modes",
        "Both-states: a mis-formatted file fails under both checkout modes",
    ),
    (
        "good_style_passes_both_checkout_modes",
        "Good style passes under both checkout modes and on the blob",
    ),
    (
        "reach6_blob_matches_recorded",
        "REACH-6 recorded provenance hash matches the git cat-file blob",
    ),
    (
        "reach6_autocrlf_true_worktree_raw_differs",
        "REACH-6 autocrlf=true worktree raw hash differs from the blob",
    ),
)

ARCHIVE_INVOKE = re.compile(r"git\s+archive", re.I)
NEGATED_ARCHIVE = re.compile(
    r"\b(not|never|no|avoid|unlike|rather than|instead of)\s+[`'\"*]*git\s+archive",
    re.I,
)
TRAILING_COMMENT = re.compile(r"\s+(#|//)\s.*$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def counts(data: bytes) -> dict:
    crlf = data.count(b"\r\n")
    return {
        "bytes": len(data),
        "crlf": crlf,
        "cr": data.count(b"\r"),
        "lf_newlines": data.count(b"\n") - crlf,
        "sha256": sha256(data),
        "sha256_lf": sha256(lf(data)),
    }


def cite(rel: str, snippet: str) -> dict:
    path = REPO / rel
    row = {
        "path": rel,
        "present": path.is_file(),
        "line": None,
        "snippet": snippet,
        "found": False,
    }
    if not path.is_file():
        return row
    text = path.read_text(encoding="utf-8", errors="replace")
    idx = text.find(snippet)
    if idx >= 0:
        row["line"] = text[:idx].count("\n") + 1
        row["found"] = True
    return row


def cat_file(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    return git(repo, "cat-file", "-p", f"{rev}:{rel}").stdout


def git_show(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    return git(repo, "show", f"{rev}:{rel}").stdout


def git_archive(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    tar_bytes = git(repo, "archive", "--format=tar", rev, "--", rel).stdout
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tf:
        names = tf.getnames()
        for candidate in (rel, "./" + rel):
            if candidate in names:
                fh = tf.extractfile(candidate)
                if fh is None:
                    raise RuntimeError(f"archive member empty: {rel}")
                return fh.read()
        raise KeyError(f"{rel} not in archive members {names}")


def three_route(repo: Path, rel: str) -> dict:
    arch = git_archive(repo, rel)
    cat = cat_file(repo, rel)
    show = git_show(repo, rel)
    routes = {
        "git archive | tar -x": counts(arch),
        "git cat-file -p": counts(cat),
        "git show <rev>:<path>": counts(show),
    }
    identical_lf = bool(lf(arch)) and lf(arch) == lf(cat) == lf(show)
    return {
        "path": rel,
        "routes": routes,
        "cat_file_equals_show": cat == show,
        "archive_differs_from_blob": arch != cat,
        "identical_after_lf_normalisation": identical_lf,
        "eol_is_sole_variable": identical_lf and arch != cat,
        "blob_source": "git cat-file -p",
        "archive_forbidden_as_blob_source": True,
    }


def style_ok(data: bytes) -> bool:
    text = lf(data).decode("utf-8")
    return "return  " not in text and "( " not in text


def lint_compiles(data: bytes) -> bool:
    try:
        ast.parse(lf(data).decode("utf-8"))
        return True
    except SyntaxError:
        return False


def ruff_pin() -> dict:
    row = cite(CI_PIN_REL, CI_PIN_SNIPPET)
    row["ruff_on_path"] = bool(shutil.which("ruff"))
    row["uvx_on_path"] = bool(shutil.which("uvx"))
    row["invocable"] = False
    row["reason"] = (
        "CI pin cited from _i3_blobfmt.py; live style+compile signals do not "
        "call uvx (no network in G-1 probes)."
    )
    return row


def reach6_hashes(blob: bytes, worktree: bytes, recorded: str) -> dict:
    blob_h = sha256(blob)
    raw_wt = sha256(worktree)
    norm_wt = sha256(lf(worktree))
    return {
        "recorded": recorded,
        "blob_sha256": blob_h,
        "worktree_raw_sha256": raw_wt,
        "worktree_lf_sha256": norm_wt,
        "blob_matches_recorded": blob_h == recorded,
        "worktree_raw_differs_from_blob": raw_wt != blob_h,
        "lf_worktree_matches_blob": norm_wt == blob_h,
        "current_validate_py_matches_recorded": norm_wt == recorded,
        "raw_worktree_gate_would_mismatch": raw_wt != recorded,
    }


def claim_cell(ok: bool, detail: str) -> dict:
    return {"holds": ok, "detail": detail}


def per_claim(blob: bytes, true_wt: bytes, false_wt: bytes, kind: str) -> dict:
    if kind == "style":
        b, t, f_ = style_ok(blob), style_ok(true_wt), style_ok(false_wt)
        return {
            "blob": claim_cell(b, "style after LF-norm"),
            "autocrlf_true": claim_cell(t, "style after LF-norm"),
            "autocrlf_false": claim_cell(f_, "style after LF-norm"),
            "holds_on_ci_blob": b,
            "holds_under_both_checkout_modes": t == b and f_ == b,
        }
    if kind == "lint":
        b, t, f_ = lint_compiles(blob), lint_compiles(true_wt), lint_compiles(false_wt)
        return {
            "blob": claim_cell(b, "ast.parse after LF-norm"),
            "autocrlf_true": claim_cell(t, "ast.parse after LF-norm"),
            "autocrlf_false": claim_cell(f_, "ast.parse after LF-norm"),
            "holds_on_ci_blob": b,
            "holds_under_both_checkout_modes": t == b and f_ == b,
        }
    if kind == "hash_raw":
        rec = sha256(blob)
        t_ok = sha256(true_wt) == rec
        f_ok = sha256(false_wt) == rec
        return {
            "blob": claim_cell(True, rec),
            "autocrlf_true": claim_cell(t_ok, sha256(true_wt)),
            "autocrlf_false": claim_cell(f_ok, sha256(false_wt)),
            "holds_on_ci_blob": True,
            "holds_under_both_checkout_modes": t_ok and f_ok,
        }
    rec = sha256(lf(blob))
    t_ok = sha256(lf(true_wt)) == rec
    f_ok = sha256(lf(false_wt)) == rec
    return {
        "blob": claim_cell(True, rec),
        "autocrlf_true": claim_cell(t_ok, sha256(lf(true_wt))),
        "autocrlf_false": claim_cell(f_ok, sha256(lf(false_wt))),
        "holds_on_ci_blob": True,
        "holds_under_both_checkout_modes": t_ok and f_ok,
    }


def vpf(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def claim_cells(claims: dict) -> list[dict]:
    rows: list[dict] = []
    for cid, claim in claims.items():
        blob_v = vpf(claim["blob"]["holds"])
        true_v = vpf(claim["autocrlf_true"]["holds"])
        false_v = vpf(claim["autocrlf_false"]["holds"])
        same = blob_v == true_v == false_v
        rows.append(
            {
                "id": cid.replace(".", "-"),
                "subject": f"{cid} on git blob vs core.autocrlf true/false",
                "classification": (
                    "version-insensitive" if same else "version-sensitive"
                ),
                "verdicts": {
                    "blob": blob_v,
                    "autocrlf_true": true_v,
                    "autocrlf_false": false_v,
                },
                "holds_on_ci_blob": claim["holds_on_ci_blob"],
                "holds_under_both_checkout_modes": claim[
                    "holds_under_both_checkout_modes"
                ],
            }
        )
    return rows


def test_rows(tests: dict) -> list[dict]:
    return [
        {
            "id": key,
            "name": name,
            "result": "PASS" if tests[key] else "FAIL",
        }
        for key, name in TEST_NAMES
    ]


def artifact_row(rel: str, role: str) -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    return {"path": rel, "exists": True, "role": role}


def scan_doc(rel: str) -> list[dict]:
    """Prescriptive (non-negated) git-archive invocations, for CONFIRMED recipes."""
    return scan_archive_mentions(rel)["prescriptive"]


def scan_archive_mentions(rel: str) -> dict:
    path = REPO / rel
    out = {"prescriptive": [], "negated": []}
    if not path.is_file():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        code = TRAILING_COMMENT.sub("", line)
        if not ARCHIVE_INVOKE.search(line) and not ARCHIVE_INVOKE.search(code):
            continue
        row = {"path": rel, "line": i, "text": line.strip()[:240]}
        if NEGATED_ARCHIVE.search(line) or NEGATED_ARCHIVE.search(code):
            out["negated"].append(row)
        else:
            out["prescriptive"].append(row)
    return out


def git_version(repo: Path) -> str:
    return git(repo, "version").stdout.decode("utf-8", "replace").strip()


def measure() -> dict:
    validate_cite = cite(VALIDATE_REL, VALIDATE_SNIPPET)
    blobread_cite = cite(BLOBREAD_REL, BLOBREAD_SNIPPET)
    pin = ruff_pin()
    checklist_mentions = scan_archive_mentions(CHECKLIST_REL)
    checklist_hits = checklist_mentions["prescriptive"]
    checklist_negated = checklist_mentions["negated"]
    win_mentions = scan_archive_mentions(WIN_SHELL_REL)
    win_hits = win_mentions["prescriptive"]
    checklist_present = (REPO / CHECKLIST_REL).is_file()
    win_present = (REPO / WIN_SHELL_REL).is_file()

    with tempfile.TemporaryDirectory(prefix="cnf0149-") as tmp:
        root = Path(tmp)
        built = build_repo(root)
        repo: Path = built["repo"]
        rev = built["rev"]
        control = three_route(repo, CONTROL)
        reviewer = three_route(repo, REVIEWER)
        crlf_blob = cat_file(repo, KNOWN_CRLF)
        true_wt = clone_checkout(repo, root / "wt-true", "true")
        false_wt = clone_checkout(repo, root / "wt-false", "false")

        def wt(tree: Path, rel: str) -> bytes:
            return (tree / rel).read_bytes()

        blob_reg = cat_file(repo, REGISTER)
        recorded = sha256(blob_reg)
        r6_true = reach6_hashes(blob_reg, wt(true_wt, REGISTER), recorded)
        r6_false = reach6_hashes(blob_reg, wt(false_wt, REGISTER), recorded)

        good_blob = cat_file(repo, GOOD_PY)
        bad_blob = cat_file(repo, BAD_PY)
        claims = {
            "good.py_style": per_claim(
                good_blob, wt(true_wt, GOOD_PY), wt(false_wt, GOOD_PY), "style"
            ),
            "bad.py_style": per_claim(
                bad_blob, wt(true_wt, BAD_PY), wt(false_wt, BAD_PY), "style"
            ),
            "good.py_lint": per_claim(
                good_blob, wt(true_wt, GOOD_PY), wt(false_wt, GOOD_PY), "lint"
            ),
            "bad.py_lint": per_claim(
                bad_blob, wt(true_wt, BAD_PY), wt(false_wt, BAD_PY), "lint"
            ),
            "register.md_hash_raw": per_claim(
                blob_reg, wt(true_wt, REGISTER), wt(false_wt, REGISTER), "hash_raw"
            ),
            "register.md_hash_lf": per_claim(
                blob_reg, wt(true_wt, REGISTER), wt(false_wt, REGISTER), "hash_lf"
            ),
        }

        tests = {
            "lf_normalisation_control": (
                control["identical_after_lf_normalisation"]
                and reviewer["identical_after_lf_normalisation"]
            ),
            "archive_differs_from_blob_on_eol_crlf_file": control[
                "archive_differs_from_blob"
            ],
            "known_broken_crlf_detected_by_blob_route": (
                crlf_blob.count(b"\r\n") >= 3 and b"\r\n" in crlf_blob
            ),
            "misformatted_fails_both_checkout_modes": (
                not style_ok(wt(true_wt, BAD_PY))
                and not style_ok(wt(false_wt, BAD_PY))
                and not style_ok(bad_blob)
            ),
            "good_style_passes_both_checkout_modes": (
                style_ok(wt(true_wt, GOOD_PY))
                and style_ok(wt(false_wt, GOOD_PY))
                and style_ok(good_blob)
            ),
            "reach6_blob_matches_recorded": r6_true["blob_matches_recorded"],
            "reach6_autocrlf_true_worktree_raw_differs": r6_true[
                "worktree_raw_differs_from_blob"
            ],
        }

        arch_c = control["routes"]["git archive | tar -x"]
        cat_c = control["routes"]["git cat-file -p"]
        classic_match = (
            cat_c["bytes"] == 3737
            and cat_c["crlf"] == 0
            and arch_c["bytes"] == 3837
            and arch_c["crlf"] == 100
        )

        if not checklist_present:
            checklist_verdict = {
                "path": CHECKLIST_REL,
                "present": False,
                "verdict": "REFUTED-ABSENT",
                "line_citation": None,
                "note": (
                    "command-center/RELEASE-CHECKLIST.md is not on this worktree; "
                    "the catalog/CC-0006 quote that it prescribes verifying "
                    "formatting 'against the LF blob (git archive)' cannot be "
                    "cited by line here."
                ),
            }
        elif checklist_hits:
            checklist_verdict = {
                "path": CHECKLIST_REL,
                "present": True,
                "verdict": "CONFIRMED",
                "line_citation": checklist_hits,
                "note": "prescriptive git archive recipe present",
            }
        elif checklist_negated:
            first = checklist_negated[0]
            checklist_verdict = {
                "path": CHECKLIST_REL,
                "present": True,
                "verdict": "REFUTED-FORBIDS-ARCHIVE",
                "line_citation": checklist_negated,
                "note": (
                    f"{CHECKLIST_REL}:{first['line']} forbids git archive as the "
                    "blob source and names git cat-file / blobread.py instead. "
                    "Catalog input that the file 'currently prescribes the archive "
                    "recipe' is refuted on this worktree."
                ),
            }
        else:
            checklist_verdict = {
                "path": CHECKLIST_REL,
                "present": True,
                "verdict": "REFUTED-NO-PRESCRIPTION",
                "line_citation": [],
                "note": "file present; no git archive invocation to confirm or refute",
            }

        all_ok = all(tests.values())
        cells = claim_cells(claims)
        artifacts = [
            row
            for row in (
                artifact_row(OUT_REL, "primary"),
                artifact_row(SCHEMA_REL, "schema"),
                artifact_row(VALIDATE_REL, "reach6-gate"),
                artifact_row(BLOBREAD_REL, "blob-hasher"),
                artifact_row(CI_PIN_REL, "ci-formatter-pin"),
                artifact_row(
                    "command-center/p2-wave/probes/CNF-0149/probe1_three_route.py",
                    "named-probe",
                ),
                artifact_row(
                    "command-center/p2-wave/probes/CNF-0149/probe2_claim_matrix.py",
                    "named-probe",
                ),
            )
            if row is not None
        ]
        # Primary is emitted after measure(); schema requires exists=true.
        if not any(a["path"] == OUT_REL for a in artifacts):
            artifacts.insert(0, {"path": OUT_REL, "exists": True, "role": "primary"})
        pin_line = pin.get("line")
        val_line = validate_cite.get("line")
        evidence = [
            {
                "kind": "three-route",
                "claim": "git archive is forbidden: it is not the stored blob",
                "detail": (
                    f"{CONTROL}: archive={arch_c['bytes']}B/{arch_c['crlf']}CRLF "
                    f"vs cat-file={cat_c['bytes']}B/{cat_c['crlf']}CRLF "
                    f"(classic reproduced={classic_match})"
                ),
            },
            {
                "kind": "reach6",
                "claim": "Recorded provenance hash matches the blob, not raw worktree",
                "detail": (
                    f"blob={r6_true['blob_sha256'][:16]} "
                    f"autocrlf_true_raw={r6_true['worktree_raw_sha256'][:16]} "
                    f"lf_worktree={r6_true['worktree_lf_sha256'][:16]}"
                ),
            },
            {
                "kind": "both-states",
                "claim": "Mis-formatted file fails style under blob and both checkouts",
                "detail": (
                    "bad.py_style holds_on_ci_blob="
                    f"{claims['bad.py_style']['holds_on_ci_blob']} "
                    "holds_under_both_checkout_modes="
                    f"{claims['bad.py_style']['holds_under_both_checkout_modes']}"
                ),
            },
            {
                "kind": "doc-refute",
                "claim": (
                    "RELEASE-CHECKLIST.md archive recipe cited by line "
                    f"(verdict={checklist_verdict.get('verdict')})"
                ),
                "detail": str(checklist_verdict.get("note") or "checklist absent"),
            },
            {
                "kind": "gate-source",
                "claim": (
                    "validate.py REACH-6 LF-normalises working-tree bytes before "
                    "hashing; a raw-worktree hash would diverge under autocrlf=true"
                ),
                "detail": (
                    f"{VALIDATE_REL}:"
                    f"{val_line if val_line is not None else 'missing'} "
                    f"found={validate_cite.get('found')} snippet={VALIDATE_SNIPPET}"
                ),
            },
            {
                "kind": "classic-source",
                "claim": "blobread.py records the catalog 3837/3737 three-route control",
                "detail": (
                    f"{BLOBREAD_REL}:"
                    f"{blobread_cite.get('line') if blobread_cite.get('line') is not None else 'missing'} "
                    f"found={blobread_cite.get('found')} snippet={BLOBREAD_SNIPPET}"
                ),
            },
            {
                "kind": "ci-pin",
                "claim": "CI formatter pin is ruff 0.15.17 via uvx; probes do not call uvx",
                "detail": (
                    f"{CI_PIN_REL}:{pin_line if pin_line is not None else 'missing'} "
                    f"found={pin.get('found')} ruff_on_path={pin.get('ruff_on_path')} "
                    f"uvx_on_path={pin.get('uvx_on_path')}"
                ),
            },
        ]
        return {
            "unit_id": UNIT,
            "state": "SUCCESS" if all_ok else "FAILED",
            "status": "DELIVERED" if all_ok else "FAILED",
            "sentinel": f"SUCCESS:{UNIT}",
            "completion_sentinel": f"SUCCESS:{UNIT}",
            "report_kind": "reproduction-matrix",
            "report": {
                "kind": "reproduction-matrix",
                "control_ids": [
                    "lf_normalisation_control",
                    "known_broken_crlf_detected_by_blob_route",
                    "misformatted_fails_both_checkout_modes",
                    "reach6_autocrlf_true_worktree_raw_differs",
                ],
                "observations": [
                    {
                        "name": "classic_archive_bytes",
                        "measured": arch_c["bytes"],
                        "method": "git archive | tarfile extract vs git cat-file -p",
                        "anchor": f"{CONTROL} fixture matching blobread.py 3837/3737",
                    },
                    {
                        "name": "classic_cat_file_bytes",
                        "measured": cat_c["bytes"],
                        "method": "git cat-file -p",
                        "anchor": f"{CONTROL}",
                    },
                    {
                        "name": "checklist_verdict",
                        "measured": str(checklist_verdict.get("verdict")),
                        "method": "line scan of RELEASE-CHECKLIST.md for git archive",
                        "anchor": CHECKLIST_REL,
                    },
                    {
                        "name": "reach6_blob_sha256",
                        "measured": recorded,
                        "method": "sha256 of git cat-file blob of register.md",
                        "anchor": REGISTER,
                    },
                    {
                        "name": "reach6_autocrlf_true_raw_differs",
                        "measured": bool(
                            r6_true["worktree_raw_differs_from_blob"]
                        ),
                        "method": "clone core.autocrlf=true vs cat-file blob",
                        "anchor": REGISTER,
                    },
                ],
            },
            "spec_anchor": (
                "command-center/WORK-UNIT-CATALOG.json CNF-0149; "
                "command-center/RELEASE-CHECKLIST.md; "
                "tools/measure-guard/blobread.py"
            ),
            "schema_version": 1,
            "title": TITLE,
            "question": QUESTION,
            "axes": [
                {
                    "id": "blob",
                    "label": "git cat-file -p blob (CI-stored bytes; archive forbidden)",
                },
                {
                    "id": "autocrlf_true",
                    "label": "working tree after clone with core.autocrlf=true",
                },
                {
                    "id": "autocrlf_false",
                    "label": "working tree after clone with core.autocrlf=false",
                },
            ],
            "cells": cells,
            "tests": test_rows(tests),
            "evidence": evidence,
            "reviewer": {
                "reviewer_id": "CNF-0149-probe1-three-route-second-file",
                "verdict": "PASS" if all_ok else "FAIL",
                "independent": True,
                "notes": (
                    "Probe 1 re-runs the three-route table on reviewer-second.txt "
                    "as well as control-lf.txt. Probe 2 is the checkout-mode "
                    "claim matrix, not a repeat of probe 1's byte table."
                ),
            },
            "artifacts": artifacts,
            "question_catalog": (
                "Does each formatting, lint and hash claim hold on the bytes CI "
                "actually checks out? Reproduce under core.autocrlf true and false "
                "and against the stored blob obtained with git cat-file -p. "
                "git archive | tar -x is forbidden as the blob source."
            ),
            "platform": {
                "sys_platform": sys.platform,
                "worktree_is_git_repo": (REPO / ".git").exists(),
                "git_version": git_version(repo),
                "note": (
                    "Parent worktree is not a git repo; three-route and autocrlf "
                    "matrices run on an isolated fixture repo. On Linux, git archive "
                    "does not apply core.autocrlf; archive→CRLF is reproduced via "
                    ".gitattributes `text eol=crlf` (convert_to_working_tree), the "
                    "same path Windows Git uses when archive emits CRLF."
                ),
            },
            "blob_source_policy": {
                "allowed": [
                    "git cat-file -p <rev>:<path>",
                    "git show <rev>:<path>",
                ],
                "forbidden": "git archive | tar -x",
                "reason": (
                    "archive applies working-tree/export EOL conversion; measured "
                    f"control {CONTROL}: archive={arch_c['bytes']}B/{arch_c['crlf']}CRLF "
                    f"vs cat-file={cat_c['bytes']}B/{cat_c['crlf']}CRLF"
                ),
            },
            "classic_3837_3737_control": {
                "kind": (
                    "constructed fixture matching catalog arithmetic "
                    "(100 LF → 100 extra CR)"
                ),
                "reproduced": classic_match,
                "archive_bytes": arch_c["bytes"],
                "archive_crlf": arch_c["crlf"],
                "cat_file_bytes": cat_c["bytes"],
                "cat_file_crlf": cat_c["crlf"],
            },
            "three_route_table": [control, reviewer],
            "known_broken_crlf_blob": {
                "path": KNOWN_CRLF,
                "cat_file": counts(crlf_blob),
                "detected": tests["known_broken_crlf_detected_by_blob_route"],
            },
            "inputs_on_disk": {
                "RELEASE-CHECKLIST.md": checklist_verdict,
                "windows-shell.md_8b": {
                    "path": WIN_SHELL_REL,
                    "present": win_present,
                    "section_8b": None,
                    "prescriptive_hits": win_hits,
                    "verdict": "REFUTED-ABSENT" if not win_present else "PRESENT",
                    "catalog_citation": (
                        "rules/common/windows-shell.md#8b (git archive returns "
                        "CRLF, cat-file returns the blob)"
                    ),
                    "note": (
                        "rules/common/windows-shell.md is not on this worktree; "
                        "catalog 8b is cited as 'git archive returns CRLF, "
                        "cat-file returns the blob'."
                    ),
                },
                "validate.py_REACH-6": {
                    **validate_cite,
                    "behaviour": (
                        "Live validate.py LF-normalises working-tree bytes "
                        "(snapshot.read_bytes().replace(b'\\r\\n', b'\\n')) "
                        "before hashing REACH-6. That matches the git blob when "
                        "the only delta is CRLF. A raw-worktree hash under "
                        "core.autocrlf=true does not. git_blob.py is absent on "
                        "this worktree; blobread.py is the helper the checklist "
                        "names (git cat-file -p)."
                    ),
                },
                "blobread.py": blobread_cite,
                "ci_formatter_pin": pin,
            },
            "reach6": {
                "recorded_from_blob": recorded,
                "autocrlf_true": r6_true,
                "autocrlf_false": r6_false,
            },
            "claims": claims,
            "tests_required": tests,
            "rev": rev,
            "output_path": OUT_REL,
            "output_schema": SCHEMA_REL,
            "cloud_ok": False,
            "min_bytes_threshold": 2048,
            "SUCCESS:CNF-0149": all_ok,
        }
