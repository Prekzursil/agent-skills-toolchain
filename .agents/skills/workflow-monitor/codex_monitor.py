#!/usr/bin/env python3
"""codex_monitor.py — launchable entry for the codexmon live board (``mon codexmon``).

Thin shim: running ``python codex_monitor.py`` puts this skill dir at ``sys.path[0]``,
so the vendored, 100%-gated ``monitorcore`` package resolves and everything real —
stream + rollout tailing, mandatory redaction at ingest, the ANSI full-screen board —
lives in ``monitorcore.codex_tail`` (PR-B3's port of the personal codex_monitor).

Flags (all optional): ``--stream-dir`` / ``--sessions-dir`` / ``--since-min`` /
``--idle`` / ``--interval`` / ``--max-threads`` / ``--width`` / ``--once``.
"""

from monitorcore.codex_tail import main

if __name__ == "__main__":
    raise SystemExit(main())
