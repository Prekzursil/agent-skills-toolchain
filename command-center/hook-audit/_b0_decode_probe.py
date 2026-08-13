r"""B0 - decide the shape of the wire-check decode regression test by MEASUREMENT.

Three questions, each answered by running the thing rather than reasoning about it:

  Q1 does ripgrep pass RAW invalid-UTF-8 bytes through to its stdout, or does it
     substitute U+FFFD itself? (decides whether a universal, locale-independent
     trigger byte can even reach Python)
  Q2 does a valid-UTF-8 character whose bytes are UNDEFINED in cp1252 reproduce the
     silent-empty failure through the shipped `text=True` call shape?
  Q3 is a PATH shim named `rg.bat` resolvable by `subprocess.run(["rg", ...])` on
     Windows (CreateProcess appends .exe only)? (decides whether a fake-rg seam is
     available as a universal test transport)

Prints a terminal SUCCESS:/FAILED: marker. Writes B0-DECODE-PROBE.json.
"""

from __future__ import annotations

import json
import locale
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent
RES: dict[str, object] = {
    "preferred_encoding": locale.getpreferredencoding(False),
    "utf8_mode": sys.flags.utf8_mode,
    "python": sys.version.split()[0],
}


def _tmp() -> Path:
    p = Path(tempfile.gettempdir()) / f"b0-{uuid.uuid4().hex[:10]}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def q1_raw_invalid_utf8() -> None:
    """Write a lone 0x81 continuation byte (invalid UTF-8, undefined in cp1252)."""
    d = _tmp()
    (d / "f.py").write_bytes(b"x_target_q1 = 1  # \x81 tail\n")
    p = subprocess.run(
        ["rg", "-w", "-n", "--no-heading", "-S", "-g", "!.git", "x_target_q1", str(d)],
        capture_output=True,
        timeout=30,
    )
    raw = p.stdout
    RES["q1"] = {
        "rc": p.returncode,
        "raw_len": len(raw),
        "contains_raw_0x81": b"\x81" in raw,
        "contains_fffd": b"\xef\xbf\xbd" in raw,
        "raw_repr": repr(raw[:200]),
        "stderr": p.stderr.decode("utf-8", "replace")[:200],
    }


def q2_cp1252_undefined() -> None:
    """Cyrillic 'э' = D1 8D. 0x8D is UNDEFINED in cp1252 -> strict decode raises."""
    d = _tmp()
    (d / "f.py").write_text("x_target_q2 = 1  # э tail\n", encoding="utf-8")
    args = [
        "rg",
        "-w",
        "-n",
        "--no-heading",
        "-S",
        "-g",
        "!.git",
        "x_target_q2",
        str(d),
    ]

    # (a) EXACTLY the shipped call shape: text=True, no encoding=.
    shipped = {"raised": None, "rc": None, "stdout_len": None}
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=30)
        shipped.update(raised=False, rc=r.returncode, stdout_len=len(r.stdout or ""))
    except Exception as e:  # noqa: BLE001 - measuring, not handling
        shipped.update(raised=f"{type(e).__name__}", rc=None, stdout_len=None)

    # (b) the proposed fix.
    fixed = {"raised": None, "rc": None, "stdout_len": None}
    try:
        r2 = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        fixed.update(raised=False, rc=r2.returncode, stdout_len=len(r2.stdout or ""))
    except Exception as e:  # noqa: BLE001
        fixed.update(raised=f"{type(e).__name__}", rc=None, stdout_len=None)

    # (c) CONTROL: a pure-ASCII file must be non-empty under BOTH shapes, otherwise
    #     an empty result above proves nothing (it could just be a bad rg invocation).
    d2 = _tmp()
    (d2 / "f.py").write_bytes(b"x_target_q2 = 1  # ascii tail\n")
    ctl_args = list(args)
    ctl_args[-1] = str(d2)
    c1 = subprocess.run(ctl_args, capture_output=True, text=True, timeout=30)
    c2 = subprocess.run(
        ctl_args, capture_output=True, text=True, encoding="utf-8", timeout=30
    )
    RES["q2"] = {
        "shipped_text_true": shipped,
        "with_encoding_utf8": fixed,
        "ascii_control_shipped_len": len(c1.stdout or ""),
        "ascii_control_fixed_len": len(c2.stdout or ""),
        "silently_emptied": bool(
            shipped.get("raised") is False
            and shipped.get("rc") == 0
            and shipped.get("stdout_len") == 0
            and (fixed.get("stdout_len") or 0) > 0
        ),
    }


def q3_bat_shim() -> None:
    d = _tmp()
    if os.name == "nt":
        (d / "rg.bat").write_text("@echo shim-hit\r\n", encoding="ascii")
        (d / "rg.cmd").write_text("@echo shim-hit\r\n", encoding="ascii")
    else:
        sh = d / "rg"
        sh.write_text("#!/bin/sh\necho shim-hit\n", encoding="ascii")
        sh.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(d) + os.pathsep + env.get("PATH", "")
    out: dict[str, object] = {}
    try:
        r = subprocess.run(
            ["rg", "--nope"], capture_output=True, text=True, timeout=20, env=env
        )
        out = {"found": True, "rc": r.returncode, "stdout": (r.stdout or "")[:80]}
    except Exception as e:  # noqa: BLE001
        out = {"found": False, "error": type(e).__name__}
    # A real rg on PATH would answer with its own error text, so require the marker.
    out["shim_actually_ran"] = "shim-hit" in str(out.get("stdout", ""))
    RES["q3_bat_shim"] = out


def main() -> int:
    q1_raw_invalid_utf8()
    q2_cp1252_undefined()
    q3_bat_shim()
    (OUT / "B0-DECODE-PROBE.json").write_text(
        json.dumps(RES, indent=2), encoding="utf-8"
    )
    print(json.dumps(RES, indent=2))
    q2 = RES["q2"]
    assert isinstance(q2, dict)
    if not q2.get("ascii_control_shipped_len"):
        print("FAILED:b0-decode-probe ascii control empty - the rg invocation is wrong")
        return 1
    print("SUCCESS:b0-decode-probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
