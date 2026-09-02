"""Shared ADV-0062 rebuild experiments.

The historical shipped zip at platform/plugin/dist/ast-integrate-platform-1.0.0.zip
is absent on this worktree. The unit therefore attests the live tools/plugin
tree, records source_revision + toolchain, packs a release, and rebuilds it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from packager import (
    CANONICAL_EPOCH,
    CANONICAL_LEVEL,
    CANONICAL_ORDER,
    compare_archives,
    dump_zip,
    sha256_bytes,
    source_revision,
    toolchain,
    write_zip,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HISTORICAL_ZIP = "platform/plugin/dist/ast-integrate-platform-1.0.0.zip"
PLUGIN_MEMBERS = (
    "tools/plugin/__init__.py",
    "tools/plugin/manifest_loader.py",
    "tools/plugin/permission_diff.py",
    "tools/plugin/rollback_additive.py",
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0062/probe1_rebuild_compare.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0062/probe2_causal_attribution.py"
)


def plugin_json_bytes(version: str = "1.0.0") -> bytes:
    body = {
        "name": "ast-integrate-platform",
        "permissions": ["fs:read:/pkg"],
        "version": version,
    }
    return (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_source_members(*, mutant_version: str | None = None) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    for rel in PLUGIN_MEMBERS:
        path = REPO / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        members[rel] = path.read_bytes()
    version = mutant_version or "1.0.0"
    members["plugin.json"] = plugin_json_bytes(version)
    return members


def with_provenance(members: dict[str, bytes], *, epoch: int, compresslevel: int, order: str) -> dict[str, bytes]:
    payload = {k: v for k, v in members.items() if k != "PROVENANCE.json"}
    prov = {
        "unit_id": "ADV-0062",
        "package": "ast-integrate-platform",
        "source_revision": source_revision(payload),
        "toolchain": toolchain(epoch=epoch, compresslevel=compresslevel, order=order),
        "member_paths": sorted(payload),
    }
    out = dict(payload)
    out["PROVENANCE.json"] = (
        json.dumps(prov, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return out


def pack(
    members: dict[str, bytes],
    dest: Path,
    *,
    epoch: int = CANONICAL_EPOCH,
    compresslevel: int = CANONICAL_LEVEL,
    order: str = CANONICAL_ORDER,
    locale: str | None = None,
    provenance_bytes: bytes | None = None,
) -> bytes:
    dest.parent.mkdir(parents=True, exist_ok=True)
    saved = None
    if locale is not None:
        saved = {k: os.environ.get(k) for k in ("LC_ALL", "LANG", "LC_CTYPE")}
        os.environ["LC_ALL"] = locale
        os.environ["LANG"] = locale
        os.environ["LC_CTYPE"] = locale
    try:
        if provenance_bytes is None:
            payload = with_provenance(
                members, epoch=epoch, compresslevel=compresslevel, order=order
            )
        else:
            payload = {k: v for k, v in members.items() if k != "PROVENANCE.json"}
            payload["PROVENANCE.json"] = provenance_bytes
        data = write_zip(
            payload, epoch=epoch, compresslevel=compresslevel, order=order
        )
    finally:
        if saved is not None:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    dump_zip(dest, data)
    return data


def historical_zip_state() -> dict:
    path = REPO / HISTORICAL_ZIP
    if not path.is_file():
        return {
            "path": HISTORICAL_ZIP,
            "present": False,
            "bytes": 0,
            "sha256": None,
            "note": "absent on this worktree; prior Windows harvest cited sha256 af62a8836abc4f73e2a6a529dab7ea5e09b7e0828183a7caa3a08965b3067b04",
        }
    raw = path.read_bytes()
    return {
        "path": HISTORICAL_ZIP,
        "present": True,
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "note": "present; compare is a separate target",
    }


def run_rebuild_compare() -> dict:
    work = HERE / "probe1-work"
    work.mkdir(parents=True, exist_ok=True)
    members = load_source_members()
    payload = with_provenance(
        members, epoch=CANONICAL_EPOCH, compresslevel=CANONICAL_LEVEL, order=CANONICAL_ORDER
    )
    src_rev = source_revision({k: v for k, v in payload.items() if k != "PROVENANCE.json"})
    tc = toolchain(
        epoch=CANONICAL_EPOCH, compresslevel=CANONICAL_LEVEL, order=CANONICAL_ORDER
    )
    release = pack(members, work / "build-a" / "ast-integrate-platform-1.0.0.zip")
    rebuild_b = pack(members, work / "build-b" / "ast-integrate-platform-1.0.0.zip")
    rebuild_c = pack(members, work / "build-c" / "ast-integrate-platform-1.0.0.zip")
    mutant_members = load_source_members(mutant_version="9.9.9-mutant")
    mutant = pack(mutant_members, work / "build-mutant" / "ast-integrate-platform-1.0.0.zip")
    ident_ab = compare_archives(release, rebuild_b)
    ident_bc = compare_archives(rebuild_b, rebuild_c)
    vs_mutant = compare_archives(release, mutant)
    hist = historical_zip_state()
    identical_env = (
        ident_ab["byte_identical"]
        and ident_bc["byte_identical"]
        and ident_ab["left_sha256"] == ident_bc["left_sha256"]
    )
    comparator_red = (not vs_mutant["byte_identical"]) and bool(
        vs_mutant["differing_members"] or vs_mutant["only_left"] or vs_mutant["only_right"]
    )
    vs_hist = None
    if hist["present"]:
        vs_hist = compare_archives(release, (REPO / HISTORICAL_ZIP).read_bytes())
    result = {
        "probe": "probe1-rebuild-compare",
        "source_revision": src_rev,
        "toolchain": tc,
        "release_sha256": ident_ab["left_sha256"],
        "release_bytes": ident_ab["left_bytes"],
        "rebuild_b_sha256": ident_ab["right_sha256"],
        "rebuild_c_sha256": ident_bc["right_sha256"],
        "identical_environment_rebuilds_match": identical_env,
        "attested_rebuild_byte_identical": ident_ab["byte_identical"] and identical_env,
        "member_diff_release_vs_rebuild": ident_ab,
        "mutant_sha256": vs_mutant["right_sha256"],
        "comparator_fires_on_source_mutant": comparator_red,
        "silent_on_good_identical_rebuild": identical_env,
        "historical_zip": hist,
        "historical_compare": vs_hist,
        "package_measurement": {
            "artifact": "ast-integrate-platform-1.0.0.zip",
            "package": "ast-integrate-platform",
            "archive_bytes": ident_ab["left_bytes"],
            "archive_sha256": ident_ab["left_sha256"],
            "member_count": ident_ab["member_count_left"],
            "source_revision": src_rev,
            "toolchain": tc,
            "package_measurement_binds_digest": True,
            "package_measurement_has_source_revision": True,
            "package_measurement_has_toolchain": True,
        },
        "pass": identical_env and comparator_red,
    }
    (HERE / "probe1-measurement.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def run_causal_attribution() -> dict:
    work = HERE / "probe2-work"
    work.mkdir(parents=True, exist_ok=True)
    members = load_source_members()
    canonical_payload = with_provenance(
        members,
        epoch=CANONICAL_EPOCH,
        compresslevel=CANONICAL_LEVEL,
        order=CANONICAL_ORDER,
    )
    frozen_prov = canonical_payload["PROVENANCE.json"]
    canonical = pack(members, work / "canonical" / "ast-integrate-platform-1.0.0.zip")
    cases = []

    ts = pack(
        members,
        work / "timestamp-variant.zip",
        epoch=CANONICAL_EPOCH + 3600,
        provenance_bytes=frozen_prov,
    )
    cmp_ts = compare_archives(canonical, ts)
    cases.append(
        {
            "variable": "embedded-timestamp",
            "knob": "SOURCE_DATE_EPOCH+3600",
            "causes_byte_diff": not cmp_ts["byte_identical"],
            "compare": {
                "byte_identical": cmp_ts["byte_identical"],
                "left_sha256": cmp_ts["left_sha256"],
                "right_sha256": cmp_ts["right_sha256"],
                "differing_members_head": cmp_ts["differing_members"][:8],
                "member_order_differs": cmp_ts["member_order_differs"],
            },
        }
    )

    order = pack(
        members,
        work / "ordering-variant.zip",
        order="reverse",
        provenance_bytes=frozen_prov,
    )
    cmp_ord = compare_archives(canonical, order)
    cases.append(
        {
            "variable": "file-ordering",
            "knob": "member_order=reverse",
            "causes_byte_diff": not cmp_ord["byte_identical"],
            "compare": {
                "byte_identical": cmp_ord["byte_identical"],
                "left_sha256": cmp_ord["left_sha256"],
                "right_sha256": cmp_ord["right_sha256"],
                "member_order_differs": cmp_ord["member_order_differs"],
                "differing_members_head": cmp_ord["differing_members"][:8],
            },
        }
    )

    lvl1 = pack(
        members,
        work / "release-content-level1.zip",
        compresslevel=1,
        provenance_bytes=frozen_prov,
    )
    lvl9 = pack(
        members,
        work / "release-content-level9.zip",
        compresslevel=9,
        provenance_bytes=frozen_prov,
    )
    cmp_l1 = compare_archives(canonical, lvl1)
    cmp_l9 = compare_archives(canonical, lvl9)
    cases.append(
        {
            "variable": "compressor-level",
            "knob": "compresslevel 6 vs 1 and 9",
            "causes_byte_diff": (not cmp_l1["byte_identical"]) or (not cmp_l9["byte_identical"]),
            "level1_differs": not cmp_l1["byte_identical"],
            "level9_differs": not cmp_l9["byte_identical"],
            "compare_level1": {
                "byte_identical": cmp_l1["byte_identical"],
                "right_sha256": cmp_l1["right_sha256"],
            },
            "compare_level9": {
                "byte_identical": cmp_l9["byte_identical"],
                "right_sha256": cmp_l9["right_sha256"],
            },
        }
    )

    loc_c = pack(
        members,
        work / "locale-C" / "ast-integrate-platform-1.0.0.zip",
        locale="C",
        provenance_bytes=frozen_prov,
    )
    loc_utf = pack(
        members,
        work / "locale-UTF8" / "ast-integrate-platform-1.0.0.zip",
        locale="C.UTF-8",
        provenance_bytes=frozen_prov,
    )
    cmp_loc = compare_archives(loc_c, loc_utf)
    cmp_loc_can = compare_archives(canonical, loc_c)
    cases.append(
        {
            "variable": "locale",
            "knob": "LC_ALL=C vs C.UTF-8",
            "causes_byte_diff": not cmp_loc["byte_identical"],
            "differs_from_canonical": not cmp_loc_can["byte_identical"],
            "compare": {
                "byte_identical": cmp_loc["byte_identical"],
                "left_sha256": cmp_loc["left_sha256"],
                "right_sha256": cmp_loc["right_sha256"],
            },
        }
    )

    path_a = pack(
        members,
        work / "path-A" / "out" / "ast-integrate-platform-1.0.0.zip",
        provenance_bytes=frozen_prov,
    )
    path_b = pack(
        members,
        work / "path-B" / "out" / "ast-integrate-platform-1.0.0.zip",
        provenance_bytes=frozen_prov,
    )
    cmp_path = compare_archives(path_a, path_b)
    cases.append(
        {
            "variable": "build-path",
            "knob": "distinct output directories path-A vs path-B",
            "causes_byte_diff": not cmp_path["byte_identical"],
            "compare": {
                "byte_identical": cmp_path["byte_identical"],
                "left_sha256": cmp_path["left_sha256"],
                "right_sha256": cmp_path["right_sha256"],
            },
        }
    )

    # Timestamp mutant is the both-states partner of the source mutant in probe 1:
    # good identical rebuilds already ran; this probe shows timestamp alone goes red.
    timestamp_fires = any(c["variable"] == "embedded-timestamp" and c["causes_byte_diff"] for c in cases)
    ordering_fires = any(c["variable"] == "file-ordering" and c["causes_byte_diff"] for c in cases)
    compressor_fires = any(c["variable"] == "compressor-level" and c["causes_byte_diff"] for c in cases)
    path_silent = any(c["variable"] == "build-path" and not c["causes_byte_diff"] for c in cases)
    result = {
        "probe": "probe2-causal-attribution",
        "canonical_sha256": sha256_bytes(canonical),
        "cases": cases,
        "classified": {
            "embedded-timestamp": "causes-diff" if timestamp_fires else "no-diff",
            "file-ordering": "causes-diff" if ordering_fires else "no-diff",
            "compressor-level": "causes-diff" if compressor_fires else "no-diff",
            "locale": next(
                "causes-diff" if c["causes_byte_diff"] else "no-diff"
                for c in cases
                if c["variable"] == "locale"
            ),
            "build-path": "causes-diff" if not path_silent else "no-diff",
        },
        "timestamp_mutant_fires": timestamp_fires,
        "identical_path_rebuild_silent": path_silent,
        "pass": timestamp_fires and ordering_fires and path_silent,
    }
    (HERE / "probe2-measurement.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
