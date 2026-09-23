# Live response — Velociraptor OFFLINE COLLECTOR ONLY

Velociraptor (Rapid7, AGPL-3.0 — wrap, do not vendor) is used here in **exactly one
mode**: the self-contained *offline collector*. You build a collector executable/
config, run it once on an authorized endpoint, and it writes a results archive
(zip). **No server. No agent. No client-server callback. No C2.**

> Hard boundary: this skill NEVER stands up a Velociraptor/GRR server, enrolls a
> client, or opens a network channel back to a console. If an investigation needs
> a fleet console, that is an owner-run platform decision outside this skill.

## Build the collector (analyst workstation, offline)

```
# Interactive builder → emits a standalone collector + embedded config:
velociraptor collector velociraptor.config.yaml            # GUI/wizard build
# or generate from an offline-collector spec you control:
velociraptor --config server.config.yaml collector_upload  # produces Collector_*.exe
```

The collector embeds the artifacts to run (e.g. `Windows.KapeFiles.Targets`,
`Generic.Client.Info`, `Windows.Sysinternals.Autoruns`) and where to write output
(local zip, or an owner-owned S3/GCS bucket by env-named creds — never inline keys).

## Run on the authorized endpoint (one shot)

```
Collector_velociraptor.exe            # writes Collection-<host>-<time>.zip locally
# Linux/macOS collector equivalents run the same single-shot way.
```

Then bring the zip **back to the workstation** and parse it offline:

```
python3 ../scripts/evidence_manifest.py Collection-*.zip --json > collection.hashes.json
# unpack read-only, then feed artifacts into the dissect / EZ Tools / EVTX lanes.
# You can also re-query VQL against a collection locally, no server:
velociraptor --config velociraptor.config.yaml artifacts collect \
  Windows.Search.FileFinder --args ... -o results.zip
```

## Notes / stop rules

- **Authorized endpoints only** — a named incident on an owned/authorized host.
- Prefer collector artifacts that **copy** volatile/target files; avoid modules that
  modify the endpoint.
- Hash the collection zip on arrival and treat its contents as evidence copies.
- For live *memory* capture, acquire the image with your approved acquisition tool,
  then analyze it in **`volatility-3`** — memory analysis is not in this skill.
