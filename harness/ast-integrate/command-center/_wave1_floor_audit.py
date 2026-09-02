"""WAVE 1 FLOOR AUDIT - mechanical, no eyeballing, no agent self-report trusted.

Measures under platform/:
  1  registry/          distinct workflow candidates            FLOOR >= 160
  1b                    survivors after trivial-fork/rename normalisation
  2  council/protocols/ count + per-file councilspec validation FLOOR >= 48
  3  council/presets/   count + per-file councilspec validation FLOOR >= 64
  4  schema/            each schema compiles as JSON Schema 2020-12
  5  lib/               run every test file, verbatim pass/fail
  6  (external)         12-condition predicate mutation battery
  CTL detector control: seeded invalid council file + seeded duplicate candidate
      must both FIRE; plus both-states control over schema/examples/{valid,invalid}

Writes JSON to stdout. Nothing in platform/ is modified: the seeded defects go
into a throwaway temp dir.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PLATFORM = REPO / "platform"
SCHEMA_DIR = PLATFORM / "schema"
COUNCILSPEC_SCHEMA = SCHEMA_DIR / "councilspec.schema.json"

sys.path.insert(0, str(PLATFORM / "lib"))

import jsonschema  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

OUT: dict = {"unit": "verify/wave1-floors", "root": str(PLATFORM)}


# --------------------------------------------------------------------------- #
# validator: two layers (JSON Schema, then the repo's own semantic rules)
# --------------------------------------------------------------------------- #

_SCHEMA = json.loads(COUNCILSPEC_SCHEMA.read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(_SCHEMA)

try:
    # errors() FILTERS Finding objects; it does NOT take a spec. Passing the spec
    # dict made it iterate the dict's KEYS (strings) and raise
    # "'str' object has no attribute 'severity'" on 100% of inputs - a detector
    # that fires on every file including known-good ones. Fixed to errors(check(spec)).
    from councilspec.semantics import check as _sem_check  # type: ignore
    from councilspec.semantics import errors as _sem_filter  # type: ignore

    _SEM_OK = True
    _SEM_IMPORT_ERR = None

    def _sem_errors(spec):  # type: ignore
        return _sem_filter(_sem_check(spec))

    def _sem_warnings(spec):  # type: ignore
        return [f for f in _sem_check(spec) if f.severity != "ERROR"]

except Exception as exc:  # pragma: no cover
    _SEM_OK = False
    _SEM_IMPORT_ERR = f"{type(exc).__name__}: {exc}"

    def _sem_errors(spec):  # type: ignore
        return []

    def _sem_warnings(spec):  # type: ignore
        return []


def validate_councilspec(path: Path) -> dict:
    """Return a per-file verdict. schema_ok = pure JSON Schema; sem_ok = semantics."""
    rec = {"file": path.name}
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        rec.update(
            parse_ok=False,
            schema_ok=False,
            sem_ok=False,
            ok=False,
            schema_error_count=1,
            schema_errors=[f"JSON parse: {type(exc).__name__}: {exc}"],
            sem_error_count=0,
            sem_errors=[],
        )
        return rec
    rec["parse_ok"] = True
    serrs = sorted(_VALIDATOR.iter_errors(spec), key=lambda e: list(e.absolute_path))
    rec["schema_ok"] = not serrs
    rec["schema_error_count"] = len(serrs)
    rec["schema_errors"] = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message[:200]}"
        for e in serrs[:5]
    ]
    try:
        semerrs = list(_sem_errors(spec))
    except Exception as exc:
        semerrs = [f"semantics raised {type(exc).__name__}: {exc}"]
    rec["sem_ok"] = not semerrs
    rec["sem_error_count"] = len(semerrs)
    rec["sem_errors"] = [str(s)[:200] for s in semerrs[:5]]
    try:
        warns = list(_sem_warnings(spec))
    except Exception:
        warns = []
    rec["sem_warn_count"] = len(warns)
    rec["ok"] = rec["schema_ok"] and rec["sem_ok"]
    return rec


# --------------------------------------------------------------------------- #
# 1. registry
# --------------------------------------------------------------------------- #

_VER = re.compile(r"\bv?\d+(?:\.\d+)+\b")
_PARENS = re.compile(r"\([^)]*\)")
_EXT = re.compile(r"\.(?:js|mjs|md|py|json|ts)$", re.I)
_NONALNUM = re.compile(r"[^a-z0-9]+")
_TRAILNUM = re.compile(r"\d+$")


def norm_name(name) -> str:
    s = str(name or "").lower()
    s = s.split(" - ")[0].split(" — ")[0]
    s = _PARENS.sub(" ", s)
    s = _VER.sub(" ", s)
    s = _EXT.sub("", s.strip())
    s = s.split("/")[-1].split("\\")[-1]
    s = _NONALNUM.sub("-", s).strip("-")
    s = _TRAILNUM.sub("", s).strip("-")
    return s


def prov_key(prov) -> str:
    """Coarse provenance identity: repo/upstream/anchor leaf, lowercased."""
    if prov is None:
        return ""
    if isinstance(prov, list):
        prov = prov[0] if prov else ""
    if isinstance(prov, str):
        blob = prov
    elif isinstance(prov, dict):
        for k in (
            "upstream_repo",
            "repo",
            "primary_anchor",
            "anchor",
            "verified_body",
            "path",
        ):
            if prov.get(k):
                blob = str(prov[k])
                break
        else:
            blob = json.dumps(prov, sort_keys=True)
    else:
        blob = str(prov)
    blob = blob.lower().replace("\\", "/")
    leaf = [p for p in blob.split("/") if p]
    tail = "/".join(leaf[-2:]) if leaf else blob
    return _NONALNUM.sub("-", tail).strip("-")


def audit_registry() -> dict:
    reg = PLATFORM / "registry"
    files = sorted(
        p
        for p in reg.glob("workflow-candidates-*.json")
        if ".COVERAGE." not in p.name and ".METHOD." not in p.name
    )
    rows, per_file, manifests, rejected = [], [], [], []
    for f in files:
        raw = json.loads(f.read_text(encoding="utf-8"))
        arr = raw["candidates"] if isinstance(raw, dict) else raw
        kept = 0
        for e in arr:
            if not isinstance(e, dict):
                rejected.append({"file": f.name, "why": "non-object element"})
                continue
            if "_manifest" in e:
                manifests.append({"file": f.name, "id": e.get("id")})
                continue
            cid = e.get("id")
            if isinstance(cid, str) and "REJECT" in cid.upper():
                rejected.append({"file": f.name, "id": cid, "why": "id marked REJECT"})
                continue
            rows.append(
                {
                    "file": f.name,
                    "id": cid,
                    "name": e.get("name"),
                    "nn": norm_name(e.get("name")),
                    "pk": prov_key(e.get("provenance")),
                    "classification": e.get("classification"),
                }
            )
            kept += 1
        per_file.append(
            {"file": f.name, "elements": len(arr), "counted_candidates": kept}
        )

    total = len(rows)

    # exact duplicate ids
    byid: dict = {}
    for r in rows:
        byid.setdefault(str(r["id"]), []).append(r)
    dup_ids = {k: [x["file"] for x in v] for k, v in byid.items() if len(v) > 1}

    # trivial fork / rename: same normalised name  (name-only key)
    byname: dict = {}
    for r in rows:
        byname.setdefault(r["nn"], []).append(r)
    name_groups = {k: v for k, v in byname.items() if len(v) > 1}

    # stricter: same normalised name AND same provenance leaf
    bynp: dict = {}
    for r in rows:
        bynp.setdefault((r["nn"], r["pk"]), []).append(r)
    np_groups = {f"{k[0]}||{k[1]}": v for k, v in bynp.items() if len(v) > 1}

    collapse_name = sum(len(v) - 1 for v in name_groups.values())
    collapse_np = sum(len(v) - 1 for v in np_groups.values())

    return {
        "files_read": [p.name for p in files],
        "per_file": per_file,
        "manifest_rows_excluded": manifests,
        "rows_excluded_as_REJECT": rejected,
        "total_candidates_counted": total,
        "floor": 160,
        "floor_met": total >= 160,
        "distinct_ids": len(byid),
        "duplicate_ids": dup_ids,
        "normalisation_rule": (
            "name lowercased; ' - '/' - ' tail dropped; parentheticals, semver, "
            "file extension, path prefix and trailing digits stripped; non-alnum -> '-'"
        ),
        "trivial_fork_groups_by_name": {
            k: [{"file": x["file"], "id": x["id"], "name": x["name"]} for x in v]
            for k, v in sorted(name_groups.items())
        },
        "trivial_fork_groups_by_name_and_provenance": {
            k: [{"file": x["file"], "id": x["id"], "name": x["name"]} for x in v]
            for k, v in sorted(np_groups.items())
        },
        "survivors_after_name_normalisation": total - collapse_name,
        "survivors_after_name_and_provenance_normalisation": total - collapse_np,
        "survivors_floor_met_name_only": (total - collapse_name) >= 160,
    }


# --------------------------------------------------------------------------- #
# 2 + 3. council protocols / presets
# --------------------------------------------------------------------------- #


def audit_council(sub: str, floor: int) -> dict:
    d = PLATFORM / "council" / sub
    specs = sorted(d.glob("*.councilspec.json"))
    other_json = sorted(
        p.name for p in d.glob("*.json") if not p.name.endswith(".councilspec.json")
    )
    recs = [validate_councilspec(p) for p in specs]
    npass = sum(1 for r in recs if r["ok"])
    nschema = sum(1 for r in recs if r["schema_ok"])
    return {
        "dir": str(d),
        "councilspec_file_count": len(specs),
        "floor": floor,
        "floor_met": len(specs) >= floor,
        "other_json_files_not_counted": other_json,
        "schema_layer_pass": nschema,
        "schema_layer_fail": len(specs) - nschema,
        "both_layers_pass": npass,
        "both_layers_fail": len(specs) - npass,
        "semantics_layer_available": _SEM_OK,
        "semantics_import_error": _SEM_IMPORT_ERR,
        "per_file": recs,
        "failing_files": [
            {
                "file": r["file"],
                "schema_ok": r["schema_ok"],
                "sem_ok": r["sem_ok"],
                "schema_errors": r["schema_errors"],
                "sem_errors": r["sem_errors"],
            }
            for r in recs
            if not r["ok"]
        ],
    }


# --------------------------------------------------------------------------- #
# 4. schema self-compilation
# --------------------------------------------------------------------------- #


def audit_schemas() -> dict:
    rows = []
    for p in sorted(SCHEMA_DIR.glob("*.json")):
        rec = {"file": p.name, "bytes": p.stat().st_size}
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            rec.update(
                parse_ok=False,
                is_schema_document=None,
                compiles_2020_12=False,
                error=f"{type(exc).__name__}: {exc}",
            )
            rows.append(rec)
            continue
        rec["parse_ok"] = True
        decl = doc.get("$schema") if isinstance(doc, dict) else None
        rec["declared_$schema"] = decl
        looks_like_schema = isinstance(doc, dict) and (
            decl is not None
            or any(k in doc for k in ("$defs", "properties", "type", "$id"))
        )
        rec["is_schema_document"] = bool(looks_like_schema)
        if not looks_like_schema:
            rec["compiles_2020_12"] = None
            rec["note"] = "not a schema document (data/report file) - not compiled"
            rows.append(rec)
            continue
        try:
            Draft202012Validator.check_schema(doc)
            rec["compiles_2020_12"] = True
            rec["error"] = None
        except jsonschema.exceptions.SchemaError as exc:
            rec["compiles_2020_12"] = False
            rec["error"] = str(exc)[:400]
        # resolvability: can it be instantiated and used at all?
        try:
            Draft202012Validator(doc).is_valid({})
            rec["instantiates_and_runs"] = True
        except Exception as exc:
            rec["instantiates_and_runs"] = False
            rec["run_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        rec["is_2020_12"] = decl == "https://json-schema.org/draft/2020-12/schema"
        rows.append(rec)
    schema_docs = [r for r in rows if r.get("is_schema_document")]
    return {
        "dir": str(SCHEMA_DIR),
        "json_files": len(rows),
        "schema_documents": len(schema_docs),
        "compile_pass": sum(1 for r in schema_docs if r.get("compiles_2020_12")),
        "compile_fail": sum(
            1 for r in schema_docs if r.get("compiles_2020_12") is False
        ),
        "declared_2020_12": sum(1 for r in schema_docs if r.get("is_2020_12")),
        "per_file": rows,
    }


# --------------------------------------------------------------------------- #
# 5. lib tests
# --------------------------------------------------------------------------- #

_SUM = re.compile(
    r"^(?:=+\s*)?(?P<body>(?:\d+\s+\w+(?:,\s*)?)+)(?:\s*in\s+[\d.]+s.*)?$"
)


def parse_pytest_tail(out: str) -> dict:
    counts = {}
    line = ""
    for ln in reversed(out.strip().splitlines()):
        if re.search(r"\b(passed|failed|error|errors|no tests ran)\b", ln):
            line = ln.strip()
            break
    for n, w in re.findall(
        r"(\d+)\s+(passed|failed|errors?|skipped|xfailed|xpassed|warnings?|deselected)",
        line,
    ):
        counts[w.rstrip("s") if w.startswith("error") else w] = int(n)
    return {"summary_line": line, "counts": counts}


def audit_lib_tests() -> dict:
    test_files = sorted(
        p for p in (PLATFORM / "lib").rglob("test_*.py") if "__pycache__" not in p.parts
    )
    rows = []
    for tf in test_files:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(tf),
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ]
        pr = subprocess.run(
            cmd, cwd=str(PLATFORM / "lib"), capture_output=True, text=True, timeout=1800
        )
        out = (pr.stdout or "") + (pr.stderr or "")
        parsed = parse_pytest_tail(out)
        rows.append(
            {
                "test_file": str(tf.relative_to(PLATFORM)).replace("\\", "/"),
                "exit_code": pr.returncode,
                "verbatim_summary_line": parsed["summary_line"],
                "counts": parsed["counts"],
                "green": pr.returncode == 0,
                "tail": "\n".join(out.strip().splitlines()[-6:]),
            }
        )
    tot = {}
    for r in rows:
        for k, v in r["counts"].items():
            tot[k] = tot.get(k, 0) + v
    return {
        "test_files_found": len(test_files),
        "files_green": sum(1 for r in rows if r["green"]),
        "files_red": sum(1 for r in rows if not r["green"]),
        "aggregate_counts": tot,
        "per_file": rows,
    }


# --------------------------------------------------------------------------- #
# CTL. detector control
# --------------------------------------------------------------------------- #


def detector_control() -> dict:
    ctl: dict = {}

    # --- control A: both-states over the shipped example corpus -------------
    ex = SCHEMA_DIR / "examples"
    known_good = sorted((ex / "valid").glob("*.councilspec.json"))
    known_bad = sorted((ex / "invalid").glob("*.councilspec.json"))
    good = [validate_councilspec(p) for p in known_good]
    bad = [validate_councilspec(p) for p in known_bad]
    ctl["both_states_over_shipped_examples"] = {
        "known_valid_files": len(good),
        "known_valid_that_PASS": sum(1 for r in good if r["ok"]),
        "known_valid_that_wrongly_FAIL": [r["file"] for r in good if not r["ok"]],
        "known_invalid_files": len(bad),
        "known_invalid_that_FIRE": sum(1 for r in bad if not r["ok"]),
        "known_invalid_that_wrongly_PASS": [r["file"] for r in bad if r["ok"]],
        "known_invalid_caught_by_schema_layer_only": [
            r["file"] for r in bad if not r["schema_ok"] and r["sem_ok"]
        ],
        "known_invalid_caught_by_semantics_layer_only": [
            r["file"] for r in bad if r["schema_ok"] and not r["sem_ok"]
        ],
        "per_file_invalid": bad,
    }

    # --- control B: seed an invalid council file into a scratch copy ---------
    tmp = Path(tempfile.mkdtemp(prefix="wave1audit_"))
    try:
        src = sorted((PLATFORM / "council" / "protocols").glob("*.councilspec.json"))[0]
        base = json.loads(src.read_text(encoding="utf-8"))
        pre = validate_councilspec(src)

        seeds = []

        # B1: drop a required top-level key
        m1 = copy.deepcopy(base)
        m1.pop("voting", None)
        p1 = tmp / "SEED1-missing-required-voting.councilspec.json"
        p1.write_text(json.dumps(m1, indent=2), encoding="utf-8")
        seeds.append(("drop required key 'voting'", validate_councilspec(p1)))

        # B2: inject an unknown top-level key (additionalProperties: false)
        m2 = copy.deepcopy(base)
        m2["totally_bogus_key_seeded_by_audit"] = 1
        p2 = tmp / "SEED2-unknown-top-level-key.councilspec.json"
        p2.write_text(json.dumps(m2, indent=2), encoding="utf-8")
        seeds.append(("inject unknown top-level key", validate_councilspec(p2)))

        # B3: wrong type on a required field
        m3 = copy.deepcopy(base)
        m3["council_id"] = 12345
        p3 = tmp / "SEED3-wrong-type-council_id.councilspec.json"
        p3.write_text(json.dumps(m3, indent=2), encoding="utf-8")
        seeds.append(("council_id str -> int", validate_councilspec(p3)))

        # B4: malformed JSON
        p4 = tmp / "SEED4-malformed.councilspec.json"
        p4.write_text('{"schema_version": "1.0.0",,}', encoding="utf-8")
        seeds.append(("malformed JSON", validate_councilspec(p4)))

        ctl["seeded_invalid_council_file"] = {
            "donor_file": src.name,
            "donor_passes_before_seeding": pre["ok"],
            "donor_verdict": {
                "schema_ok": pre["schema_ok"],
                "sem_ok": pre["sem_ok"],
                "schema_errors": pre["schema_errors"],
                "sem_errors": pre["sem_errors"],
            },
            "mutants": [
                {
                    "mutation": why,
                    "validator_FIRED": not r["ok"],
                    "schema_ok": r["schema_ok"],
                    "sem_ok": r["sem_ok"],
                    "first_errors": (
                        r["schema_errors"] or r["sem_errors"] or r.get("errors")
                    ),
                }
                for why, r in seeds
            ],
            "all_seeded_mutants_fired": all(not r["ok"] for _, r in seeds),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- control C: seed a duplicate candidate -------------------------------
    reg_before = audit_registry()
    tmp2 = Path(tempfile.mkdtemp(prefix="wave1audit_dup_"))
    try:
        # rebuild the row set, then append an exact clone + a renamed clone
        rows = []
        for f in sorted(
            p
            for p in (PLATFORM / "registry").glob("workflow-candidates-*.json")
            if ".COVERAGE." not in p.name and ".METHOD." not in p.name
        ):
            raw = json.loads(f.read_text(encoding="utf-8"))
            arr = raw["candidates"] if isinstance(raw, dict) else raw
            for e in arr:
                if isinstance(e, dict) and "_manifest" not in e:
                    cid = e.get("id")
                    if isinstance(cid, str) and "REJECT" in cid.upper():
                        continue
                    rows.append(e)
        donor = rows[0]

        clone_exact = copy.deepcopy(donor)
        clone_ren = copy.deepcopy(donor)
        clone_ren["id"] = str(donor.get("id")) + "-FORKCOPY"
        clone_ren["name"] = str(donor.get("name")) + " v2.0.1 (fork)"

        def keyset(items):
            byname: dict = {}
            for e in items:
                byname.setdefault(norm_name(e.get("name")), []).append(e.get("id"))
            return byname

        base_keys = keyset(rows)
        with_dupes = keyset(rows + [clone_exact, clone_ren])
        base_groups = {k: v for k, v in base_keys.items() if len(v) > 1}
        new_groups = {k: v for k, v in with_dupes.items() if len(v) > 1}
        detected = {
            k: v for k, v in new_groups.items() if len(v) > len(base_groups.get(k, []))
        }
        ctl["seeded_duplicate_candidate"] = {
            "donor_id": donor.get("id"),
            "donor_name": donor.get("name"),
            "seeded": [
                {"id": clone_exact.get("id"), "kind": "exact clone"},
                {"id": clone_ren["id"], "kind": "renamed + version-bumped clone"},
            ],
            "normalised_key": norm_name(donor.get("name")),
            "duplicate_groups_before_seeding": len(base_groups),
            "duplicate_groups_after_seeding": len(new_groups),
            "detector_FIRED": bool(detected),
            "groups_that_grew": detected,
            "collapse_delta_expected_2": (
                sum(len(v) - 1 for v in with_dupes.values() if len(v) > 1)
                - sum(len(v) - 1 for v in base_keys.values() if len(v) > 1)
            ),
        }
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)

    ctl["registry_snapshot_used_for_control"] = {
        "total": reg_before["total_candidates_counted"]
    }
    ctl["control_verdict"] = (
        "PASS"
        if (
            ctl["seeded_invalid_council_file"]["all_seeded_mutants_fired"]
            and ctl["seeded_duplicate_candidate"]["detector_FIRED"]
            and ctl["both_states_over_shipped_examples"]["known_invalid_that_FIRE"]
            == ctl["both_states_over_shipped_examples"]["known_invalid_files"]
            and not ctl["both_states_over_shipped_examples"][
                "known_valid_that_wrongly_FAIL"
            ]
        )
        else "PARTIAL-OR-FAIL"
    )
    return ctl


# --------------------------------------------------------------------------- #


def main() -> int:
    OUT["detector_control"] = detector_control()
    OUT["floor_1_registry"] = audit_registry()
    OUT["floor_2_protocols"] = audit_council("protocols", 48)
    OUT["floor_3_presets"] = audit_council("presets", 64)
    OUT["floor_4_schemas"] = audit_schemas()
    OUT["floor_5_lib_tests"] = audit_lib_tests()
    print(json.dumps(OUT, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
