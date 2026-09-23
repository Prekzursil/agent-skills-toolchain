# Artifact parsing — dissect (one pip) + EZ Tools / KAPE

Turn raw forensic artifacts (disk images, KAPE targets, individual registry/
browser/filesystem artifacts) into structured records. All read-only against a
copy.

## dissect (Fox-IT, AGPL-3.0 — wrap, do not vendor; one pip covers most artifacts)

`dissect` mounts and parses images and loose artifacts across Windows/Linux/macOS
with one install. Prefer it as the default parser — it replaces a drawer of
single-purpose tools.

```
pip install dissect            # or: pipx install dissect

# Inventory what an image/target exposes:
target-info  disk.e01
target-query -f amcache,shimcache,runkeys,scheduled_tasks disk.e01

# Common triage functions (each streams records; add -j for JSON lines):
target-query -f mft            disk.e01 -j > mft.jsonl
target-query -f evtx           disk.e01 -j > evtx.jsonl
target-query -f browser.history disk.e01 -j > web.jsonl
target-query -f services,runkeys,scheduled_tasks disk.e01 -j > persistence.jsonl

# Interactive shell over the image (read-only):
target-shell disk.e01
```

dissect reads E01/VMDK/VHDX/raw directly, so you rarely need to pre-mount. Its
record stream also feeds the Plaso/timeline lane.

## Eric Zimmerman (EZ) Tools + KAPE (Windows; free, closed-source — wrap, do not vendor)

The reference Windows artifact parsers. KAPE collects targets and runs modules;
the EZ Tools parse individual artifacts to CSV for Timeline Explorer.

```
# KAPE: collect a triage target set to an output dir (offline, from a copy/mount):
kape.exe --tsource E: --target KapeTriage --tdest .\out\triage --vhdx case01

# KAPE: run parsing modules over collected artifacts:
kape.exe --msource .\out\triage --mdest .\out\parsed --module !EZParser

# EZ Tools directly:
MFTECmd.exe   -f "$MFT" --csv .\out            # $MFT / $J / $Boot / $SDS
RECmd.exe     --bn BatchExamples\Kroll.reb -d .\reg --csv .\out   # registry
PECmd.exe     -d C:\Windows\Prefetch --csv .\out                  # prefetch
LECmd.exe -d .\lnk --csv .\out ; JLECmd.exe -d .\jump --csv .\out # LNK / jump lists
AmcacheParser.exe -f Amcache.hve --csv .\out ; SBECmd.exe -d .\reg --csv .\out
```

Everything lands as CSV → open in Timeline Explorer or merge into the Plaso lane.

## Notes / stop rules

- Parse a **copy**; keep the original write-blocked. Re-hash outputs into the manifest.
- KAPE `--tsource`/`--msource` should point at mounted-read-only or copied evidence.
- Executables/DLLs found in Amcache/prefetch/services are **leads, not verdicts** —
  hash them and hand to `capa-triage` before concluding.
