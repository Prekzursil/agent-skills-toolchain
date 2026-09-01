# Perplexity Computer Workflows: Source Artifact Cross-Check & Structural Analysis

**Date:** 2026-08-29  
**Target Scope:** Authoritative 40-Workflow Suite  
**Output Destination:** `C:\Users\Prekzursil\.agents\PERPLEXITY-WORKFLOWS-SOURCE-CROSSCHECK_2026-08-29.md`

---

## 1. Source Artifact Metadata & Physical Verification

| Metric / Attribute | PDF Source Artifact | PNG Source Artifact |
| :--- | :--- | :--- |
| **Full File Path** | `C:\Users\Prekzursil\Downloads\Perplexity-Computer-Workflows.pdf` | `C:\Users\Prekzursil\Downloads\Perplexity-Computer-Workflows.png` |
| **File Size** | 5,217,800 bytes (~5.22 MB) | 2,223,411 bytes (~2.22 MB) |
| **Page / Canvas Count** | 1 Single-Page Document | 1 Canvas Image |
| **Native Dimensions** | `Rect(0.0, 0.0, 1912.0, 9022.0)` points | `1912 x 9022` pixels (RGBA) |
| **Internal Encoding** | Embedded `DCTDecode` JPEG image stream (`DeviceRGB`, 8-bit) | Lossless 24-bit PNG with 8-bit alpha channel |
| **Text Stream Extraction** | 0 extractable text characters (pure raster scan/render) | N/A (Image format) |
| **Visual Legibility** | High fidelity; slight JPEG compression artifacts around micro-text | Pristine, pixel-perfect 1:1 screen capture; 100% legible |
| **Equivalence Assessment** | The PDF is a single-page raster container encapsulating the rendered canvas of the PNG file. The PNG is the primary visual ground truth. |

---

## 2. Visual Hierarchy & Grouping Architecture

The visual layout represents a full desktop viewport capture of the **Perplexity Computer "Workflows"** hub interface in dark mode.

### 2.1 Global Chrome & Layout Structure
- **Top Navigation Bar:**
  - Product glyph (snowflake / asterism icon) on the top left.
  - Primary navigation links: `Connectors` · `Skills` · `Workflows` (active tab with bottom highlight indicator) · `Memory`.
  - Global Search Input: `Search workflows` field with magnifying glass glyph aligned to the right.
- **Section Sub-Header & Controls:**
  - Main Title: `Workflows`
  - Subtitle: `Guided flows that turn complex tasks into simple steps`
  - View Switcher / Filter Pills: `Browse` (active selected dark pill) vs. `Pinned` (secondary pill).
  - Category Selector: `All categories v` (interactive dropdown menu on the right).
- **Left Navigation Sidebar (Collapsible):**
  - Action Items: `+ New`, `Computer`, `Artifacts`, `Customize` (active selection with gear icon).
  - `Projects` Tree: `Bookmarks`, `Researching`, `Coding`.
  - `Sessions` List: Historical conversation threads.
  - User Badge: Account identifier (`Prekzursil` `Pro`) with notification icon.
- **Main Workflow Grid:**
  - Responsive two-column asymmetrical card layout (Left Column / Right Column).
  - Each workflow card contains:
    1. **Leading Glyph:** Bounded square/squircle with domain-specific icon (e.g., document, spark, wrench, chart, scale, briefcase, pulse).
    2. **Workflow Title:** Bold sans-serif header.
    3. **Action Subtitle / Description:** Concise 1–2 sentence operational summary explaining what the flow produces and its expected inputs/outputs (truncated with `...` when overflowing 2 lines).
    4. **Pin Indicator:** Angled pin icon in the upper-right corner of pinned items (e.g., `Prompt refinement`, `Autonomous Candidates Sourcer`).

---

## 3. Observed Category Catalog (16 Sections)

Across the entire 9022px canvas, 16 distinct categorical groupings are rendered:

1. **For you** (1 card): Personalized recommendation carousel/card (`Autonomous Candidates Sourcer` [pinned]).
2. **Utility** (5 cards): Core developer/prompting tools (`Prompt refinement` [pinned], `Billable hours`, `Message polish`, `Background removal`, `Candidate sourcing`).
3. **Recruiting** (1 card): Talent acquisition pipeline (`Autonomous Candidates Sourcer` [pinned]).
4. **Research** (19 cards; `Show less` toggle): Deep investigation, clinical studies, market mapping, and intelligence monitoring.
5. **Finance** (51 cards; `Show less` toggle): Heavy institutional investment, M&A, private equity, equity research, modeling (DCF, LBO), and credit analysis.
6. **Sales** (6 cards): Account profiling, outreach generation, and customer demonstration prep.
7. **Marketing** (14 cards; `Show less` toggle): SEO, Google Ads keyword generation, teardowns, storefront optimization, and social creator flows.
8. **Writing** (3 cards): Document summarization, newsletter drafting, and draft polishing.
9. **Productivity** (6 cards): File conversions, slide building, memo drafting, website generation, and final document QA.
10. **Creative** (2 cards): Presentation design and website generation.
11. **Legal** (8 cards; `Show less` toggle): Contract drafting, playbook review, litigation prep, compliance monitoring, and legal research.
12. **Personal Finance** (7 cards; `Show less` toggle): Digest feeds, run-rate dashboards, subscription cleanup, and net-worth tracking.
13. **Media** (3 cards): Video thumbnail generation, background removal, and AI product photography.
14. **Careers** (10 cards; `Show less` toggle): Job search, interview prep, cover letter generation, headshots, fellowships, housing, and STAR stories.
15. **Health** (6 cards): Comprehensive health reviews, nutrition planning, lab interpretation, doctor visit prep, fitness coaching, and sleep/recovery.
16. **Investments** (1 card): Portfolio overlap and ETF diversification analysis.

---

## 4. Authoritative 40-Workflow Reconciliation Matrix

Every workflow in the requested 40-item list is cross-referenced below against the raw visual artifacts.

| # | Authoritative Requested Name | Artifact UI Display Title | Observed Category Placements | Grid Column / Position | Exact Card Description (Verbatim from Artifact) | Status & Alignment |
| :-: | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Prompt refinement | `Prompt refinement` | `Utility` | Left Col, Row 1 | *"Improve any AI prompt with proven techniques for clarity, specificity, and effectiveness."* | **Exact Match** (Pinned in UI) |
| **2** | Background removal | `Background removal` | `Utility`<br>`Media` | Right Col, Row 2<br>Right Col, Row 1 | *"Upload an image and get a clean PNG with the background removed."* | **Exact Match** (Cross-listed in 2 categories) |
| **3** | Message polish | `Message polish` | `Utility`<br>`Writing` | Left Col, Row 2<br>Left Col, Row 2 | *"Refine and improve your drafts with adjustable tone, audience targeting, and custom instructions."* | **Exact Match** (Cross-listed in 2 categories) |
| **4** | Research update (clinical) | `Research update` | `Research` | Left Col, Row 4 | *"Summarize recent clinical studies on a condition or therapy and explain what they may mean for patients."* | **Reconciled** (Requested name includes clinical domain specifier from description) |
| **5** | Website audit | `Website audit` | `Research`<br>`Marketing` | Left Col, Row 5<br>Right Col, Row 3 | *"Enter a URL and get a full marketing audit"* | **Exact Match** (Cross-listed in 2 categories) |
| **6** | Evidence brief (medical) | `Evidence brief` | `Research` | Left Col, Row 6 | *"Create a concise clinical evidence brief on a therapy, drug class, intervention, or clinical question."* | **Reconciled** (Requested name includes medical domain specifier from description) |
| **7** | Medical evidence council | `Medical evidence council` | `Research` | Right Col, Row 7 | *"Compare medical-journal evidence on a health topic, therapy, or intervention, including consensus, disagreements, and clinician..."* | **Exact Match** |
| **8** | SEO keyword research | `SEO keyword research` | `Marketing` | Left Col, Row 4 | *"Research SEO keywords for your site — get search intent analysis, competitor gaps, and a prioritized content plan."* | **Exact Match** |
| **9** | Keyword generator (Google Ads) | `Keyword generator` | `Marketing` | Left Col, Row 2 | *"Analyze competitor Google Ads and generate a comprehensive keyword list with search volumes, competition levels, and bid..."* | **Reconciled** (Requested name includes Google Ads specifier from description) |
| **10** | Product teardown | `Product teardown` | `Research`<br>`Marketing` | Left Col, Row 1<br>Left Col, Row 1 | *"Browse a product, capture screenshots, and analyze pricing, features, onboarding, and positioning into a structured teardown."* | **Exact Match** (Cross-listed in 2 categories) |
| **11** | Brand inspiration | `Brand inspiration` | `Marketing` | Right Col, Row 4 | *"Analyze competitor websites, capture creative examples, and build a visual reference deck with annotations on copy, CTAs, and..."* | **Exact Match** |
| **12** | Store optimizer | `Store optimizer` | `Marketing` | Right Col, Row 5 | *"Analyze and optimize your online storefront with product listing improvements, SEO tags, photography tips, and competitive..."* | **Exact Match** |
| **13** | Product photos | `Product photos` | `Marketing`<br>`Media` | Right Col, Row 6<br>Left Col, Row 2 | *"Upload a product image and generate multiple versions across various lightings, angles, and backgrounds."* | **Exact Match** (Cross-listed in 2 categories) |
| **14** | Post creator | `Post creator` | `Marketing` | Right Col, Row 7 | *"Draft multiple social media post variations optimized for engagement and tailored to your voice."* | **Exact Match** |
| **15** | Document summary | `Document summary` | `Writing` | Left Col, Row 1 | *"Upload a document and get an exportable summary with key metrics, charts, and takeaways."* | **Exact Match** |
| **16** | Filetype converter | `Filetype converter` | `Productivity` | Left Col, Row 1 | *"Upload a document and convert it to multiple file formats in one step."* | **Exact Match** |
| **17** | Memo draft (investment) | `Memo draft` | `Finance`<br>`Productivity` | Left Col, Row 8<br>Left Col, Row 2 | *"Draft an investment memo for a target company using a precedent template with additional research and analysis."* | **Reconciled** (Requested name includes investment specifier from description) |
| **18** | Slide creation | `Slide creation` | `Productivity`<br>`Creative` | Right Col, Row 2<br>Left Col, Row 1 | *"Research any topic, distill the key insights, and get back a polished presentation."* | **Exact Match** (Cross-listed in 2 categories) |
| **19** | Website builder | `Website builder` | `Productivity`<br>`Creative` | Left Col, Row 3<br>Right Col, Row 1 | *"Describe your website and get a guided build with design planning and deployment."* | **Exact Match** (Cross-listed in 2 categories) |
| **20** | Final pass (document QA) | `Final pass` | `Finance`<br>`Productivity`<br>`Legal` | Left Col, Row 22<br>Right Col, Row 3<br>Left Col, Row 4 | *"Hit \"Send\" with confidence. Drop in a document and get it back with expert-level annotations flagging errors, inconsistencies, and..."* | **Reconciled** (Requested name includes document QA specifier from description; 3 categories) |
| **21** | Legal research | `Legal research` | `Legal` | Right Col, Row 4 | *"Research a legal question with citation-backed analysis. Get controlling authority, IRAC analysis, contrary authority, and a..."* | **Exact Match** |
| **22** | Draft a contract | `Draft a contract` | `Legal` | Left Col, Row 1 | *"Generate a first draft of a contract from a term sheet, grounded in your firm's precedent. Includes a drafter's note flagging..."* | **Exact Match** |
| **23** | Contract review | `Contract review` | `Legal` | Left Col, Row 2 | *"Review a contract against your firm's playbook. Get clause-by-clause analysis, risk ratings, redline suggestions, and a prioritized..."* | **Exact Match** |
| **24** | Thumbnail creator | `Thumbnail creator` | `Media` | Left Col, Row 1 | *"Generate multiple thumbnail options for your video using AI image generation with different styles, text overlays, and visual hooks."* | **Exact Match** |
| **25** | Job finder | `Job finder` | `Careers` | Left Col, Row 1 | *"Upload a resume and optional target-role context to get a personalized list of relevant jobs and internships, including match..."* | **Exact Match** |
| **26** | Interview prep | `Interview prep` | `Careers` | Right Col, Row 1 | *"Prepare for interviews with company-specific technical questions, case studies, behavioral prep, and modeling exercises."* | **Exact Match** |
| **27** | Cover letter generator | `Cover letter generator` | `Careers` | Left Col, Row 2 | *"Upload a resume and paste a job description to generate a tailored, polished cover letter that highlights the strongest fit for the role."* | **Exact Match** |
| **28** | LinkedIn headshot generator | `LinkedIn headshot generator` | `Careers` | Right Col, Row 2 | *"Upload any photo and turn it into a natural, professional-looking LinkedIn headshot while preserving the person's recognizable..."* | **Exact Match** |
| **29** | Scholarship and fellowship finder | `Scholarship and fellowship finder` | `Careers` | Left Col, Row 3 | *"Upload a resume or CV and get a concise table of relevant scholarships and fellowships with deadlines, eligibility signals, and..."* | **Exact Match** |
| **30** | Career explorer | `Career explorer` | `Careers` | Right Col, Row 3 | *"Get personalized career recommendations based on your major, interests, skills, goals, and work preferences. Explore role titles,..."* | **Exact Match** |
| **31** | Internship housing finder | `Internship housing finder` | `Careers` | Left Col, Row 4 | *"Find short-term internship housing in a target city based on budget, commute, dates, and additional details. Searches comprehensively..."* | **Exact Match** |
| **32** | Alumni finder | `Alumni finder` | `Careers` | Right Col, Row 4 | *"Find and verify alumni from your school who currently work at target companies on LinkedIn."* | **Exact Match** |
| **33** | Resume editor | `Resume editor` | `Careers` | Left Col, Row 5 | *"Upload a resume or provide a Google Docs link to get a professional, recruiter-ready resume review with ATS-aware guidance, impact-..."* | **Exact Match** |
| **34** | Behavioral story generator | `Behavioral story generator` | `Careers` | Right Col, Row 5 | *"Upload a resume and get a structured conversational coaching flow that helps you identify, refine, and practice 3–5 versatile STAR care..."* | **Exact Match** |
| **35** | Health review | `Health review` | `Health` | Left Col, Row 1 | *"Get a comprehensive view of your health with actionable insights"* | **Exact Match** |
| **36** | Nutrition planner | `Nutrition planner` | `Health` | Right Col, Row 1 | *"Create a meal plan aligned with your goals and labs"* | **Exact Match** |
| **37** | Lab results interpreter` | `Lab results interpreter` | `Health` | Left Col, Row 2 | *"Get a comprehensive analysis of your lab results with actionable next steps"* | **Exact Match** |
| **38** | Visit prep assistant | `Visit prep assistant` | `Health` | Right Col, Row 2 | *"Get a personalized briefing for your next appointment"* | **Exact Match** |
| **39** | Fitness coach | `Fitness coach` | `Health` | Left Col, Row 3 | *"Build a workout plan tailored to your activity and goals"* | **Exact Match** |
| **40** | Sleep & recovery coach | `Sleep & recovery coach` | `Health` | Right Col, Row 3 | *"Improve sleep and recovery with personalized insights"* | **Exact Match** |

---

## 5. Structural Nuances & Discrepancy Analysis

### 5.1 Title Qualification in the 40-Item Authoritative Scope
Five workflows in the authoritative request contain disambiguating parentheticals that do not appear in the top-level card heading in the UI, but directly reflect the functional description rendered on the card:
1. **Item 4 (`Research update (clinical)`):** Displayed as `Research update` in the UI. The subtitle explicitly specifies: *"Summarize recent clinical studies on a condition or therapy..."*.
2. **Item 6 (`Evidence brief (medical)`):** Displayed as `Evidence brief` in the UI. The subtitle specifies: *"Create a concise clinical evidence brief on a therapy, drug class..."*.
3. **Item 9 (`Keyword generator (Google Ads)`):** Displayed as `Keyword generator` in the UI. The subtitle specifies: *"Analyze competitor Google Ads and generate a comprehensive keyword list..."*.
4. **Item 17 (`Memo draft (investment)`):** Displayed as `Memo draft` in the UI. The subtitle specifies: *"Draft an investment memo for a target company using a precedent template..."*.
5. **Item 20 (`Final pass (document QA)`):** Displayed as `Final pass` in the UI. The subtitle specifies: *"Hit \"Send\" with confidence. Drop in a document and get it back with expert-level annotations flagging errors, inconsistencies..."*.

### 5.2 Multi-Category Cross-Listing (Tags vs. Silos)
In the Perplexity Workflows UI, individual workflows are tagged with multiple categories rather than assigned to mutually exclusive folders:
- **`Final pass`** appears in **3 categories**: `Finance`, `Productivity`, and `Legal`.
- **`Product teardown`** appears in **2 categories**: `Research` and `Marketing`.
- **`Background removal`** appears in **2 categories**: `Utility` and `Media`.
- **`Message polish`** appears in **2 categories**: `Utility` and `Writing`.
- **`Website audit`** appears in **2 categories**: `Research` and `Marketing`.
- **`Product photos`** appears in **2 categories**: `Marketing` and `Media`.
- **`Memo draft`** appears in **2 categories**: `Finance` and `Productivity`.
- **`Slide creation`** appears in **2 categories**: `Productivity` and `Creative`.
- **`Website builder`** appears in **2 categories**: `Productivity` and `Creative`.

### 5.3 Full Catalog vs. 40-Item Curated Scope
The artifact displays approximately 85+ unique workflow implementations (with heavy representation in specialized financial modeling, real estate underwriting, M&A diligence, and commercial insurance). The authoritative 40-workflow list represents a cross-functional curation across:
- General Utility & LLM Prompt Optimization (Items 1–3, 15–16)
- Clinical, Medical & Scientific Research (Items 4, 6, 7)
- Marketing, Advertising, Growth & E-Commerce (Items 5, 8–14)
- Document QA, Presentation & Web Deployment (Items 17–20)
- Legal Drafting, Compliance & Litigation Analysis (Items 21–23)
- Media & Visual Content Generation (Items 24, 28)
- Career Growth, Recruiting, Job Search & Behavioral Coaching (Items 25–27, 29–34)
- Personal Health, Diagnostics, Clinical Visits & Lifestyle Optimization (Items 35–40)

---

## 6. Inferable UI/UX Patterns & Interaction Model

1. **Card Architecture:**
   - Fixed aspect-ratio container with subtle border outline on dark background (`#1A1A1A` / `#222222`).
   - Standardized three-tier content structure: Glyphed icon box (left), 1-line bold Title, 2-line truncated description.
2. **Progressive Disclosure:**
   - Large sections (`Finance`, `Research`, `Marketing`, `Legal`, `Careers`, `Personal Finance`) implement a `Show less` / `Show more` action link in the section header to prevent cognitive overload.
3. **Favorites & Personalization:**
   - Dedicated `For you` recommendation hero card at the top.
   - Pinned workflows receive an anchor icon in the card header and surface when the user toggles the `Pinned` tab filter.
4. **Search & Discovery Facets:**
   - Global keyword search across all titles and descriptions.
   - Dual-mode filtering: Browse view vs. Pinned view.
   - Category-scoped filtering via the top-level `All categories` dropdown.

---

## 7. Design & Implementation Implications

When modeling or referencing these workflows in an agentic orchestrator or registry:
1. **Schema Design:** Every workflow definition requires a metadata schema containing:
   - `id`: Unique kebab-case slug (e.g., `medical-evidence-council`, `behavioral-story-generator`).
   - `canonical_title`: Authoritative title string.
   - `display_title`: Short UI display title.
   - `categories`: Array of applicable domain categories (supporting multi-category indexing).
   - `description`: Verbatim operational description.
   - `pinned`: Boolean flag indicating default pinned status.
   - `domain_specialization`: Functional domain classification (e.g., `medical`, `legal`, `finance`, `marketing`, `careers`, `health`, `utility`).
2. **Execution Contracts:**
   - Clinical/Medical workflows (`Evidence brief`, `Medical evidence council`, `Research update`) require strict multi-source citation and evidence synthesis contracts.
   - Document QA & Review workflows (`Final pass`, `Contract review`) operate as multi-pass rubric linters and redline annotators.
   - Interactive Coaching workflows (`Behavioral story generator`, `Interview prep`, `Visit prep assistant`) require stateful conversational loops.
