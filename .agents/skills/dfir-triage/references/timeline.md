# Super-timeline — Plaso (`log2timeline` / `psort`)

Plaso (Apache-2.0 — wrap, do not vendor) builds one combined, time-ordered view
across many artifact types. Use it when the question is "what happened, in what
order?" rather than "what does this one artifact say?"

## Build → filter → export

```
# 1) Extract events from an image or a KAPE/dissect target into a .plaso store:
log2timeline.py --storage-file case01.plaso ./triage_copy/        # dir or E01/raw
log2timeline.py --status-view none --storage-file case01.plaso disk.e01

# 2) Inspect what was parsed:
pinfo.py case01.plaso

# 3) Export a filtered super-timeline (narrow the window — full ones are huge):
psort.py -o l2tcsv -w timeline.csv case01.plaso \
  "date > '2026-08-01 00:00:00' AND date < '2026-08-15 00:00:00'"

# JSON line output for downstream tooling / Timesketch import file:
psort.py -o json_line -w timeline.jsonl case01.plaso
```

Tips:
- Always bound the time window in `psort`; an unfiltered super-timeline is
  unreadable and slow.
- Use `--parsers` to scope `log2timeline` (e.g. `winevtx,mft,prefetch,webhist`)
  when you already know the lane.
- The Hayabusa/Chainsaw CSVs and dissect JSONL from the other lanes can be merged
  alongside the Plaso CSV in Timeline Explorer for a single pane.

## Notes / stop rules

- Timesketch is the usual Plaso front-end but it is a **server/daemon** — out of
  scope for this 0-daemon skill. Export the CSV/JSONL and analyze it flat, or hand
  the file to an owner-run Timesketch instance; do not stand one up here.
- Run against a **copy**; record the `.plaso` store hash in the manifest so the
  timeline is reproducible.
