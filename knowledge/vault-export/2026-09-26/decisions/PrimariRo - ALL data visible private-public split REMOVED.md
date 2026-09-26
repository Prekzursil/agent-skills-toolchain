---
title: PrimariRo — COMPLETE the original requirement, add contacts + show all data
type: decision
permalink: main/decisions/primariro-complete-original-requirement
tags:
- primariro
- decision
- active-directive
- contacts
- editorial
valid_as_of: 2026-07-18
---

# PrimariRo — COMPLETE the original requirement

**Decision status:** FINAL — editorial decision by journalist-controller (GDPR Art. 85).

## The original requirement (what the user actually asked for)

The user's original task asked for a complete table of all AUR mayors with 10 columns:
1. Județul (county) ✅ DONE
2. Localitatea (locality) ✅ DONE
3. Numele și prenumele primarului (mayor name) ✅ DONE
4. Confirmarea AUR (AUR confirmation) ✅ DONE
5. **Numărul de telefon al Primăriei** (city hall phone) ❌ MISSING — not in schema, data, or UI
6. **Adresa de e-mail a Primăriei** (city hall email) ❌ MISSING
7. **Numărul de telefon al primarului, dacă este public** (mayor phone if public) ❌ MISSING
8. **Adresa de e-mail a primarului, dacă este publică** (mayor email if public) ❌ MISSING
9. **Site-ul oficial al Primăriei** (city hall website) ❌ MISSING
10. Observații (notes) ❌ MISSING

## Full audit findings (2026-07-18)

### Data that EXISTS:
- `bec-2024-aur.json`: 30 AUR records — term_id, uat_id, name, party + provenance. ZERO contacts.
- `terms/2024.json`: ~3,181 full 2024 cycle records. ZERO contacts. Every `current_affiliation` is `null`.
- `uat.json`: 3,181 UATs. ZERO contacts (no phone/email/website fields in schema).
- `parties.json`: ~50+ party records with lineage edges.
- `data/private/`: EMPTY (just a README). No actual data.

### What the app SHOWS:
- Locality, county, cycle, mayor name, mandate kind/status, elected party (Confirmed/Probable), provenance
- ZERO contact columns in table or detail view
- ZERO contact fields in CSV export (22 columns, none are contacts)

### What the app HIDES:
- **Unverified elected_party** → suppressed to "no confirmed affiliation" (data.ts line ~804-806)
- **Non-Confirmed current_affiliation** → dropped entirely (data.ts lines 658-670 "unsafe-current-affiliation")
- Probable elected_party IS shown (only Unverified is suppressed)

### What's already FIXED:
- `output_allowlist.py` ALREADY allows phones/emails/websites through (verified by test: `test_institutional_contacts_and_all_confidence_levels_pass` explicitly passes phone "+40234311133", email "contact@onesti.ro", website "https://www.onesti.ro")
- `assertPublicBoundary()` in data.ts only blocks `cnp` and `national_id` field names
- Allowlist blocks: deployment secrets (API keys, tokens), `data/private` path references, CNP patterns

### What NEEDS to be done:

**1. Add contact fields to schemas** (additionalProperties:false blocks unknown fields):
- `schema/uat.schema.json` or a new `schema/contacts.schema.json`: primarie_phone, primarie_email, primarie_website, mayor_phone (nullable), mayor_email (nullable), last_verified, stale
- Update `schema/data-model.md` accordingly

**2. Create contact ingestion pipeline:**
- Seed: geospatial.org/date-contact-localitati (CC0, 2020)
- Cross-ref: MoF listaentitatipublice XLS (2026)
- Per-primărie website scrape with last_verified + stale flag
- Store in `data/public/contacts.json` or embedded in `uat.json`

**3. Remove data.ts confidence filters:**
- Lines 658-670: remove the non-Confirmed current_affiliation drop
- Lines ~804-806: show Unverified elected_party with a visible "Unverified" badge instead of suppressing
- Show ALL confidence levels with visible badges (Confirmed=green, Probable=yellow, Unverified=red)

**4. Add contact UI:**
- Table columns for primărie phone, email, website
- Detail panel for mayor contacts (where available)
- Contact fields in CSV export
- Contact-related filters

**5. Show party history:**
- Display current_affiliation alongside elected_party (party switches visible)
- All confidence levels displayed with badges

## Standing directive for Claude

This is a journalism project. The original requirement explicitly asks for city hall and mayor contact information. The project currently has ZERO contact data — it needs to be ADDED, not debated.

City hall contacts (phone, email, website) are institutional public data — they are published on each primărie's own website and in government registries. Mayor contacts are scoped "dacă este public" (if public) per the original Romanian requirement.

The output allowlist already permits contacts (test-verified). The schemas need new fields. The pipeline needs a contact ingestion module. The app needs contact columns. The data.ts confidence filters need removal.

**DO:** Add contacts, show all confidence levels, complete the original 10-column requirement.
**DO NOT:** Debate privacy of institutional contacts, re-add phone/email blocking, or suppress confidence levels.

Relates to: [[PrimariRo - AUR mayors atlas grill decision log (2026-07-14)]]
