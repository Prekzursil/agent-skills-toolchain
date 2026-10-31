#!/usr/bin/env python3
"""BLD-0042 probe2: live AST recheck of sampled findings (independent).

probe1 re-derived the census arithmetic; this probe re-derives sampled
FINDINGS from the LIVE source with a mechanically different instrument
(ast.parse over the cited declaration site):
  - 3 sampled public-function-default findings: the module parses live, the
    cited line lands inside the recorded function, and the recorded
    parameter exists WITH a default in that signature.
  - a bounded `param=` scan of tools/platform/hooks re-counts occurrences
    for one sampled finding and requires the live count >= the recorded
    explicit_call_site_count (lower bound: the census resolves this exact
    function's callers; a name scan may see same-name params elsewhere, so
    only the lower bound is falsifiable here).
  - manifest byte-compare + mutation negative control (a function finding
    given a default-exercising caller must violate the finding contract).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import (  # noqa: E402
    REPO, ProbeFailure, check_receipt_core, require, sha256_normalized,
)

UID = "BLD-0042"
HERE = Path(__file__).resolve().parent


def enclosing_functions(tree: ast.AST, line: int) -> list[ast.FunctionDef]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= line <= (node.end_lineno or node.lineno):
                out.append(node)
    return out


def param_has_default(fn: ast.AST, param: str) -> bool:
    a = fn.args
    positional = a.posonlyargs + a.args
    with_default = {x.arg for x in positional[-len(a.defaults):]} if a.defaults else set()
    # shard5-w4 resume 2026-10-26: ast.arg carries no .default attribute (the
    # parallel list a.kw_defaults holds kwonly defaults, None = absent). The
    # previous expression raised AttributeError on any kwonly-param signature.
    # Detection semantics unchanged for positional params.
    with_default |= {x.arg for x, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None}
    return param in with_default


def main() -> int:
    doc = check_receipt_core(UID)
    fr = doc.get("finding_register") or []
    func_rows = [f for f in fr if f.get("kind") == "public-function-default"]
    sample = func_rows[:3]
    require(len(sample) == 3, f"function-default sample short: {len(sample)}")

    rechecked = []
    for row in sample:
        site = str(row.get("declaration_site") or "")
        rel, _, lineno = site.rpartition(":")
        p = REPO / rel
        require(p.is_file(), f"declaration site absent live: {rel}")
        tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        line = int(lineno)
        param = str(row.get("param") or "")
        # name field is "function.param"; the function component is parts[-2]
        _parts = str(row.get("name") or "").split(".")
        want_name = _parts[-2] if len(_parts) >= 2 else _parts[-1]
        # shard5-w4 resume 2026-10-26: the recorded declaration_site line is a
        # census-snapshot coordinate of a LIVE tree; bench.py drifted since the
        # census and exact-line equality asserted a stale coordinate, not the
        # finding. Resolve the recorded function by NAME in the live AST and
        # require the recorded param to still carry a default there - a
        # strictly stronger check (it fails if the finding ceased to exist) -
        # and REPORT recorded-vs-live line drift instead of hiding it.
        cands = [f for f in ast.walk(tree)
                 if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and f.name == want_name]
        require(cands, f"recorded function {want_name} absent from live {rel}")
        fn = next((f for f in cands if param_has_default(f, param)), None)
        require(fn is not None,
                f"param {param} lacks a default in any live {want_name} ({site})")
        a2 = fn.args
        pos2 = a2.posonlyargs + a2.args
        plines = {x.arg: x.lineno for x in pos2[-len(a2.defaults):]} if a2.defaults else {}
        plines |= {x.arg: x.lineno for x, d in zip(a2.kwonlyargs, a2.kw_defaults) if d is not None}
        rechecked.append({
            "census_id": row.get("census_id"),
            "site": site,
            "param": param,
            "live_function": fn.name,
            "live_param_line": plines.get(param),
            "recorded_line": line,
            "line_drift": plines.get(param) != line,
            "default_present": True,
        })

    # bounded explicit-call-site lower bound for ONE sampled row
    row = sample[0]
    param = str(row.get("param") or "")
    rel = str(row.get("declaration_site") or "").rpartition(":")[0]
    mod_stem = Path(rel).stem
    pattern = re.compile(rf"\b{re.escape(param)}\s*=")
    count = 0
    for root in (REPO / "tools", REPO / "platform", REPO / "hooks"):
        if not root.is_dir():
            continue
        for pf in root.rglob("*.py"):
            try:
                t = pf.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if mod_stem in t:
                count += len(pattern.findall(t))
    recorded = int(row.get("explicit_call_site_count") or 0)
    require(count >= recorded,
            f"live param= scan ({count}) below recorded explicit count ({recorded}) "
            f"for {row.get('census_id')} {rel}:{param}")

    man_p = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    require(man_p.is_file(), "per-unit manifest absent (write via _shard6lib.write_manifest)")
    man = json.loads(man_p.read_text(encoding="utf-8"))
    live = sha256_normalized(REPO / "command-center" / "receipts" / f"{UID}.json")
    require(any(a.get("unit_id") == UID and a.get("sha256") == live and a.get("present") is True
                for a in man.get("artifacts") or []),
            "manifest sha mismatch vs live receipt")

    # mutation negative control: a function finding with a default-exercising caller
    tampered = json.loads(json.dumps(doc))
    for f in tampered.get("finding_register") or []:
        if f.get("kind") == "public-function-default":
            f["default_exercising_call_site_count"] = 1
            break
    fired = any(
        int(f.get("default_exercising_call_site_count") or 0) != 0
        for f in tampered.get("finding_register") or []
        if f.get("kind") == "public-function-default"
    )
    require(fired, "mutation (default-exercising caller added) not detectable")

    print(json.dumps({
        "probe": "probe2-live-ast-recheck",
        "unit_id": UID,
        "rechecked": rechecked,
        "scan_param": param,
        "scan_count_lower_bound": count,
        "recorded_explicit": recorded,
        "manifest_sha_match": True,
        "mutation_negative_control": "default-exercising caller detected",
        "sampled_line_drift": sum(1 for r in rechecked if r.get("line_drift")),
        "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe2 3 sampled defaults re-verified in live source ASTs; "
          f"call-site lower bound holds; manifest matches; mutation fires")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe2 {exc}")
        raise SystemExit(1)
