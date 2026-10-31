"""Rail adapter facades for the Cross-Rail Control Plane."""

from .base import RailAdapter
from .chatgpt import ChatGPTRail

__all__ = ["ChatGPTRail", "RailAdapter"]
