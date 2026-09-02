"""AUD-0055 skip/xfail census: AST extraction plus execute-after-unmark.

Probe 1 reads markers and blame age; it does not run tests.
Probe 2 copies a stratified sample to a scratch directory, strips the marker,
and executes the test body.

pytest is not required. A stdlib stub is injected only so fixture files that
`import pytest` can load on this tree.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0055"
OUT_REL = "command-center/audit/AUD-0055-skip-xfail-reason-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0055 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
FIXTURES = HERE / "fixtures"
SKIP_DIR_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    "dist",
    "build",
    "site-packages",
}
PREFILTER = (
    "skip",
    "xfail",
    "expectedFailure",
    "importorskip",
    "skipIf",
    "skipUnless",
    "xit(",
    "it.skip",
    "test.skip",
    "describe.skip",
    "test.todo",
)
MARK_LEAF = {
    "skip": "skip",
    "skipif": "skipif",
    "skipIf": "skipif",
    "skipUnless": "skipif",
    "xfail": "xfail",
    "expectedFailure": "xfail",
    "importorskip": "skip",
}
TEMP_RE = re.compile(
    r"\b(temp(orary|orarily)?|for now|wip|todo|fixme|until fixed|pending rewrite)\b",
    re.I,
)
DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
JS_SKIP_RE = re.compile(
    r"\b(it\.skip|xit|test\.skip|describe\.skip|test\.todo|xdescribe)\s*\(",
)
CONTROL_FUNCS = {
    "test_aud0055_stale_xfail_arithmetic_fixed": "stale-xfail-bug-fixed",
    "test_aud0055_still_broken_zero_div": "live-xfail-bug-present",
    "test_aud0055_masquerade_skip_would_pass": "masquerade-temporary-skip",
    "test_aud0055_skipif_always_would_pass": "skipif-true-unconditional",
    "test_aud0055_clean_no_marker": "clean-no-marker",
}


class _Skip(Exception):
    """Raised by the pytest.skip stub during body exec."""


def _ensure_pytest_stub() -> None:
    if "pytest" in sys.modules:
        return
    pytest = types.ModuleType("pytest")

    def _identity(*args: Any, **kwargs: Any) -> Any:
        def deco(fn: Any) -> Any:
            return fn

        if args and callable(args[0]) and not kwargs and len(args) == 1:
            return args[0]
        return deco

    class _Mark:
        skip = staticmethod(_identity)
        skipif = staticmethod(_identity)
        xfail = staticmethod(_identity)

    pytest.mark = _Mark()

    def skip(reason: str = "", **_k: Any) -> None:
        raise _Skip(reason)

    def xfail(reason: str = "", **_k: Any) -> None:
        raise _Skip(reason)

    def importorskip(mod: str, *_a: Any, **_k: Any) -> Any:
        raise _Skip(f"importorskip:{mod}")

    pytest.skip = skip
    pytest.xfail = xfail
    pytest.importorskip = importorskip
    sys.modules["pytest"] = pytest


def _chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    parts.reverse()
    return parts


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _kw_str(keywords: list[ast.keyword], name: str) -> str | None:
    for kw in keywords:
        if kw.arg == name:
            return _const_str(kw.value)
    return None


def _reason_from_call(call: ast.Call, kind: str) -> str | None:
    reason = _kw_str(call.keywords, "reason")
    if reason:
        return reason
    if kind in {"skip", "xfail"} and call.args:
        return _const_str(call.args[0])
    return None


def _decorator_marker(dec: ast.AST) -> dict | None:
    call = dec if isinstance(dec, ast.Call) else None
    target = call.func if call is not None else dec
    chain = _chain(target)
    if not chain:
        return None
    leaf = chain[-1]
    if leaf not in MARK_LEAF:
        return None
    if not (
        "pytest" in chain
        or "unittest" in chain
        or "mark" in chain
        or leaf in {"skipIf", "skipUnless", "expectedFailure"}
    ):
        return None
    kind = MARK_LEAF[leaf]
    reason = None
    condition_source = None
    if call is not None:
        reason = _reason_from_call(call, kind)
        if kind == "skipif" and call.args:
            try:
                condition_source = ast.unparse(call.args[0])
            except Exception:
                condition_source = None
    return {
        "kind": kind,
        "reason": reason,
        "condition_source": condition_source,
        "decorator_chain": ".".join(chain),
        "style": "decorator",
    }


def _call_marker(call: ast.Call) -> dict | None:
    chain = _chain(call.func)
    if not chain:
        return None
    leaf = chain[-1]
    if leaf not in {"skip", "xfail", "importorskip"}:
        return None
    if "pytest" not in chain and chain not in (["skip"], ["xfail"]):
        if leaf != "importorskip":
            return None
    kind = MARK_LEAF.get(leaf, "skip")
    reason = _reason_from_call(call, kind)
    if leaf == "importorskip" and call.args:
        mod = _const_str(call.args[0])
        reason = reason or (f"importorskip {mod}" if mod else "importorskip")
    return {
        "kind": kind,
        "reason": reason,
        "condition_source": None,
        "decorator_chain": ".".join(chain),
        "style": "runtime-call",
    }


def eval_skipif(condition_source: str | None) -> bool | None:
    if not condition_source:
        return None
    try:
        tree = ast.parse(condition_source, mode="eval")
    except SyntaxError:
        return None
    allowed = {"True", "False", "None", "sys", "os"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in allowed:
            return None
    try:
        val = eval(  # noqa: S307 — restricted names only
            compile(tree, "<skipif>", "eval"),
            {"__builtins__": {}},
            {"True": True, "False": False, "None": None, "sys": sys, "os": os},
        )
        return bool(val)
    except Exception:
        return None


def _in_fixtures(rel: str) -> bool:
    posix = rel.replace("\\", "/")
    return posix.startswith("command-center/p2-wave/probes/AUD-0055/fixtures/")


def extract_markers_from_source(source: str, rel: str) -> list[dict]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [
            {
                "path": rel,
                "function": None,
                "lineno": getattr(exc, "lineno", 1) or 1,
                "kind": "parse-error",
                "reason": f"{exc}",
                "style": "parse-error",
                "control": False,
                "control_id": None,
                "in_aud0055_fixtures": _in_fixtures(rel),
                "condition_source": None,
                "condition_true": None,
            }
        ]
    rows: list[dict] = []

    def add(owner: ast.AST, info: dict, function: str | None) -> None:
        lineno = int(getattr(owner, "lineno", 1) or 1)
        control_id = CONTROL_FUNCS.get(function or "")
        cond = info.get("condition_source")
        cond_true = eval_skipif(cond) if info.get("kind") == "skipif" else None
        rows.append(
            {
                "path": rel,
                "function": function,
                "lineno": lineno,
                "kind": info["kind"],
                "reason": info.get("reason"),
                "condition_source": cond,
                "condition_true": cond_true,
                "decorator_chain": info.get("decorator_chain"),
                "style": info.get("style"),
                "control": bool(control_id),
                "control_id": control_id,
                "in_aud0055_fixtures": _in_fixtures(rel),
            }
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                info = _decorator_marker(dec)
                if info:
                    add(dec, info, node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for stmt in node.body:
                    for child in ast.walk(stmt):
                        if isinstance(child, ast.Call):
                            info = _call_marker(child)
                            if info:
                                add(child, info, node.name)
    return rows


def _should_skip_dir(path: Path) -> bool:
    return any(part in SKIP_DIR_PARTS for part in path.parts)


def cheap_hit(text: str) -> bool:
    return any(tok in text for tok in PREFILTER)


def blame_age(rel: str, lineno: int) -> dict:
    git_dir = REPO / ".git"
    if not git_dir.exists():
        return {
            "status": "NOT-CHECKED",
            "age_days": None,
            "author_time": None,
            "reason": "no .git directory in this worktree; git blame cannot run",
        }
    try:
        proc = subprocess.run(
            [
                "git",
                "blame",
                "-L",
                f"{lineno},{lineno}",
                "--line-porcelain",
                "--",
                rel,
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "NOT-CHECKED",
            "age_days": None,
            "author_time": None,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    if proc.returncode != 0:
        return {
            "status": "NOT-CHECKED",
            "age_days": None,
            "author_time": None,
            "reason": (proc.stderr or proc.stdout or "git blame failed")[:400],
        }
    author_time = None
    for line in (proc.stdout or "").splitlines():
        if line.startswith("author-time "):
            try:
                author_time = int(line.split()[1])
            except (IndexError, ValueError):
                author_time = None
            break
    if author_time is None:
        return {
            "status": "NOT-CHECKED",
            "age_days": None,
            "author_time": None,
            "reason": "git blame lacked author-time",
        }
    age_days = int((datetime.now(timezone.utc).timestamp() - author_time) // 86400)
    return {
        "status": "ok",
        "age_days": age_days,
        "author_time": author_time,
        "reason": None,
    }


def collect_python_markers() -> list[dict]:
    rows: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(REPO, followlinks=False):
        p = Path(dirpath)
        if _should_skip_dir(p):
            dirnames[:] = []
            continue
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIR_PARTS and not d.startswith(".")
        ]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            fp = p / name
            if fp.is_symlink():
                continue
            try:
                raw = fp.read_bytes()
            except OSError:
                continue
            if b"\x00" in raw[:4096]:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
            rel = fp.relative_to(REPO).as_posix()
            if fp.parent == FIXTURES or cheap_hit(text):
                rows.extend(extract_markers_from_source(text, rel))
    for row in rows:
        row["blame"] = blame_age(row["path"], int(row.get("lineno") or 1))
    rows.sort(
        key=lambda r: (
            r.get("path") or "",
            int(r.get("lineno") or 0),
            r.get("function") or "",
        )
    )
    return rows


def collect_js_candidates() -> list[dict]:
    rows: list[dict] = []
    suffixes = {".js", ".ts", ".mjs", ".cjs", ".tsx", ".jsx"}
    for dirpath, dirnames, filenames in os.walk(REPO, followlinks=False):
        p = Path(dirpath)
        if _should_skip_dir(p):
            dirnames[:] = []
            continue
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIR_PARTS and not d.startswith(".")
        ]
        for name in filenames:
            fp = p / name
            if fp.suffix not in suffixes or fp.is_symlink():
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not cheap_hit(text):
                continue
            rel = fp.relative_to(REPO).as_posix()
            for i, line in enumerate(text.splitlines(), 1):
                if JS_SKIP_RE.search(line):
                    rows.append(
                        {
                            "path": rel,
                            "lineno": i,
                            "kind": "js-skip-lexical",
                            "reason": line.strip()[:240],
                            "style": "lexical",
                            "control": False,
                            "in_aud0055_fixtures": False,
                            "blame": blame_age(rel, i),
                        }
                    )
    return rows


def strip_skip_xfail(source: str) -> str:
    tree = ast.parse(source)

    class Transformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
            self.generic_visit(node)
            node.decorator_list = [
                d for d in node.decorator_list if _decorator_marker(d) is None
            ]
            return node

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
            self.generic_visit(node)
            node.decorator_list = [
                d for d in node.decorator_list if _decorator_marker(d) is None
            ]
            return node

        def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
            self.generic_visit(node)
            node.decorator_list = [
                d for d in node.decorator_list if _decorator_marker(d) is None
            ]
            return node

        def visit_Expr(self, node: ast.Expr) -> ast.AST:
            if isinstance(node.value, ast.Call) and _call_marker(node.value):
                return ast.Pass()
            return self.generic_visit(node)

    new_tree = Transformer().visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


def execute_function(source: str, func_name: str, filename: str) -> dict:
    _ensure_pytest_stub()
    ns: dict[str, Any] = {"__name__": "aud0055_exec", "__file__": filename}
    try:
        exec(compile(source, filename, "exec"), ns, ns)  # noqa: S102
    except _Skip as exc:
        return {"outcome": "SKIP", "error": str(exc), "executed": False}
    except Exception as exc:
        return {
            "outcome": "LOAD-FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "executed": False,
        }
    fn = ns.get(func_name)
    if not callable(fn):
        return {
            "outcome": "LOAD-FAIL",
            "error": f"function {func_name} missing after exec",
            "executed": False,
        }
    try:
        fn()
        return {"outcome": "PASS", "error": None, "executed": True}
    except _Skip as exc:
        return {"outcome": "SKIP", "error": str(exc), "executed": True}
    except Exception as exc:
        return {
            "outcome": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "executed": True,
        }


def run_marked_and_unmarked(marker: dict, source: str) -> dict:
    func = marker.get("function")
    if not func:
        return {
            "path": marker["path"],
            "function": None,
            "executed": False,
            "unmarked_executed": False,
            "marked_outcome": "NOT-RUN",
            "unmarked_outcome": "NOT-RUN",
            "reason": "no function name",
        }
    kind = marker.get("kind")
    cond_true = marker.get("condition_true")
    with tempfile.TemporaryDirectory(prefix="aud0055-") as tmp:
        scratch = Path(tmp) / Path(marker["path"]).name
        unmarked_src = strip_skip_xfail(source)
        scratch.write_text(unmarked_src, encoding="utf-8")
        unmarked = execute_function(unmarked_src, func, str(scratch))
        if kind == "skip" or (kind == "skipif" and cond_true is True):
            marked_outcome = "SKIP"
            marked_executed = False
            marked_error = "honored-marker-without-calling-body"
        elif kind == "xfail":
            marked = execute_function(source, func, str(scratch) + ".marked")
            if marked["outcome"] == "PASS":
                marked_outcome = "XPASS"
            elif marked["outcome"] == "FAIL":
                marked_outcome = "XFAIL"
            else:
                marked_outcome = marked["outcome"]
            marked_executed = marked["executed"]
            marked_error = marked["error"]
        else:
            marked = execute_function(source, func, str(scratch) + ".marked")
            marked_outcome = marked["outcome"]
            marked_executed = marked["executed"]
            marked_error = marked["error"]
        return {
            "path": marker["path"],
            "function": func,
            "kind": kind,
            "control_id": marker.get("control_id"),
            "reason": marker.get("reason"),
            "scratch_dir": tmp,
            "scratch_is_git_worktree": False,
            "scratch_note": (
                "temp copy; git worktree not used (git checkout forbidden; "
                ".git absent on this tree)"
            ),
            "marked_outcome": marked_outcome,
            "marked_executed": marked_executed,
            "marked_error": marked_error,
            "unmarked_outcome": unmarked["outcome"],
            "unmarked_executed": unmarked["executed"],
            "unmarked_error": unmarked["error"],
            "executed": bool(unmarked["executed"] or marked_executed),
            "reason_still_holds": (
                True
                if unmarked["outcome"] == "FAIL"
                else False
                if unmarked["outcome"] == "PASS"
                else None
            ),
        }


def stratified_sample(markers: list[dict]) -> list[dict]:
    sample: list[dict] = []
    seen: set[tuple] = set()

    def take(row: dict) -> None:
        key = (row.get("path"), row.get("function"), row.get("lineno"), row.get("kind"))
        if key in seen:
            return
        seen.add(key)
        sample.append(row)

    for row in markers:
        if row.get("control") and row.get("kind") in {"skip", "skipif", "xfail"}:
            take(row)
    by_kind: dict[str, list[dict]] = {"skip": [], "skipif": [], "xfail": []}
    for row in markers:
        if row.get("in_aud0055_fixtures"):
            continue
        if row.get("kind") in by_kind:
            by_kind[row["kind"]].append(row)
    for _kind, rows in by_kind.items():
        if rows:
            take(rows[0])
    return sample


def classify_masquerade(marker: dict, unmark: dict | None) -> dict:
    reason = marker.get("reason") or ""
    kind = marker.get("kind")
    cond = marker.get("condition_source")
    notes: list[str] = []
    masquerade = False
    if kind == "skipif" and cond == "True":
        masquerade = True
        notes.append("skipif(True) is an unconditional skip")
    if not reason and kind in {"skip", "skipif", "xfail"}:
        masquerade = True
        notes.append("missing reason string")
    if TEMP_RE.search(reason) and not DATE_RE.search(reason):
        notes.append("temporary language without an expiry date")
        if unmark and unmark.get("unmarked_outcome") == "PASS":
            masquerade = True
            notes.append("unmarked body PASSES — skip is not protecting a failure")
        elif unmark is None:
            masquerade = True
    if (
        kind == "xfail"
        and unmark
        and unmark.get("unmarked_outcome") == "PASS"
        and unmark.get("marked_outcome") == "XPASS"
    ):
        masquerade = True
        notes.append("xfail whose bug is already fixed (XPASS marked, PASS unmarked)")
    expiry = DATE_RE.search(reason)
    return {
        "permanent_masquerading_as_temporary": masquerade,
        "has_reason": bool(reason),
        "has_expiry_date": bool(expiry),
        "expiry": expiry.group(0) if expiry else None,
        "notes": notes,
    }


def run_unmark_campaign(markers: list[dict]) -> dict:
    sample = stratified_sample(markers)
    results = []
    for marker in sample:
        if marker.get("kind") not in {"skip", "skipif", "xfail"}:
            continue
        source = (REPO / marker["path"]).read_text(encoding="utf-8")
        result = run_marked_and_unmarked(marker, source)
        result["masquerade"] = classify_masquerade(marker, result)
        results.append(result)
    executed = [r for r in results if r.get("executed")]
    stale_xfail = [
        r
        for r in results
        if r.get("kind") == "xfail"
        and r.get("unmarked_outcome") == "PASS"
        and r.get("marked_outcome") == "XPASS"
    ]
    justified = [r for r in results if r.get("unmarked_outcome") == "FAIL"]
    masquerades = [
        r
        for r in results
        if (r.get("masquerade") or {}).get("permanent_masquerading_as_temporary")
    ]
    control_stale = next(
        (r for r in results if r.get("control_id") == "stale-xfail-bug-fixed"),
        None,
    )
    control_live = next(
        (r for r in results if r.get("control_id") == "live-xfail-bug-present"),
        None,
    )
    control_ok = bool(
        control_stale
        and control_stale.get("marked_outcome") == "XPASS"
        and control_stale.get("unmarked_outcome") == "PASS"
        and control_stale.get("unmarked_executed") is True
        and control_live
        and control_live.get("marked_outcome") == "XFAIL"
        and control_live.get("unmarked_outcome") == "FAIL"
        and control_live.get("unmarked_executed") is True
    )
    return {
        "sample_size": len(results),
        "executed_count": len(executed),
        "stale_xfail_count": len(stale_xfail),
        "still_justified_count": len(justified),
        "masquerade_count": len(masquerades),
        "control_ok": control_ok,
        "control_stale_xfail": control_stale,
        "control_live_xfail": control_live,
        "results": results,
    }


def clean_control_silent() -> dict:
    rel = "command-center/p2-wave/probes/AUD-0055/fixtures/test_clean_control.py"
    source = (REPO / rel).read_text(encoding="utf-8")
    marks = [
        m
        for m in extract_markers_from_source(source, rel)
        if m.get("kind") in {"skip", "skipif", "xfail"}
    ]
    body = execute_function(source, "test_aud0055_clean_no_marker", str(REPO / rel))
    return {
        "path": rel,
        "markers_found": marks,
        "silent_on_clean": marks == [],
        "body": body,
    }


def census() -> dict:
    py = collect_python_markers()
    js = collect_js_candidates()
    real = [m for m in py if m.get("kind") in {"skip", "skipif", "xfail"}]
    fixtures = [m for m in real if m.get("in_aud0055_fixtures")]
    live = [m for m in real if not m.get("in_aud0055_fixtures")]
    missing_reason = [m for m in real if not m.get("reason")]
    unmark = run_unmark_campaign(real)
    clean = clean_control_silent()
    kinds = {"skip": 0, "skipif": 0, "xfail": 0}
    for m in real:
        kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
    headline = {
        "python_skip_xfail_markers": len(real),
        "live_tree_outside_aud0055_fixtures": len(live),
        "control_fixture_markers": len(fixtures),
        "skip": kinds["skip"],
        "skipif": kinds["skipif"],
        "xfail": kinds["xfail"],
        "missing_reason": len(missing_reason),
        "js_lexical_skip_candidates": len(js),
        "stale_xfail_confirmed_by_unmark": unmark["stale_xfail_count"],
        "still_justified_confirmed_by_unmark": unmark["still_justified_count"],
        "permanent_masquerading_as_temporary": unmark["masquerade_count"],
        "sample_executed": unmark["executed_count"],
        "git_blame": "NOT-CHECKED" if not (REPO / ".git").exists() else "attempted",
    }
    return {
        "headline": headline,
        "markers": real,
        "js_candidates": js,
        "unmark": unmark,
        "clean_control": clean,
        "control_ok": unmark["control_ok"] and clean["silent_on_clean"],
    }


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_path() -> Path:
    return REPO / OUT_REL


def load_artifact() -> dict:
    path = artifact_path()
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise ValueError("artifact is not an object")
    return doc
