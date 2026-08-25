Environments
============

An environment is a running instance of a cluster profile. It records the
values that make a deployment specific, such as its provider, region, size, and
owning team.

Northstar treats the profile as desired configuration and continuously compares
it with the environment's reported state. This model makes drift visible; it
does not excuse teams from reviewing production changes.

Example
-------

================= =====================
Field             Example value
================= =====================
Profile           ``web-service``
Environment       ``payments-production``
Provider          ``aws``
Region            ``us-west-2``
Owner             ``payments-platform``
================= =====================

Use the :doc:`../guides/create-environment` guide to make an example instance.
