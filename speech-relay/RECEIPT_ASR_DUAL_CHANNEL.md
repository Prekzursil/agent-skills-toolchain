# ASR dual-channel receipt — 2026-09-19 07:53
## Offline channel (provider=local) — SUCCESS
- MCP server: ~/.agents/mcp-servers/video-agent-kit (local patched copy)
- Test: 40s Romanian speech (Dan Puric, Aiud 2026) -> speech_transcribe(provider=local)
- Result: 33s wall, 71 words, lang=ro, channel=local_whisper, word timestamps OK
- Quality: >= cloud channel ('casetofon' vs cloud 'tufona'); offline is unmetered
- Model: faster-whisper large-v3-turbo, CPU int8 (CUDA opt-in; lazy CUDA load hangs
  on Windows without cuDNN DLLs — measured)
- Root causes fixed (keep in any port):
  1) whisper in server thread hangs -> run in subprocess worker (local_asr_worker.py)
  2) import faster_whisper in server process risks DLL-loader deadlock (av double-load)
     -> subprocess probe only
  3) python grandchildren of the server blocked on inherited overlapped stdin handles
     (ZCode exec layer) -> ALWAYS stdin=DEVNULL for spawned children; ffprobe unaffected
- Artifacts: shorts-work/sample_local.json (offline), sample_relay.json (online via relay)
