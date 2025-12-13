from flask import Flask, render_template_string, abort, request, redirect, url_for, jsonify
from . import db
try:
  from prometheus_client import generate_latest, Counter, CollectorRegistry, CONTENT_TYPE_LATEST
  PROM_AVAILABLE = True
  registry = CollectorRegistry()
  SEARCH_COUNTER = Counter('wps_search_requests_total', 'Total search requests', registry=registry)
except Exception:
  PROM_AVAILABLE = False

app = Flask(__name__)

INDEX_TMPL = '''
<h1>Watched sites</h1>
<ul>
{% for s in sites %}
  <li><a href="/site/{{s.id}}">{{s.normalized_root}}</a> — pages: {{s.page_count}} — last crawled: {{s.last_crawled}} — <a href="/site/{{s.id}}/edit">edit</a></li>
{% endfor %}
</ul>
'''

SITE_TMPL = '''
<h1>Site {{site.normalized_root}}</h1>
<p>Last crawled: {{site.last_crawled}}</p>
<h2>Pages</h2>
<ul>
{% for p in pages %}
  <li>{{p.normalized_url}} — last archived: {{p.last_archived}} — versions: {{p.versions}}</li>
{% endfor %}
</ul>
<p><a href="/">Back</a></p>
'''

EDIT_TMPL = '''
<h1>Edit site {{site.normalized_root}}</h1>
<form method="post">
  <label>Active: <input type="checkbox" name="active" {% if site.active %}checked{% endif %}></label><br>
  <label>User Agent: <input type="text" name="user_agent" value="{{site.user_agent or ''}}" size=60></label><br>
  <label>Crawl Delay (seconds): <input type="number" name="crawl_delay" value="{{site.crawl_delay or 1}}"></label><br>
  <input type="submit" value="Save">
</form>
<p><a href="/site/{{site.id}}">Back</a></p>
'''

SEARCH_TMPL = '''
<h1>Search</h1>
<form method="get" action="/search">
  <input name="q" value="{{q or ''}}" size=60>
  <input type="submit" value="Search">
</form>
{% if results %}
  <h2>Results ({{total}})</h2>
  <div style="display:flex;gap:2rem">
    <div style="min-width:160px">
      <h3>Facets</h3>
      <h4>Sites</h4>
      <ul>
      {% for sid,count in site_facets.items() %}
        <li><a href="/search?q={{q}}&site={{sid}}">{{site_names.get(sid, 'Site '+sid|string)}}</a> ({{count}})</li>
      {% endfor %}
      </ul>
      <h4>By month</h4>
      <ul>
      {% for ym,count in date_facets.items() %}
        <li><a href="/search?q={{q}}&date={{ym}}">{{ym}}</a> ({{count}})</li>
      {% endfor %}
      </ul>
    </div>
    <div>
      <ul>
      {% for r in results %}
        <li>PV {{r.page_version_id}} (site {{r.site_id}}) — {{r.archived_at}}<br>{{r.snippet}}</li>
      {% endfor %}
      </ul>
      <div style="margin-top:1rem">
        {% if page>1 %}
          <a href="/search?q={{q}}&page={{page-1}}&per_page={{per_page}}">Previous</a>
        {% endif %}
        &nbsp; Page {{page}} &nbsp;
        {% if page*per_page < total %}
          <a href="/search?q={{q}}&page={{page+1}}&per_page={{per_page}}">Next</a>
        {% endif %}
      </div>
    </div>
  </div>
{% endif %}
<p><a href="/">Back</a></p>
'''


@app.route('/')
def index():
    conn = db.get_conn()
    cur = conn.cursor()
    sites = cur.execute('SELECT s.id, s.normalized_root, s.last_crawled, COUNT(p.id) as page_count FROM Sites s LEFT JOIN Pages p ON p.site_id=s.id GROUP BY s.id').fetchall()
    conn.close()
    return render_template_string(INDEX_TMPL, sites=sites)


@app.route('/site/<int:site_id>')
def site_view(site_id):
    conn = db.get_conn()
    cur = conn.cursor()
    site = cur.execute('SELECT * FROM Sites WHERE id=?', (site_id,)).fetchone()
    if not site:
        abort(404)
    pages = cur.execute('SELECT p.id, p.normalized_url, p.last_archived, (SELECT COUNT(*) FROM PageVersions pv WHERE pv.page_id=p.id) as versions FROM Pages p WHERE p.site_id=?', (site_id,)).fetchall()
    conn.close()
    return render_template_string(SITE_TMPL, site=site, pages=pages)


@app.route('/site/<int:site_id>/edit', methods=['GET', 'POST'])
def site_edit(site_id):
  conn = db.get_conn()
  cur = conn.cursor()
  site = cur.execute('SELECT * FROM Sites WHERE id=?', (site_id,)).fetchone()
  if not site:
    abort(404)
  if request.method == 'POST':
    active = 1 if request.form.get('active') == 'on' else 0
    user_agent = request.form.get('user_agent') or None
    try:
      crawl_delay = int(request.form.get('crawl_delay') or 1)
    except Exception:
      crawl_delay = 1
    cur.execute('UPDATE Sites SET active=?, user_agent=?, crawl_delay=? WHERE id=?', (active, user_agent, crawl_delay, site_id))
    conn.commit()
    conn.close()
    return redirect(url_for('site_view', site_id=site_id))
  conn.close()
  return render_template_string(EDIT_TMPL, site=site)


@app.route('/search')
def search():
  q = request.args.get('q')
  results = []
  page = int(request.args.get('page') or 1)
  per_page = int(request.args.get('per_page') or 10)
  if q:
    # optional filters
    site_filter = request.args.get('site')
    date_filter = request.args.get('date')
    # basic input validation
    if len(q) > 200:
      return render_template_string('<p>Query too long</p>'), 400
    rows = db.search_page_versions(q, limit=200)
    # convert sqlite rows to dict-like
    for r in rows:
      results.append({
        'page_version_id': r['page_version_id'],
        'content_hash': r['content_hash'],
        'site_id': r['site_id'] if 'site_id' in r.keys() else None,
        'archived_at': r['archived_at'] if 'archived_at' in r.keys() else None,
        'snippet': r['snippet'] if 'snippet' in r.keys() else ''
      })
    # apply simple filters
    if site_filter:
      results = [r for r in results if str(r.get('site_id')) == str(site_filter)]
    if date_filter:
      results = [r for r in results if (r.get('archived_at') or '').startswith(date_filter)]
  total = len(results)
  # pagination slice
  start = (page-1) * per_page
  end = start + per_page
  paged = results[start:end]
  # compute simple facets and map site ids to normalized_root for display
  site_facets = {}
  date_facets = {}
  site_names = {}
  if results:
    conn = db.get_conn()
    cur = conn.cursor()
    srows = cur.execute('SELECT id, normalized_root FROM Sites').fetchall()
    for s in srows:
      site_names[s['id']] = s['normalized_root']
    conn.close()
  for r in paged:
    sid = r.get('site_id')
    site_facets[sid] = site_facets.get(sid, 0) + 1
    dt = r.get('archived_at') or ''
    ym = dt[:7] if dt else 'unknown'
    date_facets[ym] = date_facets.get(ym, 0) + 1
  return render_template_string(SEARCH_TMPL, q=q, results=paged, site_facets=site_facets, date_facets=date_facets, site_names=site_names, page=page, per_page=per_page, total=total)


@app.route('/health')
def health():
    # basic health: DB accessible
    try:
        conn = db.get_conn()
        conn.execute('SELECT 1').fetchone()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception:
        return jsonify({'status': 'error'}), 500


@app.route('/metrics')
def metrics():
    if not PROM_AVAILABLE:
        return 'Prometheus client not installed', 503
    # expose metrics
    return generate_latest(registry), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route('/admin/metrics')
def admin_metrics():
    # aggregate counts from DB
    conn = db.get_conn()
    cur = conn.cursor()
    sites = cur.execute('SELECT COUNT(*) as c FROM Sites').fetchone()['c']
    pages = cur.execute('SELECT COUNT(*) as c FROM Pages').fetchone()['c']
    pvs = cur.execute('SELECT COUNT(*) as c FROM PageVersions').fetchone()['c']
    changes = cur.execute('SELECT COUNT(*) as c FROM Changes').fetchone()['c']
    conn.close()
    return jsonify({'sites': sites, 'pages': pages, 'page_versions': pvs, 'changes': changes})


@app.route('/admin/global_preservation_health')
def global_preservation_health():
    conn = db.get_conn()
    cur = conn.cursor()
    # aggregate preservation metrics
    avg_survival = cur.execute('SELECT AVG(knowledge_survival_rate) as avg FROM PreservationMetrics').fetchone()['avg']
    top_sites = cur.execute('SELECT id, normalized_root, cultural_significance_score FROM Sites ORDER BY cultural_significance_score DESC LIMIT 10').fetchall()
    forest_count = cur.execute('SELECT COUNT(*) as c FROM MerkleForest').fetchone()['c']
    conn.close()
    top = [{'id': s['id'], 'root': s['normalized_root'], 'score': s['cultural_significance_score']} for s in top_sites]
    return jsonify({'avg_knowledge_survival_rate': avg_survival or 0.0, 'top_sites_by_cultural_significance': top, 'merkle_forest_count': forest_count})


@app.route('/admin/crisis_mode', methods=['GET', 'POST'])
def admin_crisis_mode():
    conn = db.get_conn()
    cur = conn.cursor()
    if request.method == 'POST':
        action = request.form.get('action') or request.json.get('action') if request.is_json else request.form.get('action')
        note = request.form.get('note') or (request.json.get('note') if request.is_json else None)
        if action == 'activate':
            cur.execute("INSERT INTO CrisisStatus (active, activated_at, note) VALUES (1, datetime('now'), ?)", (note,))
            conn.commit()
            conn.close()
            return jsonify({'status': 'activated'})
        elif action == 'deactivate':
            cur.execute("INSERT INTO CrisisStatus (active, activated_at, note) VALUES (0, datetime('now'), ?)", (note,))
            conn.commit()
            conn.close()
            return jsonify({'status': 'deactivated'})
        else:
            conn.close()
            return jsonify({'error': 'unknown action'}), 400
    # GET: return last crisis status
    row = cur.execute('SELECT * FROM CrisisStatus ORDER BY id DESC LIMIT 1').fetchone()
    conn.close()
    if not row:
        return jsonify({'active': False})
    return jsonify({'active': bool(row['active']), 'activated_at': row['activated_at'], 'note': row['note']})


@app.route('/api/search')
def api_search():
  q = request.args.get('q')
  if not q:
    return {'results': []}
  rows = db.search_page_versions(q, limit=100)
  out = []
  for r in rows:
    out.append({
      'page_version_id': r['page_version_id'],
      'content_hash': r['content_hash'],
      'site_id': r['site_id'] if 'site_id' in r.keys() else None,
      'archived_at': r['archived_at'] if 'archived_at' in r.keys() else None,
      'snippet': r['snippet'] if 'snippet' in r.keys() else ''
    })
  return {'results': out}


@app.route('/api/merkle/push', methods=['POST'])
def api_merkle_push():
    data = request.get_json(force=True)
    if not data:
        return {'error': 'no data'}, 400
    delta = data.get('delta')
    signature = data.get('signature')
    if not delta or not signature:
        return {'error': 'delta and signature required'}, 400
    # verify and check sequence ordering
    from .merkle_sync import verify_delta, store_delta, apply_delta
    try:
        ok = verify_delta(delta, signature)
    except Exception as e:
        return {'error': 'verify-failed', 'detail': str(e)}, 400
    if not ok:
        return {'error': 'invalid signature'}, 400
    # simple ordering checks: validate lamport and sequence if present
    seq = delta.get('sequence') or 0
    lam = delta.get('lamport') or 0
    site_id = delta.get('site_id')
    if seq or lam:
        conn = db.get_conn()
        cur = conn.cursor()
        row = cur.execute('SELECT MAX(sequence) as m, MAX(lamport) as lm FROM MerkleDeltas WHERE site_id=?', (site_id,)).fetchone()
        conn.close()
        current = row['m'] or 0
        current_lam = row['lm'] or 0
        # reject obvious replays
        if seq and seq <= current:
            return {'error': 'obsolete sequence', 'current': current}, 409
        if lam and lam <= current_lam:
            return {'error': 'obsolete lamport', 'current_lam': current_lam}, 409
    # store delta
    try:
        vid = store_delta(delta, signature)
    except Exception as e:
        return {'error': 'store-failed', 'detail': str(e)}, 500
    # apply delta (best-effort)
    applied = False
    try:
        applied = apply_delta(delta)
    except Exception:
        applied = False
    return {'stored_id': vid, 'applied': bool(applied)}


@app.route('/api/merkle/pull')
def api_merkle_pull():
    site = request.args.get('site')
    if not site:
        return {'error': 'site required'}, 400
    conn = db.get_conn()
    cur = conn.cursor()
    row = cur.execute('SELECT * FROM MerkleForest WHERE site_id=? ORDER BY last_updated DESC LIMIT 1', (site,)).fetchone()
    conn.close()
    if not row:
        return {'site_id': site, 'root': '', 'tree_blob': {}}
    import json
    return {'site_id': row['site_id'], 'root': row['tree_root'], 'tree_blob': json.loads(row['tree_blob'])}
