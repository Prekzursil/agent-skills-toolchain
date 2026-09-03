# Azure validate recipes

Per-tooling validation notes used by the azure-validate skill. Each subdirectory
covers one deploy/auth surface:

| Recipe | Contents |
|---|---|
| [azd/](azd/) | Azure Developer CLI environment + error patterns |
| [azcli/](azcli/) | Azure CLI error patterns |
| [bicep/](bicep/) | Bicep error patterns |
| [terraform/](terraform/) | Terraform error patterns |

Open the matching recipe when the skill routes a failure to a specific toolchain.
