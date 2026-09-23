#!/usr/bin/env python3
"""Validate the models registry (``.agents/models.json``) and report its routing.

Read-only: the registry is parsed, validated and summarised, never rewritten.
Exit 0 prints one ``SUCCESS:models-registry`` line (warnings go to stderr);
exit 2 prints one ``FAILED:models-registry <reason>`` line and nothing else.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from typing import Any

import models_control_plane as models

COLUMNS = ("endpoint", "runtime", "decision", "reason", "alternative", "wrappers")
FAILED_EXIT = 2


def json_report(config: Mapping[str, Any], warnings: list[str]) -> dict[str, Any]:
    """The ``--json`` payload: warnings, credential names, routing rows per runtime."""
    return {
        "warnings": warnings,
        "credential_names": models.credential_names(config),
        "routing": {
            runtime: models.routing_report(config, runtime)
            for runtime in models.RUNTIMES
        },
    }


def format_routing_table(rows: list[dict[str, Any]]) -> str:
    """Aligned text table of routing rows; ``None`` alternatives print as ``-``."""
    table = [
        COLUMNS,
        *(
            tuple(
                "-" if row[column] is None else str(row[column]) for column in COLUMNS
            )
            for row in rows
        ),
    ]
    widths = [max(len(line[index]) for line in table) for index in range(len(COLUMNS))]
    return "\n".join(
        "  ".join(
            cell.ljust(width) for cell, width in zip(line, widths, strict=True)
        ).rstrip()
        for line in table
    )


def success_line(config: Mapping[str, Any], warnings: list[str]) -> str:
    return (
        "SUCCESS:models-registry "
        f"endpoints={len(config['endpoints'])} models={len(config['models'])} "
        f"warnings={len(warnings)} hash={models.registry_hash(config)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default=str(models.DEFAULT_REGISTRY_PATH),
        help="path of the models registry to validate (default: the repo's .agents/models.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="print {warnings, credential_names, routing} as JSON before the summary line",
    )
    parser.add_argument(
        "--runtime",
        help="print one runtime's routing report as a text table before the summary line",
    )
    args = parser.parse_args(argv)

    try:
        config = models.load_registry(args.registry)
        warnings = models.validate_registry(config)
        if args.as_json:
            print(json.dumps(json_report(config, warnings), indent=2))
        if args.runtime is not None:
            print(format_routing_table(models.routing_report(config, args.runtime)))
    except OSError as error:
        print(f"FAILED:models-registry {args.registry}: {error.strerror or error}")
        return FAILED_EXIT
    except models.ModelsRegistryError as error:
        print(f"FAILED:models-registry {error}")
        return FAILED_EXIT

    for warning in warnings:
        print(f"WARNING:models-registry {warning}", file=sys.stderr)
    print(success_line(config, warnings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
