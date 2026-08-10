"""``astplugin`` — the real, installable ast-integrate platform plugin.

Phase 5 of the program spec (`_USER-PROMPTS.md:10824-10842`). This is a package, not a design:
``python platform/plugin/cli.py build`` produces a deterministic archive, and
``install / update / repair / rollback / uninstall / sync / cache / health-check / conform /
migrate / diagnose / doctor`` all run against a real prefix.

Module map:

============================ =================================================================
``errors``                   error taxonomy, exit-code contract, message renderer
``fsops``                    containment, reserved names, long paths, EOL-stable hashing
``proc``                     explicit interpreters, argv-array exec, per-OS launch adapters
``manifest``                 strict manifest parse + client negotiation
``payload``                  deny-by-default allowlist, forbidden scan, secret gate, inventory
``packager``                 deterministic zip pack/unpack
``journal``                  prefix layout, lock, transaction journal, crash recovery
``deploy``                   live sync, per-file provenance, two-directional drift classifier
``lifecycle``                install / update / repair / rollback / uninstall
``cache``                    content-addressed cache, refresh, invalidation, quarantine
``health``                   probe registry + both-states control harness + doctor
``conformance``              the plugin's own contract test over a built package
``migrate``                  legacy-layout migration + compatibility diagnostics
``logs``                     structured logging with deny-by-default redaction
``policy``                   exec policy + fail-open/fail-closed table
``schemas``                  JSON Schemas for every emitted artifact + the manifest schema
``build``                    staging-tree projection + the build entry point
``cli``                      the ``astplugin`` command line
============================ =================================================================
"""

from __future__ import annotations

__all__ = ["__version__"]

#: Kept in step with ``build.PLUGIN_VERSION``; ``test_build.py`` asserts they agree.
__version__ = "1.0.0"
