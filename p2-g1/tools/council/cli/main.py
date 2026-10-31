#!/usr/bin/env python3
"""Council CLI used by IMP-0325 exit-code matrix."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from exit_codes import (
    EXIT_COUNCIL_FAILED,
    EXIT_EXPLAIN_OK,
    EXIT_INSPECT_OK,
    EXIT_LIST_PRESETS_OK,
    EXIT_MISSING_ARTIFACT,
    EXIT_NO_CHECKPOINT,
    EXIT_NO_LINEAGE,
    EXIT_NO_PRESETS,
    EXIT_RESUME_OK,
    EXIT_RUN_OK,
    EXIT_USAGE,
)
from runtime import COUNCIL_SUCCESS_SENTINEL


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _votes_pass(spec: dict) -> bool:
    parts = spec.get("participants") or []
    votes = [str(p.get("vote") or "").lower() for p in parts]
    rule = str((spec.get("voting") or {}).get("rule") or "majority").lower()
    yes = sum(1 for v in votes if v in {"yes", "aye"})
    if rule == "unanimous":
        return bool(votes) and yes == len(votes)
    return yes * 2 >= max(1, len(votes))


def cmd_run(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec)
    if not spec_path.is_file():
        return EXIT_MISSING_ARTIFACT
    spec = _load(spec_path)
    if not _votes_pass(spec):
        if args.out:
            Path(args.out).write_text(
                json.dumps({"status": "FAILED", "sentinel": "FAILED:COUNCIL"}, indent=2)
                + "\n",
                encoding="utf-8",
            )
        return EXIT_COUNCIL_FAILED
    write = bool((spec.get("artifacts") or {}).get("write", True))
    if not write:
        return EXIT_MISSING_ARTIFACT
    if args.out:
        Path(args.out).write_text(
            json.dumps(
                {
                    "status": "SUCCESS",
                    "sentinel": COUNCIL_SUCCESS_SENTINEL,
                    "spec_id": spec.get("id"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return EXIT_RUN_OK


def cmd_resume(args: argparse.Namespace) -> int:
    ck = Path(args.checkpoint)
    if not ck.is_file():
        return EXIT_NO_CHECKPOINT
    if args.out:
        Path(args.out).write_text(ck.read_text(encoding="utf-8"), encoding="utf-8")
    return EXIT_RESUME_OK


def cmd_inspect(args: argparse.Namespace) -> int:
    art = Path(args.artifact)
    if not art.is_file():
        return EXIT_MISSING_ARTIFACT
    return EXIT_INSPECT_OK


def cmd_list_presets(args: argparse.Namespace) -> int:
    if args.catalog:
        cat = Path(args.catalog)
        if not cat.is_file():
            return EXIT_NO_PRESETS
        doc = _load(cat)
        presets = doc.get("presets") if isinstance(doc, dict) else doc
        if not presets:
            return EXIT_NO_PRESETS
    print("default-preset")
    return EXIT_LIST_PRESETS_OK


def cmd_explain(args: argparse.Namespace) -> int:
    art = Path(args.artifact)
    if not art.is_file():
        return EXIT_MISSING_ARTIFACT
    doc = _load(art)
    if not doc.get("lineage") and str(doc.get("status") or "").upper() == "FAILED":
        return EXIT_NO_LINEAGE
    if not doc.get("lineage") and not doc.get("rule") and doc.get("reason") == "hung":
        return EXIT_NO_LINEAGE
    return EXIT_EXPLAIN_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="council")
    sub = parser.add_subparsers(dest="verb")

    p_run = sub.add_parser("run")
    p_run.add_argument("--spec", required=True)
    p_run.add_argument("--out")
    p_run.set_defaults(func=cmd_run)

    p_resume = sub.add_parser("resume")
    p_resume.add_argument("--checkpoint", required=True)
    p_resume.add_argument("--out")
    p_resume.set_defaults(func=cmd_resume)

    p_ins = sub.add_parser("inspect")
    p_ins.add_argument("--artifact", required=True)
    p_ins.set_defaults(func=cmd_inspect)

    p_lp = sub.add_parser("list-presets")
    p_lp.add_argument("--catalog")
    p_lp.set_defaults(func=cmd_list_presets)

    p_ex = sub.add_parser("explain")
    p_ex.add_argument("--artifact", required=True)
    p_ex.set_defaults(func=cmd_explain)

    args = parser.parse_args(argv)
    if not getattr(args, "verb", None):
        return EXIT_USAGE
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
