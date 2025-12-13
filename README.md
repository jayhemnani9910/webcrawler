Website Watcher using ArchiveBox

This project implements a local "website watcher" that uses ArchiveBox to snapshot pages and a small Python service to:
- discover pages (sitemap + limited internal links)
- submit pages to ArchiveBox
- extract readable text and images from ArchiveBox snapshots
- compute stable content hashes and detect changes
- store site/page/version/change metadata in a local SQLite database
- run every 2 hours (scheduler)

Requirements
- Python 3.10+
- ArchiveBox installed and available on PATH (see https://archivebox.io)
- Install Python deps: pip install -r requirements.txt

Quick start
1. Configure ArchiveBox (make sure `archivebox` CLI works).
2. Install deps:
```
pip install -r requirements.txt
```
3. Add and run a site watcher:
```
python -m src.main add-site https://example.com
python -m src.main run
```

New useful commands
- `python -m src.main add-site <url> --agent "MyAgent/1.0"` — add site with custom user-agent
- `python -m src.main status` — show tracked sites and basic stats
- `python -m src.main web` — run minimal web UI (Flask)
- `python -m src.main search "query"` — full-text search over archived page versions (requires SQLite FTS5)

ArchiveBox index JSON
- For more reliable ArchiveBox snapshot lookup you can provide a pre-generated `archivebox list --json` output file. Set it with:

```
python -m src.main archive-index-set /path/to/archivebox_list.json
```
Or set the `ARCHIVEBOX_INDEX_JSON` environment variable to point to that file.

Robots parsing
- This project uses `reppy` when available for robust robots.txt parsing. If `reppy` is not installed, it falls back to Python's built-in `RobotFileParser`. Install `reppy` for best compliance:

```
pip install reppy
```

Files
- `src/db.py` - sqlite schema and simple helpers
- `src/crawler.py` - discovery, scheduling, and crawl orchestration
- `src/archivebox_interface.py` - wrapper to call ArchiveBox CLI
- `src/utils.py` - normalization, extraction, hashing, diff helpers
- `src/main.py` - CLI and scheduler entrypoint

Systemd and cron
- Examples for a systemd service and timer are in `systemd/website-watcher.service` and `systemd/website-watcher.timer`.
- A crontab example is in `CRON.md`.

Deployment & monitoring

Basic deployment steps:

1. Install systemd units and timer (requires root):

```bash
sudo ./install_service.sh
```

2. The installer creates `/etc/default/website-watcher` where you can set `WPS_DB_PATH` and `ARCHIVEBOX_INDEX_JSON`.

3. For containerized deployments, use the included `Dockerfile` and `docker-compose.yml` to run the watcher and (optionally) an ArchiveBox service. Ensure volumes are configured for persistent archive storage and the DB.
For production deployments, a `docker-compose.prod.yml` is provided to run a full stack (watcher, ArchiveBox, IPFS, Prometheus, Grafana). Example:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Ensure you edit `.env.prod` to set `WPS_DB_PATH` and `ARCHIVEBOX_INDEX_JSON` as appropriate, and map volumes for `archivebox_data` and `ipfs_data` to persistent storage.

Monitoring
---

- A `/health` endpoint is available for basic liveness checks.
- If `prometheus_client` is installed, a `/metrics` endpoint exposes a simple counter for search requests; install `prometheus_client` via pip to enable this.

Backups
---

- A simple DB backup script is provided at `scripts/backup_db.sh`. Schedule it via cron or systemd timer to periodically dump and gzip the SQLite DB.

Security & hardening (starter checklist)
---

- Run the watcher as a dedicated system user (installer will create `website-watcher` system user).
- Keep `watcher.db` and ArchiveBox outputs on a secure filesystem and back them up regularly.
- Validate and limit user-supplied inputs in the UI (query length limits applied).
- When exposing the web UI publicly, run behind a reverse proxy and enforce TLS.

Notes
- This is intentionally conservative: it only follows same-domain URLs and respects robots.txt.
- ArchiveBox is the storage engine — this code delegates actual downloads to ArchiveBox.

API
---

The watcher exposes a small JSON search API for automation and integrations:

- GET /api/search?q={query}
	- Response: JSON object { "results": [ { "page_version_id": int, "content_hash": str, "site_id": int|null, "archived_at": str|null, "snippet": str }, ... ] }
	- Example: curl "http://localhost:5000/api/search?q=Anthropic"

The web UI supports pagination (page/per_page) and facets; the JSON API returns up to 100 results by default.

Systemd / Scheduling
---

Examples for a systemd service and timer are provided in `systemd/website-watcher.service` and `systemd/website-watcher.timer`. Use `install_service.sh` to install the timer on systems running systemd. The project falls back to cron if systemd is not available.

Notes on optional dependencies
---

`reppy` is optional but recommended for robust robots.txt parsing; it can require a C/C++ toolchain to compile. If `reppy` installation fails, the project will use Python's `urllib.robotparser` as a fallback.
