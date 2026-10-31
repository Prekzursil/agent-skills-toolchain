#!/usr/bin/env python3
"""capa-triage — thin wrapper that runs Mandiant capa with the local rules + FLIRT sigs.

capa (flare-capa) identifies the capabilities in an executable and maps them to MITRE ATT&CK
and MBC. The pip LIBRARY needs the rule set and signatures passed explicitly (only the
standalone binary bundles them); this wrapper defaults them so you can just:

    python capa_triage.py <binary> [-j] [-v|-vv] [extra capa args]

Override the locations with the CAPA_RULES / CAPA_SIGS env vars. Exit code is capa's own.
"""

import os
import subprocess
import sys

HOME = os.path.expanduser("~")
RULES = os.environ.get("CAPA_RULES", os.path.join(HOME, ".capa", "rules"))
SIGS = os.environ.get("CAPA_SIGS", os.path.join(HOME, ".capa", "sigs"))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("usage: python capa_triage.py <binary> [-j] [-v|-vv] [extra capa args]")
        return 0
    cmd = [sys.executable, "-m", "capa.main"]
    if "-r" not in argv and "--rules" not in argv:
        cmd += ["-r", RULES]
    if "-s" not in argv and "--signatures" not in argv:
        cmd += ["-s", SIGS]
    cmd += argv
    try:
        return subprocess.run(cmd).returncode
    except FileNotFoundError:
        sys.stderr.write(
            "capa not found — is flare-capa installed? (pip install flare-capa)\n"
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
