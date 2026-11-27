"""Loopback visibility server. Only local draft writes; no production commands."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import re
from urllib.parse import urlsplit, parse_qs
from . import bridge, data, history, model, places, retained_notes, templates

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).parent / 'static'
DEFAULT_STORE = ROOT / 'autonomy/runtime/local_dashboard_v3_preview'
US_STATES = frozenset('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC'.split())


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(6) + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


class Conflict(Exception):
    pass


class Dashboard:
    def __init__(self, store=DEFAULT_STORE, db=data.PRODUCTION_DB, reader=bridge.read):
        self.store, self.db, self.reader = Path(store), Path(db), reader
        self.guard = threading.RLock()
        self.refresh_guard = threading.Lock()
        self.city_guard = threading.Lock()
        self.draft_guard = threading.Lock()
        self.cookie = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.cache_error = None
        try:
            self.cache = load_json(self.store / 'observations.json', {})
            if not isinstance(self.cache, dict):
                raise ValueError()
        except (ValueError, OSError):
            self.cache = {}
            self.cache_error = '旧快照无法读取，需要重新刷新。'

    def observe(self, key, action):
        try:
            value = action()
        except Exception as error:
            with self.guard:
                value = dict(self.cache.get(key, {}))
            value.update(error='读取失败：' + type(error).__name__, last_attempt_at=data.now())
        with self.guard:
            self.cache[key] = value
        return value

    def catalog(self):
        return self.observe('catalog', lambda: {'data': data.catalog(self.db), 'observed_at': data.now(),
            'last_attempt_at': data.now(), 'error': None, 'source': '正式库 · 限定字段只读'})

    def save_cache(self):
        with self.guard:
            atomic_json(self.store / 'observations.json', self.cache)

    def refresh(self):
        if not self.refresh_guard.acquire(blocking=False):
            raise Conflict('正在读取最新状态，请稍候。')
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                jobs = [pool.submit(self.observe, key, lambda op=op: self.reader(op))
                        for key, op in [('health', 'health'), ('runtime', 'runtime'), ('provider', 'provider-audit')]]
                jobs.append(pool.submit(self.catalog))
                for job in jobs:
                    job.result()
            self.save_cache()
            return self.snapshot()
        finally:
            self.refresh_guard.release()

    def snapshot(self):
        with self.guard:
            cache = json.loads(json.dumps(self.cache))
        for item in cache.values():
            if isinstance(item, dict):
                item['fresh'] = model.fresh(item)
        runtime = cache.get('runtime', {}).get('data', {})
        return {'observations': {k: cache.get(k, {}) for k in ('health', 'runtime', 'provider', 'catalog')},
                'runs': model.runs(runtime), 'server_time': data.now(), 'cache_error': self.cache_error,
                'capabilities': {'production_read_only': True, 'drafts': True, 'submit_plan': False,
                    'reason': '正式计划写入入口尚未接通；本地草稿不会改变下一次生产搜索。'}}

    def city(self, city_id, force=False):
        if not 1 <= city_id <= 9999:
            raise ValueError('城市编号无效')
        key = 'city:' + str(city_id)
        with self.city_guard:
            with self.guard:
                value = self.cache.get(key, {})
            if force or not model.fresh(value):
                value = self.observe(key, lambda: self.reader('city', city_id))
                self.save_cache()
            with self.guard:
                recent = model.runs(self.cache.get('runtime', {}).get('data', {}))
            latest = next((r for r in recent if r['city_id'] == city_id), None)
            try:
                health = self.cache.get('health', {})
                if (not model.fresh(value) or not model.fresh(health)
                        or not model.diagnostic_rules_match(value.get('data', {}), health.get('data', {}))):
                    diagnostics = {'available': False, 'items': [], 'reason': '规则版本或数据时效未核实'}
                else:
                    diagnostics = data.linked_gate_diagnostics(self.db, city_id,
                        (value.get('data', {}).get('blocking_attribution') or {}).get('linked_backlog_retry_refs', []))
            except Exception:
                diagnostics = {'available': False, 'items': []}
            try:
                provider = (value.get('data', {}).get('ruleset') or {}).get('provider')
                totals = data.city_history_totals(self.db, city_id, provider)
            except Exception:
                totals = {'available': False}
            return {**value, 'fresh': model.fresh(value), 'diagnostics': diagnostics, 'history_totals': totals,
                    'explanation': model.explain(value.get('data', {}), latest), 'latest_run': latest}

    def draft(self):
        value = load_json(self.store / 'draft.json', {'revision': 0, 'plan': None})
        if not isinstance(value, dict) or type(value.get('revision')) is not int:
            raise ValueError('草稿文件损坏；请保留文件并检查，未覆盖。')
        return value | {'accepted_by_production': False}

    def save_draft(self, value):
        if set(value) != {'revision', 'plan'} or type(value['revision']) is not int:
            raise ValueError('草稿格式无效')
        plan = value['plan']
        if plan is not None:
            if not isinstance(plan, dict) or set(plan) != {'name', 'author', 'concurrency', 'cities'}:
                raise ValueError('计划字段无效')
            if not all(isinstance(plan[k], str) and 0 < len(plan[k].strip()) <= 100 for k in ('name', 'author')):
                raise ValueError('计划名称或制定者无效')
            if type(plan['concurrency']) is not int or not 1 <= plan['concurrency'] <= 20:
                raise ValueError('并发数无效')
            if not isinstance(plan['cities'], list) or not 1 <= len(plan['cities']) <= 100:
                raise ValueError('城市清单无效')
            cities = data.catalog(self.db)['cities']
            by_id = {c['id']: c for c in cities}
            seen = set()
            normalized = []
            for item in plan['cities']:
                required = {'city_id', 'types', 'sources', 'keywords', 'boundary', 'minutes', 'request_limit', 'page_limit'}
                if not isinstance(item, dict) or not required <= set(item) or set(item) - required - {'city_name', 'state_code'}:
                    raise ValueError('城市范围无效')
                cid = item['city_id']
                if cid is None:
                    name, code = item.get('city_name'), item.get('state_code')
                    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,79}", name.strip()) or code not in US_STATES:
                        raise ValueError('请输入有效的美国城市英文名及州')
                    name = ' '.join(name.strip().split())
                    matches = [c for c in cities if c['state'] == code and c['city'].casefold() == name.casefold()]
                    if len(matches) > 1:
                        raise ValueError('同州同名城市有多个记录，请选择现有城市编号')
                    city = matches[0] if matches else {'id': None, 'city': name, 'state': code,
                            'timezone': None, 'status': None, 'started_at': None, 'completed_at': None}
                    cid = city['id']
                elif type(cid) is int and cid in by_id:
                    city = by_id[cid]
                else:
                    raise ValueError('城市不存在')
                key = (city['state'], ' '.join(city['city'].split()).casefold())
                if key in seen:
                    raise ValueError('草稿中存在重复城市')
                seen.add(key)
                if any(not isinstance(item[k], str) or len(item[k]) > 500 for k in ('types', 'sources', 'keywords', 'boundary')):
                    raise ValueError('范围内容无效')
                if any(item[k] is not None and (type(item[k]) is not int or not 1 <= item[k] <= 100000) for k in ('minutes', 'request_limit', 'page_limit')):
                    raise ValueError('额度无效')
                normalized.append(dict(item, city_id=cid, city=city['city'], state=city['state'], timezone=city['timezone'],
                    existing_status=city['status'], started_at=city['started_at'], completed_at=city['completed_at']))
            plan = {'name': plan['name'].strip(), 'author': plan['author'].strip(),
                    'concurrency': plan['concurrency'], 'cities': normalized}
        with self.draft_guard:
            current = self.draft()
            if current['revision'] != value['revision']:
                raise Conflict('另一页面已修改草稿，请刷新后再保存。')
            saved = {'revision': current['revision'] + 1, 'plan': plan, 'saved_at': data.now(),
                     'accepted_by_production': False}
            atomic_json(self.store / 'draft.json', saved)
            return saved


def handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'LocalDiscovery/1'

        def log_message(self, *args):
            pass  # Do not log business data or session material.

        def send(self, status, body, mime='application/json; charset=utf-8', session=False):
            content = json.dumps(body, ensure_ascii=False).encode('utf-8') if isinstance(body, (dict, list)) else body
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if session:
                self.send_header('Set-Cookie', f'dashboard_session={app.cookie}; HttpOnly; SameSite=Strict; Path=/')
            self.end_headers()
            self.wfile.write(content)

        def trusted(self, session=True, write=False):
            expected = '127.0.0.1:' + str(self.server.server_address[1])
            if self.headers.get('Host') != expected:
                return False
            origin = self.headers.get('Origin')
            if origin is not None and origin != 'http://' + expected:
                return False
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return False
            if session:
                cookie = SimpleCookie()
                try:
                    cookie.load(self.headers.get('Cookie', ''))
                except Exception:
                    return False
                token = cookie.get('dashboard_session')
                if not token or not secrets.compare_digest(token.value, app.cookie):
                    return False
            if write and not secrets.compare_digest(self.headers.get('X-Dashboard-Token', ''), app.csrf):
                return False
            return True

        def do_GET(self):
            parsed = urlsplit(self.path)
            public = parsed.path in {'/', '/app.js', '/history.js', '/templates.js', '/retained-notes.js', '/style.css'}
            if not self.trusted(session=not public):
                return self.send(403, {'error': '仅允许本机已打开的看板访问。'})
            try:
                if public:
                    name, mime = {'/': ('index.html', 'text/html; charset=utf-8'),
                        '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                        '/history.js': ('history.js', 'text/javascript; charset=utf-8'),
                        '/templates.js': ('templates.js', 'text/javascript; charset=utf-8'),
                        '/retained-notes.js': ('retained-notes.js', 'text/javascript; charset=utf-8'),
                        '/style.css': ('style.css', 'text/css; charset=utf-8')}[parsed.path]
                    return self.send(200, (ASSETS / name).read_bytes(), mime, session=parsed.path == '/')
                args = parse_qs(parsed.query)
                one = lambda key, default='': args.get(key, [default])[0]
                if parsed.path == '/api/session':
                    result = {'csrf': app.csrf}
                elif parsed.path == '/api/snapshot':
                    result = app.snapshot()
                elif parsed.path == '/api/places':
                    code = one('state')
                    if code not in US_STATES:
                        raise ValueError('invalid state')
                    catalog = app.catalog()
                    result = {'places': places.for_state(code, catalog.get('data', {}).get('cities', [])),
                              'history_available': not bool(catalog.get('error')),
                              'history_observed_at': catalog.get('observed_at'), 'source': places.SOURCE}
                elif parsed.path == '/api/city':
                    result = app.city(int(one('id')), one('refresh') == '1')
                elif parsed.path == '/api/merchants':
                    result = data.merchants(app.db, int(one('city')), int(one('page', '1')),
                        one('search'), one('status'), one('email') == '1')
                elif parsed.path == '/api/retained':
                    result = data.retained(app.db, int(one('city')), int(one('page', '1')),
                        one('search'), one('reason'))
                elif parsed.path == '/api/retained-notes':
                    result = retained_notes.read(app.store, app.db, int(one('city')), int(one('id')))
                elif parsed.path == '/api/retained-saved':
                    result = retained_notes.saved_for_city(app.store, int(one('city')))
                elif parsed.path == '/api/history':
                    city = one('city')
                    result = history.inventory(app.db, int(one('page', '1')), int(city) if city else None)
                elif parsed.path == '/api/city-request-audit':
                    result = history.city_request_audit(app.db, int(one('city')), int(one('page', '1')))
                elif parsed.path == '/api/history-reports':
                    result = history.report_snapshots(app.db.parent.parent / 'output')
                elif parsed.path == '/api/draft':
                    result = app.draft()
                elif parsed.path == '/api/templates':
                    result = templates.read(app.store)
                elif parsed.path == '/api/template-asset':
                    result = templates.asset(app.store, one('id'))
                else:
                    return self.send(404, {'error': '没有这个入口。'})
                self.send(200, result)
            except (ValueError, TypeError):
                self.send(400, {'error': '输入或本地数据格式无效；未改动生产。'})
            except Exception as error:
                self.send(503, {'error': '读取不可用：' + type(error).__name__ + '。没有把失败当作 0。'})

        def do_POST(self):
            if not self.trusted(write=True):
                return self.send(403, {'error': '本机会话或请求来源校验未通过。'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                limit = 2800000 if self.path == '/api/template-asset' else 700000 if self.path == '/api/template-save' else 32000 if self.path == '/api/retained-notes' else 8192
                if not 0 < size <= limit or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError()
                value = json.loads(self.rfile.read(size))
                if not isinstance(value, dict):
                    raise ValueError()
                if self.path == '/api/refresh' and not value:
                    result = app.refresh()
                elif self.path == '/api/draft':
                    result = app.save_draft(value)
                elif self.path == '/api/template-save':
                    result = templates.save(app.store, value)
                elif self.path == '/api/template-asset':
                    result = templates.save_asset(app.store, value)
                elif self.path == '/api/retained-notes':
                    result = retained_notes.save(app.store, app.db, value)
                elif self.path == '/api/retained-capture':
                    if set(value) != {'city_id'}:
                        raise ValueError('invalid capture request')
                    result = retained_notes.capture_city(app.store, app.db, value['city_id'])
                else:
                    return self.send(404, {'error': '该动作未接通；没有执行生产操作。'})
                self.send(200, result)
            except (Conflict, templates.VersionConflict, retained_notes.VersionConflict) as error:
                self.send(409, {'error': str(error)})
            except (ValueError, TypeError, KeyError):
                self.send(400, {'error': '输入或本地数据无效；请刷新核对，未改动生产。'})
            except Exception as error:
                self.send(503, {'error': '操作未完成：' + type(error).__name__ + '；请重新读取状态。'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description='本地商家搜索看板：生产只读，本地计划草稿。')
    parser.add_argument('--port', type=int, default=8792)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or args.port == 8791:
        parser.error('请选择 1024–65535 的独立本地端口，保留 8791。')
    app = Dashboard()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(app))
    print('本地只读看板：http://127.0.0.1:' + str(args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
