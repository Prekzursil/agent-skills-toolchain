# EVTX / Sigma sweep — Chainsaw + Hayabusa

Two fast, file-mode Windows event-log hunters. Both read `.evtx` off a copy and
apply Sigma rules; neither installs a service or touches the source host. Use them
first on any Windows event-log evidence, then pivot to timeline/artifact lanes.

## Chainsaw (WithSecure Labs, GPL-3.0 — wrap, do not vendor)

Fast triage + Sigma detection + keyword/regex hunting over EVTX.

```
# Sigma detections over an EVTX directory, CSV out (mapping ships in the release):
chainsaw hunt ./evtx_copy/ -s ./sigma/ --mapping ./mappings/sigma-event-logs-all.yml --csv -o ./out/

# Quick built-in ruleset + JSON for tooling:
chainsaw hunt ./evtx_copy/ -r ./rules/ --json > chainsaw.json

# Dump/search a single log for an indicator:
chainsaw search -t 'Event.System.EventID: =4624' ./Security.evtx
```

High-signal first passes: logons (4624/4625/4648), service installs (7045),
Scheduled Tasks (4698), PowerShell (4104), WMI, and RDP. Chainsaw's shimcache/
srum/timeline sub-passes are triage-grade — confirm hits in the dedicated lanes.

## Hayabusa (Yamato Security, GPL-3.0 — wrap, do not vendor)

Sigma-based EVTX to a single timeline with a built-in, versioned rule set and a
severity summary. Great for "give me one ranked timeline of this box."

```
# Update the bundled rules (offline-cacheable), then build a CSV timeline:
hayabusa update-rules
hayabusa csv-timeline -d ./evtx_copy/ -o hayabusa_timeline.csv

# Terminal summary of detections by level:
hayabusa csv-timeline -d ./evtx_copy/ -o out.csv -p verbose
```

`csv-timeline` output drops straight into Timeline Explorer / the Plaso lane.

## Notes / stop rules

- Work on a **copy** of the logs; never let a tool rewrite the source EVTX.
- Sigma coverage is a floor, not proof — an empty result is "no rule matched,"
  not "nothing happened." Confirm with artifact + timeline lanes.
- Authoring/tuning Sigma rules is the **`detection-as-code`** skill's job; this lane
  only *runs* rules to triage evidence.
- Record the rule-set version/commit alongside the output so a hit is reproducible.
