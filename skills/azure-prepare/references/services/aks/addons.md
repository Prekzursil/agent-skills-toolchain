---
title: addons
type: note
permalink: dqverify-repo-20261013/skills/azure-prepare/references/services/aks/addons
---

# AKS - Add-ons

## Container Monitoring

```bicep
addonProfiles: {
  omsagent: {
    enabled: true
    config: {
      logAnalyticsWorkspaceResourceID: logAnalytics.id
    }
  }
}
```

## Azure CNI Networking

```bicep
networkProfile: {
  networkPlugin: 'azure'
  networkPolicy: 'calico'
}
```

## Azure Key Vault Provider

```bicep
addonProfiles: {
  azureKeyvaultSecretsProvider: {
    enabled: true
    config: {
      enableSecretRotation: 'true'
    }
  }
}
```

## Application Gateway Ingress Controller

```bicep
addonProfiles: {
  ingressApplicationGateway: {
    enabled: true
    config: {
      applicationGatewayId: appGateway.id
    }
  }
}
```

## Add-ons Summary

| Add-on | Purpose |
|--------|---------|
| omsagent | Container Insights monitoring |
| azureKeyvaultSecretsProvider | Mount Key Vault secrets as volumes |
| ingressApplicationGateway | Application Gateway as ingress controller |
| azurepolicy | Azure Policy for Kubernetes |