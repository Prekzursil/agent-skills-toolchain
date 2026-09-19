#!/usr/bin/env python3
"""AUD-0027 Probe 1: wheel tag matrix published for each package.

Catalog evidence_requirement verbatim:
  Probe 1: the wheel tag matrix published for each package.

Inputs: AUD-0022 transitive closure + declared support contract (Windows/Linux/macOS,
CPython 3.12 per AGENTS.md / quality CI / cross-platform release plan).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-wheel-tag-matrix.json"
OUT_RAW = PROBE / "probe1-wheel-tag-matrix.raw.txt"
AUD0022 = REPO / "command-center/audit/AUD-0022-transitive-dep-graph.json"

CATALOG_VERBATIM = "Probe 1: the wheel tag matrix published for each package."

# Declared support contract (docs/plans/2026-03-11-cross-platform-release-layer.md
# + AGENTS.md Cursor Cloud / quality.yml ubuntu-latest + Windows-first workstation).
DECLARED_PLATFORMS = [
    {
        "id": "linux-x86_64-cp312",
        "os": "linux",
        "arch": "x86_64",
        "python": "3.12",
        "wheel_plat_needles": ("manylinux", "linux_x86_64", "musllinux"),
        "arch_needles": ("x86_64", "amd64"),
    },
    {
        "id": "windows-amd64-cp312",
        "os": "windows",
        "arch": "amd64",
        "python": "3.12",
        "wheel_plat_needles": ("win_amd64", "win32"),
        "arch_needles": ("win_amd64", "amd64", "win32"),
    },
    {
        "id": "macos-arm64-cp312",
        "os": "macos",
        "arch": "arm64",
        "python": "3.12",
        "wheel_plat_needles": ("macosx",),
        "arch_needles": ("arm64", "aarch64", "universal2"),
    },
    {
        "id": "macos-x86_64-cp312",
        "os": "macos",
        "arch": "x86_64",
        "python": "3.12",
        "wheel_plat_needles": ("macosx",),
        "arch_needles": ("x86_64", "universal2", "intel", "fat64"),
    },
]

PLANTED_SOURCE_ONLY = {
    "name": "crcmod",
    "version": "1.7",
    "reason": "PyPI publishes sdist only (zero wheels); planted negative control",
}

LOCAL_SKIP = {
    "scholarly-access-mcp"
}  # in-repo package, not on PyPI as a wheel census target

PYPI_NAME_FIX = {
    "pyyaml": "PyYAML",
    "pyjwt": "PyJWT",
    "jwcrypto": "jwcrypto",
}


def pypi_project(name: str) -> str:
    return PYPI_NAME_FIX.get(name.lower(), name)


def fetch_pypi(name: str, timeout: float = 45.0) -> dict | None:
    url = f"https://pypi.org/pypi/{pypi_project(name)}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.load(resp)
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        return {"_error": f"{type(exc).__name__}: {exc}", "_url": url}


def parse_wheel_tags(filename: str) -> dict | None:
    if not filename.endswith(".whl"):
        return None
    stem = filename[:-4]
    parts = stem.split("-")
    if len(parts) < 4:
        return None
    # PEP 427: {distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl
    python_tag, abi_tag, platform_tag = parts[-3], parts[-2], parts[-1]
    return {
        "filename": filename,
        "python_tag": python_tag,
        "abi_tag": abi_tag,
        "platform_tag": platform_tag,
        "tag": f"{python_tag}-{abi_tag}-{platform_tag}",
    }


def is_pure(tag: dict) -> bool:
    return tag["abi_tag"] == "none" and tag["platform_tag"] == "any"


def covers_cp312(tag: dict) -> bool:
    py = tag["python_tag"].lower()
    if "py3" in py.split(".") or py in {"py3", "py2.py3", "py3.py4"}:
        return True
    if "cp312" in py or "cp3" == py:
        return True
    # abi3 wheels usable on 3.12 if cp3x-abi3
    if "abi3" in tag["abi_tag"] and re.search(r"cp3(0|[1-9]|1[0-2])", py):
        return True
    if "cp312" in tag["abi_tag"]:
        return True
    return False


def platform_match(plat: dict, tag: dict) -> bool:
    if not covers_cp312(tag):
        return False
    if is_pure(tag):
        return True
    pt = tag["platform_tag"].lower()
    if not any(n in pt for n in plat["wheel_plat_needles"]):
        # win32 special-case for windows-amd64: prefer win_amd64 but note win32 separately
        if plat["os"] == "windows" and "win" in pt:
            return "win_amd64" in pt or pt == "win32"
        return False
    if plat["os"] == "macos":
        return any(n in pt for n in plat["arch_needles"])
    if plat["os"] == "linux":
        # exclude aarch64-only from x86_64 target
        if (
            "aarch64" in pt
            or "armv7" in pt
            or "ppc64" in pt
            or "s390x" in pt
            or "riscv" in pt
        ):
            if "x86_64" not in pt and "i686" not in pt:
                return False
        return any(
            n in pt for n in ("x86_64", "amd64", "i686", "manylinux", "musllinux")
        )
    if plat["os"] == "windows":
        return "win_amd64" in pt or (plat["arch"] == "amd64" and "win" in pt)
    return False


def classify_package(name: str, data: dict | None, *, planted: bool = False) -> dict:
    row: dict = {
        "name": name,
        "planted_source_only_control": planted,
        "pypi_project": pypi_project(name),
    }
    if data is None:
        row.update(
            {
                "status": "fetch-failed",
                "classification": "unknown",
                "error": "null-response",
            }
        )
        return row
    if "_error" in data:
        row.update(
            {
                "status": "fetch-failed",
                "classification": "unknown",
                "error": data["_error"],
                "url": data.get("_url"),
            }
        )
        return row

    version = data["info"].get("version")
    urls = data.get("urls") or []
    wheels = []
    sdists = []
    for u in urls:
        fn = u.get("filename") or ""
        if fn.endswith(".whl"):
            tag = parse_wheel_tags(fn)
            if tag:
                tag["packagetype"] = u.get("packagetype")
                wheels.append(tag)
        else:
            sdists.append(fn)

    pure = [w for w in wheels if is_pure(w)]
    platform_wheels = [w for w in wheels if not is_pure(w)]
    native_abi = [
        w
        for w in platform_wheels
        if w["abi_tag"] not in {"none", "abi3"} or "cp" in w["abi_tag"]
    ]
    # abi3 still counts as compiled/native runtime dependency
    compiledish = [w for w in platform_wheels if w["abi_tag"] != "none"]

    if not wheels and sdists:
        classification = "sdist-only"
    elif pure and not platform_wheels:
        classification = "pure-python"
    elif platform_wheels and not pure:
        classification = "platform-wheel-only"
    elif platform_wheels and pure:
        classification = "mixed-pure-and-platform"
    elif wheels:
        classification = "wheel-present"
    else:
        classification = "no-files"

    requires_compiler_or_native = classification in {
        "sdist-only",
        "platform-wheel-only",
        "mixed-pure-and-platform",
    } and (classification == "sdist-only" or bool(compiledish))
    if classification == "sdist-only":
        requires_compiler_or_native = True

    coverage = {}
    fail_platforms = []
    for plat in DECLARED_PLATFORMS:
        ok = any(platform_match(plat, w) for w in wheels) if wheels else False
        if classification == "sdist-only":
            ok = False  # no wheel → install needs compiler on every platform
        coverage[plat["id"]] = {
            "installable_via_wheel": ok,
            "would_need_sdist_build": not ok,
        }
        if not ok:
            fail_platforms.append(plat["id"])

    row.update(
        {
            "status": "ok",
            "version": version,
            "classification": classification,
            "wheel_count": len(wheels),
            "sdist_count": len(sdists),
            "pure_wheel_count": len(pure),
            "platform_wheel_count": len(platform_wheels),
            "compiled_abi_wheel_count": len(compiledish),
            "native_cp_abi_wheel_count": len(native_abi),
            "requires_compiler_platform_wheel_or_native": requires_compiler_or_native,
            "wheel_tags_sample": sorted({w["tag"] for w in wheels})[:40],
            "sdist_sample": sdists[:5],
            "declared_platform_coverage": coverage,
            "fail_install_platforms_without_wheel": fail_platforms,
            "summary": (
                f"{name}@{version} class={classification} wheels={len(wheels)} "
                f"sdist={len(sdists)} fail_plats={len(fail_platforms)}"
            ),
        }
    )
    return row


def load_aud0022_python_names() -> list[str]:
    doc = json.loads(AUD0022.read_text(encoding="utf-8"))
    names = []
    for n in doc.get("report", {}).get("nodes", []):
        if n.get("ecosystem") != "python":
            continue
        nid = n.get("id")
        if not nid:
            continue
        names.append(nid)
    # stable unique
    seen = set()
    out = []
    for n in names:
        k = n.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(n)
    return out


def main() -> int:
    names = load_aud0022_python_names()
    rows = []
    lines = [
        "unit=AUD-0027 probe=1",
        f"catalog_verbatim={CATALOG_VERBATIM}",
        f"aud0022_python_packages={len(names)}",
        f"declared_platforms={[p['id'] for p in DECLARED_PLATFORMS]}",
        f"planted_control={PLANTED_SOURCE_ONLY['name']}=={PLANTED_SOURCE_ONLY['version']}",
    ]

    for name in names:
        if name.lower() in {s.lower() for s in LOCAL_SKIP}:
            rows.append(
                {
                    "name": name,
                    "status": "skipped-local",
                    "classification": "in-repo-local",
                    "requires_compiler_platform_wheel_or_native": False,
                    "fail_install_platforms_without_wheel": [],
                    "note": "local package from AUD-0022; not queried on PyPI",
                }
            )
            lines.append(f"SKIP local {name}")
            continue
        data = fetch_pypi(name)
        row = classify_package(name, data, planted=False)
        rows.append(row)
        lines.append(row.get("summary") or f"{name} status={row.get('status')}")

    # Planted source-only control always included
    planted_data = fetch_pypi(PLANTED_SOURCE_ONLY["name"])
    # Prefer exact version file list if available
    if planted_data and "_error" not in planted_data:
        ver = PLANTED_SOURCE_ONLY["version"]
        try:
            url = f"https://pypi.org/pypi/{PLANTED_SOURCE_ONLY['name']}/{ver}/json"
            with urllib.request.urlopen(url, timeout=45) as resp:
                planted_data = json.load(resp)
        except Exception:
            pass
    planted_row = classify_package(
        PLANTED_SOURCE_ONLY["name"], planted_data, planted=True
    )
    planted_row["control_expected_classification"] = "sdist-only"
    planted_row["control_ok"] = planted_row.get("classification") == "sdist-only"
    rows.append(planted_row)
    lines.append(
        f"PLANTED {planted_row.get('summary')} control_ok={planted_row.get('control_ok')}"
    )

    live = [r for r in rows if not r.get("planted_source_only_control")]
    by_class = Counter(r.get("classification", "unknown") for r in live)
    native_or_platform = [
        r
        for r in live
        if r.get("requires_compiler_platform_wheel_or_native")
        and r.get("classification") not in {"in-repo-local"}
    ]
    sdist_only = [r for r in live if r.get("classification") == "sdist-only"]
    fail_any = [
        r
        for r in live
        if r.get("fail_install_platforms_without_wheel")
        and r.get("classification") not in {"in-repo-local", "unknown"}
    ]

    payload = {
        "ok": bool(planted_row.get("control_ok")) and by_class.total() > 0,
        "unit": "AUD-0027",
        "probe": 1,
        "catalog_verbatim": CATALOG_VERBATIM,
        "aud0022_path": str(AUD0022.relative_to(REPO)).replace("\\", "/"),
        "declared_platforms": DECLARED_PLATFORMS,
        "packages_queried": len(live),
        "by_classification": dict(by_class),
        "native_or_platform_count": len(native_or_platform),
        "sdist_only_count": len(sdist_only),
        "packages_failing_any_declared_platform": len(fail_any),
        "planted_source_only": {
            "name": PLANTED_SOURCE_ONLY["name"],
            "version": PLANTED_SOURCE_ONLY["version"],
            "classification": planted_row.get("classification"),
            "wheel_count": planted_row.get("wheel_count"),
            "control_ok": planted_row.get("control_ok"),
            "requires_compiler_platform_wheel_or_native": planted_row.get(
                "requires_compiler_platform_wheel_or_native"
            ),
        },
        "packages": rows,
        "native_or_platform_names": [r["name"] for r in native_or_platform],
        "sdist_only_names": [r["name"] for r in sdist_only],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines.append(
        f"SUMMARY packages={len(live)} by_class={dict(by_class)} "
        f"native_or_platform={len(native_or_platform)} sdist_only={len(sdist_only)} "
        f"fail_any_platform={len(fail_any)} planted_ok={planted_row.get('control_ok')} ok={payload['ok']}"
    )
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_RAW.read_text(encoding="utf-8"))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
