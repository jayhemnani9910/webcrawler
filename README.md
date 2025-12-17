# Website Archiver & Change Detection System

A production-ready website monitoring and archival system built on ArchiveBox. Automatically discovers, snapshots, and tracks changes across websites with full-text search, cryptographic verification, and distributed storage capabilities.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-API-green)
![Docker](https://img.shields.io/badge/Docker-ready-blue)

## Overview

This project implements an intelligent website watcher that combines ArchiveBox's powerful archival capabilities with advanced change detection, distributed storage, and cryptographic verification. Perfect for compliance monitoring, research archival, competitive intelligence, or preserving important web content.

## Key Features

- **Intelligent Discovery**: Automatic sitemap parsing and internal link crawling with robots.txt compliance
- **Change Detection**: Content-hash based change tracking with stable diff algorithms
- **Full-Text Search**: SQLite FTS5 powered search across all archived versions
- **Distributed Storage**: Optional IPFS integration for decentralized content preservation
- **Cryptographic Verification**: Merkle trees and content anchoring for authenticity
- **Production Ready**: Systemd timers, Docker support, Prometheus metrics, health checks
- **Web Interface**: Flask-based UI for search, monitoring, and site management
- **Automated Scheduling**: Configurable intervals (default: every 2 hours)

## Technology Stack

| Category | Technologies |
|----------|-------------|
| **Core** | Python 3.10+, ArchiveBox, SQLite (FTS5) |
| **Web** | Flask, BeautifulSoup4, lxml, readability-lxml |
| **Scheduling** | APScheduler, Systemd timers |
| **Crypto** | PyNaCl, Cryptography, Merkle trees |
| **Monitoring** | Prometheus, Health checks |
| **Storage** | IPFS (optional), SQLite |

## Quick Start

```bash
# Prerequisites: Install ArchiveBox
pip install archivebox && archivebox init

# Clone and install
git clone https://github.com/jayhemnani9910/webcrawler.git
cd webcrawler
pip install -r requirements.txt

# Add a site and run
python -m src.main add-site https://example.com
python -m src.main run

# Search archived content
python -m src.main search "query"

# Launch web UI
python -m src.main web  # http://localhost:5000
```

## Production Deployment

### Docker

```bash
docker compose up -d --build

# Production with Prometheus + Grafana
docker compose -f docker-compose.prod.yml up -d
```

### Systemd

```bash
sudo ./install_service.sh
sudo systemctl enable website-watcher.timer
sudo systemctl start website-watcher.timer
```

## API

```bash
# Search endpoint
GET /api/search?q={query}

# Health check
GET /health

# Prometheus metrics
GET /metrics
```

## Project Structure

```
webcrawler/
├── src/
│   ├── main.py              # CLI and scheduler
│   ├── crawler.py           # Discovery and orchestration
│   ├── archivebox_interface.py
│   ├── db.py                # SQLite schema
│   ├── crypto.py            # Cryptographic utilities
│   ├── merkle.py            # Merkle tree implementation
│   └── ipfs_interface.py    # IPFS storage layer
├── systemd/                 # Service units
├── docker-compose.yml
└── scripts/backup_db.sh
```

## Use Cases

- Compliance monitoring and regulatory tracking
- Research archival and citation preservation
- Competitive intelligence
- Content preservation before deletion
- Change auditing with verifiable records

## License

MIT
