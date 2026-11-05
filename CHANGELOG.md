# Changelog

All notable changes to this project are written down here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
There are no tagged releases yet.

## [Unreleased]

### Added
- MIT license file. The README already said MIT.
- `.env.example` listing every environment variable the code reads.
- `ruff check .` in CI, and a test run on Python 3.10 and 3.11.
- CONTRIBUTING.md, issue templates and a pull request template.
- Demo GIF of the web UI.

### Changed
- README rewritten around what the code does today.
- `.gitignore` covers all `.env*` files, `anchors/` and `archivebox_data/`.

### Fixed
- Unused imports and other hits from ruff's default rules.

## 2026-10-07

### Changed
- Every web UI page has a viewport meta tag, a small stylesheet and a Sites / Search nav.
- Unused modules removed.

### Fixed
- otsd-sim only reads and writes files inside its data dir, and `/stamp` takes hex hashes only.
- `crawl_delay` set from the edit form is clamped to 0 to 3600 seconds.
- ArchiveBox lookups match the exact URL, so a subpage no longer gets the site root's snapshot. Failed archives return nothing instead of an error dict, and each `archivebox` call times out after 300 seconds.
- The crawl delay applies before every page request. A 401 or 403 on `robots.txt` means stay out.
- Only `www.` folds into the root host. Other subdomains stay separate pages.
- Search filters by site and month in SQL before the 200-row cap, and facets count all results.
- An existing private key is never regenerated.
- Foreign keys are on for every database connection.

## 2026-08-28 to 2026-08-29

A long pass of fixes, one commit each. The main ones:

### Fixed
- Every crawl failed: `crawl_site` and the `search` command called `.get()` on a `sqlite3.Row`.
- CI never ran, because it triggered on a branch that did not exist.
- The two-hourly crawl job was added paused and never fired again.
- `WPS_DB_PATH` was documented but never read.
- Admin routes had no authentication. They now need `X-Admin-Token` matching `WPS_ADMIN_TOKEN`.
- The HMAC and Ed25519 key files were written world-readable.
- The crawler treated lookalike domains as internal links.
- Pages without a charset were decoded as latin-1.
- `If-Modified-Since` was sent in the wrong date format.
- The Docker image ran as root and baked in the signing keys and the live database.
- The containerised web UI listened on 127.0.0.1 and could not be reached.
- The systemd service could never start.
- The IPFS layer and the OpenTimestamps paths returned made-up results on failure.
- Tests that passed against an empty database now check what they get back.

### Removed
- README claims about anchoring that the code does not do.

## 2026-03-06

### Added
- HashiCorp Vault signing provider, with tests.

## 2025-12-12 to 2025-12-19

### Added
- First version: site discovery from sitemaps and homepage links, ArchiveBox snapshots, change detection, FTS5 search, Ed25519 signing, Flask web UI, Docker and systemd setup.
- GitHub Pages workflows.
