Website Watcher API
====================

Endpoints
---------

/ (GET)
- Web UI: lists watched sites with page counts and last-crawled time.

/site/<id> (GET)
- Web UI: lists pages for a site.

/site/<id>/edit (GET, POST)
- Web UI: view/edit a site's active flag, user agent and crawl delay. POST mutates
  the Sites table. No authentication.

/search (GET)
- Web UI: full-text search form and results, with site/date facets and pagination.
  Query params: `q`, `page`, `per_page`, `site`, `date`.

/health (GET)
- Returns {"status": "ok"} if the database is reachable, else {"status": "error"}
  with HTTP 500.

/metrics (GET)
- Prometheus metrics in text exposition format. Returns HTTP 503 if
  `prometheus_client` is not installed.

/admin/metrics (GET)
- Returns aggregate counts: {"sites", "pages", "page_versions", "changes"}.
- Requires admin auth (see below).

/admin/global_preservation_health (GET)
- Returns {"avg_knowledge_survival_rate", "top_sites_by_cultural_significance", "merkle_forest_count"}.
- Requires admin auth (see below).

/admin/crisis_mode (GET, POST)
- GET returns the latest crisis status: {"active", "activated_at", "note"}.
- POST accepts form or JSON body {"action": "activate"|"deactivate", "note": "..."}
  and inserts a new CrisisStatus row. Returns {"status": "activated"|"deactivated"},
  or 400 for an unknown action.
- Requires admin auth (see below).

Admin auth
----------
The three `/admin/*` routes above require a `X-Admin-Token` header matching the
`WPS_ADMIN_TOKEN` environment variable. If `WPS_ADMIN_TOKEN` is not set, the routes
refuse every request with HTTP 503 (they do not default open). A header that does
not match the expected token gets HTTP 401.

/api/search (GET)
- Query params: `q` (required; missing or empty returns {"results": []}).
- Returns {"results": [{"page_version_id", "content_hash", "site_id", "archived_at", "snippet"}, ...]}.
- No authentication.

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
