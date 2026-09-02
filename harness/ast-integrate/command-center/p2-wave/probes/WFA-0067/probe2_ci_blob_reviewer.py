#!/usr/bin/env python3
"""Probe 2: committed-blob CRLF control + independent both-states re-run.

Evidence B: the gate is invoked exactly as CI invokes it (empty argv).
Tests-required: the gate runs on the committed blob so it is not
CRLF-dependent. Reviewer re-runs this unit's both-states control.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import mechanism_registry_gate as mech  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0067-mechanism-registry-gate.json"
GATE_REL = S.GATE_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0067-probe2 {msg}")
    return 1


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        check=check,
    )


def argparse_opt_in_flags(src: str) -> list[str]:
    """Flags that default off and would ARM a check if passed."""
    tree = ast.parse(src)
    armed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "attr", None) or getattr(fn, "id", None)
        if name != "add_argument":
            continue
        flags = [
            a.value
            for a in node.args
            if isinstance(a, ast.Constant) and isinstance(a.value, str)
        ]
        keys = {
            k.arg: k.value
            for k in node.keywords
            if isinstance(k.value, ast.Constant)
        }
        joined = " ".join(flags).lower()
        if any(tok in joined for tok in ("--require", "--check", "--enable", "--skip")):
            armed.append(joined)
        if keys.get("action") == "store_true" and any(
            "require" in f or "check" in f or "enable" in f or "skip" in f for f in flags
        ):
            armed.append(joined)
    return armed


def both_states(root: Path) -> tuple[bool, bool]:
    good = S.bare_cli(root)
    good_ok = good.returncode == 0 and "SUCCESS:mech-registry-gate" in S.out_of(good)
    S.plant_undefined(root)
    bad = S.bare_cli(root)
    bad_ok = bad.returncode != 0 and "MECH-UNDEF" in S.out_of(bad)
    print(f"reviewer_both_states good_rc={good.returncode} bad_rc={bad.returncode}")
    print(S.out_of(good).splitlines()[-1:][0] if S.out_of(good) else "")
    print(S.out_of(bad).splitlines()[-1:][0] if S.out_of(bad) else "")
    return good_ok, bad_ok


def main() -> int:
    src = (REPO / GATE_REL).read_text(encoding="utf-8")
    armed = argparse_opt_in_flags(src)
    print(f"opt_in_flags={armed}")
    if armed:
        return fail(f"gate still has opt-in/skip flags: {armed}")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0067" not in json.dumps(doc):
        return fail("sentinel absent")
    blob_recipe = str(
        (doc.get("blob_recipe") or doc.get("gate") or {}).get("blob_recipe")
        if isinstance(doc.get("blob_recipe"), dict)
        else doc.get("blob_recipe")
        or (doc.get("gate") or {}).get("blob_recipe")
        or ""
    )
    print(f"artifact_blob_recipe={blob_recipe}")
    if "cat-file" not in blob_recipe:
        return fail("artifact does not record git cat-file blob recipe")

    with tempfile.TemporaryDirectory(prefix="wfa0067-p2-") as tmp:
        root = Path(tmp)
        S.copy_estate(root)
        git(root, "init")
        git(root, "add", "-A")
        git(
            root,
            "-c",
            "user.email=wfa0067@local",
            "-c",
            "user.name=wfa0067",
            "commit",
            "-m",
            "estate",
        )
        path = root / mech.REL_REGISTRY
        lf = path.read_bytes().replace(b"\r\n", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")
        path.write_bytes(crlf)
        work = path.read_bytes()
        if b"\r\n" not in work:
            return fail("working tree did not materialise CRLF")
        blob, source = mech.read_blob(root, mech.REL_REGISTRY)
        print(f"blob_source={source} blob_bytes={len(blob)} work_bytes={len(work)}")
        print(f"blob_crlf={blob.count(b'\r\n')} work_crlf={work.count(b'\r\n')}")
        if source != "git-cat-file-HEAD":
            return fail(f"gate did not use committed blob, source={source}")
        if blob != lf:
            return fail("committed blob bytes != LF original")
        if blob == work:
            return fail("committed blob matched CRLF working tree; recipe is not discriminating")
        proc = S.bare_cli(root)
        text = S.out_of(proc)
        print(f"crlf_estate rc={proc.returncode}")
        print(text.splitlines()[-2:] and "\n".join(text.splitlines()[-2:]))
        if proc.returncode != 0:
            return fail("CRLF working tree turned the gate red (blob recipe not used)")
        if "git-cat-file-HEAD" not in text:
            return fail("bare CLI did not report git-cat-file-HEAD")

    with tempfile.TemporaryDirectory(prefix="wfa0067-p2-states-") as tmp:
        root = Path(tmp)
        S.copy_estate(root)
        good_ok, bad_ok = both_states(root)
        if not good_ok or not bad_ok:
            return fail("reviewer both-states re-run failed")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or not reviewer.get("both_states_rerun"):
        return fail("artifact reviewer did not record both_states_rerun PASS")
    if not reviewer.get("independent"):
        return fail("artifact reviewer independent flag is false")

    print("blob_recipe=git-cat-file-HEAD crlf_independent=True")
    print("reviewer_both_states_rerun=True")
    print("SUCCESS:WFA-0067-probe2 committed-blob + reviewer both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
