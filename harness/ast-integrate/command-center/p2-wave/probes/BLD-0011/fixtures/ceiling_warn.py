"""Ceiling probe: emit a DeprecationWarning and refuse to swallow it."""
from __future__ import annotations

import datetime
import sys
import warnings


def main() -> int:
    warnings.simplefilter("default", DeprecationWarning)
    warnings.simplefilter("default", PendingDeprecationWarning)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        warnings.simplefilter("always", PendingDeprecationWarning)
        datetime.datetime.utcnow()
        utcnow_notes = [
            str(item.message)
            for item in caught
            if issubclass(item.category, Warning)
        ]
    # Also emit an explicit, version-stable deprecation so the ceiling
    # records a warning even if utcnow is not yet deprecated on this CPython.
    warnings.warn(
        "BLD-0011-ceiling: recorded deprecation channel (not suppressed)",
        DeprecationWarning,
        stacklevel=1,
    )
    print("CEILING_RAN", sys.version.split()[0])
    print("UTCNOW_WARNINGS", len(utcnow_notes))
    for note in utcnow_notes[:8]:
        print("UTCNOW:", note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
