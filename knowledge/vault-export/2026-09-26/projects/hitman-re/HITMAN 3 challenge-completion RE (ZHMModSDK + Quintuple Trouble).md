---
title: HITMAN 3 challenge-completion RE (ZHMModSDK + Quintuple Trouble)
type: note
permalink: main/projects/hitman-re/hitman-3-challenge-completion-re-zhmmod-sdk-quintuple-trouble
tags:
- hitman
- reverse-engineering
- zhmmodsdk
- frida
- ida
- challenges
---

# HITMAN 3 challenge-completion RE

**Goal:** clear the *bugged* "Quintuple Trouble" challenge (Hantu Port / "The Pen and The Sword" — achieve 5 multi-kills, unlocks Druzhina 34 ICA; new 2026 "Patient Zero Requiem" content, widely reported stuck at 1/5). Then generalize to a **force-complete-any-challenge** tool (incl. prerequisite ones like Discovery/Chameleon). User on RETAIL + OFFICIAL IOI servers (Azure 172.201.40.227:443). ZHMModSDK + DebugMod loaded; game pid 25724, base 0x140000000.

## Architecture (confirmed)
- Challenge logic is **client-side** (engine strings present: `ChallengeCompleted`, `ChallengeProgress`, `ChallengeProgress.count`, `ChallengeStates`, `ChallengesSaveData`, `ChallengeScoringEventReplicator`, `AchievementManager`). Event NAMES are not all literals — engine often uses hashes; IDA `find_regex` is BLIND until auto-analysis completes (even "Achievement" returned 0 mid-analysis) — use raw byte scan via py_eval instead.
- Challenge state = a **ZDynamicObject** keyed by `Completed` (bool), `State.CurrentState` (string; `"Success"` when done), `Progression`, `ChallengeId`, `Definition`, `Tags`, `GroupId`, `Repeatable`, `_SessionRewards`. Counter SM (Peacock fmt): `MultiKillTargets` event w/ `$Value.KillCount>1` → `$inc Count` → `Count==Goal(5)` → Success. Scope=session (resets on restart).

## Key RE facts (ZHMModSDK / IDA)
- `ZAchievementManagerSimple::OnEventSent` = **vtable[7]** @ RVA 0xb5e0e0 (abs 0x140b5e0e0). Vtable RVA 0x1e5ae88. Signature `void(this, uint32 eventIndex, const ZDynamicObject& event)`. **DEAD END for completion: this is the telemetry/event-send bus, NOT the challenge state-machine feed** — re-emitting `MultiKillTargets` here (even 5× distinct-Id) does NOT advance the counter.
- `ZDynamicObject_ToString` @ 0x14005ce60 (pattern in Functions.cpp). `ZJsonDeserializer_Deserialize` @ 0x94b810 — **real sig** `ZDynamicObject*(ZDynamicObject& result /*RCX*/, const ZString& json /*RDX*/, bool /*R8b*/)` (SDK header wrong: arg2 is ZString&, arg3 bool). ZDynamicObject = 16 bytes (ZObjectRef {STypeID* m_pTypeID; void* m_pData}). ZString = {u32 len (mask 0x3FFFFFFF, bit31=literal); char* at +8}.
- **Completion handler = `sub_14091EF40`**: refs state-lookup `sub_140956B10(progressionMgr=*(*ctx+448), &id)` + builds `ChallengeCompleted` event + sets `State.CurrentState="Success"` + `Completed` + grants `_SessionRewards`. THIS is the general lever. (Siblings refing ChallengeCompleted: `sub_140921270` (caller sub_14091D680), `sub_140B5F9A0`=vtable[8].)
- Progression state lookup `sub_140956B10(mgr, id)` → state obj; **count at +0x34 (+52)**. Set-progress `sub_140957600(dynobj, &key, &val)`. Save/sync path `sub_1409204A0` (walks `SwitchData.Data.Challenges`, reads count, writes `ChallengeProgress.count`).
- MultiKillTargets event shape (captured live): `{Timestamp,Name:"MultiKillTargets",ContractSessionId,ContractId,Value:{KillCount:2},UserId,SessionId,Origin:"gameclient",Id:<guid>}`.

## Status / next steps
- IDA 9.3 has HITMAN3.exe loaded (IDB at retail\HITMAN3.exe.i64), MCP at http://127.0.0.1:13337/mcp (stateless JSON-RPC; helper `scratchpad/ida.py`). **Auto-analysis NOT finished (~17min in)** → caller/xref of sub_14091EF40 incomplete. Need analysis done to nail its calling convention.
- Two impl paths once analysis done: (X) call `sub_14091EF40` at runtime (Frida) with the live Quintuple challenge → full correct completion+reward+persist; (Y) directly set live challenge-state ZDynamicObject `Completed=true`/`CurrentState="Success"`+count via the progression mgr, then save/sync (may not grant unlock without the reward path).
- Tooling: Frida 17 (frida-mcp ephemeral; resident hook needs python driver — scratchpad/driver.py+hook*.js). CheatEngine MCP attached pid 25724 (a value-scan timed out — bound scans to low heap 0x6xxxxxx, NOT all writable/GBs). Live achMgr instance found earlier at 0x06BE0510 (vtable 0x141e5ae88) — but per-session; re-find by scanning writable mem for vtable ptr 0x141e5ae88.

Relates to [[reference_frida_hotpath_interceptor_crash]].


## 2026-06-27 deep-RE session — corrections + new findings

**Challenge confirmed:** "Quintuple Trouble" (game spells *Quintuple*) — Hantu Port / "The Pen and the Sword", **Sniper Assassin**. "Achieve 5 multi-kills (incl. piercing) in one playthrough." Reward = **Druzhina 34 ICA**. It is the 14th/last Assassination challenge. User is **ONLINE (Lvl 1725)** → the unlock is **server-granted**, so a real completion *event must reach the server* (a cosmetic memory poke is insufficient — this is why the user's "make sure unlock hits all" matters).

**CORRECTION — count offset:** authoritative count = `*((int*)stateObj + 52)` = **`*(stateObj + 0xD0)`**, where `stateObj = sub_140956B10(progMgr, idZString*)` returns `node+0x30`. The earlier "+0x34/+52" note was a misread of `*((_DWORD*)result + 52)` (that's +52 **dwords** = +0xD0, NOT +0x34 bytes). Verified in `sub_1409204A0` decompile.

**Progress field:** key string **`"ChallengeProgress.count"`** (nested `"ChallengeProgress"→"count"`); value stored as a **double-typed dynamic value** `{typeptr=0x14230F998 ; dataptr → double}`.

**Manager layout:** `challengeMgr` (persistent/profile) = static **`unk_1430E7480`**; `progMgr = *(0x1430E7640) = 0x1430E7558` but its tree (`progMgr+0x18`) is **EMPTY / self-referential** → the LIVE mission challenges live in a **SESSION manager whose address was not yet found** (key open problem). `sub_1409204A0(challengeMgr)` = the sync: iterates `"SwitchData.Data.Challenges"`, reads each `ChallengeProgress.count`, looks up persistent state via `sub_140956B10`, writes diffs. Caller = `sub_14095A6E0` (calls it on `&unk_1430E7480`).

**Key negative results (don't re-walk):**
- `sub_140956B10` (state-lookup) does **NOT** fire during normal play (kills, opening the Challenges menu) — only on a **sync** (save / specific events). **Saving is unavailable in Sniper Assassin** → can't trigger a sync that way.
- `sub_140965A80` (CompletionCount, key `_SysVars.Repeatable.CompletionCount`) is for **repeatable kill-counter** challenges (blow past 5) — NOT Quintuple's multikill progress.
- `sub_140A2A350` (UI counter builder: `counterString`/`percent`/`isActive`) is downstream display only; capturing its source struct was flaky.
- **OnEventSent vtable[7] @0x140b5e0e0 = TELEMETRY ONLY** (re-emit does not feed the SM). `vtable[8] sub_140B5F9A0` = event-APPLY = candidate real SM input.
- CE Lua `nextScan` via `evaluate_lua` does **not** filter (use `firstScan`+address-intersection or the dedicated CE MCP scan tools).
- Static value-scan for the live count is hopeless: 173k bare `double 3.0`; even typed (`0x14230F998` + value 3.0) = 200+ candidates. Cannot isolate without a value **transition**, and the user refuses further multikills.
- Challenge **name is not in memory as text** (ASCII & wide = 0 hits) → stored as a localization hash; cannot anchor by name.

**Completion machinery:** notifier `sub_140986730(obj, key)` walks a listener list, `_stricmp` on field name, virtual-calls matching listeners (this is how a count change drives SM re-eval/completion). Completion handler `sub_14091EF40` builds the `"ChallengeCompleted"` event (`@0x141e1d8e0`), handles `"_SessionRewards"`, sets `State.CurrentState="Success"/"Completed"`.

**Constraint shift (user, 2026-06-27):** user will NOT interact further (no multikills/saves). Demands an **unattended, no-crash, server-granting, GENERAL** force-complete-any-challenge solution + docs.

**Action:** launched ultracode Workflow `wf_51204329-f75` (research: Peacock UUID + server-grant mechanism + ZHMModSDK challenge API + trainers; RE: find session manager + completion/report path + real SM event input + ZAchievementManagerSimple; synth + adversarial verify). Plan: execute validated method on live game, verify Druzhina 34 unlock, document. **Most promising clean path = use ZHMModSDK's own ZAchievementManagerSimple API (user already builds against it) rather than raw memory pokes.**


## 2026-06-27 round-1+2 workflow — VERIFIED CORRECTIONS (supersede earlier same-day notes)

- **CORRECTION — OnEventSent is NOT telemetry-only.** Earlier this day I noted "OnEventSent vtable[7] @0x140b5e0e0 = telemetry only, re-emit doesn't feed the SM." That is WRONG. Per ZHMModSDK ground truth: `ZAchievementManagerSimple_OnEventSent(th, uint32_t eventIndex, const ZDynamicObject& event)` is the achievement/challenge **event INTAKE** — the SDK's `AdvancedRating` mod detours it to read the live gameplay event stream. The earlier "re-emit did nothing" was almost certainly a **malformed event** (round-1 confirmed the builders were misidentified). Correct injection = build a *valid* ZDynamicObject event + call the **original** OnEventSent **on the game thread**.
- **Server model (decisive):** the official IOI server **re-derives** challenge completion from the uploaded gameplay event stream (`SaveAndSynchronizeEvents4` = `sub_140D11710`), not from a client flag ⇒ memory poke = cosmetic/reverts; must inject genuine qualifying events that reach the outbound sync.
- **Exact challenge def (Peacock `contractdata/SNIPER/_SALTY_CHALLENGES.json`):** Id `66fe5dfa-2014-4f5d-9bb9-460078ed893d`; SM `Start --MultiKillTargets[$gt Value.KillCount 1]--> Check`; `Check`: `$inc Count`, `Success` when `Count==Goal(5)`; `Scope:"session"`; `Rewards.MasteryXP:0`; `Drops:["FIREARMS_SNIPER_DRUZHINA_34_ICA"]`. **Only challenge on contract `00e57709-…` listening for MultiKillTargets** (no collateral); plain `$inc` (not `$pushunique`). At 3/5 ⇒ 2 more events.
- **Why the persistent tree is empty:** challenge is `Scope:"session"` — live Count lives in the session SM (+656 listener structure on `0x1430E7480`), NOT the persistent progMgr tree (+448). **Do NOT read the count via `sub_140956B10` — it is find-or-INSERT and will pollute/corrupt the persistent profile tree.** Use a non-mutating session read.
- **Correct event-build primitives (SDK):** `ZDynamicObject::Object()` + `.Set(key,val)` (Include/Glacier/ZObject.h), or JSON deser `0x14094B810`; assert result type-id == `0x1445B3DC0`. Round-1's `sub_14005CAB0`/`sub_1400AA510` were misidentified (copy/assign-op + raw-cstring) → crash.
- **Round-1 synthesized plan FAILED all 4 adversarial reviews** (crash via malformed event; save-corruption via find-or-insert oracle; server-grant + `_SessionRewards` commit-timing unproven; collateral [later disproven]). Caught before any live action. **Round-2 `wf_2aa9e2bc-ba6` (task wcnk7m1fv)** fixes them, SDK-grounded, and gates "done" on observed proof (outbound POST carries the event + inbound server ChallengeCompleted), with a SAFE one-event test first.
- **Robust general tool = a ZHMModSDK mod** (`C:\Users\Prekzursil\source\repos\ZHMModSDK`): game-thread-safe (no race), correct SDK primitives, hook `ZAchievementManagerSimple_OnEventSent` → `CallOriginal(th, eventIndex, builtEvent)` N times, Drops-keyed guard, parameterized by the challenge's event Name + Value condition. Model on `Mods/AdvancedRating`.


## 2026-06-27 round-2 outcome — VERIFIED procedure + the real BLOCKER (online gate)

**Round-2 (`wf_2aa9e2bc-ba6`) caught two more bugs; both fixed; rest IDB-verified:**
- **Another misID:** `0x14094B810` is the **loadout parser** (calls real parser then rewrites to a loadout struct + stomps globals); the SDK's `ZJsonDeserializer_Deserialize` AOB binds there too → using it crashes. **Real generic JSON→ZDynamicObject parser = `sub_14151DCB0`** (RCX=result16B, RDX=char*, R8=len, R9=bool0, [rsp+0x20]=ZString* label). Assert result type-id == `0x1445B3DC0` (the engine's own dict check in `sub_14005BC90`).
- **Inject point = the gameplay funnel `sub_140CB0860(ZEventsManager* 0x1430EAEA0, &event)`** (reaches BOTH the challenge SM fan-out AND the outbound sync). NOT OnEventSent (that's the read-only oracle: `0x140B5E0E0`, event in R8). Marshal onto the **game thread** via a one-shot trampoline on per-frame flush `sub_140CAC470` — and **preserve RCX/volatiles** around the funnel call (round-2 crash: cave clobbered RCX = the flush `this` → crash); rebuild a fresh event for the 2nd inject.
- **Verification (mandatory, gate "done" on observed proof):** outbound watcher on `sub_140D11710` (values=RDX); inbound grant watcher on `sub_14091EF40` (RDX) — it does the `+448` profile write per inbound entry, so a server echo for `66fe5dfa` appears even at 3→4 → use it as a PRE-irreversible acceptance gate (abort before the 5th event if no echo). Never use find-or-insert `sub_140956B10` as a count oracle.

**THE BLOCKER (why completion is deferred):** `SaveAndSynchronizeEvents4` (`sub_140D11710`) only forwards challenge events to IOI's server when **`dword_1430EA4B8 == 2`** (verified in decompile: `==2` branch calls the network service vtable `qword_143BA8E78`+16; else = no server send). **Live value is stably 40** (game parked/idle/backgrounded ~75 min while user away). So injecting now = local-only **cosmetic 5/5, NO server grant** — which the user explicitly forbade. **Cannot satisfy unattended** (needs the game in active online play). Do NOT force-write the gate to 2 (sync would hit a dead connection → error/crash). **Resume when the game is in active online play (gate==2):** run the verified procedure (≈30s) supervised, watching the inbound echo. General tool = the corrected ZHMModSDK mod (game-thread-native, `ZDynamicObject::Object()/.Set()`, CallOriginal on `ZAchievementManagerSimple_OnEventSent`, Drops-keyed). Account-flag risk LOW (researched: no bans, at most leaderboard shadow-ban). Full procedure: `scratchpad/HITMAN-Quintuple-ForceComplete.md`; round-2 output `tasks/wcnk7m1fv.output`.
