"""ADV-0058 helpers: planted shipped zip, artifact enumeration, SBOM set-diff."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART_REL = "command-center/adversarial/ADV-0058-sbom-completeness-planted-transitive.json"
ART = REPO / ART_REL
SCHEMA_REL = "command-center/schema/supply-chain-attestation.schema.json"
ZIP_REL = "command-center/p2-wave/probes/ADV-0058/fixtures/adv0058-shipped-artifact.zip"
ZIP_PATH = REPO / ZIP_REL
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0058 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0058 <reason>."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0058/probe1_artifact_setdiff.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0058/probe2_direct_plant.py"
)
CTRL_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0058/control_enumerator.py"
)
QUESTION = (
    "Does the SBOM list every component actually present in the shipped "
    "artifact, including transitive, vendored, bundled-binary and "
    "runtime-downloaded components?"
)

APP_PURL = "pkg:npm/adv0058-app@1.0.0"
DECLARED_PURL = "pkg:npm/declared-normal@2.3.4"
VENDORED_PURL = "pkg:npm/stealth-transitive@7.8.9"
RUNTIME_PURL = "pkg:npm/runtime-fetched-helper@4.5.6"
WHEEL_PURL = "pkg:pypi/bundled-wheel-helper@3.2.1"
NATIVE_PURL = "pkg:generic/native-helper@9.1.0"
NATIVE_MARKER = b"ADV0058_NATIVE pkg:generic/native-helper@9.1.0"
PLANTED_PURLS = (VENDORED_PURL, RUNTIME_PURL, WHEEL_PURL, NATIVE_PURL)

ZIP_STAMP = (2026, 8, 24, 20, 0, 0)

GENERATOR_CONFIG = {
    "generator": "adv0058-manifest-only-cyclonedx",
    "inputs": ["package.json", "package-lock.json"],
    "include_node_modules": True,
    "include_vendor": False,
    "include_cache": False,
    "include_wheels": False,
    "include_native": False,
    "note": (
        "Walks the package manifest and node_modules only. Vendored trees, "
        "runtime-download caches, bundled wheels and native binaries are "
        "outside the configured walk."
    ),
}


def _json_bytes(doc: Any) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _add(zf: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(filename=name.replace("\\", "/"), date_time=ZIP_STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def _make_wheel() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as inner:
        _add(
            inner,
            "bundled_wheel_helper-3.2.1.dist-info/METADATA",
            (
                "Metadata-Version: 2.1\n"
                "Name: bundled-wheel-helper\n"
                "Version: 3.2.1\n"
                "Summary: ADV-0058 planted bundled wheel, undeclared in SBOM\n"
            ).encode("utf-8"),
        )
        _add(
            inner,
            "bundled_wheel_helper-3.2.1.dist-info/WHEEL",
            (
                "Wheel-Version: 1.0\n"
                "Generator: adv0058\n"
                "Root-Is-Purelib: true\n"
                "Tag: py3-none-any\n"
            ).encode("utf-8"),
        )
        _add(
            inner,
            "bundled_wheel_helper/__init__.py",
            b'PLANTED = True\nPURL = "pkg:pypi/bundled-wheel-helper@3.2.1"\n',
        )
    return buf.getvalue()


def fixture_members() -> dict[str, bytes]:
    """Deterministic shipped-archive contents."""
    pkg_root = {
        "name": "adv0058-app",
        "version": "1.0.0",
        "private": True,
        "dependencies": {"declared-normal": "2.3.4"},
    }
    lock = {
        "name": "adv0058-app",
        "version": "1.0.0",
        "lockfileVersion": 2,
        "packages": {
            "": {"name": "adv0058-app", "version": "1.0.0", "dependencies": {"declared-normal": "2.3.4"}},
            "node_modules/declared-normal": {
                "name": "declared-normal",
                "version": "2.3.4",
            },
        },
        "dependencies": {
            "declared-normal": {"version": "2.3.4"},
        },
    }
    sbom = generate_sbom_document({APP_PURL, DECLARED_PURL})
    return {
        "package.json": _json_bytes(pkg_root),
        "package-lock.json": _json_bytes(lock),
        "sbom.cdx.json": _json_bytes(sbom),
        "sbom-generator-config.json": _json_bytes(GENERATOR_CONFIG),
        "README.md": (
            "# adv0058-app\n\n"
            "Shipped fixture for ADV-0058. The SBOM generator walks only\n"
            "package.json / package-lock.json / node_modules. Planted paths:\n"
            "- vendor/stealth-transitive (undeclared vendored transitive)\n"
            "- .cache/runtime-download/runtime-fetched-helper (runtime download)\n"
            "- vendor/wheels/*.whl (bundled wheel)\n"
            "- bin/native-helper (bundled native binary)\n"
        ).encode("utf-8"),
        "node_modules/declared-normal/package.json": _json_bytes(
            {"name": "declared-normal", "version": "2.3.4", "license": "MIT"}
        ),
        "node_modules/declared-normal/index.js": b"module.exports = {ok: true};\n",
        "vendor/stealth-transitive/package.json": _json_bytes(
            {
                "name": "stealth-transitive",
                "version": "7.8.9",
                "description": "ADV-0058 planted vendored transitive",
            }
        ),
        "vendor/stealth-transitive/index.js": b"module.exports = {planted: true};\n",
        "vendor/stealth-transitive/PLANTED-MARKER.txt": (
            "ADV0058_PLANTED_VENDORED pkg:npm/stealth-transitive@7.8.9\n"
        ).encode("utf-8"),
        ".cache/runtime-download/runtime-fetched-helper/package.json": _json_bytes(
            {
                "name": "runtime-fetched-helper",
                "version": "4.5.6",
                "description": "ADV-0058 planted runtime-downloaded helper",
            }
        ),
        ".cache/runtime-download/runtime-fetched-helper/PLANTED-MARKER.txt": (
            "ADV0058_PLANTED_RUNTIME pkg:npm/runtime-fetched-helper@4.5.6\n"
        ).encode("utf-8"),
        "vendor/wheels/bundled_wheel_helper-3.2.1-py3-none-any.whl": _make_wheel(),
        "bin/native-helper": b"\x7fELF" + b"\x00" * 16 + NATIVE_MARKER + b"\n",
    }


def ensure_fixture() -> Path:
    members = fixture_members()
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(members):
            _add(zf, name, members[name])
    raw = buf.getvalue()
    if not ZIP_PATH.is_file() or ZIP_PATH.read_bytes() != raw:
        ZIP_PATH.write_bytes(raw)
    return ZIP_PATH


def zip_namelist(path: Path | None = None) -> list[str]:
    path = path or ensure_fixture()
    with zipfile.ZipFile(path) as zf:
        return sorted(n.replace("\\", "/") for n in zf.namelist())


def zip_read(name: str, path: Path | None = None) -> bytes:
    path = path or ensure_fixture()
    with zipfile.ZipFile(path) as zf:
        return zf.read(name)


def generate_sbom_document(purls: set[str]) -> dict[str, Any]:
    """Manifest-only CycloneDX: root application plus listed libraries."""
    comps = []
    for purl in sorted(p for p in purls if p != APP_PURL):
        name, version = _split_npm_or_other(purl)
        comps.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": purl,
                "bom-ref": purl,
            }
        )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:00000000-0000-4000-a000-000000000058",
        "version": 1,
        "metadata": {
            "tools": [{"name": GENERATOR_CONFIG["generator"], "version": "1.0.0"}],
            "component": {
                "type": "application",
                "name": "adv0058-app",
                "version": "1.0.0",
                "purl": APP_PURL,
                "bom-ref": APP_PURL,
            },
        },
        "components": comps,
    }


def _split_npm_or_other(purl: str) -> tuple[str, str]:
    body = purl.split("pkg:", 1)[-1]
    _eco, rest = body.split("/", 1)
    if "@" in rest:
        name, version = rest.rsplit("@", 1)
        version = version.split("?", 1)[0]
        return name, version
    return rest, ""


def _parse_package_json(raw: bytes) -> tuple[str, str] | None:
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    name = str(doc.get("name") or "").strip()
    version = str(doc.get("version") or "").strip()
    if not name or not version:
        return None
    return name, version


def _parse_wheel_metadata(raw: bytes) -> tuple[str, str] | None:
    name = ""
    version = ""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as inner:
            for member in inner.namelist():
                posix = member.replace("\\", "/")
                if posix.endswith(".dist-info/METADATA"):
                    text = inner.read(member).decode("utf-8", errors="replace")
                    for line in text.splitlines():
                        if line.lower().startswith("name:"):
                            name = line.split(":", 1)[1].strip()
                        elif line.lower().startswith("version:"):
                            version = line.split(":", 1)[1].strip()
    except zipfile.BadZipFile:
        return None
    if name and version:
        return name, version
    return None


def enumerate_artifact_components(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Ground-truth component set from the shipped archive bytes."""
    path = path or ensure_fixture()
    found: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            posix = name.replace("\\", "/")
            if posix.endswith("/") or posix.endswith("\\"):
                continue
            data = zf.read(name)
            if posix.endswith("package.json"):
                parsed = _parse_package_json(data)
                if parsed:
                    pkg, ver = parsed
                    purl = f"pkg:npm/{pkg}@{ver}"
                    kind = "application" if purl == APP_PURL else "npm-package"
                    if posix.startswith("vendor/"):
                        kind = "vendored-transitive"
                    elif posix.startswith(".cache/"):
                        kind = "runtime-download"
                    elif posix.startswith("node_modules/"):
                        kind = "declared-direct"
                    found[purl] = {"purl": purl, "kind": kind, "path": posix}
            elif posix.endswith(".whl"):
                parsed = _parse_wheel_metadata(data)
                if parsed:
                    pkg, ver = parsed
                    purl = f"pkg:pypi/{pkg}@{ver}"
                    found[purl] = {
                        "purl": purl,
                        "kind": "bundled-wheel",
                        "path": posix,
                    }
            if NATIVE_MARKER in data:
                found[NATIVE_PURL] = {
                    "purl": NATIVE_PURL,
                    "kind": "bundled-native-binary",
                    "path": posix,
                }
    return found


def enumerate_manifest_only(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Mutant enumerator: package.json + node_modules only (generator walk)."""
    path = path or ensure_fixture()
    found: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            posix = name.replace("\\", "/")
            if not posix.endswith("package.json"):
                continue
            if posix.startswith("vendor/") or posix.startswith(".cache/"):
                continue
            parsed = _parse_package_json(zf.read(name))
            if not parsed:
                continue
            pkg, ver = parsed
            purl = f"pkg:npm/{pkg}@{ver}"
            kind = "application" if purl == APP_PURL else "declared-direct"
            found[purl] = {"purl": purl, "kind": kind, "path": posix}
    return found


def load_sbom_purls(path: Path | None = None) -> set[str]:
    path = path or ensure_fixture()
    doc = json.loads(zip_read("sbom.cdx.json", path).decode("utf-8"))
    purls: set[str] = set()
    meta = doc.get("metadata") or {}
    root = meta.get("component") or {}
    if isinstance(root, dict) and root.get("purl"):
        purls.add(str(root["purl"]))
    for comp in doc.get("components") or []:
        if isinstance(comp, dict) and comp.get("purl"):
            purls.add(str(comp["purl"]))
    return purls


def generator_config(path: Path | None = None) -> dict[str, Any]:
    path = path or ensure_fixture()
    return json.loads(zip_read("sbom-generator-config.json", path).decode("utf-8"))


def setdiff(path: Path | None = None) -> dict[str, Any]:
    """Probe 1: unpack/identify every component, set-difference against the SBOM."""
    path = path or ensure_fixture()
    artifact = enumerate_artifact_components(path)
    sbom = load_sbom_purls(path)
    art_set = set(artifact)
    missing = sorted(art_set - sbom)
    extra = sorted(sbom - art_set)
    both = sorted(art_set & sbom)
    declared_ok = DECLARED_PURL in art_set and DECLARED_PURL in sbom
    plants_in_artifact = [p for p in PLANTED_PURLS if p in art_set]
    plants_in_sbom = [p for p in PLANTED_PURLS if p in sbom]
    zero_diff = not missing and not extra
    enumeration_broken = zero_diff and (not plants_in_artifact)
    return {
        "probe": "probe1-artifact-setdiff",
        "unit_id": "ADV-0058",
        "zip": ZIP_REL,
        "artifact_purls": sorted(art_set),
        "sbom_purls": sorted(sbom),
        "in_both": both,
        "present_in_artifact_absent_from_sbom": missing,
        "listed_in_sbom_absent_from_artifact": extra,
        "zero_difference": zero_diff,
        "declared_in_both": declared_ok,
        "plants_in_artifact": plants_in_artifact,
        "plants_in_sbom": plants_in_sbom,
        "enumeration_broken": enumeration_broken,
        "components": [artifact[p] for p in sorted(artifact)],
        "pass": declared_ok and (not enumeration_broken) and bool(plants_in_artifact),
    }


def plant_check(path: Path | None = None) -> dict[str, Any]:
    """Probe 2: confirm planted files exist in the zip, then ask the SBOM."""
    path = path or ensure_fixture()
    names = set(zip_namelist(path))
    sbom = load_sbom_purls(path)
    rows = []
    plants = (
        (
            VENDORED_PURL,
            "vendor/stealth-transitive/PLANTED-MARKER.txt",
            "vendored-subdirectory",
        ),
        (
            RUNTIME_PURL,
            ".cache/runtime-download/runtime-fetched-helper/PLANTED-MARKER.txt",
            "runtime-download-cache",
        ),
        (
            WHEEL_PURL,
            "vendor/wheels/bundled_wheel_helper-3.2.1-py3-none-any.whl",
            "bundled-wheel",
        ),
        (NATIVE_PURL, "bin/native-helper", "bundled-native-binary"),
    )
    for purl, marker, channel in plants:
        in_zip = marker in names
        if in_zip and purl == NATIVE_PURL:
            in_zip = NATIVE_MARKER in zip_read(marker, path)
        if in_zip and purl == WHEEL_PURL:
            parsed = _parse_wheel_metadata(zip_read(marker, path))
            in_zip = parsed == ("bundled-wheel-helper", "3.2.1")
        listed = purl in sbom
        rows.append(
            {
                "purl": purl,
                "channel": channel,
                "marker_path": marker,
                "present_in_artifact": in_zip,
                "listed_in_sbom": listed,
                "missed_by_sbom": in_zip and not listed,
            }
        )
    missed = [r["purl"] for r in rows if r["missed_by_sbom"]]
    all_present = all(r["present_in_artifact"] for r in rows)
    none_listed = not any(r["listed_in_sbom"] for r in rows)
    cfg = generator_config(path)
    generator_skips_plants = (
        cfg.get("include_vendor") is False
        and cfg.get("include_cache") is False
        and cfg.get("include_wheels") is False
        and cfg.get("include_native") is False
    )
    return {
        "probe": "probe2-direct-plant",
        "unit_id": "ADV-0058",
        "zip": ZIP_REL,
        "independent_of_probe1_setdiff": True,
        "plants": rows,
        "plants_present_in_artifact": all_present,
        "plants_listed_in_sbom": [r["purl"] for r in rows if r["listed_in_sbom"]],
        "plants_missed_by_sbom": missed,
        "generator_configured_to_skip_plant_paths": generator_skips_plants,
        "manifest_only_generator_would_report_success": none_listed and all_present,
        "pass": all_present and bool(missed) and generator_skips_plants,
    }


def negative_control(path: Path | None = None) -> dict[str, Any]:
    """Manifest-only mutant: zero-diff vs SBOM while plants sit in the zip."""
    path = path or ensure_fixture()
    mutant = set(enumerate_manifest_only(path))
    full = set(enumerate_artifact_components(path))
    sbom = load_sbom_purls(path)
    mutant_missing = sorted(mutant - sbom)
    mutant_extra = sorted(sbom - mutant)
    mutant_zero = not mutant_missing and not mutant_extra
    plants_in_full = [p for p in PLANTED_PURLS if p in full]
    plants_in_mutant = [p for p in PLANTED_PURLS if p in mutant]
    fired = mutant_zero and bool(plants_in_full) and not plants_in_mutant
    good_zero = not (set(full) - sbom) and not (sbom - set(full))
    silent_on_good = (not good_zero) and bool(plants_in_full)
    return {
        "id": "NC-MANIFEST-ONLY-ZERO-DIFFERENCE",
        "name": (
            "A generator that reads the manifest rather than the artifact "
            "reports success (zero-diff) while missing planted components"
        ),
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent_on_good,
        "pass": fired and silent_on_good,
        "mutant_purls": sorted(mutant),
        "mutant_zero_difference": mutant_zero,
        "plants_in_full_enumeration": plants_in_full,
        "plants_in_mutant": plants_in_mutant,
        "summary": (
            "Manifest-only walk matches the SBOM exactly and omits every "
            "planted component that the full archive walk finds."
        ),
    }


def declared_control(path: Path | None = None) -> dict[str, Any]:
    """Catalog control: declared-normal in both sets; zero-diff+missed plant is broken."""
    diff = setdiff(path)
    ok = bool(diff["declared_in_both"]) and not diff["enumeration_broken"]
    return {
        "id": "T-DECLARED-DEPENDENCY-CONTROL",
        "name": (
            "control: a normally declared dependency must appear in both sets; "
            "a zero-difference result that also misses the planted component "
            "means the artifact enumeration is not working"
        ),
        "pass": ok,
        "declared_in_both": diff["declared_in_both"],
        "zero_difference": diff["zero_difference"],
        "enumeration_broken": diff["enumeration_broken"],
        "plants_in_artifact": diff["plants_in_artifact"],
    }


def target_verdicts(
    diff: dict[str, Any], plants: dict[str, Any]
) -> list[dict[str, Any]]:
    """Per-target: CONFIRMED = listed in SBOM, REFUTED = present but unlisted."""
    art = set(diff["artifact_purls"])
    sbom = set(diff["sbom_purls"])

    def listed(purl: str) -> str:
        if purl not in art:
            return "NOT-CHECKED"
        return "CONFIRMED" if purl in sbom else "REFUTED"

    complete = (not diff["present_in_artifact_absent_from_sbom"]) and bool(art)
    plant_miss = bool(plants["plants_missed_by_sbom"])
    return [
        {
            "target_id": "T0-universal-completeness",
            "target": "every identified artifact component is billed in the SBOM",
            "verdict": "CONFIRMED" if complete else "REFUTED",
            "missing": diff["present_in_artifact_absent_from_sbom"],
        },
        {
            "target_id": "T1-application",
            "target": APP_PURL,
            "verdict": listed(APP_PURL),
        },
        {
            "target_id": "T2-declared-control",
            "target": DECLARED_PURL,
            "verdict": listed(DECLARED_PURL),
        },
        {
            "target_id": "T3-vendored-transitive",
            "target": VENDORED_PURL,
            "verdict": listed(VENDORED_PURL),
            "channel": "vendored-subdirectory",
        },
        {
            "target_id": "T4-runtime-downloaded-cache",
            "target": RUNTIME_PURL,
            "verdict": listed(RUNTIME_PURL),
            "channel": "runtime-download",
        },
        {
            "target_id": "T5-bundled-wheel",
            "target": WHEEL_PURL,
            "verdict": listed(WHEEL_PURL),
            "channel": "bundled-wheel",
        },
        {
            "target_id": "T6-bundled-native-binary",
            "target": NATIVE_PURL,
            "verdict": listed(NATIVE_PURL),
            "channel": "bundled-native-binary",
        },
        {
            "target_id": "T7-manifest-only-generator-misses-plants",
            "target": "generator that reads the manifest reports success while missing plants",
            "verdict": "CONFIRMED" if plant_miss else "REFUTED",
            "missed": plants["plants_missed_by_sbom"],
        },
    ]


def live_bundle() -> dict[str, Any]:
    ensure_fixture()
    diff = setdiff()
    plants = plant_check()
    ctrl = declared_control()
    nc = negative_control()
    targets = target_verdicts(diff, plants)
    return {
        "diff": diff,
        "plants": plants,
        "declared_control": ctrl,
        "negative_control": nc,
        "targets": targets,
    }
