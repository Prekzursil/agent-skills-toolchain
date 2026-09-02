"""Planted second completion predicate. Scan-only fixture for ARC-0064 probe 2.

A local judge that treats exit_code == 0 as COMPLETE. The shared reducer
forbids that collapse. This file is not a call site.
"""


def judge(exit_code):
    if exit_code == 0:
        return "COMPLETE"
    return "INCOMPLETE"
