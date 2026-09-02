#!/usr/bin/env python3
"""Install gate CLI: negotiate the client version before anything is written.

Usage::

    python3 -B tools/plugin/install_gate.py --manifest plugin.json \
        --client claude-code --version 1.2.3 --dest ./out [--write-on-allow]

The negotiation result is printed to stdout as JSON (``negotiation``,
``installed``, ``dest_has_payload`` ...). On refusal the user-facing message
is printed to stderr verbatim — it is the same string as
``negotiation.message`` — and the process exits 2 without touching ``dest``.
On allow the exit code is 0 and, only with ``--write-on-allow``, the payload
is written to ``dest``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if __package__ in (None, ""):
    sys.path.insert(0, str(HERE.parent))

from plugin.client_negotiate import load_manifest, preflight_install  # noqa: E402

EXIT_ALLOW = 0
EXIT_REFUSE = 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="install_gate", description=__doc__.split("\n\n")[0])
    p.add_argument("--manifest", default=None, help="plugin manifest path (plugin.json)")
    p.add_argument("--client", default="", help="client id, e.g. claude-code")
    p.add_argument("--version", default=None, help="client version string as reported")
    p.add_argument("--dest", required=True, help="install destination directory")
    p.add_argument(
        "--write-on-allow",
        action="store_true",
        help="write the payload to --dest when the negotiation allows the install",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = load_manifest(args.manifest)
    result = preflight_install(
        Path(args.dest),
        manifest,
        args.client,
        args.version,
        write=bool(args.write_on_allow),
    )
    result["manifest_path"] = str(args.manifest) if args.manifest else None
    result["exit_code"] = EXIT_ALLOW if result["allowed"] else EXIT_REFUSE
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    sys.stdout.flush()
    if not result["allowed"]:
        sys.stderr.write(str(result["negotiation"]["message"]) + "\n")
        sys.stderr.flush()
        return EXIT_REFUSE
    return EXIT_ALLOW


if __name__ == "__main__":
    raise SystemExit(main())
