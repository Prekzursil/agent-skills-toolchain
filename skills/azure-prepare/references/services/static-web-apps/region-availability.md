---
title: region-availability
type: note
permalink: dqverify-repo-20261013/skills/azure-prepare/references/services/static-web-apps/region-availability
---

# SWA Region Availability

⚠️ **NOT available in many common regions** — Check before deployment.

| ✅ Available | ❌ NOT Available (will FAIL) |
|-------------|------------------------------|
| `westus2` | `eastus` |
| `centralus` | `northeurope` |
| `eastus2` | `southeastasia` |
| `westeurope` | `uksouth` |
| `eastasia` | `canadacentral` |
| | `australiaeast` |
| | `westus3` |

## Recommended Regions

| Pattern | Use |
|---------|-----|
| SWA only | `westus2`, `centralus`, `eastus2`, `westeurope`, `eastasia` |
| SWA + backend | `westus2`, `centralus`, `eastus2`, `westeurope`, `eastasia` |
| SWA + Azure OpenAI | `eastus2` (only region with full overlap) |