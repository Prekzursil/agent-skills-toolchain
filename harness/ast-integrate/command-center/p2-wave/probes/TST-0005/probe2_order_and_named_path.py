#!/usr/bin/env python3
"""Probe 2: existence check is before digest parse; reject names the path.

Mechanically independent of probe 1 (which is a both-states behavioral pair).
This probe (1) AST-orders check_outputs_exist before _parse_digest in admit(),
(2) asserts a naive parse-first mutant records digest_parsed on an absent path
while the real barrier does not, (3) asserts the rejection message names the
absent contracted path.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from fan_in.barrier import SHA256_TOKEN, admit  # noqa: E402
import fixtures as F  # noqa: E402

RAW = HERE / "probe2-order-and-named-path.raw.json"
SRC = REPO / "tools" / "fan_in" / "barrier.py"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0005-probe2 {msg}")
    return 1


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def call_names_with_lines(fn: ast.FunctionDef) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found.append((node.lineno, func.id))
        elif isinstance(func, ast.Attribute):
            found.append((node.lineno, func.attr))
    found.sort()
    return found


def naive_parse_first(root: Path, contracted: list[str], digest_text: str) -> dict:
    """Known-wrong fan-in: parse the digest, then Test-Path.

    A plausible sha256 in prose is treated as a receipt until the later
    existence check. This is the measured Codex failure mode.
    """
    match = SHA256_TOKEN.search(digest_text or "")
    parsed = match is not None
    digest_sha = match.group(1).lower() if match else None
    absent = []
    for rel in contracted:
        path = root / rel if not Path(rel).is_absolute() else Path(rel)
        if not path.is_file():
            absent.append(rel)
    if absent:
        return {
            "admitted": parsed and False,
            "status": "REJECT",
            "digest_parsed": parsed,
            "digest_sha256": digest_sha,
            "absent_paths": absent,
            "message": "naive reject after parsing digest",
        }
    live = (root / contracted[0]).read_bytes()
    live_sha = hashlib.sha256(live).hexdigest()
    ok = digest_sha == live_sha
    return {
        "admitted": ok,
        "status": "ACCEPT" if ok else "REJECT",
        "digest_parsed": True,
        "digest_sha256": digest_sha,
        "absent_paths": [],
        "message": "naive accept/mismatch after parse",
    }


def main() -> int:
    src = SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    admit_fn = _fn(tree, "admit")
    check_fn = _fn(tree, "check_outputs_exist")
    parse_fn = _fn(tree, "_parse_digest")
    test_fn = _fn(tree, "test_path_leaf")
    if admit_fn is None or check_fn is None or parse_fn is None or test_fn is None:
        return _fail("admit/check_outputs_exist/_parse_digest/test_path_leaf missing")

    calls = call_names_with_lines(admit_fn)
    exist_lines = [ln for ln, name in calls if name == "check_outputs_exist"]
    parse_lines = [ln for ln, name in calls if name == "_parse_digest"]
    if not exist_lines:
        return _fail("admit() does not call check_outputs_exist")
    if not parse_lines:
        return _fail("admit() does not call _parse_digest")
    if min(exist_lines) >= min(parse_lines):
        return _fail(
            f"existence call line {min(exist_lines)} is not before parse line {min(parse_lines)}"
        )
    if "EXISTENCE-BEFORE-PARSE" not in src:
        return _fail("barrier lost the EXISTENCE-BEFORE-PARSE source marker")

    # _parse_digest must refuse unless existence_check is already in phases.
    parse_src = ast.get_source_segment(src, parse_fn) or ""
    if "existence check has not run" not in parse_src and "PHASE_EXIST not in phases" not in src:
        # The function body (not just a comment) must gate on PHASE_EXIST.
        parse_names = {
            n.id for n in ast.walk(parse_fn) if isinstance(n, ast.Name)
        }
        if "PHASE_EXIST" not in parse_names and "existence_check" not in parse_src:
            return _fail("_parse_digest does not gate on existence_check")

    prose = F.load_convincing_digest()
    absent_rel = F.ABSENT_PATH
    if (REPO / absent_rel).exists():
        return _fail(f"absent-oracle path unexpectedly exists: {absent_rel}")

    real = admit(REPO, [absent_rel], prose)
    naive = naive_parse_first(REPO, [absent_rel], prose)
    print(
        f"real digest_parsed={real['digest_parsed']} reason={real['reason_id']} "
        f"message_has_path={absent_rel in real['message']}"
    )
    print(
        f"naive digest_parsed={naive['digest_parsed']} admitted={naive['admitted']} "
        f"sha={naive.get('digest_sha256')}"
    )

    if real["admitted"] or real["reason_id"] != "absent-artifact":
        return _fail(f"real barrier did not reject absent path: {real}")
    if real["digest_parsed"]:
        return _fail("real barrier parsed digest for an absent path")
    if absent_rel not in real["message"]:
        return _fail(f"rejection message does not name {absent_rel!r}: {real['message']}")
    if absent_rel not in real["absent_paths"]:
        return _fail("absent_paths does not list the contracted path")
    if not naive["digest_parsed"]:
        return _fail("parse-first mutant did not parse the convincing digest")
    if naive.get("digest_sha256") is None:
        return _fail("parse-first mutant did not extract sha256")
    if naive["admitted"]:
        return _fail("parse-first mutant admitted an absent path")

    # Message-name control: a different absent path must appear in the message.
    other = "command-center/receipts/TST-0005-OTHER-ABSENT.json"
    other_v = admit(REPO, [other], prose)
    if other not in other_v["message"] or absent_rel in other_v["message"]:
        return _fail(f"message does not track the contracted path: {other_v['message']}")

    exist_line = min(exist_lines)
    parse_line = min(parse_lines)
    doc = {
        "ast_existence_line": exist_line,
        "ast_parse_line": parse_line,
        "ast_existence_before_parse": exist_line < parse_line,
        "naive_digest_parsed_on_absent": True,
        "real_digest_parsed_on_absent": False,
        "rejection_message": real["message"],
        "rejection_names_absent_path": True,
        "absent_path": absent_rel,
        "pass": True,
        "probe": "probe2-order-and-named-path",
        "unit_id": "TST-0005",
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"ast_ok=True exist_line={exist_line} parse_line={parse_line} "
        f"named_path=True naive_parsed=True real_parsed=False"
    )
    print("SUCCESS:TST-0005-probe2 order-and-named-path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
