# Rehab notes

Notes for `project-rehab`. Written 2026-08-27 from the README, CRON.md, the three
docker-compose files, install_service.sh, the systemd units, scripts/ and the CI
workflows.

## Environment setup

A `.venv` now exists at the repo root (created 2026-08-28). There is still no
`pyproject.toml`, only `requirements.txt`. If a fresh checkout needs one:

```
uv venv
uv pip install -r requirements.txt
uv pip install pytest
```

`.venv/` is already in `.gitignore`, so this leaves no trace in git. `pytest` is not
in `requirements.txt`; CI installs it separately in `.github/workflows/ci.yml`, so
this matches CI.

## Safe run command

```
uv run python -m src.main status
uv run python -m src.main search "Anthropic"
```

Both read the database and print. Neither crawls, archives, opens a port or calls out
to the network.

The README quickstart shows `python -m src.main run` as the main command. That one is
not safe here. See "Do not run".

## What success looks like

Not yet known. I have not run either command, so these criteria get pinned by the
Phase 3 baseline capture and this section should be rewritten with the real output
afterwards. Expected shape:

- `status` exits 0 and reports the 3 rows in Sites and the 303 rows in Pages.
- `search "Anthropic"` exits 0 and returns rows from the FTS index, or returns
  nothing without erroring. PageVersions has only 2 rows and PageVersionsFTS is
  empty, so an empty result is a plausible healthy answer.

## Test command

```
uv run pytest -q
```

This is what `.github/workflows/ci.yml` runs. 8 test files under `tests/`.

`tests/conftest.py` redirects `db.DB_PATH` to a temp dir for the whole session, so
this command no longer writes to the live database. See "Live data" below for other
commands that still can.

## Live data

`watcher.db` at the repo root is real data: 3 sites, 303 pages, 2 page versions,
12 merkle deltas. It is in `.gitignore` and it is untracked, so git cannot restore it.

`src/db.py:6` hardcodes the path:

```
DB_PATH = Path(__file__).resolve().parents[1] / "watcher.db"
```

It does not read `WPS_DB_PATH`, even though `.env.prod.example`, `install_service.sh`
and `scripts/backup_db.sh` all set or honour that variable. So there is no environment
override available and the path cannot be redirected without editing code.

`tests/test_merkle_ordering.py:10` calls `db.init_db()` and then `db.add_site(...)`,
but `tests/conftest.py` now has a session-scoped, autouse fixture that points
`db.DB_PATH` at a pytest `tmp_path` before any test runs, so a plain `pytest` run no
longer touches the live database.

Procedure for any command that can open the database for writing (other than running
the test suite, which is now safe on its own):

1. `cp -p watcher.db <scratchpad>/watcher.db.orig` (already done, md5
   `f8f9b43ce13b3ab49e9ad78bf8d82c59`)
2. `mv watcher.db watcher.db.rehab-held`
3. `cp <scratchpad>/watcher.db.orig watcher.db`
4. run the command, which now writes to a disposable copy
5. `mv watcher.db.rehab-held watcher.db` when the run is finished

The original file is never opened for writing. Step 5 restores the exact original.

## Do not run

Nothing on this list gets run.

Live network and archival:
- `python -m src.main run` (crawls the 3 configured sites and their 303 pages, calls
  ArchiveBox, writes to the database)
- `python -m src.main proof-worker` (OpenTimestamps calls over the network, updates
  PageVersions rows)
- `python -m src.main add-site`, `python -m src.main archive-index-set` (mutate state)

Servers and ports:
- `python -m src.main web` (long-running Flask server on 127.0.0.1:1212)

Root and system state:
- `sudo ./install_service.sh` (creates a system user, writes to /etc/systemd/system
  and /etc/default, runs `systemctl enable --now`)
- `./secure_permissions.sh` (chmods `keys/` and `watcher.db`)
- any `systemctl` command

Containers:
- `docker compose up` against any of `docker-compose.yml`, `docker-compose.prod.yml`,
  `docker-compose.integration.yml` (builds images, pulls, binds ports 1212, 8000,
  4001, 5001, 3000, 9090, 15000, 16000)
- `scripts/run_integration.sh` (wraps docker compose up, the integration test, and down)

Environment mutation:
- `scripts/install_spacy_models.sh` (downloads and installs a spaCy model)
- any `pip install` into system Python

Publishing:
- `git push`, `gh workflow run`, anything that triggers `pages.yml` or
  `jekyll-gh-pages.yml`, since both deploy to a public GitHub Pages site

Credentials:
- anything reading or writing `keys/hmac.key`, `keys/fallback_hmac.key`, or a `.env`

Read-only inspection of these files is fine. Running them is not.

## Needs credentials

These parts cannot be checked in this run, and the report should list them as unchecked
rather than guess:

- `src/keys_kms.py` KMS path needs `AWS_KMS_KEY_ID` and boto3
- `src/keys_kms.py` Vault path needs `VAULT_ADDR` and `VAULT_TOKEN` and hvac
- `src/crypto_asym.py` KMS signing needs `WPS_KMS_KEY_ID` or `AWS_KMS_KEY_ID`
- `src/anchor_ots.py` needs `OTSD_URL` and a reachable OpenTimestamps server, or the
  `ots` binary
- `src/archivebox_interface.py` needs ArchiveBox installed and `ARCHIVEBOX_OUTPUT_DIR`
  or an index JSON. `watcher_config.json` currently points at
  `/tmp/anthropic_archive_list.json`, which may not exist.
- `src/ipfs_interface.py` needs a reachable IPFS daemon on 5001
- `src/p2p_libp2p.py` and `src/gossip_distributed.py` need the libp2p relay service

## Known broken, leave alone

Nothing declared. Add entries here if you want something left untouched.
