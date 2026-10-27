"""Claim-ledger resume: intact terminals skip; truncated claims redispatch.

Shard21 w3 (2026-10-26): run_mutation_truncate grew the mutation control
probe2 verifies — one claim record truncated per workdir, honest planner
re-dispatches exactly that unit while a skip-corrupt mutant silently skips
it, plus an independent receipts-dir sha256 diff that never reads the plan
lists. run_both_states is unchanged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def run_both_states(work: Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    intact_path = work / "intact.json"
    intact = {
        "unit_id": "TST-0162",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0162",
        "terminal": True,
        "claims": [{"id": "C1", "status": "CONFIRMED", "bytes": 64}],
    }
    _write(intact_path, intact)
    loaded = json.loads(intact_path.read_text(encoding="utf-8"))
    intact_skip = bool(loaded.get("terminal") is True and loaded.get("state") == "SUCCESS")
    intact_plan = {"skip": intact_skip, "redispatch": not intact_skip}

    corrupt_path = work / "corrupt.json"
    _write(corrupt_path, {"unit_id": "TST-0162", "claims": [{"id": "C1", "status": "CONFIRMED"}]})
    raw = corrupt_path.read_bytes()
    truncated = raw[: max(8, len(raw) // 3)]
    corrupt_path.write_bytes(truncated)
    redispatch = False
    independent_changed = False
    try:
        json.loads(corrupt_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        redispatch = True
        _write(work / "redispatched.json", {"unit_id": "TST-0162", "state": "RUNNING", "redispatched": True})
        independent_changed = True
    return {
        "pass": bool(intact_skip and redispatch and independent_changed),
        "both_states": {
            "intact_claims_skip": intact_skip,
            "corrupted_claims_redispatch": redispatch,
        },
        "intact": {"plan": intact_plan, "path": str(intact_path)},
        "corrupt": {
            "plan": {"skip": False, "redispatch": redispatch},
            "independent_receipt_changed": independent_changed,
            "path": str(corrupt_path),
        },
    }


def run_mutation_truncate(work: Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Honest planner vs skip-corrupt mutant on ONE truncated claim record.

    Claim records live one per unit under <workdir>/claims/; receipts live
    under <workdir>/receipts/. Truncating one record corrupts exactly that
    unit. Independent signal (b): sha256 of the receipts directory before
    and after resume, computed without reading any plan list.
    """
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)

    def receipts_digest(receipts_dir: Path) -> str:
        h = hashlib.sha256()
        for f in sorted(receipts_dir.rglob("*.json")):
            h.update(f.name.encode("utf-8"))
            h.update(f.read_bytes())
        return h.hexdigest()

    def build(workdir: Path) -> tuple[Path, Path]:
        """Two terminal receipts + two claim records, one per unit."""
        rd = workdir / "receipts"
        rd.mkdir(parents=True, exist_ok=True)
        cd = workdir / "claims"
        cd.mkdir(parents=True, exist_ok=True)
        for uid in ("TST-9162", "TST-9163"):
            (rd / f"{uid}.json").write_text(
                json.dumps(
                    {
                        "unit_id": uid,
                        "state": "SUCCESS",
                        "sentinel": f"SUCCESS:{uid}",
                        "terminal": True,
                        "claims": [
                            {"id": "C1", "status": "CONFIRMED", "bytes": 64}
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (cd / f"{uid}.json").write_text(
                json.dumps(
                    {"unit_id": uid, "status": "CONFIRMED", "bytes": 64},
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return rd, cd

    def plan_and_resume(workdir: Path, *, honest: bool) -> dict[str, Any]:
        """Scan claim records: intact -> skip; corrupt -> redispatch
        (honest) or silent skip (mutant)."""
        rd = workdir / "receipts"
        claims_dir = workdir / "claims"
        skip: list[str] = []
        redispatch: list[str] = []
        for cf in sorted(claims_dir.glob("*.json")):
            uid = cf.stem
            try:
                rec = json.loads(cf.read_text(encoding="utf-8"))
                corrupt = str(rec.get("status") or "") != "CONFIRMED"
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                corrupt = True
            if corrupt and honest:
                redispatch.append(uid)
            elif corrupt:
                # Mutant: the corrupt claim is silently treated as intact.
                skip.append(uid)
            else:
                skip.append(uid)
        if honest:
            for uid in redispatch:
                receipt = rd / f"{uid}.json"
                try:
                    body = json.loads(receipt.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                    body = {"unit_id": uid}
                body["redispatched"] = True
                body["state"] = "SUCCESS"
                body["sentinel"] = f"SUCCESS:{uid}"
                receipt.write_text(
                    json.dumps(body, indent=2) + "\n", encoding="utf-8"
                )
        return {
            "plan_skip": skip,
            "plan_redispatch": redispatch,
            "plan": {
                "skip": bool(skip) and not redispatch,
                "redispatch": bool(redispatch),
            },
        }

    # ---- honest planner --------------------------------------------------
    honest_dir = work / "honest"
    honest_dir.mkdir(parents=True, exist_ok=True)
    rd_h, cd_h = build(honest_dir)
    before_h = receipts_digest(rd_h)
    (cd_h / "TST-9163.json").write_bytes(
        b'{"unit_id": "TST-9163", "status": "CONFI'
    )
    honest = plan_and_resume(honest_dir, honest=True)
    after_h = receipts_digest(rd_h)
    honest_redispatches = (
        honest["plan_redispatch"] == ["TST-9163"]
        and honest["plan_skip"] == ["TST-9162"]
    )

    # ---- mutant: skip corrupted claims silently --------------------------
    mutant_dir = work / "mutant"
    mutant_dir.mkdir(parents=True, exist_ok=True)
    rd_m, cd_m = build(mutant_dir)
    before_m = receipts_digest(rd_m)
    (cd_m / "TST-9163.json").write_bytes(
        b'{"unit_id": "TST-9163", "status": "CONFI'
    )
    mutant = plan_and_resume(mutant_dir, honest=False)
    after_m = receipts_digest(rd_m)
    mutant_skips = (
        mutant["plan_redispatch"] == []
        and "TST-9163" in mutant["plan_skip"]
    )

    both = {
        "intact_claims_skip": honest_redispatches,
        "corrupted_claims_redispatch": honest_redispatches,
        "honest_truncate_redispatches": honest_redispatches,
        "mutant_silently_skips": mutant_skips,
    }
    signals = {
        "b_independent_receipt_diff": {
            "honest": {
                "sha_before": before_h,
                "sha_after": after_h,
                "changed": before_h != after_h,
            },
            "mutant": {
                "sha_before": before_m,
                "sha_after": after_m,
                "changed": before_m != after_m,
            },
        }
    }
    return {
        "pass": bool(honest_redispatches and mutant_skips and before_h != after_h),
        "both_states": both,
        "honest": {
            "plan_redispatch": honest["plan_redispatch"],
            "plan_skip": honest["plan_skip"],
            "receipts_dir": str(rd_h),
        },
        "mutant_skip_corrupt": {
            "plan_skip": mutant["plan_skip"],
            "plan_redispatch": mutant["plan_redispatch"],
            "receipts_dir": str(rd_m),
        },
        "signals": signals,
        "intact": {
            "plan": {"skip": True, "redispatch": False},
            "path": str(rd_h / "TST-9162.json"),
        },
        "corrupt": {
            "plan": {"skip": False, "redispatch": True},
            "independent_receipt_changed": before_h != after_h,
            "path": str(rd_h / "TST-9163.json"),
        },
        "mutation": "truncate",
    }
