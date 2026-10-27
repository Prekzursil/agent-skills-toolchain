#!/usr/bin/env python3
"""CNF-0184 named normalizer set (wave-2 reconstruction, per receipt).

Five named normalizers, one per nondeterminism class, each carrying the
over-normalization contract: a planted CLAIM-BODY change is NEVER absorbed.
Reconstructed from the recorded descriptions in command-center/receipts/
CNF-0184.json (normalizer ids preserved).

Wave-2 port note: norm.temp_paths additionally folds Windows percent-TEMP
mkdtemp paths (this host returns them); the POSIX and macOS forms are the
receipt's own. Written with backslash-free regex classes so the port is
shell-mangle-proof.
"""
from __future__ import annotations

import json
import re

ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
LABELED_CLOCK_RE = re.compile(r"\b(?:now_s|now_ns|unix)=\d+")
TMPDIR_RE = re.compile(r"(?:/tmp/tmp[A-Za-z0-9_]+|/var/folders/[A-Za-z0-9_/]+|[A-Za-z]:..{0,120}?Temp[^A-Za-z0-9_][A-Za-z0-9_-]+)")
SEED_RE = re.compile(r"\b(?:rng|seed_draw|seed)[:=]\s*(?:0x[0-9a-fA-F]+|\d+\.\d+|\d+)")
HOST_RE = re.compile(r"\b(?:host|hostname|HOST)=\S+")


def norm_timestamps(text):
    out = ISO_RE.sub("<TIMESTAMP>", text)
    return LABELED_CLOCK_RE.sub("<TIMESTAMP>", out)


def norm_temp_paths(text):
    return TMPDIR_RE.sub("<TMPDIR>", text)


def norm_ordering(text):
    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text
    return json.dumps(doc, sort_keys=True)


def norm_seeds(text):
    return SEED_RE.sub("<SEED>", text)


def norm_host_identifiers(text):
    return HOST_RE.sub("<HOST>", text)


NORMALIZERS = [
    {"id": "norm.timestamps.iso-and-labeled-unix", "class": "timestamps", "fn": norm_timestamps},
    {"id": "norm.temp_paths.tmp-and-var-folders", "class": "temp_paths", "fn": norm_temp_paths},
    {"id": "norm.ordering.json-sort-keys", "class": "ordering", "fn": norm_ordering},
    {"id": "norm.seeds.labeled-draw", "class": "seeds", "fn": norm_seeds},
    {"id": "norm.host_identifiers.labeled-host", "class": "host_identifiers", "fn": norm_host_identifiers},
]


def over_normalization_control(fn):
    """True when the normalizer REFUSES to absorb a planted content change."""
    alpha, beta = "CLAIM-BODY: alpha", "CLAIM-BODY: beta"
    return fn(alpha) != fn(beta)
