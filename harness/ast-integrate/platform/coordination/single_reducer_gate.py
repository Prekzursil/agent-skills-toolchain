"""Executable gate: this package must contain exactly ONE completion reducer.

    python platform/coordination/single_reducer_gate.py [directory]

Exit 0 with ``SUCCESS:single-reducer …`` when N of N modules scanned and none defines the shared
reducer's decision surface. Exit 1 with one ``FAILED:single-reducer …`` line per violation.

Shaped to ``rules/common/ci-hygiene.md`` section 1, which records that ``python -m <module>`` as a
CI gate is a NO-OP unless the module enumerates real inputs, fails closed, and exits non-zero. All
three hold here, and ``test_reducer.py`` runs this script against a known-bad tree and against an
EMPTY directory, requiring exit 1 for both - a gate that has never been observed going red is
indistinguishable from a gate that does nothing.

This wrapper exists rather than a ``__main__`` block inside ``reducer.py`` because that module uses
relative imports: ``python reducer.py`` raises *"attempted relative import with no known parent
package"*. Measured while building this gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from coordination.reducer import main  # noqa: E402  - after the sys.path fix above

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
