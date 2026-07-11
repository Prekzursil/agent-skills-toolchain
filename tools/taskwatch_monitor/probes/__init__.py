"""Probes: log-line parsers that lift a raw poll into a progress reading.

A *probe* consumes the ``lines`` a source adapter's ``poll()`` returns (see
:mod:`core.adapters`) and distils them into a :class:`~probes.base.ProbeReading`
— a ``done``/``total`` frontier plus phase, GPU, and terminal signals — WITHOUT
the two bug-classes the FEP dashboard shipped (grill S6):

* **No phantom cap.** A frontier that runs past its denominator is preserved as
  an overshoot (``fraction() > 1``), never clamped — so the ETA band widens
  instead of a hidden clamp hiding that the model is off.
* **Frontier, not distinct-count.** Progress is the MAX index reached across the
  whole record, immune to log-rolloff (a rolled tail can never undercount).

Two live probes ship (``fep-databricks``, ``bpmd-modal``) plus a
``generic-logfile`` fallback; :mod:`probes.templates` carries the ready-made
registry-entry presets (modal, gh-actions-ci, rclone, builds, git, llm, …).
"""

from __future__ import annotations

from .base import (
    Probe,
    ProbeError,
    ProbeReading,
    extract_gpu,
    frontier_of,
    parse_ratio,
    reading_from_poll,
)
from .bpmd import BpmdModalProbe
from .fep import FepDatabricksProbe
from .generic import GenericLogfileProbe
from .registry import PROBES, get_probe, probe_for
from .templates import (
    TEMPLATES,
    TaskTemplate,
    TemplateError,
    build_from_template,
    template_for,
)

__all__ = [
    "PROBES",
    "TEMPLATES",
    "BpmdModalProbe",
    "FepDatabricksProbe",
    "GenericLogfileProbe",
    "Probe",
    "ProbeError",
    "ProbeReading",
    "TaskTemplate",
    "TemplateError",
    "build_from_template",
    "extract_gpu",
    "frontier_of",
    "get_probe",
    "parse_ratio",
    "probe_for",
    "reading_from_poll",
    "template_for",
]
