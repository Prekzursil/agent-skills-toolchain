"""Per-vendor identical-output rate measurement (IMP-0260)."""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Sequence

NOT_PINNABLE = "NOT-PINNABLE"
PINNED = "PINNED"
ESTATE_LIVE_HTTP_RESIDUAL = False
N_REPEATS = 8


@dataclass
class SamplingParams:
    seed: int | None = None
    temperature: float = 0.0


@dataclass
class SeatSpec:
    seat_id: str
    vendor: str
    model: str
    sampling: SamplingParams


class SeedHonouringVendor:
    def __init__(self, vendor_id: str) -> None:
        self.vendor_id = vendor_id

    def sample(self, prompt: str, seed: int | None) -> str:
        material = f"{self.vendor_id}:{seed}:{prompt}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


class SeedIgnoringVendor:
    def __init__(self, vendor_id: str) -> None:
        self.vendor_id = vendor_id
        self._n = 0

    def sample(self, prompt: str, seed: int | None) -> str:
        self._n += 1
        material = f"{self.vendor_id}:tick-{self._n}:{prompt}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


class UnseededStableVendor:
    def __init__(self, vendor_id: str) -> None:
        self.vendor_id = vendor_id

    def sample(self, prompt: str, seed: int | None) -> str:
        return hashlib.sha256(f"{self.vendor_id}:stable:{prompt}".encode("utf-8")).hexdigest()[:16]


def identical_output_rate(outputs: Sequence[str]) -> float:
    if not outputs:
        raise ValueError("no outputs")
    counts = Counter(outputs)
    return max(counts.values()) / float(len(outputs))


def classify(rec: dict[str, Any] | None = None, **kwargs: Any) -> Any:
    if rec is None:
        rec = {
            "seed_exposed": kwargs.get("seed_exposed"),
            "identical_output_rate": kwargs.get("rate"),
            "sampling": {"seed": 1 if kwargs.get("seed_exposed") else None},
        }
        status, reason = _classify_pair(rec)
        return {"pin_status": status, "pin_reason": reason}
    return _classify_pair(rec)


def _classify_pair(rec: dict[str, Any]) -> tuple[str, str]:
    seed = rec.get("sampling", {}).get("seed")
    rate = rec.get("identical_output_rate")
    seed_exposed = rec.get("seed_exposed")
    if not seed_exposed or seed is None:
        return NOT_PINNABLE, "seed-not-exposed"
    if rate is None or rate < 1.0:
        return NOT_PINNABLE, "seed-ignored"
    return PINNED, "seed-honoured"


def liar_classify_if_seed_exposed(rec: dict[str, Any]) -> tuple[str, str]:
    if rec.get("seed_exposed"):
        return PINNED, "assumed-from-seed-parameter"
    return classify(rec)


def record_seat(
    spec: SeatSpec,
    vendor: Any,
    classifier: Callable[[dict[str, Any]], tuple[str, str]] = classify,
    prompt: str = "determinism-probe",
    n: int = N_REPEATS,
) -> dict[str, Any]:
    outputs = [vendor.sample(prompt, spec.sampling.seed) for _ in range(n)]
    rate = identical_output_rate(outputs)
    rec = {
        "seat_id": spec.seat_id,
        "vendor": spec.vendor,
        "model": spec.model,
        "seed_exposed": spec.sampling.seed is not None,
        "sampling": {"seed": spec.sampling.seed, "temperature": spec.sampling.temperature},
        "outputs": outputs,
        "identical_output_rate": rate,
        "distinct_outputs": len(set(outputs)),
        "pin_status": "",
        "pin_reason": "",
    }
    classified = classifier(rec)
    if isinstance(classified, tuple):
        status, reason = classified
    else:
        status, reason = classified["pin_status"], classified["pin_reason"]
    rec["pin_status"] = status
    rec["pin_reason"] = reason
    return rec


def default_council() -> list[SeatSpec]:
    return [
        SeatSpec("s-seeded", "local-echo-seeded", "echo-v1", SamplingParams(seed=7, temperature=0.0)),
        SeatSpec("s-ignored", "local-echo-seed-ignored", "echo-v1", SamplingParams(seed=7, temperature=0.0)),
        SeatSpec("s-unseeded", "local-echo-unseeded", "echo-v1", SamplingParams(seed=None, temperature=0.0)),
    ]


def estate_vendors() -> set[str]:
    return {s.vendor for s in default_council()} | {
        "seed-ignoring-mutant",
        "seed-honouring-control",
    }


def _vendor_for(spec: SeatSpec) -> Any:
    if spec.vendor == "local-echo-seed-ignored":
        return SeedIgnoringVendor(spec.vendor)
    if spec.vendor == "local-echo-unseeded":
        return UnseededStableVendor(spec.vendor)
    return SeedHonouringVendor(spec.vendor)


def record_council() -> dict[str, Any]:
    seats = []
    for spec in default_council():
        seats.append(record_seat(spec, _vendor_for(spec)))
    pinned = sum(1 for s in seats if s["pin_status"] == PINNED)
    return {
        "seats": seats,
        "council_reproducible_fraction": pinned / float(len(seats)),
        "live_http_measured": False,
        "measurement_surface": "local-echo-vendors",
        "per_vendor": {s["vendor"]: s["pin_status"] for s in seats},
    }
