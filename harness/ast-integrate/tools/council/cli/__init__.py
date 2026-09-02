"""Council command-line surface.

Submodules: ``audit`` (replay / inspect / lineage / explain over recorded councils), ``main``
(argument parsing and dispatch), ``runtime`` (process plumbing) and ``exit_codes``.  Import
the submodule you need; this package deliberately re-exports nothing so that loading the CLI
never pulls in the audit or runtime code paths implicitly.
"""
