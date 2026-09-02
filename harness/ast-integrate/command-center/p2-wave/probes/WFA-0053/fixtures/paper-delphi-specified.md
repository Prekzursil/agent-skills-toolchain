# Delphi panel protocol (local corpus fixture; not a copyrighted reprint)

A panel of 12 experts issues independent numeric estimates.

Turn structure is iterative anonymous rounds: each expert sees only the previous-round median and IQR, never other names, then revises.

The stopping rule is: stop when the interquartile range IQR is below 0.5, or after 4 rounds, whichever comes first.

Scoring is the median of the final round compared to ground-truth, reported as absolute error.
