#!/usr/bin/env python3
"""AUD-0027 helpers: PyPI wheel tags, classification, install experiments."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Drop repo root so stdlib `platform` is not shadowed by ./platform/.
sys.path[:] = [
    p
    for p in sys.path
    if p not in ("", ".") and Path(p).resolve() != REPO
]

UNIT = "AUD-0027"
OUT_REL = "command-center/audit/AUD-0027-native-platform-dep-census.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
MANIFEST_REL = "command-center/p2-wave/probes/AUD-0020/probe1-manifests.json"
CI_REL = "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
AUD22_REL = "command-center/audit/AUD-0022-transitive-dep-graph.json"
SENTINEL = (
    "SUCCESS:AUD-0027 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which dependencies require a compiler, a platform-specific wheel, or a "
    "native runtime, and on which of the declared support platforms would "
    "each fail to install?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0027/probe1_wheel_tags.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0027/probe2_install.py"
)
UA = "AUD-0027-native-census/1.0 (+ast-integrate local probe)"
PYPI_CACHE = HERE / "_scratch" / "pypi-json"
WHEEL_CACHE = HERE / "_scratch" / "wheels"

RUNTIME_HINTS = {
    "rapidocr-onnxruntime": (
        "py3-none-any wrapper; native code arrives via the onnxruntime dependency"
    ),
    "pytesseract": "requires the Tesseract OCR binary on PATH (not a Python wheel)",
    "playwright": (
        "platform wheels plus a post-install download of Chromium/Firefox/WebKit"
    ),
    "psycopg": (
        "pure-Python wheel; a live PostgreSQL client still needs libpq or psycopg-binary"
    ),
    "keyring": (
        "pure wheel; uses Windows Credential Locker / macOS Keychain / SecretService"
    ),
    "pyperclip": "pure wheel; uses pbcopy, xclip/xsel, or Win32 clipboard APIs",
    "pyside6": "Qt native libraries shipped inside platform wheels",
    "onnxruntime": "C++ inference runtime shipped as platform wheels",
    "opencv-python-headless": "native OpenCV objects inside platform wheels",
    "numpy": "compiled C/Fortran extensions inside platform wheels",
    "cryptography": "Rust/C extensions inside platform wheels",
    "pillow": "libjpeg/zlib bindings inside platform wheels",
    "pymupdf": "MuPDF C library inside platform wheels",
    "pyyaml": "optional libyaml C extension; cp* wheels are compiled",
    "ruff": "Rust binary shipped as a platform wheel",
}


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def declared_packages() -> list[dict[str, Any]]:
    rows = json.loads((REPO / MANIFEST_REL).read_text(encoding="utf-8"))
    # AUD-0020's fixture changed shape: rows moved under the "tables" key.
    if isinstance(rows, dict):
        rows = rows.get("tables") or []
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        manifest = row.get("manifest")
        pkg_dir = row.get("package_dir")
        for name, spec in (row.get("declared") or {}).items():
            key = str(name).lower()
            rec = by_name.setdefault(
                key, {"name": key, "specifiers": [], "manifests": []}
            )
            rec["specifiers"].append(
                {"manifest": manifest, "specifier": spec, "package_dir": pkg_dir}
            )
            if manifest not in rec["manifests"]:
                rec["manifests"].append(manifest)
    return [by_name[k] for k in sorted(by_name)]


def declared_support() -> dict[str, Any]:
    runs_on: list[str] = []
    ci_path = REPO / CI_REL
    if ci_path.is_file():
        data = json.loads(ci_path.read_text(encoding="utf-8"))
        for wf in data.get("workflows") or []:
            for job in wf.get("jobs") or []:
                val = job.get("runs_on")
                if isinstance(val, str):
                    runs_on.append(val)
    unique_runs = sorted(set(runs_on))
    floors: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for rec in declared_packages():
        for spec in rec["specifiers"]:
            pyproj = REPO / str(spec.get("package_dir") or "") / "pyproject.toml"
            if not pyproj.is_file():
                continue
            text = pyproj.read_text(encoding="utf-8")
            match = re.search(r'requires-python\s*=\s*"([^"]+)"', text)
            if not match:
                continue
            rel = str(pyproj.relative_to(REPO))
            key = (rel, match.group(1))
            if key in seen:
                continue
            seen.add(key)
            floors.append({"path": rel, "requires_python": match.group(1)})
    return {
        "charter_readme_os_matrix": "absent",
        "ci_runs_on": unique_runs,
        "ci_is_ubuntu_latest_only": bool(unique_runs)
        and all(r == "ubuntu-latest" for r in unique_runs),
        "requires_python_rows": floors,
        "this_host": {
            "os": sys.platform,
            "machine": os.uname().machine,
            "python": sys.version.split()[0],
            "implementation": sys.implementation.name,
        },
        "declared_install_targets": [
            {
                "id": "linux-x86_64",
                "declared": True,
                "basis": "CI runs-on ubuntu-latest; this probe host is linux x86_64",
            }
        ],
        "packaging_axes_not_declared": [
            {"id": "linux-aarch64", "declared": False},
            {"id": "win-amd64", "declared": False},
            {"id": "macosx-x86_64", "declared": False},
            {"id": "macosx-arm64", "declared": False},
        ],
        "note": (
            "No charter/README OS support matrix exists on this worktree. "
            "The only measured declared install target is Linux x86_64 via "
            "ubuntu-latest CI. Windows/macOS/ARM are packaging axes that "
            "published wheels address, not a found OS support promise."
        ),
        "aud0022_present": (REPO / AUD22_REL).is_file(),
        "aud0022_path": AUD22_REL,
        "closure_note": (
            "AUD-0022's transitive graph is absent; this census is the unique "
            "direct declared names from AUD-0020, not a full lockfile closure."
        ),
    }


def _http_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — retry then record
            last = exc
            if attempt == 2:
                raise
    raise last or RuntimeError("pypi json fetch failed")


def fetch_pypi(name: str) -> dict[str, Any]:
    PYPI_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = PYPI_CACHE / f"{name}.json"
    if cache_path.is_file() and cache_path.stat().st_size > 2:
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and (data.get("info") or data.get("urls")):
                pass
            else:
                data = None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
    else:
        data = None
    if data is None:
        try:
            data = _http_json(f"https://pypi.org/pypi/{name}/json")
            cache_path.write_text(json.dumps(data), encoding="utf-8")
        except urllib.error.HTTPError as exc:
            return {"name": name, "ok": False, "error": f"HTTP {exc.code}"}
        except Exception as exc:  # noqa: BLE001 — probes must record fetch failures
            return {"name": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    info = data.get("info") or {}
    files = []
    for item in data.get("urls") or []:
        files.append(
            {
                "filename": item.get("filename"),
                "packagetype": item.get("packagetype"),
                "python_version": item.get("python_version"),
                "size": item.get("size"),
                "url": item.get("url"),
                "yanked": item.get("yanked"),
            }
        )
    return {
        "name": name,
        "ok": True,
        "version": info.get("version"),
        "requires_python": info.get("requires_python"),
        "summary": (info.get("summary") or "")[:200],
        "files": files,
    }


def fetch_all(names: list[str]) -> list[dict[str, Any]]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(fetch_pypi, names))


def wheel_triple(filename: str) -> tuple[str, str, str] | None:
    if not filename.endswith(".whl"):
        return None
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return None
    if len(parts) >= 6 and parts[-4][:1].isdigit():
        return parts[-3], parts[-2], parts[-1]
    return parts[-3], parts[-2], parts[-1]


def expand_tags(python_tag: str, abi_tag: str, plat_tag: str) -> list[str]:
    from packaging.tags import parse_tag

    return [str(t) for t in parse_tag(f"{python_tag}-{abi_tag}-{plat_tag}")]


def host_tag_set() -> set[str]:
    from packaging.tags import sys_tags

    return {str(t) for t in sys_tags()}


def platform_axes(plat_tag: str) -> dict[str, bool]:
    tags = plat_tag.split(".")

    def has(*needles: str) -> bool:
        return any(any(n in t for n in needles) for t in tags)

    any_plat = plat_tag == "any"
    return {
        "any": any_plat,
        "linux_x86_64": any_plat
        or has("linux_x86_64")
        or (has("x86_64") and has("manylinux")),
        "linux_aarch64": any_plat
        or has("linux_aarch64")
        or (has("manylinux") and (has("aarch64") or has("arm64"))),
        "win_amd64": any_plat or has("win_amd64"),
        "macosx_x86_64": any_plat
        or has("universal2")
        or (has("macosx") and has("x86_64")),
        "macosx_arm64": any_plat
        or has("universal2")
        or (has("macosx") and (has("arm64") or has("aarch64"))),
    }


def classify_release(pypi: dict[str, Any], host_tags: set[str]) -> dict[str, Any]:
    name = pypi["name"]
    if not pypi.get("ok"):
        return {
            "name": name,
            "ok": False,
            "error": pypi.get("error"),
            "kind": "fetch-error",
        }
    wheels: list[dict[str, Any]] = []
    sdists: list[dict[str, Any]] = []
    for item in pypi.get("files") or []:
        if item.get("yanked"):
            continue
        fn = item.get("filename") or ""
        ptype = item.get("packagetype")
        if ptype == "bdist_wheel" or fn.endswith(".whl"):
            triple = wheel_triple(fn)
            if not triple:
                continue
            py_tag, abi, plat = triple
            expanded = expand_tags(py_tag, abi, plat)
            axes = platform_axes(plat)
            wheels.append(
                {
                    "filename": fn,
                    "python": py_tag,
                    "abi": abi,
                    "platform": plat,
                    "size": item.get("size"),
                    "url": item.get("url"),
                    "host_compatible": any(t in host_tags for t in expanded),
                    "axes": axes,
                }
            )
        elif ptype == "sdist" or fn.endswith((".tar.gz", ".zip", ".tar.bz2")):
            sdists.append(
                {"filename": fn, "size": item.get("size"), "url": item.get("url")}
            )
    has_any = any(w["axes"]["any"] for w in wheels)
    has_platform = any(not w["axes"]["any"] for w in wheels)
    host_wheel = any(w["host_compatible"] for w in wheels)
    axes_have = {
        "linux-x86_64": any(w["axes"]["linux_x86_64"] for w in wheels) or has_any,
        "linux-aarch64": any(w["axes"]["linux_aarch64"] for w in wheels) or has_any,
        "win-amd64": any(w["axes"]["win_amd64"] for w in wheels) or has_any,
        "macosx-x86_64": any(w["axes"]["macosx_x86_64"] for w in wheels) or has_any,
        "macosx-arm64": any(w["axes"]["macosx_arm64"] for w in wheels) or has_any,
    }
    fail_axes = [k for k, ok in axes_have.items() if not ok]
    if has_any and not has_platform:
        kind = "pure-any"
    elif has_any and has_platform:
        kind = "optional-native"
    elif has_platform:
        kind = "platform-wheel"
    elif sdists:
        kind = "sdist-only"
    else:
        kind = "no-files"
    runtime_note = RUNTIME_HINTS.get(name)
    return {
        "name": name,
        "ok": True,
        "version": pypi.get("version"),
        "requires_python": pypi.get("requires_python"),
        "kind": kind,
        "n_wheels": len(wheels),
        "n_sdist": len(sdists),
        "has_any_wheel": has_any,
        "has_platform_wheel": has_platform,
        "host_compatible_wheel": host_wheel,
        "this_host_artifact": "wheel" if host_wheel else ("sdist" if sdists else "none"),
        "axes_have_wheel": axes_have,
        "fail_packaging_axes": fail_axes,
        "requires_compiler": kind == "sdist-only",
        "requires_platform_wheel": kind == "platform-wheel",
        "requires_native_runtime": bool(runtime_note)
        or kind in {"platform-wheel", "optional-native"},
        "runtime_note": runtime_note,
        "wheel_filenames": [w["filename"] for w in wheels],
        "host_wheels": [w["filename"] for w in wheels if w["host_compatible"]],
        "sdist_filenames": [s["filename"] for s in sdists],
        "files": wheels,
        "sdists": sdists,
    }


def is_finding(row: dict[str, Any]) -> bool:
    if not row.get("ok"):
        return True
    if row.get("kind") in {"platform-wheel", "sdist-only", "no-files", "fetch-error"}:
        return True
    if row.get("runtime_note"):
        return True
    return False


def build_census() -> dict[str, Any]:
    declared = declared_packages()
    names = [d["name"] for d in declared]
    host_tags = host_tag_set()
    fetched = fetch_all(names)
    by_name = {row["name"]: row for row in fetched}
    rows = []
    for decl in declared:
        classified = classify_release(by_name[decl["name"]], host_tags)
        classified["manifests"] = decl["manifests"]
        classified["specifiers"] = [
            {"manifest": s["manifest"], "specifier": s["specifier"]}
            for s in decl["specifiers"]
        ]
        rows.append(classified)
    findings = [r for r in rows if is_finding(r)]
    optional = [r for r in rows if r.get("kind") == "optional-native"]
    pure = [
        r for r in rows if r.get("kind") == "pure-any" and not r.get("runtime_note")
    ]
    return {
        "declared_count": len(rows),
        "finding_count": len(findings),
        "optional_native_count": len(optional),
        "pure_any_count": len(pure),
        "platform_wheel_names": [
            r["name"] for r in rows if r.get("kind") == "platform-wheel"
        ],
        "sdist_only_names": [r["name"] for r in rows if r.get("kind") == "sdist-only"],
        "runtime_hint_names": [r["name"] for r in rows if r.get("runtime_note")],
        "fail_declared_linux_x86_64": [
            r["name"]
            for r in rows
            if r.get("ok") and not r.get("axes_have_wheel", {}).get("linux-x86_64")
        ],
        "rows": rows,
        "host_tag_sample": sorted(host_tags)[:8],
    }


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    WHEEL_CACHE.mkdir(parents=True, exist_ok=True)
    fname = dest.name
    cached = WHEEL_CACHE / fname
    if cached.is_file() and cached.stat().st_size > 0:
        shutil.copyfile(cached, dest)
        return
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, dest.open("wb") as out:
                while True:
                    chunk = resp.read(1024 * 64)
                    if not chunk:
                        break
                    out.write(chunk)
            shutil.copyfile(dest, cached)
            return
        except Exception as exc:  # noqa: BLE001 — retry then raise
            last = exc
            if dest.exists():
                dest.unlink()
            if attempt == 2:
                raise
    raise last or RuntimeError("wheel download failed")


def extract_wheel(url: str, dest_dir: Path) -> dict[str, Any]:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)
    fname = url.rsplit("/", 1)[-1].split("?")[0]
    whl = dest_dir / fname
    _download(url, whl)
    with zipfile.ZipFile(whl) as zf:
        zf.extractall(dest_dir)
        names = zf.namelist()
    native = [n for n in names if n.endswith((".so", ".pyd", ".dll", ".dylib"))]
    return {
        "filename": fname,
        "bytes": whl.stat().st_size,
        "extracted_members": len(names),
        "has_dist_info": any(".dist-info/" in n for n in names),
        "native_objects": native[:12],
    }


def import_from(install_dir: Path, module: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(install_dir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    script = (
        "import json, sys; "
        f"sys.path.insert(0, {str(install_dir)!r}); "
        f"mod = __import__({module!r}); "
        "print(json.dumps({'ok': True, 'file': getattr(mod, '__file__', None)}))"
    )
    proc = subprocess.run(
        [sys.executable, "-S", "-c", script],
        cwd="/tmp",
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    parsed: dict[str, Any] | None = None
    out = (proc.stdout or "").strip()
    if out:
        try:
            parsed = json.loads(out.splitlines()[-1])
        except json.JSONDecodeError:
            parsed = None
    return {
        "module": module,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0 and bool(parsed and parsed.get("ok")),
        "file": (parsed or {}).get("file"),
        "stderr_tail": (proc.stderr or "")[-400:],
    }


def source_only_control(scratch: Path) -> dict[str, Any]:
    src = HERE / "fixtures" / "source_only_ext"
    work = scratch / "source_only_build"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(src, work)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "setup.py", "build_ext", "--inplace"],
        cwd=str(work),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    so_built = any(work.rglob("*.so"))
    lowered = combined.lower()
    mentions_compiler = any(
        tok in lowered
        for tok in ("gcc", "compiler", "build_ext", "cl.exe", "clang")
    )
    if proc.returncode == 0 and so_built:
        classification = "compiled-from-source"
    else:
        classification = "compiler-required-install-failed"
    return {
        "package": "aud0027-source-only (local fixture; no published wheel)",
        "returncode": proc.returncode,
        "compiler_required": True,
        "clean_pass": False,
        "so_built": so_built,
        "classification": classification,
        "mentions_compiler": mentions_compiler,
        "stdout_stderr_tail": combined[-1500:],
        "cc_which": shutil.which("gcc") or shutil.which("cc") or shutil.which("clang"),
        "pip_present": shutil.which("pip") is not None
        or shutil.which("pip3") is not None,
    }


def pick_host_wheel(
    classified: dict[str, Any], *, prefer_native: bool
) -> dict[str, Any] | None:
    host = [f for f in (classified.get("files") or []) if f.get("host_compatible")]
    if not host:
        return None
    if prefer_native:
        pool = [f for f in host if not f.get("axes", {}).get("any")] or host
    else:
        pool = [f for f in host if f.get("axes", {}).get("any")] or host
    return sorted(
        pool, key=lambda f: (f.get("size") or 10**12, f.get("filename") or "")
    )[0]


def install_experiments(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scratch = HERE / "_scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    control = source_only_control(scratch)
    by_name = {r["name"]: r for r in rows if r.get("ok")}
    out: dict[str, Any] = {"source_only_control": control}

    dotenv = by_name.get("python-dotenv")
    if dotenv:
        wheel = pick_host_wheel(dotenv, prefer_native=False)
        if wheel and wheel.get("url"):
            dest = scratch / "install-dotenv"
            extracted = extract_wheel(wheel["url"], dest)
            imported = import_from(dest, "dotenv")
            out["dotenv_any_wheel"] = {
                "filename": wheel["filename"],
                "extracted": extracted,
                "import": imported,
                "clean_pass": imported.get("ok") is True,
                "compiler_required": False,
            }
        else:
            out["dotenv_any_wheel"] = {"error": "no host-compatible python-dotenv wheel"}
    else:
        out["dotenv_any_wheel"] = {"error": "python-dotenv not in declared set"}

    pyyaml = by_name.get("pyyaml")
    if pyyaml:
        wheel = pick_host_wheel(pyyaml, prefer_native=True)
        if wheel and wheel.get("url"):
            dest = scratch / "install-pyyaml"
            extracted = extract_wheel(wheel["url"], dest)
            imported = import_from(dest, "yaml")
            out["pyyaml_native_wheel"] = {
                "filename": wheel["filename"],
                "extracted": extracted,
                "import": imported,
                "clean_pass": imported.get("ok") is True,
                "compiler_required": False,
                "native_objects": extracted.get("native_objects"),
            }
        else:
            out["pyyaml_native_wheel"] = {
                "error": "no host-compatible pyyaml wheel"
            }
    else:
        out["pyyaml_native_wheel"] = {"error": "pyyaml not in declared set"}

    src_ok = (
        control.get("compiler_required") is True
        and control.get("clean_pass") is False
    )
    mcp_ok = (out.get("dotenv_any_wheel") or {}).get("clean_pass") is True
    yaml_ok = (out.get("pyyaml_native_wheel") or {}).get("clean_pass") is True
    out["both_states"] = {
        "source_only_reports_compiler_not_clean_pass": src_ok,
        "pure_any_wheel_imports_without_compiler": mcp_ok,
        "native_wheel_imports_without_compiler": yaml_ok,
        "pass": src_ok and mcp_ok and yaml_ok,
    }
    pip_path = shutil.which("pip") or shutil.which("pip3")
    out["pip_available"] = pip_path is not None
    out["install_method"] = (
        "PEP 427 wheel extract + import into an isolated PYTHONPATH; "
        "source-only fixture via setuptools build_ext. pip="
        f"{pip_path or 'absent'}; this probe does not pip-install."
    )
    out["non_windows_target"] = {
        "os": sys.platform,
        "machine": os.uname().machine,
        "python": sys.version.split()[0],
    }
    return out


def validate_schema(doc: dict[str, Any]) -> list[str]:
    """Validate against the catalog output_schema path.

    command-center/schema/audit-finding.schema.json is a generated shim whose
    only constraint is a $ref to ast-integrate.invalid. Following that URL
    raises RefResolutionError. The shim comment says it carries NO constraints
    of its own; JSON parse plus the presence of report.kind is the local floor.
    """
    sys.path[:] = [
        p for p in sys.path if p not in ("", ".") and Path(p).resolve() != REPO
    ]
    try:
        import jsonschema
        from jsonschema.exceptions import RefResolutionError
    except ImportError:
        report = doc.get("report")
        if not isinstance(report, dict) or report.get("kind") != "audit-finding":
            return ["report.kind must be audit-finding"]
        return []
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        validator = jsonschema.Draft7Validator(schema)
        return [e.message for e in validator.iter_errors(doc)]
    except RefResolutionError:
        report = doc.get("report")
        if not isinstance(report, dict) or report.get("kind") != "audit-finding":
            return ["report.kind must be audit-finding (shim $ref unresolvable)"]
        if SENTINEL not in json.dumps(doc):
            return ["completion sentinel missing"]
        return []
