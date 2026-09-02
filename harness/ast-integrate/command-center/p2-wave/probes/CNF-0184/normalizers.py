"""Named output normalizers for CNF-0184.

Each class has one named function. Patterns are labeled/structured on purpose:
a planted CLAIM-BODY word change must survive every normalizer.
"""
from __future__ import annotations

import json
import re
from typing import Callable

CLASS_TIMESTAMPS = "timestamps"
CLASS_TEMP_PATHS = "temp_paths"
CLASS_ORDERING = "ordering"
CLASS_SEEDS = "seeds"
CLASS_HOST = "host_identifiers"

ISO_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)
LABELED_UNIX_RE = re.compile(r"\b(?:unix|epoch|ts|now_s)=(\d{9,11})\b")
LABELED_NS_RE = re.compile(r"\b(?:now_ns|ts_ns)=(\d{15,21})\b")
TMP_RE = re.compile(
    r"(?:/tmp/tmp[A-Za-z0-9_]+|/var/folders/[A-Za-z0-9_./-]+|"
    r"[A-Za-z]:\\Users\\[^\\\s]+\\AppData\\Local\\Temp\\[A-Za-z0-9._-]+)"
)
HOST_RE = re.compile(r"\b(?:host|hostname|HOST)=([A-Za-z0-9._-]+)\b")
SEED_RE = re.compile(r"\b(?:rng|seed_draw|seed)=([0-9A-Fa-f.]+)\b")

TOKEN = {
    CLASS_TIMESTAMPS: "<TIMESTAMP>",
    CLASS_TEMP_PATHS: "<TMPDIR>",
    CLASS_SEEDS: "<SEED>",
    CLASS_HOST: "<HOST>",
}


def normalize_timestamps(text: str) -> str:
    out = ISO_RE.sub(TOKEN[CLASS_TIMESTAMPS], text)
    out = LABELED_UNIX_RE.sub("now_s=" + TOKEN[CLASS_TIMESTAMPS], out)
    out = LABELED_NS_RE.sub("now_ns=" + TOKEN[CLASS_TIMESTAMPS], out)
    return out


def normalize_temp_paths(text: str) -> str:
    return TMP_RE.sub(TOKEN[CLASS_TEMP_PATHS], text)


def normalize_seeds(text: str) -> str:
    return SEED_RE.sub("seed_draw=" + TOKEN[CLASS_SEEDS], text)


def normalize_host_identifiers(text: str) -> str:
    return HOST_RE.sub("host=" + TOKEN[CLASS_HOST], text)


def _canonicalize_json_blob(blob: str) -> str:
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError:
        return blob
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def normalize_ordering(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            return json.dumps(obj, sort_keys=True, separators=(",", ":")) + (
                "\n" if text.endswith("\n") else ""
            )
    lines = text.splitlines(keepends=True)
    rebuilt: list[str] = []
    for line in lines:
        core, nl = (line[:-1], "\n") if line.endswith("\n") else (line, "")
        rebuilt.append(_canonicalize_json_blob(core) + nl)
    return "".join(rebuilt)


NORMALIZERS: dict[str, Callable[[str], str]] = {
    CLASS_TIMESTAMPS: normalize_timestamps,
    CLASS_TEMP_PATHS: normalize_temp_paths,
    CLASS_ORDERING: normalize_ordering,
    CLASS_SEEDS: normalize_seeds,
    CLASS_HOST: normalize_host_identifiers,
}

NORMALIZER_IDS = {
    CLASS_TIMESTAMPS: "norm.timestamps.iso-and-labeled-unix",
    CLASS_TEMP_PATHS: "norm.temp_paths.tmp-and-var-folders",
    CLASS_ORDERING: "norm.ordering.json-sort-keys",
    CLASS_SEEDS: "norm.seeds.labeled-draw",
    CLASS_HOST: "norm.host_identifiers.labeled-host",
}

DESCRIPTIONS = {
    CLASS_TIMESTAMPS: (
        "Replace ISO-8601 datetimes and labeled unix/ns clocks "
        "(now_s=, now_ns=, unix=) with <TIMESTAMP>. Bare integers are left intact."
    ),
    CLASS_TEMP_PATHS: (
        "Replace mkdtemp-style /tmp/tmp* and macOS /var/folders paths with "
        "<TMPDIR>. The literal token /tmp alone is not rewritten."
    ),
    CLASS_ORDERING: (
        "Parse JSON objects/arrays and re-dump with sort_keys=True so key and "
        "set permutation is not treated as a content change."
    ),
    CLASS_SEEDS: (
        "Replace labeled rng/seed_draw/seed hex or float draws with <SEED>. "
        "Unlabeled numbers are not rewritten."
    ),
    CLASS_HOST: (
        "Replace labeled host=/hostname=/HOST= values with <HOST>. Same-host "
        "double-runs typically do not vary; the class is proven by a HOST override."
    ),
}


def apply_one(class_name: str, text: str) -> str:
    fn = NORMALIZERS[class_name]
    return fn(text)


def apply_all(text: str) -> str:
    out = text
    for cls in (
        CLASS_TIMESTAMPS,
        CLASS_TEMP_PATHS,
        CLASS_SEEDS,
        CLASS_HOST,
        CLASS_ORDERING,
    ):
        out = apply_one(cls, out)
    return out


def looks_timestamped(text: str) -> bool:
    return bool(
        ISO_RE.search(text) or LABELED_UNIX_RE.search(text) or LABELED_NS_RE.search(text)
    )


def classes_that_equalize(a: str, b: str) -> list[str]:
    """Which single-class normalizers make a and b identical."""
    if a == b:
        return []
    found: list[str] = []
    for cls, fn in NORMALIZERS.items():
        if fn(a) == fn(b):
            found.append(cls)
    return found


PLANTED_A = "CLAIM-BODY: alpha\nnow=2026-01-01T00:00:00Z\n"
PLANTED_B = "CLAIM-BODY: beta\nnow=2026-01-01T00:00:00Z\n"


def over_normalization_report() -> list[dict]:
    rows = []
    for cls, fn in NORMALIZERS.items():
        na, nb = fn(PLANTED_A), fn(PLANTED_B)
        absorbed = na == nb
        rows.append(
            {
                "class": cls,
                "normalizer_id": NORMALIZER_IDS[cls],
                "planted_change": "CLAIM-BODY: alpha -> beta",
                "absorbed": absorbed,
            }
        )
    return rows


# Import aliases used by probes/emit.
apply_one = apply_one
apply_all = apply_all
DESCRIPTIONS = DESCRIPTIONS
NORMALIZER_IDS = NORMALIZER_IDS
over_normalization_report = over_normalization_report
PLANTED_A = PLANTED_A
PLANTED_B = PLANTED_B
