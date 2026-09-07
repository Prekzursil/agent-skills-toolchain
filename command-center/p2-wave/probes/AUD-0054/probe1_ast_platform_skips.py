#!/usr/bin/env python3
"""AUD-0054 Probe 1: AST scan of skip/skipif decorators resolving platform predicates.

Catalog evidence_requirement Probe 1:
  an AST scan of skip and skipif decorators resolving the platform predicate.

Scope of "resolving": a decorator condition counts as platform-gated only when its
expression -- possibly through ONE level of same-file variable assignment or
cross-file import -- textually contains one of the three platform predicates this
repo actually uses: ``sys.platform``, ``os.name``, ``platform.system()``. Tool-presence
gates (``shutil.which(...) is None``) are NOT counted even when a helper internally
reads a platform value, because the condition text itself asserts tool absence, not a
platform. That exclusion is recorded, not silently dropped (see residual_unknowns in the
packed receipt).

By design this probe is DECORATOR-ONLY. A ``pytest.skip()``/``raise SkipTest`` call
inside a test body is invisible here on purpose -- Probe 2's real collected-vs-executed
diff is the only thing that can catch a runtime-only skip, and the catalog's
tests_required control demands exactly that asymmetry.
"""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-ast-platform-skips.json"
OUT_RAW = PROBE / "probe1-ast-platform-skips.raw.txt"

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
VENDOR_PREFIX = "tools/editor/ralph-orchestrator/vendor/"
OTHER_PROBE_PREFIX = "command-center/p2-wave/probes/AUD-0054-"  # n/a, kept for symmetry

PLATFORM_PREDICATES = ("sys.platform", "os.name", "platform.system()")

# Candidate roots this repo's various pytest rootdirs put on sys.path, so an
# ``import coordination.leases`` style name resolves to a real file on disk.
IMPORT_ROOTS = ["", "platform", "tools", ".agents", "hooks", "ci", "agent-self"]

MARKER_ATTRS_PLATFORM_CAPABLE = {"skipif"}
UNITTEST_ATTRS_PLATFORM_CAPABLE = {"skipIf", "skipUnless"}


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
    if r.startswith(VENDOR_PREFIX):
        return False
    if r.startswith("command-center/p2-wave/_"):
        return False
    return path.suffix == ".py"


def unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return "<unparseable>"


def has_platform_predicate(text: str) -> bool:
    return any(p in text for p in PLATFORM_PREDICATES)


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


def _reason_from_call(call: ast.Call) -> str | None:
    for kw in call.keywords:
        if kw.arg == "reason":
            try:
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    return kw.value.value
                return unparse(kw.value)
            except Exception:  # noqa: BLE001
                return "<non-literal>"
    if len(call.args) >= 2:
        arg = call.args[1]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


class ModuleFacts:
    """Module-level facts needed to resolve one hop of indirection."""

    def __init__(self, path: Path, tree: ast.Module, src: str):
        self.path = path
        self.tree = tree
        self.lines = src.splitlines()
        # name -> unparsed RHS text, for simple `NAME = <expr>` at module level
        self.assigns: dict[str, str] = {}
        # name -> unparsed condition text, for `NAME = pytest.mark.skipif(cond, ...)`
        # or `NAME = unittest.skipIf(cond, ...)` module-level skip-decorator factories
        self.skip_vars: dict[str, dict] = {}
        # imported_name -> dotted module path, from `from a.b import name [as alias]`
        self.imports: dict[str, str] = {}
        self._scan()

    def _scan(self) -> None:
        for node in self.tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    local = alias.asname or alias.name
                    self.imports[local] = f"{node.module}.{alias.name}"
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                tgt = node.targets[0]
                if isinstance(tgt, ast.Name):
                    self.assigns[tgt.id] = unparse(node.value)
                    if isinstance(node.value, ast.Call):
                        chain = _attr_chain(node.value.func)
                        if chain and (
                            (chain[-1] in MARKER_ATTRS_PLATFORM_CAPABLE and "mark" in chain)
                            or (
                                chain
                                and chain[0] in {"unittest", "ut"}
                                and chain[-1] in UNITTEST_ATTRS_PLATFORM_CAPABLE
                            )
                        ):
                            cond = node.value.args[0] if node.value.args else None
                            self.skip_vars[tgt.id] = {
                                "kind": chain[-1],
                                "cond_text": unparse(cond) if cond is not None else "<none>",
                                "reason": _reason_from_call(node.value),
                                "lineno": node.lineno,
                            }


def resolve_module_for_dotted(dotted: str) -> Path | None:
    """Best-effort: turn `coordination.leases` into platform/coordination/leases.py."""
    rel_path = dotted.replace(".", "/") + ".py"
    for root in IMPORT_ROOTS:
        cand = REPO / root / rel_path if root else REPO / rel_path
        if cand.is_file():
            return cand
    return None


_module_cache: dict[str, ModuleFacts | None] = {}


def load_module_facts(path: Path) -> ModuleFacts | None:
    key = str(path)
    if key in _module_cache:
        return _module_cache[key]
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        _module_cache[key] = None
        return None
    mf = ModuleFacts(path, tree, src)
    _module_cache[key] = mf
    return mf


def resolve_condition_text(name: str, mf: ModuleFacts, hops: int = 0) -> tuple[str, str]:
    """Resolve a bare Name used as a skipif condition to its defining expression text.

    Returns (resolved_text, resolution_path). resolution_path documents how we got
    there so a reviewer can audit the indirection instead of trusting a black box.
    """
    if name in mf.assigns:
        return mf.assigns[name], f"same-file:{rel(mf.path)}:{name}"
    if hops < 1 and name in mf.imports:
        dotted = mf.imports[name]
        mod_path, _, attr = dotted.rpartition(".")
        target = resolve_module_for_dotted(mod_path)
        if target is not None:
            target_mf = load_module_facts(target)
            if target_mf is not None and attr in target_mf.assigns:
                return (
                    target_mf.assigns[attr],
                    f"cross-file:{rel(target.resolve())}:{attr} (imported as {dotted})",
                )
    return "<unresolved>", "unresolved"


def unwrap_and_resolve(cond_node: ast.AST, mf: ModuleFacts) -> tuple[str, str]:
    """Resolve a condition AST node to text, following `NAME` and `not NAME` one hop.

    Bare ``Name`` and ``UnaryOp(Not, Name)`` are the only two shapes this repo's
    skipif conditions actually use when indirecting through a variable (measured:
    ``_CASE_INSENSITIVE_FS`` and ``not _CASE_INSENSITIVE_FS``). Anything else is
    unparsed as-is; classify_direction() then decides whether it textually contains
    a platform predicate.
    """
    if isinstance(cond_node, ast.Name):
        return resolve_condition_text(cond_node.id, mf)
    if (
        isinstance(cond_node, ast.UnaryOp)
        and isinstance(cond_node.op, ast.Not)
        and isinstance(cond_node.operand, ast.Name)
    ):
        inner_text, path = resolve_condition_text(cond_node.operand.id, mf)
        return f"not {inner_text}", path
    return unparse(cond_node), "inline-decorator"


def classify_direction(cond_text: str) -> tuple[str, bool]:
    """Return (required_platform_label, never_on_linux_only_ci).

    Heuristics over the small, closed set of comparison shapes this repo actually
    uses. Anything outside that closed set is reported as "unclassified" rather than
    guessed, per the anti-false-green rule: an unfalsifiable label is worse than an
    honest miss.
    """
    t = cond_text.strip()
    neg = t.startswith("not ")
    inner = t[4:].strip() if neg else t

    # sys.platform != "win32"  (skip unless win32)  -> windows-only
    # sys.platform == "win32"  (skip if win32)       -> posix-only
    if "sys.platform" in inner:
        if '!= "win32"' in inner or "!= 'win32'" in inner:
            return ("windows-only", True)
        if '== "win32"' in inner or "== 'win32'" in inner:
            return ("posix-only", False)
        if '== "darwin"' in inner or "== 'darwin'" in inner:
            return ("darwin-only", True)
        if '!= "darwin"' in inner or "!= 'darwin'" in inner:
            return ("non-darwin-only", False)
        if "win32" in inner and "darwin" in inner:
            # e.g. skip-predicate `sys.platform in {"win32", "darwin"}` (bare, not
            # negated): skips ON win32/darwin, so the test EXECUTES only on linux.
            # Negated (`not ...`): skips on linux, executes only on win32/darwin.
            if neg:
                return ("windows-or-darwin-only", True)
            return ("linux-case-sensitive-only", False)
        return ("unclassified-sys.platform", False)

    # os.name == "nt"  (skip if nt) -> posix-only ; os.name != "nt" -> windows-only
    if "os.name" in inner:
        if '== "nt"' in inner or "== 'nt'" in inner:
            return ("posix-only", False)
        if '!= "nt"' in inner or "!= 'nt'" in inner:
            return ("windows-only", True)
        return ("unclassified-os.name", False)

    if "platform.system()" in inner:
        if '== "Windows"' in inner:
            return ("posix-only", False)
        if '!= "Windows"' in inner:
            return ("windows-only", True)
        if '== "Darwin"' in inner:
            return ("darwin-only", True)
        return ("unclassified-platform.system", False)

    # Resolved via a boolean constant like `_CASE_INSENSITIVE_FS = sys.platform in {...}`
    # that did not also contain the literal text "sys.platform" at this point (already
    # handled above) -- kept as a second net for other spellings of the same shape.
    if "in {" in inner and ("win32" in inner or "darwin" in inner):
        # bare (neg False): skip-predicate is "platform in {win32,darwin}" -> skips ON
        # windows/darwin -> test EXECUTES only on linux (case-sensitive, in-matrix).
        # negated (neg True): skip-predicate is "not (platform in {win32,darwin})" ->
        # skips on linux -> test EXECUTES only on windows/darwin (never in this matrix).
        if neg:
            return ("windows-or-darwin-only", True)
        return ("linux-case-sensitive-only", False)

    return ("unclassified", False)


def extract_platform_gated(path: Path) -> list[dict]:
    mf = load_module_facts(path)
    if mf is None:
        return []
    found: list[dict] = []

    for node in ast.walk(mf.tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for dec in node.decorator_list:
            call = dec if isinstance(dec, ast.Call) else None
            if call is not None:
                chain = _attr_chain(call.func)
                is_platform_capable = ("mark" in chain and chain[-1] == "skipif") or (
                    chain and chain[0] in {"unittest", "ut"} and chain[-1] in UNITTEST_ATTRS_PLATFORM_CAPABLE
                )
                if not is_platform_capable or not call.args:
                    continue
                cond_node = call.args[0]
                reason = _reason_from_call(call)
                cond_text, resolution = unwrap_and_resolve(cond_node, mf)
                if not has_platform_predicate(cond_text):
                    continue
                label, never_on_linux_ci = classify_direction(cond_text)
                found.append(
                    {
                        "path": rel(path),
                        "lineno": getattr(dec, "lineno", node.lineno),
                        "target": node.name,
                        "decorator_form": "inline-call",
                        "resolution_path": resolution,
                        "condition_text": cond_text,
                        "reason": reason,
                        "required_platform": label,
                        "never_on_current_ci_matrix": never_on_linux_ci,
                    }
                )
            elif isinstance(dec, ast.Name) and dec.id in mf.skip_vars:
                sv = mf.skip_vars[dec.id]
                cond_text = sv["cond_text"]
                resolution = f"same-file-variable:{dec.id}:L{sv['lineno']}"
                if not has_platform_predicate(cond_text):
                    # the variable's condition may itself be a bare/negated Name one
                    # more hop out (e.g. `windows_only = pytest.mark.skipif(SOME_FLAG)`)
                    try:
                        cond_ast = ast.parse(cond_text, mode="eval").body
                    except SyntaxError:
                        cond_ast = None
                    if cond_ast is not None:
                        resolved_text, chain_res = unwrap_and_resolve(cond_ast, mf)
                        if resolved_text != cond_text:
                            cond_text = resolved_text
                            resolution = f"{resolution} -> {chain_res}"
                if not has_platform_predicate(cond_text):
                    continue
                label, never_on_linux_ci = classify_direction(cond_text)
                found.append(
                    {
                        "path": rel(path),
                        "lineno": getattr(dec, "lineno", node.lineno),
                        "target": node.name,
                        "decorator_form": f"shared-variable:{dec.id}",
                        "resolution_path": resolution,
                        "condition_text": cond_text,
                        "reason": sv.get("reason"),
                        "required_platform": label,
                        "never_on_current_ci_matrix": never_on_linux_ci,
                    }
                )
    return found


def iter_py_files() -> list[Path]:
    files: list[Path] = []
    for p in REPO.rglob("*.py"):
        if not in_scope(p):
            continue
        files.append(p)
    for p in (PROBE / "fixtures").glob("*.py"):
        if p not in files:
            files.append(p)
    return sorted(files, key=lambda x: rel(x))


def main() -> int:
    files = iter_py_files()
    rows: list[dict] = []
    for f in files:
        rows.extend(extract_platform_gated(f))

    only_test_targets = [r for r in rows if r["target"].startswith("test_")]

    by_platform = Counter(r["required_platform"] for r in only_test_targets)
    windows_only = sum(
        1 for r in only_test_targets if r["required_platform"] == "windows-only"
    )
    posix_only = sum(1 for r in only_test_targets if r["required_platform"] == "posix-only")
    darwin_only = sum(1 for r in only_test_targets if r["required_platform"] == "darwin-only")
    windows_or_darwin_only = sum(
        1 for r in only_test_targets if r["required_platform"] == "windows-or-darwin-only"
    )
    linux_case_sensitive_only = sum(
        1 for r in only_test_targets if r["required_platform"] == "linux-case-sensitive-only"
    )
    unclassified = sum(
        1 for r in only_test_targets if r["required_platform"].startswith("unclassified")
    )
    never_on_current_ci_matrix = sum(
        1 for r in only_test_targets if r["never_on_current_ci_matrix"]
    )

    # Deliberate exclusion, made countable rather than silently dropped: skipif
    # conditions that reference tool-presence (e.g. `BASH is None`, `letter is None`)
    # rather than a textual platform predicate, even though the helper that produced
    # the value is itself platform-branching internally.
    excluded_tool_presence_files = []
    for f in files:
        mf = load_module_facts(f)
        if mf is None:
            continue
        for name, expr in mf.assigns.items():
            if "is None" in expr and not has_platform_predicate(expr):
                # e.g. `BASH = find_bash()` used later as `BASH is None` in a skipif
                excluded_tool_presence_files.append(
                    {"path": rel(f), "name": name, "expr": expr}
                )

    control_names = {r["target"] for r in only_test_targets}
    control_missed_runtime_fixture = (
        "test_control_windows_only_runtime_skip_no_decorator" not in control_names
    )

    doc = {
        "unit": "AUD-0054",
        "probe": 1,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files_scanned": len(files),
        "platform_gated_marker_rows": len(rows),
        "platform_gated_test_rows": len(only_test_targets),
        "windows_only_count": windows_only,
        "posix_only_count": posix_only,
        "darwin_only_count": darwin_only,
        "windows_or_darwin_only_count": windows_or_darwin_only,
        "linux_case_sensitive_only_count": linux_case_sensitive_only,
        "unclassified_count": unclassified,
        "never_on_current_ci_matrix_declared_count": never_on_current_ci_matrix,
        "by_required_platform": dict(sorted(by_platform.items())),
        "excluded_tool_presence_count": len(excluded_tool_presence_files),
        "excluded_tool_presence_examples": excluded_tool_presence_files[:10],
        "rows": only_test_targets,
        "control": {
            # This control asserts the NEGATIVE: probe1 must NOT find the runtime-only
            # fixture, because it declares no decorator at all. Probe 2 is the one that
            # must find it; the pairing is verified in _pack_receipt.py / the combined
            # control script.
            "runtime_only_fixture_correctly_missed": control_missed_runtime_fixture,
        },
        "ok": len(only_test_targets) > 0 and control_missed_runtime_fixture,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw_lines = [
        "SUCCESS:AUD-0054-probe1" if doc["ok"] else "FAILED:AUD-0054-probe1",
        f"unit=AUD-0054 probe=1 files_scanned={len(files)}",
        f"platform_gated_test_rows={len(only_test_targets)} by_required_platform={dict(by_platform)}",
        f"never_on_current_ci_matrix_declared_count={never_on_current_ci_matrix}",
        f"excluded_tool_presence_count={len(excluded_tool_presence_files)}",
        f"control_runtime_only_fixture_correctly_missed={control_missed_runtime_fixture}",
        "--- rows (path:lineno target required_platform resolution) ---",
    ]
    for r in only_test_targets:
        raw_lines.append(
            f"{r['path']}:{r['lineno']} {r['target']} platform={r['required_platform']} "
            f"never_on_ci={r['never_on_current_ci_matrix']} via={r['resolution_path']} "
            f"cond={r['condition_text']!r}"
        )
    OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    print(OUT_RAW.read_text(encoding="utf-8"))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
