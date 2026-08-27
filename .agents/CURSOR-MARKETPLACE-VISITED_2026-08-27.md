# Cursor marketplace visited-set

Purpose: ids already parsed by an audit — future marketplace hunts SKIP anything listed here at the same version/hash. Append-only; re-visit only if the version/hash changes.

## Visit 1 — 27.08.2026 (Customize + marketplace audit)

### Bolt team marketplace (`ai-marketplace-public`, Bolt Technology OÜ)

- Source dir: `~\.cursor\plugins\marketplaces\origin.cursor.com\bolt-technology-o\ai-marketplace-public\edb099967002433599d2f9c46738ff8510b0b35b\`
- Marketplace revision hash: `edb099967002433599d2f9c46738ff8510b0b35b`
- All 25 plugin ids visited 27.08.2026:

| id | version (if unpacked locally) |
| --- | --- |
| common | 1.0.22 (installed, skills parsed) |
| boltable | 1.0.3 (installed, skills parsed) |
| jira-hygiene | catalog only |
| delivery-management | catalog only |
| commerce | catalog only |
| im-rides | catalog only |
| n8n | catalog only |
| design | catalog only |
| rider-qa | catalog only |
| insights | catalog only |
| internal-products | catalog only |
| developers-ai-marketplace | catalog only |
| performance-cycle | catalog only |
| customer-payments-skills | catalog only |
| new-bets-strategy-skills | catalog only |
| ux-research | catalog only |
| diy-unmoderated-usability-test | catalog only |
| performance-creative-automation | catalog only |
| usability-reviewer | catalog only |
| apis | catalog only |
| comms-privacy-dev | catalog only |
| analytics-engineering-tooling | catalog only |
| micromobility-supply-chain-team | catalog only |
| talent-management | catalog only |
| central-fp-a | catalog only |

`common` skills parsed (26): abandoned-slack-promises, anti-slop, auto-convert-to-markdown, bolt-a11y-annotate, bolt-data-governance-check, bolt-governance-compliant-alternatives, bolt-slides, claude-spend-diagnosis, codex-bridge, confluence-export, conversation-kickoff, create-report, cs-forecasting-skill, databricks-workspace, elastic-cli, electronics-design-review, find-answer, invoices-check-in-gmail, migrate-cursor-conversational-analytics, polish-pr, review-like-im-rides, rides-wbr-commentary, setup-engineering-quality-skills, token-diet, weekly-notes-and-strategy-docs-writing-style, write-right-beta.

`boltable` skills parsed (4): boltable-core, boltable-database, boltable-integrations, boltable-storage.

### Cursor public catalog cache (`cursor-public`)

- Source dir: `~\.cursor\plugins\cache\cursor-public\` — **catalog cache, NOT installs**; left intact per hard rule.
- 181 folder ids enumerated 27.08.2026. Per-id version hashes NOT enumerated (RAM-starved box; one hash subdir per id was confirmed for the four cleanup suspects only).

1password, agent-compatibility, agentmail, airtable, airwallex-dev, aleph, amazon-location-service, amd-skills, antimetal, apify, app-builder, appwrite-plugin, arize-skills, asana, astronomer-data, atlan, atlassian-twg-cli, auth0, aws-agents, aws-amplify, aws-core, aws-data-analytics, aws-serverless, box, braintrust, bright-data, browse, browser-use, browserstack, buildkite, canva, chainguard, chatprd, checkmarx, circle, circleback, clay, clerk, cli-for-agent, clickup, cloudflare, cloudinary, cockroachdb, coderabbit, composio, compound-engineering, context7-plugin, continual-learning, coralogix-mcp, corridor, create-plugin, ctx, cursor-sdk, cursor-team-kit, dagster-expert, databases-on-aws, databricks, datarobot-agent-skills, dataverse, dbt, deploy-on-aws, dnb-commercial-graph, dnb-risk-analytics, docs-canvas, docusign, dynatrace, elastic, encore, endorlabs, exa, falconer, figma, firebase, firecrawl, firetiger, forge, functions, gitbook, githits, github, gitlab, glean, gong, grafana-assistant, grafana-cloud-mcp, gsap-skills, harness, here_now, hex, heygen, higgsfield, hubspot, huggingface-skills, icepanel, intercom, jfrog, juicebox, langfuse, launchdarkly, linear, link, lovable, lucid, magic-patterns, magicpath, mainframe, manufact, mem0, merge-agent-handler, meta-vr, meticulous, mintlify-cursor-plugin, mixpanel-mcp, mobbin, modern-web-guidance, monday-crm, mongodb, monk, neon-postgres, netlify-skills, nvidia-skills, observe, omni-analytics, opensearch-agent-skills, opsera-devsecops, orchestrate, pagerduty, paper-desktop, paradedb, parallel, phantom-connect, pinecone, plain, planetscale, playwright, port, postman, pr-review-canvas, prisma, profound, pstack, quiverai, railway, raisely, ramp, react-doctor, redis-development, remotion, render, resend, resolve-ai, resolve-ai-admin, revenuecat, revolut-x, runlayer, sagemaker-ai, salesforce, sanity, scylladb, semgrep-plugin, sentry, shadcn, shopify-plugin, snowflake-cursor-plugin, sourcegraph-cursor-plugin, spottercode, stripe, subtext-verify, svelte, tabnine, tavily, temporal, thermos, tierzero, tldraw, turbopuffer, webflow, wix, x, zenity-inventory.

### Other cache roots

- `bolt-ai-marketplace-ai-marketplace-public`: boltable, common only (the two installed).
- `ai-marketplace-github`: empty.
- `plugins\local`: empty (per 27.08 cleanup log).
