"""Provenance validation for preprint-citable capture (WU-2L).

Every captured Datum MUST carry complete provenance: a database name, an
access-date, and at least one citable locator (PMID or accession). ``source_class``
must be stamped on EVERY Datum (the closed Literal domain from :mod:`wearables.datum`).

Pure validation/formatting — no I/O. The capture stage (WU-2F) calls
:func:`require_provenance` BEFORE writing so a Datum missing provenance is
refused (fail-closed) rather than persisted un-citable.
"""

from __future__ import annotations

import re

from .datum import _SOURCE_CLASSES, Datum, Provenance

# Minimal ISO date shape (YYYY-MM-DD); we validate shape, not calendar.
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ProvenanceError(ValueError):
    """Raised when a Datum lacks the provenance required for citable capture."""


def _has_locator(prov: Provenance) -> bool:
    """A citable locator = a non-empty PMID or accession."""
    pmid_ok = bool(prov.pmid and str(prov.pmid).strip())
    acc_ok = bool(prov.accession and str(prov.accession).strip())
    return pmid_ok or acc_ok


def require_provenance(datum: Datum) -> Datum:
    """Return ``datum`` unchanged iff its provenance is complete; else raise.

    Complete = a :class:`Provenance` with a non-empty ``db``, a well-formed ISO
    ``access_date``, and at least one citable locator (PMID or accession). The
    Datum's ``source_class`` must also be in the closed Literal domain.
    """
    prov = datum.provenance
    if not isinstance(prov, Provenance):
        raise ProvenanceError("Datum has no Provenance record")
    if not (prov.db and str(prov.db).strip()):
        raise ProvenanceError("provenance.db is required")
    if not (prov.access_date and _ISO_DATE.match(str(prov.access_date))):
        raise ProvenanceError("provenance.access_date must be an ISO date (YYYY-MM-DD)")
    if not _has_locator(prov):
        raise ProvenanceError("provenance needs a citable locator (PMID or accession)")
    if datum.source_class not in _SOURCE_CLASSES:
        raise ProvenanceError(
            f"source_class {datum.source_class!r} not in allowed domain"
        )
    return datum


def provenance_fields(datum: Datum) -> dict:
    """Flatten a Datum's provenance into a preprint-citable field dict."""
    prov = datum.provenance
    return {
        "pmid": prov.pmid,
        "db": prov.db,
        "accession": prov.accession,
        "access_date": prov.access_date,
        "source": datum.source,
        "source_class": datum.source_class,
    }
