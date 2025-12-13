"""Knowledge extraction scaffold. Uses spaCy when available, else a heuristic.

Creates DB tables: KnowledgeEntities, EntityRelations, SemanticChanges and provides
`run_extraction(limit)` to process recent PageVersions.
"""
from .db import get_conn
from datetime import datetime
import os
import subprocess
try:
    import spacy
    _HAS_SPACY = True
    try:
        nlp = spacy.load('en_core_web_sm')
    except Exception:
        # model missing; mark as not available
        _HAS_SPACY = False
        nlp = None
except Exception:
    _HAS_SPACY = False
    nlp = None


def ensure_spacy_model(model_name: str = 'en_core_web_sm') -> bool:
    """Ensure a spaCy model is installed. Returns True if available afterwards."""
    global _HAS_SPACY, nlp
    if not _HAS_SPACY:
        try:
            import spacy
            _HAS_SPACY = True
        except Exception:
            return False
    try:
        nlp = spacy.load(model_name)
        return True
    except Exception:
        # try to download via spacy CLI
        try:
            subprocess.run(["python", "-m", "spacy", "download", model_name], check=True)
            nlp = spacy.load(model_name)
            _HAS_SPACY = True
            return True
        except Exception:
            return False


def init_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS KnowledgeEntities (
        id INTEGER PRIMARY KEY,
        page_version_id INTEGER,
        entity_type TEXT,
        entity_text TEXT,
        confidence REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS EntityRelations (
        id INTEGER PRIMARY KEY,
        source_id INTEGER,
        target_id INTEGER,
        relationship_type TEXT,
        confidence REAL
    );
    CREATE TABLE IF NOT EXISTS SemanticChanges (
        id INTEGER PRIMARY KEY,
        entity_id INTEGER,
        change_type TEXT,
        before_state TEXT,
        after_state TEXT,
        detected_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    conn.commit()
    conn.close()


def extract_entities_from_text(text: str):
    if _HAS_SPACY:
        doc = nlp(text)
        ents = [(ent.label_, ent.text, float(ent.kb_id_ and 1.0 or 0.9)) for ent in doc.ents]
        return ents
    # fallback: naive capitalized words heuristic
    words = set()
    for w in text.split():
        if w.istitle() and len(w) > 3:
            words.add(w.strip('.,'))
        if len(words) >= 10:
            break
    return [('ENTITY', w, 0.5) for w in words]


def run_extraction(limit=50):
    init_tables()
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute('SELECT id, content_text FROM PageVersions ORDER BY archived_at DESC LIMIT ?', (limit,)).fetchall()
    for r in rows:
        pv_id = r['id']
        text = r['content_text'] or ''
        ents = extract_entities_from_text(text)
        for etype, etext, conf in ents:
            cur.execute('INSERT INTO KnowledgeEntities (page_version_id, entity_type, entity_text, confidence, created_at) VALUES (?, ?, ?, ?, ?)', (pv_id, etype, etext, conf, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
