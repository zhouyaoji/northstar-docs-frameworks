Cluster profiles
================

A cluster profile is a versioned template for an application environment. It
groups the Kubernetes version, network settings, storage class, observability
add-ons, and policy settings that a team wants to reuse.

Profiles separate platform standards from project-specific values. For example,
the ``web-service`` profile can define baseline logging and security, while each
environment supplies its own region, node size, and labels.

Why profiles help
-----------------

* **Consistency:** teams begin from an approved baseline.
* **Change control:** a profile change can be reviewed before it is applied.
* **Reuse:** one profile can serve several environments through documented variables.

.. code-block:: yaml

   profile:
     name: web-service
     kubernetesVersion: "1.31"
     addons:
       - metrics
       - policy-agent

Next, see how a profile is combined with placement and ownership data in
:doc:`environments`.
