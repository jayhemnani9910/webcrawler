"""Proof upgrade and verification worker.

Scans PageVersions for stored proofs (proof_path) that are not yet verified
and attempts to upgrade/verify them using `src/anchor_ots` helpers. Marks
`proof_verified=1` in DB when verification succeeds.
"""
import time
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_conn
from anchor_ots import upgrade_ots, verify_ots, fetch_proof

logger = logging.getLogger(__name__)


def run_once(anchor_dir: Path = Path('anchors')):
    try:
        conn = get_conn()
        cur = conn.cursor()
        rows = cur.execute("SELECT id, proof_path, witness_tx_id FROM PageVersions WHERE proof_path IS NOT NULL AND proof_path != '' AND proof_verified=0").fetchall()
    except Exception as e:
        logger.exception('proof_upgrader failed to set up run: %s', e)
        return
    for r in rows:
        vid = r['id']
        ppath = r['proof_path']
        try:
            if r['witness_tx_id'] is None:
                # No OTS stamp was ever obtained for this row (see anchor.anchor_hash);
                # proof_path is a local fallback marker, not real proof material, and
                # will never verify. Mark it failed instead of retrying forever.
                cur.execute('UPDATE PageVersions SET proof_verified=-1 WHERE id=?', (vid,))
                conn.commit()
                logger.warning('PageVersion id=%s has no OTS witness; marking proof_verified=-1 (failed) instead of retrying forever', vid)
                continue
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
            logger.info('Proof for PageVersion id=%s still unverified; will retry next run', vid)
        except Exception as e:
            logger.exception('Error processing proof for PageVersion id=%s: %s', vid, e)
    conn.close()


def run_loop(interval_seconds: int = 3600, anchor_dir: Path = Path('anchors')):
    while True:
        try:
            run_once(anchor_dir=anchor_dir)
        except Exception as e:
            logger.exception('proof_upgrader run_once failed: %s', e)
        time.sleep(interval_seconds)
