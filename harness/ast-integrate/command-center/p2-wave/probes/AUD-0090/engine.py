#!/usr/bin/env python3
"""AUD-0090: pinned ruff/semgrep/bandit counts on git-cat-file blobs vs CRLF analogue.

Probe 1 scans bytes from `git cat-file -p` (never git archive).
Probe 2 scans a Windows core.autocrlf=true analogue (LF -> CRLF) of those
same blob bytes and records BOTH counts. Identical counts on the planted
CRLF-sensitive file means blob extraction silently returned worktree bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def unshadow() -> None:
    """Drop the repo-root `platform/` package so stdlib `platform` loads."""
    drop = {str(REPO.resolve()), "", ".", str(Path.cwd().resolve())}
    cleaned: list[str] = []
    for p in sys.path:
        if p in drop:
            continue
        try:
            if Path(p).resolve() == REPO.resolve():
                continue
        except OSError:
            pass
        cleaned.append(p)
    sys.path[:] = cleaned
    sys.modules.pop("platform", None)
    sys.modules.pop("uuid", None)


unshadow()

UID = "AUD-0090"
OUT_REL = "command-center/audit/AUD-0090-static-analysis-baseline.json"
SCHEMA_REL = "command-center/schema/audit-metric-baseline.schema.json"
COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0090 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "What is the exact finding count per rule for ruff, semgrep, and bandit "
    "at PINNED versions against the COMMITTED BLOB bytes, so a later diff "
    "is meaningful?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0090/probe1_blob.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0090/probe2_worktree.py"
)
UA = "AUD-0090-static-analysis-baseline/1.0"
RUFF_PIN = "0.15.17"
BANDIT_PIN = "1.9.4"
SEMGREP_PIN = "1.174.0"
SENSITIVE_NAME = "crlf_sensitive.py"
INERT_NAME = "crlf_inert.py"
SKIP_MARK = re.compile(
    r"""extra\s*==|sys_platform\s*==\s*['\"]win|platform_system\s*==\s*['\"]Windows"""
)
REQ_NAME = re.compile(r"^([A-Za-z0-9_.-]+)")


def e501_line(width: int = 88) -> str:
    prefix = 'S = "'
    suffix = '"'
    n = width - len(prefix) - len(suffix)
    if n < 1:
        raise ValueError("width too small")
    line = prefix + ("x" * n) + suffix
    if len(line) != width:
        raise AssertionError(len(line))
    return line


def sensitive_lf() -> bytes:
    body = (
        '"""AUD-0090 CRLF-sensitive fixture. Blob bytes are LF via git cat-file -p."""\n'
        'x = eval("1+1")\n'
        f"{e501_line(88)}\n"
    )
    return body.encode("ascii")


def inert_lf() -> bytes:
    body = (
        '"""AUD-0090 short-line fixture. eval is still present; lines stay under 88."""\n'
        'y = eval("2+2")\n'
    )
    return body.encode("ascii")


def cr_count(raw: bytes) -> int:
    return raw.count(b"\r")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def deps_root() -> Path:
    return HERE / "deps"


def py_deps() -> Path:
    return deps_root() / "py"


def wheels_dir() -> Path:
    return deps_root() / "wheels"


def blob_git_dir() -> Path:
    return HERE / "fixtures" / "blob-repo" / ".git"


def blob_tree_dir() -> Path:
    return HERE / "trees" / "blob"


def windows_tree_dir() -> Path:
    return HERE / "trees" / "windows"


def rules_path() -> Path:
    return HERE / "fixtures" / "semgrep-rules.yaml"


def _http_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp, tmp.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 64)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)


def _wheel_score(filename: str) -> tuple[int, str]:
    fn = filename.lower()
    if "manylinux" in fn and "x86_64" in fn and "musl" not in fn:
        return (0, filename)
    if "linux_x86_64" in fn and "musl" not in fn:
        return (1, filename)
    if "py3-none-any" in fn or "none-any.whl" in fn:
        return (2, filename)
    return (9, filename)


def pick_wheel(urls: list[dict[str, Any]]) -> dict[str, Any] | None:
    wheels = [u for u in urls if str(u.get("packagetype") or "") == "bdist_wheel"]
    if not wheels:
        wheels = [u for u in urls if str(u.get("filename") or "").endswith(".whl")]
    ranked = sorted(wheels, key=lambda u: _wheel_score(str(u.get("filename") or "")))
    if not ranked:
        return None
    best = ranked[0]
    if _wheel_score(str(best.get("filename") or ""))[0] >= 9:
        return None
    return best


def extract_wheel(url: str, dest: Path) -> str:
    dest.mkdir(parents=True, exist_ok=True)
    fname = url.rsplit("/", 1)[-1].split("?")[0]
    whl = wheels_dir() / fname
    _download(url, whl)
    with zipfile.ZipFile(whl) as zf:
        zf.extractall(dest)
    return fname


def install_pypi(name: str, version: str | None, dest: Path, seen: set[str]) -> str:
    key = name.lower().replace("_", "-")
    if key in seen:
        return key
    seen.add(key)
    url = (
        f"https://pypi.org/pypi/{name}/{version}/json"
        if version
        else f"https://pypi.org/pypi/{name}/json"
    )
    data = _http_json(url)
    info = data["info"]
    ver = str(info["version"])
    for req in info.get("requires_dist") or []:
        if not isinstance(req, str) or SKIP_MARK.search(req):
            continue
        m = REQ_NAME.match(req.strip())
        if not m:
            continue
        install_pypi(m.group(1), None, dest, seen)
    wheel = pick_wheel(data.get("urls") or [])
    if wheel is None:
        raise RuntimeError(f"no compatible wheel for {name}=={ver}")
    extract_wheel(str(wheel["url"]), dest)
    return f"{info['name']}=={ver}"


def find_ruff_bin(root: Path) -> Path:
    candidates: list[Path] = []
    for p in root.rglob("ruff"):
        if p.is_file() and os.access(p, os.X_OK) and p.suffix == "":
            candidates.append(p)
    for p in root.rglob("ruff"):
        if p.is_file() and p.stat().st_size > 1_000_000:
            candidates.append(p)
    if not candidates:
        raise RuntimeError("ruff binary missing after wheel extract")
    bin_path = max(candidates, key=lambda p: p.stat().st_size)
    bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)
    return bin_path


def find_semgrep_core(root: Path) -> Path | None:
    names = ("opengrep-core", "semgrep-core", "osemgrep")
    found: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.name in names:
            found.append(p)
        elif p.is_file() and p.name.startswith("semgrep") and p.stat().st_size > 5_000_000:
            found.append(p)
    if not found:
        return None
    bin_path = max(found, key=lambda p: p.stat().st_size)
    bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)
    return bin_path


def ensure_tools() -> dict[str, Any]:
    dest = py_deps()
    dest.mkdir(parents=True, exist_ok=True)
    wheels_dir().mkdir(parents=True, exist_ok=True)
    try:
        ruff_bin = find_ruff_bin(dest)
        core = find_semgrep_core(dest)
    except RuntimeError:
        ruff_bin = None
        core = None
    bandit_ok = (dest / "bandit").is_dir()
    if ruff_bin is not None and core is not None and bandit_ok:
        return {
            "ruff_spec": f"ruff=={RUFF_PIN}",
            "bandit_spec": f"bandit=={BANDIT_PIN}",
            "semgrep_spec": f"semgrep=={SEMGREP_PIN}",
            "ruff_bin": str(ruff_bin),
            "semgrep_core": str(core),
            "py_deps": str(dest),
            "reused": True,
        }
    seen: set[str] = set()
    ruff_spec = install_pypi("ruff", RUFF_PIN, dest, seen)
    bandit_spec = install_pypi("bandit", BANDIT_PIN, dest, seen)
    semgrep_spec = install_pypi("semgrep", SEMGREP_PIN, dest, seen)
    ruff_bin = find_ruff_bin(dest)
    core = find_semgrep_core(dest)
    return {
        "ruff_spec": ruff_spec,
        "bandit_spec": bandit_spec,
        "semgrep_spec": semgrep_spec,
        "ruff_bin": str(ruff_bin),
        "semgrep_core": str(core) if core else None,
        "py_deps": str(dest),
        "reused": False,
    }


def pythonpath() -> str:
    dest = py_deps()
    parts = [str(dest)]
    parts.extend(str(p) for p in dest.glob("*.data/purelib"))
    parts.extend(str(p) for p in dest.glob("*.data/platlib"))
    return os.pathsep.join(parts)


def tool_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPATH"] = pythonpath()
    env["SEMGREP_USER_AGENT_APPEND"] = "AUD-0090"
    env["NO_COLOR"] = "1"
    env.pop("PYTHONHOME", None)
    return env


def run_cmd(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    env = tool_env()
    if extra_env:
        env.update(extra_env)
    try:
        p = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"TIMEOUT after {timeout}s: {' '.join(argv)}"
    except OSError as exc:
        return 127, "", f"{type(exc).__name__}:{exc}"
    out = (p.stdout or b"").decode("utf-8", errors="replace")
    err = (p.stderr or b"").decode("utf-8", errors="replace")
    return int(p.returncode), out, err


def git_in(repo_dir: Path, args: list[str], *, data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "AUD-0090"
    env["GIT_AUTHOR_EMAIL"] = "aud-0090@local"
    env["GIT_COMMITTER_NAME"] = "AUD-0090"
    env["GIT_COMMITTER_EMAIL"] = "aud-0090@local"
    env["GIT_DIR"] = str(repo_dir / ".git")
    env["GIT_WORK_TREE"] = str(repo_dir)
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_dir),
        input=data,
        capture_output=True,
        timeout=30,
        env=env,
    )


def ensure_fixture_git() -> dict[str, Any]:
    """Store LF fixtures as git blobs without git add/commit/checkout."""
    repo_dir = HERE / "fixtures" / "blob-repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    if not (repo_dir / ".git").is_dir():
        p = subprocess.run(
            ["git", "init", "-q", str(repo_dir)],
            capture_output=True,
            timeout=30,
        )
        if p.returncode != 0:
            raise RuntimeError(p.stderr.decode("utf-8", errors="replace"))
    files = {SENSITIVE_NAME: sensitive_lf(), INERT_NAME: inert_lf()}
    entries: list[str] = []
    shas: dict[str, str] = {}
    for name, raw in files.items():
        p = git_in(repo_dir, ["hash-object", "-w", "--stdin"], data=raw)
        if p.returncode != 0:
            raise RuntimeError(p.stderr.decode("utf-8", errors="replace"))
        sha = p.stdout.decode("ascii").strip()
        shas[name] = sha
        entries.append(f"100644 blob {sha}\t{name}")
    tree_p = git_in(
        repo_dir,
        ["mktree"],
        data=("\n".join(entries) + "\n").encode("utf-8"),
    )
    if tree_p.returncode != 0:
        raise RuntimeError(tree_p.stderr.decode("utf-8", errors="replace"))
    tree = tree_p.stdout.decode("ascii").strip()
    commit_p = git_in(repo_dir, ["commit-tree", tree, "-m", "AUD-0090 fixture blobs"])
    if commit_p.returncode != 0:
        raise RuntimeError(commit_p.stderr.decode("utf-8", errors="replace"))
    commit = commit_p.stdout.decode("ascii").strip()
    upd = git_in(repo_dir, ["update-ref", "HEAD", commit])
    if upd.returncode != 0:
        raise RuntimeError(upd.stderr.decode("utf-8", errors="replace"))
    return {
        "git_dir": str(blob_git_dir()),
        "commit": commit,
        "tree": tree,
        "blob_shas": shas,
        "used_git_add": False,
        "used_git_commit": False,
        "used_git_archive": False,
        "used_git_checkout": False,
        "method": "git hash-object -w + mktree + commit-tree + git cat-file -p HEAD:<path>",
    }


def git_cat_file(path: str) -> bytes:
    repo_dir = HERE / "fixtures" / "blob-repo"
    p = git_in(repo_dir, ["cat-file", "-p", f"HEAD:{path}"])
    if p.returncode != 0:
        raise RuntimeError(
            p.stderr.decode("utf-8", errors="replace") or f"cat-file miss {path}"
        )
    return p.stdout or b""


def materialize_comparable_trees() -> dict[str, Any]:
    meta = ensure_fixture_git()
    blob_dir = blob_tree_dir()
    win_dir = windows_tree_dir()
    if blob_dir.exists():
        shutil.rmtree(blob_dir)
    if win_dir.exists():
        shutil.rmtree(win_dir)
    blob_dir.mkdir(parents=True)
    win_dir.mkdir(parents=True)
    rows = []
    for name in (SENSITIVE_NAME, INERT_NAME):
        blob = git_cat_file(name)
        if b"\r" in blob:
            raise RuntimeError(f"blob {name} contains CR; cat-file is not LF")
        (blob_dir / name).write_bytes(blob)
        crlf = blob.replace(b"\n", b"\r\n")
        (win_dir / name).write_bytes(crlf)
        rows.append(
            {
                "path": name,
                "blob_bytes": len(blob),
                "blob_sha256": hashlib.sha256(blob).hexdigest(),
                "blob_cr": cr_count(blob),
                "windows_bytes": len(crlf),
                "windows_sha256": hashlib.sha256(crlf).hexdigest(),
                "windows_cr": cr_count(crlf),
                "bytes_differ": blob != crlf,
                "method_blob": "git cat-file -p HEAD:<path>",
                "method_windows": "LF->CRLF analogue of cat-file bytes (core.autocrlf=true)",
                "used_git_archive": False,
            }
        )
    meta["files"] = rows
    meta["blob_tree"] = str(blob_dir.relative_to(REPO))
    meta["windows_tree"] = str(win_dir.relative_to(REPO))
    return meta


def discover_ruff_pin() -> dict[str, Any]:
    pins: list[str] = []
    ci = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    manifests = REPO / "command-center/p2-wave/probes/AUD-0020/probe1-manifests.json"
    for path in (ci, manifests):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        pins.extend(re.findall(r"ruff==([0-9]+\.[0-9]+\.[0-9]+)", text))
    unique = sorted(set(pins))
    return {
        "ci_inventory": str(ci.relative_to(REPO)) if ci.is_file() else None,
        "manifest_inventory": str(manifests.relative_to(REPO)) if manifests.is_file() else None,
        "ruff_versions_found": unique,
        "ruff_pin_used": RUFF_PIN,
        "ruff_pin_source": (
            "AUD-0041 quality.yml gate-lint-format pip install ruff==0.15.17"
            if "0.15.17" in unique
            else "fallback-constant"
        ),
        "bandit_in_ci": False,
        "semgrep_in_ci": False,
        "bandit_pin_used": BANDIT_PIN,
        "semgrep_pin_used": SEMGREP_PIN,
        "bandit_pin_source": "not-in-CI-YAML-inventory; PyPI version recorded at measurement",
        "semgrep_pin_source": "not-in-CI-YAML-inventory; PyPI version recorded at measurement",
    }


def live_git_status() -> dict[str, Any]:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(REPO),
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "inside_work_tree": False,
            "reason": f"{type(exc).__name__}:{exc}",
            "live_blob_scan": "NOT-CHECKED",
        }
    inside = p.returncode == 0 and (p.stdout or b"").decode().strip() == "true"
    err = (p.stderr or b"").decode("utf-8", errors="replace").strip()[:240]
    return {
        "inside_work_tree": inside,
        "exit_code": p.returncode,
        "stderr_tail": err,
        "live_blob_scan": "available" if inside else "NOT-CHECKED",
        "reason": None if inside else (err or "not a git repository"),
    }


def _parse_json_blob(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        start_arr = text.find("[")
        idxs = [i for i in (start, start_arr) if i >= 0]
        if not idxs:
            return None
        i = min(idxs)
        try:
            return json.loads(text[i:])
        except json.JSONDecodeError:
            return None


def count_ruff(tree: Path) -> dict[str, Any]:
    tools = ensure_tools()
    argv = [tools["ruff_bin"], "check", "--no-cache", "--output-format=json", "."]
    code, out, err = run_cmd(argv, cwd=tree, timeout=90)
    data = _parse_json_blob(out)
    findings = data if isinstance(data, list) else []
    per_rule: Counter[str] = Counter()
    per_file: dict[str, Counter[str]] = {}
    for row in findings:
        if not isinstance(row, dict):
            continue
        rule = str(row.get("code") or "UNKNOWN")
        fn = str(row.get("filename") or row.get("path") or "")
        base = Path(fn).name if fn else ""
        per_rule[rule] += 1
        per_file.setdefault(base, Counter())[rule] += 1
    return {
        "tool": "ruff",
        "version_pin": RUFF_PIN,
        "argv": argv,
        "exit_code": code,
        "stderr_tail": err[-800:],
        "finding_count": sum(per_rule.values()),
        "per_rule": dict(sorted(per_rule.items())),
        "per_file": {k: dict(sorted(v.items())) for k, v in sorted(per_file.items())},
        "parse_ok": isinstance(data, list),
    }


def count_bandit(tree: Path) -> dict[str, Any]:
    ensure_tools()
    argv = [
        sys.executable,
        "-B",
        "-m",
        "bandit",
        "-r",
        ".",
        "-f",
        "json",
        "-q",
    ]
    code, out, err = run_cmd(argv, cwd=tree, timeout=90)
    data = _parse_json_blob(out)
    results = []
    if isinstance(data, dict):
        results = data.get("results") or []
    per_rule: Counter[str] = Counter()
    per_file: dict[str, Counter[str]] = {}
    for row in results:
        if not isinstance(row, dict):
            continue
        rule = str(row.get("test_id") or "UNKNOWN")
        fn = str(row.get("filename") or "")
        base = Path(fn).name if fn else ""
        per_rule[rule] += 1
        per_file.setdefault(base, Counter())[rule] += 1
    return {
        "tool": "bandit",
        "version_pin": BANDIT_PIN,
        "argv": argv,
        "exit_code": code,
        "stderr_tail": err[-800:],
        "finding_count": sum(per_rule.values()),
        "per_rule": dict(sorted(per_rule.items())),
        "per_file": {k: dict(sorted(v.items())) for k, v in sorted(per_file.items())},
        "parse_ok": isinstance(data, dict),
    }


def _semgrep_findings(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        res = data.get("results") or data.get("matches") or []
        if isinstance(res, list):
            return [r for r in res if isinstance(r, dict)]
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return []


def _write_semgrep_targets(files: list[Path], dest: Path) -> None:
    targets: list[Any] = []
    for path in files:
        rel = "/" + path.name
        for analyzer in ("python", "regex"):
            targets.append(
                [
                    "CodeTarget",
                    {
                        "path": {"fpath": str(path), "ppath": rel},
                        "analyzer": analyzer,
                        "products": ["sast"],
                    },
                ]
            )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(["Targets", targets]), encoding="utf-8")


def count_semgrep(tree: Path) -> dict[str, Any]:
    files = sorted(
        p
        for p in tree.rglob("*.py")
        if p.is_file() and ".ruff_cache" not in p.parts
    )
    return count_semgrep_files(files)


def scan_tree(tree: Path) -> dict[str, Any]:
    return {
        "tree": str(tree.relative_to(REPO)) if tree.is_relative_to(REPO) else str(tree),
        "ruff": count_ruff(tree),
        "semgrep": count_semgrep(tree),
        "bandit": count_bandit(tree),
    }


def file_tool_counts(scan: dict[str, Any], filename: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for tool in ("ruff", "semgrep", "bandit"):
        per_file = (scan.get(tool) or {}).get("per_file") or {}
        rules = per_file.get(filename) or {}
        out[tool] = int(sum(rules.values())) if isinstance(rules, dict) else 0
    return out


def total_per_rule(scan: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
        tool: dict((scan.get(tool) or {}).get("per_rule") or {})
        for tool in ("ruff", "semgrep", "bandit")
    }


def versions() -> dict[str, Any]:
    tools = ensure_tools()
    ruff_code, ruff_out, ruff_err = run_cmd(
        [tools["ruff_bin"], "--version"], cwd=Path("/tmp"), timeout=20
    )
    b_code, b_out, b_err = run_cmd(
        [sys.executable, "-B", "-m", "bandit", "--version"],
        cwd=Path("/tmp"),
        timeout=20,
    )
    core = tools.get("semgrep_core")
    s_code, s_out, s_err = (127, "", "semgrep-core missing")
    if core:
        s_code, s_out, s_err = run_cmd([core, "-version"], cwd=Path("/tmp"), timeout=20)
    return {
        "ruff": {
            "pin": RUFF_PIN,
            "exit_code": ruff_code,
            "text": (ruff_out or ruff_err).strip()[:200],
        },
        "bandit": {
            "pin": BANDIT_PIN,
            "exit_code": b_code,
            "text": (b_out or b_err).strip()[:200],
        },
        "semgrep": {
            "pin": SEMGREP_PIN,
            "exit_code": s_code,
            "text": (s_out or s_err).strip()[:200],
            "core": core,
        },
    }


def live_python_files() -> list[Path]:
    skip = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "deps",
        "blob-tree",
        "cache",
        "_scratch",
    }
    root = REPO / "command-center"
    out: list[Path] = []
    if not root.is_dir():
        return out
    for p in root.rglob("*.py"):
        if "probes" in p.parts:
            continue
        if any(s in p.parts for s in skip):
            continue
        out.append(p)
    return sorted(out)


def count_ruff_files(files: list[Path]) -> dict[str, Any]:
    if not files:
        return {
            "tool": "ruff",
            "finding_count": 0,
            "per_rule": {},
            "parse_ok": True,
            "file_count": 0,
        }
    tools = ensure_tools()
    argv = [
        tools["ruff_bin"],
        "check",
        "--no-cache",
        "--output-format=json",
        *[str(p) for p in files],
    ]
    code, out, err = run_cmd(argv, cwd=Path("/tmp"), timeout=90)
    data = _parse_json_blob(out)
    findings = data if isinstance(data, list) else []
    per_rule: Counter[str] = Counter()
    for row in findings:
        if isinstance(row, dict):
            per_rule[str(row.get("code") or "UNKNOWN")] += 1
    return {
        "tool": "ruff",
        "version_pin": RUFF_PIN,
        "exit_code": code,
        "stderr_tail": err[-400:],
        "finding_count": sum(per_rule.values()),
        "per_rule": dict(sorted(per_rule.items())),
        "parse_ok": isinstance(data, list),
        "file_count": len(files),
    }


def count_bandit_files(files: list[Path]) -> dict[str, Any]:
    if not files:
        return {
            "tool": "bandit",
            "finding_count": 0,
            "per_rule": {},
            "parse_ok": True,
            "file_count": 0,
        }
    ensure_tools()
    argv = [
        sys.executable,
        "-B",
        "-m",
        "bandit",
        "-f",
        "json",
        "-q",
        *[str(p) for p in files],
    ]
    code, out, err = run_cmd(argv, cwd=Path("/tmp"), timeout=90)
    data = _parse_json_blob(out)
    results = (data.get("results") or []) if isinstance(data, dict) else []
    per_rule: Counter[str] = Counter()
    for row in results:
        if isinstance(row, dict):
            per_rule[str(row.get("test_id") or "UNKNOWN")] += 1
    return {
        "tool": "bandit",
        "version_pin": BANDIT_PIN,
        "exit_code": code,
        "stderr_tail": err[-400:],
        "finding_count": sum(per_rule.values()),
        "per_rule": dict(sorted(per_rule.items())),
        "parse_ok": isinstance(data, dict),
        "file_count": len(files),
    }


def count_semgrep_files(files: list[Path]) -> dict[str, Any]:
    if not files:
        return {
            "tool": "semgrep",
            "finding_count": 0,
            "per_rule": {},
            "per_file": {},
            "parse_ok": True,
            "file_count": 0,
        }
    tools = ensure_tools()
    core = tools.get("semgrep_core")
    if not core:
        return {
            "tool": "semgrep",
            "finding_count": 0,
            "per_rule": {},
            "per_file": {},
            "parse_ok": False,
            "file_count": len(files),
            "error": "semgrep-core binary missing after wheel extract",
        }
    tgt = HERE / "cache" / f"semgrep-targets-{os.getpid()}.json"
    _write_semgrep_targets(files, tgt)
    argv = [
        core,
        "-json_nodots",
        "-rules",
        str(rules_path()),
        "-targets",
        str(tgt),
    ]
    code, out, err = run_cmd(argv, cwd=Path("/tmp"), timeout=90)
    data = _parse_json_blob(out)
    findings = _semgrep_findings(data)
    per_rule: Counter[str] = Counter()
    per_file: dict[str, Counter[str]] = {}
    for row in findings:
        rule = str(row.get("check_id") or row.get("rule_id") or "UNKNOWN")
        path = str(row.get("path") or "")
        base = Path(path).name if path else ""
        per_rule[rule] += 1
        per_file.setdefault(base, Counter())[rule] += 1
    return {
        "tool": "semgrep",
        "version_pin": SEMGREP_PIN,
        "method": "semgrep-core -json_nodots -rules <vendored.yaml> -targets Targets JSON",
        "argv": argv,
        "exit_code": code,
        "stderr_tail": err[-400:],
        "finding_count": sum(per_rule.values()),
        "per_rule": dict(sorted(per_rule.items())),
        "per_file": {k: dict(sorted(v.items())) for k, v in sorted(per_file.items())},
        "parse_ok": isinstance(data, dict) and not (data.get("errors") or []),
        "file_count": len(files),
        "rules_path": str(rules_path().relative_to(REPO)),
    }


def live_worktree_scan() -> dict[str, Any]:
    files = live_python_files()
    rels = [p.relative_to(REPO).as_posix() for p in files]
    return {
        "method": "Linux worktree bytes; not git cat-file blobs (estate has no .git)",
        "file_count": len(files),
        "files_head": rels[:20],
        "ruff": count_ruff_files(files),
        "semgrep": count_semgrep_files(files),
        "bandit": count_bandit_files(files),
        "used_git_archive": False,
        "used_git_cat_file": False,
    }


def comparable_scan() -> dict[str, Any]:
    trees = materialize_comparable_trees()
    blob = scan_tree(blob_tree_dir())
    windows = scan_tree(windows_tree_dir())
    sensitive_blob = file_tool_counts(blob, SENSITIVE_NAME)
    sensitive_win = file_tool_counts(windows, SENSITIVE_NAME)
    differ = sensitive_blob != sensitive_win
    blob_raw = git_cat_file(SENSITIVE_NAME)
    win_raw = (windows_tree_dir() / SENSITIVE_NAME).read_bytes()
    control = {
        "file": SENSITIVE_NAME,
        "blob_cr": cr_count(blob_raw),
        "windows_cr": cr_count(win_raw),
        "blob_bytes": len(blob_raw),
        "windows_bytes": len(win_raw),
        "sha_differ": hashlib.sha256(blob_raw).hexdigest()
        != hashlib.sha256(win_raw).hexdigest(),
        "blob_is_lf": cr_count(blob_raw) == 0 and b"\n" in blob_raw,
        "windows_is_crlf": win_raw.count(b"\r\n") > 0 and b"\r\n" in win_raw,
        "counts_blob": sensitive_blob,
        "counts_windows": sensitive_win,
        "counts_differ": differ,
        "used_git_archive": False,
        "pass": bool(
            differ
            and cr_count(blob_raw) == 0
            and cr_count(win_raw) > 0
            and blob_raw != win_raw
        ),
    }
    return {
        "trees": trees,
        "blob": blob,
        "windows_worktree": windows,
        "per_rule": {
            "blob": total_per_rule(blob),
            "windows_worktree": total_per_rule(windows),
        },
        "control": control,
    }


def measure() -> dict[str, Any]:
    pins = discover_ruff_pin()
    git_st = live_git_status()
    tools = ensure_tools()
    vers = versions()
    comparable = comparable_scan()
    live = live_worktree_scan()
    return {
        "pins": pins,
        "tools": {
            "ruff_bin": tools["ruff_bin"],
            "semgrep_core": tools.get("semgrep_core"),
            "py_deps": tools["py_deps"],
        },
        "versions": vers,
        "live_git": git_st,
        "comparable": comparable,
        "live_linux_worktree": live,
    }


def control_ok(snap: dict[str, Any] | None = None) -> bool:
    snap = snap or measure()
    return bool(((snap.get("comparable") or {}).get("control") or {}).get("pass"))


if __name__ == "__main__":
    snap = measure()
    ctl = snap["comparable"]["control"]
    print(json.dumps({"control": ctl, "per_rule": snap["comparable"]["per_rule"]}, sort_keys=True))
    print(
        f"control_pass={ctl['pass']} blob={ctl['counts_blob']} "
        f"windows={ctl['counts_windows']}"
    )
    raise SystemExit(0 if ctl["pass"] else 1)
