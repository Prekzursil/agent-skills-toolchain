# Digest of ADV-0107-RAW

[UNVERIFIED] C-U1: Latch leaks under load. tools/adv0107/latch.py:41
confidence_band: almost-certain

[UNVERIFIED] C-U2: Timer drifts after midnight.
confidence_band: likely

C-U3: Queue drops the last item; this has not been independently verified.
See tools/adv0107/queue.py line 100.
