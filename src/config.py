import json
from pathlib import Path

CFG_PATH = Path(__file__).resolve().parents[1] / 'watcher_config.json'

def read_config(strict: bool = False):
    if not CFG_PATH.exists():
        return {}
    try:
        return json.loads(CFG_PATH.read_text(encoding='utf-8'))
    except Exception as e:
        if strict:
            # A read-modify-write must never treat a corrupt file as empty. Doing
            # so writes {} back over it and silently loses every other key.
            raise ValueError('%s is not valid JSON: %s' % (CFG_PATH, e)) from e
        return {}

def write_config(d: dict):
    CFG_PATH.write_text(json.dumps(d, indent=2), encoding='utf-8')

def set_archive_index(path: str):
    cfg = read_config(strict=True)
    cfg['archivebox_index_json'] = path
    write_config(cfg)

def get_archive_index():
    cfg = read_config()
    return cfg.get('archivebox_index_json')
