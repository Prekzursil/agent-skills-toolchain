"""Hand-computed speaking-order expectations for IMP-0337 probe1.

These literals were derived from the seating chart in comments below, not
from tools/council/order.py. Probe1 fails if the live module disagrees.
"""

from __future__ import annotations

# Roster (index is the tie-break):
#   0 alice priority=3 seniority=10 chair
#   1 bob   priority=1 seniority=8
#   2 cara  priority=2 seniority=2
#   3 drew  priority=2 seniority=5
#
# round-robin r: rotate left by r.
# priority: alice(3), then cara before drew (both 2, cara has lower index), bob(1).
# seniority-inverted: cara(2), drew(5), bob(8), alice(10).
# chair-recognition: chair alice, then remaining roster / recognition list.
# random: Random(7 + 1009*r).shuffle of [alice, bob, cara, drew].

HAND_ROSTER_SPEC = (
    {"seat_id": "alice", "priority": 3, "seniority": 10, "is_chair": True},
    {"seat_id": "bob", "priority": 1, "seniority": 8, "is_chair": False},
    {"seat_id": "cara", "priority": 2, "seniority": 2, "is_chair": False},
    {"seat_id": "drew", "priority": 2, "seniority": 5, "is_chair": False},
)

HAND_EXPECTED = {
    ("round-robin", 0, None): ["alice", "bob", "cara", "drew"],
    ("round-robin", 1, None): ["bob", "cara", "drew", "alice"],
    ("round-robin", 2, None): ["cara", "drew", "alice", "bob"],
    ("round-robin", 3, None): ["drew", "alice", "bob", "cara"],
    ("round-robin", 4, None): ["alice", "bob", "cara", "drew"],
    ("priority", 0, None): ["alice", "cara", "drew", "bob"],
    ("seniority-inverted", 0, None): ["cara", "drew", "bob", "alice"],
    ("chair-recognition", 0, None): ["alice", "bob", "cara", "drew"],
    ("chair-recognition", 0, ("drew", "cara", "bob")): [
        "alice",
        "drew",
        "cara",
        "bob",
    ],
    ("random", 0, None): ["drew", "bob", "alice", "cara"],
    ("random", 1, None): ["alice", "bob", "drew", "cara"],
    ("random", 2, None): ["drew", "bob", "cara", "alice"],
}

RANDOM_SEED = 7
