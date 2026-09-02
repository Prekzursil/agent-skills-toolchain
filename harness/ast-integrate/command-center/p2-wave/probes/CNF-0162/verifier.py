"""Receipt-to-disk verifier: completion-predicate conditions 2, 3, 4, 12.

Catalog quote of spec:11634-11636, 11644 and 10646:
  2  the artifact exists on disk — a path string in text is not existence
  3  it exceeds a meaningful minimum size (named default, with rationale)
  4  it parses against its declared schema
  12 a declared downstream consumer can actually read it

The size floor is DEFAULT_MIN_BYTES. Production evaluation MUST call
check_size(path) with no min_bytes argument so the default is live.
A prior estate defect had every caller pass the value explicitly, so a
mutation of the default never reddened a test.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft7Validator

from consumer import ConsumerError, consume

DEFAULT_MIN_BYTES = 64
DEFAULT_MIN_BYTES_RATIONALE = (
    "A JSON object carrying unit_id, state, and sentinel is already tens of "
    "bytes. 64 bytes is the smallest floor that still rejects empty stubs, "
    "0-byte files, and 1-byte placeholders while remaining below every real "
    "catalog receipt. Callers that pass min_bytes explicitly do not exercise "
    "this default; production evaluate_receipt calls check_size(path) with "
    "no second argument."
)

CONDITIONS = ("2", "3", "4", "12")


def repo_root() -> Path:
    cur = Path(__file__).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return parent
    raise RuntimeError("cannot locate worktree root from CNF-0162/verifier.py")


REPO = repo_root()
RECEIPTS_DIR = REPO / "command-center" / "receipts"
CATALOG_PATH = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SELF_UNIT = "CNF-0162"


def check_size(path: Path, min_bytes: int | None = None) -> tuple[bool, int]:
    """Return (meets_floor, byte_count).

    When min_bytes is omitted the module default is read at call time, not
    bound at def time, so a mutation of DEFAULT_MIN_BYTES is observable.
    """
    floor = DEFAULT_MIN_BYTES if min_bytes is None else int(min_bytes)
    if not path.is_file():
        return False, 0
    n = path.stat().st_size
    return n >= floor, n


def load_catalog(path: Path | None = None) -> dict[str, dict]:
    target = path or CATALOG_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    rows = data.get("work_units") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return out
    for unit in rows:
        if isinstance(unit, dict) and isinstance(unit.get("id"), str):
            out[unit["id"]] = unit
    return out


def resolve_repo_path(rel: str, repo: Path | None = None) -> Path:
    root = repo or REPO
    text = str(rel or "").replace("\\", "/").strip()
    p = Path(text)
    if p.is_absolute():
        return p
    return root / text


def cited_artifact_paths(doc: Any) -> list[str]:
    """Paths named as artifacts or evidence. Not every slash-containing string."""
    found: list[str] = []

    def take(val: Any) -> None:
        if not isinstance(val, str):
            return
        text = val.replace("\\", "/").strip()
        if not text or text.startswith(("http://", "https://", "mailto:")):
            return
        found.append(text)

    if isinstance(doc, dict):
        arts = doc.get("artifacts")
        if isinstance(arts, list):
            for item in arts:
                if isinstance(item, dict):
                    take(item.get("path"))
        ev = doc.get("evidence")
        if isinstance(ev, list):
            for item in ev:
                if isinstance(item, dict):
                    take(item.get("path"))
    seen: set[str] = set()
    out: list[str] = []
    for p in found:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _schema_status(
    unit: dict | None,
    repo: Path,
    schema_override: dict | None,
    schema_path: str | None,
) -> tuple[dict | None, str, str]:
    if schema_override is not None:
        return schema_override, schema_path or "override", "ok"
    if not unit:
        return None, "", "catalog-missing"
    declared = str(unit.get("output_schema") or "").replace("\\", "/").strip()
    if not declared:
        return None, "", "schema-undeclared"
    if declared.startswith(("http://", "https://")):
        return None, declared, "schema-unresolvable"
    path = resolve_repo_path(declared, repo)
    if not path.is_file():
        return None, declared, "schema-unresolvable"
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
    except Exception:
        return None, declared, "schema-unresolvable"
    return schema, declared, "ok"


def parse_against_schema(
    path: Path, schema: dict | None, schema_status: str
) -> tuple[str, dict | None, list[str]]:
    if not path.is_file():
        return "not-run", None, ["file missing"]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return "unparseable", None, [type(exc).__name__]
    if not isinstance(doc, dict):
        return "not-object", None, [type(doc).__name__]
    if schema_status != "ok" or schema is None:
        return schema_status or "schema-unresolvable", doc, [schema_status]
    errors = []
    for err in Draft7Validator(schema).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path)
        errors.append((loc + ": " if loc else "") + err.message)
        if len(errors) >= 8:
            break
    if errors:
        return "schema-invalid", doc, errors
    return "ok", doc, []


def consumer_read(path: Path) -> tuple[str, dict | None]:
    if not path.is_file():
        return "not-run", None
    try:
        got = consume(path)
    except ConsumerError as exc:
        return exc.code, None
    return "ok", got


def evaluate_receipt(
    path: Path,
    *,
    repo: Path | None = None,
    catalog: dict[str, dict] | None = None,
    schema_override: dict | None = None,
    schema_path: str | None = None,
) -> dict[str, Any]:
    """Evaluate one receipt path against conditions 2, 3, 4, 12.

    check_size is invoked with no min_bytes argument so DEFAULT_MIN_BYTES
    is the live floor. Do not add an explicit min_bytes here.
    """
    root = repo or REPO
    catalog = catalog if catalog is not None else {}
    rel = path.as_posix()
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()

    exists = path.is_file()
    size_ok, nbytes = check_size(path)

    unit_id = path.stem
    unit = catalog.get(unit_id)
    schema, declared_schema, schema_status = _schema_status(
        unit, root, schema_override, schema_path
    )
    parse_result, doc, parse_errors = parse_against_schema(path, schema, schema_status)
    consumer_result, consumed = consumer_read(path)

    cited_rows: list[dict[str, Any]] = []
    cited_missing: list[str] = []
    cited_undersize: list[str] = []
    if isinstance(doc, dict):
        for cited in cited_artifact_paths(doc):
            cpath = resolve_repo_path(cited, root)
            c_ok, c_bytes = check_size(cpath)
            c_exists = cpath.is_file()
            claimed = None
            arts = doc.get("artifacts")
            if isinstance(arts, list):
                for item in arts:
                    if not isinstance(item, dict):
                        continue
                    item_path = str(item.get("path") or "").replace("\\", "/")
                    if item_path == cited and "exists" in item:
                        claimed = item.get("exists")
                        break
            cited_rows.append(
                {
                    "path": cited,
                    "exists": c_exists,
                    "bytes": c_bytes,
                    "size_ok": c_ok,
                    "claimed_exists": claimed,
                    "claimed_exists_trusted": False,
                }
            )
            if not c_exists:
                cited_missing.append(cited)
            elif not c_ok:
                cited_undersize.append(cited)

    c2_pass = exists and not cited_missing
    c3_pass = bool(exists and size_ok and not cited_undersize)
    c4_pass = parse_result == "ok"
    c12_pass = consumer_result == "ok"
    verdict = "PASS" if (c2_pass and c3_pass and c4_pass and c12_pass) else "FAIL"

    return {
        "path": rel,
        "unit_id": unit_id,
        "exists": exists,
        "bytes": nbytes,
        "parse_result": parse_result,
        "parse_errors": parse_errors,
        "consumer_read_result": consumer_result,
        "consumer_extracted": None if consumed is None else consumed.get("extracted"),
        "schema_path": declared_schema,
        "schema_status": schema_status,
        "cited_artifacts": cited_rows,
        "conditions": {
            "2": {
                "pass": c2_pass,
                "detail": (
                    "missing-receipt"
                    if not exists
                    else (
                        "cited-missing:" + ",".join(cited_missing)
                        if cited_missing
                        else "exists-on-disk"
                    )
                ),
            },
            "3": {
                "pass": c3_pass,
                "detail": (
                    f"bytes={nbytes} floor={DEFAULT_MIN_BYTES}"
                    + (
                        f" cited-undersize:{','.join(cited_undersize)}"
                        if cited_undersize
                        else ""
                    )
                ),
            },
            "4": {
                "pass": c4_pass,
                "detail": parse_result
                + (f" {parse_errors[0]}" if parse_errors else ""),
            },
            "12": {
                "pass": c12_pass,
                "detail": consumer_result,
            },
        },
        "verdict": verdict,
    }


def as_public_row(row: dict[str, Any]) -> dict[str, Any]:
    """Per-receipt evidence row: path, exists, bytes, parse, consumer-read."""
    return {
        "path": row["path"],
        "exists": row["exists"],
        "bytes": row["bytes"],
        "parse_result": row["parse_result"],
        "consumer_read_result": row["consumer_read_result"],
        "verdict": row["verdict"],
        "conditions": row["conditions"],
        "cited_artifacts": row.get("cited_artifacts") or [],
        "schema_path": row.get("schema_path") or "",
        "schema_status": row.get("schema_status") or "",
        "unit_id": row.get("unit_id") or "",
    }


def iter_receipt_paths(root: Path | None = None) -> list[Path]:
    base = root or RECEIPTS_DIR
    if not base.is_dir():
        return []
    return sorted(p for p in base.glob("*.json") if p.is_file())


def evaluate_corpus(
    paths: Iterable[Path] | None = None,
    *,
    repo: Path | None = None,
    catalog: dict[str, dict] | None = None,
    exclude_unit_ids: Iterable[str] = (),
    schema_override: dict | None = None,
    schema_path: str | None = None,
) -> list[dict[str, Any]]:
    root = repo or REPO
    skip = {s.strip() for s in exclude_unit_ids if s}
    cat = catalog if catalog is not None else load_catalog()
    files = list(paths) if paths is not None else iter_receipt_paths()
    rows = []
    for path in files:
        if path.stem in skip:
            continue
        rows.append(
            evaluate_receipt(
                path,
                repo=root,
                catalog=cat,
                schema_override=schema_override,
                schema_path=schema_path,
            )
        )
    return rows
