# Figma Setup — Plugins, MCP/Tools, and the Design-Tokens Pipeline

**Synthesized:** 2026-06-30 from the 9 design-research lens digests in this folder.
**For:** code-first power-user (Reframe, momentstudio, WebCoder, bilbo) wiring Figma into the TCR Loop (see `DESIGN-WORKFLOW.md`).
**Confidence:** 🟢 proven/primary · 🟡 emerging-but-real · 🔴 vendor self-claim.

---

## 1. Recommended Figma plugins — ranked (install in this order)

### The starter stack (the "is-it-good-UX-and-why" + a11y + tokens core)

| Rank | Plugin | Job in the loop (TCR gate) | Cost | Conf. |
|---|---|---|---|---|
| **1** | **UX-Ray by Baymard** | **G1 AUDIT** — scans a frame → severity-rated UX issues, each linked to a research-backed guideline + fix rationale. Built on Baymard's 700+ guidelines / 200K+ research hrs; rates ~209 UX parameters. **Ecommerce-centric** but checkout/form/search/listing guidance generalizes. The most *evidence-grounded* AI auditor. | Free install; deeper guidelines = Baymard sub | 🟢 capability / 🔴 the "95% vs human" figure is Baymard's own |
| **2** | **Stark — Contrast & Accessibility AI Checker** | **G1 a11y backbone** — WCAG 2.1/2.2 AA/AAA contrast, Vision Simulator (8 color-blindness types), Focus Order, Alt-Text, Touch-Target sizing, Auto-Scan & Fix. | Free tier (contrast + vision sim); **Pro $99/yr/user** (focus order, alt-text, touch targets) | 🟢 |
| **3** | **axe for Designers (Deque)** | **G1 free second a11y opinion** — auto-scan (contrast/touch/headings) + **auto-annotations for 31 categories with code snippets** that survive into G6 handoff. Run *alongside* Stark — redundancy is a feature. | **Free** | 🟢 |
| **4** | **Design Lint** (destefanis, OSS) | **G1/G5** — catches missing/forked styles + off-token inconsistencies before review; the de-facto free linter. Don't stack 4 linters (UX-Ray/onBeacon also lint). | **Free / OSS** | 🟢 |
| **5** | **Tokens Studio for Figma** | **G5/G6 token spine** — full token system (color/space/type/radius/shadow), W3C DTCG format, references/aliases, themes; **Pro adds Git branching** (GitHub/GitLab/Azure/Bitbucket) → bidirectional design↔code source-of-truth. | Free Starter; Pro paid (Git) | 🟢 |

### Add as needed

| Plugin | Job | Cost | Conf. |
|---|---|---|---|
| **onBeacon / "AI Design Reviewer"** | G3 *fast first-pass* critique (GPT-5 + Claude, 130+ behavioral principles + WCAG lint). **Junior reviewer, not the verdict.** | Freemium | 🟡/🔴 on "expert-level" |
| **ComponentQA** / **Design System Auditor** | G2 NORMALIZE — detached-instance / rogue-hex detection; library hygiene before review. | Freemium | 🟡 |
| **EightShapes Specs** | G6 — auto spacing/anatomy annotations for handoff. | Free | 🟡 |
| **Contrast (WillowTree)** | Extra fast pass/fail contrast incl. gradients/opacity. | Free/Freemium | 🟡 |

### Transpose plugins (code → Figma) — pick by altitude (the key decision)

| Tool | Direction | Granularity | Drift | Use for |
|---|---|---|---|---|
| **story.to.design** | Storybook/code → **real Figma components + variants** | component-level | 🟢 Low | **the system loop** — what lands in Figma *is* your component graph |
| **Figma MCP `generate_figma_design`** | live UI (incl. **localhost**) → semantic editable frames | screen-level | 🟡 Medium | live/auth'd app capture (G2) |
| **html.to.design / html2design** | web/app → flat editable layers (DOM-accurate; works on localhost/private) | flat | 🔴 High | **audit/benchmark record only** — *not* the system loop |
| **image.to.design / Codia** (screenshot→design) | image → AI-guessed layers | lossy | 🔴 High | only when you have **no DOM** (competitor native app, video frame) |

> **Rule:** DOM-accurate ≫ screenshot for fidelity. For your *own* apps always prefer `story.to.design` (system loop) or `generate_figma_design` (live). Screenshot/vision tools hallucinate structure.

**Don't over-stack:** one UX auditor (UX-Ray) + two a11y (Stark + axe) + one linter (Design Lint) + one token system (Tokens Studio). The AI-reviewer category is exploding (UXGuard, "AI UX Audit", FigmaLint) — all useful, all need a human revert-gate; don't auto-trust their scores.

---

## 2. Figma MCP / tools setup — how an agent reads & edits a file

### 2.1 The mental model (3 surfaces)
- **Read** can come from any surface; **write always bottoms out in the Plugin API.** The MCP server is the agent-friendly façade exposing both.
- **REST API is READ-ONLY for file content** (returns the node tree as JSON + image renders; writes only comments/webhooks/dev-resources, and variables on Enterprise). Use REST for **bulk reads / CI exports / token+analytics sync** — *not* the agent's edit step.
- **Plugin API** (`figma.*`, runs inside Figma's sandbox) is the only path to arbitrary file edits — the MCP `use_figma` tool injects/executes Plugin-API JS for you.

### 2.2 Install + auth (recommended)
```bash
# Bundles MCP config + the four agent skills (figma-use, figma-generate-design,
# figma-use-figjam, figma-code-connect):
claude plugin install figma@claude-plugins-official
# select the "figma" server → Enter to open the auth page → Allow (OAuth)
```
Alternatives:
```bash
# Remote server directly (all seats/plans; where the write tools live):
claude mcp add --transport http figma https://mcp.figma.com/mcp
# Desktop server (needs Figma desktop + Dev/Full seat; selection-based, read-leaning):
#   Figma desktop → Dev Mode (Shift+D) → Inspect → "Enable desktop MCP server"
claude mcp add --transport http figma-desktop http://127.0.0.1:3845/mcp
```
**Remote vs Desktop:** use **Remote** as default — available on all seats/plans and where most **write** tools live (`use_figma`, `generate_figma_design`, `create_new_file`, `upload_assets`, `get_libraries`, `whoami` are remote-only). Desktop is local/low-latency but does not expose the full write surface.

**Selecting a target node:** in Figma select a frame → **Copy as → Copy link to selection** → paste the URL into your prompt; the MCP server resolves the node. (`figma-implement-design` parses `node-id` from `/design/:fileKey/:fileName?node-id=1-2`.)

### 2.3 The tool surface (what the agent calls)
**READ (safe, non-mutating):**
- `get_design_context` — structured **React + Tailwind** of the selection (the core design→code pull; successor to `get_code`).
- `get_variable_defs` — variables & styles (color/spacing/type) → reference your **tokens** directly.
- `get_screenshot` — PNG render (visual ground-truth; feeds the critique/diff gate).
- `get_metadata` — sparse **XML** outline (layer IDs/names/types/x/y/w/h) → **"scan first, then zoom in"** to beat context limits on big screens.
- `get_code_connect_map` / `get_code_connect_suggestions` / `get_context_for_code_connect` — existing + suggested node→component mappings.
- `get_libraries` / `search_design_system` — discover/search connected design-system libraries.
- `download_assets`, `get_figjam`, shader tools, `whoami`.

**WRITE / canvas (mutating):**
- `use_figma` — **the general-purpose write engine** (executes Plugin-API JS: create/edit/delete nodes, variables, components, auto-layout). Also for JS-execution reads ("list all pages/components").
- `generate_figma_design` — **the "Code to Canvas" primitive** — turns live/staging/**localhost** UI into fully editable Figma frames (render-mediated: spins your dev server, serializes the rendered DOM; single-use capture IDs).
- `create_new_file`, `upload_assets`, `generate_diagram` (Mermaid→FigJam).
- `add_code_connect_map` / `send_code_connect_mappings` — write node↔code-component bindings.

### 2.4 Rate limits & cost (budget for this)
> ⚠️ **Corrected 2026-07-03** — rate limits track **SEAT type, not plan**. The earlier "Starter = ~6 calls/month" was wrong (it conflated the free *plan* with the View/Collab *seat*).
- **View / Collab seats: ~6 tool calls/month** (ANY plan — effectively a toy).
- **Dev / Full seats: real per-minute throughput even on the FREE tier** — Starter **200/day, 10/min**; Professional 15/min; Organization 600/day, 20/min. ([official table](https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/))
- ⭐ **Figma for Education (free) grants a FULL seat** → full MCP read throughput at **no cost** for verified students/educators. Verified 2026-07-03 on a `tier:student` Full seat: `whoami` reports `seat:Full`, and `get_design_context` returns the full source tree with no throttle. So a paid seat is NOT required for real MCP throughput if you qualify for Education.
- **Writes are rate-limit-EXEMPT** — `generate_figma_design`, `use_figma`, `add_code_connect_map`, `whoami` never count against the limit (**free during beta**, slated to become **usage-based paid**).
- **Known bug:** seat/plan detection can lag a seat *change* (forum reports of "stuck at 6/month despite a new Dev seat") — re-auth the MCP if throughput doesn't match your seat.

### 2.5 Community read-only fallback
**GLips / Framelink `figma-context-mcp`** — free, any Figma account, **read-only** (`get_figma_data`, `download_figma_images`). Good for cheap read/audit without a Dev seat, but **cannot transpose code→canvas** — you lose G2.
> **When it's worth keeping (2026-07-03):** with a **Full seat** (including free **Figma for Education**), the official MCP already gives full read throughput + writes + `download_assets`, so this fallback is **optional/redundant** for interactive work. Keep it ONLY for **truly-headless** Figma reads (cron / gateway / detached CLI) where the official **OAuth** server is absent but a **PAT** (`FIGMA_ACCESS_TOKEN`) still works — otherwise prune it for leanness.

### 2.6 Code Connect — the single biggest fidelity lever (invest early)
Maps a Figma component → its **real repo component**, so Dev Mode / MCP responses emit *your* `<Button>`/`<Card>`, not re-derived markup. Two setups: **UI** (inside Figma, language-agnostic, GitHub optional) and **CLI** (`@figma/code-connect`); supports one-to-many (React + SwiftUI + Compose + Vue). **Without it, blogs report ~85–90% styling inaccuracy / generic hardcoded JSX** (single-blog metric, directionally right). **Code-Connect-your-kit once** converts every future G6 from "generate fresh divs" into "reuse my components."

---

## 3. The design-tokens pipeline (the only lossless round-trip channel)

**Canonical pipeline:**
```
Figma Variables → Tokens Studio → JSON (Git = source of truth)
  → @tokens-studio/sd-transforms → Style Dictionary
  → platform outputs (CSS vars / SCSS / JS / Tailwind / iOS / Android)
```
- **Tokens Studio** = the Figma bridge: create tokens, bind to Figma styles/variables, **push/pull to GitHub/GitLab/Bitbucket/Azure** (genuinely two-way).
- **`@tokens-studio/sd-transforms`** (npm) = the required glue that prepares Tokens-Studio JSON for Style Dictionary.
- **Style Dictionary** = the transformer: one JSON token tree → every platform output.
- **Git-as-truth variant:** Figma ships a **GitHub Action** that auto-syncs Figma Variables → CSS tokens (designer edits a variable → Action opens a **PR** → devs review/merge). Both sides stay native; the manual copy step is gone.
- **W3C DTCG spec hit v1.0 (Oct 28 2025)** — the first stable standardized token format, with reference impls in Style Dictionary, Tokens Studio, Terrazzo. *This is why the interchange is now stable.*

**Why it's the spine of the loop:** pixels and components are lossy across the round-trip; **tokens are not** — both Figma and code dereference the *same* JSON, so a token change in the "discuss" gate is provably non-lossy in both directions. It's also the cleanest **revert** surface (token diffs are tiny + reviewable). Encode design decisions as **token changes through a PR**, not one-off pixel tweaks.

**Tokens-first setup order (do once, pays off across all 4 apps):**
1. Establish the Figma **Variables** token set per app **before** capture (color HSL ramps, ~25%-step spacing scale `4·8·12·16·24·32·48·64`, type scale `12·14·16·18·20·24·30·36·48·64`, 5-level elevation).
2. Stand up **Tokens Studio ⇄ Git ⇄ Style Dictionary** once.
3. Install the **Figma MCP server** + **Code-Connect your shared kit** once.
4. Assign a **per-app sync owner** — "sync is a practice, not a handoff"; un-governed systems decay into "47 sources of truth."

**Direction-of-truth rule:** lead with **design** for *visual/token* decisions (don't let code dictate the system); lead with **code** for *behavior/state*. The token pipeline makes Figma variables the *technical* source of truth, not just aspirational.

---

*Sources: `figma-plugins.md`, `figma-mcp-tools.md`, `code-figma-roundtrip.md`, `design-systems-sota.md`, `wildcard.md`, `ai-design-tools.md` in this folder — grounded in Figma first-party docs (MCP server guide, Code Connect, Dev Mode), Baymard/UX-Ray, Stark/axe/Deque, Tokens Studio docs, and the W3C DTCG v1.0 announcement.*
