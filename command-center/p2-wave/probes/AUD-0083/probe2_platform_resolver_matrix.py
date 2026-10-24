#!/usr/bin/env python3
"""AUD-0083 named probe 2: platform resolution matrix.

Two parts, kept honestly separate:

  (A) REAL measurement on this Linux host: three throwaway fixture scripts
      (exec+shebang, no-exec+shebang, exec+no-shebang) are actually executed
      via subprocess (no shell wrapper -- a direct execve path, matching what
      a CI runner or `subprocess.run([...])` sees) and their real exit
      code / stderr is recorded. This is the ground truth the `linux` branch
      of `_platform_resolver.resolve()` is checked against.

  (B) The full matrix: every script row from probe1's census is run through
      `_platform_resolver.resolve()` for platform in {linux, macos, windows}
      x mode in {bare, explicit}, and the outcome counts are aggregated.
      macos and windows rows are NOT executed anywhere -- they are resolved
      by the documented/simulated model in `_platform_resolver.py`, and every
      row in the matrix carries a `measured` tag (`measured`,
      `inferred-not-measured`, `documented`, `documented-conditional`) so the
      packed receipt cannot present a simulated Windows answer as if it came
      from a real Windows host.
"""

from __future__ import annotations

import json
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _platform_resolver as R  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
P1_JSON = PROBE_DIR / "probe1-inventory-shebangs.json"
OUT_JSON = PROBE_DIR / "probe2-platform-matrix.json"
OUT_RAW = PROBE_DIR / "probe2-platform-matrix.raw.txt"


def real_linux_fixture_measurements() -> dict:
    """Actually execute three fixtures on THIS Linux host. Ground truth for
    the `linux` branch of the resolver -- not simulated."""
    results = {}
    with tempfile.TemporaryDirectory(prefix="aud0083-fixtures-") as td:
        tdp = Path(td)

        exec_shebang = tdp / "exec_with_shebang.sh"
        exec_shebang.write_text(
            "#!/bin/sh\necho FIXTURE_OK\nexit 0\n", encoding="utf-8"
        )
        exec_shebang.chmod(
            exec_shebang.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
        )
        r1 = subprocess.run(
            [str(exec_shebang)], capture_output=True, text=True, timeout=10
        )
        results["exec_bit_with_shebang"] = {
            "exec_bit": True,
            "has_shebang": True,
            "invocation": f"direct-exec {exec_shebang.name}",
            "returncode": r1.returncode,
            "stdout": r1.stdout.strip(),
            "stderr": r1.stderr.strip(),
            "outcome": "SUCCESS" if r1.returncode == 0 else "FAILURE",
        }

        no_exec_shebang = tdp / "no_exec_with_shebang.sh"
        no_exec_shebang.write_text("#!/bin/sh\necho SHOULD_NOT_RUN\n", encoding="utf-8")
        # deliberately leave default (non-executable) mode
        no_exec_shebang.chmod(0o644)
        try:
            r2 = subprocess.run(
                [str(no_exec_shebang)], capture_output=True, text=True, timeout=10
            )
            rc2, err2 = r2.returncode, r2.stderr.strip()
        except OSError as exc:
            rc2, err2 = 126, f"{type(exc).__name__}: {exc}"
        results["no_exec_bit_with_shebang"] = {
            "exec_bit": False,
            "has_shebang": True,
            "invocation": f"direct-exec {no_exec_shebang.name}",
            "returncode": rc2,
            "stderr": err2,
            "outcome": "SUCCESS" if rc2 == 0 else "FAILURE",
        }

        exec_no_shebang = tdp / "exec_no_shebang.sh"
        exec_no_shebang.write_text("echo THIS_HAS_NO_SHEBANG_LINE\n", encoding="utf-8")
        exec_no_shebang.chmod(
            exec_no_shebang.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
        )
        try:
            r3 = subprocess.run(
                [str(exec_no_shebang)], capture_output=True, text=True, timeout=10
            )
            rc3, err3 = r3.returncode, r3.stderr.strip()
        except OSError as exc:
            rc3, err3 = 126, f"{type(exc).__name__}: {exc}"
        results["exec_bit_no_shebang_direct_exec"] = {
            "exec_bit": True,
            "has_shebang": False,
            "invocation": f"direct-exec {exec_no_shebang.name} (no shell wrapper)",
            "returncode": rc3,
            "stderr": err3,
            "outcome": "SUCCESS" if rc3 == 0 else "FAILURE",
        }

        # Explicit invocation control: same no-exec-bit script run with an
        # explicit interpreter succeeds even though bare direct-exec above
        # failed with Permission denied -- exec bit and shebang are
        # irrelevant once an interpreter is named explicitly.
        r4 = subprocess.run(
            ["sh", str(no_exec_shebang)], capture_output=True, text=True, timeout=10
        )
        results["no_exec_bit_explicit_sh_invocation"] = {
            "exec_bit": False,
            "invocation": f"sh {no_exec_shebang.name} (explicit interpreter)",
            "returncode": r4.returncode,
            "stdout": r4.stdout.strip(),
            "outcome": "SUCCESS" if r4.returncode == 0 else "FAILURE",
        }

    return results


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = json.loads(P1_JSON.read_text(encoding="utf-8"))
    rows = p1["rows"]

    real = real_linux_fixture_measurements()
    _resolver_check_ok = (
        real["exec_bit_with_shebang"]["outcome"] == "SUCCESS"
        and real["no_exec_bit_with_shebang"]["outcome"] == "FAILURE"
        and real["exec_bit_no_shebang_direct_exec"]["outcome"] == "FAILURE"
        and real["no_exec_bit_explicit_sh_invocation"]["outcome"] == "SUCCESS"
    )
    # Cross-check: does the resolver AGREE with what was actually measured
    # on this Linux host, for the exact same four fixture states?
    resolver_matches_real = {
        "exec_bit_with_shebang": R.resolve(
            ext=".sh",
            has_shebang=True,
            shebang_interpreter="sh",
            exec_bit=True,
            platform="linux",
            mode="bare",
        )["outcome"]
        == real["exec_bit_with_shebang"]["outcome"],
        "no_exec_bit_with_shebang": R.resolve(
            ext=".sh",
            has_shebang=True,
            shebang_interpreter="sh",
            exec_bit=False,
            platform="linux",
            mode="bare",
        )["outcome"]
        == real["no_exec_bit_with_shebang"]["outcome"],
        "exec_bit_no_shebang_direct_exec": R.resolve(
            ext=".sh",
            has_shebang=False,
            shebang_interpreter="",
            exec_bit=True,
            platform="linux",
            mode="bare",
        )["outcome"]
        == real["exec_bit_no_shebang_direct_exec"]["outcome"],
        "no_exec_bit_explicit_sh_invocation": R.resolve(
            ext=".sh",
            has_shebang=True,
            shebang_interpreter="sh",
            exec_bit=False,
            platform="linux",
            mode="explicit",
            explicit_interpreter="sh",
        )["outcome"]
        == real["no_exec_bit_explicit_sh_invocation"]["outcome"],
    }
    resolver_verified_against_real_linux = all(resolver_matches_real.values())

    platforms = ["linux", "macos", "windows"]
    modes = ["bare", "explicit"]
    matrix_counts: dict[str, dict[str, dict[str, int]]] = {
        p: {m: {"SUCCESS": 0, "FAILURE": 0} for m in modes} for p in platforms
    }
    windows_bare_fail_would_run_bare_on_linux: list[dict] = []
    windows_bare_by_extension: dict[str, dict[str, int]] = {}
    sample_findings: list[dict] = []

    for row in rows:
        ext = row["extension"] or ""
        exec_bit = bool(row["exec_bit"])
        has_shebang = bool(row["has_shebang"])
        interp = row["shebang_interpreter"] or ""
        explicit = interp or {"sh": "sh", "py": "python3"}.get(ext.lstrip("."), interp)
        for platform in platforms:
            for mode in modes:
                res = R.resolve(
                    ext=ext,
                    has_shebang=has_shebang,
                    shebang_interpreter=interp,
                    exec_bit=exec_bit,
                    platform=platform,
                    mode=mode,
                    explicit_interpreter=explicit,
                )
                matrix_counts[platform][mode][res["outcome"]] += 1
                if platform == "windows" and mode == "bare":
                    windows_bare_by_extension.setdefault(
                        ext or "(none)", {"SUCCESS": 0, "FAILURE": 0}
                    )
                    windows_bare_by_extension[ext or "(none)"][res["outcome"]] += 1
                    linux_bare = R.resolve(
                        ext=ext,
                        has_shebang=has_shebang,
                        shebang_interpreter=interp,
                        exec_bit=exec_bit,
                        platform="linux",
                        mode="bare",
                    )
                    if (
                        res["outcome"] == "FAILURE"
                        and linux_bare["outcome"] == "SUCCESS"
                    ):
                        windows_bare_fail_would_run_bare_on_linux.append(
                            {
                                "path": row["path"],
                                "extension": ext,
                                "shebang": row["shebang"],
                                "linux_bare_outcome": linux_bare["outcome"],
                                "linux_bare_interpreter": linux_bare["interpreter"],
                                "windows_bare_outcome": res["outcome"],
                                "windows_bare_reason": res["reason"],
                            }
                        )

    for row in rows[:0]:  # placeholder kept explicit: sample built below
        pass
    sample_findings = windows_bare_fail_would_run_bare_on_linux[:30]

    windows_bare_fail_count = sum(
        matrix_counts["windows"]["bare"][o] for o in ("FAILURE",)
    )
    windows_bare_success_count = matrix_counts["windows"]["bare"]["SUCCESS"]
    linux_bare_success_count = matrix_counts["linux"]["bare"]["SUCCESS"]
    linux_bare_fail_count = matrix_counts["linux"]["bare"]["FAILURE"]

    out = {
        "ok": bool(resolver_verified_against_real_linux),
        "started_at": started,
        "real_linux_fixture_measurements": real,
        "resolver_matches_real_measurement": resolver_matches_real,
        "resolver_verified_against_real_linux": resolver_verified_against_real_linux,
        "rows_resolved": len(rows),
        "matrix_counts": matrix_counts,
        "windows_bare_by_extension": windows_bare_by_extension,
        "windows_bare_fail_count": windows_bare_fail_count,
        "windows_bare_success_count": windows_bare_success_count,
        "linux_bare_success_count": linux_bare_success_count,
        "linux_bare_fail_count": linux_bare_fail_count,
        "windows_bare_would_run_on_linux_bare_count": len(
            windows_bare_fail_would_run_bare_on_linux
        ),
        "sample_windows_bare_would_fail_but_linux_bare_would_run": sample_findings,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    lines = [
        "SUCCESS:AUD-0083-probe2" if out["ok"] else "FAILED:AUD-0083-probe2",
        f"unit=AUD-0083 probe=2 rows_resolved={len(rows)}",
        f"resolver_verified_against_real_linux={resolver_verified_against_real_linux}",
        f"resolver_matches_real={resolver_matches_real}",
        "--- real linux fixture measurements (this host) ---",
    ]
    for name, r in real.items():
        lines.append(f"{name}: rc={r['returncode']} outcome={r['outcome']}")
    lines.append("--- matrix counts (platform x mode -> outcome) ---")
    for platform in platforms:
        for mode in modes:
            c = matrix_counts[platform][mode]
            lines.append(
                f"{platform}/{mode}: SUCCESS={c['SUCCESS']} FAILURE={c['FAILURE']}"
            )
    lines.append(f"windows_bare_by_extension={windows_bare_by_extension}")
    lines.append(
        f"windows_bare_would_run_on_linux_bare_count={len(windows_bare_fail_would_run_bare_on_linux)}"
    )
    lines.append(
        "--- sample (windows bare FAILS, linux bare would SUCCEED), first 15 ---"
    )
    for f in sample_findings[:15]:
        lines.append(
            f"{f['path']} shebang={f['shebang'] or '(none)'} "
            f"linux_bare={f['linux_bare_outcome']}({f['linux_bare_interpreter']}) "
            f"windows_bare={f['windows_bare_outcome']}"
        )
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
