"""AUD-0025 floating-constraint census: classify, dual-seed resolve, blast radius."""
from __future__ import annotations

import json
import os
import re
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0025"
OUT_REL = "command-center/audit/AUD-0025-unpinned-version-census.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
INDEX_REL = "command-center/p2-wave/probes/AUD-0025/fixtures/index.json"
SENTINEL = (
    "SUCCESS:AUD-0025 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which dependencies are declared with a floating constraint that allows a "
    "different resolution tomorrow, and for each, what is the blast radius if "
    "it resolves to a new major?"
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0025/probe1_constraint_syntax.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0025/probe2_dual_resolution.py"
)
NAMED_SYNTAX = ("exact", "compatible", "caret", "tilde", "wildcard", "none")
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".tox",
    ".eggs",
}
PROBES_PREFIX = "command-center/p2-wave/probes/"
PEP508 = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>.*)$"
)
# Fixture rows probe 1 must classify into the six named syntax classes.
FIXTURE_EXPECTED: dict[tuple[str, str], str] = {
    ("pinned-pkg", "pep440-zoo/pyproject.toml"): "exact",
    ("compat-pkg", "pep440-zoo/pyproject.toml"): "compatible",
    ("float-pkg", "pep440-zoo/pyproject.toml"): "range",
    ("bare-pkg", "pep440-zoo/pyproject.toml"): "none",
    ("setuptools", "pep440-zoo/pyproject.toml"): "exact",
    ("caret-pkg", "npm-syntax/package.json"): "caret",
    ("tilde-pkg", "npm-syntax/package.json"): "tilde",
    ("wild-pkg", "npm-syntax/package.json"): "wildcard",
    ("none-pkg", "npm-syntax/package.json"): "none",
}
CONTROL_EXACT_NAME = "pinned-pkg"
CONTROL_FLOAT_NAME = "float-pkg"


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def load_index() -> dict[str, dict]:
    doc = json.loads((REPO / INDEX_REL).read_text(encoding="utf-8"))
    pkgs = doc.get("packages") or {}
    out: dict[str, dict] = {}
    for name, rec in pkgs.items():
        vers = [str(v) for v in (rec.get("versions") or [])]
        out[norm_name(name)] = {
            "ecosystem": rec.get("ecosystem") or "python-pep440",
            "versions": sorted(vers, key=ver_key),
        }
    return out


def norm_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def ver_key(v: str) -> tuple:
    try:
        pv = Version(v)
        return (0, pv)
    except InvalidVersion:
        nums = tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-+]", v)[:4])
        return (1, nums)


def parse_ver_triple(v: str) -> tuple[int, int, int]:
    try:
        pv = Version(v)
        rels = list(pv.release) + [0, 0, 0]
        return int(rels[0]), int(rels[1]), int(rels[2])
    except InvalidVersion:
        parts = []
        for x in v.split("."):
            m = re.match(r"(\d+)", x)
            parts.append(int(m.group(1)) if m else 0)
        while len(parts) < 3:
            parts.append(0)
        return parts[0], parts[1], parts[2]


def next_major(v: str) -> str:
    maj, _, _ = parse_ver_triple(v)
    return f"{maj + 1}.0.0"


def strip_marker(spec: str) -> str:
    return (spec or "").split(";")[0].strip()


def classify(spec: str, ecosystem: str) -> str:
    """Map a constraint string onto the catalog's named classes, plus range/other."""
    s = strip_marker(spec)
    eco = ecosystem or "python-pep440"
    if s == "":
        return "none"
    if eco == "npm-semver":
        if s in ("*", "x", "X", "latest"):
            return "wildcard"
        if re.match(r"^\d+\.(x|X|\*)$", s) or re.match(r"^\d+\.\d+\.(x|X|\*)$", s):
            return "wildcard"
        if s.startswith("^"):
            return "caret"
        if s.startswith("~") and not s.startswith("~="):
            return "tilde"
        if re.match(r"^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$", s):
            return "exact"
        if s.startswith((">=", "<=", ">", "<", "!=")):
            return "range"
        return "other"
    # python / pep440 / poetry-in-pyproject
    if s.startswith("^"):
        return "caret"
    if s.startswith("~="):
        return "compatible"
    if s.startswith("~"):
        return "tilde"
    if s in ("*", "x", "X"):
        return "wildcard"
    clauses = [c.strip() for c in s.split(",") if c.strip()]
    if any("*" in c or ".x" in c.lower() for c in clauses):
        return "wildcard"
    if clauses and all(c.startswith("===") or c.startswith("==") for c in clauses):
        return "exact"
    if any(c.startswith((">=", "<=", ">", "<", "!=")) for c in clauses):
        return "range"
    if clauses and all(re.match(r"^\d", c) for c in clauses) and len(clauses) == 1:
        # poetry-style bare version without operator: treat as exact
        return "exact"
    return "other"


def pep440_ok(spec: str, version: str) -> bool:
    s = strip_marker(spec)
    try:
        return Version(version) in SpecifierSet(s)
    except (InvalidSpecifier, InvalidVersion, ValueError):
        return False


def npm_ok(spec: str, version: str) -> bool:
    s = strip_marker(spec)
    v = parse_ver_triple(version)
    if s == "" or s in ("*", "x", "X", "latest"):
        return True
    m = re.match(r"^(\d+)\.(x|X|\*)$", s)
    if m:
        return v[0] == int(m.group(1))
    m = re.match(r"^(\d+)\.(\d+)\.(x|X|\*)$", s)
    if m:
        return v[0] == int(m.group(1)) and v[1] == int(m.group(2))
    if s.startswith("^"):
        base = parse_ver_triple(s[1:].strip())
        if v < base:
            return False
        if base[0] > 0:
            return v[0] == base[0]
        if base[1] > 0:
            return v[0] == 0 and v[1] == base[1]
        return v[0] == 0 and v[1] == 0 and v[2] == base[2]
    if s.startswith("~") and not s.startswith("~="):
        raw = s[1:].strip()
        base = parse_ver_triple(raw)
        dots = raw.count(".")
        if v < base:
            return False
        if dots == 0:
            return v[0] == base[0]
        return v[0] == base[0] and v[1] == base[1]
    if re.match(r"^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$", s):
        return parse_ver_triple(s) == v
    if s.startswith((">=", "<=", ">", "<", "!=")):
        try:
            return Version(version) in SpecifierSet(s.replace(" ", ""))
        except (InvalidSpecifier, InvalidVersion, ValueError):
            return False
    return False


def satisfies(spec: str, version: str, ecosystem: str) -> bool:
    if ecosystem == "npm-semver":
        return npm_ok(spec, version)
    return pep440_ok(spec, version)


def resolve_dual(name: str, spec: str, ecosystem: str, index: dict) -> dict:
    rec = index.get(norm_name(name))
    if rec is None:
        return {
            "in_index": False,
            "matching": [],
            "seed_lowest": None,
            "seed_highest": None,
            "floats_in_practice": "NOT-CHECKED",
            "note": "package absent from fixture index; not a live registry resolve",
        }
    matching = [v for v in rec["versions"] if satisfies(spec, v, ecosystem)]
    matching_sorted = sorted(matching, key=ver_key)
    lowest = matching_sorted[0] if matching_sorted else None
    highest = matching_sorted[-1] if matching_sorted else None
    floats: bool | str
    if lowest is None:
        floats = "NOT-CHECKED"
    else:
        floats = lowest != highest
    return {
        "in_index": True,
        "matching": matching_sorted,
        "seed_lowest": lowest,
        "seed_highest": highest,
        "floats_in_practice": floats,
        "note": "dual-seed = lowest vs highest satisfying version in the fixture index",
    }


def allows_new_major(spec: str, ecosystem: str, from_version: str | None) -> bool | str:
    if not from_version:
        return "NOT-CHECKED"
    return satisfies(spec, next_major(from_version), ecosystem)


def parse_pep508_list(items: list) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for raw in items:
        m = PEP508.match(str(raw))
        if not m:
            continue
        spec = strip_marker(m.group("spec") or "")
        out.append((m.group("name"), spec))
    return out


def parse_pyproject(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [
            {
                "name": "__error__",
                "declared": "",
                "syntax_class": "other",
                "ecosystem": "python-pep440",
                "dep_class": "parse-error",
                "manifest": rel(path),
                "error": f"{type(exc).__name__}: {exc}",
            }
        ]
    manifest = rel(path)
    for raw in (data.get("build-system") or {}).get("requires") or []:
        m = PEP508.match(str(raw))
        if m:
            spec = strip_marker(m.group("spec") or "")
            rows.append(_decl(m.group("name"), spec, "python-pep440", "build-system", manifest))
    proj = data.get("project") or {}
    for name, spec in parse_pep508_list(proj.get("dependencies") or []):
        rows.append(_decl(name, spec, "python-pep440", "runtime", manifest))
    for group, items in (proj.get("optional-dependencies") or {}).items():
        for name, spec in parse_pep508_list(items or []):
            rows.append(_decl(name, spec, "python-pep440", f"optional:{group}", manifest))
    poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    for k, v in poetry.items():
        if norm_name(k) == "python":
            continue
        spec = str(v if not isinstance(v, dict) else v.get("version", ""))
        rows.append(_decl(k, spec, "python-pep440", "poetry", manifest))
    return rows


def parse_package_json(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [
            {
                "name": "__error__",
                "declared": "",
                "syntax_class": "other",
                "ecosystem": "npm-semver",
                "dep_class": "parse-error",
                "manifest": rel(path),
                "error": f"{type(exc).__name__}: {exc}",
            }
        ]
    if not isinstance(data, dict):
        return rows
    manifest = rel(path)
    mapping = (
        ("dependencies", "runtime"),
        ("devDependencies", "dev"),
        ("peerDependencies", "peer"),
        ("optionalDependencies", "optional"),
    )
    for key, dep_class in mapping:
        block = data.get(key)
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            rows.append(_decl(str(name), str(spec), "npm-semver", dep_class, manifest))
    return rows


def _decl(name: str, spec: str, ecosystem: str, dep_class: str, manifest: str) -> dict:
    return {
        "name": norm_name(name),
        "raw_name": name,
        "declared": spec,
        "syntax_class": classify(spec, ecosystem),
        "ecosystem": ecosystem,
        "dep_class": dep_class,
        "manifest": manifest,
    }


def iter_manifests(scope: str) -> list[Path]:
    """scope: live (product tree) or fixture (AUD-0025 planted manifests)."""
    found: list[Path] = []
    if scope == "fixture":
        root = HERE / "fixtures"
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn in {"pyproject.toml", "package.json"}:
                    found.append(Path(dirpath) / fn)
        return sorted(found)
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = Path(dirpath).relative_to(REPO).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        prefix = (rel_dir + "/") if rel_dir else ""
        if prefix.startswith(PROBES_PREFIX) or rel_dir.startswith(PROBES_PREFIX.rstrip("/")):
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn in {"pyproject.toml", "package.json", "setup.cfg"} or (
                fn.startswith("requirements") and fn.endswith(".txt")
            ):
                found.append(Path(dirpath) / fn)
    return sorted(found)


def collect(scope: str) -> list[dict]:
    rows: list[dict] = []
    for path in iter_manifests(scope):
        if path.name == "pyproject.toml":
            rows.extend(parse_pyproject(path))
        elif path.name == "package.json":
            rows.extend(parse_package_json(path))
    return [r for r in rows if r.get("name") != "__error__"]


def attach_resolution(rows: list[dict], index: dict) -> list[dict]:
    out = []
    for row in rows:
        rec = dict(row)
        dual = resolve_dual(row["name"], row["declared"], row["ecosystem"], index)
        rec.update(dual)
        from_v = dual.get("seed_lowest")
        rec["allows_new_major"] = allows_new_major(
            row["declared"], row["ecosystem"], from_v if isinstance(from_v, str) else None
        )
        rec["next_major_tested"] = (
            next_major(from_v) if isinstance(from_v, str) else None
        )
        rec["release_cadence"] = "NOT-CHECKED"
        rec["resolved_today"] = "NOT-CHECKED"
        rec["scope"] = row.get("scope") or (
            "fixture" if "/probes/AUD-0025/fixtures/" in row["manifest"] else "live"
        )
        out.append(rec)
    return out


def blast_for(row: dict, live_rows: list[dict]) -> dict:
    dependents = [
        r["manifest"]
        for r in live_rows
        if r["name"] == row["name"] and r.get("scope") == "live"
    ]
    allows = row.get("allows_new_major")
    if allows is True:
        impact = "accepted by declared constraint; no exclusive upper bound below next major"
    elif allows is False:
        impact = "constraint rejects next major; in-major float only (if any)"
    else:
        impact = "NOT-CHECKED"
    return {
        "live_declaration_count": len(dependents),
        "dependents": sorted(set(dependents)),
        "if_new_major": impact,
        "dep_class": row.get("dep_class"),
    }


def histogram(rows: list[dict]) -> dict[str, int]:
    c: Counter[str] = Counter(r["syntax_class"] for r in rows)
    return {k: int(c[k]) for k in sorted(c)}


def fixture_classifier_hits(rows: list[dict]) -> dict:
    """Every planted syntax-zoo row must land on its expected class."""
    by_key: dict[tuple[str, str], str] = {}
    for r in rows:
        man = r["manifest"]
        tail = man.split("/fixtures/")[-1] if "/fixtures/" in man else man
        by_key[(r["name"], tail)] = r["syntax_class"]
    missing = []
    wrong = []
    for key, want in FIXTURE_EXPECTED.items():
        got = by_key.get(key)
        if got is None:
            missing.append({"key": list(key), "want": want})
        elif got != want:
            wrong.append({"key": list(key), "want": want, "got": got})
    named_present = sorted(
        {by_key[k] for k in FIXTURE_EXPECTED if by_key.get(k) in NAMED_SYNTAX}
    )
    return {
        "missing": missing,
        "wrong": wrong,
        "named_classes_hit": named_present,
        "all_six_named": set(named_present) == set(NAMED_SYNTAX),
        "ok": not missing and not wrong and set(named_present) == set(NAMED_SYNTAX),
    }


def control_exact_and_float(fixture_rows: list[dict]) -> dict:
    exact = next(
        (
            r
            for r in fixture_rows
            if r["name"] == CONTROL_EXACT_NAME and r["syntax_class"] == "exact"
        ),
        None,
    )
    floating = next(
        (r for r in fixture_rows if r["name"] == CONTROL_FLOAT_NAME),
        None,
    )
    exact_same = bool(
        exact
        and exact.get("seed_lowest")
        and exact.get("seed_lowest") == exact.get("seed_highest")
        and exact.get("floats_in_practice") is False
    )
    float_differs = bool(
        floating
        and floating.get("seed_lowest")
        and floating.get("seed_lowest") != floating.get("seed_highest")
        and floating.get("floats_in_practice") is True
    )
    contaminated = bool(exact) and not exact_same
    return {
        "exact_row": _brief(exact) if exact else None,
        "float_row": _brief(floating) if floating else None,
        "exact_identical_across_seeds": exact_same,
        "float_differs_across_seeds": float_differs,
        "contaminated": contaminated,
        "ok": exact_same and float_differs and not contaminated,
    }


def _brief(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "name": row["name"],
        "declared": row["declared"],
        "syntax_class": row["syntax_class"],
        "seed_lowest": row.get("seed_lowest"),
        "seed_highest": row.get("seed_highest"),
        "floats_in_practice": row.get("floats_in_practice"),
        "allows_new_major": row.get("allows_new_major"),
    }


def live_findings(live_rows: list[dict]) -> list[dict]:
    findings = []
    for row in live_rows:
        item = {
            "name": row["name"],
            "raw_name": row.get("raw_name") or row["name"],
            "declared": row["declared"],
            "syntax_class": row["syntax_class"],
            "ecosystem": row["ecosystem"],
            "dep_class": row["dep_class"],
            "manifest": row["manifest"],
            "scope": "live",
            "floats_in_practice": row.get("floats_in_practice"),
            "seed_lowest": row.get("seed_lowest"),
            "seed_highest": row.get("seed_highest"),
            "allows_new_major": row.get("allows_new_major"),
            "next_major_tested": row.get("next_major_tested"),
            "matching_index_versions": row.get("matching") or [],
            "release_cadence": "NOT-CHECKED",
            "resolved_today": "NOT-CHECKED",
            "blast_radius": blast_for(row, live_rows),
        }
        findings.append(item)
    return findings


def census_doc() -> dict:
    index = load_index()
    live = attach_resolution(
        [{**r, "scope": "live"} for r in collect("live")], index
    )
    fixture = attach_resolution(
        [{**r, "scope": "fixture"} for r in collect("fixture")], index
    )
    findings = live_findings(live)
    floating = [
        f
        for f in findings
        if f.get("floats_in_practice") is True
    ]
    clf = fixture_classifier_hits(fixture)
    ctl = control_exact_and_float(fixture)
    hist = histogram(live + fixture)
    payload = {
        "live_manifest_count": len(iter_manifests("live")),
        "live_declaration_count": len(live),
        "fixture_declaration_count": len(fixture),
        "floating_in_practice_count": len(floating),
        "exact_live_count": sum(1 for r in live if r["syntax_class"] == "exact"),
        "syntax_histogram": hist,
        "syntax_histogram_live": histogram(live),
        "classifier_control": clf,
        "resolution_control": ctl,
        "live": [_brief(r) | {"manifest": r["manifest"], "dep_class": r["dep_class"]} for r in live],
        "fixture": [_brief(r) | {"manifest": r["manifest"]} for r in fixture],
        "floating_names": sorted({f["name"] for f in floating}),
        "findings": findings,
    }
    return payload


def probe1_payload() -> dict:
    doc = census_doc()
    return {
        "unit_id": UNIT,
        "probe": "probe1-constraint-syntax",
        "live_manifest_count": doc["live_manifest_count"],
        "live_declaration_count": doc["live_declaration_count"],
        "syntax_histogram": doc["syntax_histogram"],
        "syntax_histogram_live": doc["syntax_histogram_live"],
        "classifier_control": {
            "ok": doc["classifier_control"]["ok"],
            "named_classes_hit": doc["classifier_control"]["named_classes_hit"],
            "all_six_named": doc["classifier_control"]["all_six_named"],
            "missing": doc["classifier_control"]["missing"],
            "wrong": doc["classifier_control"]["wrong"],
        },
        "live": doc["live"],
        "fixture_classes": [
            {
                "name": r["name"],
                "declared": r["declared"],
                "syntax_class": r["syntax_class"],
                "manifest": r["manifest"],
            }
            for r in doc["fixture"]
        ],
    }


def named_probes_of(doc: dict) -> list:
    """named_probes live under report: receipt_core forbids extra top-level keys."""
    for src in (doc, doc.get("report") or {}, doc.get("extensions") or {}):
        if isinstance(src, dict):
            probes = src.get("named_probes")
            if isinstance(probes, list) and probes:
                return probes
    return []


def census_of(doc: dict) -> dict:
    for src in (doc, doc.get("report") or {}):
        if isinstance(src, dict) and isinstance(src.get("census"), dict) and src["census"]:
            return src["census"]
    return {}


def json_object(raw: str) -> dict:
    """Parse the first JSON object, ignoring a trailing SUCCESS line."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty raw_output")
    obj, _ = json.JSONDecoder().raw_decode(text)
    if not isinstance(obj, dict):
        raise ValueError("raw_output is not a JSON object")
    return obj


def probe2_payload() -> dict:
    doc = census_doc()
    ctl = doc["resolution_control"]
    return {
        "unit_id": UNIT,
        "probe": "probe2-dual-resolution",
        "seeds": ["lowest", "highest"],
        "index": INDEX_REL,
        "floating_in_practice_count": doc["floating_in_practice_count"],
        "floating_names": doc["floating_names"],
        "resolution_control": {
            "ok": ctl["ok"],
            "exact_identical_across_seeds": ctl["exact_identical_across_seeds"],
            "float_differs_across_seeds": ctl["float_differs_across_seeds"],
            "contaminated": ctl["contaminated"],
            "exact_row": ctl["exact_row"],
            "float_row": ctl["float_row"],
        },
        "live_dual": [
            {
                "name": r["name"],
                "declared": r["declared"],
                "manifest": r["manifest"],
                "seed_lowest": r.get("seed_lowest"),
                "seed_highest": r.get("seed_highest"),
                "floats_in_practice": r.get("floats_in_practice"),
                "allows_new_major": r.get("allows_new_major"),
            }
            for r in doc["live"]
        ],
    }
