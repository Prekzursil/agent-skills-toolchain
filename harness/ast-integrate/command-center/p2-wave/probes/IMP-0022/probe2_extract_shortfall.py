#!/usr/bin/env python3
"""Named probe 2: extract-count shortfall on a case-insensitive overlay (signal 2).

Independent of the set-collision count. Builds a zip, extracts through an
os.listdir NFC+casefold overlay implemented HERE (not the production
extractor), then compares ``zip.namelist`` file-entry count against
``os.walk`` file count. A collision is a shortfall.

Also discharges the reviewer_requirement: normalisation is casefold (not
lower()) and NFC is applied first — proven by planted pairs that lower()
or casefold-without-NFC would miss.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.case_collision import (  # noqa: E402
    both_signals,
    extract_zip_case_insensitive,
    find_casefold_collisions,
)
from plugin.pathnorm import nfc_casefold  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0022.json"


def independent_resolve(directory: Path, name: str) -> str:
    want = nfc_casefold(name)
    if directory.is_dir():
        for existing in os.listdir(directory):
            if nfc_casefold(existing) == want:
                return existing
    return name


def independent_extract(zf: zipfile.ZipFile, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            continue
        parts = [p for p in name.split("/") if p]
        current = dest
        for i, part in enumerate(parts):
            actual = independent_resolve(current, part)
            target = current / actual
            if i == len(parts) - 1:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, open(target, "wb") as out:
                    out.write(src.read())
            else:
                target.mkdir(parents=True, exist_ok=True)
                current = target
    n = 0
    for _dirpath, _dirnames, filenames in os.walk(dest):
        n += len(filenames)
    return n


def zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def shortfall(members: dict[str, bytes]) -> dict:
    raw = zip_bytes(members)
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        entries = [n for n in zf.namelist() if n and not n.endswith("/")]
    with tempfile.TemporaryDirectory(prefix="imp0022-p2-") as tmp:
        dest = Path(tmp)
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            indep_count = independent_extract(zf, dest / "indep")
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            prod_count = extract_zip_case_insensitive(zf, dest / "prod")
    return {
        "archive_entry_count": len(entries),
        "independent_extracted": indep_count,
        "production_extracted": prod_count,
        "independent_shortfall": len(entries) - indep_count,
        "production_shortfall": len(entries) - prod_count,
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0022-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0022-probe2 receipt unparseable: {exc}")
        return 1
    if "SUCCESS:IMP-0022" not in text:
        print("FAILED:IMP-0022-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0022-probe2 self-declared {st}")
        return 1

    planted = {
        "docs/README.md": b"UPPER-README\n",
        "docs/readme.md": b"lower-readme\n",
        "docs/unique.txt": b"unique\n",
    }
    planted_sf = shortfall(planted)
    if planted_sf["independent_shortfall"] < 1:
        print(f"FAILED:IMP-0022-probe2 planted extract silent {planted_sf}")
        return 1
    if planted_sf["independent_shortfall"] != planted_sf["production_shortfall"]:
        print(f"FAILED:IMP-0022-probe2 extract disagreement {planted_sf}")
        return 1
    both = both_signals(planted)
    if not both["set_fired"] or not both["extract_fired"]:
        print(f"FAILED:IMP-0022-probe2 both-signals control {both}")
        return 1
    if both["shortfall"] != planted_sf["independent_shortfall"]:
        print(
            f"FAILED:IMP-0022-probe2 production both_signals shortfall "
            f"{both['shortfall']} != indep {planted_sf['independent_shortfall']}"
        )
        return 1

    clean = {"a.txt": b"a\n", "b.txt": b"b\n"}
    clean_sf = shortfall(clean)
    if clean_sf["independent_shortfall"] != 0 or clean_sf["production_shortfall"] != 0:
        print(f"FAILED:IMP-0022-probe2 clean shortfall {clean_sf}")
        return 1

    # Reviewer: casefold, not lower().
    sharp_s = "Straße.md"
    ss = "STRASSE.md"
    if sharp_s.lower() == ss.lower():
        print("FAILED:IMP-0022-probe2 ß/SS pair no longer distinguishes lower()")
        return 1
    if nfc_casefold(sharp_s) != nfc_casefold(ss):
        print("FAILED:IMP-0022-probe2 casefold missed ß/SS")
        return 1
    if not find_casefold_collisions([sharp_s, ss]):
        print("FAILED:IMP-0022-probe2 detector used lower() (ß/SS silent)")
        return 1

    # Reviewer: NFC first.
    nfc_name = "caf\u00e9.txt"
    nfd_name = "cafe\u0301.txt"
    if nfc_name == nfd_name:
        print("FAILED:IMP-0022-probe2 NFC/NFD pair collapsed before the test")
        return 1
    if nfc_name.casefold() == nfd_name.casefold():
        print("FAILED:IMP-0022-probe2 pair no longer requires NFC-first")
        return 1
    if unicodedata.normalize("NFC", nfd_name) != nfc_name:
        print("FAILED:IMP-0022-probe2 NFD did not NFC-equal the precomposed form")
        return 1
    if not find_casefold_collisions([nfc_name, nfd_name]):
        print("FAILED:IMP-0022-probe2 detector skipped NFC (NFD/NFC silent)")
        return 1

    report = {
        "probe": "probe2-extract-shortfall",
        "unit_id": "IMP-0022",
        "planted": planted_sf,
        "clean": clean_sf,
        "both_signals_fired_on_readme_pair": True,
        "reviewer_casefold_not_lower": True,
        "reviewer_nfc_first": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"planted_shortfall={planted_sf['independent_shortfall']} "
        f"clean_shortfall={clean_sf['independent_shortfall']} "
        "casefold_not_lower=True nfc_first=True"
    )
    print("SUCCESS:IMP-0022-probe2 extract-count shortfall and reviewer NFC+casefold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
