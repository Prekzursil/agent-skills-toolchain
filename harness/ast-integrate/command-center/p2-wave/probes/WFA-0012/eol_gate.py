#!/usr/bin/env python3
"""WFA hash-portability gate: committed blob via git cat-file -p, never git archive.

On a Windows checkout (text eol=crlf) the working tree and `git archive`
yield CRLF. CI hashes the stored LF blob. Hashing worktree or archive bytes
therefore goes red locally and green in CI on the same commit (the REACH-6
class named on validate.py). This module is the WFA gate recipe:

  * content_bytes / hash_gate read `git cat-file -p <rev>:<path>` (or git show)
  * untracked / non-git trees LF-normalise before hashing
  * git archive is measurement-only and is never on the gate path
"""
from __future__ import annotations

import ast
import hashlib
import io
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0012"
PAYLOAD_REL = "payload.txt"
NOTES_REL = "notes.md"
KNOWN_PAYLOAD_LINES = 32
KNOWN_NOTES_LINES = 12
GIT_IDENT = ["-c", "user.name=WFA-0012", "-c", "user.email=wfa-0012@local"]
GATE_FUNCS = frozenset(
    {"cat_file", "git_show", "content_bytes", "content_read", "hash_gate"}
)


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
    )
    if check and proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {err[-500:]}")
    return proc


def cat_file(repo: Path, rel: str, rev: str = "HEAD") -> bytes | None:
    """Committed blob. Never git archive."""
    proc = git(repo, "cat-file", "-p", f"{rev}:{rel}", check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_show(repo: Path, rel: str, rev: str = "HEAD") -> bytes | None:
    proc = git(repo, "show", f"{rev}:{rel}", check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def archive_bytes_for_measurement_only(
    repo: Path, rel: str, rev: str = "HEAD"
) -> bytes:
    """Trap route only. Do not use this for any content-dependent gate."""
    raw = git(repo, "archive", rev, "--", rel).stdout
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
        member = tf.extractfile(rel)
        if member is None:
            raise RuntimeError(f"git archive missing {rel}")
        return member.read()


def worktree_bytes(repo: Path, rel: str) -> bytes:
    return (repo / rel).read_bytes()


def _discover_repo(start: Path) -> Path | None:
    cur = start if start.is_dir() else start.parent
    try:
        cur = cur.resolve()
    except OSError:
        return None
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists():
            proc = git(candidate, "rev-parse", "--is-inside-work-tree", check=False)
            if proc.returncode == 0 and proc.stdout.strip() == b"true":
                return candidate
    return None


def content_read(
    path: Path, repo: Path | None = None, rev: str = "HEAD"
) -> tuple[bytes, str]:
    path = Path(path)
    repo = repo or _discover_repo(path)
    if repo is not None:
        try:
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = None
        if rel:
            blob = cat_file(repo, rel, rev)
            if blob is not None:
                return blob, "git cat-file"
    return lf(path.read_bytes()), "worktree-lf-normalised"


def content_bytes(path: Path, repo: Path | None = None, rev: str = "HEAD") -> bytes:
    """Bytes a WFA content-dependent gate must hash. Never git archive."""
    data, _route = content_read(path, repo=repo, rev=rev)
    return data


def hash_gate(observed: bytes, expected_sha: str) -> dict:
    got = sha256_hex(observed)
    return {
        "gate": "hash",
        "verdict": "GREEN" if got == expected_sha else "RED",
        "got_sha256": got,
        "expected_sha256": expected_sha,
    }


def line_count(data: bytes) -> int:
    return lf(data).count(b"\n")


def classify_eol_delta(worktree: bytes, blob: bytes) -> dict:
    """Signal B: CRLF/LF size difference vs line count.

    Pure EOL conversion of an LF blob into CRLF adds exactly one byte per
    newline. That equality is not sufficient on its own: a same-length
    content substitution can keep delta == line_count. LF-normalised
    identity is the second, independent check so a real defect is not
    dismissed as newline noise.
    """
    blob_lf = lf(blob)
    tree_lf = lf(worktree)
    n_lines = blob_lf.count(b"\n")
    delta = len(worktree) - len(blob)
    lf_equal = tree_lf == blob_lf
    delta_equals_lines = delta == n_lines
    if lf_equal and delta_equals_lines:
        kind = "EOL-ARTIFACT"
    elif lf_equal and delta == 0:
        kind = "BYTE-IDENTICAL"
    else:
        kind = "CONTENT-DIFFERENCE"
    return {
        "blob_bytes": len(blob),
        "worktree_bytes": len(worktree),
        "delta_bytes": delta,
        "line_count": n_lines,
        "crlf_count": worktree.count(b"\r\n"),
        "delta_equals_line_count": delta_equals_lines,
        "lf_bytes_equal": lf_equal,
        "class": kind,
    }


def payload_source(n: int = KNOWN_PAYLOAD_LINES) -> str:
    lines = [f"WFA-0012 payload line {i:03d} hash-gate-control" for i in range(1, n + 1)]
    return "\n".join(lines) + "\n"


def notes_source(n: int = KNOWN_NOTES_LINES) -> str:
    lines = [f"notes paragraph {i:02d} — WFA-0012 eol arithmetic" for i in range(1, n + 1)]
    return "\n".join(lines) + "\n"


def mutate_one_content_byte(data: bytes) -> bytes:
    """Same-length substitution; preserves CRLF vs LF shape."""
    crlf = b"\r\n" in data
    body = lf(data)
    needle = b"payload"
    if needle not in body:
        needle = b"paragraph"
    if needle not in body:
        raise RuntimeError("mutate_one_content_byte: no substitution site")
    mutated = body.replace(needle, needle[:-1] + b"X", 1)
    if mutated == body:
        raise RuntimeError("mutate_one_content_byte: substitution was a no-op")
    return mutated.replace(b"\n", b"\r\n") if crlf else mutated


def _init_fixture(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(root), check=True)
    (root / ".gitattributes").write_text(
        f"{PAYLOAD_REL} text eol=crlf\n{NOTES_REL} text eol=crlf\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / PAYLOAD_REL).write_text(payload_source(), encoding="utf-8", newline="\n")
    (root / NOTES_REL).write_text(notes_source(), encoding="utf-8", newline="\n")
    subprocess.run(
        ["git", *GIT_IDENT, "add", "-A"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *GIT_IDENT, "commit", "-q", "-m", "WFA-0012 eol fixture"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    (root / PAYLOAD_REL).unlink()
    (root / NOTES_REL).unlink()
    subprocess.run(
        ["git", *GIT_IDENT, "checkout", "-q", "HEAD", "--", PAYLOAD_REL, NOTES_REL],
        cwd=str(root),
        check=True,
        capture_output=True,
    )


class EolFixture:
    """Disposable git repo: payload/notes convert; blobs stay LF."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="wfa0012-eol-"))
        _init_fixture(self.root)

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "EolFixture":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def route_row(path: str, route: str, data: bytes) -> dict:
    return {
        "path": path,
        "route": route,
        "bytes": len(data),
        "crlf_count": data.count(b"\r\n"),
        "lf_count": data.count(b"\n"),
        "line_count": line_count(data),
        "sha256": sha256_hex(data),
        "sha256_lf": sha256_hex(lf(data)),
    }


def three_routes(repo: Path, rel: str) -> dict[str, bytes]:
    return {
        "git archive": archive_bytes_for_measurement_only(repo, rel),
        "git cat-file": cat_file(repo, rel) or b"",
        "git show": git_show(repo, rel) or b"",
        "worktree": worktree_bytes(repo, rel),
    }


def materialise_lf_checkout(repo: Path, dest: Path, rels: list[str]) -> None:
    """Write committed blobs (LF) into dest — Linux-CI form of the same commit."""
    dest.mkdir(parents=True, exist_ok=True)
    for rel in rels:
        blob = cat_file(repo, rel)
        if blob is None:
            raise RuntimeError(f"lf checkout missing blob {rel}")
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)


def inspect_gate_source(src: str | None = None) -> dict:
    text = src if src is not None else Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    by_name = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    missing = sorted(GATE_FUNCS - set(by_name))
    archive_in_gate: list[str] = []
    for name in sorted(GATE_FUNCS):
        fn = by_name.get(name)
        if fn is None:
            continue
        for child in ast.walk(fn):
            if isinstance(child, ast.Call) and "archive" in ast.dump(child).lower():
                archive_in_gate.append(name)
                break
    cat_fn = by_name.get("cat_file")
    cat_dump = ast.dump(cat_fn).lower() if cat_fn is not None else ""
    show_fn = by_name.get("git_show")
    show_dump = ast.dump(show_fn).lower() if show_fn is not None else ""
    meas = by_name.get("archive_bytes_for_measurement_only")
    meas_has_archive = False
    if meas is not None:
        for child in ast.walk(meas):
            if isinstance(child, ast.Call) and "archive" in ast.dump(child).lower():
                meas_has_archive = True
                break
    dash_p = "-p" in cat_dump
    return {
        "source": "command-center/p2-wave/probes/WFA-0012/eol_gate.py",
        "gate_funcs": sorted(GATE_FUNCS),
        "missing_gate_funcs": missing,
        "archive_call_in_gate_funcs": archive_in_gate,
        "cat_file_uses_cat_file_dash_p": "cat-file" in cat_dump and dash_p,
        "git_show_uses_show": "show" in show_dump,
        "archive_confined_to_measurement": meas_has_archive and not archive_in_gate,
        "pass": (
            not missing
            and not archive_in_gate
            and "cat-file" in cat_dump
            and dash_p
            and "show" in show_dump
            and meas_has_archive
        ),
    }


def _source_lf_normalises(text: str) -> bool:
    return (
        'replace(b"\\r\\n", b"\\n")' in text
        or "replace(b'\\r\\n', b'\\n')" in text
        or "LF-NORMALISE BEFORE HASHING" in text
        or "lf_normalised" in text
    )


def inspect_validate_reach6() -> dict:
    """REACH-6 is the named defect class, not a rebuild target.

    Catalog question_or_target allows either `git cat-file -p` / blobread or
    LF-normalise-before-hash. Live validate.py uses the second: it hashes
    `snapshot.read_bytes().replace(b"\\r\\n", b"\\n")` and never git archive.
    """
    path = REPO / "tools" / "command-center" / "validate.py"
    present = path.is_file()
    text = path.read_text(encoding="utf-8") if present else ""
    uses_blobread = "blobread.content_bytes" in text
    uses_cat_file = "cat-file" in text and "-p" in text
    lf_norm = _source_lf_normalises(text)
    mentions_reach6 = "REACH-6" in text
    never_archive = "never git archive" in text.lower()
    archive_for_hash = "git archive" in text.lower() and "never" not in text.lower()
    catalog_allowed = (uses_blobread or uses_cat_file or lf_norm) and not archive_for_hash
    return {
        "path": "tools/command-center/validate.py",
        "present": present,
        "uses_blobread_content_bytes": uses_blobread,
        "uses_git_cat_file": uses_cat_file,
        "lf_normalises_before_hash": lf_norm,
        "mentions_reach6": mentions_reach6,
        "never_git_archive_documented": never_archive,
        "prescribes_git_archive": archive_for_hash,
        "catalog_allowed_recipe": catalog_allowed,
        "pass": present and mentions_reach6 and catalog_allowed,
    }


def scan_wfa_receipt_hashers() -> list[dict]:
    """Census of sibling WFA write_receipts.py hash recipes.

    SUCCESS for THIS unit gates only WFA-0012's own writer. A sibling that
    hashes via a helper (so the replace() is not in write_receipts.py) is
    reported, not used to fail WFA-0012.
    """
    probes = HERE.parent
    rows: list[dict] = []
    for path in sorted(probes.glob("WFA-*/write_receipts.py")):
        text = path.read_text(encoding="utf-8")
        lf_norm = _source_lf_normalises(text)
        uses_archive = "git archive" in text.lower() and "never" not in text.lower()
        rel = path.relative_to(REPO).as_posix()
        rows.append(
            {
                "path": rel,
                "lf_normalises_before_hash": lf_norm,
                "prescribes_git_archive": uses_archive,
                "allowed_recipe": lf_norm and not uses_archive,
                "this_unit": rel.endswith("/WFA-0012/write_receipts.py"),
            }
        )
    return rows


def worktree_inputs() -> dict:
    gitattributes = REPO / ".gitattributes"
    windows_shell = REPO / "rules" / "common" / "windows-shell.md"
    schema_pack = REPO / "command-center" / "wfa" / "schema" / "wfa-schema-pack.json"
    git_dir = REPO / ".git"
    fixture_8b = HERE / "fixtures" / "windows-shell-8b.md"
    validate = REPO / "tools" / "command-center" / "validate.py"
    return {
        "repo_is_git_checkout": git_dir.exists(),
        "gitattributes": {
            "path": ".gitattributes",
            "present": gitattributes.is_file(),
        },
        "windows_shell_8b": {
            "catalog_path": "rules/common/windows-shell.md",
            "present": windows_shell.is_file(),
            "fixture_path": (
                fixture_8b.relative_to(REPO).as_posix() if fixture_8b.is_file() else None
            ),
            "fixture_present": fixture_8b.is_file(),
        },
        "wfa_schema_pack": {
            "path": "command-center/wfa/schema/wfa-schema-pack.json",
            "present": schema_pack.is_file(),
        },
        "validate_py": {
            "path": "tools/command-center/validate.py",
            "present": validate.is_file(),
        },
    }


def measure_fixture(fix: EolFixture) -> dict:
    repo = fix.root
    rels = [PAYLOAD_REL, NOTES_REL]
    tables: dict[str, list[dict]] = {}
    routes_by_rel: dict[str, dict[str, bytes]] = {}
    for rel in rels:
        payloads = three_routes(repo, rel)
        routes_by_rel[rel] = payloads
        tables[rel] = [
            route_row(rel, name, payloads[name])
            for name in ("git archive", "git cat-file", "git show", "worktree")
        ]

    payload_routes = routes_by_rel[PAYLOAD_REL]
    blob = payload_routes["git cat-file"]
    expected = sha256_hex(blob)
    worktree = payload_routes["worktree"]
    archive = payload_routes["git archive"]
    shown = payload_routes["git show"]

    gated, route = content_read(repo / PAYLOAD_REL, repo=repo)
    ci = hash_gate(blob, expected)
    portable = hash_gate(gated, expected)
    naive = hash_gate(worktree, expected)
    lf_copy_gate = hash_gate(lf(worktree), expected)
    archive_gate = hash_gate(archive, expected)

    lf_dest = Path(tempfile.mkdtemp(prefix="wfa0012-lf-checkout-"))
    try:
        materialise_lf_checkout(repo, lf_dest, rels)
        lf_checkout_bytes = (lf_dest / PAYLOAD_REL).read_bytes()
        lf_checkout_gate = hash_gate(lf(lf_checkout_bytes), expected)
        lf_checkout_is_blob = lf_checkout_bytes == blob
    finally:
        shutil.rmtree(lf_dest, ignore_errors=True)

    mutant_wt = mutate_one_content_byte(worktree)
    mutant_lf_gate = hash_gate(lf(mutant_wt), expected)
    mutant_naive = hash_gate(mutant_wt, expected)

    eol_delta = classify_eol_delta(worktree, blob)
    notes_delta = classify_eol_delta(
        routes_by_rel[NOTES_REL]["worktree"],
        routes_by_rel[NOTES_REL]["git cat-file"],
    )
    mutant_delta = classify_eol_delta(mutant_wt, blob)

    payload_norms = [
        lf(payload_routes[name])
        for name in ("git archive", "git cat-file", "worktree")
    ]
    identical_after_lf = bool(payload_norms[0]) and all(
        n == payload_norms[0] for n in payload_norms
    )

    inspection = inspect_gate_source()
    reach6 = inspect_validate_reach6()
    receipts = scan_wfa_receipt_hashers()

    signal_a_identical = (
        portable["verdict"] == ci["verdict"] == lf_copy_gate["verdict"] == "GREEN"
    )
    both_states_armed = (
        portable["verdict"] == "GREEN"
        and lf_copy_gate["verdict"] == "GREEN"
        and mutant_lf_gate["verdict"] == "RED"
        and ci["verdict"] == "GREEN"
    )

    return {
        "control_paths": rels,
        "known_payload_lines": KNOWN_PAYLOAD_LINES,
        "known_notes_lines": KNOWN_NOTES_LINES,
        "byte_tables": tables,
        "eol_normalisation": {
            "routes_identical_after_lf": identical_after_lf,
            "method": "replace CRLF then CR with LF",
            "sha256_after_lf": sha256_hex(payload_norms[0]) if payload_norms[0] else "",
        },
        "cat_file_equals_git_show": blob == shown,
        "archive_returns_crlf": archive.count(b"\r\n") > 0,
        "blob_crlf": blob.count(b"\r\n"),
        "worktree_crlf": worktree.count(b"\r\n"),
        "content_bytes_route": route,
        "gates": {
            "hash_ci_blob": ci,
            "hash_portable_cat_file": portable,
            "hash_naive_worktree": naive,
            "hash_lf_copy": lf_copy_gate,
            "hash_archive": archive_gate,
            "hash_lf_checkout": lf_checkout_gate,
            "hash_one_byte_mutant_lf_norm": mutant_lf_gate,
            "hash_one_byte_mutant_naive": mutant_naive,
        },
        "signal_a": {
            "method": (
                "same commit: hash_gate(git cat-file -p) on the Windows-like "
                "eol=crlf worktree versus hash_gate(LF-normalised copy) versus "
                "the CI blob digest"
            ),
            "windows_worktree_portable_verdict": portable["verdict"],
            "lf_copy_verdict": lf_copy_gate["verdict"],
            "ci_blob_verdict": ci["verdict"],
            "naive_worktree_verdict": naive["verdict"],
            "archive_verdict": archive_gate["verdict"],
            "identical_portable_and_ci": signal_a_identical,
            "naive_differs_from_ci": naive["verdict"] != ci["verdict"],
        },
        "signal_b": {
            "method": (
                "delta_bytes = len(CRLF worktree) - len(LF blob); for a pure "
                "EOL conversion this equals line_count. LF-normalised identity "
                "is required so a same-length content substitution is not "
                "classed as newline noise."
            ),
            "payload": {"path": PAYLOAD_REL, **eol_delta},
            "notes": {"path": NOTES_REL, **notes_delta},
            "same_length_content_substitution": {
                "path": PAYLOAD_REL,
                **mutant_delta,
                "note": (
                    "One-byte letter swap keeps length; delta may still equal "
                    "line_count, but lf_bytes_equal is false so class is "
                    "CONTENT-DIFFERENCE and the portable LF-norm gate is RED."
                ),
            },
            "pure_eol_delta_equals_line_count": (
                eol_delta["class"] == "EOL-ARTIFACT"
                and eol_delta["delta_equals_line_count"]
                and notes_delta["class"] == "EOL-ARTIFACT"
                and notes_delta["delta_equals_line_count"]
            ),
        },
        "both_states": {
            "eol_only_portable_green": portable["verdict"] == "GREEN"
            and lf_copy_gate["verdict"] == "GREEN",
            "one_byte_content_change_still_red": mutant_lf_gate["verdict"] == "RED",
            "portability_fix_did_not_disarm": both_states_armed,
            "naive_worktree_red_on_eol_only": naive["verdict"] == "RED",
        },
        "lf_checkout": {
            "method": (
                "materialise git cat-file -p blobs into a fresh directory "
                "(Linux CI working tree of the same commit)"
            ),
            "bytes_equal_blob": lf_checkout_is_blob,
            "verdict": lf_checkout_gate["verdict"],
            "matches_ci": lf_checkout_gate["verdict"] == ci["verdict"] == "GREEN",
        },
        "inspection": inspection,
        "validate_reach6": reach6,
        "wfa_receipt_hashers": receipts,
        "parity": {
            "local_portable_matches_ci": portable["verdict"] == ci["verdict"] == "GREEN",
            "naive_worktree_differs_from_ci": naive["verdict"] != ci["verdict"],
        },
    }


def live_measure() -> dict:
    with EolFixture() as fix:
        return measure_fixture(fix)
