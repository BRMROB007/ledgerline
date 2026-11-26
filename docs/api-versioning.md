# API versioning

`/v1` is consumed by the billing portal, the finance export job and partner
integrations. Within `/v1`:

- Fields may be added to responses.
- Fields are not removed, renamed or retyped.
- New request fields are optional with a default.

Anything else ships under `/v2`.
