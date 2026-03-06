from flask import Flask, request, jsonify, send_file
import os
import uuid

app = Flask(__name__)
STORE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
os.makedirs(STORE, exist_ok=True)


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
from flask import Flask, request, jsonify
from pathlib import Path
import os
import time
import base64

app = Flask(__name__)
DATA_DIR = Path(os.environ.get('OTSD_DATA_DIR', '/data/ots'))
DATA_DIR.mkdir(parents=True, exist_ok=True)


@app.route('/stamp', methods=['POST'])
def stamp():
    data = request.get_json(force=True)
    h = data.get('hash')
    if not h:
        return jsonify({'error': 'hash required'}), 400
    ts = int(time.time())
    fname = DATA_DIR / f"{h}.{ts}.ots"
    fname.write_text(h)
    return jsonify({'ots_path': str(fname), 'status': 'stamped'})


@app.route('/upgrade', methods=['POST'])
def upgrade():
    data = request.get_json(force=True)
    path = data.get('ots_path')
    if not path:
        return jsonify({'error': 'ots_path required'}), 400
    p = Path(path)
    if not p.exists():
        return jsonify({'error': 'not found'}), 404
    # simulate upgrade by appending a line
    p.write_text(p.read_text() + '\nupgraded')
    return jsonify({'status': 'upgraded', 'ots_path': str(p)})


@app.route('/fetch', methods=['POST'])
def fetch():
    data = request.get_json(force=True)
    path = data.get('ots_path') or data.get('fname')
    if not path:
        return jsonify({'error': 'ots_path or fname required'}), 400
    p = Path(path)
    if not p.exists():
        return jsonify({'error': 'not found'}), 404
    # return base64-encoded content for safe transport
    content = p.read_bytes()
    return jsonify({'content_b64': base64.b64encode(content).decode('ascii'), 'fname': p.name})


@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json(force=True)
    path = data.get('ots_path')
    p = Path(path)
    if not p.exists():
        return jsonify({'error': 'not found'}), 404
    return jsonify({'status': 'ok', 'verified': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 16000)))
