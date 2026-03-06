Merkle Sync API
================

Endpoints
---------

/api/merkle/push (POST)
- Accepts JSON: {"delta": <delta_dict>, "signature": "<hex>"}
- Verifies signature (DID-aware if `delta.signer_did` present).
- Performs basic ordering guards (site-scoped):
  - If `delta.sequence` is present and <= max stored sequence for the site, the request is rejected with HTTP 409 and error `obsolete sequence`.
  - If `delta.lamport` is present and <= max stored lamport for the site, the request is rejected with HTTP 409 and error `obsolete lamport`.
- On success the delta is stored; the server will attempt to apply it to the local Merkle forest (best-effort) and return {"stored_id": <id>, "applied": true|false}.

/api/merkle/pull (GET)
- Query params: ?site=<site_id>
- Returns the latest stored Merkle forest for that site: {"site_id": <id>, "root": "<root>", "tree_blob": {...}}

Error codes
-----------
- 400: bad request / verification failed
- 409: obsolete sequence/lamport (client should reconcile and retry)

Notes
-----
- This is a prototype API. For robust multi-node synchronization you should:
  - Use DID-backed signatures and a stable resolver
  - Implement conflict resolution and delta replay strategies
  - Run integration tests with OTSD/IPFS/libp2p services to validate end-to-end flows
