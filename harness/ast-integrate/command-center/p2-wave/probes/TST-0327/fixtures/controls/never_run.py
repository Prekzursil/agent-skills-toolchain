#!/usr/bin/env python3
"""Control artifact that exists on disk but has never been observed in the ledger."""
print("TST-0327-control never_run (must not be treated as coverage)")
raise SystemExit(1)
