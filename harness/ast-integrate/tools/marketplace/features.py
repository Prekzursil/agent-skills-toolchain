"""Feature-coverage matrix for the marketplace fixture registry (IMP-0118).

A fixture registry is only useful as a known-good corpus when every feature the
marketplace tests care about is *exercised* by at least one package.  This module
decides that structurally rather than by trusting labels: a package counts as

* ``signed`` when its signature record verifies (status ``"OK"``);
* ``multi-version`` when the index holds another version of the same name;
* ``with-dependencies`` when it declares dependencies and every one of them
  resolves to a package in the index;
* ``with-sbom`` when its payload manifest carries SBOM components (name+version);
* ``with-benchmark-evidence`` when its manifest carries a benchmark with the
  reproduction fields (command, seed, runs) and a numeric value;
* ``deprecated`` when its manifest points at a successor that exists in the index;
* ``channel-pinned`` when its manifest pins a channel that matches the index
  entry's channel and the version is visible under that pin.

:func:`coverage_matrix` reports, per declared feature, the sorted package ids
that back it, the declared features nobody exercises (``missing``) and every
package whose ``features`` labels or ``*_present`` flags disagree with the
structural evidence (``label_mismatches``).  ``complete`` is true only when both
lists are empty.  Output is deterministic and free of timestamps and paths.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from tools.marketplace.channels import resolve as channel_visible
from tools.marketplace.crypto import OK as SIGNATURE_OK
from tools.marketplace.crypto import verify_signature

__all__ = [
    "CHANNELS",
    "DECLARED_FEATURES",
    "FLAG_LABELS",
    "REPRODUCTION_FIELDS",
    "channel_of",
    "coverage_matrix",
    "declared_labels",
    "feature_evidence",
    "observed_features",
    "payload_document",
    "split_package_id",
]

#: The feature surface the fixture must span, in the order the receipt lists it.
DECLARED_FEATURES: tuple[str, ...] = (
    "signed",
    "multi-version",
    "with-dependencies",
    "with-sbom",
    "with-benchmark-evidence",
    "deprecated",
    "channel-pinned",
)

#: Release channels, least to most experimental (mirrors ``channels.py``).
CHANNELS: tuple[str, ...] = ("stable", "beta", "canary")

#: Index-entry boolean flags and the feature label each one asserts.
FLAG_LABELS: dict[str, str] = {
    "sbom_present": "with-sbom",
    "benchmark_present": "with-benchmark-evidence",
    "deprecated": "deprecated",
}

#: Fields a benchmark ``reproduction`` block must carry to count as evidence.
REPRODUCTION_FIELDS: tuple[str, ...] = ("command", "seed", "runs")


# --------------------------------------------------------------------------- small helpers


def split_package_id(package_id: str) -> tuple[str, str]:
    """Split ``name@version`` into its two parts (both non-empty) or raise ``ValueError``."""
    if not isinstance(package_id, str):
        raise ValueError(f"package id must be a string, not {type(package_id).__name__}")
    name, sep, version = package_id.partition("@")
    if not sep or not name or not version:
        raise ValueError(f"package id {package_id!r} is not of the form name@version")
    return name, version


def channel_of(version: str) -> str:
    """The release channel a version string belongs to.

    Pre-release tags name the channel (``1.2.0-canary.1`` -> ``canary``,
    ``1.1.0-beta.1`` -> ``beta``); anything else is ``stable``.  This is the
    same classification :mod:`tools.marketplace.channels` uses to decide
    visibility under a pin.
    """
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"version must be a non-empty string, not {version!r}")
    if "canary" in version:
        return "canary"
    if "beta" in version:
        return "beta"
    return "stable"


def payload_document(payload: Any) -> dict[str, Any] | None:
    """Parse a payload as a JSON object manifest; ``None`` when it is not one.

    Blobs are opaque bytes to the registry.  Packages that carry structural
    evidence (SBOM, benchmark, deprecation, channel pin) do so in a JSON object
    manifest; plain-text payloads yield ``None`` and can only evidence the
    index-level features (``signed``, ``multi-version``).
    """
    if isinstance(payload, Mapping):
        return dict(payload)
    if isinstance(payload, (bytes, bytearray, memoryview)):
        try:
            text = bytes(payload).decode("utf-8")
        except UnicodeDecodeError:
            return None
    elif isinstance(payload, str):
        text = payload
    else:
        return None
    text = text.strip()
    if not text.startswith("{"):
        return None
    try:
        doc = json.loads(text)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def _packages(index: Any) -> list[dict[str, Any]]:
    if not isinstance(index, Mapping):
        raise TypeError(f"index must be a mapping, not {type(index).__name__}")
    packages = index.get("packages")
    if not isinstance(packages, list):
        raise ValueError("index has no 'packages' list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pos, entry in enumerate(packages):
        if not isinstance(entry, Mapping):
            raise ValueError(f"index package #{pos} is not an object")
        pid = entry.get("id")
        if not isinstance(pid, str) or not pid:
            raise ValueError(f"index package #{pos} has no id")
        if pid in seen:
            raise ValueError(f"index lists package {pid!r} twice")
        seen.add(pid)
        out.append(dict(entry))
    return out


def _name_version(entry: Mapping[str, Any]) -> tuple[str, str]:
    name = entry.get("name")
    version = entry.get("version")
    if isinstance(name, str) and name and isinstance(version, str) and version:
        return name, version
    return split_package_id(str(entry["id"]))


def _resolve(ref: Any, by_id: Mapping[str, str], by_name: Mapping[str, list[str]]) -> str | None:
    """Resolve a dependency/successor reference to a package id in the index."""
    if isinstance(ref, str):
        if ref in by_id:
            return ref
        if "@" not in ref and by_name.get(ref):
            return sorted(by_name[ref])[-1]
        return None
    if isinstance(ref, Mapping):
        ref_id = ref.get("id")
        if isinstance(ref_id, str):
            return ref_id if ref_id in by_id else None
        name = ref.get("name")
        version = ref.get("version")
        if isinstance(name, str) and isinstance(version, str):
            candidate = f"{name}@{version}"
            return candidate if candidate in by_id else None
        if isinstance(name, str) and by_name.get(name):
            return sorted(by_name[name])[-1]
    return None


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# --------------------------------------------------------------------------- structural evidence


def _has_sbom(doc: Mapping[str, Any] | None) -> bool:
    if doc is None:
        return False
    sbom = doc.get("sbom")
    if not isinstance(sbom, Mapping):
        return False
    components = sbom.get("components")
    if not isinstance(components, list) or not components:
        return False
    return all(
        isinstance(c, Mapping) and _non_empty_str(c.get("name")) and _non_empty_str(c.get("version"))
        for c in components
    )


def _has_benchmark_evidence(doc: Mapping[str, Any] | None) -> bool:
    if doc is None:
        return False
    bench = doc.get("benchmark")
    if not isinstance(bench, Mapping):
        return False
    if not _non_empty_str(bench.get("metric")) or not _is_number(bench.get("value")):
        return False
    repro = bench.get("reproduction")
    if not isinstance(repro, Mapping) or any(f not in repro for f in REPRODUCTION_FIELDS):
        return False
    return (
        _non_empty_str(repro.get("command"))
        and _is_int(repro.get("seed"))
        and _is_int(repro.get("runs"))
        and repro["runs"] >= 1
    )


def _successor(doc: Mapping[str, Any] | None) -> Any:
    if doc is None:
        return None
    block = doc.get("deprecated")
    if isinstance(block, Mapping):
        return block.get("successor")
    return None


def _channel_pin(doc: Mapping[str, Any] | None) -> str | None:
    if doc is None:
        return None
    pin = doc.get("channel_pin")
    return pin if isinstance(pin, str) and pin in CHANNELS else None


def feature_evidence(
    entry: Mapping[str, Any],
    packages: Iterable[Mapping[str, Any]],
    payloads: Mapping[str, Any],
    sig_status: Mapping[str, str],
) -> dict[str, bool]:
    """Structural evidence for every declared feature on one index entry.

    ``packages`` is the whole index (needed for version pairs and reference
    resolution), ``payloads`` maps id -> blob bytes (or parsed manifest) and
    ``sig_status`` maps id -> verification status string.
    """
    pid = str(entry["id"])
    name, version = _name_version(entry)
    others = [dict(p) for p in packages if isinstance(p, Mapping) and p.get("id") != pid]
    by_id = {str(p["id"]): str(p["id"]) for p in others if isinstance(p.get("id"), str)}
    by_name: dict[str, list[str]] = {}
    for p in others:
        try:
            n, _v = _name_version(p)
        except (ValueError, KeyError):
            continue
        by_name.setdefault(n, []).append(str(p["id"]))
    doc = payload_document(payloads.get(pid)) if pid in payloads else None

    signed = isinstance(entry.get("signature"), Mapping) and sig_status.get(pid) == SIGNATURE_OK

    multi_version = any(
        _name_version(p)[0] == name and _name_version(p)[1] != version
        for p in others
        if isinstance(p.get("id"), str)
    )

    deps = entry.get("dependencies")
    with_dependencies = (
        isinstance(deps, list)
        and bool(deps)
        and all(_resolve(d, by_id, by_name) not in (None, pid) for d in deps)
    )
    if with_dependencies and doc is not None and isinstance(doc.get("dependencies"), list):
        with_dependencies = all(_resolve(d, by_id, by_name) not in (None, pid) for d in doc["dependencies"])

    successor = _successor(doc)
    deprecated = successor is not None and _resolve(successor, by_id, by_name) not in (None, pid)

    pin = _channel_pin(doc)
    channel = entry.get("channel")
    channel_pinned = (
        pin is not None
        and channel == pin
        and channel_of(version) == pin
        and bool(channel_visible(pin, version))
    )

    return {
        "signed": bool(signed),
        "multi-version": bool(multi_version),
        "with-dependencies": bool(with_dependencies),
        "with-sbom": _has_sbom(doc),
        "with-benchmark-evidence": _has_benchmark_evidence(doc),
        "deprecated": bool(deprecated),
        "channel-pinned": bool(channel_pinned),
    }


def observed_features(
    entry: Mapping[str, Any],
    packages: Iterable[Mapping[str, Any]],
    payloads: Mapping[str, Any],
    sig_status: Mapping[str, str],
) -> list[str]:
    """Declared features the entry structurally exercises, in declared order."""
    evidence = feature_evidence(entry, packages, payloads, sig_status)
    return [f for f in DECLARED_FEATURES if evidence[f]]


def declared_labels(entry: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """``(labels, unknown)``: the features an entry claims, and claims that are not declared features.

    Claims come from the ``features`` list and from the boolean flags in
    :data:`FLAG_LABELS` when they are true.
    """
    raw = entry.get("features")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ValueError(f"package {entry.get('id')!r}: 'features' must be a list")
    labels: set[str] = set()
    unknown: set[str] = set()
    for label in raw:
        if not isinstance(label, str) or not label:
            raise ValueError(f"package {entry.get('id')!r}: feature labels must be strings")
        (labels if label in DECLARED_FEATURES else unknown).add(label)
    for flag, label in FLAG_LABELS.items():
        if entry.get(flag) is True:
            labels.add(label)
    ordered = [f for f in DECLARED_FEATURES if f in labels]
    return ordered, sorted(unknown)


# --------------------------------------------------------------------------- the matrix


def coverage_matrix(
    index: Mapping[str, Any],
    payloads: Mapping[str, Any],
    sig_status: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Which packages exercise which declared features, and whether labels tell the truth.

    ``sig_status`` maps package id -> :func:`tools.marketplace.crypto.verify_signature`
    status; when omitted it is computed here from ``payloads`` and each entry's
    ``signature`` record.  Returns::

        {
          "declared_features": [...],            # DECLARED_FEATURES, in order
          "covered_by": {feature: [sorted ids]}, # structural evidence only
          "missing": [features nobody exercises],
          "label_mismatches": [per-package disagreements],
          "complete": bool,                      # no missing and no mismatches
        }

    A mismatch row names the package, its declared labels, the features
    observed structurally, the labels with no evidence behind them
    (``unbacked_labels``), evidence nobody labelled (``unlabelled_evidence``),
    labels outside the declared surface (``unknown_labels``) and ``*_present``
    flags that contradict the structure (``flag_disagreements``).
    """
    packages = _packages(index)
    if payloads is None:
        payloads = {}
    if not isinstance(payloads, Mapping):
        raise TypeError(f"payloads must map package id -> bytes, not {type(payloads).__name__}")
    if sig_status is None:
        sig_status = {
            entry["id"]: verify_signature(payloads.get(entry["id"]), entry.get("signature"))
            for entry in packages
        }
    elif not isinstance(sig_status, Mapping):
        raise TypeError(f"sig_status must map package id -> status, not {type(sig_status).__name__}")

    covered: dict[str, list[str]] = {feature: [] for feature in DECLARED_FEATURES}
    mismatches: list[dict[str, Any]] = []
    for entry in packages:
        pid = str(entry["id"])
        evidence = feature_evidence(entry, packages, payloads, sig_status)
        observed = [f for f in DECLARED_FEATURES if evidence[f]]
        for feature in observed:
            covered[feature].append(pid)
        labels, unknown = declared_labels(entry)
        unbacked = [f for f in labels if f not in observed]
        unlabelled = [f for f in observed if f not in labels]
        flag_disagreements = [
            {"flag": flag, "value": bool(entry.get(flag)), "observed": evidence[label]}
            for flag, label in FLAG_LABELS.items()
            if flag in entry and bool(entry.get(flag)) != evidence[label]
        ]
        if unbacked or unlabelled or unknown or flag_disagreements:
            mismatches.append(
                {
                    "id": pid,
                    "declared": labels,
                    "observed": observed,
                    "unbacked_labels": unbacked,
                    "unlabelled_evidence": unlabelled,
                    "unknown_labels": unknown,
                    "flag_disagreements": flag_disagreements,
                    "payload_present": pid in payloads,
                    "signature_status": sig_status.get(pid),
                }
            )

    covered_by = {feature: sorted(ids) for feature, ids in covered.items()}
    missing = [feature for feature in DECLARED_FEATURES if not covered_by[feature]]
    return {
        "declared_features": list(DECLARED_FEATURES),
        "covered_by": covered_by,
        "missing": missing,
        "label_mismatches": mismatches,
        "complete": not missing and not mismatches,
    }
