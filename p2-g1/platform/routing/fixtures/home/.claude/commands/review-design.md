# Review Design Command

Run the design review gate on a design document to get feedback from Product Manager, Architect, Designer, Security Design, and CTO agents.

## Usage

```bash
/review-design <path-to-design-doc>
```

## Examples

```bash
# Review a specific design document
/review-design docs/plans/2026-01-11-contact-assistant-design.md

# Review the most recent design document
/review-design --latest

# Re-run review after revisions
/review-design docs/plans/2026-01-11-contact-assistant-design.md --iteration 2
```

## What This Does

1. **Validates the design document exists** and is in the expected format
2. **Spawns five review agents in parallel**:
   - **Product Manager Agent** - Validates use cases and user benefits
   - **Architect Agent** - Reviews technical architecture
   - **Designer Agent** - Reviews UX, API design, developer experience
   - **Security Design Agent** - Reviews security threats and mitigations
