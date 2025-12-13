import argparse
import time
import logging
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.blocking import BlockingScheduler
from pathlib import Path

# configure root logger with rotating file handler
LOGDIR = Path('/home/jey/projects/webcrawler/logs')
LOGDIR.mkdir(parents=True, exist_ok=True)
LOGFILE = str(LOGDIR / 'website-watcher.log')
handler = RotatingFileHandler(LOGFILE, maxBytes=5_000_000, backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(handler)

from .crawler import SiteWatcher
from . import db


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd')
    addp = sub.add_parser('add-site')
    addp.add_argument('url')
    addp.add_argument('--agent', help='Override user-agent for this site')
    sub.add_parser('archive-index')
    ai = sub.add_parser('archive-index-set')
    ai.add_argument('path')
    runp = sub.add_parser('run')
    sub.add_parser('proof-worker')
    sub.add_parser('status')
    webp = sub.add_parser('web')
    webp.add_argument('--host', default='127.0.0.1')
    webp.add_argument('--port', type=int, default=1212)
    searchp = sub.add_parser('search')
    searchp.add_argument('query')
    args = parser.parse_args()
    sw = SiteWatcher()
    if args.cmd == 'add-site':
        sid = sw.add_site(args.url, user_agent=getattr(args, 'agent', None))
        print('site id', sid)
        return
    if args.cmd == 'status':
        conn = db.get_conn()
        cur = conn.cursor()
        sites = cur.execute('SELECT * FROM Sites').fetchall()
        for s in sites:
            pages = cur.execute('SELECT COUNT(*) FROM Pages WHERE site_id=?', (s['id'],)).fetchone()[0]
            last = s['last_crawled'] or 'never'
            print(f"{s['id']}: {s['normalized_root']} — pages={pages} — last_crawled={last} — status={s['status']}")
        conn.close()
        return
    if args.cmd == 'proof-worker':
        from .workers.proof_upgrader import run_loop, run_once
        # run once then run loop with default hourly interval
        run_once()
        try:
            run_loop(interval_seconds=3600)
        except (KeyboardInterrupt, SystemExit):
            print('Proof worker shutting down')
        return
    if args.cmd == 'archive-index-set':
        from .config import set_archive_index
        set_archive_index(args.path)
        print('archive index path set to', args.path)
        return
    if args.cmd == 'web':
        from .ui import app
        app.run(host=args.host, port=args.port)
        return
    if args.cmd == 'search':
        rows = db.search_page_versions(args.query, limit=20)
        for r in rows:
            print(r['page_version_id'], r.get('snippet') or '')
        return
    if args.cmd == 'run':
        sched = BlockingScheduler()
        # run immediately then every 2 hours
        def job():
            print('Starting crawl cycle')
            sw.run_cycle()
            print('Crawl cycle completed')
        sched.add_job(job, 'interval', hours=2, next_run_time=None)
        # run once now
        job()
        try:
            sched.start()
        except (KeyboardInterrupt, SystemExit):
            print('Shutting down')

if __name__ == '__main__':
    db.init_db()
    main()
