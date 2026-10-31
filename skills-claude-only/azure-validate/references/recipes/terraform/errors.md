---
title: errors
type: note
permalink: dqverify-repo-20261013/skills-claude-only/azure-validate/references/recipes/terraform/errors
---

# Terraform Validation Errors

| Error | Fix |
|-------|-----|
| `Backend init failed` | Check storage account access |
| `Provider version conflict` | Update required_providers |
| `State lock failed` | Wait or force unlock |
| `Validation failed` | Check terraform validate output |

## Debug

```bash
TF_LOG=DEBUG terraform plan
```