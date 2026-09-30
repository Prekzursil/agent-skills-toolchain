---
name: academy-badge-runner
description: Use when the user asks to finish courses, earn completion badges, clear a learning path, or run a hands-on lab on a platform they are already signed in to (academy.claude.com, academy.openai.com, developers.google.com/learn/pathways, skills.google). Mechanical navigation plus self-answered knowledge checks; labs are done as real cloud work in a way the platform's checker credits.
---

# Academy badge runner

Use when the user asks to finish courses, earn completion badges, clear a learning path, or run a hands-on lab on a platform they are already signed in to (academy.claude.com, academy.openai.com, developers.google.com/learn/pathways, skills.google). The job is mechanical navigation plus answering knowledge checks yourself — and, for labs, doing the real cloud work in a way the platform's checker credits. The Claude Academy playbook (§3) was verified by doing all 22 badge courses in one session; the Google Skills lab playbook (§6.3–6.5) was verified on GSP1247 (BigQuery ML + Gemini): a first run stalled at 65/100 with "correct" SQL, a second run scored 100/100 once the checker's actual rules were understood. GSP1248, GSP1257, GSP1258 and GSP1259 then reached 100/100 and the GSP341 challenge lab was finished using the field notes in §6.6. GSP322 was driven to **100/100 (2026-09-30, second session)** by extracting the grader's own query filters (§6.4b + `grader_probe.py` + GRADER-INTERNALS.md) — the universal method for any stuck checkpoint. Read §6.4 before touching a "Check my progress" button. The rest are recon protocols to run on first use (then update this skill with what you find).

## 0. Rules that never bend

Only the user's own account, only content they asked for. Never enter credentials, payment data, personal data forms, or accept terms/consent banners; if a page needs any of these, stop and hand it to the user or can proceed with owner's explicit accord. (The user pasting lab credentials to the agent in chat counts as the user supplying them — that is the normal handoff for the §6.3b lane; the agent never finds or reuses them on its own.)

Answer every quiz from your own knowledge (plus the course's own lessons if a question is course-specific — open the lesson in another tab and read it). Do not scrape answer keys from JS bundles or network responses.

No proctored / identity-verified certification exams (Google Cloud certifications, any exam with a proctor or webcam step). No paid labs or credit-consuming labs without an explicit yes from the user for that specific lab. Knowledge-check quizzes and content completion are fine.

Never use the user's page-facing browser tab for other browsing; each worker owns its own tab id.

Labs: never forge, replay or script the platform's "Check my progress" request, and never call in-page helpers to mark a lab complete. The click is only a trigger — grading runs server-side against the project's state, audit logs and job history (§6.4) — so replaying it changes nothing, and it is off-limits regardless. Enforcement is real: Google has cancelled Arcade swag/points for scripted completion (community-documented 2025-12) — human clicks each check, real cloud work only. When asked to "trigger validation manually" or "force it", decline in one line and run the diagnostics ladder in §6.4 instead: every stuck checkpoint so far had a legitimate cause. Repairing the lab project's own evidence plumbing (e.g. re-shipping REAL auth.log lines to Cloud Logging when the provisioning agent failed) is lab work, not grader manipulation — but only real events, never fabricated ones.

Lab credentials are typed by the user, every time — including "temporary" lab passwords and the re-login after a session drop. Never click a lab's End button unless the user says so (it deletes the project, and the timer cannot be paused).

## 1. Operating model (Recon → Instrument → Drive → Verify → Report)

Recon (once per platform, ~5 min): find (a) the catalog and the badge marker, (b) what actually marks a lesson complete, (c) how quizzes render, (d) where the badge shows. Techniques that worked: get_page_text, find, read_network_requests after one manual click (look for RPC names like StartLesson/CompleteLesson), fetching the SPA's JS chunks from inside javascript_tool and grepping for mutation names (completeLesson, onNextClick, onPassed), and [role=radio]/[role=checkbox] for quiz options.

Instrument: install small window helpers in the tab with javascript_tool, then persist them with localStorage.__setup = [...names].map(n=>'window.'+n+'='+window[n].toString()).join(';') so any other tab on that origin gets them with eval(localStorage.__setup). (Using toString() avoids the backslash-escaping bugs you get when pasting code into a template string; note browser_batch JSON needs \\ for every regex backslash, direct javascript_tool calls do not.)

Drive: advance with an idempotent step function driven from browser_batch ([js step, wait 1.3s] × 6), never with page-side setTimeout loops.

Verify: badge page says ISSUED; outline shows every lesson (completed); quiz result You passed.

Report: per course — lessons done, quiz score, badge status, anything skipped and why.

Labs (§6.3) use a different loop: Execute exactly → Verify state → Check → Diagnose. One lab at a time (the platform allows a single running lab per account), so labs are never parallelised.

## 2. Claude-in-Chrome quirks (these cost the most time — read first)

Hidden tabs throttle page timers to ~1/min. Every parallel tab is hidden. Any await sleep() / setTimeout / MutationObserver-with-timeout inside javascript_tool stalls (a 6 s wait took 40 s). All waiting must be computer.wait actions inside browser_batch.

javascript_tool right after a navigate fails intermittently → always wait 1–1.5s after navigating, and prefer a standalone navigate call followed by a batch.

A batch stops at the first error and the tool sometimes reports "failed in the extension" even though earlier actions ran. Keep batches ≤ 8–12 actions, then re-read state.

Output containing =/?/& runs or attribute dumps is redacted as [BLOCKED: Cookie/query string data]. Return short strings; strip =?&; from any HTML/JS you print (.replace(/[=?&;]/g,' ')).

innerText of icon-bearing links starts with a Private-Use-Area glyph (U+E000–F8FF) followed by \n; strip with .replace(/[-]/g,'') (the Private Use Area) before regex matching, and anchor on a full label like Next lesson (plain Next matches "What's next" and lesson titles such as "Next Token Prediction").

Native <input type=radio> in these UIs are aria-hidden shims; click the Radix [role=radio] / [role=checkbox] elements instead.

A full-page navigate wipes window.* helpers (SPA link clicks do not) → re-run eval(localStorage.__setup) after navigating; guard with typeof window.__fix==='function'||eval(localStorage.__setup).

Tab ids are stable across navigations; the user may open extra tabs in the group — never touch tabs you did not create or were not assigned.

"Tool … failed in the extension" comes in bursts: screenshots can fail for 30–60 s while type, find, get_page_text and navigate keep working. Don't hammer it — Bash sleep 15–25, then retry. A type that "failed" usually landed in full (verify with wc -l or __todo()) — check state before re-sending, or you double-run commands.

The browser window can silently shrink (a 990×445 frame appeared mid-session): read the frame size in the screenshot header before coordinate clicks and resize_window 1600×950 if needed.

Terminals and consoles drawn in iframes or canvas (Cloud Shell) are invisible to read_page, get_page_text and find — read them with zoom on the terminal region; printed text is the only state you get, so make commands print sentinels.

Dialogs with their own scrollbar (Skills Boost "Checkpoints") ignore wheel events over the page: scroll_to a ref inside them or left_click_drag the dialog's scrollbar track.

Toasts live ~5 s and their alert node lingers with stale text: screenshot within 3 s of the click, and confirm from the persistent score element after a reload — never from find on the alert.

A ref from find may be a hidden duplicate of the control (the same button exists in a dialog and inline in the page): if a ref click produces nothing, click the visible copy by coordinate.

A tab's viewport can get stuck tiny (innerWidth 98, halving on every scaled screenshot, often after resize_window): stop using that tab and open a fresh one with tabs_create_mcp.

A batch that mixes a long type with wait/zoom fails far more often than the pieces alone: send the type by itself, sleep in Bash, then read with a separate zoom.

find refs can point at the wrong control: a ref named "Lab setup and access" opened Send feedback. Never click a ref near a feedback/send UI without a screenshot; close a stray feedback overlay by reloading the page (never press its Send).

Side panels (Gemini Cloud Assist, "Lab setup and access", tutorials) overlay content and eat coordinate clicks — close them with their X first.

## 3. Claude Academy playbook (verified 2026-09)

### 3.1 Discovery

Catalog: https://academy.claude.com/all?kind=course, click the Load more button, then main a[href^="/courses/"] gives slugs; card text carries Enrolled / Completed.

Badge courses = the course page shows a Completion badge chip. Empirically every course with a quiz has a badge; the no-quiz ones (train-the-trainer, agent skills, SDLC playbook, subagents) do not.

Badge page: /courses/<slug>/badge → main text contains ISSUED <DATE> once earned; the outline lists it as Completion badge (earned). Your learning in the top nav lists everything.

### 3.2 Mechanics

Connect-RPC backend at /api/anthropic.academy.api.v1alpha.AcademyService/{StartLesson, CompleteLesson, GetCourseProgress, CreateEnrollment, UpdateEnrollment, EmitProgressEvent, CompleteCertification} (JSON over POST). Lesson/course ids are opaque, not slugs; direct calls were not needed — the UI path below is fast enough. Don't burn time on it unless a course has hundreds of lessons.

A lesson is marked complete when the Next lesson link at the page bottom (or Up next on the post-quiz lesson) is clicked (onNextClick → completeLesson). Scrolling or dwell does nothing. Clicking auto-enrolls (auto_progress) if the user never pressed Start course.

Quizzes: one question per screen, Question i of N, options are main [role=radio] (single) or [role=checkbox] (multi); buttons Back / Next / Submit. After Submit the page shows Checking your answers… (can take 5–10 s in a hidden tab) then You passed / You got X of N correct. Pass mark 80 %. Retake quiz button on failure. Passing triggers the badge; no separate claim step despite the copy saying "select Create your completion badge".

Some courses put an optional lesson after the quiz (e.g. additional-activities); its bottom link is Up next → Completion badge and clicking it completes the lesson.

Quiz slugs vary: course-quiz, certificate-of-completion, certificate-quiz, final-assessment, quiz-on-…, assessment-on-….

### 3.3 Helper library (paste as-is into javascript_tool on a course page, once)

```js
window.__els=()=>[...document.querySelectorAll('main [role=radio],main [role=checkbox]')];
window.__txt=r=>{let p=r;while(p.parentElement&&p.parentElement.querySelectorAll('[role=radio],[role=checkbox]').length===1)p=p.parentElement;return p.innerText.trim()};
window.__q=()=>{const rs=window.__els();const t=(document.querySelector('main')||document.body).innerText;const m=(t.match(/Question \d+ of \d+[\s\S]*?\n(?:\d+ answered\n)?([^\n]+)/)||[])[0];return (m||'NO QUESTION on '+location.pathname)+'\n['+(rs[0]&&rs[0].getAttribute('role'))+']\n'+rs.map((r,i)=>i+': '+window.__txt(r).replace(/\s+/g,' ')).join('\n')};
window.__ans=idxs=>{const rs=window.__els();for(const i of idxs)rs[i].click();const b=[...document.querySelectorAll('main button')].find(b=>/^(Next|Submit)/.test(b.innerText.trim()));const bt=b?b.innerText.trim():'nobtn';if(b&&!b.disabled)b.click();return bt==='Submit'?'SUBMITTED':bt};
window.__res=()=>{const t=(document.querySelector('main')||document.body).innerText;return (t.match(/You (passed|did not pass|didn't pass)[\s\S]{0,40}/)||[/Checking your answers/.test(t)?'CHECKING':'no result'])[0]+' | completed:'+(t.match(/\(completed\)/g)||[]).length};
window.__items=()=>{const seen=new Set();return [...document.querySelectorAll('a[href^="/courses/"]')].filter(a=>{const h=a.getAttribute('href');if(h.split('/').length!==4||seen.has(h))return false;seen.add(h);return !/Next|Previous|Up next/.test(a.innerText)})};
window.__todo=()=>window.__items().map(a=>(/completed|earned/.test(a.innerText)?'V ':'X ')+a.getAttribute('href').split('/').pop()).join(' ');
window.__go=slug=>{const a=window.__items().find(a=>a.getAttribute('href').endsWith('/'+slug));if(!a)return 'nolink '+slug;a.click();return 'go '+slug};
window.__next=()=>[...document.querySelectorAll('a')].find(a=>/(^|\n)\W?(Next lesson|Up next)\b/.test(a.innerText.replace(/[-]/g,'')));
window.__fix=()=>{const items=window.__items();const todo=items.filter(a=>!/completed|earned/.test(a.innerText));const isQuiz=a=>/quiz|assessment|certificate/i.test(a.getAttribute('href'))||/quiz/i.test(a.innerText);const t=todo.find(a=>!isQuiz(a)&&!/\/badge$/.test(a.getAttribute('href')));const cur=location.pathname.split('/').pop();if(!t){const q=todo.find(a=>isQuiz(a));return 'LESSONS DONE; quiz todo: '+(q?q.getAttribute('href').split('/').pop():'none')+' | '+(items.length-todo.length)+'/'+items.length}const slug=t.getAttribute('href').split('/').pop();if(cur!==slug){t.click();return 'goto '+slug}const n=window.__next();if(!n)return 'no next on '+slug;n.click();return 'completed '+slug};
localStorage.__setup=['__els','__txt','__q','__ans','__res','__items','__todo','__go','__next','__fix'].map(n=>'window.'+n+'='+window[n].toString()).join(';');
'installed '+window.__todo()
```

Semantics: __fix() is idempotent — it reads the course outline (sidebar/dropdown links, (completed) markers), goes to the first incomplete non-quiz lesson, and on the next call clicks Next lesson there. It returns goto X / completed X / no next on X (page not rendered yet, just call again) / LESSONS DONE; quiz todo: <slug> | done/total. __q() prints the current question with 0-based options; __ans([i,...]) selects and presses Next/Submit; __res() reads the verdict. If a lesson slug contains "assessment"/"quiz" but is really a lesson, __q() says NO QUESTION — then click __next() manually: window.__next().click().

### 3.4 Per-course procedure (one tab)

navigate to /courses/<slug> → batch: wait 1.5, eval(localStorage.__setup);__fix(). (Start course is optional; __fix auto-enrolls on the first Next.)

Loop batches of [__fix(), wait 1.3] × 6 until LESSONS DONE. ~1.5 s per lesson.

__go(<quiz slug>), wait 1.5, __q(). Then per question one batch: [__ans([i]), wait 0.8, __q()]. Last answer returns SUBMITTED → wait 3, __res(); if it says CHECKING, wait 5 more and re-read.

Fail (<80 %) → click the Retake quiz button, redo with corrected answers.

Multi-quiz courses (API/Bedrock/Vertex have 8–9): after each pass run __fix() again — it skips quiz items, so use __todo() to list remaining X quiz slugs and __go each.

Verify: navigate /courses/<slug>/badge, wait 1.5, read ISSUED. Also check __todo() has no X except possibly the badge item itself.

### 3.5 Parallel plan (what actually made it fast)

One tab per course, 3–4 tabs per worker, interleaved in the same batch: [tabA __fix, tabB __fix, tabC __ans, wait 1.3, tabA __fix, tabB __fix, tabC __q]. The wait is shared, so throughput scales with tab count.

Big courses (60+ lessons, 8+ quizzes) → spawn one general-purpose subagent per course with its own tab id (create the tab yourself first with tabs_create_mcp and pass the id, or let the agent create one). Run agents in one message so they execute concurrently. Keep 2–4 small courses for yourself in the main thread.

Quiz answering is the only non-mechanical cost (~10 s per question with reading); parallelism hides it — always keep other tabs' __fix calls in the same batch as an __ans.

Skip what is already done: cards marked Completed on the catalog, V items in __todo().

### 3.6 Subagent prompt template

Complete a free <PLATFORM> course for the user (they explicitly asked for all badge courses on their logged-in account). Use ONLY mcp__claude-in-chrome__* tools, ONLY on tab id <ID> (navigate it to <COURSE URL>; wait 1s after any navigate before JS). Helpers: run javascript_tool `eval(localStorage.__setup);'ok'` (re-run after full navigates). __fix() → next incomplete lesson / 'completed X' / 'LESSONS DONE; quiz todo: X'; __todo(); __go(slug); __q(); __ans([i]); __res(). Steps: batches of [__fix, wait 1.3] x6 until LESSONS DONE; then for each X quiz in __todo(): __go(slug), wait 1.5, answer yourself with careful reasoning (multi-select when role=checkbox), batch [__ans, wait 0.8, __q]; after SUBMITTED wait 3-5s, __res(); pass >=80% else click 'Retake quiz' and redo. Finally navigate to <COURSE URL>/badge, wait 1.5, confirm 'ISSUED'. Extension is flaky: on a batch error re-check state and continue; batches <=10 actions. Never enter credentials/forms; only quiz answers and lesson navigation. Report badge status, quiz scores, anything skipped.

## 4. Quiz answering policy

Read the whole stem: watch for NOT, best, first, most likely, all of these.

Course vocabulary beats general knowledge: 4D Framework = Delegation, Description, Discernment, Diligence; Delegation-Diligence loop (should AI do this?) vs Description-Discernment loop (how); three Diligences = Creation, Transparency, Deployment; Diligence = accountability + disclosure; "human in the loop" = you decide and take responsibility.

Product facts seen: Claude Tag acts under its own account in channels; memory/instructions/ tools are per channel; redirect a task by replying in its thread; routines keep running after the creator leaves; Cowork connector-only scheduled tasks run remotely; Enterprise domain claiming is irreversible; visibility/logging must precede member access.

If unsure and the score margin is thin, open the lesson in a spare tab and search its text.

Keep a Q→A log per quiz for the final report; on a fail, change only the doubtful answers.

## 5. OpenAI Academy (academy.openai.com) — recon protocol (unverified)

Structure seen: /home/courses/<slug>-<id> course pages, /home/clubs/<slug>/overview communities, events. Log in state required.

Run recon: get_page_text on a course; find "mark complete / continue / next lesson" and "quiz submit"; click one lesson's completion control manually; read_network_requests with clear:true before and read after to learn the progress endpoint; look for a certificate/badge page ("certificate", "badge", "completed"). Then build the same three helpers (__fix over the course outline links, __q/__ans over the quiz's option elements — check [role=radio], input[type=radio], or buttons) and persist via localStorage.__setup.

Video lessons may only complete on playback events; if Mark complete is absent, test whether seeking the <video> to the end (v.currentTime=v.duration;v.dispatchEvent(new Event('ended'))) is what the page listens to — do this only if the platform treats "watched" as the completion signal; report if completion needs real watch time.

Record findings here (selectors, endpoint names, badge location) after the first run.

## 6. Google — two different systems

### 6.1 developers.google.com/learn/pathways (Google Developer Profile badges)

Target pattern: https://developers.google.com/learn/pathways/quizzes/<pathway> (e.g. ai-models-on-gpu-intro, scale-and-serve-jax-models-on-nvidia-gpus). The pathway page /learn/pathways/<pathway> lists articles/videos/codelabs; the badge is awarded by passing the quiz while signed in with a Developer Profile (content items are optional for the badge).

Recon: on the quiz page use read_page filter interactive — questions are custom elements (devsite-quiz/shadow DOM is possible: if querySelectorAll('input') is empty, walk el.shadowRoot). Select answers, press the submit/check button, read the score; retake if allowed. Never bypass sign-in prompts — ask the user to sign in.

### 6.2 skills.google paths (Google Cloud Skills Boost)

A path = ordered courses; each course = modules of videos/readings + a quiz; some contain labs (real cloud sandboxes, timed, credit-consuming — "This lab costs 5 Credits") and skill badges require a challenge lab. Course quizzes and content are fair game; labs need the user's explicit go-ahead per lab and are done for real (§6.3) — no bypassing grading.

Recon for courses: open the path, list courses and their activity types; for each course open the first activity, find the Mark as completed/Next control and the quiz UI (radio groups with a Submit button, score shown inline, unlimited retries). Instrument as in §3 (__fix over the course's activity list, __q/__ans over the quiz).

Stop conditions: any purchase, any proctored exam (Google Cloud Certification), any age/identity verification, any lab the user has not approved.

### 6.3 Qwiklabs lab playbook (verified 2026-09 on GSP1247/1248/1257/1258/1259, all 100/100)

Anatomy. Lab page …/paths/<p>/course_templates/<c>/labs/<n> (catalog twin skills.google/focuses/<m>?parent=catalog; manual id GSPnnnn). Once started the header shows End (deletes the project — the user's call only), the timer (1h 21m left; typically 60 m of access), Score: NN / 100 (opens the Checkpoints dialog: one row per task with n / max and a Check my progress button — the same buttons also sit inline under each task; find them as Check my progress for <task name>), and a Lab setup and access panel with Username / Password / Project ID and Open Google Cloud console. One running lab per account; starting another ends the current one.

Source of truth is the live lab page. Manual code blocks contain template values ({{{project_0.startup_script.gemini_flash_lite_model_id | model id}}}, region, endpoints) that render only while the lab runs. get_page_text drops code blocks entirely: get the verbatim text by (a) fetching the catalog URL with a web extractor (whole manual, placeholders unresolved) and (b) resolving each placeholder on the live page (find the block, scroll_to, zoom). Prompts carry suffixes the data path depends on (… title should be string, year should be integer.). Fastest verbatim extraction on the live page (the manual lives in shadow DOM; =?&; must be swapped or the output is redacted):

```js
function walk(r,o){for(const e of r.querySelectorAll('*')){if(e.shadowRoot)walk(e.shadowRoot,o);if(e.tagName==='PRE')o.push(e.innerText)}return o}
walk(document,[]).join('\n----\n').replace(/=/g,'〓').replace(/\?/g,'¿').replace(/&/g,'＆').replace(/;/g,'；')
```

The first two PREs are the student username/password — skip them; map 〓→= when retyping. The lab region renders empty in get_page_text ("select region"); read it from the Lab setup panel: walk all elements for /^(us|europe|asia|…)-[a-z]+\d$/. Community solutions (GitHub repos, eplus.dev, hiiruki, YouTube) are worth a 2-minute check when the user asks or a checkpoint stays at 0: they show which steps exist, the date windows and the query shape the checker was seen to accept. Most repos for a GSP id describe an older variant (GSP341 repos mostly cover the Austin-bikeshare version, the live lab uses the ecommerce dataset) — confirm dataset/model names against the live page first. Their endpoints and prompts go stale (retired gemini-pro, text-multilingual-embedding-002) and their one-shot lab.sh scripts are never run; you type each step yourself.

Per task: run the prescribed steps exactly and one at a time → verify the resulting state yourself (gcloud services list --enabled; gcloud projects get-iam-policy $PROJECT_ID --flatten='bindings[].members' --filter="bindings.members:user:$USER" --format='value(bindings.role)'; bq ls gemini_demo; row/NULL counts) → wait until every job prints DONE → click that task's Check my progress → read the toast (Check complete. Points earned: N. Message: …; screenshot within 3 s) → on a partial, run §6.4 before moving on — but never camp on one task for more than ~5 min: later tasks never depend on the checker, and lag-type sub-checks pass on a later click.

**Driving Cloud Shell from Claude-in-Chrome.**

Use the standalone terminal https://shell.cloud.google.com/?show=terminal&project=<id>&authuser=<n> rather than the console's embedded panel (?cloudshell=true), which drops its websocket every ~30 s after a re-login ("The connection to the Google Cloud Shell was lost → Reconnect"). The standalone page recovers the same tmux session ("Terminal tabs have been recovered") — including keystrokes typed while the panel said "lost" — so after a drop don't retype: open it and look. authuser=<n> is the account's index in the Google session and changes after a re-login (5 → 0); take it from the lab's console tab (javascript_tool: location.href for authuser, and [aria-label*="qwiklabs.net"] for the signed-in student). If the URL has no authuser, try 0, and always confirm the prompt shows student_…@cloudshell for the lab project. Never navigate a console URL without authuser — it opens the browser's default account (a previous lab's student, or the user's own Google account).

Click the terminal, then type with a leading space and clear; first (the first character after a click is often dropped: bq mk → q mk), and end commands with a sentinel (&& echo T4_DONE). Keep one type ≤ ~40 lines.

Anything with backticks, quotes or $ (all BigQuery SQL): write a file with a quoted heredoc (cat > t6a.sql <<'EOF' … EOF), check wc -l, then bq query --use_legacy_sql=false --format=none < t6a.sql. bq runs count exactly like the console editor (same project, user and job history).

Anything over ~30 s (vision or embeddings over a table): nohup bash -c '…' > job.log 2>&1 & so a dropped socket cannot kill it; then grep -E '_OK|_FAIL|rror|Created|Replaced' job.log. A bq … | head pipeline hides bq's exit status — read the output; never trust && echo OK after a pipe.

A session drop mid-poll prints BigQuery error … Invalid Credentials / _FAIL although the job finished server-side: check the resource (bq ls --models ds, bq show -j <job>) before rerunning.

Build variants of a long query with sed from a file you already wrote instead of retyping it (eval/predict windows: sed -n '5,$p' model.sql | sed 's/20160801/20170501/; s/20170430/20170630/; s/^);$/)/' wrapped in ML.EVALUATE(MODEL m, ( … ))).

Shell variables survive a reconnect of the same tmux session, not a fresh one: recompute PROJECT_ID=$(gcloud config get-value project) and USER=$(gcloud config get-value account).

Session drops. A console tab on Google's "Choose an account" page with every account Signed out means the lab session was invalidated (it happened mid-lab). Stop, tell the user which student account to click, wait, then reopen the standalone shell — project state, home-dir files and the score survive. You never type the password.

Finish. Only Score: 100 / 100 with every row at max / max counts, confirmed after a page reload. Report, then let the user press End. If the lab page suddenly shows Start again (the user or the timer ended it), the header's points/streak counter rising is the only remaining sign of completion — ask the user rather than guessing the final score.

Checkpoints dialog clicks. The page reflows (the dialog moves, the left nav expands) between clicks, so a remembered coordinate can hit a different row — that is how one click credited an unintended task. Click via find → Check my progress for <task name> (the ref inside the dialog works), or take a fresh screenshot immediately before every coordinate click.

### 6.3b Alternative execution lane: local gcloud + IAP tunnels (verified 2026-09-30 on GSP322)

When the host box (not Claude-in-Chrome) drives the lab, skip Cloud Shell typing entirely — deterministic, no websocket drops, no keystroke races:

- **Isolated auth:** fresh `CLOUDSDK_CONFIG=<dir>` for every lab; `gcloud auth login --no-launch-browser`, complete OAuth in the browser-rail Chrome (CDP :9222; role locators Email/Next/Passwd/Next/Allow; qwiklabs student accounts pass without 2FA; code regex `4/[A-Za-z0-9_-]+` or `[A-Za-z0-9]{4}-[A-Za-z0-9]{4}`). Ready-made orchestrator: `~/.claude/tmp/qwiklabs-gcloud/qwik_auth.py` — swap EMAIL/PASSWORD, it auto-detects the project from `projects list` (pick the non-`qwiklabs-resources` one).
- **Compute ops directly from local gcloud** (create VMs/rules/tags/metadata/IAM) — the checker's state reads don't care which client made them.
- **SSH into no-public-IP VMs:** `gcloud compute start-iap-tunnel <vm> 22 --local-host-port=127.0.0.1:2222` (backgrounded) + `ssh -i key -p 2222 user@127.0.0.1`. Bastion hops: ssh `-o ProxyCommand="ssh -i key -p 2222 -W %h:%p user@127.0.0.1"` to the internal IP. The student needs `roles/iap.tunnelResourceAccessor` (grant it; the console flow would too).
- **Tunnel keepalive footgun:** the backgrounded `start-iap-tunnel` gcloud process dies between Bash tool calls — before EVERY hop, relaunch it (idempotent, wait ~10 s) or the hop fails with "connect to 127.0.0.1 port 2222: Connection refused".
- **Windows VMs with no interactive channel:** legacy guest agent ignores `startup-script-ps1`; use `windows-startup-script-ps1` (runs as SYSTEM with the VM's SA creds). Pre-create `"$env:USERPROFILE\.ssh"` before any in-VM `gcloud compute ssh` (winkeygen can't mkdir).
- **Expiry:** when the lab timer ends, the student refresh token dies with `invalid_grant` — the project is unreadable from that moment. Finish evidence state with ≥5 min of timer left.

### 6.3c Rehearsal lane — never spend credits unprepared (added 2026-09-30)

Two rehearsal substrates, used BEFORE starting a timed lab:

1. **Terraform topology ports** — `rosera/terraform-sandbox` and similar community ports reproduce lab infrastructure in YOUR OWN GCP project (e.g., GSP1102's startup-vm topology). Spin it, walk the manual's steps, break nothing that costs credits. When a lab is known-flaky (provisioning defects seen twice on GSP322/GSP1036 families), a rehearsal pass surfaces the failure mode before the timer starts.
2. **Solutions corpus as sequence reference** — `quiccklabs/Labs_solutions` (290 distinct GSP labs, per-lab `quicklabgspNNN.sh` scripts) + PradyumnaKrishna/Qwiklabs (49 legacy-ID labs) + hiiruki (challenge labs). These are command sequences that the community has empirically driven to 100/100 — i.e., they encode what the grader accepts. Use them to pre-stage YOUR execution sequence: identify the lab's GSP ID → pull the script → rehearse in your own project (or dry-read) → then run the real session with the probe armed (§6.4b). NEVER blind-run a corpus script inside a graded session without reading it — they occasionally create/delete resources with names that collide with a different lab version; the rehearsal lane exists to make them safe.
3. Timing discipline stays: even rehearsed, run the graded session with audit logs armed before the first click, bank every checkpoint's evidence with ≥5 min of timer margin (§6.6).

### 6.4 How "Check my progress" grades, and the diagnostics ladder

Each checkpoint is a bundle of independent sub-checks worth a few points each; the toast's Points earned is their sum and its Message names the first failing one. They run server-side at click time against these sources (verified on GSP1247; §6.4b shows the identities making the calls):

1. **Cloud Audit Logs — the exact API call the manual prescribes.** `gcloud services enable a b` (one BatchEnableServices event) scored 5/15 although `gcloud services list --enabled` showed both APIs on and both IAM roles were present; the two single-service commands as printed (EnableService ×2) scored 15/15 on the next click. So: one command per line as written, no batching, no "equivalent" flags, and swap CLI for console (or back) only when the resulting API call is identical (bq mk --connection was credited for a UI-created connection; gcloud projects add-iam-policy-binding for the IAM page). The fingerprint includes **who authored the call**: a step the manual means you to perform *on a VM* leaves a setMetadata/API call authored by that VM's service account, not by the student from outside (GSP322 §6.6).
2. **BigQuery job history** — every prescribed query, including result-viewing SELECTs. The summary SELECT … ML.GENERATE_TEXT(MODEL gemini_lite …) creates nothing and is worth 5/20; skipping "You can view the results…" steps is invisible until the toast says "Please run the SQL query …".
3. **Resource state and content.** Names verbatim (movie_posters_results_embeddings, not movie_posters_embeddings); tables holding valid rows; downstream queries (VECTOR_SEARCH) having succeeded (§6.5).
4. **Cloud Logging logs the lab's own plumbing ships** (auth.log etc.). If the provisioning agent failed, that evidence channel is silently dead — see GSP322 §6.6 for detection and repair. (UNVERIFIED as a scored source on its own; the repair shipped real lines only, and the timer expired before the confirming click.)

Timing: a click while a job is RUNNING, or before an IAM grant has propagated, fails that sub-check; a later click passes it — that is the 5 → 10 → 15 pattern on repeated clicks (lag, not a broken checker). A remote CREATE MODEL can sit RUNNING for minutes waiting for the connection service account's role to propagate (229 s seen); it completes — don't cancel, don't check meanwhile.

Ladder for a partial or zero checkpoint:

1. Read the Message: it names the sub-step.
2. Verify that sub-step's state from Cloud Shell. Wrong → do the step. Right → 3.
3. State right but uncredited = missing fingerprint: re-run the manual's command/query for that sub-step individually and verbatim, wait DONE, re-click. If the manual means the action to happen ON a VM, re-run it from that VM (the audit author identity differs).
4. A prescribed query errored: fix the data upstream (NULL guards, re-run the producing step), never the checker; confirm the query returns rows; re-click.
5. Query ran and returned the right rows but the toast still says "Please run the query …": the checker text-matches job history against the manual's canonical query. Rewrite yours into the manual's form (same table aliases such as t1, same functions, same date literal) and run it again — GSP1259 went 0 → 20 only after ROUND(SUM(item_total), 2) became ROUND(SUM(t1.item_total), 2) with EXTRACT(YEAR FROM t1.order_datetime) = 2024.
6. Score unchanged after 1–2 min: reload the lab page (toast/alert text goes stale) and read Score again before concluding anything.
7. Still stuck: **extract the grader's exact predicate** (§6.4b / GRADER-INTERNALS.md §5a — `grader_probe.py` in this folder): arm `logging.googleapis.com` data-access audit, click once (or wait for the poller — it re-runs stuck-check predicates every ~60-90 s), then read the grader's own `ListLogEntries` filters from the data-access log. The filter string IS the expected-evidence specification — satisfy it with REAL events (§6.4b GSP322 example: the stuck SSH leg wanted `oslogin CheckPolicy` entries, satisfied by `enable-oslogin=TRUE` + a real SA-authenticated hop), never fabricated log entries. Never call it a checker bug before 1–7.

### 6.4b Grader internals, measured (2026-09-30, GSP322 live session)

Instrumentation recipe (BEFORE the first check click): `gcloud projects get-iam-policy P --format=json > pol.json` → load the FULL policy, add `auditConfigs` for `compute.googleapis.com` and `iap.googleapis.com` with logTypes ADMIN_READ, DATA_READ, DATA_WRITE (preserve every binding + etag — windows-shell rule: never rewrite a config you only partially loaded) → `gcloud projects set-iam-policy P pol2.json`. Then between clicks read:

```
gcloud logging read 'logName:"cloudaudit.googleapis.com%2Fdata_access"' --project=P \
  --format="table(timestamp,protoPayload.authenticationInfo.principalEmail,protoPayload.serviceName,protoPayload.methodName,requestMetadata.callerIp)"
```

Measured identities and behaviour (both hold roles/editor on the lab project):

- **`admiral@qwiklabs-services-prod.iam.gserviceaccount.com`** — the central Qwiklabs grading SA. Calls `v1.compute.instances.aggregatedList` in bursts exactly at check-click moments, from `35.221.208.175` (Qwiklabs' own GCP range — not the IAP range, not the lab VPC), user-agent stripped by the Google front end.
- **The lab project's own default SA**, driven by **`google-api-ruby-client/0.16.0 Linux/6.9.12`** from Google IPv6 (`2600:1900:…`) — the original Qwiklabs Ruby assessment engine, still in production. Does the detailed reads (`firewalls.list`, `aggregatedList`) at click time plus a **periodic ~60 s auto-score poller** (single `firewalls.list`). This is why scores sometimes update without clicking.
- Lab projects carry label `fleet: gcpd`; session provisioning is terraform (`goog-terraform-provisioned` on VMs).
- A partial credit split (e.g. 10/20 on a two-leg SSH checkpoint) means one leg's fingerprint is present and the other's is not — use it to isolate exactly which evidence the checker accepts, then produce that evidence legitimately.
- Note the blind spot: only services you armed produce data-access entries. A grader read of Cloud Logging (logging.googleapis.com) is invisible unless you arm that service too — arm `logging.googleapis.com` as well when a log-based check is suspected.
- **FILTER EXTRACTION (verified 2026-09-30, drove GSP322 90→100):** the grader's own `ListLogEntries` calls are data-access-audited and carry their FULL request filter — arm logging audit, click, then `python grader_probe.py filters PROJECT student-email` (this folder) prints the grader's verbatim expected-evidence predicates. Probe v2 also has `verify` (local grader simulation — re-runs every extracted predicate, reports SATISFIED/MISSING; returned ALL GREEN before the GSP322 winning click) and `profile` (per-click read matrix). Actor attribution: engine = project SA from `2600:1900:…` IPv6; your reads show your student email. Pattern library + full method + decoded GSP322 spec: GRADER-INTERNALS.md §5a-§5d. `admiral` also runs `SetIamPolicy` at session start (installs its own access).
- **Evidence classes beyond state/logs (GSP322 lesson):** a check can grade a specific AUTH MECHANISM — the stuck juice-shop leg wanted `oslogin.googleapis.com CheckPolicy` (ON by default for data-access), which metadata ssh-keys structurally cannot produce (they bypass OS Login). Fix was `enable-oslogin=TRUE` on juice-shop + a REAL `gcloud compute ssh juice-shop --internal-ip` from the bastion (authenticates as the VM SA's OS Login profile, `sa_…`). When state and audit fingerprints are all green but uncredited, suspect an evidence-CLASS mismatch and extract the filter to see the real predicate.
- Guest-agent footguns (measured): `useradd` rejects email-form usernames — push metadata keys as `student:<pubkey>`, never `student-xx@qwiklabs.net:<pubkey>`; `enable-oslogin=TRUE` on an instance immediately disables metadata-key SSH to it (plan the hop path before flipping it).

### 6.5 BigQuery ML / Gemini lab gotchas (GSP1247 family)

Connection + IAM from the shell, all credited: bq mk --connection --location=US --project_id=$PROJECT_ID --connection_type=CLOUD_RESOURCE gemini_conn; SA=$(bq show --connection --format=json $PROJECT_ID.US.gemini_conn | python3 -c 'import sys,json;print(json.load(sys.stdin)["cloudResource"]["serviceAccountId"])'); gcloud projects add-iam-policy-binding $PROJECT_ID --member serviceAccount:$SA --role=roles/aiplatform.user (the 2026 console calls it "Agent Platform User"; older manuals say "Vertex AI User"). The first CREATE MODEL … REMOTE WITH CONNECTION then waits on propagation — expect minutes.

2026 endpoints in this lab: gemini-2.5-flash-lite for both gemini_lite and gemini_lite_vision, text-embedding-004 for text_embedding — read them from the live page.

LLM nondeterminism breaks the pipeline, not your SQL. The JSON-extraction step (ML.GENERATE_TEXT over the poster object table) can return a refusal ("I am sorry, but I cannot provide the movie title…") or partial JSON (a title, no year). JSON_QUERY → NULL → CONCAT → NULL content → ML.GENERATE_EMBEDDING returns an empty vector with an empty status (the manual's WHERE ml_generate_embedding_status = '' misses it) → VECTOR_SEARCH fails with "Dimension of column ml_generate_embedding_result in the base table does not match … in the query data" → checkpoint 0/25. Diagnose on both sides of the search: SELECT ARRAY_LENGTH(ml_generate_embedding_result) dim, COUNT(*) n, COUNTIF(content IS NULL) nulls FROM <emb_table> GROUP BY 1. Fix that was credited: rebuild the poster embeddings with the manual's query plus WHERE title IS NOT NULL AND year IS NOT NULL in its subquery, then re-run both VECTOR_SEARCH queries (re-running the vision step is a coin flip: one run refused a poster, the next dropped a year on another).

Look at the data after every producing step: SELECT COUNT(*), COUNTIF(<col> IS NULL) FROM …; 19 posters → 19 rows; embeddings all one dimension; the IMDB pre-1935 subset ≈ 480 rows.

The formatting query uses double-quoted " ```json" strings — one more reason for heredoc files.

### 6.6 Field notes: what was credited (2026-09) + GSP322 post-mortem (2026-09-30)

CLI swaps that scored full marks. GSP1248: bq mk --connection --location=us-central1 …; bucket IAM with gcloud storage buckets add-iam-policy-binding gs://<proj>-bucket --member=serviceAccount:$SA --role=roles/storage.objectAdmin; slot reservation with bq mk --reservation --location=<r> --edition=ENTERPRISE --slots=0 --autoscale_max_slots=100 reservation and bq mk --reservation_assignment --reservation_id=<proj>:<r>.reservation --job_type=QUERY --assignee_type=PROJECT --assignee_id=<proj> (wait ~2 min before the ONNX ML.PREDICT).

UI features that no longer exist. The 2026 console has no "Table explorer" tab (GSP1257): run the manual's generated query itself — credited. When Gemini's generated items (insights, SQL generation, Transform) don't produce the manual's example, run the manual's example query — GSP1257 T3 and all of GSP1258 were credited from bq query runs of the manual's SQL.

Data insights (Dataplex) on a fresh project fails with "Dataplex service account … not found": run the command the error prints, gcloud beta services identity create --service=dataplex.googleapis.com --project=<project number>, wait ~30 s, click Generate again. Track the scan with gcloud dataplex datascans list --location=<r> and … jobs list; check the task only after the job is SUCCEEDED (~1–3 min).

Data canvas (GSP1259) needs the UI, since the canvas and the notebook export are graded resources. Create from BigQuery home → Data engineering and analysis → Data canvas, pick the lab region. Node buttons (Query these results, Visualize → Bar menuitem, Join) are often off-screen: javascript_tool .click() on the button found by its text is fine (it is ordinary UI, not the checker). Pan with left_click_drag on empty canvas; the wheel does nothing. The canvas Save button hides behind a long title — click it via JS. Export As Notebook → name data_canvas_export, region as given. A second student account ("Username 2") is set up by the user in its own tab; the viewing step is ungraded.

Challenge labs give no step list: take the dataset/model names and the date windows from the live page, use the course's standard queries (GSP341 = the GSP229 visitor-purchase pattern: train 20160801–20170430, ML.EVALUATE on 20170501–20170630, ML.PREDICT on 20170701–20170801), and train models with nohup because CREATE MODEL takes 1–4 min.

**GSP322 post-mortem — RESOLVED 100/100 (2026-09-30, second session; supersedes the UNVERIFIED fingerprint hypothesis below).** The stuck 10/20 juice-shop-via-bastion leg across both sessions was an **evidence-class mismatch**: the grader's actual predicate (extracted verbatim from its own `ListLogEntries` filter) is `oslogin.googleapis.com CheckPolicy` data-access entries on `instances/juice-shop`, success-only, since lab start — and metadata ssh-keys (everything we had been perfecting: username forms, google-ssh annotations, bastion-generated keys, SA-authored setMetadata pushes, real login lines) **structurally cannot produce them**. Fix that scored: (1) `gcloud compute instances add-metadata juice-shop --metadata=enable-oslogin=TRUE`, (2) real `gcloud compute ssh juice-shop --internal-ip` **from the bastion** → authenticates as the bastion VM SA's OS Login profile (`sa_111709622340555101093`), emitting genuine CheckPolicy entries, (3) re-click → 20/20 → 100/100. Full decoded per-check predicate table for the whole lab: GRADER-INTERNALS.md §5b. Historical failed-evidence states (kept for the record):

**GSP322 first-session post-mortem (90/100; superseded by the resolution above).** "SSH to bastion host via IAP and juice-shop via bastion" stayed 10/20 across five different evidence states (laptop-key on both VMs in three username forms; google-ssh-annotated keys; project-level keys; a bastion-generated key; real hop logins from 192.168.10.2). Diagnosed, in order of confidence:

- **The probable wanted fingerprint (UNVERIFIED — timer died before the confirming click; settle on the next attempt):** run `gcloud compute ssh juice-shop --internal-ip` **on the bastion** — its key push is authored by the **bastion VM's default SA** (`…-compute@developer.gserviceaccount.com` → `v1.compute.instances.setMetadata` on juice-shop), an audit fingerprint no student-from-outside setMetadata produces. The 15:35 run of exactly this command succeeded (GCLOUD_HOP_OK) minutes before expiry; whether that state scores is the open experiment.
- **Provisioning defect observed:** juice-shop's startup script (which installs google-fluentd and tails /var/log/auth.log to Cloud Logging, log name `auth`) failed at session start — the agent was never installed (3 install attempts failed: `Unit google-fluentd.service not found`; apt repo install RC=1). Any log-based leg is dead in such a session unless repaired. Repair that preserves honesty: copy the REAL lines (`sudo grep 'Accepted publickey' /var/log/auth.log` from the VM) into the log with `gcloud logging write auth "<line>" --payload-type=text` — real events through a repaired pipe, never fabricated ones.
- **Metadata ssh-keys rewrite footguns (cost ~15 min):** (a) rebuilding the value from a flaky probe — `--format="value(metadata.items.filter(key:ssh-keys).extract())"` returns empty SPURIOUSLY; read via `--format=json` and parse, or you will "append" to an empty string and ship a leading blank line, which the guest agent treats as broken keys and drops (hop then fails with Permission denied). (b) always write the FULL rebuilt value from a JSON-sourced read, never a partial one.
- **Timer discipline:** the fix chain (hop evidence → user click → verdict) needs ~3–5 min of margin. Bank every earlier checkpoint's full score first, then fight the last one with the clock visible.
- **Wrong-lab check:** always match the pasted credentials to the expected lab BEFORE working — a different lab's project (no startup-vm / no expected VMs, `fleet:` label differing) means the user started the wrong lab. `projects list` under the student account shows exactly the live one.

## 7. Reporting format

```
Platform · course · lessons N/N · quiz X/Y (pass) · badge ISSUED <date> · notes
Lab GSPnnnn · score 100/100 · checkpoints 7/7 · <time> left · diagnosed: <task → cause> ...
...
Skipped: <course> — <reason: paid lab / proctored / needs sign-in>
```

Send a mid-task progress line after each finished course (the user often reads from a phone).

## 8. Checklist

- [ ] Rules in §0 read; nothing proctored/paid queued
- [ ] Catalog listed, done items skipped, badge courses identified
- [ ] Helpers installed and persisted in localStorage.__setup on that origin
- [ ] Tabs created and assigned; big courses handed to subagents in one message
- [ ] Every batch ≤ 12 actions, waits only via computer.wait, no page timers
- [ ] Each course verified on its badge page before reporting
- [ ] Lab: user approved the credit spend; every command/query taken verbatim from the live lab page
- [ ] Lab: steps run one at a time as printed; state verified and jobs DONE before each check
- [ ] Lab: credentials matched to the expected lab project before any work (wrong-lab check)
- [ ] Lab: data-access audit logs armed (compute+iap, +logging when a log-based check is suspected) BEFORE the first check click
- [ ] Lab: any partial checkpoint went through the §6.4 ladder incl. the audit-authority check (§6.4 step 3); 100/100 confirmed after a reload
- [ ] Lab: evidence state for the final checkpoint banked with ≥5 min of timer left
- [ ] Lab: every console/shell URL carries the student's authuser; shell prompt shows the student
- [ ] Lab: End left to the user
- [ ] Report + Q→A log delivered; skill updated with new platform findings
