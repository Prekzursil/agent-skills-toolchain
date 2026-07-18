#!/usr/bin/env python3
"""re-triage-preflight — hash-cached reverse-engineering triage preflight.

Folds several cheap static-triage signals into ONE structured ``TRIAGE:`` block
that an agent can read before touching a binary:

  * SHA-256 identity + a per-file result CACHE (re-runs are instant)
  * File-format detection via magic bytes (PE / ELF / Mach-O / DEX / ZIP / ...)
  * Shannon entropy analysis (whole-file + sliding window) -> a packer verdict
    that works with ZERO external tools (the Detect-It-Easy substitute)
  * Detect-It-Easy (``diec``) packer/compiler detection      [best-effort, optional]
  * FLOSS auto string-deobfuscation (static/stack/tight/decoded) [opt-in, optional]
  * capa capability rules                                     [best-effort, optional]
  * Triton dynamic-taint availability probe                   [opt-in / documented]

DESIGN CONTRACT
---------------
* **Never blocks, never crashes on a missing tool.** Every external tool is
  invoked as a *subprocess* (never imported), probed for availability first, run
  with a bounded timeout, and degraded to a status string on absence / timeout /
  error. The overall run still emits a ``TRIAGE:`` block and exits 0. Exit code 2
  is reserved for hard input errors (missing / unreadable file, bad args).
* **Advisory / shadow-first (COUNCIL C5).** Output is pure advice — this script
  cannot gate anything. ``--shadow`` additionally appends the summary to a
  bounded, auto-rotating log sink (a *separate* sink, never the main ledger) and
  stays quiet on stdout, for when it is later folded into a cheap lifecycle hook.
* **Stdlib only.** No third-party import at module scope, so the script is
  import-safe even when capa / FLOSS / Triton are absent.
* **Anti-overfit.** Rides the existing re-harness bus (same ``re-ensure`` idiom,
  ``SUCCESS:``/``FAILED:`` terminal markers). The ``revula`` mega-bundle is
  rejected; only cherry-picked, already-useful tools are wired.

USAGE
-----
    python triage.py <path> [--full] [--json] [--refresh] [--no-cache]
                            [--tools t1,t2,...] [--timeout SECS]
                            [--floss-full] [--minlen N] [--shadow] [--quiet]
    python triage.py --selftest        # internal unit checks (no external tools)
    python triage.py --probe-tools     # report which external tools are wired up

Default (fast) tool set: format + entropy + die (probe/run if present).
``--full`` additionally runs floss (all string types) + capa. Slow tools are
always bounded by ``--timeout`` (default 90s each) and degrade gracefully.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCHEMA_VERSION = 3  # bump invalidates cached results
WINDOW = 4096
# Entropy thresholds (bits/byte, max 8.0).
PACKED_WINDOW_THRESHOLD = 7.2
STRONG_WHOLE = 7.5
STRONG_FRACTION = 0.85
WEAK_WHOLE = 7.2
WEAK_FRACTION = 0.50
SECTION_PACKED_ENTROPY = 7.4
DEFAULT_TIMEOUT = 90
DEFAULT_MINLEN = 5
SHADOW_MAX_BYTES = 256 * 1024  # rotate the shadow sink at 256 KiB
STRING_SAMPLE = 8  # how many decoded strings to surface

# Section names that packers/protectors are known to create.
PACKER_SECTION_NAMES = {
    "upx0",
    "upx1",
    "upx2",
    "upx!",
    ".aspack",
    ".adata",
    ".nsp0",
    ".nsp1",
    ".nsp2",
    "nsp0",
    "nsp1",
    ".packed",
    ".themida",
    ".vmp0",
    ".vmp1",
    ".vmp2",
    ".enigma1",
    ".enigma2",
    ".pklstb",
    ".mpress1",
    ".mpress2",
    ".petite",
    ".pec2",
    ".rlpack",
    ".fsg",
    ".mew",
    ".yp",
    ".boom",
    ".ccg",
    "pebundle",
    ".winlice",
    ".seau",
    ".taz",
    ".svkp",
    ".gentee",
    ".ndata",
}

# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Entropy
# ---------------------------------------------------------------------------


def shannon_entropy(data: bytes) -> float:
    """Shannon entropy of ``data`` in bits/byte (0.0 .. 8.0)."""
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    ent = 0.0
    for c in counts:
        if c:
            p = c / n
            ent -= p * math.log2(p)
    return ent


def _entropy_from_hist(counts: list[int], n: int) -> float:
    if n <= 0:
        return 0.0
    ent = 0.0
    for c in counts:
        if c:
            p = c / n
            ent -= p * math.log2(p)
    return ent


def windowed_entropy(path: str, window: int = WINDOW) -> dict:
    """Stream the file: whole-file entropy + per-window stats (memory-safe)."""
    total = [0] * 256
    n_total = 0
    n_windows = 0
    packed_windows = 0
    max_window = 0.0
    sum_window = 0.0
    with open(path, "rb") as fh:
        while True:
            buf = fh.read(window)
            if not buf:
                break
            n_total += len(buf)
            counts = [0] * 256
            for b in buf:
                counts[b] += 1
            for i, c in enumerate(counts):
                total[i] += c
            # Only score full-size windows as "packed" (tail chunks are noisy).
            if len(buf) >= window:
                we = _entropy_from_hist(counts, len(buf))
                n_windows += 1
                sum_window += we
                if we > max_window:
                    max_window = we
                if we >= PACKED_WINDOW_THRESHOLD:
                    packed_windows += 1
            else:
                we = _entropy_from_hist(counts, len(buf))
                if we > max_window:
                    max_window = we
    whole = _entropy_from_hist(total, n_total)
    frac = (packed_windows / n_windows) if n_windows else 0.0
    mean = (sum_window / n_windows) if n_windows else whole
    return {
        "whole": round(whole, 4),
        "max_window": round(max_window, 4),
        "mean_window": round(mean, 4),
        "packed_fraction": round(frac, 4),
        "n_full_windows": n_windows,
        "size": n_total,
        "window": window,
    }


def packer_verdict(ent: dict, pe_sections: list[dict] | None) -> dict:
    """Combine entropy stats + PE section hints into a packer verdict."""
    reasons: list[str] = []
    verdict = "unlikely_packed"

    whole = ent.get("whole", 0.0)
    frac = ent.get("packed_fraction", 0.0)
    small = ent.get("n_full_windows", 0) < 2

    if pe_sections:
        named = [
            s
            for s in pe_sections
            if (s.get("name") or "").lower() in PACKER_SECTION_NAMES
        ]
        if named:
            reasons.append(
                "packer-style section name(s): "
                + ",".join(sorted({s["name"] for s in named}))
            )
            verdict = "likely_packed"
        big_hot = [
            s
            for s in pe_sections
            if s.get("entropy", 0) >= SECTION_PACKED_ENTROPY
            and s.get("raw_size", 0) > 0
        ]
        if big_hot:
            reasons.append(
                "high-entropy section(s): "
                + ",".join(f"{s['name']}={s['entropy']:.2f}" for s in big_hot[:4])
            )
            if verdict == "unlikely_packed":
                verdict = "possibly_packed"

    if whole >= STRONG_WHOLE and frac >= STRONG_FRACTION:
        reasons.append(
            f"whole entropy {whole:.2f} >= {STRONG_WHOLE} and "
            f"{frac * 100:.0f}% of windows >= {PACKED_WINDOW_THRESHOLD}"
        )
        verdict = "likely_packed"
    elif whole >= WEAK_WHOLE and frac >= WEAK_FRACTION:
        reasons.append(
            f"whole entropy {whole:.2f} >= {WEAK_WHOLE} and "
            f"{frac * 100:.0f}% of windows elevated"
        )
        if verdict == "unlikely_packed":
            verdict = "possibly_packed"

    if not reasons:
        reasons.append(
            f"whole entropy {whole:.2f} within normal range for native code/data"
        )
    if small:
        reasons.append("small file: verdict low-confidence")
    return {"verdict": verdict, "reasons": reasons}


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_PE_MACHINES = {
    0x014C: "x86",
    0x8664: "x86-64",
    0x01C0: "ARM",
    0xAA64: "ARM64",
    0x01C4: "ARMv7-Thumb",
    0x0200: "IA64",
    0x5032: "RISC-V32",
    0x5064: "RISC-V64",
    0x6232: "LoongArch32",
    0x6264: "LoongArch64",
}
_ELF_MACHINES = {
    0x03: "x86",
    0x3E: "x86-64",
    0x28: "ARM",
    0xB7: "ARM64",
    0x08: "MIPS",
    0x14: "PowerPC",
    0x15: "PPC64",
    0xF3: "RISC-V",
}
_MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce": "Mach-O 32 (BE)",
    b"\xce\xfa\xed\xfe": "Mach-O 32 (LE)",
    b"\xfe\xed\xfa\xcf": "Mach-O 64 (BE)",
    b"\xcf\xfa\xed\xfe": "Mach-O 64 (LE)",
}


def detect_format(path: str) -> dict:
    """Best-effort magic-byte format detection. Never raises."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
    except OSError as exc:  # pragma: no cover - guarded by caller
        return {"kind": "unreadable", "detail": str(exc)}

    if len(head) >= 2 and head[:2] == b"MZ":
        # DOS/PE. Find PE header via e_lfanew @ 0x3C.
        try:
            e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
            with open(path, "rb") as fh:
                fh.seek(e_lfanew)
                sig = fh.read(4)
            if sig == b"PE\x00\x00":
                with open(path, "rb") as fh:
                    fh.seek(e_lfanew + 4)
                    machine = struct.unpack("<H", fh.read(2))[0]
                arch = _PE_MACHINES.get(machine, f"machine=0x{machine:04x}")
                return {
                    "kind": "PE",
                    "detail": arch,
                    "arch": arch,
                    "pe_offset": e_lfanew,
                }
        except (struct.error, OSError):
            pass
        return {"kind": "MZ", "detail": "DOS/16-bit or malformed PE"}

    if head[:4] == b"\x7fELF":
        cls = {1: "32", 2: "64"}.get(head[4], "?") if len(head) > 4 else "?"
        endian = {1: "LE", 2: "BE"}.get(head[5], "?") if len(head) > 5 else "?"
        mach = ""
        try:
            off = 18  # e_machine offset
            emach = struct.unpack_from("<H" if endian != "BE" else ">H", head, off)[0]
            mach = _ELF_MACHINES.get(emach, f"machine=0x{emach:04x}")
        except struct.error:
            mach = "?"
        return {
            "kind": "ELF",
            "detail": f"ELF{cls} {endian} {mach}".strip(),
            "arch": mach,
        }

    if head[:4] in _MACHO_MAGIC:
        return {"kind": "Mach-O", "detail": _MACHO_MAGIC[head[:4]]}

    if head[:4] == b"\xca\xfe\xba\xbe":
        # Ambiguous: Java .class OR Mach-O universal (FAT) binary.
        try:
            second = struct.unpack_from(">I", head, 4)[0]
        except struct.error:
            second = 0
        if second and second < 0x20:
            return {"kind": "Mach-O", "detail": f"universal/FAT ({second} arch)"}
        return {
            "kind": "class-or-macho",
            "detail": "Java .class or Mach-O FAT (0xCAFEBABE)",
        }

    if head[:4] == b"dex\n":
        ver = head[4:7].decode("ascii", "replace")
        return {"kind": "DEX", "detail": f"Android DEX v{ver}"}

    if head[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        return {"kind": "ZIP", "detail": "ZIP/JAR/APK/OOXML container"}

    if head[:4] == b"%PDF":
        return {"kind": "PDF", "detail": "PDF document"}

    if head[:2] == b"#!":
        line = head.split(b"\n", 1)[0].decode("utf-8", "replace")
        return {"kind": "script", "detail": line.strip()}

    if head[:2] == b"\x1f\x8b":
        return {"kind": "gzip", "detail": "gzip stream"}

    return {"kind": "unknown", "detail": "no known magic"}


def parse_pe_sections(path: str, pe_offset: int) -> list[dict]:
    """Defensive PE section-header parse returning name + per-section entropy."""
    out: list[dict] = []
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        # COFF header @ pe_offset+4: Machine(2) NumSections(2) ...
        num_sections = struct.unpack_from("<H", data, pe_offset + 6)[0]
        opt_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
        sect_off = pe_offset + 24 + opt_size
        if num_sections > 96:  # PE spec cap; guard against garbage
            num_sections = 96
        for i in range(num_sections):
            base = sect_off + i * 40
            if base + 40 > len(data):
                break
            name = data[base : base + 8].split(b"\x00", 1)[0]
            name = name.decode("ascii", "replace")
            raw_size = struct.unpack_from("<I", data, base + 16)[0]
            raw_ptr = struct.unpack_from("<I", data, base + 20)[0]
            ent = 0.0
            if raw_size and raw_ptr and raw_ptr + raw_size <= len(data):
                ent = shannon_entropy(data[raw_ptr : raw_ptr + raw_size])
            out.append({"name": name, "raw_size": raw_size, "entropy": round(ent, 4)})
    except (struct.error, OSError, ValueError):
        return out
    return out


# ---------------------------------------------------------------------------
# External tools (subprocess, best-effort, never raise)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int) -> tuple[int, str, str]:
    """Run a subprocess; return (rc, stdout, stderr). rc=-9 timeout, -1 error."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return -9, "", f"timeout after {timeout}s"
    except (OSError, ValueError) as exc:
        return -1, "", str(exc)


def _find_die() -> str | None:
    env = os.environ.get("DIE_PATH")
    if env and (shutil.which(env) or Path(env).exists()):
        return env
    for name in ("diec", "die", "diec.exe", "die.exe", "diec-console"):
        p = shutil.which(name)
        if p:
            return p
    return None


def run_die(path: str, timeout: int) -> dict:
    exe = _find_die()
    if not exe:
        return {
            "status": "unavailable",
            "note": "Detect-It-Easy CLI not found (set DIE_PATH or install "
            "'diec'); entropy heuristic used instead",
        }
    rc, out, err = _run([exe, "-j", path], timeout)
    if rc == -9:
        return {"status": "timeout", "note": err}
    if rc == -1:
        return {"status": "error", "note": err}
    detects: list[str] = []
    try:
        j = json.loads(out)
        for d in j.get("detects", []):
            for v in d.get("values", []):
                label = f"{v.get('type', '?')}:{v.get('name', '?')}"
                ver = v.get("version")
                if ver:
                    label += f" {ver}"
                detects.append(label)
    except (json.JSONDecodeError, AttributeError):
        # Fall back to raw text run.
        rc2, out2, _ = _run([exe, path], timeout)
        text = (out2 or out).strip().splitlines()
        detects = [ln.strip() for ln in text if ln.strip()][:8]
    return {
        "status": "ok",
        "detects": detects[:12],
        "summary": "; ".join(detects[:6]) or "no detections",
    }


def _floss_cmd() -> list[str] | None:
    exe = shutil.which("floss") or shutil.which("floss.exe")
    if exe:
        return [exe]
    # Module invocation (FLOSS registers a runnable package in this env).
    rc, out, _ = _run([sys.executable, "-m", "floss", "--version"], 15)
    if rc == 0 or "floss" in out.lower():
        return [sys.executable, "-m", "floss"]
    return None


def run_floss(path: str, timeout: int, full: bool, minlen: int) -> dict:
    base = _floss_cmd()
    if base is None:
        return {"status": "unavailable", "note": "FLOSS not importable/installed"}
    cmd = base + ["-q", "-j", "-n", str(minlen)]
    if not full:
        cmd += ["--only", "static"]
    cmd += ["--", path]
    rc, out, err = _run(cmd, timeout)
    if rc == -9:
        return {
            "status": "timeout",
            "note": f"{err}; retry with a longer --timeout or drop --full",
        }
    if rc == -1:
        return {"status": "error", "note": err}
    try:
        j = json.loads(out)
    except json.JSONDecodeError:
        return {"status": "error", "note": (err or out or "no JSON").strip()[:200]}
    strings = j.get("strings", {}) if isinstance(j, dict) else {}

    def _count(key: str) -> int:
        v = strings.get(key)
        return len(v) if isinstance(v, list) else 0

    def _sample(key: str) -> list[str]:
        v = strings.get(key)
        out_s: list[str] = []
        if isinstance(v, list):
            for item in v[:STRING_SAMPLE]:
                if isinstance(item, dict):
                    s = item.get("string")
                    if s:
                        out_s.append(str(s)[:80])
        return out_s

    decoded = (
        _sample("decoded_strings") + _sample("stack_strings") + _sample("tight_strings")
    )
    res = {
        "status": "ok",
        "static": _count("static_strings"),
        "stack": _count("stack_strings"),
        "tight": _count("tight_strings"),
        "decoded": _count("decoded_strings"),
        "deobfuscated_sample": decoded[:STRING_SAMPLE],
        "mode": "full" if full else "static-only",
    }
    total_deobf = res["stack"] + res["tight"] + res["decoded"]
    res["summary"] = (
        f"static={res['static']} stack={res['stack']} "
        f"tight={res['tight']} decoded={res['decoded']}"
        + (" (run --full for deobfuscation)" if not full else "")
    )
    res["has_deobfuscated"] = total_deobf > 0
    return res


def run_capa(path: str, timeout: int) -> dict:
    exe = shutil.which("capa") or shutil.which("capa.exe")
    if not exe:
        return {
            "status": "unavailable",
            "note": "capa console CLI not on PATH (the lib may be present as "
            "a FLOSS dependency; install the capa entrypoint + rules "
            "to enable capability triage)",
        }
    rc, out, err = _run([exe, "-j", path], timeout)
    if rc == -9:
        return {"status": "timeout", "note": err}
    if rc == -1:
        return {"status": "error", "note": err}
    caps: list[str] = []
    attack: set[str] = set()
    try:
        j = json.loads(out)
        rules = j.get("rules", {})
        for name, meta in rules.items():
            caps.append(name)
            m = meta.get("meta", {}) if isinstance(meta, dict) else {}
            for a in m.get("attack", []) or []:
                if isinstance(a, dict):
                    tid = a.get("id") or a.get("technique")
                    if tid:
                        attack.add(str(tid))
    except (json.JSONDecodeError, AttributeError):
        return {"status": "error", "note": (err or "unparseable capa JSON")[:200]}
    return {
        "status": "ok",
        "n_capabilities": len(caps),
        "capabilities": caps[:12],
        "attack": sorted(attack)[:12],
        "summary": f"{len(caps)} capabilities; ATT&CK "
        f"{','.join(sorted(attack)[:6]) or 'n/a'}",
    }


def probe_triton() -> dict:
    rc, out, _ = _run(
        [
            sys.executable,
            "-c",
            "import triton,sys;sys.stdout.write(getattr(triton,'VERSION','?')"
            " if hasattr(triton,'VERSION') else 'ok')",
        ],
        15,
    )
    if rc == 0:
        return {
            "status": "available",
            "note": "dynamic taint is OPT-IN — build a taint harness per "
            "target; not auto-run in preflight (see SKILL.md)",
        }
    return {
        "status": "unavailable",
        "note": "Triton not importable; dynamic taint disabled",
    }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def cache_dir() -> Path:
    env = os.environ.get("RE_TRIAGE_CACHE")
    if env:
        return Path(env)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        return Path(base) / "re-triage" / "cache"
    return Path.home() / ".cache" / "re-triage"


def shadow_dir() -> Path:
    return cache_dir().parent / "shadow-log"


def load_cache(sha: str) -> dict | None:
    p = cache_dir() / f"{sha}.json"
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("schema") == SCHEMA_VERSION:
            return data
    except (OSError, json.JSONDecodeError):
        return None
    return None


def save_cache(sha: str, result: dict) -> Path:
    d = cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{sha}.json"
    tmp = d / f".{sha}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    os.replace(tmp, p)
    return p


def append_shadow(line: str) -> None:
    """Append one JSON line to a bounded, size-rotating shadow sink."""
    d = shadow_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        log = d / "triage-shadow.log"
        if log.exists() and log.stat().st_size > SHADOW_MAX_BYTES:
            bak = d / "triage-shadow.log.1"
            os.replace(log, bak)  # keep exactly one backup
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(line.rstrip("\n") + "\n")
    except OSError:
        pass  # shadow logging must never fail the run


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

DEFAULT_TOOLS = ["format", "entropy", "die"]
FULL_TOOLS = ["format", "entropy", "die", "floss", "capa", "triton"]


def build_triage(
    path: str, tools: list[str], timeout: int, floss_full: bool, minlen: int
) -> dict:
    t0 = time.time()
    fmt = detect_format(path)
    pe_sections = None
    if fmt.get("kind") == "PE" and "format" in tools:
        pe_sections = parse_pe_sections(path, fmt.get("pe_offset", 0))

    result: dict = {
        "schema": SCHEMA_VERSION,
        "path": os.path.abspath(path),
        "size": os.path.getsize(path),
        "format": fmt,
        "tools_requested": tools,
        "generated_at": int(time.time()),
    }
    if pe_sections is not None:
        result["pe_sections"] = pe_sections

    if "entropy" in tools:
        ent = windowed_entropy(path)
        result["entropy"] = ent
        result["packer"] = packer_verdict(ent, pe_sections)

    if "die" in tools:
        result["die"] = run_die(path, timeout)
    if "floss" in tools:
        result["floss"] = run_floss(path, timeout, floss_full, minlen)
    if "capa" in tools:
        result["capa"] = run_capa(path, timeout)
    if "triton" in tools:
        result["triton"] = probe_triton()

    result["elapsed_sec"] = round(time.time() - t0, 3)
    return result


def _ran_ok(result: dict) -> list[str]:
    ran = ["format", "entropy"] if "entropy" in result else ["format"]
    for tool in ("die", "floss", "capa", "triton"):
        st = (result.get(tool) or {}).get("status")
        if st in ("ok", "available"):
            ran.append(tool)
    return ran


def format_triage_block(result: dict, sha: str, cache_state: str) -> str:
    fmt = result["format"]
    lines: list[str] = []
    ent = result.get("entropy", {})
    packer = result.get("packer", {})
    whole = ent.get("whole", 0.0)
    verdict = packer.get("verdict", "n/a")
    header = (
        f"TRIAGE:{sha[:8]} {result['path']} "
        f"fmt={fmt.get('kind')} size={result['size']} "
        f"entropy={whole:.2f} packer={verdict} cache={cache_state}"
    )
    lines.append(header)
    lines.append(f"  format    : {fmt.get('kind')} — {fmt.get('detail')}")
    if ent:
        lines.append(
            f"  entropy   : whole={ent.get('whole')} "
            f"max_window={ent.get('max_window')} "
            f"packed_fraction={ent.get('packed_fraction')} "
            f"windows={ent.get('n_full_windows')}"
        )
        lines.append(
            f"  packer    : {verdict} ({'; '.join(packer.get('reasons', []))[:220]})"
        )
    if result.get("pe_sections"):
        hot = [
            s
            for s in result["pe_sections"]
            if s.get("entropy", 0) >= SECTION_PACKED_ENTROPY
        ]
        if hot:
            lines.append(
                "  sections  : hot="
                + ",".join(f"{s['name']}({s['entropy']:.2f})" for s in hot[:6])
            )
    for tool in ("die", "floss", "capa", "triton"):
        info = result.get(tool)
        if not info:
            continue
        st = info.get("status")
        if st in ("ok", "available"):
            msg = info.get("summary") or info.get("note") or st
            lines.append(f"  {tool:<9} : {st} — {msg}")
            if tool == "floss" and info.get("deobfuscated_sample"):
                for s in info["deobfuscated_sample"][:4]:
                    lines.append(f"              deobf> {s}")
        else:
            lines.append(f"  {tool:<9} : {st} ({info.get('note', '')})")
    ran = _ran_ok(result)
    lines.append(
        f"SUCCESS:re-triage {sha[:8]} tools={','.join(ran)} "
        f"elapsed={result.get('elapsed_sec')}s"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-test (keeps unit coverage within the single target file)
# ---------------------------------------------------------------------------


def selftest() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        if not cond:
            failures.append(name)

    # Entropy bounds.
    check("entropy-empty", shannon_entropy(b"") == 0.0)
    check("entropy-uniform-zero", shannon_entropy(b"\x00" * 1000) == 0.0)
    check("entropy-two-symbol", abs(shannon_entropy(b"\x00\xff" * 500) - 1.0) < 1e-9)
    full = shannon_entropy(bytes(range(256)) * 4)
    check("entropy-uniform-8bit", abs(full - 8.0) < 1e-9)

    # Format detection on synthetic magic bytes.
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)

        elf = tdp / "x.elf"
        elf.write_bytes(
            b"\x7fELF\x02\x01\x01"
            + b"\x00" * 11
            + struct.pack("<H", 0x3E)
            + b"\x00" * 4000
        )
        check("fmt-elf", detect_format(str(elf))["kind"] == "ELF")

        dex = tdp / "x.dex"
        dex.write_bytes(b"dex\n035\x00" + b"\x00" * 100)
        check("fmt-dex", detect_format(str(dex))["kind"] == "DEX")

        zf = tdp / "x.apk"
        zf.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        check("fmt-zip", detect_format(str(zf))["kind"] == "ZIP")

        unk = tdp / "x.bin"
        unk.write_bytes(b"\x01\x02\x03\x04random data here" * 10)
        check("fmt-unknown", detect_format(str(unk))["kind"] == "unknown")

        # Minimal but valid PE (MZ + e_lfanew -> PE\0\0 + machine).
        pe = tdp / "x.exe"
        buf = bytearray(512)
        buf[0:2] = b"MZ"
        pe_off = 0x80
        struct.pack_into("<I", buf, 0x3C, pe_off)
        buf[pe_off : pe_off + 4] = b"PE\x00\x00"
        struct.pack_into("<H", buf, pe_off + 4, 0x8664)  # machine x86-64
        pe.write_bytes(bytes(buf))
        fmt = detect_format(str(pe))
        check("fmt-pe", fmt["kind"] == "PE" and "x86-64" in fmt["detail"])

        # High-entropy synthetic -> packer heuristic should flag it.
        import random

        rnd = tdp / "packed.bin"
        random.seed(1)
        rnd.write_bytes(bytes(random.randrange(256) for _ in range(WINDOW * 6)))
        ent = windowed_entropy(str(rnd))
        pv = packer_verdict(ent, None)
        check("entropy-packed-high", ent["whole"] > 7.5)
        check(
            "packer-flags-random", pv["verdict"] in ("likely_packed", "possibly_packed")
        )

        # Low-entropy -> unlikely packed.
        low = tdp / "low.bin"
        low.write_bytes(b"AAAA BBBB CCCC the quick brown fox " * 400)
        entl = windowed_entropy(str(low))
        pvl = packer_verdict(entl, None)
        check("packer-unlikely-lowent", pvl["verdict"] == "unlikely_packed")

        # PE section packer-name detection.
        pv_sec = packer_verdict(
            {"whole": 4.0, "packed_fraction": 0.0, "n_full_windows": 5},
            [
                {"name": "UPX0", "entropy": 0.0, "raw_size": 0},
                {"name": "UPX1", "entropy": 7.9, "raw_size": 4096},
            ],
        )
        check("packer-section-name", pv_sec["verdict"] == "likely_packed")

        # Cache round-trip (isolated temp cache).
        os.environ["RE_TRIAGE_CACHE"] = str(tdp / "cache")
        sample = tdp / "sample.dat"
        sample.write_bytes(b"hello triage world" * 50)
        sha = sha256_file(str(sample))
        res = build_triage(str(sample), ["format", "entropy"], 5, False, 5)
        save_cache(sha, res)
        loaded = load_cache(sha)
        check(
            "cache-roundtrip", loaded is not None and loaded["schema"] == SCHEMA_VERSION
        )
        # Schema-bump invalidation.
        bad = dict(res)
        bad["schema"] = 999
        save_cache(sha + "b", bad)
        check("cache-schema-invalidation", load_cache(sha + "b") is None)

        # TRIAGE block renders + carries terminal markers.
        block = format_triage_block(res, sha, "miss")
        check("block-has-triage", block.startswith("TRIAGE:"))
        check("block-has-success", "SUCCESS:re-triage" in block)

        # Missing external tool -> graceful status, never raises.
        die = run_die(str(sample), 5)
        check(
            "die-graceful", die["status"] in ("unavailable", "ok", "timeout", "error")
        )

        # Shadow sink rotation.
        os.environ["RE_TRIAGE_CACHE"] = str(tdp / "cache2")
        for _ in range(50):
            append_shadow("x" * 8000)
        sd = shadow_dir()
        check("shadow-rotated", (sd / "triage-shadow.log.1").exists())
        del os.environ["RE_TRIAGE_CACHE"]

    if failures:
        print("FAILED:re-triage selftest failures=" + ",".join(failures))
        return 1
    print(
        "SUCCESS:re-triage selftest all-checks-passed "
        "(entropy,format,pe,packer,cache,block,tool-graceful,shadow)"
    )
    return 0


def probe_tools() -> int:
    print("re-triage tool availability:")
    print("  entropy   : built-in (stdlib) — always available")
    print("  format    : built-in (stdlib) — always available")
    die = _find_die()
    print(f"  die       : {'FOUND ' + die if die else 'not found (set DIE_PATH)'}")
    fl = _floss_cmd()
    print(f"  floss     : {'FOUND ' + ' '.join(fl) if fl else 'not found'}")
    capa = shutil.which("capa") or shutil.which("capa.exe")
    print(f"  capa      : {'FOUND ' + capa if capa else 'no console CLI'}")
    tri = probe_triton()
    print(f"  triton    : {tri['status']}")
    print(f"  cache dir : {cache_dir()}")
    print(f"  shadow dir: {shadow_dir()}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="triage.py",
        description="Hash-cached RE triage preflight (advisory / never blocks).",
    )
    ap.add_argument("target", nargs="?", help="path to the binary to triage")
    ap.add_argument(
        "--full", action="store_true", help="also run floss (all string types) + capa"
    )
    ap.add_argument(
        "--tools", help="explicit comma tool set (format,entropy,die,floss,capa,triton)"
    )
    ap.add_argument(
        "--floss-full",
        action="store_true",
        help="FLOSS: extract stack/tight/decoded (deobfuscation)",
    )
    ap.add_argument(
        "--minlen", type=int, default=DEFAULT_MINLEN, help="FLOSS minimum string length"
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="per-external-tool timeout seconds",
    )
    ap.add_argument(
        "--refresh", action="store_true", help="ignore any cached result and recompute"
    )
    ap.add_argument(
        "--no-cache", action="store_true", help="do not read or write the cache"
    )
    ap.add_argument("--json", action="store_true", help="emit the full result as JSON")
    ap.add_argument(
        "--shadow",
        action="store_true",
        help="append to the rotating shadow sink and stay quiet",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="suppress the human TRIAGE block (JSON/shadow only)",
    )
    ap.add_argument(
        "--selftest", action="store_true", help="run internal unit checks and exit"
    )
    ap.add_argument(
        "--probe-tools",
        action="store_true",
        help="report external-tool availability and exit",
    )
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.probe_tools:
        return probe_tools()

    if not args.target:
        ap.print_usage()
        print(
            "FAILED:re-triage no-target (pass a file path, --selftest, or "
            "--probe-tools)"
        )
        return 2
    path = args.target
    if not os.path.isfile(path):
        print(f"FAILED:re-triage not-a-file path={path}")
        return 2
    try:
        os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.read(1)
    except OSError as exc:
        print(f"FAILED:re-triage unreadable path={path} err={exc}")
        return 2

    if args.tools:
        tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    elif args.full:
        tools = list(FULL_TOOLS)
    else:
        tools = list(DEFAULT_TOOLS)
    floss_full = args.floss_full or args.full

    sha = sha256_file(path)
    cache_state = "off" if args.no_cache else "miss"
    result: dict | None = None
    if not args.no_cache and not args.refresh:
        cached = load_cache(sha)
        if cached is not None:
            # Only reuse the cache if it covers every requested tool.
            covered = all(
                (t in ("format", "entropy") and t in cached)
                or cached.get(t, {}).get("status") in ("ok", "unavailable", "available")
                for t in tools
            )
            if covered:
                result = cached
                cache_state = "hit"

    if result is None:
        result = build_triage(path, tools, args.timeout, floss_full, args.minlen)
        if not args.no_cache:
            try:
                saved = save_cache(sha, result)
                result["_cache_file"] = str(saved)
            except OSError:
                pass

    block = format_triage_block(result, sha, cache_state)

    if args.shadow:
        append_shadow(
            json.dumps(
                {
                    "sha": sha,
                    "path": result["path"],
                    "verdict": result.get("packer", {}).get("verdict"),
                    "fmt": result["format"].get("kind"),
                    "at": int(time.time()),
                }
            )
        )
        if not args.json and not args.quiet:
            # Shadow mode stays quiet on stdout by contract.
            return 0

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif not args.quiet:
        print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
