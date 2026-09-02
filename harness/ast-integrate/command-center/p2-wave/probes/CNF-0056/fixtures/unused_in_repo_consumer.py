"""In-repo consumer that only uses the stable public type and compute().

The unit contract: an undocumented removal is a defect even when nothing in
this repo uses the dropped symbol, because consumers are external.
"""

from pkg_api import PublicAlpha, compute  # noqa: F401
