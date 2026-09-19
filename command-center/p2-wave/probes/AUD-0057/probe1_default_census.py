#!/usr/bin/env python3
"""AUD-0057 NAMED PROBE 1: assertion-strength census of unexercised defaults.

Catalog evidence_requirement Probe 1:
  an AST pass computing, per parameter with a default, whether any test
  invokes the function without supplying it.

Use-vs-mention: only Call / kwargs-dict sites count. Strings in
fixtures/mention_only_noise.py must not inflate the census.

Planted control: planted_unexercised.threshold must be UNEXERCISED;
planted_exercised.threshold must be EXERCISED.
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-default-census.json"
OUT_RAW = PROBE / "probe1-default-census.raw.txt"

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

OTHER_PROBE_RE = re.compile(r"command-center/p2-wave/probes/AUD-(?!0057)\d+/")

# Production modules whose defaults are the scar class under census.
SOURCE_FILES = [
    "hooks/_shared/completion.py",
    "tools/mutation-gate/sample/threshold.py",
    "tools/monitorcore/monitorcore/dbx_completion.py",
    "skills/workflow-foundry/scripts/receipt_gate.py",
    ".agents/skills/workflow-foundry/scripts/receipt_gate.py",
    "command-center/p2-wave/probes/AUD-0057/fixtures/planted_defaults.py",
]

# Test / caller files that may exercise those defaults.
TEST_GLOBS = [
    "hooks/_shared/test_*.py",
    "tools/mutation-gate/sample/test_*.py",
    "tools/monitorcore/tests/test_dbx_completion.py",
    "skills/workflow-foundry/**/test_*.py",
    ".agents/skills/workflow-foundry/**/test_*.py",
    "command-center/p2-wave/probes/AUD-0057/fixtures/test_*.py",
    "command-center/p2-wave/probes/AUD-0057/fixtures/mention_only_noise.py",
]

PLANTED_UNEX = ("planted_unexercised", "threshold")
PLANTED_EX = ("planted_exercised", "threshold")


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def in_scope(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    if set(path.parts) & EXCLUDE_PARTS:
        return False
    r = rel(path)
    if OTHER_PROBE_RE.search(r):
        return False
    return True


def _const_repr(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        try:
            return ast.unparse(node)
        except Exception:
            return node.attr
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def extract_defs(path: Path) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []

    found: list[dict] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        positional = list(args.posonlyargs) + list(args.args)
        defaults = list(args.defaults)
        if not defaults:
            # Still check kwonly defaults
            pass
        # Map defaults onto trailing positional params
        npos = len(positional)
        ndef = len(defaults)
        for i, default in enumerate(defaults):
            param = positional[npos - ndef + i]
            if param.arg in {"self", "cls"}:
                continue
            found.append(
                {
                    "func": node.name,
                    "param": param.arg,
                    "kind": "positional-or-keyword",
                    "default_repr": _const_repr(default),
                    "lineno": node.lineno,
                    "path": rel(path),
                    "param_index": npos - ndef + i,
                    "positional_count": npos,
                }
            )
        for kw, default in zip(args.kwonlyargs, args.kw_defaults):
            if default is None:
                continue
            if kw.arg in {"self", "cls"}:
                continue
            found.append(
                {
                    "func": node.name,
                    "param": kw.arg,
                    "kind": "kwonly",
                    "default_repr": _const_repr(default),
                    "lineno": node.lineno,
                    "path": rel(path),
                    "param_index": None,
                    "positional_count": npos,
                }
            )
    return found


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _dict_keys(d: ast.Dict) -> set[str]:
    keys: set[str] = set()
    for k in d.keys:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            keys.add(k.value)
    return keys


def _resolve_name_to_dict_keys(fn: ast.AST, name: str) -> list[set[str]]:
    """Best-effort: Assign/AnnAssign of Name = Dict in the same function."""
    out: list[set[str]] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if (
                isinstance(t, ast.Name)
                and t.id == name
                and isinstance(node.value, ast.Dict)
            ):
                out.append(_dict_keys(node.value))
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if (
                node.target.id == name
                and node.value is not None
                and isinstance(node.value, ast.Dict)
            ):
                out.append(_dict_keys(node.value))
    return out


def extract_call_sites(path: Path, target_funcs: set[str]) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []

    sites: list[dict] = []
    rpath = rel(path)

    # Data-driven kwargs packs (hooks/_shared/test_completion.py pattern).
    dict_packs: list[tuple[int, set[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = _dict_keys(node)
            if keys & {
                "min_bytes",
                "sentinel_tail",
                "threshold",
                "artifact",
                "sentinel",
                "exit_code",
                "detector_ok",
            }:
                dict_packs.append((getattr(node, "lineno", 0), keys))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name is None or name not in target_funcs:
            continue
        kw_names = {k.arg for k in node.keywords if k.arg}
        star_kwargs = [k for k in node.keywords if k.arg is None]
        n_pos = len(node.args)
        resolved_kw_sets: list[set[str]] = []
        if star_kwargs:
            for sk in star_kwargs:
                if isinstance(sk.value, ast.Name):
                    resolved = _resolve_name_to_dict_keys(tree, sk.value.id)
                    if resolved:
                        for keys in resolved:
                            resolved_kw_sets.append(kw_names | keys)
                    else:
                        resolved_kw_sets.append(kw_names | {"**opaque**"})
                elif isinstance(sk.value, ast.Dict):
                    resolved_kw_sets.append(kw_names | _dict_keys(sk.value))
                else:
                    resolved_kw_sets.append(kw_names | {"**opaque**"})
        else:
            resolved_kw_sets = [kw_names]
        for keys in resolved_kw_sets:
            sites.append(
                {
                    "func": name,
                    "path": rpath,
                    "lineno": getattr(node, "lineno", 0),
                    "n_positional": n_pos,
                    "keywords": sorted(k for k in keys if not k.startswith("**")),
                    "opaque_kwargs": "**opaque**" in keys,
                    "form": "call",
                }
            )

    # Inferred dict-kwargs for classify/artifact_* when **opaque packs exist.
    has_opaque_target = any(
        s["func"] in {"classify", "artifact_ok", "artifact_text_ok"}
        and s.get("opaque_kwargs")
        for s in sites
    )
    if has_opaque_target or any(
        s["func"] == "classify" and s["form"] == "call" for s in sites
    ):
        for lineno, keys in dict_packs:
            for fname in sorted(
                target_funcs & {"classify", "artifact_ok", "artifact_text_ok"}
            ):
                if not (
                    keys
                    & {
                        "min_bytes",
                        "sentinel",
                        "artifact",
                        "sentinel_tail",
                        "exit_code",
                    }
                ):
                    continue
                # Only attribute packs to classify when classify is called with **kwargs.
                if fname != "classify" and "artifact" not in keys:
                    continue
                if fname == "classify" and not any(
                    s["func"] == "classify" for s in sites
                ):
                    continue
                sites.append(
                    {
                        "func": fname,
                        "path": rpath,
                        "lineno": lineno,
                        "n_positional": 0,
                        "keywords": sorted(keys),
                        "opaque_kwargs": False,
                        "form": "inferred-dict-kwargs",
                    }
                )

    seen: set[tuple] = set()
    uniq: list[dict] = []
    for s in sites:
        sig = (
            s["func"],
            s["path"],
            s["lineno"],
            s["form"],
            tuple(s["keywords"]),
            s["n_positional"],
        )
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append(s)
    return uniq


def call_omits_param(site: dict, param: str, param_index: int | None) -> bool | None:
    """Return True if this call leaves the param to its default; False if supplied; None unknown."""
    if site.get("opaque_kwargs"):
        return None
    kws = set(site.get("keywords") or [])
    if param in kws:
        return False  # explicitly supplied
    if param_index is not None and site["n_positional"] > param_index:
        return False  # covered positionally
    # For kwonly or trailing defaults not covered by positionals:
    return True


def main() -> int:
    sources: list[Path] = []
    for rel_s in SOURCE_FILES:
        p = REPO / rel_s
        if p.is_file() and in_scope(p):
            sources.append(p)

    defs: list[dict] = []
    for p in sources:
        defs.extend(extract_defs(p))

    target_funcs = {d["func"] for d in defs}

    test_files: list[Path] = []
    for pattern in TEST_GLOBS:
        for p in REPO.glob(pattern):
            if p.is_file() and in_scope(p):
                test_files.append(p)
    # unique
    test_files = sorted({p.resolve() for p in test_files}, key=lambda x: rel(x))

    sites: list[dict] = []
    for p in test_files:
        sites.extend(extract_call_sites(p, target_funcs))

    # Index sites by func
    by_func: dict[str, list[dict]] = defaultdict(list)
    for s in sites:
        by_func[s["func"]].append(s)

    rows: list[dict] = []
    for d in defs:
        func_sites = by_func.get(d["func"], [])
        omit = 0
        supply = 0
        unknown = 0
        site_samples: list[dict] = []
        for s in func_sites:
            verdict = call_omits_param(s, d["param"], d["param_index"])
            if verdict is True:
                omit += 1
                if len(site_samples) < 5:
                    site_samples.append({**s, "omits_default": True})
            elif verdict is False:
                supply += 1
                if len(site_samples) < 5:
                    site_samples.append({**s, "omits_default": False})
            else:
                unknown += 1

        if omit > 0:
            status = "EXERCISED"
        elif supply > 0 and omit == 0:
            status = "UNEXERCISED"
        elif supply == 0 and omit == 0:
            status = "NO_CALLERS"
        else:
            status = "UNKNOWN"

        # Risk: DEFAULT_* / min_bytes / threshold / planted
        risk = "low"
        dr = d["default_repr"] or ""
        if (
            d["param"] in {"min_bytes", "threshold", "sentinel_tail"}
            or dr.startswith("DEFAULT_")
            or "PLANTED_" in dr
        ):
            risk = "high" if status == "UNEXERCISED" else "medium"

        planted = None
        if (d["func"], d["param"]) == PLANTED_UNEX:
            planted = "unexercised-control"
        elif (d["func"], d["param"]) == PLANTED_EX:
            planted = "exercised-control"

        rows.append(
            {
                **d,
                "call_site_count": len(func_sites),
                "omit_count": omit,
                "supply_count": supply,
                "unknown_count": unknown,
                "status": status,
                "risk": risk,
                "planted": planted,
                "site_samples": site_samples,
            }
        )

    unexercised = [r for r in rows if r["status"] == "UNEXERCISED"]
    exercised = [r for r in rows if r["status"] == "EXERCISED"]
    no_callers = [r for r in rows if r["status"] == "NO_CALLERS"]
    high_unex = [r for r in unexercised if r["risk"] == "high"]

    # Suite-local holes: a single test file that always supplies a high-risk default
    # even when the global census shows EXERCISED (the DEFAULT_MIN_BYTES weak-suite scar).
    suite_holes: list[dict] = []
    high_risk_defs = [
        r
        for r in rows
        if r["param"] in {"min_bytes", "threshold", "sentinel_tail"}
        or (r["default_repr"] or "").startswith(("DEFAULT_", "PLANTED_"))
    ]
    for d in high_risk_defs:
        by_file: dict[str, dict[str, int]] = defaultdict(
            lambda: {"omit": 0, "supply": 0}
        )
        for s in by_func.get(d["func"], []):
            v = call_omits_param(s, d["param"], d["param_index"])
            if v is True:
                by_file[s["path"]]["omit"] += 1
            elif v is False:
                by_file[s["path"]]["supply"] += 1
        for fpath, counts in sorted(by_file.items()):
            if counts["supply"] > 0 and counts["omit"] == 0:
                suite_holes.append(
                    {
                        "test_file": fpath,
                        "func": d["func"],
                        "param": d["param"],
                        "default_repr": d["default_repr"],
                        "def_path": d["path"],
                        "supply_count": counts["supply"],
                        "global_status": d["status"],
                    }
                )

    # Planted controls
    planted_unex_row = next(
        (r for r in rows if r.get("planted") == "unexercised-control"), None
    )
    planted_ex_row = next(
        (r for r in rows if r.get("planted") == "exercised-control"), None
    )
    planted_unex_ok = (
        planted_unex_row is not None and planted_unex_row["status"] == "UNEXERCISED"
    )
    planted_ex_ok = (
        planted_ex_row is not None and planted_ex_row["status"] == "EXERCISED"
    )
    planted_weak_hole = any(
        h["test_file"].endswith("test_planted_weak.py")
        and h["func"] == "planted_unexercised"
        for h in suite_holes
    )
    sample_weak_hole = any(
        h["test_file"].endswith("test_threshold_weak.py")
        and h["func"] == "is_large_enough"
        for h in suite_holes
    )

    # Use-vs-mention: noise file must contribute zero Call-form sites
    mention_hits = sum(
        1
        for s in sites
        if s["path"].endswith("mention_only_noise.py") and s["form"] == "call"
    )

    control_ok = (
        planted_unex_ok
        and planted_ex_ok
        and mention_hits == 0
        and planted_weak_hole
        and sample_weak_hole
    )

    doc = {
        "unit": "AUD-0057",
        "probe": 1,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": control_ok,
        "source_file_count": len(sources),
        "source_files": [rel(p) for p in sources],
        "test_file_count": len(test_files),
        "defs_with_defaults": len(rows),
        "unexercised_count": len(unexercised),
        "exercised_count": len(exercised),
        "no_callers_count": len(no_callers),
        "high_risk_unexercised_count": len(high_unex),
        "suite_local_hole_count": len(suite_holes),
        "call_site_count": len(sites),
        "control": {
            "ok": control_ok,
            "planted_unexercised_status": (planted_unex_row or {}).get("status"),
            "planted_exercised_status": (planted_ex_row or {}).get("status"),
            "planted_unexercised_ok": planted_unex_ok,
            "planted_exercised_ok": planted_ex_ok,
            "planted_weak_suite_hole": planted_weak_hole,
            "sample_weak_suite_hole": sample_weak_hole,
            "mention_only_call_hits": mention_hits,
            "note": (
                "Planted hole must be UNEXERCISED; planted covered default must be "
                "EXERCISED; weak suites (planted + mutation-gate sample) must appear "
                "as suite-local holes; mention_only_noise.py must contribute zero Calls."
            ),
        },
        "high_risk_unexercised": [
            {
                "func": r["func"],
                "param": r["param"],
                "path": r["path"],
                "lineno": r["lineno"],
                "default_repr": r["default_repr"],
                "supply_count": r["supply_count"],
                "omit_count": r["omit_count"],
            }
            for r in high_unex
        ],
        "suite_local_holes": suite_holes,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0057 NAMED PROBE 1: assertion-strength default-exercise census",
        "unit=AUD-0057",
        f"source_file_count={len(sources)}",
        f"test_file_count={len(test_files)}",
        f"defs_with_defaults={len(rows)}",
        f"unexercised_count={len(unexercised)}",
        f"exercised_count={len(exercised)}",
        f"no_callers_count={len(no_callers)}",
        f"high_risk_unexercised_count={len(high_unex)}",
        f"suite_local_hole_count={len(suite_holes)}",
        f"call_site_count={len(sites)}",
        f"planted_unexercised_status={(planted_unex_row or {}).get('status')}",
        f"planted_exercised_status={(planted_ex_row or {}).get('status')}",
        f"planted_weak_suite_hole={planted_weak_hole}",
        f"sample_weak_suite_hole={sample_weak_hole}",
        f"mention_only_call_hits={mention_hits}",
        f"control_ok={control_ok}",
        "HIGH_RISK_UNEXERCISED:",
    ]
    for r in high_unex[:40]:
        lines.append(
            f"  {r['path']}:{r['lineno']} {r['func']}({r['param']}={r['default_repr']}) "
            f"supply={r['supply_count']} omit={r['omit_count']}"
        )
    if len(high_unex) > 40:
        lines.append(f"  ... ({len(high_unex) - 40} more)")
    lines.append("SUITE_LOCAL_HOLES:")
    for h in suite_holes[:40]:
        lines.append(
            f"  {h['test_file']} never omits {h['func']}({h['param']}={h['default_repr']}) "
            f"supply={h['supply_count']} global={h['global_status']}"
        )
    if len(suite_holes) > 40:
        lines.append(f"  ... ({len(suite_holes) - 40} more)")
    lines.append(
        "SUCCESS:AUD-0057-probe1"
        if control_ok
        else "FAIL:AUD-0057-probe1 planted control miss"
    )
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if control_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
