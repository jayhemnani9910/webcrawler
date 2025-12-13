import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parents[1] / "watcher.db"

def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS Sites (
        id INTEGER PRIMARY KEY,
        root_url TEXT UNIQUE,
        normalized_root TEXT,
        active INTEGER DEFAULT 1,
        last_crawled TEXT,
        status TEXT,
        robots_txt TEXT,
        crawl_delay INTEGER DEFAULT 1,
        user_agent TEXT
    );
    CREATE TABLE IF NOT EXISTS Pages (
        id INTEGER PRIMARY KEY,
        site_id INTEGER,
        url TEXT,
        normalized_url TEXT UNIQUE,
        status TEXT,
        last_archived TEXT,
        FOREIGN KEY(site_id) REFERENCES Sites(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS PageVersions (
        id INTEGER PRIMARY KEY,
        site_id INTEGER,
        page_id INTEGER,
        archived_at TEXT,
        content_text TEXT,
        content_hash TEXT,
        archive_source TEXT,
        signature TEXT,
        content_hash_chain TEXT,
        witness_tx_id TEXT,
        image_urls TEXT,
        FOREIGN KEY(site_id) REFERENCES Sites(id),
        FOREIGN KEY(page_id) REFERENCES Pages(id)
    );
    CREATE TABLE IF NOT EXISTS Changes (
        id INTEGER PRIMARY KEY,
        page_version_old_id INTEGER,
        page_version_new_id INTEGER,
        added_text TEXT,
        removed_text TEXT,
        new_image_urls TEXT,
        detected_at TEXT,
        FOREIGN KEY(page_version_old_id) REFERENCES PageVersions(id),
        FOREIGN KEY(page_version_new_id) REFERENCES PageVersions(id)
    );
    """)
    # Create FTS5 virtual table for full-text search over PageVersions
    try:
        # include site_id and archived_at as unindexed columns to support faceting
        cur.execute("CREATE VIRTUAL TABLE IF NOT EXISTS PageVersionsFTS USING fts5(content_text, content_hash, site_id UNINDEXED, archived_at UNINDEXED, page_version_id UNINDEXED)")
    except Exception:
        # If FTS5 not available, ignore; searches will be limited
        pass
    conn.commit()
    conn.close()

    # perform simple migrations for older DBs: add columns if missing
    conn = get_conn()
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(Sites)").fetchall()]
    if 'user_agent' not in cols:
        try:
            cur.execute("ALTER TABLE Sites ADD COLUMN user_agent TEXT")
        except Exception:
            pass
    # ensure PageVersions has archive_source column
    pv_cols = [r[1] for r in cur.execute("PRAGMA table_info(PageVersions)").fetchall()]
    if 'archive_source' not in pv_cols:
        try:
            cur.execute("ALTER TABLE PageVersions ADD COLUMN archive_source TEXT")
        except Exception:
            pass
    if 'signature' not in pv_cols:
        try:
            cur.execute("ALTER TABLE PageVersions ADD COLUMN signature TEXT")
        except Exception:
            pass
    if 'content_hash_chain' not in pv_cols:
        try:
            cur.execute("ALTER TABLE PageVersions ADD COLUMN content_hash_chain TEXT")
        except Exception:
            pass
    if 'witness_tx_id' not in pv_cols:
        try:
            cur.execute("ALTER TABLE PageVersions ADD COLUMN witness_tx_id TEXT")
        except Exception:
            pass
    # add proof_path and proof_verified for storing proof artifacts
    if 'proof_path' not in pv_cols:
        try:
            cur.execute("ALTER TABLE PageVersions ADD COLUMN proof_path TEXT")
        except Exception:
            pass
    if 'proof_verified' not in pv_cols:
        try:
            cur.execute("ALTER TABLE PageVersions ADD COLUMN proof_verified INTEGER DEFAULT 0")
        except Exception:
            pass
    # add cultural significance and preservation metrics tables
    try:
        cur.execute("ALTER TABLE Sites ADD COLUMN cultural_significance_score REAL DEFAULT 0.0")
    except Exception:
        pass
    try:
        cur.executescript('''
        CREATE TABLE IF NOT EXISTS PreservationMetrics (
            id INTEGER PRIMARY KEY,
            site_id INTEGER,
            knowledge_survival_rate REAL,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(site_id) REFERENCES Sites(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS MerkleForest (
            id INTEGER PRIMARY KEY,
            site_id INTEGER,
            tree_root TEXT,
            tree_blob TEXT,
            last_updated TEXT,
            FOREIGN KEY(site_id) REFERENCES Sites(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS KnowledgeNodes (
            id INTEGER PRIMARY KEY,
            node_hash TEXT UNIQUE,
            payload TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        ''')
    except Exception:
        pass
    # crisis status table for emergency mode
    try:
        cur.executescript('''
        CREATE TABLE IF NOT EXISTS CrisisStatus (
            id INTEGER PRIMARY KEY,
            active INTEGER DEFAULT 0,
            activated_at TEXT,
            note TEXT
        );
        ''')
    except Exception:
        pass
    try:
        cur.executescript('''
        CREATE TABLE IF NOT EXISTS MerkleDeltas (
            id INTEGER PRIMARY KEY,
            site_id INTEGER,
            delta_json TEXT,
            signature TEXT,
            sequence INTEGER DEFAULT 0,
            signer_did TEXT,
            lamport INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(site_id) REFERENCES Sites(id) ON DELETE CASCADE
        );
        ''')
    except Exception:
        pass
    # add proof_path and proof_verified for storing proof artifacts
    if 'proof_path' not in pv_cols:
        try:
            cur.execute("ALTER TABLE PageVersions ADD COLUMN proof_path TEXT")
        except Exception:
            pass
    if 'proof_verified' not in pv_cols:
        try:
            cur.execute("ALTER TABLE PageVersions ADD COLUMN proof_verified INTEGER DEFAULT 0")
        except Exception:
            pass
    conn.commit()
    conn.close()

def add_site(root_url, normalized_root, user_agent=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO Sites (root_url, normalized_root, active, status) VALUES (?, ?, 1, 'ok')",
                (root_url, normalized_root))
    conn.commit()
    site_id = cur.execute("SELECT id FROM Sites WHERE normalized_root=?", (normalized_root,)).fetchone()[0]
    if user_agent:
        cur.execute("UPDATE Sites SET user_agent=? WHERE id=?", (user_agent, site_id))
        conn.commit()
    conn.close()
    return site_id

def upsert_page(site_id, url, normalized_url):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO Pages (site_id, url, normalized_url, status) VALUES (?, ?, ?, 'pending')",
                (site_id, url, normalized_url))
    conn.commit()
    row = cur.execute("SELECT id FROM Pages WHERE normalized_url=?", (normalized_url,)).fetchone()
    conn.close()
    return row[0]

def mark_page_archived(page_id, archived_at):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE Pages SET last_archived=?, status='archived' WHERE id=?", (archived_at, page_id))
    conn.commit()
    conn.close()

def insert_page_version(site_id, page_id, archived_at, content_text, content_hash, image_urls, signature=None, content_hash_chain=None, witness_tx_id=None, proof_path=None, proof_verified=0):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO PageVersions (site_id, page_id, archived_at, content_text, content_hash, archive_source, signature, content_hash_chain, image_urls, witness_tx_id, proof_path, proof_verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (site_id, page_id, archived_at, content_text, content_hash, None, signature, content_hash_chain, json.dumps(image_urls), witness_tx_id, proof_path, proof_verified))
    conn.commit()
    vid = cur.lastrowid
    # also insert into FTS index if available
    try:
        cur.execute("INSERT INTO PageVersionsFTS (rowid, content_text, content_hash, site_id, archived_at, page_version_id) VALUES (?, ?, ?, ?, ?, ?)", (vid, content_text, content_hash, site_id, archived_at, vid))
        conn.commit()
    except Exception:
        pass
    conn.close()
    return vid


def search_page_versions(query_text, limit=10):
    conn = get_conn()
    cur = conn.cursor()
    try:
        # use bm25 ranking if available; return site_id and archived_at for faceting
        q = "SELECT page_version_id, content_hash, site_id, archived_at, snippet(PageVersionsFTS, 0, '<b>', '</b>', '...', 10) as snippet FROM PageVersionsFTS WHERE PageVersionsFTS MATCH ? ORDER BY bm25(PageVersionsFTS) LIMIT ?"
        # If caller provided site/date filters encoded into query_text (handled by UI), they will be included in MATCH
        rows = cur.execute(q, (query_text, limit)).fetchall()
        conn.close()
        return rows
    except Exception:
        # fallback: basic LIKE search
        rows = cur.execute("SELECT id as page_version_id, content_hash, substr(content_text, 1, 200) as snippet, site_id, archived_at FROM PageVersions WHERE content_text LIKE ? LIMIT ?", (f'%{query_text}%', limit)).fetchall()
        conn.close()
        return rows

def latest_page_version(page_id):
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM PageVersions WHERE page_id=? ORDER BY archived_at DESC LIMIT 1", (page_id,)).fetchone()
    conn.close()
    return row

def insert_change(old_vid, new_vid, added_text, removed_text, new_image_urls):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO Changes (page_version_old_id, page_version_new_id, added_text, removed_text, new_image_urls, detected_at) VALUES (?, ?, ?, ?, ?, ?)",
                (old_vid, new_vid, added_text, removed_text, json.dumps(new_image_urls), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
