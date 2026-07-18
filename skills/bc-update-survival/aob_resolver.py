#!/usr/bin/env python3
"""aob_resolver.py -- AOB (array-of-bytes) wildcard-signature resolver for BC.

Retires hardcoded RVAs. A signature is a byte pattern with wildcards for the
bytes that move on relink (rel32 call/jump displacements, RIP-relative disp32,
reloc'd immediates). Because the *opcodes* of a function are stable across a
Battle Cats update even when its address shifts, resolving a function by its
signature survives the update where a pinned RVA does not.

Resolution backends
  offline  -- scan a `.so` file on disk  -> RVA          (fully deterministic)
  live     -- Frida `Memory.scan` over the loaded module -> runtime addr -> RVA

Signature authoring
  author-diff  -- byte-diff two known versions of the same function; wildcard
                  ONLY the bytes that differ. Robust, needs no disassembler.
                  This is the preferred, bullet-proof cross-version method.
  author       -- single-version heuristic (capstone if importable, else a
                  conservative rel32 / RIP-disp32 byte heuristic). Best-effort.

Ground truth for BC EN 15.4.1: `lib/x86_64/libnative-lib.so` has imagebase 0x0,
so **RVA == file offset** (see battlecats-event-unlock). `--imagebase 0` (the
default) is therefore correct for BC; pass `--elf-sections` for a general ELF
whose sections are not identity-mapped.

Shadow drift gate (council C5): `verify` compares AOB-resolved RVAs against a
pinned offset table and LOGS drift to a bounded, auto-rotating sink. It NEVER
blocks, nags, or exits non-zero on drift -- observe-and-log only.

No hard third-party deps. `pyelftools` (optional) sharpens `--elf-sections`;
`capstone` (optional) sharpens single-version authoring; `frida` (optional) is
needed only for the live backend. CLI: `python aob_resolver.py --help`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

# --------------------------------------------------------------------------- #
# Signature engine
# --------------------------------------------------------------------------- #

_HEX2 = re.compile(r"^[0-9A-Fa-f]{2}$")


@dataclass
class Signature:
    """An AOB pattern: fixed bytes + wildcard positions.

    tokens[i] is an int 0..255 for a fixed byte, or None for a wildcard.
    """

    tokens: list[Optional[int]]
    name: str = ""

    # -- construction -------------------------------------------------------- #
    @classmethod
    def parse(cls, text: str, name: str = "") -> "Signature":
        """Parse an IDA-style pattern: '48 8D 05 ?? ?? ?? ?? C3'.

        Accepts '??' or '?' as a wildcard; whitespace separates tokens; a bare
        contiguous hex run ('488D05') is also split into byte pairs.
        """
        toks: list[Optional[int]] = []
        for raw in text.replace(",", " ").split():
            # a contiguous even-length hex run with no wildcards -> split
            if (
                len(raw) > 2
                and _HEX2.match(raw[:2])
                and len(raw) % 2 == 0
                and "?" not in raw
            ):
                for j in range(0, len(raw), 2):
                    toks.append(int(raw[j : j + 2], 16))
                continue
            if raw in ("??", "?", "*", "x", "X"):
                toks.append(None)
            elif _HEX2.match(raw):
                toks.append(int(raw, 16))
            else:
                raise ValueError(f"bad signature token: {raw!r}")
        if not toks:
            raise ValueError("empty signature")
        return cls(toks, name)

    @classmethod
    def from_bytes_mask(
        cls, data: bytes, mask: Iterable[bool], name: str = ""
    ) -> "Signature":
        """Build from raw bytes + a keep-mask (True = fixed byte, False = wildcard)."""
        toks: list[Optional[int]] = [
            (b if keep else None) for b, keep in zip(data, mask)
        ]
        return cls(toks, name)

    # -- properties ---------------------------------------------------------- #
    def __len__(self) -> int:
        return len(self.tokens)

    @property
    def fixed_count(self) -> int:
        return sum(1 for t in self.tokens if t is not None)

    def is_specific(self, min_fixed: int = 6) -> bool:
        """A usable signature needs enough anchored bytes to be unlikely-random."""
        return self.fixed_count >= min_fixed

    # -- rendering ----------------------------------------------------------- #
    def to_ida(self) -> str:
        return " ".join("??" if t is None else f"{t:02X}" for t in self.tokens)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.to_ida()

    # -- matching ------------------------------------------------------------ #
    def _regex(self) -> re.Pattern[bytes]:
        parts = [b"." if t is None else re.escape(bytes((t,))) for t in self.tokens]
        return re.compile(b"".join(parts), re.DOTALL)

    def find_all(self, data: bytes, limit: Optional[int] = None) -> list[int]:
        """Return every file offset in `data` where this signature matches.

        Uses an overlapping scan (finditer skips overlaps, so we step manually)
        so adjacent matches are never lost.
        """
        rx = self._regex()
        out: list[int] = []
        pos = 0
        n = len(data)
        while pos <= n - len(self.tokens):
            m = rx.match(data, pos)
            if m:
                out.append(pos)
                if limit is not None and len(out) >= limit:
                    break
            pos += 1
        return out


# --------------------------------------------------------------------------- #
# ELF offset <-> virtual-address mapping
# --------------------------------------------------------------------------- #


@dataclass
class Section:
    name: str
    addr: int
    offset: int
    size: int


class ElfMap:
    """Minimal ELF64 file-offset <-> virtual-address mapping.

    Uses pyelftools when importable; otherwise a self-contained ELF64 section
    parser (no third-party dep). For BC's imagebase-0 `.so`, RVA == file
    offset, so this is only needed for general ELFs (`--elf-sections`).
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.sections: list[Section] = []
        self._parse()

    def _parse(self) -> None:
        try:
            from elftools.elf.elffile import ELFFile  # type: ignore

            with open(self.path, "rb") as fh:
                elf = ELFFile(fh)
                for sec in elf.iter_sections():
                    self.sections.append(
                        Section(
                            sec.name,
                            sec["sh_addr"],
                            sec["sh_offset"],
                            sec["sh_size"],
                        )
                    )
            return
        except ImportError:
            pass
        self._parse_manual()

    def _parse_manual(self) -> None:
        import struct

        with open(self.path, "rb") as fh:
            data = fh.read()
        if data[:4] != b"\x7fELF" or data[4] != 2:
            raise ValueError("not an ELF64 file")
        (e_shoff,) = struct.unpack_from("<Q", data, 0x28)
        (e_shentsize,) = struct.unpack_from("<H", data, 0x3A)
        (e_shnum,) = struct.unpack_from("<H", data, 0x3C)
        (e_shstrndx,) = struct.unpack_from("<H", data, 0x3E)
        headers = []
        for i in range(e_shnum):
            base = e_shoff + i * e_shentsize
            sh_name, sh_type = struct.unpack_from("<II", data, base)
            sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from(
                "<QQQQ", data, base + 8
            )
            headers.append((sh_name, sh_addr, sh_offset, sh_size))
        # section-header string table
        strtab_off = headers[e_shstrndx][2]

        def _name(nm_off: int) -> str:
            end = data.index(b"\x00", strtab_off + nm_off)
            return data[strtab_off + nm_off : end].decode("utf-8", "replace")

        for sh_name, sh_addr, sh_offset, sh_size in headers:
            self.sections.append(Section(_name(sh_name), sh_addr, sh_offset, sh_size))

    def off_to_va(self, off: int) -> int:
        for s in self.sections:
            if s.addr and s.offset <= off < s.offset + s.size:
                return s.addr + (off - s.offset)
        return off  # not in a mapped section -> identity

    def va_to_off(self, va: int) -> int:
        for s in self.sections:
            if s.addr and s.addr <= va < s.addr + s.size:
                return s.offset + (va - s.addr)
        return va

    def text_range(self) -> Optional[tuple[int, int]]:
        for s in self.sections:
            if s.name == ".text":
                return (s.offset, s.size)
        return None


def _off_to_rva(off: int, imagebase: int, elf: Optional[ElfMap]) -> int:
    if elf is not None:
        return elf.off_to_va(off)
    return off + imagebase


def _rva_to_off(rva: int, imagebase: int, elf: Optional[ElfMap]) -> int:
    if elf is not None:
        return elf.va_to_off(rva)
    return rva - imagebase


# --------------------------------------------------------------------------- #
# Offline scan / resolve
# --------------------------------------------------------------------------- #


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_file(
    path: str, sig: Signature, imagebase: int = 0, elf: Optional[ElfMap] = None
) -> list[dict]:
    """Return [{file_off, rva}] for every match of `sig` in the file."""
    with open(path, "rb") as fh:
        data = fh.read()
    return [
        {"file_off": off, "rva": _off_to_rva(off, imagebase, elf)}
        for off in sig.find_all(data)
    ]


def resolve_offline(
    path: str,
    sig: Signature,
    imagebase: int = 0,
    elf: Optional[ElfMap] = None,
) -> dict:
    """Resolve a single signature. status: ok | missing | ambiguous."""
    hits = scan_file(path, sig, imagebase, elf)
    if not hits:
        return {"name": sig.name, "status": "missing", "count": 0, "rva": None}
    if len(hits) > 1:
        return {
            "name": sig.name,
            "status": "ambiguous",
            "count": len(hits),
            "rva": hits[0]["rva"],
            "all_rva": [h["rva"] for h in hits],
        }
    return {
        "name": sig.name,
        "status": "ok",
        "count": 1,
        "rva": hits[0]["rva"],
        "file_off": hits[0]["file_off"],
    }


# --------------------------------------------------------------------------- #
# Signature authoring
# --------------------------------------------------------------------------- #

# x86-64 instruction lead-ins whose trailing disp32/rel32 is reloc-sensitive.
_MODRM_RIP = {0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D}  # mod=00, rm=101


def _heuristic_mask(code: bytes) -> list[bool]:
    """Best-effort keep-mask: wildcard rel32 / RIP-relative disp32 bytes.

    Conservative linear scan. NOT a full disassembler -- prefer author_diff or
    capstone. Only the clearest, standard encodings are wildcarded; everything
    else is kept fixed (under-wildcarding at worst reduces cross-version
    robustness, which the caller compensates for by lengthening the signature).
    """
    keep = [True] * len(code)
    i = 0
    n = len(code)
    while i < n:
        b = code[i]
        # call rel32 / jmp rel32
        if b in (0xE8, 0xE9) and i + 4 < n:
            for k in range(i + 1, i + 5):
                keep[k] = False
            i += 5
            continue
        # jcc rel32: 0F 80..8F
        if b == 0x0F and i + 5 < n and 0x80 <= code[i + 1] <= 0x8F:
            for k in range(i + 2, i + 6):
                keep[k] = False
            i += 6
            continue
        # REX.W-prefixed lea/mov with RIP-relative operand
        if 0x40 <= b <= 0x4F and i + 2 < n and code[i + 1] in (0x8D, 0x8B, 0x89, 0x63):
            if code[i + 2] in _MODRM_RIP and i + 6 < n:
                for k in range(i + 3, i + 7):
                    keep[k] = False
                i += 7
                continue
        i += 1
    return keep


def _capstone_mask(code: bytes) -> Optional[list[bool]]:
    """Precise keep-mask via capstone (wildcard rel/disp/imm operand bytes)."""
    try:
        import capstone  # type: ignore
    except ImportError:
        return None
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    keep = [True] * len(code)
    for insn in md.disasm(code, 0):
        # RIP-relative memory operand -> wildcard its disp bytes
        for op in insn.operands:
            if (
                op.type == capstone.x86.X86_OP_MEM
                and op.mem.base == capstone.x86.X86_REG_RIP
            ):
                # disp is the last 4 bytes of the instruction encoding
                for k in range(insn.size - 4, insn.size):
                    if 0 <= insn.address + k < len(keep):
                        keep[insn.address + k] = False
        # relative branch immediate (call/jmp/jcc) -> wildcard rel32
        grp = set(insn.groups)
        if (
            capstone.CS_GRP_JUMP in grp or capstone.CS_GRP_CALL in grp
        ) and insn.size >= 5:
            for k in range(insn.address + insn.size - 4, insn.address + insn.size):
                if 0 <= k < len(keep):
                    keep[k] = False
    return keep


def author_signature(
    path: str,
    rva: int,
    length: int = 32,
    min_fixed: int = 8,
    imagebase: int = 0,
    elf: Optional[ElfMap] = None,
    name: str = "",
) -> dict:
    """Author a single-version signature at `rva`, extended until unique.

    Returns {name, rva, sig, fixed, unique, length, method}. `unique` is True
    when the emitted signature matches exactly once in the whole file.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    off = _rva_to_off(rva, imagebase, elf)
    if off < 0 or off >= len(data):
        raise ValueError(f"rva {rva:#x} -> offset {off:#x} out of range")

    method = "capstone"
    grab = data[off : off + max(length, 64)]
    mask = _capstone_mask(grab)
    if mask is None:
        method = "heuristic"
        mask = _heuristic_mask(grab)

    # Extend the window until the signature is unique (or we run out of tail).
    cur = length
    while cur <= len(grab):
        chunk = grab[:cur]
        m = mask[:cur]
        sig = Signature.from_bytes_mask(chunk, m, name)
        count = len(sig.find_all(data, limit=2))
        if count == 1 and sig.fixed_count >= min_fixed:
            return {
                "name": name,
                "rva": rva,
                "sig": sig.to_ida(),
                "fixed": sig.fixed_count,
                "unique": True,
                "length": cur,
                "method": method,
            }
        cur += 8
    # Best effort: return the longest window even if not unique.
    sig = Signature.from_bytes_mask(grab, mask, name)
    count = len(sig.find_all(data, limit=5))
    return {
        "name": name,
        "rva": rva,
        "sig": sig.to_ida(),
        "fixed": sig.fixed_count,
        "unique": count == 1,
        "length": len(grab),
        "method": method,
        "match_count": count,
    }


def author_diff(
    old_path: str,
    new_path: str,
    old_rva: int,
    new_rva: int,
    length: int = 48,
    imagebase: int = 0,
    old_elf: Optional[ElfMap] = None,
    new_elf: Optional[ElfMap] = None,
    name: str = "",
) -> dict:
    """Author a cross-version signature by byte-diffing the SAME function in two
    versions. Wildcard exactly the bytes that differ; keep the rest.

    This is the robust, disassembler-free authoring path: the resulting
    signature matches both versions by construction, so it survives the update.
    Requires the function's address in both versions (from a ghidriff match or
    manual RE).
    """
    with open(old_path, "rb") as fh:
        old = fh.read()
    with open(new_path, "rb") as fh:
        new = fh.read()
    o_off = _rva_to_off(old_rva, imagebase, old_elf)
    n_off = _rva_to_off(new_rva, imagebase, new_elf)
    o_code = old[o_off : o_off + length]
    n_code = new[n_off : n_off + length]
    span = min(len(o_code), len(n_code))
    mask = [o_code[i] == n_code[i] for i in range(span)]
    sig = Signature.from_bytes_mask(o_code[:span], mask, name)
    # verify uniqueness in both files
    o_hits = len(sig.find_all(old, limit=3))
    n_hits = len(sig.find_all(new, limit=3))
    return {
        "name": name,
        "sig": sig.to_ida(),
        "fixed": sig.fixed_count,
        "length": span,
        "old_rva": old_rva,
        "new_rva": new_rva,
        "unique_old": o_hits == 1,
        "unique_new": n_hits == 1,
        "matches_both": o_hits >= 1 and n_hits >= 1,
        "method": "byte-diff",
    }


# --------------------------------------------------------------------------- #
# Frida live backend
# --------------------------------------------------------------------------- #


def gen_frida_agent(module_name: str, sigs: dict[str, str]) -> str:
    """Emit a Frida JS agent that Memory.scan's `module_name` for each signature
    and posts back name -> [ {rva} ]. Deterministic (testable) text.
    """
    entries = ",\n".join(
        f"    {json.dumps(name)}: {json.dumps(pat)}" for name, pat in sigs.items()
    )
    return (
        "// auto-generated by aob_resolver.gen_frida_agent\n"
        "'use strict';\n"
        "const SIGS = {\n" + entries + "\n};\n"
        f"const MODNAME = {json.dumps(module_name)};\n"
        "function main() {\n"
        "  const mod = Process.findModuleByName(MODNAME);\n"
        "  if (!mod) { send({error: 'module not found: ' + MODNAME}); return; }\n"
        "  const out = {};\n"
        "  for (const name in SIGS) {\n"
        "    const hits = Memory.scanSync(mod.base, mod.size, SIGS[name]);\n"
        "    out[name] = hits.map(h => ({\n"
        "      address: h.address.toString(),\n"
        "      rva: '0x' + h.address.sub(mod.base).toString(16)\n"
        "    }));\n"
        "  }\n"
        "  send({module: MODNAME, base: mod.base.toString(), results: out});\n"
        "}\n"
        "main();\n"
    )


def resolve_live(
    target: str,
    module_name: str,
    sigs: dict[str, str],
    frida_pattern_style: bool = True,
    timeout: float = 15.0,
) -> dict:
    """Attach to a running process and resolve `sigs` via Frida Memory.scan.

    `target` is a pid (int-like) or process name. Requires the `frida` package
    and a reachable frida-server on the device. Raises RuntimeError with a clear
    message if Frida is unavailable. (Not exercised in offline selftest.)
    """
    try:
        import frida  # type: ignore
    except ImportError as exc:  # pragma: no cover - env dependent
        raise RuntimeError(
            "frida not installed; live backend unavailable (offline scan still works)"
        ) from exc

    # Frida wants patterns as space-separated hex with '??' wildcards -- our
    # to_ida() form already matches, so pass signatures through unchanged.
    agent = gen_frida_agent(module_name, sigs)
    result: dict = {}
    errbox: dict = {}

    def _on_message(msg, _data):  # pragma: no cover - device dependent
        if msg.get("type") == "send":
            result.update(msg.get("payload", {}))
        elif msg.get("type") == "error":
            errbox["error"] = msg.get("description")

    device = (
        frida.get_usb_device(timeout=timeout) if False else frida.get_local_device()
    )
    try:
        pid = int(target)
        session = device.attach(pid)
    except (ValueError, TypeError):
        session = device.attach(target)
    script = session.create_script(agent)
    script.on("message", _on_message)
    script.load()
    session.detach()
    if errbox:
        raise RuntimeError(errbox["error"])
    return result


# --------------------------------------------------------------------------- #
# Offset-table helpers + SHADOW drift gate
# --------------------------------------------------------------------------- #


def load_table(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _rotating_log(sink: str, line: str, cap_bytes: int = 256 * 1024) -> None:
    """Append `line` to a size-capped, single-rotation sink. Fail-open."""
    try:
        os.makedirs(os.path.dirname(sink) or ".", exist_ok=True)
        if os.path.exists(sink) and os.path.getsize(sink) > cap_bytes:
            rotated = sink + ".1"
            try:
                if os.path.exists(rotated):
                    os.remove(rotated)
                os.replace(sink, rotated)
            except OSError:
                pass
        with open(sink, "a", encoding="utf-8") as fh:
            fh.write(line.rstrip("\n") + "\n")
    except Exception:  # noqa: BLE001 - shadow gate must never raise
        pass


def default_sink() -> str:
    root = os.environ.get("BC_DRIFT_SINK")
    if root:
        return root
    home = os.path.expanduser("~")
    return os.path.join(home, ".claude", "logs", "bc-update-survival-drift.log")


def verify_drift(
    table: dict,
    so_path: str,
    imagebase: int = 0,
    elf: Optional[ElfMap] = None,
    sink: Optional[str] = None,
    _now: Optional[Callable[[], str]] = None,
) -> dict:
    """SHADOW gate: re-resolve each pinned signature in `so_path` and compare to
    the pinned RVA. Drift is LOGGED to a bounded rotating sink and returned in
    the report. NEVER raises for drift, NEVER blocks, NEVER exits non-zero.

    A pinned table entry needs {"rva": "0x..", "sig": "AOB.."} to be checkable;
    entries without a `sig` are reported as "unchecked".
    """
    import datetime

    sink = sink or default_sink()
    now = _now() if _now else datetime.datetime.now().isoformat(timespec="seconds")
    live_sha = None
    try:
        live_sha = sha256_file(so_path)
    except OSError:
        pass
    pinned_sha = table.get("sha256")
    report = {
        "so": so_path,
        "pinned_sha256": pinned_sha,
        "live_sha256": live_sha,
        "so_changed": bool(pinned_sha and live_sha and pinned_sha != live_sha),
        "checked": 0,
        "drifted": [],
        "moved": [],
        "missing": [],
        "ambiguous": [],
        "unchecked": [],
        "ok": [],
        "shadow": True,
    }
    for name, entry in table.get("offsets", {}).items():
        sig_text = entry.get("sig")
        pinned_rva = entry.get("rva")
        if isinstance(pinned_rva, str):
            pinned_rva = int(pinned_rva, 16)
        if not sig_text:
            report["unchecked"].append(name)
            continue
        report["checked"] += 1
        res = resolve_offline(so_path, Signature.parse(sig_text, name), imagebase, elf)
        if res["status"] == "missing":
            report["missing"].append(name)
        elif res["status"] == "ambiguous":
            report["ambiguous"].append({"name": name, "count": res["count"]})
        elif res["rva"] == pinned_rva:
            report["ok"].append(name)
        else:
            report["moved"].append(
                {"name": name, "pinned": pinned_rva, "resolved": res["rva"]}
            )
    report["drifted"] = report["moved"] + report["missing"] + report["ambiguous"]
    drift = bool(report["drifted"] or report["so_changed"])
    # observe-and-log only
    _rotating_log(
        sink,
        json.dumps(
            {
                "ts": now,
                "event": "bc-drift-check",
                "so_changed": report["so_changed"],
                "moved": len(report["moved"]),
                "missing": len(report["missing"]),
                "ambiguous": len(report["ambiguous"]),
                "checked": report["checked"],
            }
        ),
    )
    report["drift_detected"] = drift
    report["advice"] = (
        "SHADOW: offsets appear stale -- re-port before trusting RVAs "
        "(python ghidriff_port.py port-aob ...)"
        if drift
        else "SHADOW: offsets consistent with pinned table"
    )
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _elf_for(path: str, use_sections: bool) -> Optional[ElfMap]:
    return ElfMap(path) if use_sections else None


def _cli(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="AOB wildcard-signature resolver (BC)")
    p.add_argument(
        "--imagebase", default="0x0", help="module imagebase (default 0x0 = BC)"
    )
    p.add_argument(
        "--elf-sections", action="store_true", help="use ELF section mapping"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="list every match of a signature in a .so")
    s.add_argument("so")
    s.add_argument("sig")

    r = sub.add_parser("resolve", help="resolve one/many signatures to RVAs")
    r.add_argument("so")
    r.add_argument("sig", nargs="?", help="single AOB pattern")
    r.add_argument("--table", help="offset table json (resolve all sigs in it)")

    a = sub.add_parser("author", help="author a single-version signature at an RVA")
    a.add_argument("so")
    a.add_argument("rva")
    a.add_argument("--length", type=int, default=32)
    a.add_argument("--name", default="")

    ad = sub.add_parser(
        "author-diff", help="author a cross-version signature by byte-diff"
    )
    ad.add_argument("old_so")
    ad.add_argument("new_so")
    ad.add_argument("old_rva")
    ad.add_argument("new_rva")
    ad.add_argument("--length", type=int, default=48)
    ad.add_argument("--name", default="")

    g = sub.add_parser("gen-agent", help="emit a Frida agent for a table's signatures")
    g.add_argument("table")
    g.add_argument("--module", default="libnative-lib.so")

    lv = sub.add_parser("live", help="resolve via Frida against a running process")
    lv.add_argument("target", help="pid or process name")
    lv.add_argument("table")
    lv.add_argument("--module", default="libnative-lib.so")

    v = sub.add_parser(
        "verify", help="SHADOW drift gate vs a pinned table (never blocks)"
    )
    v.add_argument("table")
    v.add_argument("so")
    v.add_argument("--sink", default=None)

    sub.add_parser("selftest", help="run the built-in offline self-test")

    args = p.parse_args(argv)
    imagebase = (
        int(str(args.imagebase), 16)
        if str(args.imagebase).lower().startswith("0x")
        else int(args.imagebase)
    )

    if args.cmd == "selftest":
        return 0 if selftest() else 1

    if args.cmd == "scan":
        elf = _elf_for(args.so, args.elf_sections)
        hits = scan_file(args.so, Signature.parse(args.sig), imagebase, elf)
        print(
            json.dumps(
                {"count": len(hits), "hits": [f"0x{h['rva']:x}" for h in hits]},
                indent=2,
            )
        )
        return 0

    if args.cmd == "resolve":
        elf = _elf_for(args.so, args.elf_sections)
        if args.table:
            table = load_table(args.table)
            out = {}
            for name, entry in table.get("offsets", {}).items():
                if entry.get("sig"):
                    res = resolve_offline(
                        args.so, Signature.parse(entry["sig"], name), imagebase, elf
                    )
                    out[name] = {
                        **res,
                        "rva": (
                            f"0x{res['rva']:x}" if res["rva"] is not None else None
                        ),
                    }
            print(json.dumps(out, indent=2))
        else:
            res = resolve_offline(args.so, Signature.parse(args.sig), imagebase, elf)
            if res["rva"] is not None:
                res["rva"] = f"0x{res['rva']:x}"
            print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "author":
        elf = _elf_for(args.so, args.elf_sections)
        rva = int(args.rva, 16) if args.rva.lower().startswith("0x") else int(args.rva)
        print(
            json.dumps(
                author_signature(
                    args.so,
                    rva,
                    args.length,
                    imagebase=imagebase,
                    elf=elf,
                    name=args.name,
                ),
                indent=2,
            )
        )
        return 0

    if args.cmd == "author-diff":
        oe = _elf_for(args.old_so, args.elf_sections)
        ne = _elf_for(args.new_so, args.elf_sections)
        orva = (
            int(args.old_rva, 16)
            if args.old_rva.lower().startswith("0x")
            else int(args.old_rva)
        )
        nrva = (
            int(args.new_rva, 16)
            if args.new_rva.lower().startswith("0x")
            else int(args.new_rva)
        )
        print(
            json.dumps(
                author_diff(
                    args.old_so,
                    args.new_so,
                    orva,
                    nrva,
                    args.length,
                    imagebase,
                    oe,
                    ne,
                    args.name,
                ),
                indent=2,
            )
        )
        return 0

    if args.cmd == "gen-agent":
        table = load_table(args.table)
        sigs = {
            n: e["sig"] for n, e in table.get("offsets", {}).items() if e.get("sig")
        }
        print(gen_frida_agent(args.module, sigs))
        return 0

    if args.cmd == "live":
        table = load_table(args.table)
        sigs = {
            n: e["sig"] for n, e in table.get("offsets", {}).items() if e.get("sig")
        }
        print(json.dumps(resolve_live(args.target, args.module, sigs), indent=2))
        return 0

    if args.cmd == "verify":
        elf = _elf_for(args.so, args.elf_sections)
        table = load_table(args.table)
        rep = verify_drift(table, args.so, imagebase, elf, sink=args.sink)
        print(json.dumps(rep, indent=2))
        return 0  # SHADOW: always success exit, even on drift

    return 2


# --------------------------------------------------------------------------- #
# Built-in offline self-test (proves the load-bearing paths without a device)
# --------------------------------------------------------------------------- #


def selftest() -> bool:  # noqa: C901 - a linear proof, kept in one place
    import tempfile

    ok = True

    def check(name: str, cond: bool) -> None:
        nonlocal ok
        status = "PASS" if cond else "FAIL"
        print(f"[{status}] {name}")
        ok = ok and cond

    # 1) signature parse + match against the REAL BC getGlobal fingerprint.
    #    battlecats-event-unlock: getGlobal = 48 8D 05 ?? ?? ?? ?? C3 (lea/ret).
    sig = Signature.parse("48 8D 05 ?? ?? ?? ?? C3")
    check("parse getGlobal sig len==8", len(sig) == 8)
    check("getGlobal fixed_count==4", sig.fixed_count == 4)
    # concrete lea rax,[rip+0x5bfe99]; ret  (disp differs -> must still match)
    code = bytes.fromhex("488d0599fe5b00c3")
    check("matches concrete lea/ret", sig.find_all(code) == [0])
    # a different disp still matches (this is the whole point)
    code2 = bytes.fromhex("488d05DEADBEEFc3".replace("DEADBEEF", "efbeadde"))
    check("matches relinked disp", sig.find_all(code2) == [0])
    # round-trip render
    check("to_ida round-trips", Signature.parse(sig.to_ida()).tokens == sig.tokens)

    # 2) contiguous-hex parse
    check(
        "contiguous hex parse", Signature.parse("488D05").tokens == [0x48, 0x8D, 0x05]
    )

    # 3) Build two synthetic ".so" blobs (imagebase 0 -> file offset == RVA).
    #    A "function" = prologue + a rel32 call (disp changes across versions) +
    #    a stable tail. In v2 the whole function is shifted by inserting padding.
    def make_func(call_disp: bytes) -> bytes:
        return (
            b"\x55\x48\x89\xe5"  # push rbp; mov rbp,rsp
            + b"\xe8"
            + call_disp  # call rel32 (disp is reloc-sensitive)
            + b"\x48\x83\xc4\x20\x5d\xc3"  # add rsp,0x20; pop rbp; ret
        )

    junk = b"\x90" * 64
    v1_func = make_func(b"\x11\x22\x33\x44")
    v2_func = make_func(b"\xaa\xbb\xcc\xdd")  # same opcodes, different call target
    v1 = junk + v1_func + junk  # func at offset 64
    v2 = (b"\xcc" * 96) + v2_func + junk  # func shifted to offset 96 (relink)

    with tempfile.TemporaryDirectory() as td:
        v1p = os.path.join(td, "v1.so")
        v2p = os.path.join(td, "v2.so")
        with open(v1p, "wb") as fh:
            fh.write(v1)
        with open(v2p, "wb") as fh:
            fh.write(v2)

        # 3a) author-diff builds a signature that wildcards ONLY the call disp
        ad = author_diff(v1p, v2p, 64, 96, length=len(v1_func), name="myfunc")
        check("author-diff matches_both", ad["matches_both"])
        check("author-diff unique in old", ad["unique_old"])
        check("author-diff unique in new", ad["unique_new"])
        # the 4 differing disp bytes must be wildcards, opcodes must be fixed
        diff_sig = Signature.parse(ad["sig"])
        check(
            "author-diff wildcarded 4 disp bytes",
            diff_sig.fixed_count == len(v1_func) - 4,
        )

        # 3b) THE KEY PROOF: a signature authored on v1 re-locates the function
        #     at its NEW address in the relinked v2 (survives the update).
        res_v1 = resolve_offline(v1p, diff_sig)
        res_v2 = resolve_offline(v2p, diff_sig)
        check("resolve v1 -> 0x40", res_v1["status"] == "ok" and res_v1["rva"] == 64)
        check(
            "resolve v2 -> 0x60 (relink survived)",
            res_v2["status"] == "ok" and res_v2["rva"] == 96,
        )

        # 3c) single-version heuristic authoring also wildcards the rel32
        auth = author_signature(
            v1p, 64, length=len(v1_func), min_fixed=6, name="myfunc"
        )
        heur_sig = Signature.parse(auth["sig"])
        check("heuristic sig unique in v1", auth["unique"])
        check(
            "heuristic sig wildcards call disp",
            heur_sig.tokens[5:9] == [None, None, None, None],
        )
        check(
            "heuristic sig survives relink", resolve_offline(v2p, heur_sig)["rva"] == 96
        )

        # 3d) missing / ambiguous statuses
        missing = resolve_offline(v1p, Signature.parse("DE AD BE EF CA FE BA BE"))
        check("missing status", missing["status"] == "missing")
        amb = resolve_offline(v1p, Signature.parse("90 90 90 90 90 90"))
        check("ambiguous status", amb["status"] == "ambiguous")

        # 4) SHADOW drift gate: pinned rva is stale in v2 -> reports 'moved',
        #    logs to a sink, and NEVER raises / never fails the process.
        table = {
            "so": "test.so",
            "version": "v1",
            "sha256": sha256_file(v1p),
            "offsets": {
                "myfunc": {"rva": "0x40", "sig": diff_sig.to_ida(), "note": "test"},
                "nosig": {"rva": "0x10", "note": "unchecked entry"},
            },
        }
        sink = os.path.join(td, "drift.log")
        rep_same = verify_drift(table, v1p, sink=sink, _now=lambda: "T0")
        check(
            "drift: v1 consistent (ok)",
            rep_same["moved"] == [] and not rep_same["drift_detected"],
        )
        check("drift: unchecked entry reported", rep_same["unchecked"] == ["nosig"])
        rep_moved = verify_drift(table, v2p, sink=sink, _now=lambda: "T1")
        check("drift: v2 moved detected", len(rep_moved["moved"]) == 1)
        check("drift: so_changed flagged", rep_moved["so_changed"])
        check(
            "drift: shadow report never blocks (returns dict)",
            isinstance(rep_moved, dict),
        )
        check("drift: sink written", os.path.exists(sink) and os.path.getsize(sink) > 0)

        # 5) Frida agent generation is deterministic and references the module
        agent = gen_frida_agent(
            "libnative-lib.so", {"getGlobal": "48 8D 05 ?? ?? ?? ?? C3"}
        )
        check("agent has Memory.scanSync", "Memory.scanSync" in agent)
        check("agent embeds signature", "48 8D 05 ?? ?? ?? ?? C3" in agent)
        check("agent embeds module name", "libnative-lib.so" in agent)

        # 6) ElfMap round-trip if pyelftools is present (skipped otherwise)
        try:
            import elftools  # type: ignore  # noqa: F401

            elf_ok = _selftest_elfmap(td)
            check("ElfMap off<->va round-trip", elf_ok)
        except ImportError:
            print("[SKIP] ElfMap round-trip (pyelftools not importable)")

    print("SELFTEST:", "PASS" if ok else "FAIL")
    return ok


def _build_min_elf64() -> bytes:
    """Assemble a minimal valid ELF64 .so with a `.text` section mapped at a
    non-zero vaddr (0x1000) from file offset 0x200 -- used only by the selftest
    to exercise ElfMap's section mapping.
    """
    import struct

    text_off, text_addr, text_size = 0x200, 0x1000, 16
    text_data = b"\x90" * text_size
    shstr = b"\x00.text\x00.shstrtab\x00"
    name_text, name_shstr = 1, 7
    shstr_off = 0x300
    shoff = 0x400

    buf = bytearray(shoff + 3 * 64)
    # ELF header
    buf[0:16] = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
    struct.pack_into("<H", buf, 0x10, 3)  # e_type = ET_DYN
    struct.pack_into("<H", buf, 0x12, 0x3E)  # e_machine = x86-64
    struct.pack_into("<I", buf, 0x14, 1)  # e_version
    struct.pack_into("<Q", buf, 0x28, shoff)  # e_shoff
    struct.pack_into("<H", buf, 0x34, 64)  # e_ehsize
    struct.pack_into("<H", buf, 0x3A, 64)  # e_shentsize
    struct.pack_into("<H", buf, 0x3C, 3)  # e_shnum
    struct.pack_into("<H", buf, 0x3E, 2)  # e_shstrndx

    buf[text_off : text_off + text_size] = text_data
    buf[shstr_off : shstr_off + len(shstr)] = shstr

    def sh(idx, name, stype, flags, addr, off, size):
        base = shoff + idx * 64
        struct.pack_into("<II", buf, base, name, stype)
        struct.pack_into("<QQQQ", buf, base + 8, flags, addr, off, size)

    sh(0, 0, 0, 0, 0, 0, 0)  # SHT_NULL
    sh(1, name_text, 1, 0x6, text_addr, text_off, text_size)  # .text (PROGBITS)
    sh(2, name_shstr, 3, 0, 0, shstr_off, len(shstr))  # .shstrtab (STRTAB)
    return bytes(buf)


def _selftest_elfmap(td: str) -> bool:
    """Round-trip file-offset <-> virtual-address through ElfMap."""
    path = os.path.join(td, "min.so")
    with open(path, "wb") as fh:
        fh.write(_build_min_elf64())
    em = ElfMap(path)
    tr = em.text_range()
    # .text is at file 0x200 mapped to vaddr 0x1000
    va = em.off_to_va(0x208)
    off = em.va_to_off(0x1008)
    return tr == (0x200, 16) and va == 0x1008 and off == 0x208


if __name__ == "__main__":
    sys.exit(_cli())
