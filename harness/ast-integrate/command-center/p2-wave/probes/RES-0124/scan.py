"""Publication-privacy scanner: location + category only. Never emit match text."""
from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
}
SKIP_SUFFIXES = {
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
    ".woff",
    ".woff2",
    ".tar",
    ".zip",
    ".gz",
}
MAX_FILE_BYTES = 20 * 1024 * 1024
TOP_FILES = 12

CONTENT_CATEGORIES = (
    "windows_home_path",
    "unix_home_path",
    "email",
    "credential_shape",
    "seeded_identifier",
)
PATH_CATEGORIES = (
    "credential_filename",
    "transcript_or_session",
    "event_ledger",
)
ALL_CATEGORIES = CONTENT_CATEGORIES + PATH_CATEGORIES

CREDENTIAL_BASENAMES = {
    "accounts.json",
    "credentials.json",
    "credentials.csv",
    "secrets.json",
    "auth.json",
    ".env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_ed25519",
    "id_dsa",
    "id_ecdsa",
    "application_default_credentials.json",
    "service-account.json",
    "gcloud-service-account.json",
}
CREDENTIAL_SUFFIXES = (
    ".credentials.json",
    ".pem",
    ".p12",
    ".pfx",
    ".p8",
)
SKIP_CONTENT_BASENAMES = CREDENTIAL_BASENAMES | {".env.local", ".env.example"}

SEED_PARTS = ("RES0124", "SEEDED", "IDENTIFIER", "CONTROL")


def seed_prefix() -> str:
    return "-".join(SEED_PARTS)


def seed_token(nonce: str) -> str:
    return seed_prefix() + "-" + nonce


def posix(rel: str) -> str:
    return str(rel).replace("\\", "/").lstrip("./")


def _win_re() -> re.Pattern[str]:
    drive = r"C:"
    sep = r"[/\\]+"
    users = "Users"
    name = r"[A-Za-z_][A-Za-z0-9._-]{1,63}"
    return re.compile(drive + sep + users + sep + name, re.IGNORECASE)


def _unix_re() -> re.Pattern[str]:
    # Preceding colon excluded so a Windows drive path is not also unix.
    name = r"[A-Za-z_][A-Za-z0-9._-]{1,63}"
    return re.compile(r"(?:^|[^A-Za-z0-9:])(?:/home|/Users)/" + name)


def _email_re() -> re.Pattern[str]:
    return re.compile(
        r"\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,24}\b"
    )


def _cred_re() -> re.Pattern[str]:
    return re.compile(
        r"(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}"
        r"|sk-[A-Za-z0-9]{20,})"
    )


def _seed_re() -> re.Pattern[str]:
    return re.compile(re.escape(seed_prefix()) + r"-[0-9a-f]{6,32}")


WIN_RE = _win_re()
UNIX_RE = _unix_re()
EMAIL_RE = _email_re()
CRED_RE = _cred_re()
SEED_RE = _seed_re()

def _win_byte_prefixes() -> tuple[bytes, ...]:
    drive = "C:"
    users = "Users"
    return (
        (drive + "/" + users + "/").encode("ascii"),
        (drive + "\\" + users + "\\").encode("ascii"),
        (drive + "\\\\" + users + "\\\\").encode("ascii"),
    )


WIN_BYTE_PREFIXES = _win_byte_prefixes()


def iter_files(root: Path) -> list[Path]:
    out: list[Path] = []
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            out.append(path)
    out.sort()
    return out


def rel_of(path: Path, root: Path) -> str:
    try:
        return posix(path.resolve().relative_to(root.resolve()).as_posix())
    except ValueError:
        return posix(str(path))


def path_category(rel: str) -> str | None:
    path = posix(rel)
    name = Path(path).name
    lower = name.lower()
    parts = path.lower().split("/")
    if lower in CREDENTIAL_BASENAMES or lower.startswith(".env"):
        return "credential_filename"
    if any(lower.endswith(suf) for suf in CREDENTIAL_SUFFIXES):
        return "credential_filename"
    if any(p in {"transcripts", "transcript", "agent-transcripts"} for p in parts):
        return "transcript_or_session"
    if "transcript" in lower or "agent-transcript" in lower:
        return "transcript_or_session"
    if "session-" in lower and lower.endswith((".txt", ".json", ".jsonl", ".md")):
        return "transcript_or_session"
    if "ledger" in lower or "event-log" in lower or lower.endswith("events.jsonl"):
        return "event_ledger"
    return None


def _exclusive_hits(text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> list[dict]:
    occupied: list[tuple[int, int]] = []
    hits: list[dict] = []
    for category, cre in patterns:
        for m in cre.finditer(text):
            start, end = m.span()
            if any(start < oend and end > ostart for ostart, oend in occupied):
                continue
            occupied.append((start, end))
            line = text.count("\n", 0, start) + 1
            hits.append(
                {
                    "category": category,
                    "line": line,
                    "span_len": end - start,
                    "kind": "content",
                }
            )
    return hits


def scan_text(text: str) -> list[dict]:
    return _exclusive_hits(
        text,
        [
            ("windows_home_path", WIN_RE),
            ("unix_home_path", UNIX_RE),
            ("email", EMAIL_RE),
            ("credential_shape", CRED_RE),
            ("seeded_identifier", SEED_RE),
        ],
    )


def byte_prefix_count(raw: bytes) -> int:
    n = 0
    for prefix in WIN_BYTE_PREFIXES:
        start = 0
        while True:
            idx = raw.find(prefix, start)
            if idx < 0:
                break
            n += 1
            start = idx + len(prefix)
    return n


def _read_text(path: Path) -> tuple[bytes | None, str | None]:
    try:
        size = path.stat().st_size
    except OSError:
        return None, None
    if size > MAX_FILE_BYTES:
        return None, None
    try:
        raw = path.read_bytes()
    except OSError:
        return None, None
    if b"\x00" in raw[:1024]:
        return raw, None
    text = raw.decode("utf-8", errors="replace")
    return raw, text


def scan_file(path: Path, root: Path) -> dict:
    rel = rel_of(path, root)
    pcat = path_category(rel)
    row = {
        "path": rel,
        "path_category": pcat,
        "content_hits": [],
        "byte_prefix_hits": 0,
        "content_scanned": False,
    }
    if pcat == "credential_filename" or Path(rel).name.lower() in SKIP_CONTENT_BASENAMES:
        return row
    raw, text = _read_text(path)
    if raw is None or text is None:
        return row
    row["content_scanned"] = True
    hits = scan_text(text)
    for h in hits:
        h["path"] = rel
    row["content_hits"] = hits
    row["byte_prefix_hits"] = byte_prefix_count(raw)
    return row


def _empty_counts() -> dict[str, int]:
    return {c: 0 for c in ALL_CATEGORIES}


def summarize(file_rows: list[dict], extra_path_rows: list[dict] | None = None) -> dict:
    rows = list(file_rows)
    if extra_path_rows:
        rows.extend(extra_path_rows)
    by_cat = _empty_counts()
    files_by_cat: dict[str, Counter[str]] = {c: Counter() for c in ALL_CATEGORIES}
    byte_total = 0
    content_files = 0
    path_files = 0
    locations: dict[str, list[dict]] = {c: [] for c in ALL_CATEGORIES}
    for row in rows:
        pcat = row.get("path_category")
        if pcat:
            by_cat[pcat] += 1
            files_by_cat[pcat][row["path"]] += 1
            path_files += 1
            if len(locations[pcat]) < TOP_FILES:
                locations[pcat].append({"path": row["path"], "line": 0, "kind": "path"})
        if row.get("content_scanned"):
            content_files += 1
        byte_total += int(row.get("byte_prefix_hits") or 0)
        for h in row.get("content_hits") or []:
            cat = h["category"]
            by_cat[cat] += 1
            files_by_cat[cat][h["path"]] += 1
            if len(locations[cat]) < TOP_FILES:
                locations[cat].append(
                    {
                        "path": h["path"],
                        "line": h["line"],
                        "kind": "content",
                        "span_len": h["span_len"],
                    }
                )
    grand = sum(by_cat.values())
    top_files = {
        cat: [
            {"path": p, "count": n, "value_reproduced": False}
            for p, n in files_by_cat[cat].most_common(TOP_FILES)
        ]
        for cat in ALL_CATEGORIES
    }
    return {
        "by_category": by_cat,
        "grand_total": grand,
        "sum_check_ok": grand == sum(by_cat.values()),
        "content_files_scanned": content_files,
        "path_classified_files": path_files,
        "byte_prefix_hits": byte_total,
        "top_files": top_files,
        "locations": locations,
        "files_walked": len(file_rows),
    }


def tree_snapshot(root: Path, files: list[Path]) -> str:
    h = hashlib.sha256()
    for path in files:
        rel = rel_of(path, root).encode("utf-8")
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        h.update(rel)
        h.update(b"\0")
        h.update(str(size).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def scan_tree(root: Path | None = None, extra_files: list[Path] | None = None) -> dict:
    root = (root or REPO).resolve()
    files = iter_files(root)
    extra_rows: list[dict] = []
    seen = {p.resolve() for p in files}
    for extra in extra_files or []:
        extra = extra.resolve()
        if extra.is_file() and extra not in seen:
            extra_rows.append(scan_file(extra, root))
    rows = [scan_file(p, root) for p in files]
    summary = summarize(rows, extra_rows)
    summary["root"] = posix(str(root))
    summary["snapshot_sha256"] = tree_snapshot(root, files)
    summary["value_reproduced"] = False
    return summary


def counts_match(a: dict, b: dict) -> bool:
    return dict(a.get("by_category") or {}) == dict(b.get("by_category") or {})


def artifact_payload(doc: dict) -> dict:
    """Domain payload: extensions first (schema envelope), else top-level."""
    if not isinstance(doc, dict):
        return {}
    ext = doc.get("extensions")
    if isinstance(ext, dict) and isinstance(ext.get("category_counts"), dict):
        return ext
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("category_counts"), dict):
        return report
    return doc
