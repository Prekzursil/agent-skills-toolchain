---
name: "academy-badge-runner"
description: "Complete self-paced course/badge programs on the user's logged-in account with Claude in Chrome — Claude Academy (verified), OpenAI Academy, Google Developers pathways, Google Skills paths — using parallel tabs and one subagent per course."
---

# Academy badge runner

Use when the user asks to finish courses, earn completion badges, or clear a learning path on a
platform they are already signed in to (academy.claude.com, academy.openai.com,
developers.google.com/learn/pathways, skills.google). The job is mechanical navigation plus
answering knowledge checks yourself. Everything here was learned by doing all 22 Claude Academy
badge courses in one session; the Claude Academy playbook is verified, the others are recon
protocols to run on first use (then update this skill with what you find).

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
  `\n`; strip with `.replace(/[-]/g,'')` before regex matching, and anchor on a
  full label like `Next lesson` (plain `Next` matches "What's next" and lesson titles such as
  "Next Token Prediction").
- Native `<input type=radio>` in these UIs are `aria-hidden` shims; click the Radix
  `[role=radio]` / `[role=checkbox]` elements instead.
- A full-page `navigate` wipes `window.*` helpers (SPA link clicks do not) → re-run
  `eval(localStorage.__setup)` after navigating; guard with
  `typeof window.__fix==='function'||eval(localStorage.__setup)`.
- Tab ids are stable across navigations; the user may open extra tabs in the group — never touch
  tabs you did not create or were not assigned.

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

### 6.2 skills.google paths (e.g. `/paths/4459`, Google Cloud Skills Boost)
- A path = ordered courses; each course = modules of videos/readings + a quiz; some contain
  **labs** (real cloud sandboxes, timed, may cost credits) and skill badges require a challenge
  lab. Course quizzes and content are fair game; **labs need the user's explicit go-ahead per
  lab**, and challenge labs must be done for real (no bypassing grading).
- Recon: open the path, list courses and their activity types; for each course open the first
  activity, find the `Mark as completed`/`Next` control and the quiz UI (Skills Boost quizzes are
  radio groups with a `Submit` button, score shown inline, unlimited retries). Instrument as in
  §3 (`__fix` over the course's activity list, `__q`/`__ans` over the quiz).
- Stop conditions: any "Start Lab" that consumes credits, any purchase, any proctored exam
  (Google Cloud Certification), any age/identity verification.

## 7. Reporting format
```
Platform · course · lessons N/N · quiz X/Y (pass) · badge ISSUED <date> · notes
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
- [ ] Report + Q→A log delivered; skill updated with new platform findings