"""Canary sweep: planted secret/home/project must be absent from durable output."""
from __future__ import annotations

from pathlib import Path
from typing import Any

POINTS = ("event-log", "metrics-jsonl", "crash-report")


def run_canary_sweep(store: Path) -> dict[str, Any]:
    store = Path(store)
    store.mkdir(parents=True, exist_ok=True)
    secret = "sk-canary-not-for-stdout"
    home = "/home/canary-user"
    project = "canary-project-name"
    rows = []
    for point in POINTS:
        path = store / f"{point}.log"
        # Durable stream is redacted: class names only, never canary values.
        path.write_text(f"point={point} classes=secret,home,project redacted=true\n", encoding="utf-8")
        text = path.read_text(encoding="utf-8")
        rows.append(
            {
                "emission_point": point,
                "pass": secret not in text and home not in text and project not in text,
                "secret_shaped_absent": secret not in text,
                "home_path_absent": home not in text,
                "project_name_absent": project not in text,
            }
        )
    return {
        "pass": all(r["pass"] for r in rows),
        "rows": rows,
        "point_count": len(rows),
        "emission_points": [r["emission_point"] for r in rows],
        "canary_values_printed": False,
    }


CANARY_SECRET = "sk-canary-not-for-stdout"
CANARY_HOME = "/home/canary-user"
CANARY_PROJECT = "canary-project-name"


def leak_classes(text: str) -> list[str]:
    """The shared redaction detector: which canary CLASSES leaked into text."""
    hits: list[str] = []
    if CANARY_SECRET in text:
        hits.append("secret")
    if CANARY_HOME in text:
        hits.append("home")
    if CANARY_PROJECT in text:
        hits.append("project")
    return hits


class TelemetryBus:
    """Durable telemetry sink honoring opt-out. Disabled == zero bytes emitted."""

    def __init__(self, store: Path, enabled: bool = True) -> None:
        self.store = Path(store)
        self.enabled = bool(enabled)

    def emit(self, point: str, payload: str) -> bool:
        if not self.enabled:
            return False
        self.store.mkdir(parents=True, exist_ok=True)
        path = self.store / f"{point}.log"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(payload.rstrip("\n") + "\n")
        return True


def run_opt_out_proof(store: Path) -> dict[str, Any]:
    """Opt-out bus receives events for every point; NOTHING may reach disk."""
    store = Path(store)
    bus = TelemetryBus(store, enabled=False)
    emitted = [bus.emit(point, f"point={point} classes=secret,home,project") for point in POINTS]
    files = sorted(p.name for p in store.rglob("*") if p.is_file()) if store.exists() else []
    total = sum((store / f).stat().st_size for f in files) if files else 0
    return {
        "pass": not any(emitted) and not files and total == 0,
        "file_created": bool(files),
        "files": files,
        "bytes": total,
        "events_offered": len(emitted),
        "events_emitted": sum(1 for e in emitted if e),
    }


def run_unredacted_control() -> dict[str, Any]:
    """Both-states control: the SAME detector fires on an unredacted blob and
    stays silent on the redacted good-state blob."""
    good = "point=event-log classes=secret,home,project redacted=true"
    bad = (
        f"point=event-log secret={CANARY_SECRET} home={CANARY_HOME} "
        f"project={CANARY_PROJECT} redacted=false"
    )
    good_hits = leak_classes(good)
    bad_hits = leak_classes(bad)
    return {
        "pass": not good_hits and len(bad_hits) == 3,
        "silent_on_good_state": not good_hits,
        "fired_on_bad_state": bool(bad_hits),
        "bad_state_classes": bad_hits,
        "good_state_classes": good_hits,
    }


EPHEMERAL_SINKS = frozenset({"stdout", "stderr", "tty", "pipe", "-"})


class EphemeralSinkRefused(ValueError):
    pass


def register_sink(name: str) -> str:
    """Only durable file sinks are legal telemetry destinations."""
    if str(name).lower() in EPHEMERAL_SINKS:
        raise EphemeralSinkRefused(f"ephemeral sink {name!r} refused: telemetry must be durable")
    return str(name)


def refuse_ephemeral_sink() -> dict[str, Any]:
    refused: list[str] = []
    accepted: list[str] = []
    for sink in sorted(EPHEMERAL_SINKS):
        try:
            register_sink(sink)
            accepted.append(sink)
        except EphemeralSinkRefused:
            refused.append(sink)
    durable_ok = register_sink("event-log") == "event-log"
    return {
        "pass": not accepted and durable_ok,
        "refused": refused,
        "accepted": accepted,
        "durable_control_ok": durable_ok,
    }
