"""Completion predicate library: one reducer, many sites, one census.

``reducer``  the single ``judge`` object every completion site must import
             (``completion.reducer.judge``); it never reads exit codes.
``census``   AST / regex census of ad-hoc ``exit_code == 0`` completion checks
             and the import-graph check that a site reaches the library judge.
``sites``    the declared live sites (harvester, cross-vendor adapter, local
             runner, monitor, workflow fan-in, final synthesis, cloud dispatcher)
             plus ``load_site`` / ``load_all`` adapters over them.

``reducer`` is imported first on purpose: ``census`` and ``sites`` both import
``completion.reducer`` by absolute name, so it must be bound on this package
before their re-exports run.
"""
from __future__ import annotations

from . import reducer
from .census import census_dir, census_file, import_graph_site
from .sites import SITE_FILES, SITE_IDS, load_all, load_site

__all__ = [
    "SITE_FILES",
    "SITE_IDS",
    "census_dir",
    "census_file",
    "import_graph_site",
    "load_all",
    "load_site",
    "census",
    "parse_cache",
    "reducer",
    "sites",
]
