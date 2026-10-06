"""OpenTimestamps simulator.

This file used to contain two complete Flask programs pasted one after the other,
each with its own `app = Flask(__name__)` and its own `if __name__ == '__main__'`
block. Run as a script, execution reached the first block and stayed inside its
app.run() forever, so the second program was never built and its routes did not
exist.

That mattered because the two halves served different callers. The first served
/ots/submit and /ots/proof/<pid>, which is what scripts/integration_test.py
exercises. The second served /stamp, /upgrade, /fetch and /verify, which is what
the production client src/anchor_ots.py actually calls. So the integration test
passed against a service the real code never talks to, while every production
call 404'd.

Both route sets are kept here on one app, so both callers work.
"""
from flask import Flask, request, jsonify, send_file
from pathlib import Path
import os
import time
import base64
import re
import uuid

app = Flask(__name__)

# Used by the /ots/* routes that scripts/integration_test.py exercises.
STORE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
os.makedirs(STORE, exist_ok=True)

# Used by the /stamp, /upgrade, /fetch and /verify routes that
# src/anchor_ots.py calls.
DATA_DIR = Path(os.environ.get('OTSD_DATA_DIR', '/data/ots'))
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEX_HASH = re.compile(r'[0-9a-fA-F]{1,128}')


def _data_path(path):
    """The resolved path if it lies inside DATA_DIR, else None.

    Paths come from the request body, so without this check /fetch read and
    /upgrade appended to any file the process could reach.
    """
    p = Path(path).resolve()
    return p if p.is_relative_to(DATA_DIR.resolve()) else None


@app.route('/ots/submit', methods=['POST'])
def submit():
    payload = request.get_data()
    pid = str(uuid.uuid4())
    path = os.path.join(STORE, pid + '.proof')
    with open(path, 'wb') as f:
        f.write(payload or b'')
    return jsonify({'id': pid, 'path': '/proof/' + pid}), 201


@app.route('/ots/proof/<pid>')
def get_proof(pid):
    path = os.path.join(STORE, pid + '.proof')
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    return send_file(path, mimetype='application/octet-stream')


@app.route('/stamp', methods=['POST'])
def stamp():
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'error': 'body must be a JSON object'}), 400
    h = data.get('hash')
    if not h:
        return jsonify({'error': 'hash required'}), 400
    if not isinstance(h, str) or not HEX_HASH.fullmatch(h):
        return jsonify({'error': 'hash must be hex'}), 400
    ts = int(time.time())
    fname = DATA_DIR / f"{h}.{ts}.ots"
    fname.write_text(h)
    return jsonify({'ots_path': str(fname), 'status': 'stamped'})


@app.route('/upgrade', methods=['POST'])
def upgrade():
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'error': 'body must be a JSON object'}), 400
    path = data.get('ots_path')
    if not path:
        return jsonify({'error': 'ots_path required'}), 400
    p = _data_path(path)
    if p is None:
        return jsonify({'error': 'path outside data dir'}), 400
    if not p.exists():
        return jsonify({'error': 'not found'}), 404
    # simulate upgrade by appending a line
    p.write_text(p.read_text() + '\nupgraded')
    return jsonify({'status': 'upgraded', 'ots_path': str(p)})


@app.route('/fetch', methods=['POST'])
def fetch():
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'error': 'body must be a JSON object'}), 400
    path = data.get('ots_path') or data.get('fname')
    if not path:
        return jsonify({'error': 'ots_path or fname required'}), 400
    p = _data_path(path)
    if p is None:
        return jsonify({'error': 'path outside data dir'}), 400
    if not p.exists():
        return jsonify({'error': 'not found'}), 404
    # return base64-encoded content for safe transport
    content = p.read_bytes()
    return jsonify({'content_b64': base64.b64encode(content).decode('ascii'), 'fname': p.name})


@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'error': 'body must be a JSON object'}), 400
    path = data.get('ots_path')
    # Guard the missing field. Path(None) raises TypeError, which used to surface
    # as a 500 rather than the 400 the other routes return for the same mistake.
    if not path:
        return jsonify({'error': 'ots_path required'}), 400
    p = _data_path(path)
    if p is None:
        return jsonify({'error': 'path outside data dir'}), 400
    if not p.exists():
        return jsonify({'error': 'not found'}), 404
    return jsonify({'status': 'ok', 'verified': True})


if __name__ == '__main__':
    # Defaults to 8080, which docker-compose.integration.yml publishes.
    # docker-compose.prod.yml sets PORT=16000 and publishes that instead.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
