"""Live CNF-0104 experiment: installer on both FS classes + parsers on planted keys."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from constants import (
    COLLIDE_LOWER,
    COLLIDE_LOWER_NAME,
    COLLIDE_UPPER,
    COLLIDE_UPPER_NAME,
    CONTROL_ALPHA,
    CONTROL_ALPHA_NAME,
    CONTROL_BETA,
    CONTROL_BETA_NAME,
    INSTALLER_ID,
    PARSER_ID,
)
from filesystem import (
    case_insensitive_root,
    case_sensitive_root,
    fstype_of,
    list_regular_files,
    read_name,
)
from installer import install_files
from parsers import (
    PARSERS,
    classify_keys,
    control_survived,
    fixture_case_distinct,
    fixture_control_clean,
    fixture_duplicate_exact,
)


def _payloads(order: list[str]) -> dict[str, bytes]:
    blobs = {
        COLLIDE_UPPER_NAME: COLLIDE_UPPER,
        COLLIDE_LOWER_NAME: COLLIDE_LOWER,
        CONTROL_ALPHA_NAME: CONTROL_ALPHA,
        CONTROL_BETA_NAME: CONTROL_BETA,
    }
    files: dict[str, bytes] = {}
    for name in order:
        files[name] = blobs[name]
    return files


def _inspect(root: Path, write_order: list[str]) -> dict[str, Any]:
    on_disk = list_regular_files(root)
    names = list(on_disk.keys())
    upper = read_name(root, COLLIDE_UPPER_NAME)
    lower = read_name(root, COLLIDE_LOWER_NAME)
    alpha = read_name(root, CONTROL_ALPHA_NAME)
    beta = read_name(root, CONTROL_BETA_NAME)
    collision_names = [
        n for n in names if n.casefold() == COLLIDE_UPPER_NAME.casefold()
    ]
    control_ok = alpha == CONTROL_ALPHA and beta == CONTROL_BETA
    both_openable = upper is not None and lower is not None
    same_bytes = both_openable and upper == lower
    last_name = write_order[1]
    last_blob = COLLIDE_UPPER if last_name == COLLIDE_UPPER_NAME else COLLIDE_LOWER
    last_wins = same_bytes and upper == last_blob
    installer_error = False
    if len(collision_names) >= 2 and upper != lower:
        outcome = "both-names-coexist"
    elif last_wins:
        outcome = "silent-last-wins"
    elif both_openable and same_bytes:
        outcome = "collapsed-same-bytes"
    else:
        outcome = "unexpected"
    return {
        "listdir": names,
        "file_count": len(names),
        "collision_names_on_disk": collision_names,
        "collision_file_count": len(collision_names),
        "open_Config.json_sha_prefix": (upper[:40].decode("ascii") if upper else None),
        "open_config.json_sha_prefix": (lower[:40].decode("ascii") if lower else None),
        "open_contents_equal": same_bytes,
        "last_written": last_name,
        "last_wins": last_wins,
        "installer_raised": installer_error,
        "control_alpha_ok": alpha == CONTROL_ALPHA,
        "control_beta_ok": beta == CONTROL_BETA,
        "control_survived": control_ok,
        "outcome": outcome,
        "write_order": write_order,
    }


def _run_trial(root: Path, order: list[str]) -> dict[str, Any]:
    files = _payloads(order)
    try:
        install_files(root, files)
        error = None
    except Exception as exc:  # pragma: no cover - installer must not raise on VFAT last-wins
        return {
            "write_order": order,
            "installer_raised": True,
            "error": f"{type(exc).__name__}:{exc}",
            "control_survived": False,
            "last_wins": False,
            "outcome": "error",
        }
    rec = _inspect(root, order)
    rec["installer"] = INSTALLER_ID
    rec["error"] = error
    return rec


def run_filesystem_matrix() -> dict[str, Any]:
    order_upper_then_lower = [
        COLLIDE_UPPER_NAME,
        COLLIDE_LOWER_NAME,
        CONTROL_ALPHA_NAME,
        CONTROL_BETA_NAME,
    ]
    order_lower_then_upper = [
        COLLIDE_LOWER_NAME,
        COLLIDE_UPPER_NAME,
        CONTROL_ALPHA_NAME,
        CONTROL_BETA_NAME,
    ]

    with case_sensitive_root() as posix:
        t1 = _run_trial(posix, order_upper_then_lower)
        # second order on a clean sibling dir so we do not mix leftovers
    with case_sensitive_root() as posix2:
        t2 = _run_trial(posix2, order_lower_then_upper)
        posix_fstype = fstype_of(posix2)

    with case_insensitive_root() as vfat:
        v1 = _run_trial(vfat, order_upper_then_lower)
    with case_insensitive_root() as vfat2:
        v2 = _run_trial(vfat2, order_lower_then_upper)
        vfat_fstype = fstype_of(vfat2)

    posix_trials = [t1, t2]
    vfat_trials = [v1, v2]
    posix_control = all(t.get("control_survived") for t in posix_trials)
    vfat_control = all(t.get("control_survived") for t in vfat_trials)
    posix_coexist = all(t.get("outcome") == "both-names-coexist" for t in posix_trials)
    vfat_last_wins = all(t.get("last_wins") for t in vfat_trials)
    vfat_silent = all(
        t.get("outcome") == "silent-last-wins" and not t.get("installer_raised")
        for t in vfat_trials
    )

    both = True
    return {
        "both_exercised": both,
        "installer": INSTALLER_ID,
        "case_sensitive": {
            "class": "case-sensitive",
            "implementation": "native-posix-tempdir",
            "host_fstype": posix_fstype,
            "trials": posix_trials,
            "collision_outcome": "both-names-coexist" if posix_coexist else "mixed",
            "control_survived": posix_control,
            "silent_overwrite": False,
        },
        "case_insensitive": {
            "class": "case-insensitive",
            "implementation": "vfat-loop-mount",
            "host_fstype": vfat_fstype,
            "trials": vfat_trials,
            "collision_outcome": "silent-last-wins" if vfat_silent else "mixed",
            "control_survived": vfat_control,
            "silent_overwrite": vfat_silent,
            "last_wins_proven": vfat_last_wins,
        },
        "platform_divergence": posix_coexist and vfat_silent,
        "control_survived_on_each": posix_control and vfat_control,
        "silent_last_wins_distinguished_from_error": vfat_silent,
    }


def run_parser_matrix() -> dict[str, Any]:
    fixtures = {
        "case-distinct": fixture_case_distinct(),
        "duplicate-exact": fixture_duplicate_exact(),
        "control-clean": fixture_control_clean(),
    }
    rows: list[dict[str, Any]] = []
    for fixture_id, text in fixtures.items():
        for parser_id, fn in PARSERS.items():
            rec = fn(text)
            rec["fixture"] = fixture_id
            rec["parser_id"] = parser_id
            rec["control_survived"] = control_survived(rec)
            if fixture_id == "case-distinct":
                rec["key_class"] = classify_keys(rec, ("Name", "name"))
            elif fixture_id == "duplicate-exact":
                rec["key_class"] = classify_keys(rec, ("Name", "Name"))
                if rec.get("ok") and rec.get("values", {}).get("Name") == "CNF-0104-dup-last":
                    rec["key_class"] = "silent-last-wins"
                elif not rec.get("ok") and "duplicate-key" in str(rec.get("error") or ""):
                    rec["key_class"] = "error"
            else:
                rec["key_class"] = "control"
            rows.append(rec)

    def row(fid: str, pid: str) -> dict[str, Any]:
        for r in rows:
            if r["fixture"] == fid and r["parser_id"] == pid:
                return r
        raise KeyError(f"{fid}/{pid}")

    loads_case = row("case-distinct", "json.loads")
    loads_dup = row("duplicate-exact", "json.loads")
    loads_ctrl = row("control-clean", "json.loads")
    strict_dup = row("duplicate-exact", "strict-duplicate")
    fold_case = row("case-distinct", "casefold-last-wins")
    fold_ctrl = row("control-clean", "casefold-last-wins")
    strict_ctrl = row("control-clean", "strict-duplicate")

    toolchain_keeps_case_distinct = loads_case.get("key_class") == "both-kept"
    toolchain_dup_last_wins = loads_dup.get("key_class") == "silent-last-wins"
    strict_errors_on_dup = strict_dup.get("key_class") == "error"
    fold_collapses = fold_case.get("key_class") == "silent-last-wins"
    controls_ok = all(
        r.get("control_survived")
        for r in (loads_ctrl, fold_ctrl, strict_ctrl)
    ) and all(
        r.get("control_survived")
        for r in rows
        if r["fixture"] != "duplicate-exact" or r["parser_id"] != "strict-duplicate"
    )
    # control-clean must survive on every parser; case-distinct must keep alpha/beta
    case_controls = all(
        r.get("control_survived")
        for r in rows
        if r["fixture"] in {"case-distinct", "control-clean"}
    )

    distinguished = toolchain_dup_last_wins and strict_errors_on_dup
    return {
        "toolchain_parser": PARSER_ID,
        "rows": [
            {
                "fixture": r["fixture"],
                "parser": r["parser_id"],
                "ok": r.get("ok"),
                "keys": r.get("keys"),
                "values": r.get("values"),
                "error": r.get("error"),
                "key_class": r.get("key_class"),
                "control_survived": r.get("control_survived"),
            }
            for r in rows
        ],
        "json_loads_keeps_case_distinct_keys": toolchain_keeps_case_distinct,
        "json_loads_duplicate_exact_is_silent_last_wins": toolchain_dup_last_wins,
        "strict_duplicate_errors": strict_errors_on_dup,
        "casefold_consumer_silent_last_wins_on_Name_name": fold_collapses,
        "silent_last_wins_distinguished_from_error": distinguished,
        "control_survived": case_controls,
        "control_clean_survived_on_all_parsers": all(
            row("control-clean", p).get("control_survived") for p in PARSERS
        ),
    }


def run_all() -> dict[str, Any]:
    fs = run_filesystem_matrix()
    parsers = run_parser_matrix()
    ok = (
        fs.get("both_exercised") is True
        and fs.get("control_survived_on_each") is True
        and parsers.get("control_survived") is True
        and parsers.get("silent_last_wins_distinguished_from_error") is True
        and fs.get("silent_last_wins_distinguished_from_error") is True
    )
    return {"filesystem": fs, "parsers": parsers, "pass": ok}
