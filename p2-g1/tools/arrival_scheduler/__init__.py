"""Arrival-rate scheduler (TST-0092)."""
from .scheduler import naive_burst, schedule_arrivals

WINDOW_TICKS = 10
__all__ = ["WINDOW_TICKS", "naive_burst", "schedule_arrivals"]
