# API Keys

The OpenAPI API Keys page manages credentials for published apps. The supported permission scope is currently `openapi:chat`, which grants access to `POST /api/openapi/chat`. Newly created keys use this scope by default.

## Expiration and use metadata

- `expires_at` is an optional Unix timestamp in seconds. Leave expiration empty to create a key that does not expire. You can edit the timestamp later or clear it.
- `last_used_at` is an optional Unix timestamp in seconds. The UI shows “No use recorded” when the field is missing, null, or zero. It is best-effort metadata updated after a key passes authentication and scope checks.
- `scopes` is a list of supported scope strings. An empty list grants no API access. Existing records with `scopes: null` remain unrestricted for compatibility and are labeled as legacy in the UI.

Records created before these fields existed remain usable: a missing expiration means no expiration, missing last-use data means no use is recorded, and a null scope list keeps its legacy behavior. Selecting a scope while editing a legacy key applies the selected restriction.

## Secret handling

The full API Key is returned and shown only once after creation. Copy and store it then; the key list masks the credential, and the full value cannot be viewed again from the UI. The list displays activation state, expiration, last-used time, scopes, and remark.

See the [Chinese API Key guide](api-keys.zh-CN.md) and the [Trace guide](trace.md).
