#!/usr/bin/env python3
"""CNF-0019 three-route byte measurement and gate harness.

Builds a disposable git fixture (never the worktree). `eol=crlf` makes
`git archive` emit CRLF so the documented Windows conversion is visible
on this Linux box. Formatting / lint / hash gates stand in for the CI
classes named by the catalog; `.github` workflows are absent here.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "CNF-0019"
CONTROL_REL = "control.py"
GIT_IDENT = ["-c", "user.name=CNF-0019", "-c", "user.email=cnf-0019@local"]
WRONG_PHRASE = re.compile(r"(?i)against the LF blob\s*\(\s*git archive\s*\)")
ARCHIVE_TOKEN = re.compile(r"(?i)git\s+archive")
NEGATED = re.compile(
    r"(?i)\b(do not|don't|never|not use|must not|forbid|forbidden|"
    r"wrong recipe|returns CRLF|do not verify)\b"
)
VERIFY_VERB = re.compile(r"(?i)\b(verify|run|use|prescribe|prescribed)\b")
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0019 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the three-route byte "
    "table is attached, the git archive route is shown to return CRLF, and "
    "every gate went red on the misformatted control. Any other terminal "
    "state is FAILED:CNF-0019 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "CI judges blobs, not your working tree, and the three ways of obtaining "
    "those bytes do not agree on this platform. Measure all three routes - "
    "git archive, git cat-file, and the worktree - for a control file, then "
    "re-run every formatting, linting and hash-sensitive gate on each route "
    "and answer: for how many gates does the verdict depend on which route "
    "supplied the bytes, and is the recipe currently prescribed in the "
    "release checklist the one that returns CRLF?"
)
GATES = ("format", "lint", "hash")
ROUTES = ("git archive", "git cat-file", "worktree")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def git(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {err[-500:]}")
    return proc.stdout


def control_source() -> str:
    lines = [
        '"""CNF-0019 control: blob stored LF; archive/worktree CRLF under eol=crlf."""',
        "",
        "VALUE = 1",
        "",
        "",
        "def add(a, b):",
        "    return a + b",
        "",
        "",
        "def main():",
        "    return add(VALUE, 1)",
        "",
    ]
    n = 1
    while len(lines) < 100:
        lines.append(f"# pad-{n:03d}")
        n += 1
    return "\n".join(lines) + "\n"


def misformatted_from_blob(blob: bytes) -> bytes:
    text = lf(blob).decode("utf-8")
    return (text.rstrip("\n") + "  \nBROKEN = {\n").encode("utf-8")


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(root), check=True)
    (root / ".gitattributes").write_text(
        f"{CONTROL_REL} text eol=crlf\n", encoding="utf-8", newline="\n"
    )
    (root / CONTROL_REL).write_bytes(control_source().encode("utf-8"))
    subprocess.run(
        ["git", *GIT_IDENT, "add", "-A"], cwd=str(root), check=True, capture_output=True
    )
    subprocess.run(
        ["git", *GIT_IDENT, "commit", "-q", "-m", "CNF-0019 control"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    (root / CONTROL_REL).unlink()
    subprocess.run(
        ["git", *GIT_IDENT, "checkout", "-q", "HEAD", "--", CONTROL_REL],
        cwd=str(root),
        check=True,
        capture_output=True,
    )


class ControlRepo:
    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="cnf0019-eol-"))
        _init_repo(self.root)

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "ControlRepo":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def read_archive(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    raw = git(repo, "archive", rev, "--", rel)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
        member = tf.extractfile(rel)
        if member is None:
            raise RuntimeError(f"archive missing {rel}")
        return member.read()


def read_cat_file(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    return git(repo, "cat-file", "-p", f"{rev}:{rel}")


def read_worktree(repo: Path, rel: str) -> bytes:
    return (repo / rel).read_bytes()


def three_routes(repo: Path, rel: str = CONTROL_REL) -> dict[str, bytes]:
    return {
        "git archive": read_archive(repo, rel),
        "git cat-file": read_cat_file(repo, rel),
        "worktree": read_worktree(repo, rel),
    }


def route_row(path: str, route: str, data: bytes) -> dict:
    return {
        "path": path,
        "route": route,
        "bytes": len(data),
        "crlf_count": data.count(b"\r\n"),
        "lf_count": data.count(b"\n"),
        "sha256": sha256_bytes(data),
        "sha256_lf": sha256_bytes(lf(data)),
    }


def gate_format(data: bytes) -> dict:
    reasons: list[str] = []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"gate": "format", "verdict": "RED", "reasons": ["not-utf8"]}
    if b"\r" in data:
        reasons.append("contains-CR")
    for i, line in enumerate(text.splitlines(), 1):
        if line != line.rstrip(" \t"):
            reasons.append(f"trailing-whitespace:L{i}")
            break
    try:
        ast.parse(lf(data).decode("utf-8"))
    except SyntaxError as exc:
        reasons.append(f"syntax:{exc.msg}")
    return {
        "gate": "format",
        "verdict": "RED" if reasons else "GREEN",
        "reasons": reasons,
    }


def gate_lint(data: bytes) -> dict:
    reasons: list[str] = []
    text = lf(data).decode("utf-8", "replace")
    if "BROKEN" in text:
        reasons.append("forbidden-token:BROKEN")
    if "\t" in text:
        reasons.append("tab")
    for i, line in enumerate(text.splitlines(), 1):
        if len(line) > 120:
            reasons.append(f"line-length:L{i}")
            break
    try:
        ast.parse(text)
    except SyntaxError as exc:
        reasons.append(f"syntax:{exc.msg}")
    return {
        "gate": "lint",
        "verdict": "RED" if reasons else "GREEN",
        "reasons": reasons,
    }


def gate_hash(data: bytes, blob_sha256: str) -> dict:
    got = sha256_bytes(data)
    match = got == blob_sha256
    return {
        "gate": "hash",
        "verdict": "GREEN" if match else "RED",
        "reasons": [] if match else ["sha256-mismatch"],
        "got_sha256": got,
        "want_sha256": blob_sha256,
    }


def run_gates(data: bytes, blob_sha256: str) -> dict[str, dict]:
    return {
        "format": gate_format(data),
        "lint": gate_lint(data),
        "hash": gate_hash(data, blob_sha256),
    }


def line_is_negated(line: str) -> bool:
    return bool(NEGATED.search(line))


def prescription_hits(text: str) -> list[dict]:
    hits: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        if WRONG_PHRASE.search(line) and not line_is_negated(line):
            hits.append(
                {
                    "line": i,
                    "kind": "prescription",
                    "text": line.strip(),
                    "rule": "against-the-LF-blob-(git-archive)",
                }
            )
            continue
        if ARCHIVE_TOKEN.search(line) and not line_is_negated(line):
            stripped = line.strip()
            if VERIFY_VERB.search(line) or stripped.startswith("git archive"):
                hits.append(
                    {
                        "line": i,
                        "kind": "prescription",
                        "text": stripped,
                        "rule": "git-archive-verification",
                    }
                )
    return hits


def corrected_checklist() -> str:
    return (
        "# Release checklist\n"
        "\n"
        "Byte-sensitive format, lint, and hash gates judge the **stored blob**,\n"
        "not the working tree and not `git archive` output.\n"
        "\n"
        "Obtain those bytes with:\n"
        "\n"
        "```\n"
        "git cat-file -p HEAD:path/to/file\n"
        "```\n"
        "\n"
        "Do not verify against `git archive`. On this platform `git archive`\n"
        "returns CRLF worktree form; `git cat-file -p` returns the LF blob CI\n"
        "judges. `rules/common/windows-shell.md` section 8b documents the trap\n"
        "and is a mention, not a prescription.\n"
        "\n"
        "CNF-0019 measured the three routes on a control with `eol=crlf`:\n"
        "archive and worktree emit CRLF; cat-file emits LF; all three match\n"
        "after LF normalisation.\n"
    )


def measure_once() -> dict:
    with ControlRepo() as repo:
        payloads = three_routes(repo.root)
        blob = payloads["git cat-file"]
        blob_sha = sha256_bytes(blob)
        table = [route_row(CONTROL_REL, name, payloads[name]) for name in ROUTES]
        norms = [lf(payloads[name]) for name in ROUTES]
        identical = bool(norms[0]) and all(n == norms[0] for n in norms)
        per_route = {name: run_gates(payloads[name], blob_sha) for name in ROUTES}
        broken = misformatted_from_blob(blob)
        broken_gates = run_gates(broken, blob_sha)
        route_dep = [
            gate
            for gate in GATES
            if len({per_route[r][gate]["verdict"] for r in ROUTES}) > 1
        ]
        pre_fix = (HERE / "fixtures" / "pre-fix-RELEASE-CHECKLIST.md").read_text(
            encoding="utf-8"
        )
        mention = (HERE / "fixtures" / "windows-shell-8b.md").read_text(
            encoding="utf-8"
        )
        live_path = REPO / "command-center" / "RELEASE-CHECKLIST.md"
        live_text = live_path.read_text(encoding="utf-8") if live_path.is_file() else ""
        return {
            "control_path": CONTROL_REL,
            "byte_table": table,
            "eol_normalisation": {
                "routes_identical_after_lf": identical,
                "method": "replace CRLF then CR with LF",
                "only_variable_is_line_endings": identical,
                "sha256_after_lf": sha256_bytes(norms[0]) if norms[0] else "",
            },
            "archive_returns_crlf": table[0]["crlf_count"] > 0,
            "blob_sha256": blob_sha,
            "blob_bytes": len(blob),
            "blob_crlf": blob.count(b"\r\n"),
            "gate_verdicts_by_route": per_route,
            "misformatted": {
                "bytes": len(broken),
                "crlf_count": broken.count(b"\r\n"),
                "sha256": sha256_bytes(broken),
                "gates": broken_gates,
                "all_red": all(broken_gates[g]["verdict"] == "RED" for g in GATES),
            },
            "route_dependent_gates": route_dep,
            "checklist": {
                "pre_fix_hits": prescription_hits(pre_fix),
                "mention_hits": prescription_hits(mention),
                "live_hits": prescription_hits(live_text) if live_text else [],
                "live_present": live_path.is_file(),
                "live_path": "command-center/RELEASE-CHECKLIST.md",
            },
        }


SCHEMA_REL = "command-center/schema/byte-parity-report.schema.json"


def payload(doc: dict) -> dict:
    """Unit fields live in report (receipt additionalProperties:false) or top-level."""
    rpt = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    return {**doc, **rpt}


def load_schema() -> dict:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def _disk_resolver(schema: dict):
    """Resolve ast-integrate.invalid $ref onto disk. Never the network."""
    import jsonschema

    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
        "https://ast-integrate.invalid/command-center/schema/byte-parity-report.schema.json": schema,
    }
    return jsonschema.RefResolver.from_schema(schema, store=store)


def _validator():
    import jsonschema

    schema = load_schema()
    return jsonschema.Draft7Validator(schema, resolver=_disk_resolver(schema))


def _payload_errors(doc: dict) -> list[str]:
    p = payload(doc) if isinstance(doc, dict) else {}
    errs: list[str] = []
    table = p.get("byte_table")
    if not isinstance(table, list) or len(table) < 3:
        errs.append("['byte_table']: three-route table missing")
    else:
        routes = {row.get("route") for row in table if isinstance(row, dict)}
        for name in ROUTES:
            if name not in routes:
                errs.append(f"['byte_table']: missing route {name}")
    answers = p.get("answers")
    if not isinstance(answers, dict):
        errs.append("['answers']: missing")
    else:
        for key in (
            "route_dependent_gate_count",
            "archive_returns_crlf",
            "live_checklist_prescribes_crlf_route",
            "pre_fix_checklist_prescribed_crlf_route",
        ):
            if key not in answers:
                errs.append(f"['answers']: missing {key}")
    broken = p.get("misformatted_control")
    if not isinstance(broken, dict) or "all_red" not in broken:
        errs.append("['misformatted_control']: missing all_red")
    eolm = p.get("eol_normalisation")
    if not isinstance(eolm, dict) or "routes_identical_after_lf" not in eolm:
        errs.append("['eol_normalisation']: missing routes_identical_after_lf")
    return errs


def validate_report(doc: dict) -> list[str]:
    errs: list[str] = []
    try:
        validator = _validator()
        errs.extend(
            f"{list(e.path)}: {e.message}"
            for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        )
    except Exception as exc:  # noqa: BLE001 — fail closed, never a silent pass
        errs.append(f"<resolver>: {type(exc).__name__}: {exc}")
    errs.extend(_payload_errors(doc if isinstance(doc, dict) else {}))
    return errs


def schema_rejects_garbage() -> bool:
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNF-0019", "state": "SUCCESS"},
    ]
    return all(validate_report(g) for g in garbage)
