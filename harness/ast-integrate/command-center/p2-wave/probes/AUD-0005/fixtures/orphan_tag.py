"""String registry of the planted tag that has no GitHub release.

Probe 1 (git rev-list) still sees the tag. Probe 2 (release assets +
byte-size) must report it unpublished. A detector that treats missing
releases as parity fails this control.
"""

PLANTED_ORPHAN_TAG = "v0.0.0-aud0005-orphan"
