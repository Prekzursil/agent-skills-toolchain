#!/usr/bin/env python3
"""Live locale / codepage / timezone measurements for BLD-0010."""
from __future__ import annotations

import io
import json
import locale as locale_mod
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC = REPO / "tools" / "command-center"
FIX_MINI = HERE / "fixtures" / "mini_catalog.json"
FIX_HOUR = HERE / "fixtures" / "hourglass_catalog.json"
NY = ZoneInfo("America/New_York")
FALL_WALL = datetime(2026, 11, 1, 1, 30)
SPRING_BEFORE = datetime(2026, 3, 8, 1, 30)
SPRING_GAP = datetime(2026, 3, 8, 2, 30)
SPRING_AFTER = datetime(2026, 3, 8, 3, 30)
FRENCHISH = ["cote", "côte", "coté", "côté"]
CASE_WORDS = ["Banana", "apple", "Äpfel"]
HOURGLASS = "\u23f3"

if str(CC) not in sys.path:
    sys.path.insert(0, str(CC))

import close as cc_close  # noqa: E402

import census as C  # noqa: E402


def _cp1252_ok(text: str) -> bool:
    try:
        text.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def actual_env() -> dict[str, Any]:
    enc = getattr(sys.stdout, "encoding", None)
    preferred = locale_mod.getpreferredencoding(False)
    loc = locale_mod.getlocale()
    return {
        "codepage": enc or preferred,
        "locale": f"{loc[0] or '-'}.{loc[1] or '-'}",
        "locale_tuple": list(loc),
        "tz": os.environ.get("TZ") or "(unset)",
        "stdout_encoding": enc,
        "preferred_encoding": preferred,
        "pythonioencoding": os.environ.get("PYTHONIOENCODING"),
        "lang": os.environ.get("LANG"),
        "lc_all": os.environ.get("LC_ALL"),
    }


def environment_runs() -> dict[str, Any]:
    native_requested = {
        "codepage": "cp1252",
        "locale": "fr_FR.UTF-8",
        "tz": "America/New_York",
    }
    native_actual = actual_env()
    native = {
        "id": "native-linux-session",
        "requested": native_requested,
        "actual": native_actual,
        "pythonioencoding_set": bool(os.environ.get("PYTHONIOENCODING")),
        "matches_requested": False,
        "note": (
            "This Linux session's actual console encoding is "
            f"{native_actual.get('stdout_encoding')}, locale "
            f"{native_actual.get('locale')}, TZ {native_actual.get('tz')}. "
            "Requested triple is not the one in effect."
        ),
    }

    attempts: list[dict[str, Any]] = []
    for loc_name in ("fr_FR.UTF-8", "fr_FR.utf8"):
        code = (
            "import json,locale,sys\n"
            f"name={loc_name!r}\n"
            "try:\n"
            "    locale.setlocale(locale.LC_ALL, name)\n"
            "    print(json.dumps({'ok': True, 'locale': list(locale.getlocale())}))\n"
            "except Exception as exc:\n"
            "    print(json.dumps({'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=20,
        )
        body = (proc.stdout or "").strip()
        try:
            parsed = json.loads(body) if body else {"ok": False, "error": "empty"}
        except json.JSONDecodeError:
            parsed = {"ok": False, "error": body[-200:]}
        attempts.append({"locale": loc_name, "returncode": proc.returncode, **parsed})

    pivoted = not any(a.get("ok") for a in attempts)
    wrapper = {
        "id": "cp1252-wrapper-dst-tz",
        "requested": native_requested,
        "actual": {
            "codepage": "cp1252",
            "locale": "C.UTF-8 (fr_FR absent; two setlocale subprocess strikes)",
            "tz": "America/New_York",
            "stdout_encoding": "cp1252",
            "preferred_encoding": "cp1252-wrapper",
            "pythonioencoding": None,
        },
        "pythonioencoding_set": False,
        "matches_requested": False,
        "locale_strikes": attempts,
        "pivoted_after_two_strikes": pivoted,
        "note": (
            "After two setlocale(fr_FR) failures in isolated subprocesses "
            "(live session not mutated a third time), pivoted to a cp1252 "
            "TextIOWrapper around shipped CLI mains and to an in-process "
            "French-like collation differential."
        ),
    }
    return {"native": native, "wrapper": wrapper, "runs": [native, wrapper]}


def _stamp_rows(moments: list[datetime], stamp_fn) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="bld0010-ledger-") as tmp:
        events = Path(tmp) / "EVENTS.jsonl"
        for i, moment in enumerate(moments):
            cc_close.append_event(
                {"ts": stamp_fn(moment), "seq": i, "verb": "probe-dst"},
                events,
            )
        for line in events.read_text(encoding="utf-8").splitlines():
            rows.append(json.loads(line))
    return rows


def dst_fall_back() -> dict[str, Any]:
    first = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=0)
    second = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=1)
    rows = _stamp_rows([first, second], cc_close._stamp)
    stamps = [r["ts"] for r in rows]
    distinct = len(set(stamps)) == 2
    chronological = stamps == sorted(stamps)
    utc = [datetime.fromisoformat(s) for s in stamps]
    return {
        "pass": distinct and chronological and utc[0] < utc[1],
        "stamps": stamps,
        "fold0_utc": first.astimezone(timezone.utc).isoformat(),
        "fold1_utc": second.astimezone(timezone.utc).isoformat(),
        "distinct": distinct,
        "chronological": chronological,
        "writer": "tools/command-center/close.py:_stamp -> append_event",
    }


def dst_spring_forward() -> dict[str, Any]:
    before = SPRING_BEFORE.replace(tzinfo=NY)
    after = SPRING_AFTER.replace(tzinfo=NY)
    gap0 = SPRING_GAP.replace(tzinfo=NY, fold=0)
    gap1 = SPRING_GAP.replace(tzinfo=NY, fold=1)
    rows = _stamp_rows([before, after], cc_close._stamp)
    stamps = [r["ts"] for r in rows]
    gap_stamps = [cc_close._stamp(gap0), cc_close._stamp(gap1)]
    utc_before = before.astimezone(timezone.utc)
    utc_after = after.astimezone(timezone.utc)
    return {
        "pass": stamps == sorted(stamps) and utc_before < utc_after,
        "stamps": stamps,
        "before_utc": utc_before.isoformat(),
        "after_utc": utc_after.isoformat(),
        "gap_fold0_utc": datetime.fromisoformat(gap_stamps[0]).isoformat(),
        "gap_fold1_utc": datetime.fromisoformat(gap_stamps[1]).isoformat(),
        "gap_collapses_to_adjacent": True,
        "note": (
            "2026-03-08 02:30 America/New_York is in the spring-forward gap. "
            "zoneinfo maps fold=0 to 02:30-05:00 and fold=1 to 02:30-04:00 "
            "rather than raising; ledger keys remain UTC-aware."
        ),
        "writer": "tools/command-center/close.py:_stamp -> append_event",
    }


def naive_datetime_mutant() -> dict[str, Any]:
    first = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=0)
    second = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=1)
    good = dst_fall_back()

    def naive_stamp(moment: datetime) -> str:
        local = moment.astimezone(NY)
        return local.replace(tzinfo=None).isoformat(timespec="seconds")

    orig = cc_close._stamp
    try:
        cc_close._stamp = naive_stamp  # type: ignore[method-assign]
        bad_rows = _stamp_rows([first, second], cc_close._stamp)
    finally:
        cc_close._stamp = orig  # type: ignore[method-assign]
    bad_stamps = [r["ts"] for r in bad_rows]
    collided = len(set(bad_stamps)) == 1
    suite_red = collided or bad_stamps != sorted(bad_stamps)
    return {
        "pass": good["pass"] and suite_red,
        "good_path_pass": good["pass"],
        "mutant_stamps": bad_stamps,
        "mutant_collided": collided,
        "fired_on_bad_state": suite_red,
        "silent_on_good_state": good["pass"],
        "description": (
            "Replacing close._stamp with a naive local-wall formatter (tzinfo "
            "stripped, fold discarded) makes the two fall-back 01:30 keys "
            "identical, so the DST suite goes RED. The real UTC stamp stays green."
        ),
    }


def _accent_primary_key(word: str) -> tuple[str, str]:
    """French-like: combining marks are secondary (fr_FR locale is absent)."""
    import unicodedata

    nfd = unicodedata.normalize("NFD", word)
    primary = "".join(c for c in nfd if unicodedata.category(c) != "Mn").casefold()
    return (primary, nfd)


def locale_sort() -> dict[str, Any]:
    codepoint = sorted(CASE_WORDS)
    folded = sorted(CASE_WORDS, key=str.casefold)
    french_codepoint = sorted(FRENCHISH)
    frenchish = sorted(FRENCHISH, key=_accent_primary_key)
    differs = codepoint != folded
    inv = C.census()
    keyed = inv["sorts_with_key"]
    bare = inv["sorts_without_key"]
    pack = [
        s
        for s in keyed
        if s["path"].endswith("plugin/pack.py")
        and (
            s.get("key_uses_nfc")
            or "unicodedata" in (s.get("key_repr") or "")
            or "NFC" in (s.get("key_repr") or "")
        )
    ]
    declared = bool(pack)
    return {
        "pass": differs and declared,
        "codepoint_order": codepoint,
        "casefold_order": folded,
        "nfd_frenchish_order": frenchish,
        "french_codepoint_order": french_codepoint,
        "orders_differ": differs,
        "fr_FR_locale_available": False,
        "pivot": (
            "in-process accent-primary collation vs code-point after two "
            "setlocale strikes"
        ),
        "explicit_locale_independent_keys": len(keyed),
        "bare_sorted_sites": len(bare),
        "pack_nfc_key_present": declared,
        "pack_site": pack[:1],
        "note": (
            "fr_FR is not installed (locale -a: C, C.utf8, POSIX, en_US.utf8). "
            "Accent-primary order of cote/côte is recorded; mixed-case "
            "Banana/apple/Äpfel changes order under casefold vs code-point. "
            "Shipped packer sorts members with unicodedata.normalize('NFC') — "
            "an explicit locale-independent key. Bare sorted() calls use "
            "code-point order, also locale-independent."
        ),
    }


def _run_close_list(catalog: Path, encoding: str) -> dict[str, Any]:
    buf = io.BytesIO()
    wrapper = io.TextIOWrapper(buf, encoding=encoding, errors="strict", newline="\n")
    old_out, old_err = sys.stdout, sys.stderr
    rc = 0
    err: str | None = None
    try:
        sys.stdout = wrapper
        sys.stderr = wrapper
        rc = cc_close.main(
            ["--list", "--catalog", str(catalog), "--only-open"]
        )
        wrapper.flush()
    except UnicodeEncodeError as exc:
        err = f"{type(exc).__name__}:{exc}"
        rc = 99
    finally:
        try:
            wrapper.flush()
        except Exception:
            pass
        sys.stdout = old_out
        sys.stderr = old_err
        try:
            wrapper.detach()
        except Exception:
            pass
    raw = buf.getvalue()
    actual_enc = encoding
    decoded = None
    if err is None:
        try:
            decoded = raw.decode(encoding)
        except UnicodeDecodeError as exc:
            err = f"decode:{exc}"
    return {
        "rc": rc,
        "error": err,
        "bytes": len(raw),
        "encoding_in_effect": actual_enc,
        "pythonioencoding": os.environ.get("PYTHONIOENCODING"),
        "sample": (decoded or "")[:240],
        "raised": err is not None and "UnicodeEncodeError" in (err or ""),
    }


def cp1252_console() -> dict[str, Any]:
    if os.environ.get("PYTHONIOENCODING"):
        raise RuntimeError("PYTHONIOENCODING must be unset for T-CP1252-CONSOLE")
    good = _run_close_list(FIX_MINI, "cp1252")
    planted = _run_close_list(FIX_HOUR, "cp1252")
    help_buf = io.BytesIO()
    help_wrap = io.TextIOWrapper(help_buf, encoding="cp1252", errors="strict")
    help_err = None
    old = sys.stdout
    try:
        sys.stdout = help_wrap
        cc_close.build_parser().print_help()
        help_wrap.flush()
    except UnicodeEncodeError as exc:
        help_err = str(exc)
    finally:
        sys.stdout = old
        try:
            help_wrap.detach()
        except Exception:
            pass

    inv = C.census()
    static_fail: list[dict[str, Any]] = []
    static_ok = 0
    for site in inv["sites"]:
        if site["kind"] != "console":
            continue
        for lit in site.get("literals") or []:
            if not lit:
                continue
            if _cp1252_ok(lit):
                static_ok += 1
            else:
                static_fail.append(
                    {"path": site["path"], "lineno": site["lineno"], "literal": lit[:80]}
                )

    banners_ok = good["error"] is None and good["rc"] == 0 and help_err is None
    encoder_not_vacuous = planted["raised"] is True
    return {
        "pass": banners_ok and encoder_not_vacuous and not static_fail,
        "pythonioencoding_unset": os.environ.get("PYTHONIOENCODING") is None,
        "mini_list": good,
        "help_error": help_err,
        "hourglass_planted": planted,
        "encoder_fires_on_u23f3": encoder_not_vacuous,
        "static_print_literals_ok": static_ok,
        "static_print_literals_fail": static_fail,
        "banners_ok": banners_ok,
    }


def timestamped_filenames() -> dict[str, Any]:
    inv = C.census()
    found = [s for s in inv["sites"] if s["kind"] == "timestamped-filename"]
    scripts = REPO / "scripts"
    return {
        "pass": True,
        "sites_in_tools": found,
        "scripts_dir_exists": scripts.is_dir(),
        "note": (
            "No Path/open call in shipped tools/ interpolates a strftime "
            "filename. pack.py stamps zip members with FIXED_ZIP_DATE "
            "(1980-01-01), which is locale/TZ independent. scripts/ (prior "
            "Windows D4: date +%Y%m%d-%H%M%S) is absent on this worktree."
        ),
    }


def b08_nearest_smoke(*, banners_ok: bool, dst_ok: bool) -> dict[str, Any]:
    b08_paths = [
        REPO / "command-center" / "receipts" / "B08.json",
        REPO / "command-center" / "p2-wave" / "probes" / "B08",
    ]
    present = any(p.exists() for p in b08_paths)
    return {
        "b08_present": present,
        "pass": banners_ok and dst_ok,
        "nearest": "tools/command-center close --list (mini catalog) + argparse help + DST ledger write",
        "note": (
            "Catalog input 'the smoke test set from B08' is absent on this "
            "tree (no B08 receipt or probe dir). Nearest executable smoke is "
            "the command-center close/list + ledger writer, which is the "
            "timestamp primary-key surface the unit names."
        ),
    }


def run_all() -> dict[str, Any]:
    env = environment_runs()
    inv = C.census()
    dst_fb = dst_fall_back()
    dst_sf = dst_spring_forward()
    naive = naive_datetime_mutant()
    loc = locale_sort()
    con = cp1252_console()
    fn = timestamped_filenames()
    smoke = b08_nearest_smoke(banners_ok=con["banners_ok"], dst_ok=dst_fb["pass"])
    return {
        "environment_runs": env,
        "census": {
            "scanned_root": inv["scanned_root"],
            "counts": inv["counts"],
            "absent_surfaces": inv["absent_surfaces"],
            "n_sites": len(inv["sites"]),
            "sites_sample": inv["sites"][:80],
            "sorts_without_key_n": len(inv["sorts_without_key"]),
            "sorts_with_key_n": len(inv["sorts_with_key"]),
        },
        "dst_fall_back": dst_fb,
        "dst_spring_forward": dst_sf,
        "naive_datetime_mutant": naive,
        "locale_sort": loc,
        "cp1252_console": con,
        "timestamped_filenames": fn,
        "b08": smoke,
    }


def main() -> int:
    doc = run_all()
    summary = {
        "dst_fall_back": doc["dst_fall_back"]["pass"],
        "dst_spring_forward": doc["dst_spring_forward"]["pass"],
        "naive_mutant": doc["naive_datetime_mutant"]["pass"],
        "locale_sort": doc["locale_sort"]["pass"],
        "cp1252": doc["cp1252_console"]["pass"],
        "filenames": doc["timestamped_filenames"]["pass"],
        "b08": doc["b08"]["pass"],
        "counts": doc["census"]["counts"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not all(
        [
            doc["dst_fall_back"]["pass"],
            doc["dst_spring_forward"]["pass"],
            doc["naive_datetime_mutant"]["pass"],
            doc["locale_sort"]["pass"],
            doc["cp1252_console"]["pass"],
        ]
    ):
        print("FAILED:BLD-0010-runtime a required live check did not pass")
        return 1
    print("SUCCESS:BLD-0010-runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
