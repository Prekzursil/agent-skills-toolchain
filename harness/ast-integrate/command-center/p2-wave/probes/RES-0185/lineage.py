"""Extract recorded lineage locators. Does not fetch or read source bodies."""
from __future__ import annotations

from typing import Any

from vocabulary import canonical_url, canonicalize_class, classify_url

LINEAGE_KEYS = (
    "source_lineage",
    "citations",
    "rails",
    "sources",
    "evidence",
    "captures",
    "source_records",
    "lineage",
)

URL_KEYS = (
    "permalink",
    "canonical_permalink",
    "final_url",
    "url",
    "href",
    "locator",
)


def _sha(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    if len(s) == 64 and all(c in "0123456789abcdef" for c in s):
        return s
    return None


def _arxiv(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    if s.startswith("arxiv:"):
        s = s[6:]
    s = s.strip()
    if s:
        return s
    return None


def _doi(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = value.strip()
    if s.lower().startswith("https://doi.org/"):
        s = s[16:]
    if s.lower().startswith("http://doi.org/"):
        s = s[15:]
    s = s.strip().lower()
    return s or None


def identity_keys(loc: dict) -> list[str]:
    keys: list[str] = []
    sha = loc.get("sha256")
    if sha:
        keys.append(f"sha:{sha}")
    doi = loc.get("doi")
    if doi:
        keys.append(f"doi:{doi}")
    arxiv = loc.get("arxiv")
    if arxiv:
        keys.append(f"arxiv:{arxiv}")
    for field in ("canonical_url", "permalink"):
        url = loc.get(field)
        if url:
            keys.append(f"url:{url}")
            break
    sid = loc.get("source_id")
    if sid:
        keys.append(f"sid:{sid}")
    return keys


def locator_from_mapping(node: dict) -> dict | None:
    permalink = None
    for k in URL_KEYS:
        v = node.get(k)
        if isinstance(v, str) and v.strip().startswith(("http://", "https://")):
            permalink = v.strip()
            break
    sha = _sha(node.get("sha256"))
    arxiv = _arxiv(node.get("arxiv"))
    doi = _doi(node.get("doi"))
    sid = node.get("source_id") or node.get("id")
    if isinstance(sid, str):
        sid = sid.strip() or None
    else:
        sid = None
    recorded = canonicalize_class(
        node.get("source_class") or node.get("class") or node.get("kind")
    )
    if not any((permalink, sha, arxiv, doi, sid)):
        return None
    canon = canonical_url(permalink) if permalink else None
    classified = recorded
    if classified is None and permalink:
        classified = classify_url(permalink)
    if classified is None and canon:
        classified = classify_url(canon)
    if classified is None and (arxiv or doi):
        classified = "papers"
    loc = {
        "source_id": sid,
        "permalink": permalink,
        "canonical_url": canon,
        "sha256": sha,
        "arxiv": arxiv,
        "doi": doi,
        "source_class_recorded": recorded,
        "source_class": classified,
    }
    loc["identity_keys"] = identity_keys(loc)
    if not loc["identity_keys"]:
        return None
    return loc


def walk_locators(obj: Any, acc: list[dict], *, in_lineage: bool = False) -> None:
    if isinstance(obj, dict):
        loc = locator_from_mapping(obj) if in_lineage else None
        if loc is not None:
            acc.append(loc)
        for k, v in obj.items():
            walk_locators(v, acc, in_lineage=in_lineage or k in LINEAGE_KEYS)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, str) and in_lineage:
                sid = item.strip()
                if sid:
                    loc = {
                        "source_id": sid,
                        "permalink": None,
                        "canonical_url": None,
                        "sha256": None,
                        "arxiv": None,
                        "doi": None,
                        "source_class_recorded": None,
                        "source_class": None,
                        "identity_keys": [f"sid:{sid}"],
                    }
                    acc.append(loc)
            else:
                walk_locators(item, acc, in_lineage=in_lineage)


def locators_from_node(node: dict) -> list[dict]:
    """Locators recorded on this conclusion object only."""
    acc: list[dict] = []
    nested = False
    for k in LINEAGE_KEYS:
        if k in node:
            nested = True
            walk_locators(node[k], acc, in_lineage=True)
    self_loc = locator_from_mapping(node)
    if self_loc is not None:
        acc.append(self_loc)
    if not nested and self_loc is None:
        # Claim-shaped row with arxiv/doi/permalink at top level already handled.
        pass
    return _dedupe_exact(acc)


def locators_from_top_level_lineage(doc: dict) -> list[dict]:
    acc: list[dict] = []
    for k in LINEAGE_KEYS:
        if k in doc:
            walk_locators(doc[k], acc, in_lineage=True)
    return _dedupe_exact(acc)


def _dedupe_exact(locs: list[dict]) -> list[dict]:
    seen: set[tuple[str, ...]] = set()
    out: list[dict] = []
    for loc in locs:
        key = tuple(sorted(loc.get("identity_keys") or []))
        if key in seen:
            continue
        seen.add(key)
        out.append(loc)
    return out


def collapse_independent(locators: list[dict]) -> list[list[dict]]:
    """Union-find over shared identity keys. One citation object stays one source."""
    n = len(locators)
    if n == 0:
        return []
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    first: dict[str, int] = {}
    for i, loc in enumerate(locators):
        for k in loc.get("identity_keys") or []:
            if k in first:
                union(i, first[k])
            else:
                first[k] = i
    groups: dict[int, list[dict]] = {}
    for i, loc in enumerate(locators):
        groups.setdefault(find(i), []).append(loc)
    return list(groups.values())


def group_class(group: list[dict]) -> str | None:
    for loc in group:
        c = loc.get("source_class")
        if c:
            return c
    return None
