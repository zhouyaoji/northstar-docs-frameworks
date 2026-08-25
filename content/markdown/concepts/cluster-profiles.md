---
title: Cluster profiles
page_id: concepts/cluster-profiles
---

# Cluster profiles

A cluster profile is a versioned template for an application environment. It groups the Kubernetes version, network settings, storage class, observability add-ons, and policy settings that a team wants to reuse.

Profiles separate platform standards from project-specific values. For example, the `web-service` profile can define the baseline logging and security configuration, while each environment supplies its own region, node size, and labels.

## Why profiles help

- **Consistency:** teams begin from an approved baseline instead of copying a previous cluster.
- **Change control:** a profile change can be reviewed before it is applied.
- **Reuse:** one profile can serve several environments through documented variables.

```yaml
profile:
  name: web-service
  kubernetesVersion: "1.31"
  addons:
    - metrics
    - policy-agent
```

Next, see how a profile is combined with placement and ownership data in [environments](./environments.md).
