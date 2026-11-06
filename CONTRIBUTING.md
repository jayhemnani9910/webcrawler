# Contributing

Thanks for taking a look. Small fixes and bug reports are welcome.

I try to reply to issues within a few days.

## Setup

You need Python 3.10 or newer. ArchiveBox is optional: without it the crawler fetches pages directly.

```bash
git clone https://github.com/jayhemnani9910/webcrawler.git
cd webcrawler
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest ruff
```

## Tests and lint

```bash
ruff check .
pytest -q
```

CI runs both on Python 3.10 and 3.11 for every push and pull request. The tests use a temporary database, so they never touch your `watcher.db`.

To try a change by hand, crawl a page you serve yourself rather than someone else's site:

```bash
python -m http.server 8765 --bind 127.0.0.1 -d some/folder/with/html &
python -m src.main add-site http://127.0.0.1:8765/
python -m src.main run        # Ctrl-C after "Crawl cycle completed"
python -m src.main search "some word"
```

## Style

- Match the code around you. Ruff's default rules are the only lint (see `ruff.toml`).
- Keep changes small and focused. One fix per pull request.
- Add or update a test when you change behaviour.

## Pull requests

- Branch from `master` and open the pull request against `master`.
- Say what changed and how you tested it.
- CI must be green.

## Bug reports

Open an issue with the steps to reproduce, what you expected, what happened, your Python version and OS. Include the relevant lines from `logs/website-watcher.log` if there are any.

Please don't post API keys, Vault tokens or the contents of `keys/` in issues.
