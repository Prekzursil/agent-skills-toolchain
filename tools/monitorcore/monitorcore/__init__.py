"""monitorcore — shared monitoring + export core for the unified monitoring platform.

Vendored (copied) into consuming skills as a single importable ``monitorcore``
package, so keep it stdlib-only at runtime: the vendored copy must import under a
skill's plain Python with no third-party dependencies. See ``README.md``.
"""

__version__ = "0.1.0"
