"""mcpapply -- the MUTATION sibling of the read-only ``mcpctl`` inventory core.

``mcpctl`` is read-only BY CONSTRUCTION: one of its tests walks the AST of every
module in the package and fails on any write call, any out-of-process call, and any
``http``/``socket``/``urllib`` import. That invariant is the reason this package
exists as a separate distribution instead of as an ``mcpctl.write`` submodule -- the
writer, the process guard and the loopback web GUI would each break the gate that
makes ``mcpctl`` trustworthy to read from.

So the split is: ``mcpctl`` owns every READ (the five scopes, their measured
precedence, the object-shaped ``deniedMcpServers``, the exact-cwd ``projects`` row,
credential-name-only redaction, the health matrix). ``mcpapply`` imports it and owns
everything that CHANGES something.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
