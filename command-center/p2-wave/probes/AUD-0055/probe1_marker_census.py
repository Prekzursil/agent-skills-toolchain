#!/usr/bin/env python3
"""AUD-0055 Probe 1: skip/xfail marker census with reason + git blame age.

Catalog evidence_requirement Probe 1:
  extract each marker with its reason and its git blame age.

Use-vs-mention: AST Call / decorator Attribute only. String/docstring mentions
in fixtures/mention_only_noise.py must not inflate the count.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-marker-census.json"
OUT_RAW = PROBE / "probe1-marker-census.raw.txt"

EXCLUDE_PARTS = {
    "node_modules",
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    "salvaged-at-risk",
    "salvaged-from-scratch",
    "_r2_tmp",
    "_av2_tmp",
}

# Other units' probe scratch is out of production census (AUD-0048 pattern).
OTHER_PROBE_RE = re.compile(r"command-center/p2-wave/probes/AUD-(?!0055)\d+/")

MARKER_ATTRS = {"skip", "skipif", "xfail"}
UNITTEST_ATTRS = {"skip", "skipIf", "skipUnless", "expectedFailure"}


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def in_scope(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_PARTS:
        return False
    r = rel(path)
    if OTHER_PROBE_RE.search(r):
        return False
    if r.startswith("command-center/p2-wave/_"):
        return False
    return path.suffix == ".py"


def _const_str(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):  # f-string — record as dynamic
        return "<f-string>"
    if isinstance(node, ast.Name):
        return f"<name:{node.id}>"
    if isinstance(node, ast.Attribute):
        return f"<attr:{ast.unparse(node) if hasattr(ast, 'unparse') else node.attr}>"
    if isinstance(node, ast.Call):
        return "<call>"
    return "<non-literal>"


def _reason_from_call(call: ast.Call) -> tuple[str | None, bool]:
    """Return (reason_text, reason_present)."""
    # positional: skipif(cond, reason) OR skip(reason) OR unittest.skip(reason)
    if call.args:
        # skipif: first arg is condition; reason is kw-only usually, but
        # unittest.skipUnless(cond, reason) has reason as 2nd positional.
        if len(call.args) >= 2:
            r = _const_str(call.args[1])
            if r is not None:
                return r, True
        elif len(call.args) == 1:
            # Could be reason for skip/xfail, or condition for skipif.
            # Prefer keyword reason when present.
            pass
    for kw in call.keywords:
        if kw.arg == "reason":
            r = _const_str(kw.value)
            return (r if r is not None else "<non-literal>"), True
    # bare @pytest.mark.skip with no reason
    if call.args and len(call.args) == 1:
        # For skip/xfail without kw, positional may be reason.
        r = _const_str(call.args[0])
        return (r if r is not None else "<non-literal>"), r is not None
    return None, False


def _attr_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    parts.reverse()
    return parts


def _classify_decorator(dec: ast.AST) -> dict | None:
    """Return marker dict for a decorator, or None."""
    call = dec if isinstance(dec, ast.Call) else None
    target = call.func if call else dec
    chain = _attr_chain(target)
    if not chain:
        return None

    kind = None
    family = None
    # Decorators: @pytest.mark.skip / skipif / xfail — not pytest.skip().
    if "mark" in chain and chain[-1] in MARKER_ATTRS:
        kind = chain[-1]
        family = "pytest.mark"
    elif chain[0] in {"unittest", "ut"} and chain[-1] in UNITTEST_ATTRS:
        kind = chain[-1]
        family = "unittest"
    else:
        return None

    reason = None
    reason_present = False
    if call is not None:
        reason, reason_present = _reason_from_call(call)
    else:
        # bare @pytest.mark.skip (Attribute, not Call)
        reason_present = False
        reason = None

    return {
        "kind": kind,
        "family": family,
        "reason": reason,
        "reason_present": reason_present,
        "form": "decorator",
    }


def _classify_assign_call(call: ast.Call) -> dict | None:
    """Classify marker constructors only (pytest.mark.* / unittest.*), not pytest.skip()."""
    chain = _attr_chain(call.func)
    if not chain:
        return None
    kind = None
    family = None
    # Require .mark. in the chain for pytest markers — excludes pytest.skip()/pytest.xfail().
    if "mark" in chain and chain[-1] in MARKER_ATTRS:
        kind = chain[-1]
        family = "pytest.mark"
    elif chain[0] in {"unittest", "ut"} and chain[-1] in UNITTEST_ATTRS:
        kind = chain[-1]
        family = "unittest"
    else:
        return None
    reason, reason_present = _reason_from_call(call)
    return {
        "kind": kind,
        "family": family,
        "reason": reason,
        "reason_present": reason_present,
        "form": "assignment-or-call",
    }


def extract_markers(path: Path) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return []

    found: list[dict] = []
    lines = src.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                info = _classify_decorator(dec)
                if info is None:
                    continue
                lineno = getattr(dec, "lineno", node.lineno)
                found.append(
                    {
                        **info,
                        "path": rel(path),
                        "lineno": lineno,
                        "target": node.name,
                        "line_text": lines[lineno - 1].strip()
                        if 0 < lineno <= len(lines)
                        else "",
                    }
                )
        elif isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Call):
                info = _classify_assign_call(node.value)
                if info is None:
                    continue
                lineno = node.value.lineno
                names = []
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.append(t.id)
                found.append(
                    {
                        **info,
                        "path": rel(path),
                        "lineno": lineno,
                        "target": ",".join(names) or "<assign>",
                        "line_text": lines[lineno - 1].strip()
                        if 0 < lineno <= len(lines)
                        else "",
                    }
                )
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            # module-level pytestmark = ... already via Assign; bare calls rare
            pass

    # pytestmark = pytest.mark.skipif(...) already covered by Assign.
    # Also catch: pytestmark = [pytest.mark.skip(...)]
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if not any(
                isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
            ):
                continue
            val = node.value
            elts = val.elts if isinstance(val, (ast.List, ast.Tuple)) else []
            for elt in elts:
                if isinstance(elt, ast.Call):
                    info = _classify_assign_call(elt)
                    if info is None:
                        continue
                    lineno = elt.lineno
                    found.append(
                        {
                            **info,
                            "path": rel(path),
                            "lineno": lineno,
                            "target": "pytestmark",
                            "line_text": lines[lineno - 1].strip()
                            if 0 < lineno <= len(lines)
                            else "",
                        }
                    )

    # Dynamic mark construction: pytest.mark.xfail(...) inside expressions/tuples.
    seen_lines = {(m["path"], m["lineno"]) for m in found}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        info = _classify_assign_call(node)
        if info is None:
            continue
        lineno = node.lineno
        key = (rel(path), lineno)
        if key in seen_lines:
            continue
        seen_lines.add(key)
        found.append(
            {
                **info,
                "path": rel(path),
                "lineno": lineno,
                "target": "<expr>",
                "line_text": lines[lineno - 1].strip()
                if 0 < lineno <= len(lines)
                else "",
                "form": "expression-call",
            }
        )
    return found


def git_blame_age(path: str, lineno: int) -> dict:
    """Return blame author/date/age_days for one line."""
    cmd = [
        "git",
        "-C",
        str(REPO),
        "blame",
        "-L",
        f"{lineno},{lineno}",
        "--line-porcelain",
        "--",
        path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": str(e)}
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout)[:200]}

    author = None
    author_time = None
    commit = None
    for line in proc.stdout.splitlines():
        if line.startswith("author ") and not line.startswith("author-"):
            author = line[len("author ") :]
        elif line.startswith("author-time "):
            try:
                author_time = int(line.split()[1])
            except (IndexError, ValueError):
                author_time = None
        elif re.match(r"^[0-9a-f]{40}", line):
            commit = line.split()[0]

    age_days = None
    iso = None
    if author_time is not None:
        dt = datetime.fromtimestamp(author_time, tz=timezone.utc)
        iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        age_days = (datetime.now(timezone.utc) - dt).days

    return {
        "ok": True,
        "commit": commit,
        "author": author,
        "author_time": author_time,
        "author_time_iso": iso,
        "age_days": age_days,
    }


def iter_py_files() -> list[Path]:
    files: list[Path] = []
    for p in REPO.rglob("*.py"):
        if not in_scope(p):
            continue
        files.append(p)
    # Always include our fixtures even if somehow filtered
    for p in (PROBE / "fixtures").glob("*.py"):
        if p not in files:
            files.append(p)
    return sorted(files, key=lambda x: rel(x))


def reason_validity_class(row: dict) -> str:
    """Heuristic label for census (Probe 2 settles a sample empirically)."""
    if not row.get("reason_present") or not row.get("reason"):
        return "no-reason"
    reason = str(row["reason"])
    if reason.startswith("<"):
        return "dynamic-reason"
    if "AUD-0055-CONTROL" in reason:
        if "still broken" in reason or "still required" in reason:
            return "control-planted"
        return "control-planted"
    # Permanent-looking language
    low = reason.lower()
    if any(
        w in low for w in ("permanently", "wontfix", "won't fix", "never", "deprecated")
    ):
        return "permanent-sounding"
    if any(w in low for w in ("todo", "temporary", "flaky", "interim", "until")):
        return "temporary-sounding"
    return "reason-present"


def main() -> int:
    files = iter_py_files()
    markers: list[dict] = []
    for f in files:
        for m in extract_markers(f):
            blame = git_blame_age(m["path"], m["lineno"])
            m["blame"] = blame
            m["reason_class"] = reason_validity_class(m)
            # scope flags
            r = m["path"]
            m["in_unit_fixtures"] = r.startswith(
                "command-center/p2-wave/probes/AUD-0055/fixtures/"
            )
            m["production_scope"] = not m["in_unit_fixtures"] and not r.startswith(
                "command-center/p13_suppression_census.py"
            )
            # p13 census file mentions patterns as strings — AST should not find decorators there
            markers.append(m)

    by_kind = Counter(m["kind"] for m in markers)
    by_family = Counter(m["family"] for m in markers)
    by_reason_class = Counter(m["reason_class"] for m in markers)
    prod = [m for m in markers if m["production_scope"]]
    fixtures = [m for m in markers if m["in_unit_fixtures"]]
    no_reason = [m for m in markers if m["reason_class"] == "no-reason"]
    ages = [
        m["blame"]["age_days"]
        for m in markers
        if m.get("blame", {}).get("age_days") is not None
    ]

    # Control checks
    mention_path = (
        "command-center/p2-wave/probes/AUD-0055/fixtures/mention_only_noise.py"
    )
    mention_hits = [m for m in markers if m["path"] == mention_path]
    xfail_ctrl = [
        m
        for m in fixtures
        if m["kind"] == "xfail"
        and m.get("reason")
        and "AUD-0055-CONTROL" in str(m["reason"])
    ]
    skip_ctrl = [
        m
        for m in fixtures
        if m["kind"] == "skip"
        and m.get("reason")
        and "AUD-0055-CONTROL" in str(m["reason"])
    ]
    control_ok = len(mention_hits) == 0 and len(xfail_ctrl) == 1 and len(skip_ctrl) == 1

    skip_count = sum(by_kind[k] for k in ("skip", "skipIf", "skipUnless", "skipif"))
    xfail_count = sum(by_kind[k] for k in ("xfail", "expectedFailure"))
    prod_skip = sum(
        1 for m in prod if m["kind"] in {"skip", "skipIf", "skipUnless", "skipif"}
    )
    prod_xfail = sum(1 for m in prod if m["kind"] in {"xfail", "expectedFailure"})

    doc = {
        "unit": "AUD-0055",
        "probe": 1,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files_scanned": len(files),
        "marker_count": len(markers),
        "skip_count": skip_count,
        "xfail_count": xfail_count,
        "production_marker_count": len(prod),
        "production_skip_count": prod_skip,
        "production_xfail_count": prod_xfail,
        "fixture_marker_count": len(fixtures),
        "no_reason_count": len(no_reason),
        "by_kind": dict(sorted(by_kind.items())),
        "by_family": dict(sorted(by_family.items())),
        "by_reason_class": dict(sorted(by_reason_class.items())),
        "age_days_min": min(ages) if ages else None,
        "age_days_max": max(ages) if ages else None,
        "age_days_median": sorted(ages)[len(ages) // 2] if ages else None,
        "control": {
            "ok": control_ok,
            "mention_only_hits": len(mention_hits),
            "xfail_fixed_control_found": len(xfail_ctrl) == 1,
            "skip_still_fails_control_found": len(skip_ctrl) == 1,
        },
        "markers": markers,
        "ok": control_ok and len(markers) > 0,
    }

    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw_lines = [
        "SUCCESS:AUD-0055-probe1" if doc["ok"] else "FAILED:AUD-0055-probe1",
        f"unit=AUD-0055 probe=1 files_scanned={len(files)}",
        f"marker_count={len(markers)} skip_count={skip_count} xfail_count={xfail_count}",
        f"production_skip={prod_skip} production_xfail={prod_xfail}",
        f"no_reason_count={len(no_reason)} by_kind={dict(by_kind)}",
        f"by_reason_class={dict(by_reason_class)}",
        f"age_days min={doc['age_days_min']} median={doc['age_days_median']} max={doc['age_days_max']}",
        f"control_ok={control_ok} mention_hits={len(mention_hits)} "
        f"xfail_ctrl={len(xfail_ctrl)} skip_ctrl={len(skip_ctrl)}",
        "--- markers (path:lineno kind reason age_days) ---",
    ]
    for m in markers:
        age = m.get("blame", {}).get("age_days")
        raw_lines.append(
            f"{m['path']}:{m['lineno']} {m['kind']} reason={m.get('reason')!r} "
            f"age_days={age} class={m['reason_class']} prod={m['production_scope']}"
        )
    OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    print(OUT_RAW.read_text(encoding="utf-8"))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
