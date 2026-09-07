#!/usr/bin/env python3
"""AUD-0027 Probe 2: clean-env install on a non-Windows target.

Catalog evidence_requirement verbatim:
  Probe 2: an actual install attempt into a clean environment on at least one
  non-Windows target, because a published wheel tag is not proof the install
  resolves under the pinned Python.

tests_required:
  control: attempt an install of a package known to be source-only and confirm
  the probe reports a compiler requirement rather than a clean pass

Implementation note: this host lacks python3-venv/ensurepip, so the clean
environment is a fresh empty --target directory per attempt (no site-packages
reuse), which still proves wheel resolution under the pinned CPython.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe2-clean-install.json"
OUT_RAW = PROBE / "probe2-clean-install.raw.txt"
P1_JSON = PROBE / "probe1-wheel-tag-matrix.json"

CATALOG_VERBATIM = (
    "Probe 2: an actual install attempt into a clean environment on at least one "
    "non-Windows target, because a published wheel tag is not proof the install "
    "resolves under the pinned Python."
)

PLANTED = ("crcmod", "1.7")


def run(cmd: list[str], *, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def pip_target_install(target: Path, *args: str, timeout: int = 300) -> tuple[int, str]:
    target.mkdir(parents=True, exist_ok=True)
    return run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            "--target",
            str(target),
            *args,
        ],
        timeout=timeout,
    )


def classify_install_output(rc: int, out: str, *, only_binary: bool) -> dict:
    low = out.lower()
    built = (
        "building wheel" in low
        or "running setup.py" in low
        or "preparing metadata (pyproject.toml)" in low
        or "building wheel for" in low
    )
    if only_binary and rc != 0:
        return {
            "result": "compiler_requirement",
            "reason": (
                "only-binary install failed (no matching wheel; sdist would need "
                "a compiler/build)"
            ),
            "exit_code": rc,
            "built_from_sdist": False,
            "compiler_or_binary_block_signaled": True,
        }
    if rc == 0 and not built:
        return {
            "result": "clean_wheel_pass",
            "reason": "install exited 0 without an sdist build step",
            "exit_code": rc,
            "built_from_sdist": False,
            "compiler_or_binary_block_signaled": False,
        }
    if rc == 0 and built:
        return {
            "result": "built_from_sdist",
            "reason": "install exited 0 after building from sdist (compiler present)",
            "exit_code": rc,
            "built_from_sdist": True,
            "compiler_or_binary_block_signaled": True,
        }
    return {
        "result": "compiler_requirement" if rc != 0 else "failed_other",
        "reason": "install failed or unexpected state",
        "exit_code": rc,
        "built_from_sdist": built,
        "compiler_or_binary_block_signaled": rc != 0,
    }


def main() -> int:
    if not P1_JSON.is_file():
        print(f"MISSING {P1_JSON}; run probe1 first", file=sys.stderr)
        return 2
    p1 = json.loads(P1_JSON.read_text(encoding="utf-8"))

    host = {
        "os": os.name,
        "sys_platform": sys.platform,
        "python": sys.version.split()[0],
        "non_windows_target": os.name != "nt" and not sys.platform.startswith("win"),
        "clean_env_method": "pip-install --target into fresh empty directory (no python3-venv/ensurepip on host)",
    }
    lines = [
        f"unit=AUD-0027 probe=2",
        f"catalog_verbatim={CATALOG_VERBATIM}",
        f"host={json.dumps(host)}",
    ]
    if not host["non_windows_target"]:
        lines.append("FATAL: probe requires a non-Windows target")
        OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload = {"ok": False, "unit": "AUD-0027", "probe": 2, "host": host, "attempts": []}
        OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return 1

    candidates = []
    for name in p1.get("native_or_platform_names") or []:
        if name.lower() == PLANTED[0].lower():
            continue
        row = next((r for r in p1.get("packages", []) if r.get("name") == name), None)
        if not row or row.get("status") != "ok":
            continue
        ver = row.get("version")
        if not ver:
            continue
        candidates.append((name, ver, row.get("classification")))
    prefer = ["pydantic-core", "rpds-py", "cryptography", "numpy", "tiktoken", "regex"]
    ordered = []
    seen: set[str] = set()
    for pref in prefer:
        for c in candidates:
            if c[0].lower() == pref.lower() and c[0].lower() not in seen:
                ordered.append(c)
                seen.add(c[0].lower())
    for c in candidates:
        if c[0].lower() not in seen:
            ordered.append(c)
            seen.add(c[0].lower())
    sample = ordered[:8]

    scratch = Path(tempfile.mkdtemp(prefix="aud0027-target-"))
    attempts = []
    planted_ok = False
    try:
        # --- planted source-only control ---
        ctrl_spec = f"{PLANTED[0]}=={PLANTED[1]}"
        t_ob = scratch / "planted-only-binary"
        rc_ob, out_ob = pip_target_install(t_ob, "--only-binary=:all:", ctrl_spec, timeout=120)
        cls_ob = classify_install_output(rc_ob, out_ob, only_binary=True)
        planted_ok = cls_ob["result"] == "compiler_requirement" and rc_ob != 0
        attempts.append(
            {
                "name": PLANTED[0],
                "spec": ctrl_spec,
                "mode": "only-binary-all",
                "planted_source_only_control": True,
                "target": str(t_ob),
                "exit_code": rc_ob,
                "classification": cls_ob,
                "output_tail": out_ob[-2500:],
            }
        )
        lines.append(
            f"CONTROL only-binary {ctrl_spec} rc={rc_ob} result={cls_ob['result']} "
            f"planted_ok={planted_ok}"
        )
        lines.append(out_ob[-1200:])

        t_src = scratch / "planted-allow-sdist"
        rc_src, out_src = pip_target_install(t_src, ctrl_spec, timeout=180)
        cls_src = classify_install_output(rc_src, out_src, only_binary=False)
        attempts.append(
            {
                "name": PLANTED[0],
                "spec": ctrl_spec,
                "mode": "allow-sdist",
                "planted_source_only_control": True,
                "target": str(t_src),
                "exit_code": rc_src,
                "classification": cls_src,
                "output_tail": out_src[-2500:],
            }
        )
        lines.append(
            f"CONTROL allow-sdist {ctrl_spec} rc={rc_src} result={cls_src['result']}"
        )
        lines.append(out_src[-800:])

        # --- live native/platform sample ---
        for name, ver, classification in sample:
            spec = f"{name}=={ver}"
            tdir = scratch / f"live-{name}"
            rc, out = pip_target_install(tdir, "--only-binary=:all:", spec, timeout=300)
            cls = classify_install_output(rc, out, only_binary=True)
            attempts.append(
                {
                    "name": name,
                    "spec": spec,
                    "mode": "only-binary-all",
                    "probe1_classification": classification,
                    "planted_source_only_control": False,
                    "target": str(tdir),
                    "exit_code": rc,
                    "classification": cls,
                    "output_tail": out[-2000:],
                }
            )
            lines.append(
                f"INSTALL {spec} class={classification} rc={rc} result={cls['result']}"
            )
            if rc != 0:
                lines.append(out[-900:])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    live_attempts = [a for a in attempts if not a.get("planted_source_only_control")]
    clean_passes = sum(
        1 for a in live_attempts if a["classification"]["result"] == "clean_wheel_pass"
    )
    binary_fail = sum(
        1
        for a in live_attempts
        if a["classification"]["result"] == "compiler_requirement"
    )

    payload = {
        "ok": planted_ok and host["non_windows_target"],
        "unit": "AUD-0027",
        "probe": 2,
        "catalog_verbatim": CATALOG_VERBATIM,
        "host": host,
        "planted_control": {
            "package": PLANTED[0],
            "version": PLANTED[1],
            "only_binary_result": next(
                a["classification"]["result"]
                for a in attempts
                if a.get("planted_source_only_control") and a["mode"] == "only-binary-all"
            ),
            "reports_compiler_requirement": planted_ok,
            "not_clean_pass": planted_ok,
            "ok": planted_ok,
        },
        "sample_size": len(sample),
        "sample_names": [c[0] for c in sample],
        "live_clean_wheel_pass_count": clean_passes,
        "live_only_binary_fail_count": binary_fail,
        "attempts": attempts,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines.append(
        f"SUMMARY planted_ok={planted_ok} live_clean_pass={clean_passes} "
        f"live_binary_fail={binary_fail} sample={len(sample)} ok={payload['ok']}"
    )
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_RAW.read_text(encoding="utf-8"))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
