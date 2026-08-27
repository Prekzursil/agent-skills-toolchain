# UI Prototype

Generate **several radically different UI variations** behind one switcher. The user flips between variants in the running app, picks one (or steals bits from each), then throws the rest away.

If the question is about logic/state rather than what something looks like — wrong branch. Use [LOGIC.md](LOGIC.md).

## When this is the right shape

- "What should this page look like?"
- "I want to see a few options for this dashboard before committing."
- "Try a different layout for the settings screen."
- Any time the user would otherwise spend a day picking between three vague mockups in their head.

## Two sub-shapes — strongly prefer sub-shape A

A UI prototype is far easier to judge when it is **butting up against the rest of the app** — real header, real sidebar, real data, real density. A throwaway route on its own is a vacuum: every variant looks fine in isolation. Default to A whenever there is a plausible existing host.

### Sub-shape A — adjustment to an existing page (preferred)

The host already exists. Variants render **in the same place**, gated by a variant key. Existing data fetching, params, and auth stay — only the rendering swaps. If the thing being prototyped does not yet have a page but *would naturally live inside one* (a new dashboard section, a new settings card, a new step in an existing flow) — still sub-shape A. Mount the variants inside the host.

### Sub-shape B — a new page (last resort)

Only when the thing genuinely has no existing page to live inside. Create a **throwaway route/screen** following the project's existing convention; name it so it is obviously a prototype (include `prototype` in the path/filename). Same variant-key pattern. Sanity-check first: is there really no existing surface to embed in? An empty route hides design problems a populated one would expose.

## How the switcher works per stack

- **Web (React/Next/Vite/etc.)** — gate on a `?variant=` URL search param; a floating bottom bar cycles variants and updates the param via the framework's router (`router.replace` / `navigate`) so it is shareable and reload-stable. `<-` / `->` keys also cycle (don't intercept when an input/textarea/contenteditable is focused).
- **Electron renderer** — same `?variant=` (or `#variant=`) in the renderer; the floating bar is identical. If the renderer is not routed, key off a hash or a small dev-only state value.
- **Native desktop (PySide6/WinUI/etc.)** — no URL; expose the variant key as a dev-only combo box or a hotkey in the app shell that swaps the rendered panel. Same idea: one shell, N swappable renderings.

In all stacks the switcher must be **visually distinct** from the page (high-contrast pill, shadow) so it is obviously not part of the design being evaluated, and **hidden in production builds** (`process.env.NODE_ENV !== 'production'` or equivalent) so a stray prototype merge can't ship it.

## Process

### 1. State the question and pick N

Default to **3 variants** (cap at 5 — more stops being radically different and starts being noise). Write the plan in one line in the prototype's location or a top-of-file comment, e.g. "Three variants of the settings page, switchable via `?variant=`, on the existing `/settings` route."

### 2. Generate radically different variants

Each variant must be **structurally different** — different layout, information hierarchy, primary affordance, not just colours. Three slightly-tweaked card grids is wallpaper, not a prototype. Hold each to the page's purpose and data, and to the project's component library / styling system. Give each a clear exported name (`VariantA`, `VariantB`, `VariantC`). If two come out too similar, redo one with explicit "do not use a card grid" guidance.

### 3. Wire them together

One switcher on the surface picks the active variant from the variant key; for sub-shape A keep all existing data fetching above the switcher so only the rendered subtree changes per variant.

### 4. Build the floating switcher (web/Electron)

A fixed bar at bottom-centre: left arrow (previous, wraps), variant label (`B — Sidebar layout`), right arrow (next, wraps). Arrows update the variant key; keyboard arrows cycle too. Put it in a single shared component both sub-shapes reuse.

### 5. Judge with ui-audit (workspace-native)

Don't pick by eyeball alone. Run the **`ui-audit`** skill against the running app once per variant to get objective numbers (contrast, spacing, tap targets, dead buttons, visual regression) plus the Track-B design VERDICT reasoned against a Refactoring-UI / Material / HIG / Nielsen rubric. Then surface the variant URLs/keys to the user with those numbers attached — "which looks best" becomes measured + reasoned, and the usual real answer ("the header from B with the sidebar from C") is easier to spot.

### 6. Capture the answer and clean up

Once a variant has won, record which one and why in the event ledger (`python ~/.claude/hooks/event-ledger/note.py --kind decision "..."`), and `mcp__basic-memory__write_note` if it is worth keeping across projects. If AFK and undecided, leave a `PROTOTYPE-Q:` placeholder. Then:

- **Sub-shape A** — delete the losing variants and the switcher; fold the winner into the existing page.
- **Sub-shape B** — promote the winner to a real route/screen; delete the throwaway one and the switcher.

Don't leave variant components or the switcher lying around — they rot fast and confuse the next reader.

## Anti-patterns

- **Variants that differ only in colour or copy.** That is a tweak, not a prototype. Real variants disagree about structure.
- **Sharing too much code between variants.** A shared `<Header>` is fine; a shared `<Layout>` defeats the point — each variant should be free to throw out the layout.
- **Wiring variants to real mutations.** Read-only prototypes are fine; point a variant that needs to mutate at a stub. The question is "what should this look like", not "does the backend work".
- **Promoting the prototype directly to production.** Variant code was written under prototype constraints (no tests, minimal error handling). Rewrite it properly when folding it in.
