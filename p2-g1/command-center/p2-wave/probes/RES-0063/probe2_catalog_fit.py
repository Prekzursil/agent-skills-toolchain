#!/usr/bin/env python3
"""Probe 2: apply each identity definition to one real catalog unit (RES-0063).

Control: a fabricated data-partition mutant of the same id is NOT a research
artifact; Airflow must remain DOES_NOT_FIT on the real unit; Dagster must FITS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / "command-center/research/RES-0063.json"
SENTINEL = (
    "SUCCESS:RES-0063 in the receipt AND four cited task-identity definitions "
    "each tested against one real work unit from this slice"
)


def main() -> int:
    unit = L.catalog_unit(L.SUBJECT_ID)
    if unit.get("_source_slice_file") != L.SLICE_MARKER:
        print("FAILED:RES-0063-probe2 subject not in RES-1 slice")
        return 1
    live = L.apply_fit(unit)
    by_engine = {row["engine"]: row for row in live if row.get("engine") in L.ENGINES}
    control = next(row for row in live if row.get("engine") == "_control")
    expected = {
        "airflow": ("DOES_NOT_FIT", False),
        "prefect": ("PARTIAL", False),
        "dagster": ("FITS", True),
        "flyte": ("PARTIAL", False),
    }
    mismatches = []
    for engine, (cls, fits) in expected.items():
        row = by_engine[engine]
        if row.get("fit_class") != cls or bool(row.get("fits")) != fits:
            mismatches.append(
                {
                    "engine": engine,
                    "want": {"fit_class": cls, "fits": fits},
                    "got": {"fit_class": row.get("fit_class"), "fits": row.get("fits")},
                }
            )
        if row.get("subject_unit_id") != L.SUBJECT_ID:
            mismatches.append({"engine": engine, "bad_subject": row.get("subject_unit_id")})

    art_ok = False
    art_mismatches: list[dict] = []
    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        rows = [
            r
            for r in (doc.get("catalog_fit_tests") or [])
            if isinstance(r, dict) and r.get("engine") in L.ENGINES
        ]
        art_ok = (
            st not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and SENTINEL in text
            and len(rows) == 4
        )
        live_map = {
            e: (by_engine[e]["fit_class"], bool(by_engine[e]["fits"])) for e in L.ENGINES
        }
        for r in rows:
            key = (r.get("fit_class"), bool(r.get("fits")))
            if live_map.get(r.get("engine")) != key:
                art_mismatches.append(
                    {"engine": r.get("engine"), "artifact": key, "live": live_map.get(r.get("engine"))}
                )
                art_ok = False
        which = doc.get("which_definition_fits_research_artifact") or {}
        if which.get("best_fit") != "dagster":
            art_ok = False
            art_mismatches.append({"best_fit": which.get("best_fit")})
        if "airflow" not in (which.get("does_not_fit") or []):
            art_ok = False
            art_mismatches.append({"does_not_fit_missing_airflow": True})
        nc = doc.get("negative_control") or {}
        if nc.get("fired") is not True:
            art_ok = False
            art_mismatches.append({"control_not_fired": nc})

    payload = {
        "probe": "probe2-catalog-fit",
        "unit_id": "RES-0063",
        "subject": L.subject_fields(unit),
        "fit": {
            e: {
                "fit_class": by_engine[e]["fit_class"],
                "fits": by_engine[e]["fits"],
                "invented_fields": by_engine[e]["invented_fields"],
            }
            for e in L.ENGINES
        },
        "mismatches": mismatches,
        "control": {
            "fired": control.get("fired"),
            "real_unit_is_research_artifact": control.get("real_unit_is_research_artifact"),
            "mutant_is_research_artifact": control.get("mutant_is_research_artifact"),
            "airflow_fits_real_unit": control.get("airflow_fits_real_unit"),
            "dagster_fits_real_unit": control.get("dagster_fits_real_unit"),
        },
        "artifact_ok": art_ok,
        "artifact_mismatches": art_mismatches,
        "pass": bool(
            not mismatches
            and control.get("fired") is True
            and control.get("airflow_fits_real_unit") is False
            and control.get("dagster_fits_real_unit") is True
            and art_ok
            and not art_mismatches
        ),
    }
    print(json.dumps(payload, sort_keys=True, default=str)[:6000])
    if not payload["pass"]:
        print("FAILED:RES-0063-probe2 catalog fit")
        return 1
    print(
        "airflow=DOES_NOT_FIT prefect=PARTIAL dagster=FITS flyte=PARTIAL "
        f"control_fired={control.get('fired')}"
    )
    print("SUCCESS:RES-0063-probe2 four identities tested against RES-0063")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
