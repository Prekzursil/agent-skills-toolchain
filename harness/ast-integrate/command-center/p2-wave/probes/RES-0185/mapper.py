"""Score a conclusion from recorded lineage only. Never fetches, never reads bodies."""
from __future__ import annotations

from lineage import collapse_independent, group_class
from vocabulary import SOURCE_CLASSES

UNSUPPORTED = "UNSUPPORTED"
SINGLE_SOURCE = "SINGLE-SOURCE"
SINGLE_CLASS = "SINGLE-CLASS"
MULTI = "MULTI"


def score(lineage_records: list[dict]) -> dict:
    groups = collapse_independent(lineage_records)
    n_src = len(groups)
    class_counts: dict[str, int] = {c: 0 for c in SOURCE_CLASSES}
    class_counts["unclassified"] = 0
    independent: list[dict] = []
    classes_present: list[str] = []
    for g in groups:
        cls = group_class(g) or "unclassified"
        if cls not in class_counts:
            cls = "unclassified"
        class_counts[cls] += 1
        if cls not in classes_present:
            classes_present.append(cls)
        lead = g[0]
        independent.append(
            {
                "identity_keys": sorted(
                    {k for loc in g for k in (loc.get("identity_keys") or [])}
                ),
                "source_class": None if cls == "unclassified" else cls,
                "locator_n": len(g),
                "sha256": lead.get("sha256"),
                "permalink": lead.get("permalink") or lead.get("canonical_url"),
                "source_id": lead.get("source_id"),
            }
        )
    named_classes = [c for c in classes_present if c != "unclassified"]
    n_cls = len(named_classes)
    if n_src == 0:
        status = UNSUPPORTED
        single_source = False
        single_class = False
    else:
        single_source = n_src == 1
        single_class = n_cls == 1
        if single_source:
            status = SINGLE_SOURCE
        elif single_class:
            status = SINGLE_CLASS
        else:
            status = MULTI
    return {
        "independent_source_count": n_src,
        "class_count": n_cls,
        "single_source": single_source,
        "single_class": single_class,
        "support_status": status,
        "classes": named_classes,
        "class_counts": class_counts,
        "independent_sources": independent,
    }
