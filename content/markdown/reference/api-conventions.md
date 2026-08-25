---
title: API conventions
page_id: reference/api-conventions
---

# API conventions

The fictional Northstar API illustrates conventions that make an API easier to learn and automate.

## Resource-oriented paths

Use plural nouns for collections and stable identifiers for individual resources.

```text
GET /v1/environments
GET /v1/environments/{environmentId}
POST /v1/environments
```

## Long-running operations

Return `202 Accepted` when a request starts asynchronous provisioning. Include a resource identifier and a status URL in the response so a client can poll without guessing.

## Errors

Use an error code that a script can branch on, an action-oriented message, and a request identifier for support.

```json
{
  "code": "profile_not_found",
  "message": "Create the requested profile or choose an existing profile.",
  "requestId": "req_456"
}
```

Use `allowlist` and `blocklist` instead of exclusionary legacy terms.
