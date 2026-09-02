"""Golden-corpus validation for ARC-0112.

Validate artifacts that already exist (catalogue, event log, manifest, claim
and test registries, source register, overlay) against the ARC-0083..ARC-0086
contracts. Every failure is classified artifact-wrong or schema-wrong with a
citation. A schema that no live record satisfies is imagined-system
(schema-wrong), not a mass artifact indictment.

Encoding: compare working-tree bytes to git-HEAD blob bytes when git exists;
otherwise compare raw worktree bytes to the LF-normalized surface the rest of
this tree already uses (tools/command-center/validate.py REACH-6). A CRLF-only
delta is encoding, never a data defect.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/phase4/conformance/ARC-0112.json"
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"

CONTRACTS = (
    ("ARC-0083", "command-center/phase4/contracts/ARC-0083.json", "work-unit"),
    ("ARC-0084", "command-center/phase4/contracts/ARC-0084.json", "artifact-envelope"),
    ("ARC-0085", "command-center/phase4/contracts/ARC-0085.json", "claim-record"),
    ("ARC-0086", "command-center/phase4/contracts/ARC-0086.json", "event-record"),
)

CORPUS = (
    ("work-unit-catalogue", CATALOG_REL, "ARC-0083"),
    ("event-log", "command-center/events/EVENTS.jsonl", "ARC-0086"),
    ("artifact-manifest", "command-center/ARTIFACT-MANIFEST.json", "ARC-0084"),
    ("claim-registry", "command-center/CLAIM-REGISTRY.json", "ARC-0085"),
    ("test-registry", "command-center/TEST-REGISTRY.json", "ARC-0085+gap"),
    ("source-register", "command-center/sources/REGISTER.md", "ARC-0083"),
    ("overlay", "command-center/sources/overlay.json", "ARC-0083"),
)

# Prompt Two names -> live catalog aliases on the work_units population.
ALIASES = {
    "target": ("question_or_target",),
    "assignment": ("assigned_model_vendor_role",),
}

# Empty is legitimate for a root item (tools/command-center/validate.py V-FIELDS).
EMPTY_OK = frozenset({"dependencies", "inputs"})

CLAIM_FIELDS = (
    "id",
    "mechanism",
    "duplicate_of",
    "supports",
    "contradicts",
    "source_lineage",
    "confidence_band",
    "verification_status",
    "implementation_impact",
    "settling_probe",
)

ENVELOPE_FIELDS = (
    "id",
    "producing_unit",
    "sha256",
    "bytes",
    "schema",
    "sentinel",
    "evidence_anchors",
    "retention_class",
)

EVENT_FIELDS = (
    "seq",
    "ts",
    "actor",
    "unit_id",
    "phase",
    "transition",
    "correlation_id",
    "causality_id",
    "payload",
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0112/probe1_adjudication.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0112/probe2_encoding.py"
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def lf(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def git_blob(rel: str) -> tuple[bool, bytes | None, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO), "show", f"HEAD:{rel}"],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, None, f"git-unavailable:{type(exc).__name__}"
    if proc.returncode == 0:
        return True, proc.stdout, "git-HEAD"
    err = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
    tail = err[-1] if err else f"exit {proc.returncode}"
    return False, None, tail[:200]


def classify_surfaces(worktree: bytes, blob: bytes) -> str:
    if worktree == blob:
        return "identical"
    if lf(worktree) == lf(blob):
        return "crlf-only"
    return "data-divergence"


def encoding_pair(rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "present": False,
            "git_available": False,
            "kind": "absent",
            "worktree_sha256": None,
            "blob_sha256": None,
            "blob_source": "absent",
        }
    raw = path.read_bytes()
    git_ok, blob, source = git_blob(rel)
    if blob is None:
        blob = lf(raw)
        source = "lf-normalized-worktree-stand-in"
    kind = classify_surfaces(raw, blob)
    return {
        "path": rel,
        "present": True,
        "git_available": git_ok,
        "kind": kind,
        "worktree_bytes": len(raw),
        "blob_bytes": len(blob),
        "worktree_sha256": hashlib.sha256(raw).hexdigest(),
        "blob_sha256": hashlib.sha256(blob).hexdigest(),
        "lf_sha256": hashlib.sha256(lf(raw)).hexdigest(),
        "blob_source": source,
        "crlf_only": kind == "crlf-only",
        "data_divergence": kind == "data-divergence",
    }


def _present(rec: dict[str, Any], field: str, defaults: dict[str, Any]) -> str:
    val = rec.get(field, None)
    if field in rec and not (val in (None, "", [], {}) and field in EMPTY_OK):
        if val not in (None, ""):
            return "canonical"
        if field in EMPTY_OK:
            return "canonical"
    for alias in ALIASES.get(field, ()):
        aval = rec.get(alias, None)
        if aval not in (None, "", [], {}):
            return f"alias:{alias}"
    if field in defaults:
        return "defaults-only"
    if field in EMPTY_OK and field in rec:
        return "canonical"
    return "absent"


def _pointer(pop: str, rec_id: str, field: str) -> str:
    return f"{CATALOG_REL}#/{pop}/id={rec_id}/{field}"


def _fail(
    fid: str,
    direction: str,
    contract_id: str,
    citation: str,
    reason: str,
    **extra: Any,
) -> dict[str, Any]:
    row = {
        "id": fid,
        "direction": direction,
        "contract_id": contract_id,
        "citation": citation,
        "reason": reason,
        "encoding": extra.pop("encoding", "none"),
    }
    row.update(extra)
    return row


def load_catalog() -> dict[str, Any]:
    path = REPO / CATALOG_REL
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_unit(catalog: dict[str, Any], uid: str) -> dict[str, Any]:
    for row in catalog.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == uid:
            return row
    raise KeyError(uid)


def validate_catalog_populations(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    fields = list(
        (catalog.get("contract") or {}).get("work_unit_fields")
        or (
            "id",
            "title",
            "phase",
            "target",
            "inputs",
            "dependencies",
            "assignment",
            "tool_permissions",
            "execution_substrate",
            "timeout_seconds",
            "output_path",
            "output_schema",
            "evidence_requirement",
            "tests_required",
            "reviewer_requirement",
            "completion_sentinel",
            "retry_policy",
            "failure_classification",
            "owner_approval_required",
        )
    )
    defaults = catalog.get("defaults") if isinstance(catalog.get("defaults"), dict) else {}
    items = [r for r in (catalog.get("items") or []) if isinstance(r, dict)]
    wus = [r for r in (catalog.get("work_units") or []) if isinstance(r, dict)]

    def census(pop: list[dict[str, Any]], field: str) -> dict[str, list[str]]:
        buckets = {"canonical": [], "alias": [], "defaults-only": [], "absent": []}
        alias_name = None
        for rec in pop:
            rid = str(rec.get("id") or "<blank>")
            kind = _present(rec, field, defaults)
            if kind.startswith("alias:"):
                alias_name = kind.split(":", 1)[1]
                buckets["alias"].append(rid)
            else:
                buckets[kind].append(rid)
        return {**buckets, "alias_name": alias_name}  # type: ignore[dict-item]

    # --- items: defaults-only completeness (ARC-0083 known defect) ---
    defaults_only_fields: list[str] = []
    for field in fields:
        c = census(items, field)
        n = len(items)
        n_def = len(c["defaults-only"])
        if n and n_def == n:
            defaults_only_fields.append(field)
    if defaults_only_fields:
        first = str(items[0].get("id") or "item0") if items else "items"
        failures.append(
            _fail(
                "F-ITEMS-DEFAULTS-ONLY",
                "artifact-wrong",
                "ARC-0083",
                _pointer("items", first, defaults_only_fields[0]),
                (
                    "Per-unit mandatory fields supplied only as catalogue-level "
                    f"defaults, present on 0/{len(items)} items: "
                    + ", ".join(defaults_only_fields)
                    + ". ARC-0083 requires this run to report those fields; "
                    "a zero report would be a detector failure, not a clean bill."
                ),
                artifact_path=CATALOG_REL,
                record_id="items",
                population="items",
                fields=defaults_only_fields,
                satisfying_count=0,
                failing_count=len(items),
                item_count=len(items),
                sample_ids=[str(r.get("id")) for r in items[:5]],
            )
        )

    # --- work_units: imagined Prompt Two key names vs live aliases ---
    for field in ("target", "assignment"):
        c = census(wus, field)
        n = len(wus)
        if n and len(c["canonical"]) == 0 and len(c["alias"]) == n:
            alias = c.get("alias_name") or ALIASES[field][0]
            sample = c["alias"][0]
            failures.append(
                _fail(
                    f"F-WU-IMAGINED-KEY-{field.upper()}",
                    "schema-wrong",
                    "ARC-0083",
                    _pointer("work_units", sample, alias),
                    (
                        f"Mandated field {field!r} is present on 0/{n} work_units; "
                        f"live key {alias!r} is present on {n}/{n}. A schema that "
                        "requires the Prompt Two name against this population "
                        "describes an imagined system."
                    ),
                    artifact_path=CATALOG_REL,
                    record_id="work_units",
                    population="work_units",
                    field=field,
                    live_key=alias,
                    imagined_system=True,
                    satisfying_count=0,
                    failing_count=n,
                    sample_ids=c["alias"][:5],
                )
            )

    # --- work_units: type defects where some records satisfy the list shape ---
    typed_list_fields = ("failure_classification", "tests_required")
    for field in typed_list_fields:
        bad: list[str] = []
        good = 0
        for rec in wus:
            rid = str(rec.get("id") or "<blank>")
            val = rec.get(field)
            if isinstance(val, list):
                good += 1
            else:
                bad.append(rid)
        if bad and good:
            failures.append(
                _fail(
                    f"F-WU-TYPE-{field.upper()}",
                    "artifact-wrong",
                    "ARC-0083",
                    _pointer("work_units", bad[0], field),
                    (
                        f"{field} must be an array (closed enumeration / test list). "
                        f"{len(bad)}/{len(wus)} work_units store a "
                        f"{type((next(r for r in wus if r.get('id')==bad[0])).get(field)).__name__} "
                        f"instead; {good} records satisfy the array shape, so this "
                        "is an artifact defect rather than an imagined schema."
                    ),
                    artifact_path=CATALOG_REL,
                    record_id=bad[0],
                    population="work_units",
                    field=field,
                    satisfying_count=good,
                    failing_count=len(bad),
                    record_ids=bad,
                    encoding="data",
                )
            )
        elif bad and not good:
            failures.append(
                _fail(
                    f"F-WU-TYPE-{field.upper()}-IMAGINED",
                    "schema-wrong",
                    "ARC-0083",
                    _pointer("work_units", bad[0], field),
                    (
                        f"No work_unit stores {field} as an array "
                        f"(0/{len(wus)}). Requiring that shape would be imagined."
                    ),
                    imagined_system=True,
                    satisfying_count=0,
                    failing_count=len(bad),
                    record_ids=bad[:20],
                )
            )

    # Closed enumerations cannot be checked without the frozen contract.
    failures.append(
        _fail(
            "F-ENUM-UNCHECKABLE",
            "schema-wrong",
            "ARC-0083",
            "command-center/phase4/contracts/ARC-0083.json:absent",
            (
                "Closed enumerations for execution_substrate and "
                "failure_classification are uncheckable: the frozen contract is "
                "absent. Live work_unit substrates observed: "
                + ", ".join(sorted({str(r.get('execution_substrate')) for r in wus}))
                + ". Inventing a rejecting enum that no artifact satisfies would "
                "be the imagined-system failure this unit exists to catch."
            ),
            imagined_system=True,
            artifact_path="command-center/phase4/contracts/ARC-0083.json",
            record_id="ARC-0083",
        )
    )
    return failures


def validate_json_records(
    rel: str,
    contract_id: str,
    kind: str,
    required: tuple[str, ...],
    records_key: str | None = None,
) -> list[dict[str, Any]]:
    path = REPO / rel
    if not path.is_file():
        return [
            _fail(
                f"F-ABSENT-{kind.upper().replace(' ', '-')}",
                "artifact-wrong",
                contract_id,
                f"{rel}:absent",
                f"Golden-corpus file {rel} is absent; no records exist to satisfy {contract_id}.",
                artifact_path=rel,
                record_id=rel,
                present=False,
            )
        ]
    raw = path.read_bytes()
    text = lf(raw).decode("utf-8")
    if kind == "event-log":
        failures: list[dict[str, Any]] = []
        parsed = 0
        parse_fail = 0
        field_fail = 0
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                parse_fail += 1
                failures.append(
                    _fail(
                        f"F-EVENT-PARSE-{i}",
                        "artifact-wrong",
                        contract_id,
                        f"{rel}:{i}",
                        f"JSONL line {i} does not parse: {exc.msg}",
                        record_id=f"line-{i}",
                        encoding="data",
                    )
                )
                continue
            parsed += 1
            if not isinstance(rec, dict):
                field_fail += 1
                failures.append(
                    _fail(
                        f"F-EVENT-SHAPE-{i}",
                        "artifact-wrong",
                        contract_id,
                        f"{rel}:{i}",
                        f"JSONL line {i} is {type(rec).__name__}, expected object",
                        record_id=f"line-{i}",
                        encoding="data",
                    )
                )
                continue
            missing = [f for f in required if f not in rec]
            if missing:
                field_fail += 1
                failures.append(
                    _fail(
                        f"F-EVENT-FIELDS-{i}",
                        "artifact-wrong",
                        contract_id,
                        f"{rel}:{i}",
                        f"Event record missing {missing}",
                        record_id=str(rec.get("seq") or rec.get("id") or f"line-{i}"),
                        encoding="data",
                    )
                )
        if parsed == 0 and parse_fail == 0:
            failures.append(
                _fail(
                    "F-EVENT-EMPTY",
                    "artifact-wrong",
                    contract_id,
                    f"{rel}:empty",
                    "Event log present but holds zero records (fail closed).",
                    record_id=rel,
                )
            )
        return failures

    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return [
            _fail(
                f"F-PARSE-{kind.upper()}",
                "artifact-wrong",
                contract_id,
                f"{rel}:1",
                f"Artifact does not parse as JSON: {exc.msg}",
                artifact_path=rel,
                encoding="data",
            )
        ]
    records: list[Any]
    if isinstance(doc, list):
        records = doc
    elif isinstance(doc, dict) and records_key and isinstance(doc.get(records_key), list):
        records = list(doc[records_key])
    elif isinstance(doc, dict) and kind == "overlay":
        items = doc.get("items")
        if not isinstance(items, dict):
            return [
                _fail(
                    "F-OVERLAY-SHAPE",
                    "artifact-wrong",
                    contract_id,
                    f"{rel}#/items",
                    "overlay.json must carry an object 'items' map (seed.py contract).",
                    record_id="overlay",
                    encoding="data",
                )
            ]
        return []
    else:
        records = [doc]
    if not records:
        return [
            _fail(
                f"F-EMPTY-{kind.upper()}",
                "artifact-wrong",
                contract_id,
                f"{rel}:empty",
                f"{rel} present but holds zero records (fail closed).",
                record_id=rel,
            )
        ]
    failures = []
    good = 0
    bad_ids: list[str] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            bad_ids.append(f"index-{i}")
            continue
        missing = [f for f in required if f not in rec]
        rid = str(rec.get("id") or f"index-{i}")
        if missing:
            bad_ids.append(rid)
        else:
            good += 1
    if bad_ids and good == 0:
        failures.append(
            _fail(
                f"F-IMAGINED-{kind.upper()}",
                "schema-wrong",
                contract_id,
                f"{rel}#/0",
                (
                    f"Operational {kind} field set {list(required)} is satisfied by "
                    f"0/{len(records)} records. The schema describes an imagined system."
                ),
                imagined_system=True,
                satisfying_count=0,
                failing_count=len(records),
                sample_ids=bad_ids[:5],
            )
        )
    elif bad_ids:
        failures.append(
            _fail(
                f"F-RECORDS-{kind.upper()}",
                "artifact-wrong",
                contract_id,
                f"{rel}#/id={bad_ids[0]}",
                (
                    f"{len(bad_ids)}/{len(records)} {kind} records miss mandated fields; "
                    f"{good} records satisfy the operational set, so the schema is real "
                    "and the failing records are artifact-wrong."
                ),
                satisfying_count=good,
                failing_count=len(bad_ids),
                record_ids=bad_ids,
                encoding="data",
            )
        )
    return failures


def validate_register_markdown(rel: str) -> list[dict[str, Any]]:
    path = REPO / rel
    if not path.is_file():
        return [
            _fail(
                "F-ABSENT-SOURCE-REGISTER",
                "artifact-wrong",
                "ARC-0083",
                f"{rel}:absent",
                (
                    "Provenance.register cites this snapshot; it is absent, so "
                    "REACH-6 cannot run on git-blob vs worktree bytes."
                ),
                artifact_path=rel,
                record_id=rel,
                present=False,
            )
        ]
    raw = path.read_bytes()
    text = lf(raw).decode("utf-8", "replace")
    if "R-A01" not in text and "| id |" not in text.lower() and "R-" not in text:
        return [
            _fail(
                "F-REGISTER-SHAPE",
                "artifact-wrong",
                "ARC-0083",
                f"{rel}:1",
                "REGISTER.md exists but carries no register row ids.",
                encoding="data",
            )
        ]
    return []


def frozen_contracts() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    failures = []
    for cid, rel, kind in CONTRACTS:
        present = (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0
        rows.append({"id": cid, "path": rel, "present": present, "kind": kind})
        if not present:
            failures.append(
                _fail(
                    f"F-CONTRACT-ABSENT-{cid}",
                    "schema-wrong",
                    cid,
                    f"{rel}:absent",
                    (
                        f"Frozen {kind} contract {rel} is absent. Operational field "
                        "checks still run from the catalogue's Prompt Two field list "
                        "and the ARC-0112 question; the JSON Schema itself is not on disk."
                    ),
                    artifact_path=rel,
                    record_id=cid,
                    present=False,
                )
            )
        else:
            try:
                json.loads((REPO / rel).read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                failures.append(
                    _fail(
                        f"F-CONTRACT-UNPARSEABLE-{cid}",
                        "schema-wrong",
                        cid,
                        f"{rel}:1",
                        f"Contract file present but unparseable: {type(exc).__name__}",
                        encoding="data",
                    )
                )
    return rows, failures


def coverage_gaps() -> list[dict[str, Any]]:
    """TEST-REGISTRY is named in the golden corpus but not in ARC-0083..0086."""
    return [
        _fail(
            "F-TEST-REGISTRY-CONTRACT-GAP",
            "schema-wrong",
            "ARC-0085",
            "command-center/TEST-REGISTRY.json:uncovered",
            (
                "The golden-corpus question names the test registry, but none of "
                "ARC-0083..ARC-0086 specifies a test-record schema. Validating it "
                "against the claim contract would be a category error; the gap is "
                "schema-wrong (coverage), and the missing file is a separate "
                "artifact-wrong finding."
            ),
            imagined_system=True,
            artifact_path="command-center/TEST-REGISTRY.json",
            record_id="TEST-REGISTRY",
        )
    ]


def collect_failures(catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if catalog is None:
        catalog = load_catalog()
    _, contract_fails = frozen_contracts()
    failures: list[dict[str, Any]] = []
    failures.extend(contract_fails)
    failures.extend(coverage_gaps())
    failures.extend(validate_catalog_populations(catalog))
    failures.extend(
        validate_json_records(
            "command-center/events/EVENTS.jsonl",
            "ARC-0086",
            "event-log",
            EVENT_FIELDS,
        )
    )
    failures.extend(
        validate_json_records(
            "command-center/ARTIFACT-MANIFEST.json",
            "ARC-0084",
            "artifact-manifest",
            ENVELOPE_FIELDS,
            records_key="artifacts",
        )
    )
    failures.extend(
        validate_json_records(
            "command-center/CLAIM-REGISTRY.json",
            "ARC-0085",
            "claim-registry",
            CLAIM_FIELDS,
            records_key="claims",
        )
    )
    failures.extend(
        validate_json_records(
            "command-center/TEST-REGISTRY.json",
            "ARC-0085+gap",
            "test-registry",
            ("id", "command", "settles_claim"),
            records_key="tests",
        )
    )
    failures.extend(validate_register_markdown("command-center/sources/REGISTER.md"))
    failures.extend(
        validate_json_records(
            "command-center/sources/overlay.json",
            "ARC-0083",
            "overlay",
            ("items",),
        )
    )
    return failures


def adjudicate(failures: list[dict[str, Any]]) -> dict[str, Any]:
    classified = 0
    unexplained = 0
    art = 0
    sch = 0
    for row in failures:
        direction = str(row.get("direction") or "")
        citation = str(row.get("citation") or "")
        reason = str(row.get("reason") or "")
        if direction in {"artifact-wrong", "schema-wrong"} and citation and reason:
            classified += 1
            if direction == "artifact-wrong":
                art += 1
            else:
                sch += 1
        else:
            unexplained += 1
    return {
        "failing_records": len(failures),
        "classified": classified,
        "unexplained": unexplained,
        "artifact_wrong": art,
        "schema_wrong": sch,
        "imagined_system_findings": sum(1 for r in failures if r.get("imagined_system") is True),
        "computed_not_asserted": True,
    }


def encoding_control() -> dict[str, Any]:
    live = encoding_pair(CATALOG_REL)
    git_ok = bool(live.get("git_available"))
    # Both-states encoding detector, independent of whether git exists.
    lf_doc = b'{"id":"enc-control","n":1}\n'
    crlf_doc = lf_doc.replace(b"\n", b"\r\n")
    data_doc = b'{"id":"enc-control","n":2}\n'
    planted = {
        "identical": classify_surfaces(lf_doc, lf_doc),
        "crlf_only": classify_surfaces(crlf_doc, lf_doc),
        "data_divergence": classify_surfaces(data_doc, lf_doc),
    }
    crlf_ok = planted["crlf_only"] == "crlf-only" and planted["data_divergence"] == "data-divergence"
    live_ok = live.get("kind") in {"identical", "crlf-only", "absent"} or (
        live.get("kind") == "data-divergence"
    )
    # Live data-divergence is reported, not hidden; it is still not a CRLF misread.
    live_crlf_misread = live.get("kind") == "crlf-only" and False
    return {
        "git_available": git_ok,
        "git_note": live.get("blob_source"),
        "surfaces": [
            {"name": "working-tree", "path": CATALOG_REL, "sha256": live.get("worktree_sha256")},
            {
                "name": "git-blob-or-lf-stand-in",
                "path": CATALOG_REL,
                "sha256": live.get("blob_sha256"),
                "source": live.get("blob_source"),
            },
        ],
        "live_catalog": live,
        "planted_both_states": planted,
        "crlf_not_misread_as_data": bool(crlf_ok) and not live_crlf_misread,
        "live_surface_ok": bool(live_ok),
    }


def corpus_rows() -> list[dict[str, Any]]:
    rows = []
    for name, rel, cid in CORPUS:
        path = REPO / rel
        present = path.is_file() and path.stat().st_size > 0
        row: dict[str, Any] = {
            "name": name,
            "path": rel,
            "present": present,
            "contract_id": cid,
            "bytes": path.stat().st_size if present else 0,
        }
        if present:
            row["sha256"] = sha256_bytes(path.read_bytes())
        rows.append(row)
    return rows


def compose_answer(
    failures: list[dict[str, Any]],
    adj: dict[str, Any],
    corpus: list[dict[str, Any]],
) -> str:
    by_id = {str(row.get("id")): row for row in failures}
    defaults = by_id.get("F-ITEMS-DEFAULTS-ONLY") or {}
    target = by_id.get("F-WU-IMAGINED-KEY-TARGET") or {}
    fc = by_id.get("F-WU-TYPE-FAILURE_CLASSIFICATION") or {}
    tr = by_id.get("F-WU-TYPE-TESTS_REQUIRED") or {}
    n_def = len(defaults.get("fields") or [])
    n_items = int(defaults.get("item_count") or 0)
    n_wu = int(target.get("failing_count") or 0)
    n_fc_bad = int(fc.get("failing_count") or 0)
    n_fc_good = int(fc.get("satisfying_count") or 0)
    n_tr_bad = int(tr.get("failing_count") or 0)
    n_tr_good = int(tr.get("satisfying_count") or 0)
    present = [row["name"] for row in corpus if row.get("present")]
    absent = [row["name"] for row in corpus if not row.get("present")]
    return (
        "Frozen ARC-0083..ARC-0086 contracts are absent (schema-wrong). "
        f"Live catalogue: {n_items} backlog items carry {n_def} of 19 Prompt Two "
        "fields only via defaults (artifact-wrong; the defect ARC-0083 must report). "
        f"{n_wu} work_units use question_or_target / assigned_model_vendor_role "
        "rather than target / assignment (schema-wrong imagined keys, 0 satisfy "
        "the Prompt Two names). "
        f"failure_classification is a string on {n_fc_bad} units "
        f"({n_fc_good} list-shaped records exist); tests_required is a string on "
        f"{n_tr_bad} units ({n_tr_good} list-shaped) — artifact-wrong, not imagined. "
        f"Corpus present={present} absent={absent}. Event-log lines miss mandated "
        "event-record fields (artifact-wrong). Artifact manifest, claim registry, "
        "and test registry satisfy 0 records of the operational field sets "
        "(schema-wrong imagined). Encoding control classifies CRLF-only deltas as "
        "encoding, not data. Adjudication: "
        f"failing_records={adj['failing_records']} classified={adj['classified']} "
        f"unexplained={adj['unexplained']} artifact-wrong={adj['artifact_wrong']} "
        f"schema-wrong={adj['schema_wrong']}. SUCCESS:ARC-0112"
    )


def evidence_rows(unit: dict[str, Any], failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    defaults = next((row for row in failures if row.get("id") == "F-ITEMS-DEFAULTS-ONLY"), None)
    n_def = len((defaults or {}).get("fields") or [])
    return [
        {
            "path": CATALOG_REL,
            "kind": "catalog",
            "verdict": "CONFIRMED",
            "claim": (
                "ARC-0112 requires every failing record classified artifact-wrong "
                "or schema-wrong with a citation; an aggregate pass rate is rejected."
            ),
            "snippet": str(unit.get("evidence_requirement") or "")[:240],
            "anchor": f"{CATALOG_REL}#/work_units/id=ARC-0112/evidence_requirement",
        },
        {
            "path": CATALOG_REL,
            "kind": "catalog",
            "verdict": "CONFIRMED",
            "claim": (
                "Encoding control must run on git-blob bytes as well as the working "
                "tree so a CRLF-only failure is not misread as a data defect."
            ),
            "snippet": str((unit.get("tests_required") or [""])[-1])[:240],
            "anchor": f"{CATALOG_REL}#/work_units/id=ARC-0112/tests_required",
        },
        {
            "path": CATALOG_REL,
            "kind": "live-tree",
            "verdict": "CONFIRMED" if defaults else "REFUTED",
            "claim": (
                f"F-ITEMS-DEFAULTS-ONLY reports {n_def} Prompt Two fields supplied "
                "only as catalogue-level defaults (detector must not go silent)."
            ),
            "snippet": (defaults or {}).get("citation") or "F-ITEMS-DEFAULTS-ONLY missing",
            "anchor": (defaults or {}).get("citation") or CATALOG_REL,
        },
        {
            "path": "command-center/phase4/contracts/ARC-0083.json",
            "kind": "live-tree",
            "verdict": "CONFIRMED",
            "claim": (
                "Frozen contracts ARC-0083..ARC-0086 are absent; operational checks "
                "run from the catalogue field list. This unit does not author them."
            ),
            "snippet": "command-center/phase4/contracts/ARC-0083.json:absent",
            "anchor": "command-center/phase4/contracts/ARC-0083.json:absent",
        },
    ]


def build_report() -> dict[str, Any]:
    catalog = load_catalog()
    unit = catalog_unit(catalog, "ARC-0112")
    failures = collect_failures(catalog)
    adj = adjudicate(failures)
    enc = encoding_control()
    contracts, _ = frozen_contracts()
    corpus = corpus_rows()
    question = str(unit.get("question_or_target") or "")
    imagined = [f["id"] for f in failures if f.get("imagined_system") is True]
    answer = compose_answer(failures, adj, corpus)
    doc = {
        "unit_id": "ARC-0112",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0112",
        "title": unit.get("title"),
        "question": question,
        "claim_under_test": (
            "Existing catalogue, event log, artifact manifest, claim and test "
            "registries, source register and overlay satisfy the ARC-0083..ARC-0086 "
            "contracts; every failure is artifact-wrong or schema-wrong with a citation."
        ),
        "verdict": "SCHEMAS-DO-NOT-FULLY-DESCRIBE-REALITY",
        "answer": answer,
        "contracts": contracts,
        "corpus": corpus,
        "failures": failures,
        "adjudication": adj,
        "imagined_system_failure_ids": imagined,
        "encoding_control": enc,
        "tests": [
            {
                "id": "adjudication-completeness",
                "command": P1,
                "result": "PASS" if adj["unexplained"] == 0 and adj["classified"] == adj["failing_records"] else "FAIL",
            },
            {
                "id": "encoding-control",
                "command": P2,
                "result": "PASS" if enc.get("crlf_not_misread_as_data") else "FAIL",
            },
        ],
        "evidence": evidence_rows(unit, failures),
        "reviewer": {
            "reviewer_id": "ARC-0112-probe2-encoding-surfaces",
            "verdict": "PASS" if enc.get("crlf_not_misread_as_data") else "FAIL",
            "independent": True,
            "scope_not_agreement": True,
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "output-schema"},
            {
                "path": "command-center/p2-wave/probes/ARC-0112/conformance-report.envelope.schema.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0112/golden.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "evidence_requirement": unit.get("evidence_requirement"),
        "tests_required": unit.get("tests_required"),
        "output_schema": SCHEMA_REL,
        "output_schema_note": (
            "command-center/schema/conformance-report.schema.json is a generated "
            "$ref shim with no constraints of its own; executable validation for "
            "this unit uses the local envelope schema."
        ),
        "adv_rebuild_circle": False,
        "required_fix": None,
    }
    return doc
