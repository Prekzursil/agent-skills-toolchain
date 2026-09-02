"""ADV-0021 Probe 1: CODE-DERIVED (not doc-derived) trust-boundary + data-flow enumeration.

Mechanism: AST walk over the install-path modules. For every lifecycle verb, resolve the
call graph one and two levels deep, then locate every SINK (filesystem mutation, process
exec, archive read, state read) and every CONTROL (safe_join / check_relpath / hash compare /
lock / explicit raise) with a MEASURED file:line. Independent of Probe 2, which EXECUTES.

Emits JSON so the artifact can quote line anchors that were computed, never guessed.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

PLUGIN = Path(r"C:/Users/Prekzursil/source/ast-integrate/platform/plugin")
MODULES = ["cli.py", "lifecycle.py", "packager.py", "fsops.py", "journal.py",
           "deploy.py", "manifest.py", "proc.py", "payload.py", "cache.py"]

VERBS = ["install", "update", "repair", "rollback", "uninstall"]

SINKS = {
    # name -> (category, why it is a boundary crossing)
    "unpack": ("fs-write", "untrusted archive bytes become files on disk"),
    "atomic_write_bytes": ("fs-write", "writes bytes to a path"),
    "rmtree": ("fs-destroy", "recursive delete"),
    "unlink": ("fs-destroy", "single-file delete"),
    "move_dir": ("fs-write", "directory rename/copy into the install prefix"),
    "mkdir": ("fs-write", "directory creation"),
    "copytree": ("fs-write", "non-atomic copy fallback"),
    "run": ("proc-exec", "subprocess execution"),
    "subprocess.run": ("proc-exec", "subprocess execution"),
    "probe_interpreter": ("proc-exec", "executes a PATH-resolved interpreter"),
    "check_interpreters": ("proc-exec", "executes every declared interpreter"),
    "launch_argv": ("proc-exec", "builds the argv that will run payload code"),
    "read_bytes": ("fs-read", "reads file bytes"),
    "read_text": ("fs-read", "reads file text"),
    "read_installed": ("state-read", "parses prefix state that steers later paths"),
    "load": ("state-read", "parses provenance/manifest"),
    "version_dir": ("path-derive", "derives a filesystem path from a version string"),
}

CONTROLS = {
    "safe_join": "containment: join + prove the target is under the root",
    "check_relpath": "reject traversal / absolute / UNC / drive / reserved-device names",
    "content_hash": "EOL-normalised hash used for integrity + drift comparison",
    "PrefixLock": "exclusive advisory lock (O_CREAT|O_EXCL)",
    "preflight": "disk / writability / crash-residue gate",
    "negotiate": "client + platform compatibility gate",
    "parse_semver": "version-string shape gate",
    "relative_to": "containment assertion",
    "Transaction": "journalled undo of every applied step",
    "_verify_staged": "manifest parse + per-file inventory hash check + entrypoint existence",
}


def load(mod: str) -> tuple[ast.Module, list[str]]:
    src = (PLUGIN / mod).read_text(encoding="utf-8")
    return ast.parse(src, filename=mod), src.splitlines()


def callee_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            return f.id
        if isinstance(f, ast.Attribute):
            return f.attr
    return None


def funcs(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[n.name] = n  # type: ignore[assignment]
    return out


def main() -> int:
    trees = {m: load(m) for m in MODULES}
    report: dict[str, object] = {"probe": "ADV-0021-probe1-ast-derived", "modules": MODULES}

    # ---- 1. per-verb call graph (2 levels) -------------------------------------------------
    lc_tree, lc_lines = trees["lifecycle.py"]
    lc_funcs = funcs(lc_tree)
    verb_graph: dict[str, dict] = {}
    for v in VERBS:
        fn = lc_funcs.get(v)
        if fn is None:
            verb_graph[v] = {"error": "verb function not found in lifecycle.py"}
            continue
        lvl1 = sorted({callee_name(n) for n in ast.walk(fn) if callee_name(n)} - {None})
        lvl2: dict[str, list[str]] = {}
        for c in lvl1:
            sub = lc_funcs.get(c)
            if sub is not None:
                lvl2[c] = sorted({callee_name(n) for n in ast.walk(sub) if callee_name(n)} - {None})
        verb_graph[v] = {
            "defined_at": f"lifecycle.py:{fn.lineno}-{fn.end_lineno}",
            "direct_calls": lvl1,
            "expanded_local_helpers": lvl2,
        }
    report["verb_call_graph"] = verb_graph

    # ---- 2. every sink site, with file:line ------------------------------------------------
    sink_sites: list[dict] = []
    for mod, (tree, lines) in trees.items():
        fmap = funcs(tree)
        owner_of: dict[int, str] = {}
        for name, fn in fmap.items():
            for ln in range(fn.lineno, (fn.end_lineno or fn.lineno) + 1):
                owner_of.setdefault(ln, name)
        for n in ast.walk(tree):
            nm = callee_name(n)
            if nm in SINKS:
                cat, why = SINKS[nm]
                sink_sites.append({
                    "anchor": f"{mod}:{n.lineno}",
                    "in_function": owner_of.get(n.lineno, "<module>"),
                    "callee": nm, "category": cat, "why": why,
                    "source": lines[n.lineno - 1].strip()[:160],
                })
    report["sink_sites"] = sorted(sink_sites, key=lambda d: (d["anchor"].split(":")[0], int(d["anchor"].split(":")[1])))
    report["sink_site_count"] = len(sink_sites)

    # ---- 3. every control site, with file:line ---------------------------------------------
    control_sites: list[dict] = []
    for mod, (tree, lines) in trees.items():
        fmap = funcs(tree)
        owner_of: dict[int, str] = {}
        for name, fn in fmap.items():
            for ln in range(fn.lineno, (fn.end_lineno or fn.lineno) + 1):
                owner_of.setdefault(ln, name)
        for n in ast.walk(tree):
            nm = callee_name(n)
            if nm in CONTROLS:
                control_sites.append({
                    "anchor": f"{mod}:{n.lineno}",
                    "in_function": owner_of.get(n.lineno, "<module>"),
                    "control": nm, "claims": CONTROLS[nm],
                    "source": lines[n.lineno - 1].strip()[:160],
                })
    report["control_sites"] = sorted(control_sites, key=lambda d: (d["anchor"].split(":")[0], int(d["anchor"].split(":")[1])))
    report["control_site_count"] = len(control_sites)

    # ---- 4. THE DIFFERENTIAL: path-deriving sinks that are NOT guarded --------------------
    # Every place a path is built by joining an EXTERNALLY-SUPPLIED string, and whether the
    # join went through safe_join (guarded) or a bare `/` BinOp (unguarded).
    unguarded: list[dict] = []
    for mod, (tree, lines) in trees.items():
        fmap = funcs(tree)
        owner_of: dict[int, str] = {}
        for name, fn in fmap.items():
            for ln in range(fn.lineno, (fn.end_lineno or fn.lineno) + 1):
                owner_of.setdefault(ln, name)
        for n in ast.walk(tree):
            if not isinstance(n, ast.BinOp) or not isinstance(n.op, ast.Div):
                continue
            src = lines[n.lineno - 1].strip()
            # heuristic: a `/` join whose RIGHT operand is a variable/subscript/call, i.e. not a literal
            if isinstance(n.right, ast.Constant):
                continue
            rhs = ast.unparse(n.right)
            lhs = ast.unparse(n.left)
            if not any(t in lhs.lower() for t in ("path", "root", "dir", "prefix", "live", "lr",
                                                  "staging", "versions", "state", "self")):
                continue
            unguarded.append({
                "anchor": f"{mod}:{n.lineno}",
                "in_function": owner_of.get(n.lineno, "<module>"),
                "expr": f"{lhs} / {rhs}"[:120],
                "guarded_by_safe_join": "safe_join" in src,
                "source": src[:160],
            })
    report["path_joins"] = sorted(unguarded, key=lambda d: (d["anchor"].split(":")[0], int(d["anchor"].split(":")[1])))
    report["path_join_count"] = len(unguarded)
    report["unguarded_external_joins"] = [
        j for j in unguarded if not j["guarded_by_safe_join"]
        and any(t in j["expr"] for t in ("version", "live_rel", "rel", "target", "key", "txn"))
    ]

    # ---- 5. the semver gate's actual regex, read from source ------------------------------
    m_tree, m_lines = trees["manifest.py"]
    semver_line = next((i + 1 for i, ln in enumerate(m_lines) if ln.startswith("SEMVER_RE")), None)
    report["semver_gate"] = {
        "anchor": f"manifest.py:{semver_line}",
        "source": m_lines[semver_line - 1].strip() if semver_line else None,
        "note": "the trailing (?:[-+].*)? group accepts ANY characters, including path separators",
    }

    # ---- 6. exception handling at the CLI boundary ----------------------------------------
    c_tree, c_lines = trees["cli.py"]
    handlers: list[dict] = []
    for n in ast.walk(c_tree):
        if isinstance(n, ast.Try):
            for h in n.handlers:
                handlers.append({
                    "anchor": f"cli.py:{h.lineno}",
                    "catches": ast.unparse(h.type) if h.type else "<bare except>",
                })
    report["cli_exception_handlers"] = handlers

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("adv0021_probe1_out.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"OUT={out}")
    print(f"sink_sites={report['sink_site_count']} control_sites={report['control_site_count']} "
          f"path_joins={report['path_join_count']} unguarded_external={len(report['unguarded_external_joins'])}")
    print("\n--- UNGUARDED EXTERNAL-STRING PATH JOINS ---")
    for j in report["unguarded_external_joins"]:
        print(f"  {j['anchor']}  in {j['in_function']}()  ::  {j['expr']}")
    print("\n--- SEMVER GATE ---")
    print(f"  {report['semver_gate']['anchor']}: {report['semver_gate']['source']}")
    print("\n--- CLI EXCEPTION HANDLERS ---")
    for h in handlers:
        print(f"  {h['anchor']}: except {h['catches']}")
    print("\n--- PER-VERB DIRECT CALLS ---")
    for v, g in verb_graph.items():
        print(f"  {v} ({g.get('defined_at')}): {g.get('direct_calls')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
