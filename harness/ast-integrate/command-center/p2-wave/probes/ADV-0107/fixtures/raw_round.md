# Round artifact ADV-0107-RAW

## Claims

[UNVERIFIED] C-U1: Latch leaks under load. tools/adv0107/latch.py:41 https://adv-0107.example.test/latch
confidence_band: almost-certain

[UNVERIFIED] C-U2: Timer drifts after midnight. tools/adv0107/timer.py:8
confidence_band: likely

[UNVERIFIED] C-U3: Queue drops the last item. tools/adv0107/queue.py:100 https://adv-0107.example.test/queue
confidence_band: remote

[UNVERIFIED] C-U4: Cache serves stale etags. tools/adv0107/cache.py:7 https://adv-0107.example.test/cache

## Vocabulary note

This section DISCUSSES the `UNVERIFIED` tag and the `almost-certain` band.
A document ABOUT tagging is not itself tagged. The file:line form `path.py:12`
is an example of the class, not an anchor. See also
https://example.invalid/style-guide as a mention-only URL.
