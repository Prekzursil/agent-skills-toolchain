"""Council anti-fail controls."""
from . import unanimity
from .unanimity import Vote, plurality

__all__ = ["unanimity", "Vote", "plurality"]
