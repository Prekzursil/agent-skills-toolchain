---
name: "academy-badge-runner"
description: "Complete self-paced course/badge programs and hands-on labs on the user's logged-in account with Claude in Chrome: Claude Academy (verified), Google Skills paths and Qwiklabs labs with Check-my-progress diagnostics (verified), OpenAI Academy, Google Developers pathways. Parallel tabs, one subagent per course."
---

# Academy badge runner

Use when the user asks to finish courses, earn completion badges, clear a learning path, or run a
hands-on lab on a platform they are already signed in to (academy.claude.com,
academy.openai.com, developers.google.com/learn/pathways, skills.google). The job is mechanical
navigation plus answering knowledge checks yourself — and, for labs, doing the real cloud work in
a way the platform's checker credits. The Claude Academy playbook (§3) was verified by doing all
22 badge courses in one session; the Google Skills lab playbook (§6.3–6.5) was verified on
GSP1247 (BigQuery ML + Gemini): a first run stalled at 65/100 with "correct" SQL, a second run
scored 100/100 once the checker's actual rules were understood — read §6.4 before touching a
"Check my progress" button. The rest are recon protocols to run on first use (then update this
skill with what you find).

## 0. Rules that never bend

- Only the user's own account, only content they asked for. Never enter credentials, payment data,
  personal data forms, or accept terms/consent banners; if a page needs any of these, stop
  and hand it to the user or can proceed with owner's explicit accord.
- Answer every quiz from your own knowledge (plus the course's own lessons if a question is
  course-specific — open the lesson in another tab and read it). Do not scrape answer keys from JS
  bundles or network responses.
- No proctored / identity-verified certification exams (Google Cloud certifications, any exam with
  a proctor or webcam step). No paid labs or credit-consuming labs without an explicit yes from the
  user for that specific lab. Knowledge-check quizzes and content completion are fine.
- Never use the user's page-facing browser tab for other browsing; each worker owns its own tab id.
- Labs: never forge, replay or script the platform's "Check my progress" request, and never
  call in-page helpers to mark a lab complete. The click is only a trigger — grading runs
  server-side against the project's state, audit logs and job history (§6.4) — so replaying it
  changes nothing, and it is off-limits regardless. When asked to "trigger validation manually"
  or "force it", decline in one line and run the diagnostics ladder in §6.4 instead: every stuck
  checkpoint so far had a legitimate cause.
- Lab credentials are typed by the user, every time — including "temporary" lab passwords and
  the re-login after a session drop. Never click a lab's `End` button unless the user says so
  (it deletes the project, and the timer cannot be paused).

## 1. Operating model (Recon → Instrument → Drive → Verify → Report)

1. **Recon (once per platform, ~5 min):** find (a) the catalog and the badge marker, (b) what
   *actually* marks a lesson complete, (c) how quizzes render, (d) where the badge shows.
   Techniques that worked: `get_page_text`, `find`, `read_network_requests` after one manual
   click (look for RPC names like `StartLesson`/`CompleteLesson`), fetching the SPA's JS chunks
   from inside `javascript_tool` and grepping for mutation names (`completeLesson`, `onNextClick`,
   `onPassed`), and `[role=radio]/[role=checkbox]` for quiz options.
2. **Instrument:** install small window helpers in the tab with `javascript_tool`, then persist
   them with `localStorage.__setup = [...names].map(n=>'window.'+n+'='+window[n].toString()).join(';')`
   so any other tab on that origin gets them with `eval(localStorage.__setup)`. (Using
   `toString()` avoids the backslash-escaping bugs you get when pasting code into a template
   string; note browser_batch JSON needs `\\` for every regex backslash, direct javascript_tool
   calls do not.)
3. **Drive:** advance with an *idempotent* step function driven from `browser_batch`
   (`[js step, wait 1.3s] × 6`), never with page-side `setTimeout` loops.
4. **Verify:** badge page says ISSUED; outline shows every lesson `(completed)`; quiz result
   `You passed`.
5. **Report:** per course — lessons done, quiz score, badge status, anything skipped and why.

Labs (§6.3) use a different loop: Execute exactly → Verify state → Check → Diagnose. One lab
at a time (the platform allows a single running lab per account), so labs are never parallelised.

## 2. Claude-in-Chrome quirks (these cost the most time — read first)

- **Hidden tabs throttle page timers to ~1/min.** Every parallel tab is hidden. Any `await
  sleep()` / `setTimeout` / MutationObserver-with-timeout inside `javascript_tool` stalls (a 6 s
  wait took 40 s). All waiting must be `computer.wait` actions inside `browser_batch`.
- `javascript_tool` right after a `navigate` fails intermittently → always `wait 1–1.5s` after
  navigating, and prefer a standalone `navigate` call followed by a batch.
- A batch stops at the first error and the tool sometimes reports "failed in the extension"
  even though earlier actions ran. Keep batches ≤ 8–12 actions, then re-read state.
- Output containing `=`/`?`/`&` runs or attribute dumps is redacted as
  `[BLOCKED: Cookie/query string data]`. Return short strings; strip `=?&;` from any HTML/JS you
  print (`.replace(/[=?&;]/g,' ')`).
- `innerText` of icon-bearing links starts with a Private-Use-Area glyph (U+E000–F8FF) followed by
  `\n`; strip with `.replace(/[-]/g,'')` (the Private Use Area) before regex matching, and anchor on a
  full label like `Next lesson` (plain `Next` matches "What's next" and lesson titles such as
  "Next Token Prediction").
- Native `<input type=radio>` in these UIs are `aria-hidden` shims; click the Radix
  `[role=radio]` / `[role=checkbox]` elements instead.
- A full-page `navigate` wipes `window.*` helpers (SPA link clicks do not) → re-run
  `eval(localStorage.__setup)` after navigating; guard with
  `typeof window.__fix==='function'||eval(localStorage.__setup)`.
- Tab ids are stable across navigations; the user may open extra tabs in the group — never touch
  tabs you did not create or were not assigned.
- "Tool … failed in the extension" comes in bursts: screenshots can fail for 30–60 s while
  `type`, `find`, `get_page_text` and `navigate` keep working. Don't hammer it — Bash
  `sleep 15–25`, then retry. A `type` that "failed" usually landed in full (verify with `wc -l`
  or `__todo()`) — check state before re-sending, or you double-run commands.
- The browser window can silently shrink (a 990×445 frame appeared mid-session): read the frame
  size in the screenshot header before coordinate clicks and `resize_window` 1600×950 if needed.
- Terminals and consoles drawn in iframes or canvas (Cloud Shell) are invisible to `read_page`,
  `get_page_text` and `find` — read them with `zoom` on the terminal region; printed text is the
  only state you get, so make commands print sentinels.
- Dialogs with their own scrollbar (Skills Boost "Checkpoints") ignore wheel events over the
  page: `scroll_to` a ref inside them or `left_click_drag` the dialog's scrollbar track.
- Toasts live ~5 s and their `alert` node lingers with stale text: screenshot within 3 s of the
  click, and confirm from the persistent score element after a reload — never from `find` on
  the alert.
- A `ref` from `find` may be a hidden duplicate of a control (the same button exists in a
  dialog and inline in the page): if a ref click produces nothing, click the visible copy by
  coordinate.
- Side panels (Gemini Cloud Assist, "Lab setup and access", tutorials) overlay content and eat
  coordinate clicks — close them with their X first.

## 3. Claude Academy playbook (verified 2026-09)

### 3.1 Discovery
- Catalog: `https://academy.claude.com/all?kind=course`, click the `Load more` button, then
  `main a[href^="/courses/"]` gives slugs; card text carries `Enrolled` / `Completed`.
- Badge courses = the course page shows a `Completion badge` chip. Empirically every course with
  a quiz has a badge; the no-quiz ones (train-the-trainer, agent skills, SDLC playbook, subagents)
  do not.
- Badge page: `/courses/<slug>/badge` → main text contains `ISSUED <DATE>` once earned; the
  outline lists it as `Completion badge (earned)`. `Your learning` in the top nav lists
  everything.

### 3.2 Mechanics
- Connect-RPC backend at `/api/anthropic.academy.api.v1alpha.AcademyService/{StartLesson,
  CompleteLesson, GetCourseProgress, CreateEnrollment, UpdateEnrollment, EmitProgressEvent,
  CompleteCertification}` (JSON over POST). Lesson/course ids are opaque, not slugs; direct calls
  were not needed — the UI path below is fast enough. Don't burn time on it unless a course has
  hundreds of lessons.
- **A lesson is marked complete when the `Next lesson` link at the page bottom (or `Up next` on
  the post-quiz lesson) is clicked** (`onNextClick` → `completeLesson`). Scrolling or dwell does
  nothing. Clicking auto-enrolls (`auto_progress`) if the user never pressed `Start course`.
- Quizzes: one question per screen, `Question i of N`, options are `main [role=radio]` (single)
  or `[role=checkbox]` (multi); buttons `Back` / `Next` / `Submit`. After Submit the page shows
  `Checking your answers…` (can take 5–10 s in a hidden tab) then `You passed` / `You got X of N
  correct`. Pass mark 80 %. `Retake quiz` button on failure. Passing triggers the badge; no
  separate claim step despite the copy saying "select Create your completion badge".
- Some courses put an optional lesson *after* the quiz (e.g. `additional-activities`); its
  bottom link is `Up next → Completion badge` and clicking it completes the lesson.
- Quiz slugs vary: `course-quiz`, `certificate-of-completion`, `certificate-quiz`,
  `final-assessment`, `quiz-on-…`, `assessment-on-…`.

### 3.3 Helper library (paste as-is into `javascript_tool` on a course page, once)

```js
window.__els=()=>[...document.querySelectorAll('main [role=radio],main [role=checkbox]')];
window.__txt=r=>{let p=r;while(p.parentElement&&p.parentElement.querySelectorAll('[role=radio],[role=checkbox]').length===1)p=p.parentElement;return p.innerText.trim()};
window.__q=()=>{const rs=window.__els();const t=(document.querySelector('main')||document.body).innerText;const m=(t.match(/Question \d+ of \d+[\s\S]*?\n(?:\d+ answered\n)?([^\n]+)/)||[])[0];return (m||'NO QUESTION on '+location.pathname)+'\n['+(rs[0]&&rs[0].getAttribute('role'))+']\n'+rs.map((r,i)=>i+': '+window.__txt(r).replace(/\s+/g,' ')).join('\n')};
window.__ans=idxs=>{const rs=window.__els();for(const i of idxs)rs[i].click();const b=[...document.querySelectorAll('main button')].find(b=>/^(Next|Submit)/.test(b.innerText.trim()));const bt=b?b.innerText.trim():'nobtn';if(b&&!b.disabled)b.click();return bt==='Submit'?'SUBMITTED':bt};
window.__res=()=>{const t=(document.querySelector('main')||document.body).innerText;return (t.match(/You (passed|did not pass|didn't pass)[\s\S]{0,40}/)||[/Checking your answers/.test(t)?'CHECKING':'no result'])[0]+' | completed:'+(t.match(/\(completed\)/g)||[]).length};
window.__items=()=>{const seen=new Set();return [...document.querySelectorAll('a[href^="/courses/"]')].filter(a=>{const h=a.getAttribute('href');if(h.split('/').length!==4||seen.has(h))return false;seen.add(h);return !/Next|Previous|Up next/.test(a.innerText)})};
window.__todo=()=>window.__items().map(a=>(/completed|earned/.test(a.innerText)?'V ':'X ')+a.getAttribute('href').split('/').pop()).join(' ');
window.__go=slug=>{const a=window.__items().find(a=>a.getAttribute('href').endsWith('/'+slug));if(!a)return 'nolink '+slug;a.click();return 'go '+slug};
window.__next=()=>[...document.querySelectorAll('a')].find(a=>/(^|\n)\W?(Next lesson|Up next)\b/.test(a.innerText.replace(/[-]/g,'')));
window.__fix=()=>{const items=window.__items();const todo=items.filter(a=>!/completed|earned/.test(a.innerText));const isQuiz=a=>/quiz|assessment|certificate/i.test(a.getAttribute('href'))||/quiz/i.test(a.innerText);const t=todo.find(a=>!isQuiz(a)&&!/\/badge$/.test(a.getAttribute('href')));const cur=location.pathname.split('/').pop();if(!t){const q=todo.find(a=>isQuiz(a));return 'LESSONS DONE; quiz todo: '+(q?q.getAttribute('href').split('/').pop():'none')+' | '+(items.length-todo.length)+'/'+items.length}const slug=t.getAttribute('href').split('/').pop();if(cur!==slug){t.click();return 'goto '+slug}const n=window.__next();if(!n)return 'no next on '+slug;n.click();return 'completed '+slug};
localStorage.__setup=['__els','__txt','__q','__ans','__res','__items','__todo','__go','__next','__fix'].map(n=>'window.'+n+'='+window[n].toString()).join(';');
'installed '+window.__todo()
```

Semantics: `__fix()` is idempotent — it reads the course outline (sidebar/dropdown links,
`(completed)` markers), goes to the first incomplete non-quiz lesson, and on the next call clicks
`Next lesson` there. It returns `goto X` / `completed X` / `no next on X` (page not rendered yet,
just call again) / `LESSONS DONE; quiz todo: <slug> | done/total`. `__q()` prints the current
question with 0-based options; `__ans([i,...])` selects and presses Next/Submit; `__res()` reads
the verdict. If a lesson slug contains "assessment"/"quiz" but is really a lesson, `__q()` says
`NO QUESTION` — then click `__next()` manually: `window.__next().click()`.

### 3.4 Per-course procedure (one tab)
1. `navigate` to `/courses/<slug>` → batch: `wait 1.5`, `eval(localStorage.__setup);__fix()`.
   (`Start course` is optional; `__fix` auto-enrolls on the first Next.)
2. Loop batches of `[__fix(), wait 1.3] × 6` until `LESSONS DONE`. ~1.5 s per lesson.
3. `__go(<quiz slug>)`, `wait 1.5`, `__q()`. Then per question one batch:
   `[__ans([i]), wait 0.8, __q()]`. Last answer returns `SUBMITTED` → `wait 3`, `__res()`; if it
   says `CHECKING`, wait 5 more and re-read.
4. Fail (<80 %) → click the `Retake quiz` button, redo with corrected answers.
5. Multi-quiz courses (API/Bedrock/Vertex have 8–9): after each pass run `__fix()` again — it
   skips quiz items, so use `__todo()` to list remaining `X` quiz slugs and `__go` each.
6. Verify: `navigate` `/courses/<slug>/badge`, `wait 1.5`, read `ISSUED`. Also check
   `__todo()` has no `X` except possibly the badge item itself.

### 3.5 Parallel plan (what actually made it fast)
- One tab per course, 3–4 tabs per worker, **interleaved in the same batch**:
  `[tabA __fix, tabB __fix, tabC __ans, wait 1.3, tabA __fix, tabB __fix, tabC __q]`. The wait
  is shared, so throughput scales with tab count.
- Big courses (60+ lessons, 8+ quizzes) → spawn one general-purpose subagent per course with
  its own tab id (create the tab yourself first with `tabs_create_mcp` and pass the id, or let
  the agent create one). Run agents in one message so they execute concurrently. Keep 2–4 small
  courses for yourself in the main thread.
- Quiz answering is the only non-mechanical cost (~10 s per question with reading); parallelism
  hides it — always keep other tabs' `__fix` calls in the same batch as an `__ans`.
- Skip what is already done: cards marked `Completed` on the catalog, `V` items in `__todo()`.

### 3.6 Subagent prompt template
```
Complete a free <PLATFORM> course for the user (they explicitly asked for all badge courses on
their logged-in account). Use ONLY mcp__claude-in-chrome__* tools, ONLY on tab id <ID>
(navigate it to <COURSE URL>; wait 1s after any navigate before JS).
Helpers: run javascript_tool `eval(localStorage.__setup);'ok'` (re-run after full navigates).
__fix() → next incomplete lesson / 'completed X' / 'LESSONS DONE; quiz todo: X'; __todo();
__go(slug); __q(); __ans([i]); __res().
Steps: batches of [__fix, wait 1.3] x6 until LESSONS DONE; then for each X quiz in __todo():
__go(slug), wait 1.5, answer yourself with careful reasoning (multi-select when role=checkbox),
batch [__ans, wait 0.8, __q]; after SUBMITTED wait 3-5s, __res(); pass >=80% else click
'Retake quiz' and redo. Finally navigate to <COURSE URL>/badge, wait 1.5, confirm 'ISSUED'.
Extension is flaky: on a batch error re-check state and continue; batches <=10 actions.
Never enter credentials/forms; only quiz answers and lesson navigation. Report badge status,
quiz scores, anything skipped.
```

## 4. Quiz answering policy
- Read the whole stem: watch for `NOT`, `best`, `first`, `most likely`, `all of these`.
- Course vocabulary beats general knowledge: 4D Framework = Delegation, Description,
  Discernment, Diligence; Delegation-Diligence loop (should AI do this?) vs
  Description-Discernment loop (how); three Diligences = Creation, Transparency, Deployment;
  Diligence = accountability + disclosure; "human in the loop" = you decide and take
  responsibility.
- Product facts seen: Claude Tag acts under its own account in channels; memory/instructions/
  tools are per channel; redirect a task by replying in its thread; routines keep running after the
  creator leaves; Cowork connector-only scheduled tasks run remotely; Enterprise domain claiming is
  irreversible; visibility/logging must precede member access.
- If unsure and the score margin is thin, open the lesson in a spare tab and search its text.
- Keep a Q→A log per quiz for the final report; on a fail, change only the doubtful answers.

## 5. OpenAI Academy (academy.openai.com) — recon protocol (unverified)
- Structure seen: `/home/courses/<slug>-<id>` course pages, `/home/clubs/<slug>/overview`
  communities, events. Log in state required.
- Run recon: `get_page_text` on a course; `find` "mark complete / continue / next lesson" and
  "quiz submit"; click one lesson's completion control manually; `read_network_requests` with
  `clear:true` before and read after to learn the progress endpoint; look for a certificate/badge
  page ("certificate", "badge", "completed"). Then build the same three helpers (`__fix` over the
  course outline links, `__q`/`__ans` over the quiz's option elements — check `[role=radio]`,
  `input[type=radio]`, or buttons) and persist via `localStorage.__setup`.
- Video lessons may only complete on playback events; if `Mark complete` is absent, test whether
  seeking the `<video>` to the end (`v.currentTime=v.duration; v.dispatchEvent(new Event('ended'))`)
  is what the page listens to — do this only if the platform treats "watched" as the completion
  signal; report if completion needs real watch time.
- Record findings here (selectors, endpoint names, badge location) after the first run.

## 6. Google — two different systems

### 6.1 developers.google.com/learn/pathways (Google Developer Profile badges)
- Target pattern: `https://developers.google.com/learn/pathways/quizzes/<pathway>` (e.g.
  `ai-models-on-gpu-intro`, `scale-and-serve-jax-models-on-nvidia-gpus`). The pathway page
  `/learn/pathways/<pathway>` lists articles/videos/codelabs; the badge is awarded by **passing the
  quiz** while signed in with a Developer Profile (content items are optional for the badge).
- Recon: on the quiz page use `read_page filter interactive` — questions are custom elements
  (`devsite-quiz`/shadow DOM is possible: if `querySelectorAll('input')` is empty, walk
  `el.shadowRoot`). Select answers, press the submit/check button, read the score; retake if
  allowed. Never bypass sign-in prompts — ask the user to sign in.

### 6.2 skills.google paths (Google Cloud Skills Boost)
- A path = ordered courses; each course = modules of videos/readings + a quiz; some contain
  **labs** (real cloud sandboxes, timed, credit-consuming — "This lab costs 5 Credits") and skill
  badges require a challenge lab. Course quizzes and content are fair game; **labs need the
  user's explicit go-ahead per lab** and are done for real (§6.3) — no bypassing grading.
- Recon for courses: open the path, list courses and their activity types; for each course open
  the first activity, find the `Mark as completed`/`Next` control and the quiz UI (radio groups
  with a `Submit` button, score shown inline, unlimited retries). Instrument as in §3 (`__fix`
  over the course's activity list, `__q`/`__ans` over the quiz).
- Stop conditions: any purchase, any proctored exam (Google Cloud Certification), any
  age/identity verification, any lab the user has not approved.

### 6.3 Qwiklabs lab playbook (verified 2026-09 on GSP1247, 100/100)
**Anatomy.** Lab page `…/paths/<p>/course_templates/<c>/labs/<n>` (catalog twin
`skills.google/focuses/<m>?parent=catalog`; manual id `GSPnnnn`). Once started the header shows
`End` (deletes the project — the user's call only), the timer (`1h 21m left`; typically 60 m of
access), `Score: NN / 100` (opens the **Checkpoints** dialog: one row per task with `n / max` and
a `Check my progress` button — the same buttons also sit inline under each task; `find` them as
`Check my progress for <task name>`), and a `Lab setup and access` panel with Username /
Password / Project ID and `Open Google Cloud console`. One running lab per account; starting
another ends the current one.

**Source of truth is the live lab page.** Manual code blocks contain template values
(`{{{project_0.startup_script.gemini_flash_lite_model_id | model id}}}`, region, endpoints) that
render only while the lab runs. `get_page_text` drops code blocks entirely: get the verbatim
text by (a) fetching the catalog URL with a web extractor (whole manual, placeholders
unresolved) and (b) resolving each placeholder on the live page (`find` the block, `scroll_to`,
`zoom`). Prompts carry suffixes the data path depends on (`… title should be string, year should
be integer.`). Community solution scripts/videos and official codelabs only tell you *which*
steps exist; their endpoints and prompts are stale (retired `gemini-pro`,
`text-multilingual-embedding-002`) — never paste them.

**Per task:** run the prescribed steps *exactly and one at a time* → verify the resulting state
yourself (`gcloud services list --enabled`; `gcloud projects get-iam-policy $PROJECT_ID
--flatten='bindings[].members' --filter="bindings.members:user:$USER" --format='value(bindings.role)'`;
`bq ls gemini_demo`; row/NULL counts) → wait until every job prints `DONE` → click that task's
`Check my progress` → read the toast (`Check complete. Points earned: N. Message: …`; screenshot
within 3 s) → on a partial, run §6.4 before moving on — but never camp on one task for more than
~5 min: later tasks never depend on the checker, and lag-type sub-checks pass on a later click.

**Driving Cloud Shell from Claude-in-Chrome.**
- Use the standalone terminal `https://shell.cloud.google.com/?show=terminal&project=<id>&authuser=<n>`
  rather than the console's embedded panel (`?cloudshell=true`), which drops its websocket every
  ~30 s after a re-login ("The connection to your Google Cloud Shell was lost → Reconnect"). The
  standalone page recovers the same tmux session ("Terminal tabs have been recovered") — including
  keystrokes typed while the panel said "lost" — so after a drop don't retype: open it and look.
  `authuser=<n>` is the account's index in the Google session and changes after a re-login
  (5 → 0); take it from the console URL.
- Click the terminal, then type with a leading space and `clear;` first (the first character
  after a click is often dropped: `bq mk` → `q mk`), and end commands with a sentinel
  (`&& echo T4_DONE`). Keep one `type` ≤ ~40 lines.
- Anything with backticks, quotes or `$` (all BigQuery SQL): write a file with a quoted heredoc
  (`cat > t6a.sql <<'EOF' … EOF`), check `wc -l`, then
  `bq query --use_legacy_sql=false --format=none < t6a.sql`. `bq` runs count exactly like the
  console editor (same project, user and job history).
- Anything over ~30 s (vision or embeddings over a table): `nohup bash -c '…' > job.log 2>&1 &`
  so a dropped socket cannot kill it; then `grep -E '_OK|_FAIL|rror|Created|Replaced' job.log`.
  A `bq … | head` pipeline hides bq's exit status — read the output; never trust `&& echo OK`
  after a pipe.
- Shell variables survive a reconnect of the same tmux session, not a fresh one: recompute
  `PROJECT_ID=$(gcloud config get-value project)` and `USER=$(gcloud config get-value account)`.

**Session drops.** A console tab on Google's "Choose an account" page with every account
`Signed out` means the lab session was invalidated (it happened mid-lab). Stop, tell the user
which student account to click, wait, then reopen the standalone shell — project state, home-dir
files and the score survive. You never type the password.

**Finish.** Only `Score: 100 / 100` with every row at `max / max` counts, confirmed after a page
reload. Report, then let the user press `End`.

### 6.4 How "Check my progress" grades, and the diagnostics ladder
Each checkpoint is a bundle of independent sub-checks worth a few points each; the toast's
`Points earned` is their sum and its `Message` names the first failing one. They run server-side
at click time against three sources (all verified on GSP1247):
1. **Cloud Audit Logs — the exact API call the manual prescribes.** `gcloud services enable a b`
   (one `BatchEnableServices` event) scored 5/15 although `gcloud services list --enabled` showed
   both APIs on and both IAM roles were present; the two single-service commands as printed
   (`EnableService` ×2) scored 15/15 on the next click. So: one command per line as written, no
   batching, no "equivalent" flags, and swap CLI for console (or back) only when the resulting
   API call is identical (`bq mk --connection` was credited for a UI-created connection;
   `gcloud projects add-iam-policy-binding` for the IAM page).
2. **BigQuery job history — every prescribed query, including result-viewing `SELECT`s.** The
   summary `SELECT … ML.GENERATE_TEXT(MODEL gemini_lite …)` creates nothing and is worth 5/20;
   skipping "You can view the results…" steps is invisible until the toast says "Please run the
   SQL query …".
3. **Resource state and content.** Names verbatim (`movie_posters_results_embeddings`, not
   `movie_posters_embeddings`); tables holding valid rows; downstream queries (`VECTOR_SEARCH`)
   having *succeeded* (§6.5).

Timing: a click while a job is `RUNNING`, or before an IAM grant has propagated, fails that
sub-check; a later click passes it — that is the 5 → 10 → 15 pattern on repeated clicks (lag,
not a broken checker). A remote `CREATE MODEL` can sit `RUNNING` for minutes waiting for the
connection service account's role to propagate (229 s seen); it completes — don't cancel, don't
check meanwhile.

**Ladder for a partial or zero checkpoint:**
1. Read the `Message`: it names the sub-step.
2. Verify that sub-step's state from Cloud Shell. Wrong → do the step. Right → 3.
3. State right but uncredited = missing fingerprint: re-run the manual's command/query for that
   sub-step individually and verbatim, wait `DONE`, re-click.
4. A prescribed query errored: fix the **data** upstream (NULL guards, re-run the producing
   step), never the checker; confirm the query returns rows; re-click.
5. Score unchanged after 1–2 min: reload the lab page (toast/alert text goes stale) and read
   `Score` again before concluding anything.

Never call it a checker bug before 1–5: on the first GSP1247 run all 35 uncredited points were
a batched command, a skipped `SELECT` and a failed `VECTOR_SEARCH`.

### 6.5 BigQuery ML / Gemini lab gotchas (GSP1247 family)
- Connection + IAM from the shell, all credited:
  `bq mk --connection --location=US --project_id=$PROJECT_ID --connection_type=CLOUD_RESOURCE gemini_conn`;
  `SA=$(bq show --connection --format=json $PROJECT_ID.US.gemini_conn | python3 -c 'import sys,json;print(json.load(sys.stdin)["cloudResource"]["serviceAccountId"])')`;
  `gcloud projects add-iam-policy-binding $PROJECT_ID --member serviceAccount:$SA --role=roles/aiplatform.user`
  (the 2026 console calls it "Agent Platform User"; older manuals say "Vertex AI User"). The
  first `CREATE MODEL … REMOTE WITH CONNECTION` then waits on propagation — expect minutes.
- 2026 endpoints in this lab: `gemini-2.5-flash-lite` for both `gemini_lite` and
  `gemini_lite_vision`, `text-embedding-004` for `text_embedding` — read them from the live page.
- **LLM nondeterminism breaks the pipeline, not your SQL.** The JSON-extraction step
  (`ML.GENERATE_TEXT` over the poster object table) can return a refusal ("I am sorry, but I
  cannot provide the movie title…") or partial JSON (a title, no year). `JSON_QUERY` → NULL →
  `CONCAT` → NULL content → `ML.GENERATE_EMBEDDING` returns an **empty vector with an empty
  status** (the manual's `WHERE ml_generate_embedding_status = ''` misses it) → `VECTOR_SEARCH`
  fails with "Dimension of column `ml_generate_embedding_result` in the base table does not match
  … in the query data" → checkpoint 0/25. Diagnose on both sides of the search:
  `SELECT ARRAY_LENGTH(ml_generate_embedding_result) dim, COUNT(*) n, COUNTIF(content IS NULL) nulls FROM <emb_table> GROUP BY 1`.
  Fix that was credited: rebuild the poster embeddings with the manual's query plus
  `WHERE title IS NOT NULL AND year IS NOT NULL` in its subquery, then re-run both `VECTOR_SEARCH`
  queries (re-running the vision step is a coin flip: one run refused a poster, the next dropped a
  year on another).
- Look at the data after every producing step: `SELECT COUNT(*), COUNTIF(<col> IS NULL) FROM …`;
  19 posters → 19 rows; embeddings all one dimension; the IMDB pre-1935 subset ≈ 480 rows.
- The formatting query uses double-quoted `" ```json"` strings — one more reason for heredoc files.

## 7. Reporting format
```
Platform · course · lessons N/N · quiz X/Y (pass) · badge ISSUED <date> · notes
Lab GSPnnnn · score 100/100 · checkpoints 7/7 · <time> left · diagnosed: <task → cause> …
...
Skipped: <course> — <reason: paid lab / proctored / needs sign-in>
```
Send a mid-task progress line after each finished course (the user often reads from a phone).

## 8. Checklist
- [ ] Rules in §0 read; nothing proctored/paid queued
- [ ] Catalog listed, done items skipped, badge courses identified
- [ ] Helpers installed and persisted in `localStorage.__setup` on that origin
- [ ] Tabs created and assigned; big courses handed to subagents in one message
- [ ] Every batch ≤ 12 actions, waits only via `computer.wait`, no page timers
- [ ] Each course verified on its badge page before reporting
- [ ] Lab: user approved the credit spend; every command/query taken verbatim from the live lab page
- [ ] Lab: steps run one at a time as printed; state verified and jobs `DONE` before each check
- [ ] Lab: any partial checkpoint went through the §6.4 ladder; 100/100 confirmed after a reload
- [ ] Lab: `End` left to the user
- [ ] Report + Q→A log delivered; skill updated with new platform findings