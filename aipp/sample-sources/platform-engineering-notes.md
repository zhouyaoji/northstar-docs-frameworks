# Fictional Northstar platform engineering notes

These notes are demonstration source material. They mimic internal engineering
information that might normally live in a design document, Jira ticket, or
Confluence page. They do not describe a real product.

## Profile versions

An environment records the exact cluster-profile version used at provisioning
time. Publishing a newer profile version does not automatically modify an
existing environment. An explicit upgrade operation is required.

## Provisioning failures

Northstar validates profile existence, project permissions, provider-region
compatibility, and quota before provisioning. A failed validation does not
allocate infrastructure. Retrying without correcting the reported validation
error produces the same failure.

## Duplicate requests

The fictional service does not yet document an idempotency-key contract. A
client that loses the create response should query the project environment list
by the requested name before submitting another create request.

## Source discrepancy for review

The current tutorial demonstrates a `202 Accepted` asynchronous response at
`/v1/environments`. The current OpenAPI description defines `201 Created` at
`/projects/{projectId}/environments`. Treat this as an unresolved documentation
and API-contract discrepancy; do not present either behavior as reconciled.
