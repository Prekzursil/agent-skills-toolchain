"""``mon cockpit`` — launch the unified 5-pane monitor board.

The registry (``monitors.toml``) launches a monitor as ``python <skills_root>/<dir>/<entry>``
(see :func:`monitorcore.monitors.resolve_entry` / :func:`monitorcore.monitors.build_wt_argv`),
so a monitor's entry must be a SCRIPT PATH. ``monitorcore.unified`` is a module, reachable
only as ``python -m``, which the launch ladder cannot express — that mismatch is the entire
reason the cockpit shipped merged, gated and unreachable: five panes of working code with no
registry stanza able to name them.

This shim is the adapter. It stays deliberately trivial (resolve the vendored package, hand
off to ``main``) so that everything worth testing lives in the 100%-covered
``monitorcore.unified``.

Owns the ``Workflow`` trigger (MASTER-QUEUE T0-3, executed 2026-08-20): ``trigger_tool =
"Workflow"`` moved to this stanza from the ``wfmon`` predecessor, so a Workflow call now
auto-opens this cockpit — exactly one window, replacing rather than doubling the predecessor
board, which stays launchable by hand only (``mon wfmon``).
"""

from __future__ import annotations

import os
import sys

# `mon` invokes this by absolute path, so this directory is already ``sys.path[0]`` and the
# vendored ``monitorcore`` package beside it imports cleanly. Made explicit so the script also
# works when a shim rewrites argv[0] or runs it through a launcher that clears sys.path[0].
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monitorcore.unified import main  # noqa: E402  (path setup must precede the import)

# pragma: no cover -- a launcher shim has no logic to cover; it is proven end-to-end by
# `python unified_board.py --once`, and by tests/test_registry_shipped.py proving `mon
# cockpit` resolves to this path.
if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
