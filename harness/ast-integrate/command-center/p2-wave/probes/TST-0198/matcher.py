#!/usr/bin/env python3
"""NFC path matching for manifest entries vs filesystem names.

Chosen normal form is NFC (Unicode Normalization Form C). Comparison happens
at match time on both sides. Byte-equality of UTF-8 encodings is not the
predicate: a macOS-decomposed (NFD) name and an NFC manifest entry are
different byte strings and different code-point sequences until normalised.

This worktree has no tools/plugin/pack.py. The procedure this unit is
contracted to prove lives here and is exercised live by the named probes.
"""
from __future__ import annotations

import hashlib
import os
import unicodedata
from pathlib import Path
from typing import Iterable

CHOSEN_FORM = "NFC"

# café: NFC U+00E9 vs NFD U+0065 U+0301
NFC_CAFE_STEM = "caf\u00e9"
NFD_CAFE_STEM = "cafe\u0301"
# が: NFC U+304C vs NFD U+304B U+3099
NFC_GA_STEM = "\u304c"
NFD_GA_STEM = "\u304b\u3099"
ASCII_STEM = "readme"

PAYLOADS = {
    "ascii": b"ascii-payload-TST-0198\n",
    "cafe": b"cafe-payload-TST-0198\n",
    "ga": b"hiragana-ga-payload-TST-0198\n",
}


def to_form(s: str, form: str = CHOSEN_FORM) -> str:
    if form not in {"NFC", "NFD", "NFKC", "NFKD"}:
        raise ValueError(f"unknown normal form {form!r}")
    return unicodedata.normalize(form, s.replace("\\", "/"))


def to_nfc(s: str) -> str:
    return to_form(s, "NFC")


def to_nfd(s: str) -> str:
    return to_form(s, "NFD")


def codepoints(s: str) -> list[int]:
    return [ord(c) for c in s]


def utf8_bytes(s: str) -> bytes:
    return s.encode("utf-8")


def byte_equal(a: str, b: str) -> bool:
    """Raw UTF-8 byte equality. Must FAIL for the NFD/NFC café pair."""
    return utf8_bytes(a) == utf8_bytes(b)


def paths_match(manifest_path: str, filesystem_path: str, form: str = CHOSEN_FORM) -> bool:
    return to_form(manifest_path, form) == to_form(filesystem_path, form)


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def iter_rel_files(root: Path) -> list[str]:
    rels: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = Path(dirpath) / name
            rels.append(full.relative_to(root).as_posix())
    rels.sort()
    return rels


def cafe_encodings() -> dict:
    nfc = f"{NFC_CAFE_STEM}.txt"
    nfd = f"{NFD_CAFE_STEM}.txt"
    return {
        "nfc": nfc,
        "nfd": nfd,
        "nfc_codepoints": codepoints(nfc),
        "nfd_codepoints": codepoints(nfd),
        "nfc_utf8_hex": utf8_bytes(nfc).hex(),
        "nfd_utf8_hex": utf8_bytes(nfd).hex(),
        "byte_equal": byte_equal(nfc, nfd),
        "python_str_equal": nfc == nfd,
        "nfc_match": paths_match(nfc, nfd),
    }


def build_nfd_tree(root: Path) -> dict:
    """Create a macOS-style NFD tree plus a pure-ASCII control file.

    Manifest entries are stored in NFC. On-disk names for the composed
    characters are NFD (as HFS+/APFS decompose). ASCII is identical in both.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    ascii_rel = f"{ASCII_STEM}.txt"
    cafe_rel_nfd = f"docs/{NFD_CAFE_STEM}/{NFD_CAFE_STEM}.txt"
    ga_rel_nfd = f"i18n/{NFD_GA_STEM}.txt"
    cafe_rel_nfc = f"docs/{NFC_CAFE_STEM}/{NFC_CAFE_STEM}.txt"
    ga_rel_nfc = f"i18n/{NFC_GA_STEM}.txt"

    (root / ascii_rel).write_bytes(PAYLOADS["ascii"])
    cafe_path = root / cafe_rel_nfd
    cafe_path.parent.mkdir(parents=True, exist_ok=True)
    cafe_path.write_bytes(PAYLOADS["cafe"])
    ga_path = root / ga_rel_nfd
    ga_path.parent.mkdir(parents=True, exist_ok=True)
    ga_path.write_bytes(PAYLOADS["ga"])

    on_disk = iter_rel_files(root)
    manifest = [
        {
            "path": ascii_rel,
            "form": "NFC",
            "sha256": content_sha256(PAYLOADS["ascii"]),
            "kind": "ascii",
        },
        {
            "path": cafe_rel_nfc,
            "form": "NFC",
            "sha256": content_sha256(PAYLOADS["cafe"]),
            "kind": "cafe",
        },
        {
            "path": ga_rel_nfc,
            "form": "NFC",
            "sha256": content_sha256(PAYLOADS["ga"]),
            "kind": "ga",
        },
    ]
    return {
        "root": str(root),
        "on_disk": on_disk,
        "manifest": manifest,
        "nfd_rels": [cafe_rel_nfd, ga_rel_nfd],
        "nfc_rels": [cafe_rel_nfc, ga_rel_nfc],
        "ascii_rel": ascii_rel,
    }


def match_tree(
    on_disk: Iterable[str], manifest: list[dict]
) -> tuple[list[dict], list[str]]:
    """Signal (a): per-file manifest match after NFC normalisation."""
    rows = []
    used_manifest: set[str] = set()
    for fs_rel in on_disk:
        hits = [
            m
            for m in manifest
            if paths_match(m["path"], fs_rel) and m["path"] not in used_manifest
        ]
        if len(hits) == 1:
            used_manifest.add(hits[0]["path"])
            rows.append(
                {
                    "filesystem_path": fs_rel,
                    "manifest_path": hits[0]["path"],
                    "kind": hits[0]["kind"],
                    "matched": True,
                    "form": CHOSEN_FORM,
                    "byte_equal": byte_equal(fs_rel, hits[0]["path"]),
                    "filesystem_codepoints": codepoints(fs_rel),
                    "manifest_codepoints": codepoints(hits[0]["path"]),
                }
            )
        else:
            rows.append(
                {
                    "filesystem_path": fs_rel,
                    "manifest_path": None,
                    "kind": None,
                    "matched": False,
                    "form": CHOSEN_FORM,
                    "byte_equal": False,
                    "hit_count": len(hits),
                }
            )
    unmatched_manifest = [m["path"] for m in manifest if m["path"] not in used_manifest]
    return rows, unmatched_manifest


def round_trip(src: Path, dest: Path, manifest: list[dict]) -> dict:
    """Copy every source file onto the NFC manifest path. Lose none."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    on_disk = iter_rel_files(src)
    rows, unmatched = match_tree(on_disk, manifest)
    lost = [r["filesystem_path"] for r in rows if not r["matched"]]
    written = []
    for r in rows:
        if not r["matched"]:
            continue
        src_bytes = (src / r["filesystem_path"]).read_bytes()
        out = dest / r["manifest_path"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(src_bytes)
        dest_sha = content_sha256(out.read_bytes())
        man = next(m for m in manifest if m["path"] == r["manifest_path"])
        written.append(
            {
                "dest_path": r["manifest_path"],
                "src_path": r["filesystem_path"],
                "sha256_match": dest_sha == man["sha256"],
                "dest_form_is_nfc": to_nfc(r["manifest_path"]) == r["manifest_path"],
            }
        )
    dest_files = iter_rel_files(dest)
    return {
        "source_count": len(on_disk),
        "manifest_count": len(manifest),
        "dest_count": len(dest_files),
        "lost": lost,
        "unmatched_manifest": unmatched,
        "written": written,
        "no_file_lost": (
            not lost
            and not unmatched
            and len(dest_files) == len(manifest) == len(on_disk)
            and all(w["sha256_match"] for w in written)
        ),
    }


def byte_keyed_copy_loses_nfd(src: Path, dest: Path, manifest: list[dict]) -> dict:
    """Negative: copy keyed on raw path bytes misses NFD names vs NFC keys."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    keys = {m["path"] for m in manifest}
    on_disk = iter_rel_files(src)
    copied = []
    missed = []
    for rel in on_disk:
        if rel in keys:
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes((src / rel).read_bytes())
            copied.append(rel)
        else:
            missed.append(rel)
    return {
        "copied": copied,
        "missed": missed,
        "lost_nfd": any("cafe" in p or "\u304b" in p or "\u304c" in p for p in missed),
        "ascii_copied": any(p.endswith("readme.txt") for p in copied),
    }


def live_campaign(tmp: Path) -> dict:
    src = tmp / "nfd-src"
    dest = tmp / "nfc-dest"
    byte_dest = tmp / "byte-dest"
    built = build_nfd_tree(src)
    rows, unmatched = match_tree(built["on_disk"], built["manifest"])
    trip = round_trip(src, dest, built["manifest"])
    byte_copy = byte_keyed_copy_loses_nfd(src, byte_dest, built["manifest"])
    encodings = cafe_encodings()
    ascii_row = next(r for r in rows if r.get("kind") == "ascii")
    cafe_row = next(r for r in rows if r.get("kind") == "cafe")
    ga_row = next(r for r in rows if r.get("kind") == "ga")
    all_matched = all(r["matched"] for r in rows) and not unmatched
    ascii_trivial = (
        ascii_row["matched"]
        and ascii_row["byte_equal"]
        and ascii_row["filesystem_path"] == ascii_row["manifest_path"]
    )
    nfd_byte_fail = (
        (not encodings["byte_equal"])
        and (not encodings["python_str_equal"])
        and (not cafe_row["byte_equal"])
        and (not ga_row["byte_equal"])
    )
    nfd_nfc_match = cafe_row["matched"] and ga_row["matched"] and encodings["nfc_match"]
    ok = (
        all_matched
        and ascii_trivial
        and nfd_byte_fail
        and nfd_nfc_match
        and trip["no_file_lost"]
        and byte_copy["lost_nfd"]
        and byte_copy["ascii_copied"]
        and encodings["nfc_codepoints"] != encodings["nfd_codepoints"]
    )
    return {
        "chosen_form": CHOSEN_FORM,
        "ok": ok,
        "all_matched": all_matched,
        "ascii_trivial_match": ascii_trivial,
        "nfd_byte_equality_fails": nfd_byte_fail,
        "nfd_nfc_match": nfd_nfc_match,
        "round_trip": trip,
        "byte_keyed_negative": byte_copy,
        "encodings": encodings,
        "per_file": rows,
        "unmatched_manifest": unmatched,
        "on_disk": built["on_disk"],
        "manifest": built["manifest"],
    }
