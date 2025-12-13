"""Proof upgrade and verification worker.

Scans PageVersions for stored proofs (proof_path) that are not yet verified
and attempts to upgrade/verify them using `src/anchor_ots` helpers. Marks
`proof_verified=1` in DB when verification succeeds.
"""
import time
from .db import get_conn
from ..src.anchor_ots import upgrade_ots, verify_ots, fetch_proof
from ..src.anchor_ots import stamp_hash
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def run_once(anchor_dir: Path = Path('anchors')):
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute("SELECT id, proof_path FROM PageVersions WHERE proof_path IS NOT NULL AND proof_path != '' AND proof_verified=0").fetchall()
    for r in rows:
        vid = r['id']
        ppath = r['proof_path']
        try:
            # try verify first
            ok = verify_ots(ppath)
            if ok:
                cur.execute('UPDATE PageVersions SET proof_verified=1 WHERE id=?', (vid,))
                conn.commit()
                logger.info('Verified proof for PageVersion id=%s', vid)
                continue
            # attempt upgrade then re-verify
            upgraded = upgrade_ots(ppath)
            if upgraded:
                ok = verify_ots(ppath)
                if ok:
                    cur.execute('UPDATE PageVersions SET proof_verified=1 WHERE id=?', (vid,))
                    conn.commit()
                    logger.info('Upgraded and verified proof for PageVersion id=%s', vid)
                    continue
            # if proof not found locally, try fetching from OTSD
            fetched = fetch_proof(ppath, anchor_dir)
            if fetched:
                # write fetched proof to anchors dir
                anchor_dir.mkdir(parents=True, exist_ok=True)
                fname = anchor_dir / Path(ppath).name
                fname.write_bytes(fetched)
                cur.execute('UPDATE PageVersions SET proof_path=? WHERE id=?', (str(fname), vid))
                conn.commit()
                ok = verify_ots(str(fname))
                if ok:
                    cur.execute('UPDATE PageVersions SET proof_verified=1 WHERE id=?', (vid,))
                    conn.commit()
                    logger.info('Fetched and verified proof for PageVersion id=%s', vid)
                    continue
        except Exception as e:
            logger.exception('Error processing proof for PageVersion id=%s: %s', vid, e)
    conn.close()


def run_loop(interval_seconds: int = 3600, anchor_dir: Path = Path('anchors')):
    while True:
        run_once(anchor_dir=anchor_dir)
        time.sleep(interval_seconds)
