"""Planted both-states control for AUD-0089.

planted_high_ccn has many independent branches so lizard and radon must both
rank it above planted_low_ccn (CCN 1) in this directory. Not part of the
product baseline; probes scan this folder separately.
"""


def planted_low_ccn(x):
    """Straight-line function; cyclomatic complexity must remain 1."""
    return x + 1


def planted_high_ccn(value):
    """Independent predicates: each `if` is a decision both analyzers count."""
    acc = 0
    if value == 0:
        acc += 1
    if value == 1:
        acc += 2
    if value == 2:
        acc += 3
    if value == 3:
        acc += 4
    if value == 4:
        acc += 5
    if value == 5:
        acc += 6
    if value == 6:
        acc += 7
    if value == 7:
        acc += 8
    if value == 8:
        acc += 9
    if value == 9:
        acc += 10
    if value == 10:
        acc += 11
    if value == 11:
        acc += 12
    if value == 12:
        acc += 13
    if value == 13:
        acc += 14
    if value == 14:
        acc += 15
    if value == 15:
        acc += 16
    if value == 16:
        acc += 17
    if value == 17:
        acc += 18
    if value == 18:
        acc += 19
    if value == 19:
        acc += 20
    if value == 20:
        acc += 21
    if value == 21:
        acc += 22
    if value == 22:
        acc += 23
    if value == 23:
        acc += 24
    if value == 24:
        acc += 25
    if value == 25:
        acc += 26
    if value == 26:
        acc += 27
    if value == 27:
        acc += 28
    if value == 28:
        acc += 29
    if value == 29:
        acc += 30
    if value == 30:
        acc += 31
    if value == 31:
        acc += 32
    if value == 32:
        acc += 33
    if value == 33:
        acc += 34
    if value == 34:
        acc += 35
    if value == 35:
        acc += 36
    if value == 36:
        acc += 37
    if value == 37:
        acc += 38
    if value == 38:
        acc += 39
    if value == 39:
        acc += 40
    if value == 40:
        acc += 41
    if value == 41:
        acc += 42
    if value == 42:
        acc += 43
    if value == 43:
        acc += 44
    if value == 44:
        acc += 45
    if value == 45:
        acc += 46
    if value == 46:
        acc += 47
    if value == 47:
        acc += 48
    return acc

