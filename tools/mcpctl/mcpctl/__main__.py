"""``python -m mcpctl`` entry point."""

from __future__ import annotations

import sys

from mcpctl.cli import main

if __name__ == "__main__":
    sys.exit(main())
