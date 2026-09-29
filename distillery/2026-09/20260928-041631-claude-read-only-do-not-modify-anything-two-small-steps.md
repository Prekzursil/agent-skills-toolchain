# Read-only. Do not modify anything. Two small steps: 1) grep -rn "0.727" across ALL files in out/ (every extension, inclu

- runtime: claude
- session date: 2026-09-22 19:59
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\D--Research-tools-rvc-realtime-voice-changer\405fd524-84e0-42f1-a3d6-fd549691a002.jsonl`
- distilled: 2026-09-28T04:16:31
- backend: claude

## create_summary

**Purpose:** Distills a 2026-09-22 session in `rvc-realtime-voice-changer` (Trump voice-clone project) built around a queued read-only grep task verifying similarity scores in experiment outputs.

**Key points**

1. Queued read-only task: grep "0.727" across all files in out/ plus scripts/, print matches verbatim, cap 20.
2. Second grep: "0.72" in out/*.log only; print NO-MATCH or NO-MATCH-LOG sentinels if empty.
3. Task enqueued then dequeued same second; session cwd D:\Research\tools\rvc-realtime-voice-changer, branch main.
4. Project context: Trump voice cloning across RVC, XTTS v2, and ElevenLabs IVC/PVC pipelines.
5. XTTS v2 similarity gate crossed: best 0.756 ("b10+2") against ≥0.70 gate; artifacts in out/.
6. ElevenLabs v4 classifier-blocked mid-run; v2 restored (voice_id Y5irDJyb8lW5NwV7NFjE, "SOTU 2026").
7. Training manifest: trump_wef2018, 20 clips (10 train/10 test), 10s @16kHz, pitch ~395–535 Hz.
8. Prior extraction session failed entirely: no Read/Bash tools, cursor-bridge wedged, biomni 429, agent-mail down.
9. out/pvc_edit_page.txt later became readable: revealed 1.1 GB corpus (SOTU 2018–2026 parts, WEF, D-Day).
10. GRILL decision queue: G-3 owner ABX judge pending; execution order G-11→G-13→G-9→G-7→G-10→G-12→G-8.

**Takeaways**

1. The 0.727/0.72 greps likely trace the 0.756 XTTS similarity score lineage in logs and scripts.
2. Provider classifier blocks (ElevenLabs v3/v4) recur; v2 is the stable fallback lane.
3. Tool-less sessions repeatedly fail file extraction; interactive Read+shell sessions are the reliable unblock.
4. Queued work goes stale — a later session declined a truncated tests_wave.py append chunk from the same date.
5. Project is blocked on owner ABX judgment and CPML non-commercial scope approval, not engineering capacity.

## extract_wisdom

## Digest — voice-clone sessions (2026-09-20/22, `D:\Research\tools\rvc-realtime-voice-changer`)

### Decisions and rationale
1. Restored ElevenLabs voice v2 ("SOTU 2026 (IVC v2)", voice_id `Y5irDJyb8lW5NwV7NFjE`) after v4 was classifier-blocked mid-run — keep the working lane, don't retry the blocked one.
2. XTTS v2 similarity gate crossed (best 0.756 "b10+2" vs gate ≥0.70); next = Reframe integration, still gated on owner ABX + CPML non-commercial green-light.
3. Grill queue (`GRILL-voice-clone_2026-09-21.md`): exec order G-11→G-13→G-9→G-7→G-10→G-12→G-8; v3 rebuild register-stratified at f0 140–190 Hz; 4-part gate (embed + f0-register + centroid + owner ABX); 6-window frozen probe set incl. part19-low.
4. Declined stale queued append chunks 2/3 & 3/3 to `backend/submissions/tests_wave.py`: payloads truncated mid-line, no END-CHUNK marker, "file ends at line 602" precondition false — appending would shadow-duplicate existing test classes. Rule: never append a truncated payload; verify preconditions against current file.

### Surprising findings
5. Manifest clips show pitch_mean ~395–535 Hz — 2–3× the 140–190 Hz target register; part19 f0 99.9 Hz vs 150–175 elsewhere (unverified outlier, loop F3).
6. A 1.1 GB Trump corpus exists: SOTU 2026 parts 01–25 (~29:59 each), SOTU 2018/2019, WEF 2018, D-Day 75th, Miami 2019.

### Mistakes and fixes
7. Six-target extraction failed (no native Read/Bash): cursor-bridge wedged (2×120s timeouts), biomni 429 code-1302, WebFetch http/https-only, Playwright blocks `file:`. Fix: re-run in a session with native Read + shell; one target (`out/pvc_edit_page.txt`) later unblocked.
8. Aviary v0.37.0 RECORD check returned empty twice: escaped `$d` broke the loop AND wrong dist-info glob (`fhaviary-0.37.0.dist-info`, not `aviary-*`); re-run closed both (31 files, 0 missing).

### Dependencies/tools
9. XTTS v2, ElevenLabs IVC v2/v3/v4, Reframe, biomni (WSL2, glm-5.3), cursor-bridge, `.remember/` memory, grep-task queued for "0.727"/"0.72" (open).
