---
title: hitman-3-challenge-completion-re-zhmmod-sdk-quintuple-trouble
type: note
permalink: main/hitman-3-challenge-completion-re-zhmmod-sdk-quintuple-trouble
---



## 2026-06-27 — Tool BUILT + funnel→server link VERIFIED (session continuation)

**Mechanism independently verified (fresh-context IDA trace, confirmed by literal disasm operands):** an event posted to the funnel `sub_140CB0860((ZEventsManager*)0x1430EAEA0,&event)` DOES reach the outbound upload `sub_140D11710` (SaveAndSynchronizeEvents4). The funnel, serializer `sub_140CACA50`, and uploader `sub_140CADBB0` all share the one `ZOnlineEventManager` singleton **0x1430EAEA0**, joined by event index: funnel → index list +328 + event map +480; tick-drain `sub_140CAC570` → master list +352 → (`_DONTSEND`-filtered) → vectors +520/+400 → uploader +520→+544 → `values` arg of `sub_140D11710`.

**Decisive corrections this session (each prevents a crash or a cosmetic-only result):**
- **Inject at the FUNNEL `sub_140CB0860`, NOT `CallOriginal(OnEventSent)`.** `OnEventSent` (`sub_140B5E0E0`) is a downstream consumer callback — re-running it advances only the LOCAL SM = cosmetic. Use the OnEventSent detour for game-thread TIMING only.
- **Envelope is engine-added** (decompiled `sub_140CAD8B0`): funnel adds `Timestamp`; enqueue adds `UserId/SessionId/Origin="gameclient"/Id`(fresh GUID). Inject payload = **`{Name,ContractId,Value}` ONLY**.
- **Parser `sub_14151DCB0` 5th arg = refcounted `ZString*`, NOT char\*.** The global `0x141CEBF5C` is the raw `const char* MultiByteStr`; passing it → `_InterlockedIncrement(char*-12)` = heap corruption. Safe label = empty `ZString {len=0x80000000, char*}` (bit31 set ⇒ refcount/pool paths skipped). In ZHMModSDK a default-constructed `ZString` IS this (ZString.h:23-25). Arg map: RCX=result(16B), RDX=data, R8=len, R9=0, [rsp+0x20]=label.
- **SDK `Functions::ZJsonDeserializer_Deserialize` is MISBOUND** to the loadout parser `0x14094B810` (AOB-confirmed) → crash if used. Call `0x14151DCB0` directly by address.
- **Event-lifetime:** retain injected-event memory past the flush (CE: never free; mod: ring) — UAF-safe regardless of copy-vs-ref.
- **Flush trampoline entry** `sub_140CAC470` = `sub rsp,0A8h` (7 bytes `48 81 EC A8 00 00 00`); steal it, return to flush+7 (only RCX live).

**Two artifacts built (both adversarially reviewed + re-verified):**
- `scratchpad/force_challenge.lua` — CheatEngine injector, runnable LIVE via CE MCP (no build). Canonical codecave (cave in its OWN near-alloc — an early bug had it assembling OVER live game code → fixed). Gated: `FC.preflight()→install()→build_and_dump()→inject_one()→complete()`.
- `ZHMModSDK/Mods/ForceChallenge/` (.h/.cpp/CMakeLists/README) — permanent mod. Hooks OnEventSent for timing; funnel inject; Construct + Capture-replay modes; SRWLOCK-guarded cross-thread state (parser runs on game thread); refuses inject unless gate==2. Add `ForceChallenge` to root CMakeLists MODS list to build. NOT yet compiled/in-game tested.

**Honest caveats:** (a) reaching the upload ≠ server GRANT — IOI may not honor a client-asserted completion; observe the inbound echo (`sub_14091EF40`), never assume. (b) `_DONTSEND` field is filtered before upload — never include it. (c) Online gate `0x1430EA4B8`: drain runs at {2,40,43}, network send needs ==2; parked-at-40 ⇒ not actively syncing.

**Status:** completion of "Quintuple Trouble" deferred to a SUPERVISED online session (user's explicit choice; gate==2, watch the outbound fire + inbound echo live). Doc: `scratchpad/HITMAN-Quintuple-ForceComplete.md`. Relates to [[feedback_peer_review]] (review caught the codecave-over-live-code + threading-race crashes).