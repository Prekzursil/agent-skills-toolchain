# Post-mortem: the nightly pipeline that ate our receipts

The nightly pipeline looked impeccable on paper: fetch the receipts, then validate each one against the schema, then emit the summary index. In practice it was a disaster. Fetching meant re-downloading gigabytes; validating used a stale schema snapshot; and the emitted index silently overwrote the previous day's. Do not adopt this pipeline. Its every step is an anti-pattern worth naming so the next reader avoids it.
