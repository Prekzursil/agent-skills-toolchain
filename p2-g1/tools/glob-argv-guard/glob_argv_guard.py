"""glob-argv-guard — diagnose and remediate Glob/Grep ENAMETOOLONG on Windows.

WHY THIS EXISTS (all figures measured 2026-07-18, Claude Code 2.1.214, Win11):

    Glob is the worst core tool in the harness: 6,222 calls, 13.3% error rate,
    592 of those failures are `ENAMETOOLONG: name too long, uv_spawn`.

MECHANISM (decompiled from the shipped bundle, then reproduced end-to-end):

    Claude Code keeps a cached exclusion list for its plugin cache:

        c2g = ".orphaned_at"
        r   = normalize(join(pluginRoot(), "cache"))
        n   = rg ["--files","--hidden","--no-ignore","--max-depth","4","--glob",c2g]  cwd=r
        cachedExclusions = n.map(o => `!**/${relative(r, dirname(o)).replaceAll("\\","/")}/**`)

    and then appends, to EVERY Glob/Grep invocation, two argv entries per entry:

        for (let w of await ptr(s)) m.push("--glob", w);

    `ptr()` returns the list whenever the search path is the cache dir, an
    ancestor of it, or a descendant of it -- which is why every observed failure
    was rooted at ~, ~/.claude, ~/.claude/plugins or below.

MEASURED ON THIS BOX:
    markers found by the depth-4 scan .... 1,293   (1,998 exist; 705 are deeper
                                                    than max-depth 4 and are
                                                    therefore INVISIBLE to the
                                                    scan -- deleting those saves
                                                    exactly zero argv bytes)
    constructed command line ............. 82,893 chars
    Windows CreateProcess cap ............ 32,767 chars  (measured via libuv:
                                                          32,745 OK -> 32,774 fail)
    exclusion share of the command line .. 99.92%

COMPOSITION OF THE 1,293 (this is the part the "delete orphaned plugins" framing
got wrong):
    1,191 (92.7% of the bytes) are spurious markers written INSIDE
          `temp_subdir_*` git-clone husks -- 1,123 of them under a `.git/`
          subdirectory (`.git/refs`, `.git/objects`, `.git/info`, ...).
      102 ( 7.3% of the bytes) are genuine orphaned plugin versions, which on
          their own total 6,067 chars and would NEVER breach the cap.

    Upstream cause of the spurious ones: the orphan-marker walker assumes the
    cache is exactly `marketplace/plugin/version`, so a stray `temp_subdir_*/`
    left in the cache root is mis-read as a marketplace and its `.git/*`
    internals get marked as though they were plugin versions.

WHY DELETION IS THE WRONG PRIMARY FIX:
    Claude Code already reaps orphans itself, and its reaper is deliberately
    conservative:

        if (now - markerMtime > 14 days) {
            if (await h5r(dir)) { log("Skipping orphan cleanup, in use by live session"); return }
            await rm(dir, {recursive: true, force: true})
        }

    `h5r` is a live-session in-use check. A session pins the absolute path of
    the plugin version it loaded at startup; if a newer version is installed
    mid-session the old directory is marked orphaned while still being actively
    read. That is exactly the observed counter-example -- an ACTIVE skill reading
    an "orphaned" directory is EXPECTED behaviour, not an anomaly. A hand-rolled
    bulk delete cannot reproduce `h5r`, so it can race a live session.

WHY IGNORE FILES CANNOT FIX IT (measured, both directions):
    The scan hardcodes `--no-ignore`, so `.rgignore` / `.ignore` / `.gitignore`
    are all inert: 1,297 markers before, 1,297 after, for each of the three.
    Dropping `--no-ignore` from the same scan with the same `.ignore` present
    reduces it to 102 -- proving the ignore files were valid and the hardcoded
    flag is what defeats them.

THE FIX (non-deleting, reversible, measured):
    ripgrep reads extra arguments from the file named by RIPGREP_CONFIG_PATH,
    and `--glob` is additive and independent of `--no-ignore`. A one-line config

        --glob=!temp_subdir_*/**

    prunes the scan itself: 1,297 -> 102 markers, 81,749 -> 5,508 argv chars,
    comfortably under the cap. Nothing is deleted, the husks remain on disk for
    the vendor's own reaper, and the change is undone by unsetting one variable.

Terminal-state output follows AGENTS.md section 4.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

HOSTILE_FILENAME = "o'reilly \"$(id)\" x.txt"
REVIEWER_INJECTION = "tick`id`;echo $HOME"
ECHO_CHILD = Path(__file__).resolve().parent / "fixtures" / "echo_argv.py"

# Measured on this box with a libuv spawn sweep:
#   n=1127 -> cmdline 32,745 chars -> OK
#   n=1128 -> cmdline 32,774 chars -> ENAMETOOLONG
WINDOWS_CMDLINE_CAP = 32767

ORPHAN_MARKER = ".orphaned_at"
SCAN_MAX_DEPTH = 4  # hardcoded as "--max-depth","4" in the bundle
HUSK_PREFIX = "temp_subdir_"

WHY_NOT_IGNORE_FILES = (
    "Claude Code's exclusion scan hardcodes --no-ignore "
    '(["--files","--hidden","--no-ignore","--max-depth","4","--glob",".orphaned_at"]), '
    "so .rgignore/.ignore/.gitignore are inert: measured 1,297 markers before and "
    "1,297 after for all three. Dropping --no-ignore from the same scan with the "
    "same .ignore present yields 102, proving the files are valid and the "
    "hardcoded flag is what defeats them. RIPGREP_CONFIG_PATH works because "
    "--glob is additive and is not an ignore-file mechanism."
)


# ---------------------------------------------------------------------------
# scanning -- a pure-python reimplementation of Claude Code's rg invocation
# ---------------------------------------------------------------------------
def scan_markers(cache_root: str, max_depth: int = SCAN_MAX_DEPTH) -> list[str]:
    """Return marker paths relative to `cache_root`, as ripgrep would list them.

    `--max-depth N` bounds the number of path components of the *file*, so
    `mkt/plugin/1.0.0/.orphaned_at` (4) is found and
    `mkt/a/b/c/1.0.0/.orphaned_at` (6) is not.
    """
    if not os.path.isdir(cache_root):
        return []
    out: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(cache_root):
        if ORPHAN_MARKER not in filenames:
            continue
        rel_dir = os.path.relpath(dirpath, cache_root).replace("\\", "/")
        rel = ORPHAN_MARKER if rel_dir == "." else f"{rel_dir}/{ORPHAN_MARKER}"
        if len(rel.split("/")) <= max_depth:
            out.append(rel)
    return sorted(out)


def build_exclusions(marker_paths: list[str]) -> list[str]:
    """Mirror `!**/${relative(cache, dirname(marker)).replaceAll('\\\\','/')}/**`."""
    excl = []
    for m in marker_paths:
        d = os.path.dirname(m.replace("\\", "/"))
        excl.append(f"!**/{d}/**" if d else "!**//**")
    return excl


def exclusion_argv_bytes(exclusions: list[str]) -> int:
    """Claude Code pushes '--glob' AND the pattern -> two argv entries each."""
    return sum(len("--glob") + 1 + len(e) + 1 for e in exclusions)


def classify_marker(rel_path: str) -> str:
    """'husk' = spurious marker inside a temp clone; 'genuine' = plugin version."""
    p = rel_path.replace("\\", "/")
    first = p.split("/")[0]
    if first.startswith(HUSK_PREFIX) or "/.git/" in p:
        return "husk"
    return "genuine"


# ---------------------------------------------------------------------------
# diagnosis
# ---------------------------------------------------------------------------
@dataclass
class Diagnosis:
    cache_root: str
    markers: list[str]
    exclusions: list[str]
    argv_bytes: int
    over_cap: bool
    by_class: dict[str, int] = field(default_factory=dict)
    argv_bytes_by_class: dict[str, int] = field(default_factory=dict)
    markers_at_any_depth: int = 0

    @property
    def invisible_to_scan(self) -> int:
        """Markers too deep for --max-depth 4: removing them saves zero bytes."""
        return max(self.markers_at_any_depth - len(self.markers), 0)


def diagnose(cache_root: str) -> Diagnosis:
    markers = scan_markers(cache_root)
    exclusions = build_exclusions(markers)
    by_class: dict[str, int] = {"husk": 0, "genuine": 0}
    argv_by_class: dict[str, int] = {"husk": 0, "genuine": 0}
    for m, e in zip(markers, exclusions):
        c = classify_marker(m)
        by_class[c] += 1
        argv_by_class[c] += exclusion_argv_bytes([e])

    deep = 0
    if os.path.isdir(cache_root):
        for _dp, _dn, fns in os.walk(cache_root):
            if ORPHAN_MARKER in fns:
                deep += 1

    argv = exclusion_argv_bytes(exclusions)
    return Diagnosis(
        cache_root=cache_root,
        markers=markers,
        exclusions=exclusions,
        argv_bytes=argv,
        over_cap=argv > WINDOWS_CMDLINE_CAP,
        by_class=by_class,
        argv_bytes_by_class=argv_by_class,
        markers_at_any_depth=deep,
    )


# ---------------------------------------------------------------------------
# remediation planning -- READ-ONLY, deletes nothing
# ---------------------------------------------------------------------------
@dataclass
class Plan:
    mechanism: str
    rg_config_patterns: list[str]
    current_argv_bytes: int
    projected_argv_bytes: int
    deletes: list[str]
    why_not_ignore_files: str
    diagnosis: Diagnosis

    @property
    def resolves(self) -> bool:
        return self.projected_argv_bytes <= WINDOWS_CMDLINE_CAP


def _matches_exclusion(rel_marker: str, pattern: str) -> bool:
    """`!<glob>/**` excludes a marker whose path is under a dir matching <glob>."""
    body = pattern[1:] if pattern.startswith("!") else pattern
    body = body[:-3] if body.endswith("/**") else body
    first = rel_marker.replace("\\", "/").split("/")[0]
    return fnmatch.fnmatch(first, body)


def plan_remediation(cache_root: str) -> Plan:
    d = diagnose(cache_root)

    # Only ever propose pruning the spurious husk population. Genuine plugin
    # version dirs are left entirely alone: they are 7.3% of the bytes, they
    # never breach the cap on their own, and they are exactly the population the
    # vendor's live-session-aware reaper owns.
    patterns: list[str] = []
    if any(classify_marker(m) == "husk" for m in d.markers):
        patterns.append(f"!{HUSK_PREFIX}*/**")

    kept = [m for m in d.markers if not any(_matches_exclusion(m, p) for p in patterns)]
    projected = exclusion_argv_bytes(build_exclusions(kept))

    return Plan(
        mechanism="RIPGREP_CONFIG_PATH",
        rg_config_patterns=patterns,
        current_argv_bytes=d.argv_bytes,
        projected_argv_bytes=projected,
        deletes=[],  # this tool never deletes anything, by construction
        why_not_ignore_files=WHY_NOT_IGNORE_FILES,
        diagnosis=d,
    )


def render_rg_config(patterns: list[str]) -> str:
    """ripgrep config: exactly one shell argument per line."""
    return "\n".join(f"--glob={p}" for p in patterns)


# ---------------------------------------------------------------------------
# reversibility
# ---------------------------------------------------------------------------
def build_restore_manifest(cache_root: str) -> list[dict]:
    """Capture every marker and its exact bytes so any change is undoable.

    The marker body is a 13-byte millisecond epoch; all 1,998 on this box were
    exactly 13 bytes. Content is recorded verbatim, not regenerated.
    """
    manifest = []
    if not os.path.isdir(cache_root):
        return manifest
    for dirpath, _dn, filenames in os.walk(cache_root):
        if ORPHAN_MARKER not in filenames:
            continue
        full = os.path.join(dirpath, ORPHAN_MARKER)
        try:
            with open(full, "rb") as fh:
                body = fh.read()
        except OSError:
            continue
        manifest.append(
            {
                "rel": os.path.relpath(full, cache_root).replace("\\", "/"),
                "bytes": body.decode("latin-1"),
                "len": len(body),
            }
        )
    return manifest


def restore_manifest_roundtrip(cache_root: str) -> bool:
    """Serialise -> deserialise -> compare against disk, byte for byte."""
    manifest = build_restore_manifest(cache_root)
    if not manifest:
        return False
    revived = json.loads(json.dumps(manifest))
    for entry in revived:
        full = os.path.join(cache_root, *entry["rel"].split("/"))
        try:
            with open(full, "rb") as fh:
                on_disk = fh.read()
        except OSError:
            return False
        if on_disk != entry["bytes"].encode("latin-1") or len(on_disk) != entry["len"]:
            return False
    return True


# ---------------------------------------------------------------------------
# terminal state (AGENTS.md section 4)
# ---------------------------------------------------------------------------
def terminal_state(d: Diagnosis) -> str:
    if d.over_cap:
        return (
            f"FAILED:glob-argv-guard argv={d.argv_bytes} exceeds cap="
            f"{WINDOWS_CMDLINE_CAP} from {len(d.markers)} markers "
            f"(husk={d.by_class.get('husk', 0)} genuine={d.by_class.get('genuine', 0)}) "
            f"-- Glob/Grep under {d.cache_root} will raise ENAMETOOLONG"
        )
    return (
        f"SUCCESS:glob-argv-guard argv={d.argv_bytes} within cap="
        f"{WINDOWS_CMDLINE_CAP} from {len(d.markers)} markers"
    )


def default_cache_root() -> str:
    override = os.environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR")
    if override:
        return (
            os.path.join(override, "cache")
            if not override.endswith("cache")
            else override
        )
    return os.path.join(os.path.expanduser("~"), ".claude", "plugins", "cache")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="glob-argv-guard",
        description="Diagnose/remediate Glob+Grep ENAMETOOLONG from plugin-cache "
        "orphan-exclusion argv overflow. Never deletes anything.",
    )
    ap.add_argument("--cache-root", default=default_cache_root())
    ap.add_argument("--plan", action="store_true", help="print the remediation plan")
    ap.add_argument(
        "--emit-config",
        metavar="PATH",
        help="write the ripgrep config file the fix needs",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    d = diagnose(args.cache_root)
    plan = plan_remediation(args.cache_root)

    if args.json:
        print(
            json.dumps(
                {
                    "cache_root": d.cache_root,
                    "markers_found_by_scan": len(d.markers),
                    "markers_at_any_depth": d.markers_at_any_depth,
                    "invisible_to_scan": d.invisible_to_scan,
                    "argv_bytes": d.argv_bytes,
                    "cap": WINDOWS_CMDLINE_CAP,
                    "over_cap": d.over_cap,
                    "by_class": d.by_class,
                    "argv_bytes_by_class": d.argv_bytes_by_class,
                    "mechanism": plan.mechanism,
                    "rg_config_patterns": plan.rg_config_patterns,
                    "projected_argv_bytes": plan.projected_argv_bytes,
                    "resolves": plan.resolves,
                    "deletes": plan.deletes,
                    "terminal_state": terminal_state(d),
                },
                indent=2,
            )
        )
        return 0 if not d.over_cap else 1

    print(terminal_state(d))
    if args.plan or args.emit_config:
        print(f"  markers found by scan : {len(d.markers)}")
        print(
            f"  markers at any depth  : {d.markers_at_any_depth} "
            f"({d.invisible_to_scan} too deep for the scan -> removing them saves 0 bytes)"
        )
        print(
            f"  husk / genuine        : {d.by_class.get('husk', 0)} / "
            f"{d.by_class.get('genuine', 0)}"
        )
        print(
            f"  argv bytes            : {d.argv_bytes:,} "
            f"(husk {d.argv_bytes_by_class.get('husk', 0):,}, "
            f"genuine {d.argv_bytes_by_class.get('genuine', 0):,})"
        )
        print(f"  mechanism             : {plan.mechanism}")
        print(f"  rg config patterns    : {plan.rg_config_patterns}")
        print(
            f"  projected argv bytes  : {plan.projected_argv_bytes:,} "
            f"(resolves={plan.resolves})"
        )
        print(f"  deletes               : {plan.deletes}")
    if args.emit_config:
        with open(args.emit_config, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_rg_config(plan.rg_config_patterns) + "\n")
        print(f"  wrote ripgrep config  : {args.emit_config}")
        print(f"  now set               : RIPGREP_CONFIG_PATH={args.emit_config}")
    return 0 if not d.over_cap else 1


@dataclass(frozen=True)
class Finding:
    path: str
    lineno: int
    kind: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "lineno": self.lineno,
            "kind": self.kind,
            "detail": self.detail,
        }


_SKIP_NAMES = frozenset({"intercept.py"})


def _is_shell_true(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    for kw in node.keywords:
        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _fstring_into_command(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = ""
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    if name not in {"Popen", "run", "call", "check_call", "check_output", "system"}:
        return False
    if not node.args:
        return False
    arg0 = node.args[0]
    return isinstance(arg0, ast.JoinedStr) or (
        isinstance(arg0, ast.BinOp) and isinstance(arg0.op, ast.Add)
    )


def scan_file(path: Path | str) -> list[Finding]:
    p = Path(path)
    if not p.is_file() or p.suffix != ".py":
        return []
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    rel = p.as_posix()
    out: list[Finding] = []
    for node in ast.walk(tree):
        if _is_shell_true(node):
            out.append(
                Finding(rel, getattr(node, "lineno", 0), "shell=True", "shell=True")
            )
        if _fstring_into_command(node):
            out.append(
                Finding(
                    rel,
                    getattr(node, "lineno", 0),
                    "f-string-into-command",
                    "interpolated command",
                )
            )
    return out


def scan_plugin(plugin_root: Path | str) -> list[Finding]:
    root = Path(plugin_root)
    findings: list[Finding] = []
    for p in sorted(root.rglob("*.py")):
        if p.name in _SKIP_NAMES:
            continue
        if "tests" in p.parts or "__pycache__" in p.parts:
            continue
        findings.extend(scan_file(p))
    return findings


if __name__ == "__main__":
    sys.exit(main())

