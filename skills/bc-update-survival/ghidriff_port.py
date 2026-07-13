#!/usr/bin/env python3
"""ghidriff_port.py -- one-command cross-version `.so` diff + auto-port the BC
offset table across a Battle Cats update.

The problem: BC ships an update, `lib/x86_64/libnative-lib.so` is recompiled and
relinked, and every pinned RVA in your offset table is now wrong. Acting on a
stale RVA is the worst failure mode (crash / HGT-trap). This tool re-derives the
new table automatically.

Two porting strategies (use both; they cross-check each other):

  port-aob   PRIMARY, disassembler-free, base-independent. Re-scans the NEW
             `.so` for each entry's AOB signature (via aob_resolver) and writes
             the new RVA. Needs no Ghidra. This is the robust path and the one
             that "survives updates".

  port-ghidriff  Bulk function-matching via ghidriff (Ghidra BinDiff-style).
             Consumes a ghidriff JSON result and ports every entry whose
             function ghidriff matched old->new. Needs a Ghidra install to
             PRODUCE the JSON, but the porting logic is pure and testable.

`triage` ties it together for a version bump: sha256-compare the two binaries
(pulling the `.so` out of an `.apk` if given one), and -- when the native code
changed -- port the table via AOB and, when Ghidra is available, cross-check
with ghidriff. Resource/DAT diffing is documented in SKILL.md (apktool); the
`.so` is the load-bearing part for offsets and is handled here.

Ground truth for BC EN 15.4.1: imagebase 0x0 -> RVA == file offset, so the AOB
path is exact with `--imagebase 0` (default).

CLI: `python ghidriff_port.py --help`. Long ghidriff runs should be wrapped with
`longrun` (>60s). No hard third-party deps for the AOB path; `ghidriff` +
`GHIDRA_INSTALL_DIR` are needed only for `port-ghidriff` / `diff`.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import zipfile
from typing import Optional

# Import the sibling AOB resolver regardless of CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import aob_resolver as aob  # noqa: E402


# --------------------------------------------------------------------------- #
# Table IO
# --------------------------------------------------------------------------- #

def load_table(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_table(table: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(table, fh, indent=2)
        fh.write("\n")


def _as_int(v) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s, 16) if s.lower().startswith("0x") else int(s)


def _hx(v: Optional[int]) -> Optional[str]:
    return None if v is None else f"0x{v:x}"


# --------------------------------------------------------------------------- #
# Strategy 1: AOB re-scan (primary, no Ghidra)
# --------------------------------------------------------------------------- #

def port_via_aob(
    old_table: dict,
    new_so: str,
    imagebase: int = 0,
    new_elf: Optional[aob.ElfMap] = None,
    old_so: Optional[str] = None,
    old_elf: Optional[aob.ElfMap] = None,
) -> tuple[dict, dict]:
    """Port every signature-bearing entry by re-scanning the new `.so`.

    Entries lacking a `sig` but carrying an `rva` are auto-signatured from
    `old_so` first (single-version heuristic) when `old_so` is supplied.

    Returns (new_table, report). Per-entry status is one of:
    unchanged | moved | missing | ambiguous | skipped(no-sig).
    """
    new_table = copy.deepcopy(old_table)
    new_table["ported_from"] = {
        "version": old_table.get("version"),
        "sha256": old_table.get("sha256"),
    }
    try:
        new_table["sha256"] = aob.sha256_file(new_so)
    except OSError:
        new_table["sha256"] = None

    report = {
        "new_so": new_so,
        "unchanged": [],
        "moved": [],
        "missing": [],
        "ambiguous": [],
        "skipped": [],
        "authored": [],
    }

    for name, entry in new_table.get("offsets", {}).items():
        sig = entry.get("sig")
        old_rva = _as_int(entry.get("rva"))

        if not sig and old_so and old_rva is not None:
            try:
                auth = aob.author_signature(
                    old_so, old_rva, imagebase=imagebase, elf=old_elf, name=name
                )
                if auth.get("unique"):
                    sig = auth["sig"]
                    entry["sig"] = sig
                    report["authored"].append(name)
            except (ValueError, OSError):
                pass

        if not sig:
            report["skipped"].append(name)
            continue

        res = aob.resolve_offline(
            new_so, aob.Signature.parse(sig, name), imagebase, new_elf
        )
        if res["status"] == "missing":
            entry["status"] = "missing"
            report["missing"].append(name)
        elif res["status"] == "ambiguous":
            entry["status"] = "ambiguous"
            entry["candidates"] = [_hx(r) for r in res.get("all_rva", [])]
            report["ambiguous"].append({"name": name, "count": res["count"]})
        else:
            new_rva = res["rva"]
            if new_rva == old_rva:
                entry["status"] = "unchanged"
                report["unchanged"].append(name)
            else:
                entry["old_rva"] = _hx(old_rva)
                entry["rva"] = _hx(new_rva)
                entry["status"] = "moved"
                report["moved"].append(
                    {"name": name, "old": _hx(old_rva), "new": _hx(new_rva)}
                )

    report["summary"] = {
        k: len(report[k])
        for k in ("unchanged", "moved", "missing", "ambiguous", "skipped", "authored")
    }
    return new_table, report


# --------------------------------------------------------------------------- #
# Strategy 2: ghidriff function-matching
# --------------------------------------------------------------------------- #

def parse_ghidriff_matches(obj: dict) -> list[dict]:
    """Extract matched (old->new) function pairs from a ghidriff JSON result.

    Tolerant of several ghidriff layouts:
      * {"functions": {"modified": [{"old": {...}, "new": {...}}, ...]}}
      * {"matches": [{"old_name","old_addr","new_name","new_addr"}, ...]}
      * {"funcs": {"modified":[...]}}  (alias)
    Each pair is normalized to {old_name,new_name,old_addr,new_addr}.
    """
    pairs: list[dict] = []

    def _addr(d: dict):
        for k in ("address", "paddress", "addr", "entry", "offset"):
            if k in d and d[k] is not None:
                return _as_int(d[k])
        return None

    def _name(d: dict):
        for k in ("fullname", "name", "symbol"):
            if k in d and d[k]:
                return d[k]
        return None

    # flat matches list
    for m in obj.get("matches", []) or []:
        pairs.append(
            {
                "old_name": m.get("old_name") or m.get("name"),
                "new_name": m.get("new_name") or m.get("name"),
                "old_addr": _as_int(m.get("old_addr")),
                "new_addr": _as_int(m.get("new_addr")),
            }
        )

    # nested functions/funcs -> modified (old/new sub-dicts)
    funcs = obj.get("functions") or obj.get("funcs") or {}
    for bucket in ("modified", "matched", "changed"):
        for m in funcs.get(bucket, []) or []:
            old = m.get("old") or {}
            new = m.get("new") or {}
            if not old and not new:
                continue
            pairs.append(
                {
                    "old_name": _name(old),
                    "new_name": _name(new),
                    "old_addr": _addr(old),
                    "new_addr": _addr(new),
                }
            )
    return pairs


def port_via_ghidriff(
    old_table: dict, ghidriff_obj: dict, ghidra_base: int = 0
) -> tuple[dict, dict]:
    """Port the table using ghidriff's matched function pairs.

    Matches a table entry to a pair by (1) function name == entry key/`name`,
    else (2) old address == pinned rva (+ optional Ghidra image base). ghidriff
    addresses may carry a Ghidra load base; pass `--ghidra-base` to subtract it
    so the emitted RVA is file-relative (BC: base 0x0 -> Ghidra often 0x100000).

    Returns (new_table, report) with per-entry status moved|unchanged|unmatched.
    """
    new_table = copy.deepcopy(old_table)
    pairs = parse_ghidriff_matches(ghidriff_obj)
    by_name = {p["old_name"]: p for p in pairs if p.get("old_name")}
    by_addr = {p["old_addr"]: p for p in pairs if p.get("old_addr") is not None}

    report = {"moved": [], "unchanged": [], "unmatched": []}

    for name, entry in new_table.get("offsets", {}).items():
        key = entry.get("name", name)
        old_rva = _as_int(entry.get("rva"))
        pair = by_name.get(key)
        if pair is None and old_rva is not None:
            pair = by_addr.get(old_rva + ghidra_base)
        if pair is None or pair.get("new_addr") is None:
            entry["status"] = "unmatched"
            report["unmatched"].append(name)
            continue
        new_rva = pair["new_addr"] - ghidra_base
        if new_rva == old_rva:
            entry["status"] = "unchanged"
            report["unchanged"].append(name)
        else:
            entry["old_rva"] = _hx(old_rva)
            entry["rva"] = _hx(new_rva)
            entry["status"] = "moved"
            report["moved"].append({"name": name, "old": _hx(old_rva), "new": _hx(new_rva)})

    report["summary"] = {k: len(report[k]) for k in ("moved", "unchanged", "unmatched")}
    return new_table, report


def run_ghidriff(
    old_so: str, new_so: str, outdir: str, engine: str = "VersionTrackingDiff"
) -> dict:
    """Shell out to ghidriff to diff two `.so` files and load its JSON result.

    LONG operation (Ghidra analysis, minutes) -- wrap the caller with `longrun`.
    Requires GHIDRA_INSTALL_DIR and the `ghidriff` package. Returns a dict:
    {ok, json_path, obj?, error?}. Never raises for a missing toolchain -- it
    reports the gap so the AOB path can carry the port instead.
    """
    if not os.environ.get("GHIDRA_INSTALL_DIR"):
        return {"ok": False, "error": "GHIDRA_INSTALL_DIR unset; use port-aob instead"}
    os.makedirs(outdir, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "ghidriff",
        old_so,
        new_so,
        "-o",
        outdir,
        "--engine",
        engine,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60 * 30
        )
    except FileNotFoundError:
        return {"ok": False, "error": "ghidriff not installed"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "ghidriff timed out (>30m)"}
    # find the produced .ghidriff.json
    found = None
    for root, _dirs, files in os.walk(outdir):
        for f in files:
            if f.endswith(".ghidriff.json") or f.endswith(".json"):
                found = os.path.join(root, f)
                break
        if found:
            break
    if not found:
        return {
            "ok": False,
            "error": "no ghidriff json produced",
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
    with open(found, "r", encoding="utf-8") as fh:
        obj = json.load(fh)
    return {"ok": True, "json_path": found, "obj": obj, "returncode": proc.returncode}


# --------------------------------------------------------------------------- #
# APK helper + triage orchestration
# --------------------------------------------------------------------------- #

def extract_so_from_apk(
    apk_path: str, dest_dir: str, abi_pref=("x86_64", "arm64-v8a", "armeabi-v7a")
) -> Optional[str]:
    """Pull `lib/<abi>/libnative-lib.so` out of an APK (no apktool needed -- an
    APK is a zip). Returns the extracted path or None. Prefers x86_64 (matches
    the BlueStacks image and the pinned offset table).
    """
    with zipfile.ZipFile(apk_path) as zf:
        names = zf.namelist()
        for abi in abi_pref:
            target = f"lib/{abi}/libnative-lib.so"
            if target in names:
                os.makedirs(dest_dir, exist_ok=True)
                out = os.path.join(dest_dir, f"libnative-lib-{abi}.so")
                with zf.open(target) as src, open(out, "wb") as dst:
                    dst.write(src.read())
                return out
    return None


def _resolve_so(path: str, workdir: str, tag: str) -> Optional[str]:
    if path.lower().endswith(".apk"):
        return extract_so_from_apk(path, os.path.join(workdir, tag))
    return path


def triage(
    old_input: str,
    new_input: str,
    table: Optional[dict] = None,
    workdir: Optional[str] = None,
    use_ghidriff: bool = False,
    imagebase: int = 0,
) -> dict:
    """Per-version-bump triage: extract + sha-compare the two native `.so`s and,
    if they differ and a table is given, auto-port it.

    `old_input`/`new_input` may be `.so` files or `.apk` packages. Returns a
    structured report; when the native code is unchanged it says so and does no
    porting work.
    """
    import tempfile

    tmp = workdir or tempfile.mkdtemp(prefix="bc-triage-")
    old_so = _resolve_so(old_input, tmp, "old")
    new_so = _resolve_so(new_input, tmp, "new")
    report: dict = {
        "old_input": old_input,
        "new_input": new_input,
        "old_so": old_so,
        "new_so": new_so,
    }
    if not old_so or not new_so:
        report["error"] = "could not locate libnative-lib.so in one/both inputs"
        return report

    report["old_sha256"] = aob.sha256_file(old_so)
    report["new_sha256"] = aob.sha256_file(new_so)
    report["native_changed"] = report["old_sha256"] != report["new_sha256"]

    if not report["native_changed"]:
        report["verdict"] = "native code UNCHANGED -- pinned offsets still valid"
        return report

    report["verdict"] = "native code CHANGED -- offsets must be re-ported"
    if table is not None:
        new_table, port_report = port_via_aob(
            table, new_so, imagebase=imagebase, old_so=old_so
        )
        report["aob_port"] = port_report
        report["new_table"] = new_table
        if use_ghidriff:
            gr = run_ghidriff(old_so, new_so, os.path.join(tmp, "ghidriff"))
            report["ghidriff"] = {"ok": gr["ok"], "error": gr.get("error")}
            if gr["ok"]:
                _gt, gr_report = port_via_ghidriff(table, gr["obj"])
                report["ghidriff_port"] = gr_report
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _elf_for(path: str, use_sections: bool) -> Optional[aob.ElfMap]:
    return aob.ElfMap(path) if use_sections else None


def _cli(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="ghidriff cross-version .so diff + offset porter (BC)")
    p.add_argument("--imagebase", default="0x0")
    p.add_argument("--elf-sections", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("port-aob", help="port a table by AOB re-scan of the new .so")
    pa.add_argument("table")
    pa.add_argument("new_so")
    pa.add_argument("--old-so", default=None, help="author missing sigs from this old .so")
    pa.add_argument("--out", default=None, help="write ported table json here")

    pg = sub.add_parser("port-ghidriff", help="port a table from a ghidriff JSON result")
    pg.add_argument("table")
    pg.add_argument("ghidriff_json")
    pg.add_argument("--ghidra-base", default="0x0")
    pg.add_argument("--out", default=None)

    di = sub.add_parser("diff", help="run ghidriff on two .so files (needs Ghidra; long)")
    di.add_argument("old_so")
    di.add_argument("new_so")
    di.add_argument("--out", default="ghidriff-out")

    tr = sub.add_parser("triage", help="version-bump triage (.so or .apk inputs)")
    tr.add_argument("old_input")
    tr.add_argument("new_input")
    tr.add_argument("--table", default=None)
    tr.add_argument("--ghidriff", action="store_true", help="cross-check with ghidriff")
    tr.add_argument("--out", default=None, help="write ported table json here")

    sub.add_parser("selftest", help="run the built-in offline self-test")

    args = p.parse_args(argv)
    imagebase = _as_int(args.imagebase) or 0

    if args.cmd == "selftest":
        return 0 if selftest() else 1

    if args.cmd == "port-aob":
        table = load_table(args.table)
        new_elf = _elf_for(args.new_so, args.elf_sections)
        old_elf = _elf_for(args.old_so, args.elf_sections) if args.old_so else None
        new_table, report = port_via_aob(
            table, args.new_so, imagebase, new_elf, args.old_so, old_elf
        )
        if args.out:
            save_table(new_table, args.out)
            report["written"] = args.out
        print(json.dumps(report, indent=2))
        return 0

    if args.cmd == "port-ghidriff":
        table = load_table(args.table)
        with open(args.ghidriff_json, "r", encoding="utf-8") as fh:
            gobj = json.load(fh)
        new_table, report = port_via_ghidriff(table, gobj, _as_int(args.ghidra_base) or 0)
        if args.out:
            save_table(new_table, args.out)
            report["written"] = args.out
        print(json.dumps(report, indent=2))
        return 0

    if args.cmd == "diff":
        res = run_ghidriff(args.old_so, args.new_so, args.out)
        print(json.dumps({k: v for k, v in res.items() if k != "obj"}, indent=2))
        return 0 if res["ok"] else 1

    if args.cmd == "triage":
        table = load_table(args.table) if args.table else None
        rep = triage(args.old_input, args.new_input, table, use_ghidriff=args.ghidriff, imagebase=imagebase)
        if args.out and rep.get("new_table"):
            save_table(rep["new_table"], args.out)
            rep["written"] = args.out
        # keep console output compact: drop the full table body
        printable = {k: v for k, v in rep.items() if k != "new_table"}
        print(json.dumps(printable, indent=2))
        return 0

    return 2


# --------------------------------------------------------------------------- #
# Built-in offline self-test
# --------------------------------------------------------------------------- #

def selftest() -> bool:
    import tempfile

    ok = True

    def check(name: str, cond: bool) -> None:
        nonlocal ok
        print(f"[{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    # Reuse aob's synthetic relink model: a function present in v1 and v2 at
    # different offsets, plus an unchanged function to prove 'unchanged' status.
    def make_func(prologue: bytes, disp: bytes) -> bytes:
        return prologue + b"\xe8" + disp + b"\x48\x83\xc4\x20\x5d\xc3"

    f_moved_v1 = make_func(b"\x55\x48\x89\xe5", b"\x11\x22\x33\x44")
    f_moved_v2 = make_func(b"\x55\x48\x89\xe5", b"\xaa\xbb\xcc\xdd")
    # a second, distinct function that stays at the same offset in both
    f_stable = make_func(b"\x53\x48\x89\xfb", b"\x01\x02\x03\x04")

    pad = b"\x90" * 48
    # v1: [pad][f_moved@0x30][pad][f_stable@?]
    v1 = pad + f_moved_v1 + pad + f_stable + pad
    stable_off_v1 = len(pad) + len(f_moved_v1) + len(pad)
    # v2: extra padding shifts f_moved; keep f_stable at the SAME absolute offset
    lead = b"\xcc" * 64
    body_v2 = f_moved_v2
    # pad so f_stable lands at exactly stable_off_v1 again
    gap = stable_off_v1 - (len(lead) + len(body_v2))
    assert gap >= 0, "adjust selftest layout"
    v2 = lead + body_v2 + (b"\x90" * gap) + f_stable + pad
    moved_off_v1 = len(pad)          # 0x30
    moved_off_v2 = len(lead)         # 0x40

    with tempfile.TemporaryDirectory() as td:
        v1p = os.path.join(td, "v1.so")
        v2p = os.path.join(td, "v2.so")
        with open(v1p, "wb") as fh:
            fh.write(v1)
        with open(v2p, "wb") as fh:
            fh.write(v2)

        # author cross-version sigs for both functions (author-diff for moved,
        # single-version for stable) and build a pinned v1 table.
        moved_sig = aob.author_diff(
            v1p, v2p, moved_off_v1, moved_off_v2, length=len(f_moved_v1), name="moved"
        )["sig"]
        stable_sig = aob.author_signature(
            v1p, stable_off_v1, length=len(f_stable), min_fixed=6, name="stable"
        )["sig"]

        table = {
            "so": "libnative-lib.so",
            "version": "v1",
            "sha256": aob.sha256_file(v1p),
            "offsets": {
                "moved": {"rva": aob._off_to_rva(moved_off_v1, 0, None), "sig": moved_sig},
                "stable": {"rva": aob._off_to_rva(stable_off_v1, 0, None), "sig": stable_sig},
                "nosig": {"rva": "0x10"},  # no sig, no old_so -> skipped
            },
        }
        # normalize hex form (tables are usually authored as hex strings)
        table["offsets"]["moved"]["rva"] = _hx(table["offsets"]["moved"]["rva"])
        table["offsets"]["stable"]["rva"] = _hx(table["offsets"]["stable"]["rva"])

        # --- Strategy 1: AOB port ---
        new_table, report = port_via_aob(table, v2p)
        check("aob: moved function re-located", len(report["moved"]) == 1)
        check(
            "aob: moved new rva correct",
            _as_int(new_table["offsets"]["moved"]["rva"]) == moved_off_v2,
        )
        check("aob: stable function unchanged", "stable" in report["unchanged"])
        check("aob: entry without sig skipped", "nosig" in report["skipped"])
        check("aob: new table carries new sha256", new_table["sha256"] == aob.sha256_file(v2p))
        check("aob: ported_from records old version", new_table["ported_from"]["version"] == "v1")

        # a pinned RVA in v1 that no longer resolves -> 'missing'
        bad_table = {
            "sha256": "x",
            "offsets": {"gone": {"rva": "0x0", "sig": "DE AD BE EF CA FE BA BE C0 DE"}},
        }
        _nt, bad_report = port_via_aob(bad_table, v2p)
        check("aob: unresolvable sig -> missing", "gone" in bad_report["missing"])

        # auto-author a missing sig from old_so, then port
        noSig_table = {
            "sha256": "x",
            "offsets": {"moved": {"rva": _hx(moved_off_v1)}},  # no sig
        }
        nt2, rep2 = port_via_aob(noSig_table, v2p, old_so=v1p)
        check("aob: auto-authored sig from old_so", "moved" in rep2["authored"])
        check(
            "aob: auto-authored port re-located moved fn",
            _as_int(nt2["offsets"]["moved"]["rva"]) == moved_off_v2,
        )

        # --- Strategy 2: ghidriff JSON port (both layouts) ---
        gobj_nested = {
            "functions": {
                "modified": [
                    {
                        "old": {"name": "moved", "address": _hx(moved_off_v1)},
                        "new": {"name": "moved", "address": _hx(moved_off_v2)},
                    }
                ]
            }
        }
        _gt, grep = port_via_ghidriff(table, gobj_nested)
        check("ghidriff(nested): moved matched by name", len(grep["moved"]) == 1)
        check(
            "ghidriff(nested): new rva correct",
            _as_int(_gt["offsets"]["moved"]["rva"]) == moved_off_v2,
        )
        check("ghidriff(nested): nosig unmatched", "nosig" in grep["unmatched"])

        gobj_flat = {
            "matches": [
                {
                    "old_name": "moved",
                    "new_name": "moved",
                    "old_addr": _hx(moved_off_v1),
                    "new_addr": _hx(moved_off_v2),
                }
            ]
        }
        pairs = parse_ghidriff_matches(gobj_flat)
        check("ghidriff: flat layout parsed", len(pairs) == 1 and pairs[0]["new_addr"] == moved_off_v2)

        # ghidra base subtraction
        gobj_based = {
            "matches": [
                {
                    "old_name": "moved",
                    "new_name": "moved",
                    "old_addr": _hx(moved_off_v1 + 0x100000),
                    "new_addr": _hx(moved_off_v2 + 0x100000),
                }
            ]
        }
        _gt2, grep2 = port_via_ghidriff(table, gobj_based, ghidra_base=0x100000)
        check(
            "ghidriff: ghidra base subtracted correctly",
            _as_int(_gt2["offsets"]["moved"]["rva"]) == moved_off_v2,
        )

        # --- APK extraction + triage ---
        apk_new = os.path.join(td, "new.apk")
        with zipfile.ZipFile(apk_new, "w") as zf:
            zf.writestr("lib/x86_64/libnative-lib.so", v2)
            zf.writestr("lib/arm64-v8a/libnative-lib.so", b"\x00\x01\x02")
            zf.writestr("AndroidManifest.xml", b"stub")
        extracted = extract_so_from_apk(apk_new, os.path.join(td, "ex"))
        check("apk: x86_64 .so extracted", extracted is not None and os.path.exists(extracted))
        check("apk: extracted bytes match v2", open(extracted, "rb").read() == v2)

        # triage: old .so vs new .apk, native changed -> ports the table
        tri = triage(v1p, apk_new, table=table, workdir=os.path.join(td, "tri"))
        check("triage: native change detected", tri["native_changed"])
        check("triage: verdict says re-port", "CHANGED" in tri["verdict"])
        check("triage: aob port ran", tri.get("aob_port", {}).get("summary", {}).get("moved") == 1)

        # triage: identical inputs -> no change, no porting
        tri_same = triage(v1p, v1p, table=table, workdir=os.path.join(td, "tri2"))
        check("triage: identical -> UNCHANGED", not tri_same["native_changed"] and "UNCHANGED" in tri_same["verdict"])

        # run_ghidriff degrades gracefully without GHIDRA_INSTALL_DIR
        saved = os.environ.pop("GHIDRA_INSTALL_DIR", None)
        try:
            gr = run_ghidriff(v1p, v2p, os.path.join(td, "gr"))
            check("run_ghidriff: no-ghidra reports gap (never raises)", gr["ok"] is False and "GHIDRA" in gr["error"])
        finally:
            if saved is not None:
                os.environ["GHIDRA_INSTALL_DIR"] = saved

    print("SELFTEST:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(_cli())
