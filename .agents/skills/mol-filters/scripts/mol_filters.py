#!/usr/bin/env python3
"""mol-filters: synthetic-accessibility SA_Score + structural-alert filtering.

For each input molecule (single SMILES, a one-per-line SMILES file, or an SDF)
this reports:

  1. SA_Score   -- Ertl & Schuffenhauer (2009) synthetic accessibility, where
                   1 = easy to synthesize ... 10 = hard to synthesize.
  2. Structural-alert hits from RDKit's FilterCatalog across the PAINS_A/B/C,
     BRENK, NIH and ZINC catalogs, with the matched alert's description.

SA_Score lives in RDKit's Contrib tree (not importable by default) and is
absent from some RDKit wheels; when it is missing the SA_Score degrades to
``null`` with a note and the structural-alert filters still run.

Usage:
    python mol_filters.py "CCO"
    python mol_filters.py --smiles-file mols.smi
    python mol_filters.py --sdf library.sdf
    python mol_filters.py "O=C1CSC(=S)N1" --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from rdkit import Chem, RDLogger
from rdkit.Chem import FilterCatalog
from rdkit.Chem.FilterCatalog import FilterCatalogParams

# RDKit logs a C++ error to stderr for every unparseable SMILES; we report bad
# input ourselves, so keep the console clean.
RDLogger.DisableLog("rdApp.*")

# Structural-alert catalogs to load, in a stable, documented order.
CATALOG_NAMES = ("PAINS_A", "PAINS_B", "PAINS_C", "BRENK", "NIH", "ZINC")

SA_UNAVAILABLE_NOTE = "SA_Score unavailable (RDKit Contrib not present)"

# Lazy, cached handle to Ertl's sascorer module.
_sascorer = None
_sascorer_loaded = False


def get_sascorer():
    """Return the sascorer module, or None if RDKit Contrib is unavailable.

    ``sascorer`` is not importable by default: it ships inside RDKit's Contrib
    tree. We locate it via ``RDConfig.RDContribDir`` and import it once. If the
    Contrib directory or the module is absent (some wheels omit Contrib), we
    cache and return None instead of raising.
    """
    global _sascorer, _sascorer_loaded
    if _sascorer_loaded:
        return _sascorer
    _sascorer_loaded = True
    try:
        from rdkit.Chem import RDConfig

        sa_dir = os.path.join(RDConfig.RDContribDir, "SA_Score")
        if sa_dir not in sys.path:
            sys.path.append(sa_dir)
        import sascorer  # type: ignore  # noqa: E402  (Contrib path added above)

        _sascorer = sascorer
    except Exception:  # ImportError, missing Contrib, unreadable fpscores, ...
        _sascorer = None
    return _sascorer


def sa_score(mol):
    """SA_Score for an RDKit mol, or None if the mol/scorer is unavailable."""
    scorer = get_sascorer()
    if scorer is None or mol is None:
        return None
    try:
        return float(scorer.calculateScore(mol))
    except Exception:
        return None


def build_filter_catalog(names=CATALOG_NAMES):
    """Build a FilterCatalog spanning the requested structural-alert catalogs."""
    params = FilterCatalogParams()
    for name in names:
        catalog = getattr(FilterCatalogParams.FilterCatalogs, name)
        params.AddCatalog(catalog)
    return FilterCatalog.FilterCatalog(params)


def filter_hits(mol, catalog):
    """Return [{'catalog': <FilterSet>, 'alert': <description>}, ...] for a mol."""
    hits = []
    if mol is None:
        return hits
    for entry in catalog.GetMatches(mol):
        try:
            catalog_name = entry.GetProp("FilterSet")
        except Exception:
            catalog_name = ""
        hits.append({"catalog": catalog_name, "alert": entry.GetDescription()})
    return hits


def _result(smiles, mol, catalog, name=None):
    """Build the per-molecule result dict (uniform schema for all input modes)."""
    if mol is None:
        return {
            "smiles": smiles,
            "name": name,
            "valid": False,
            "error": "invalid SMILES",
            "sa_score": None,
            "sa_score_note": None,
            "num_alerts": 0,
            "filter_hits": [],
        }
    score = sa_score(mol)
    hits = filter_hits(mol, catalog)
    return {
        "smiles": smiles,
        "name": name,
        "valid": True,
        "error": None,
        "sa_score": score,
        "sa_score_note": None if score is not None else SA_UNAVAILABLE_NOTE,
        "num_alerts": len(hits),
        "filter_hits": hits,
    }


def analyze_smiles(smiles, catalog=None):
    """Analyze a single SMILES string. Never raises on malformed input."""
    if catalog is None:
        catalog = build_filter_catalog()
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    return _result(smiles, mol, catalog)


def analyze_smiles_list(smiles_list, catalog=None):
    """Analyze many SMILES strings, reusing one FilterCatalog."""
    if catalog is None:
        catalog = build_filter_catalog()
    return [analyze_smiles(s, catalog) for s in smiles_list]


def read_smiles_file(path):
    """Read one SMILES per line.

    Blank lines and ``#`` comments are skipped; only the first whitespace token
    of a line is taken, so ``<SMILES> <name>`` lines work.
    """
    out = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line.split()[0])
    return out


def analyze_sdf(path, catalog=None):
    """Analyze every record in an SDF file (bad records are flagged invalid)."""
    if catalog is None:
        catalog = build_filter_catalog()
    results = []
    supplier = Chem.SDMolSupplier(str(path))
    for index, mol in enumerate(supplier):
        if mol is None:
            results.append(_result(f"<SDF record {index}>", None, catalog))
            continue
        name = mol.GetProp("_Name") if mol.HasProp("_Name") else None
        results.append(_result(Chem.MolToSmiles(mol), mol, catalog, name=name or None))
    return results


def format_text(results):
    """Render results as a readable per-molecule text report."""
    lines = []
    for r in results:
        header = r["smiles"]
        if r.get("name"):
            header = f'{r["name"]}  {header}'
        if not r["valid"]:
            lines.append(f"[INVALID] {header}  ({r['error']})")
            continue
        lines.append(header)
        if r["sa_score"] is None:
            lines.append(f"  SA_Score: n/a  ({r['sa_score_note']})")
        else:
            lines.append(f"  SA_Score: {r['sa_score']:.2f}")
        if r["filter_hits"]:
            lines.append(f"  Alerts ({r['num_alerts']}):")
            for hit in r["filter_hits"]:
                lines.append(f"    - {hit['catalog']}: {hit['alert']}")
        else:
            lines.append("  Alerts: none")
    return "\n".join(lines)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="mol_filters.py",
        description=(
            "SA_Score (synthetic accessibility) + PAINS/BRENK/NIH/ZINC "
            "structural-alert filtering for SMILES/SDF."
        ),
    )
    parser.add_argument("smiles", nargs="?", help="a single SMILES string")
    parser.add_argument(
        "--sdf", metavar="PATH", help="analyze every molecule in an SDF file"
    )
    parser.add_argument(
        "--smiles-file",
        metavar="PATH",
        help="analyze a file with one SMILES per line",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )
    return parser


def run(args):
    """Dispatch parsed args to the right input mode; return results or None."""
    catalog = build_filter_catalog()
    if args.sdf:
        return analyze_sdf(args.sdf, catalog)
    if args.smiles_file:
        return analyze_smiles_list(read_smiles_file(args.smiles_file), catalog)
    if args.smiles:
        return [analyze_smiles(args.smiles, catalog)]
    return None


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    results = run(args)
    if results is None:
        parser.error("provide a SMILES, --smiles-file PATH, or --sdf PATH")
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(format_text(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
