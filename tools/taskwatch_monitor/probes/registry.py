"""Probe registry — resolve a ``TaskSpec.parser`` name to a probe instance.

The parser field on a :class:`~core.models.TaskSpec` selects which probe lifts
its adapter's lines into a :class:`~probes.base.ProbeReading`. Probes are
stateless, so a single shared instance per name is registered here.
"""

from __future__ import annotations

from .base import Probe, ProbeError
from .bpmd import BpmdModalProbe
from .fep import FepDatabricksProbe
from .generic import GenericLogfileProbe

_INSTANCES: tuple[Probe, ...] = (
    FepDatabricksProbe(),
    BpmdModalProbe(),
    GenericLogfileProbe(),
)

PROBES: dict[str, Probe] = {probe.name: probe for probe in _INSTANCES}


def probe_for(name: str) -> Probe | None:
    """Return the probe registered under ``name``, or ``None`` if unknown."""
    return PROBES.get(name)


def get_probe(name: str) -> Probe:
    """Return the probe registered under ``name`` or raise :class:`ProbeError`."""
    probe = PROBES.get(name)
    if probe is None:
        raise ProbeError(
            f"unknown parser '{name}'; registered probes are {sorted(PROBES)}"
        )
    return probe
