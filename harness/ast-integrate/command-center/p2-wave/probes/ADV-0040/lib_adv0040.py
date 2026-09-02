"""ADV-0040 recall-calibrated PII sweep: text+entropy and non-text PNG metadata.

Planted values are assembled at runtime from fragments, used only in a scratch
directory, then deleted. Match text is never returned.
"""
from __future__ import annotations

import binascii
import json
import math
import os
import re
import struct
import tempfile
import zlib
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0040"
OUT_REL = "command-center/adversarial/ADV-0040-corpus-pii-recall-calibrated-sweep.json"
SCHEMA_REL = "command-center/schema/privacy-dataflow.schema.json"
NEG = HERE / "fixtures" / "negative.users-word-only.txt"

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
}
SKIP_DIR_PARTS = ("/p2-wave/probes/",)
TEXT_SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".so",
    ".o",
    ".a",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".woff",
    ".woff2",
    ".tar",
    ".zip",
    ".gz",
    ".xz",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_LOCATIONS = 12
CORPUS_ROOTS = (
    REPO / "command-center" / "adversarial",
    REPO / "command-center" / "research",
    REPO / "command-center" / "audit",
    REPO / "command-center" / "schema",
)
CORPUS_TOP_GLOBS = ("*.md", "*.json", "*.txt", "*.jsonl")

CONTENT_CATEGORIES = (
    "person_name",
    "email",
    "phone",
    "windows_home_path",
    "unix_home_path",
    "private_url",
)
HOME_CATS = {"windows_home_path", "unix_home_path"}


def _win_re() -> re.Pattern[str]:
    return re.compile(r"C:[/\\]+Users[/\\]+[A-Za-z_][A-Za-z0-9._-]{1,63}", re.I)


def _unix_re() -> re.Pattern[str]:
    name = r"[A-Za-z_][A-Za-z0-9._-]{1,63}"
    return re.compile(r"(?:^|[^A-Za-z0-9:])(?:/home|/Users)/" + name)


def _email_re() -> re.Pattern[str]:
    return re.compile(
        r"\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,24}\b"
    )


def _phone_re() -> re.Pattern[str]:
    return re.compile(r"\+1[-. ]?\d{3}[-. ]?\d{3}[-. ]?\d{4}")


def _url_re() -> re.Pattern[str]:
    priv = (
        r"(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|192\.168\.\d{1,3}\.\d{1,3}"
        r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"
    )
    return re.compile(r"https?://" + priv + r"(?:/[^\s]*)?", re.I)


def _name_re() -> re.Pattern[str]:
    return re.compile(
        r"(?im)^(?:full[_-]?name|display[_-]?name|author|from)\s*[:=]\s*"
        r"[A-Z][a-z]{1,24}(?:\s+[A-Z][a-z]{1,24}){1,3}\s*$"
    )


WIN_RE = _win_re()
UNIX_RE = _unix_re()
EMAIL_RE = _email_re()
PHONE_RE = _phone_re()
URL_RE = _url_re()
NAME_RE = _name_re()
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("windows_home_path", WIN_RE),
    ("unix_home_path", UNIX_RE),
    ("email", EMAIL_RE),
    ("phone", PHONE_RE),
    ("private_url", URL_RE),
    ("person_name", NAME_RE),
]


def posix(rel: str) -> str:
    return str(rel).replace("\\", "/").lstrip("./")


def shannon(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def assemble_text_plants() -> list[dict]:
    """Values exist only in returned dicts; callers must not persist them."""
    given = "Ada"
    family = "Lovelace" + "Piiplant"
    local = "ada.lovelace.piiplant"
    domain = "example" + "." + "test"
    owner = "Piiplant" + "Owner"
    unix_user = "piiplant" + "-owner"
    oct0 = "192"
    oct1 = "168"
    oct2 = "40"
    oct3 = "40"
    return [
        {
            "id": "P-NAME",
            "category": "person_name",
            "label": "full_name",
            "value": given + " " + family,
        },
        {
            "id": "P-EMAIL",
            "category": "email",
            "label": "email",
            "value": local + "@" + domain,
        },
        {
            "id": "P-PHONE",
            "category": "phone",
            "label": "phone",
            "value": "+1" + "-555" + "-010" + "-0040",
        },
        {
            "id": "P-WIN",
            "category": "windows_home_path",
            "label": "home_win",
            "value": "C:" + "/" + "Users" + "/" + owner + "/docs",
        },
        {
            "id": "P-UNIX",
            "category": "unix_home_path",
            "label": "home_unix",
            "value": "/home/" + unix_user + "/docs",
        },
        {
            "id": "P-URL",
            "category": "private_url",
            "label": "private_url",
            "value": "https://" + ".".join((oct0, oct1, oct2, oct3)) + "/inbox",
        },
    ]


def png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_png_ztxt(path: Path, keyword: str, payload: str) -> None:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00")
    ztxt = keyword.encode("latin-1") + b"\x00\x00" + zlib.compress(
        payload.encode("utf-8")
    )
    path.write_bytes(
        sig
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"zTXt", ztxt)
        + png_chunk(b"IDAT", idat)
        + png_chunk(b"IEND", b"")
    )


def iter_png_chunks(data: bytes):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return
    i = 8
    n = len(data)
    while i + 12 <= n:
        length = struct.unpack(">I", data[i : i + 4])[0]
        tag = data[i + 4 : i + 8]
        start = i + 8
        end = start + length
        if end + 4 > n:
            break
        yield tag, data[start:end]
        i = end + 4
        if tag == b"IEND":
            break


def extract_png_text(data: bytes) -> str:
    parts: list[str] = []
    for tag, chunk in iter_png_chunks(data):
        if tag == b"tEXt":
            nul = chunk.find(b"\x00")
            body = chunk[nul + 1 :] if nul >= 0 else chunk
            parts.append(body.decode("latin-1", "replace"))
        elif tag == b"zTXt":
            nul = chunk.find(b"\x00")
            if nul < 0 or nul + 2 > len(chunk):
                continue
            if chunk[nul + 1 : nul + 2] != b"\x00":
                continue
            try:
                parts.append(zlib.decompress(chunk[nul + 2 :]).decode("utf-8", "replace"))
            except zlib.error:
                continue
        elif tag == b"iTXt":
            nul = chunk.find(b"\x00")
            if nul < 0:
                continue
            rest = chunk[nul + 1 :]
            if len(rest) < 2:
                continue
            compressed, _comp = rest[0], rest[1]
            rest = rest[2:]
            for _ in range(2):
                z = rest.find(b"\x00")
                if z < 0:
                    rest = b""
                    break
                rest = rest[z + 1 :]
            try:
                text = (
                    zlib.decompress(rest).decode("utf-8", "replace")
                    if compressed
                    else rest.decode("utf-8", "replace")
                )
            except zlib.error:
                continue
            parts.append(text)
    return "\n".join(parts)


def extract_nontext(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    if path.suffix.lower() == ".png" or raw[:8] == b"\x89PNG\r\n\x1a\n":
        return extract_png_text(raw)
    return ""


def exclusive_hits(text: str) -> list[dict]:
    occupied: list[tuple[int, int]] = []
    hits: list[dict] = []
    for category, cre in PATTERNS:
        for m in cre.finditer(text):
            start, end = m.span()
            if any(start < oend and end > ostart for ostart, oend in occupied):
                continue
            occupied.append((start, end))
            span = m.group(0)
            hits.append(
                {
                    "category": category,
                    "line": text.count("\n", 0, start) + 1,
                    "span_len": end - start,
                    "entropy": round(shannon(span), 4),
                    "kind": "content",
                }
            )
    return hits


def scan_text(text: str) -> list[dict]:
    return exclusive_hits(text)


def decode_text(path: Path) -> str | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > MAX_FILE_BYTES:
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:1024]:
        return None
    return raw.decode("utf-8", errors="replace")


def rel_of(path: Path, root: Path) -> str:
    try:
        return posix(path.resolve().relative_to(root.resolve()).as_posix())
    except ValueError:
        return posix(str(path))


def _skip_dir(dirpath: Path) -> bool:
    posix_p = dirpath.as_posix()
    if dirpath.name in SKIP_DIR_NAMES:
        return True
    return any(part in posix_p for part in SKIP_DIR_PARTS)


def iter_corpus_text_files() -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in seen or not resolved.is_file():
            return
        if resolved.suffix.lower() in TEXT_SKIP_SUFFIXES:
            return
        seen.add(resolved)
        out.append(resolved)

    for root in CORPUS_ROOTS:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dpath = Path(dirpath)
            dirnames[:] = [
                d for d in dirnames if not _skip_dir(dpath / d)
            ]
            if _skip_dir(dpath):
                continue
            for name in filenames:
                add(dpath / name)
    top = REPO / "command-center"
    if top.is_dir():
        for pattern in CORPUS_TOP_GLOBS:
            for path in top.glob(pattern):
                if path.is_file():
                    add(path)
    out.sort()
    return out


def iter_corpus_images() -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    roots = [r for r in CORPUS_ROOTS if r.is_dir()]
    top = REPO / "command-center"
    if top.is_dir():
        roots.append(top)
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dpath = Path(dirpath)
            dirnames[:] = [d for d in dirnames if not _skip_dir(dpath / d)]
            if _skip_dir(dpath):
                continue
            if "p2-wave" in dpath.parts:
                continue
            for name in filenames:
                path = dpath / name
                if path.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                try:
                    resolved = path.resolve()
                except OSError:
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                out.append(resolved)
    out.sort()
    return out


def scan_corpus_text() -> dict:
    rows = []
    locations: dict[str, list[dict]] = {c: [] for c in CONTENT_CATEGORIES}
    by_cat = {c: 0 for c in CONTENT_CATEGORIES}
    scanned = 0
    for path in iter_corpus_text_files():
        rel = rel_of(path, REPO)
        if rel == OUT_REL:
            continue
        text = decode_text(path)
        if text is None:
            continue
        scanned += 1
        hits = scan_text(text)
        for h in hits:
            cat = h["category"]
            by_cat[cat] += 1
            if len(locations[cat]) < MAX_LOCATIONS:
                locations[cat].append(
                    {
                        "path": rel,
                        "line": h["line"],
                        "category": cat,
                        "span_len": h["span_len"],
                        "entropy": h["entropy"],
                        "value_redacted": True,
                    }
                )
        if hits:
            rows.append({"path": rel, "hit_n": len(hits)})
    return {
        "files_scanned": scanned,
        "by_category": by_cat,
        "locations": locations,
        "files_with_hits": len(rows),
        "value_reproduced": False,
    }


def scan_corpus_nontext() -> dict:
    images = iter_corpus_images()
    by_cat = {c: 0 for c in CONTENT_CATEGORIES}
    locations: dict[str, list[dict]] = {c: [] for c in CONTENT_CATEGORIES}
    extracted = 0
    for path in images:
        rel = rel_of(path, REPO)
        payload = extract_nontext(path)
        if payload:
            extracted += 1
        hits = scan_text(payload) if payload else []
        for h in hits:
            cat = h["category"]
            by_cat[cat] += 1
            if len(locations[cat]) < MAX_LOCATIONS:
                locations[cat].append(
                    {
                        "path": rel,
                        "line": h["line"],
                        "category": cat,
                        "span_len": h["span_len"],
                        "entropy": h["entropy"],
                        "channel": "png-ztxt-or-itxt",
                        "value_redacted": True,
                    }
                )
    return {
        "image_files": len(images),
        "files_with_extractable_text": extracted,
        "by_category": by_cat,
        "locations": locations,
        "value_reproduced": False,
    }


def _public_plant_row(plant: dict, found: bool) -> dict:
    return {
        "id": plant["id"],
        "category": plant["category"],
        "found": found,
        "entropy": round(shannon(plant["value"]), 4),
        "span_len": len(plant["value"]),
        "value_reproduced": False,
    }


def run_text_plants() -> dict:
    plants = assemble_text_plants()
    expected = {p["category"] for p in plants}
    with tempfile.TemporaryDirectory(prefix="adv0040-text-") as tmp:
        scratch = Path(tmp) / "planted-pii.txt"
        lines = [f"{p['label']}: {p['value']}" for p in plants]
        scratch.write_text("\n".join(lines) + "\n", encoding="utf-8")
        hits = scan_text(scratch.read_text(encoding="utf-8"))
        found_cats = {h["category"] for h in hits}
        per = [_public_plant_row(p, p["category"] in found_cats) for p in plants]
        scratch.unlink()
        removed_gone = not scratch.exists()
        removed_hits = scan_text("control-line removed\n")
        removed_cats = {h["category"] for h in removed_hits} & expected
    neg_hits = []
    if NEG.is_file():
        neg_hits = [
            h
            for h in scan_text(NEG.read_text(encoding="utf-8"))
            if h["category"] in HOME_CATS | {"email", "phone", "private_url"}
        ]
    found_n = sum(1 for r in per if r["found"])
    recall = found_n / len(plants) if plants else 0.0
    return {
        "channel": "text-pattern-plus-entropy",
        "planted": per,
        "planted_n": len(plants),
        "found_n": found_n,
        "recall": recall,
        "removed_verified": removed_gone and not removed_cats,
        "negative_users_word_only_silent": not neg_hits,
        "scratch_outside_tree": True,
        "value_reproduced": False,
        "pass": recall == 1.0
        and removed_gone
        and not removed_cats
        and not neg_hits,
    }


def run_nontext_plants() -> dict:
    plants = assemble_text_plants()
    email = next(p["value"] for p in plants if p["category"] == "email")
    phone = next(p["value"] for p in plants if p["category"] == "phone")
    payload = "email: " + email + "\nphone: " + phone + "\n"
    expected = {"email", "phone"}
    with tempfile.TemporaryDirectory(prefix="adv0040-img-") as tmp:
        planted = Path(tmp) / "screenshot-plant.png"
        clean = Path(tmp) / "screenshot-clean.png"
        pad = 0
        while True:
            body = payload + ("\n" * pad)
            write_png_ztxt(planted, "Comment", body)
            raw_plant = planted.read_bytes()
            if email.encode("ascii") not in raw_plant and phone.encode(
                "ascii"
            ) not in raw_plant:
                break
            pad += 1
            if pad > 32:
                break
        write_png_ztxt(clean, "Comment", "no personal data in this control image")
        decoded = decode_text(planted)
        if decoded is None:
            text_pii = []
        else:
            text_pii = [h for h in scan_text(decoded) if h["category"] in expected]
        extracted = extract_png_text(raw_plant)
        meta_hits = scan_text(extracted)
        meta_cats = {h["category"] for h in meta_hits if h["category"] in expected}
        clean_hits = scan_text(extract_png_text(clean.read_bytes()))
        clean_pii = [h for h in clean_hits if h["category"] in expected]
        planted.unlink()
        clean.unlink()
        removed = (not planted.exists()) and (not clean.exists())
    found_n = len(meta_cats)
    recall = found_n / len(expected)
    blindness = not text_pii and decoded is None
    return {
        "channel": "png-ztxt-inflate",
        "method": "zlib-inflate PNG zTXt (text sweep of file bytes is blind)",
        "planted_categories": sorted(expected),
        "found_n": found_n,
        "recall": recall,
        "text_sweep_hits_on_png_bytes": len(text_pii),
        "text_sweep_blind_to_screenshot": blindness,
        "clean_image_silent": not clean_pii,
        "removed_verified": removed,
        "scratch_outside_tree": True,
        "value_reproduced": False,
        "ocr_engine": None,
        "pass": recall == 1.0 and blindness and not clean_pii and removed,
    }


def artifact_leaks_values(doc: dict) -> list[str]:
    """Return leak labels. Must not include the values themselves."""
    blob = json.dumps(doc, ensure_ascii=True)
    leaks: list[str] = []
    if EMAIL_RE.search(blob):
        leaks.append("email")
    if PHONE_RE.search(blob):
        leaks.append("phone")
    if WIN_RE.search(blob):
        leaks.append("windows_home_path")
    if UNIX_RE.search(blob):
        leaks.append("unix_home_path")
    if URL_RE.search(blob):
        leaks.append("private_url")
    if '"match_text"' in blob or '"match_value"' in blob or '"snippet"' in blob:
        leaks.append("forbidden_field")
    plants = assemble_text_plants()
    for p in plants:
        if p["value"] in blob:
            leaks.append("plant_value:" + p["category"])
    return leaks


def measure() -> dict:
    text_plants = run_text_plants()
    nontext_plants = run_nontext_plants()
    corpus_text = scan_corpus_text()
    corpus_img = scan_corpus_nontext()
    text_recall = float(text_plants["recall"])
    img_recall = float(nontext_plants["recall"])
    combined_n = text_plants["planted_n"] + 2
    combined_found = text_plants["found_n"] + nontext_plants["found_n"]
    combined_recall = combined_found / combined_n if combined_n else 0.0
    missing_control = not (
        text_plants["pass"] and nontext_plants["pass"]
    )
    return {
        "text_plants": text_plants,
        "nontext_plants": nontext_plants,
        "corpus_text": corpus_text,
        "corpus_nontext": corpus_img,
        "recall": {
            "text_pattern_entropy": text_recall,
            "nontext_png_ztxt": img_recall,
            "planted_pii_recall": combined_recall,
            "planted_n": combined_n,
            "found_n": combined_found,
            "zero_findings_without_recall_is_not_checked": True,
        },
        "missing_control": missing_control,
        "controls_ok": text_plants["pass"] and nontext_plants["pass"],
    }


def target_verdict(
    hits: int, recall: float, *, incomplete: bool = False, missing: bool = False
) -> str:
    if missing:
        return "NOT-CHECKED"
    if recall <= 0:
        return "NOT-CHECKED"
    if incomplete:
        return "CONFIRMED" if hits else "PARTIAL"
    if hits:
        return "CONFIRMED"
    return "REFUTED"
