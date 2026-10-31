---
title: errors
type: note
permalink: dqverify-repo-20261013/skills-claude-only/azure-validate/references/recipes/azcli/errors
---

# AZCLI Validation Errors

| Error | Fix |
|-------|-----|
| `AADSTS700082: Token expired` | `az login` |
| `Please run 'az login'` | `az login` |
| `AADSTS50076: MFA required` | `az login --use-device-code` |
| `AuthorizationFailed` | Request Contributor role |
| `Template validation failed` | Check Bicep syntax |

## Debug

```bash
az <command> --verbose --debug
```