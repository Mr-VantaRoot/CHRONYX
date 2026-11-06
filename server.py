#!/usr/bin/env python3
"""CHRONYX's local SQLite API and desktop reminder service."""

import ipaddress
import csv
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent
SERVICE_PORT = 8765
MAX_REQUEST_BYTES = 256 * 1024
MAX_IMPORT_BYTES = 4 * 1024 * 1024
NOTIFICATION_LEASE = timedelta(minutes=2)
LAST_RUN_KEY = 'scheduler_last_run'
NOTIFICATION_KEY = re.compile(
    r'^(?P<id>.+):(?P<field>start|deadline):(?P<tag>\d+[dh])'
    r'(?::(?P<target>\d{4}-\d{2}-\d{2}T.+))?$'
)
ALLOWED_CATEGORIES = {
    'CTF', 'Hackathon', 'AI / ML', 'Robotics', 'Programming',
    'Scholarship', 'Technology', 'Other',
}
ALLOWED_STATUSES = {
    'Interested', 'Registered', 'Registration closed', 'Participating',
    'Completed', 'Cancelled',
}
ALLOWED_PRIORITIES = {'Low', 'Medium', 'High', 'Critical'}


DB_NAME = 'chronyx.sqlite3'
LEGACY_DB_NAME = 'vanta.sqlite3'
MIGRATION_MARKER = '.migrated-from-vanta'


def _resolve_environment(system, environ, home):
    system = system or os.name
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    return system, environ, home


def _data_parent(system, environ, home):
    if system == 'nt':
        roaming = Path(environ.get('APPDATA') or '')
        if not roaming.is_absolute():
            roaming = home / 'AppData' / 'Roaming'
        return roaming
    xdg_home = Path(environ.get('XDG_DATA_HOME') or '')
    if not xdg_home.is_absolute():
        xdg_home = home / '.local/share'
    return xdg_home


def data_directory(system=None, environ=None, home=None):
    system, environ, home = _resolve_environment(system, environ, home)
    return _data_parent(system, environ, home) / ('CHRONYX' if system == 'nt' else 'chronyx')


def legacy_data_directory(system=None, environ=None, home=None):
    """Where releases that were named VANTA kept their data."""
    system, environ, home = _resolve_environment(system, environ, home)
    return _data_parent(system, environ, home) / ('VANTA' if system == 'nt' else 'vanta')


def migrate_legacy_data(data_dir, legacy_dir):
    """Copy the database of a VANTA-named release into the CHRONYX data folder, once.

    Returns 'migrated', 'skipped' (nothing to do) or 'failed'. The old folder is only
    read, never changed or deleted, so a failed or unwanted migration is harmless.
    """
    data_dir, legacy_dir = Path(data_dir), Path(legacy_dir)
    marker = data_dir / MIGRATION_MARKER
    new_db = data_dir / DB_NAME
    legacy_db = legacy_dir / LEGACY_DB_NAME
    if marker.exists() or new_db.exists() or not legacy_db.is_file():
        return 'skipped'
    temporary = data_dir / f'.{DB_NAME}.migrating'
    try:
        temporary.unlink(missing_ok=True)
        source = sqlite3.connect(legacy_db, timeout=10)
        try:
            target = sqlite3.connect(temporary)
            try:
                source.backup(target)  # Consistent even if the old file has a write-ahead log.
            finally:
                target.close()
        finally:
            source.close()
        os.replace(temporary, new_db)
        marker.write_text(f'Copied from {legacy_db}\n', encoding='utf-8')
        print(f'CHRONYX: copied your data from {legacy_db}', file=sys.stderr, flush=True)
        return 'migrated'
    except (OSError, sqlite3.Error) as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        print(f'CHRONYX: could not copy data from {legacy_db}: {error}', file=sys.stderr, flush=True)
        return 'failed'


DATA = data_directory()
DATA.mkdir(parents=True, exist_ok=True)
_LEGACY_DIR = legacy_data_directory()
MIGRATION_STATUS = migrate_legacy_data(DATA, _LEGACY_DIR)
# If copying failed, keep using the old database rather than hiding it behind an empty one.
DB = _LEGACY_DIR / LEGACY_DB_NAME if MIGRATION_STATUS == 'failed' else DATA / DB_NAME


def connect(db_path=None):
    connection = sqlite3.connect(db_path or DB, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA busy_timeout=10000')
    return connection


@contextmanager
def db(db_path=None):
    connection = connect(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _migrate_legacy_deliveries(connection):
    """Translate legacy unscheduled keys to exact keys once during upgrade."""
    standard_windows = {'7d': 604800, '3d': 259200, '1d': 86400, '1h': 3600}
    legacy_rows = connection.execute(
        "SELECT key,sent_at FROM notifications WHERE status='delivered'"
    ).fetchall()
    for row in legacy_rows:
        fields = row['key'].split(':')
        if len(fields) != 3:
            continue
        event_id, field, tag = fields
        if field not in ('start', 'deadline'):
            continue
        seconds = standard_windows.get(tag)
        if seconds is None and tag.endswith('h'):
            try:
                seconds = int(tag[:-1]) * 3600
            except ValueError:
                continue
        if not seconds:
            continue
        event = connection.execute(
            f'SELECT {field} AS target FROM competitions WHERE id=?', (event_id,)
        ).fetchone()
        if not event or not event['target']:
            continue
        try:
            target = datetime.fromisoformat(event['target'].replace('Z', '+00:00'))
            sent = datetime.fromisoformat(row['sent_at'].replace('Z', '+00:00'))
            target = target.replace(tzinfo=timezone.utc) if target.tzinfo is None else target.astimezone(timezone.utc)
            sent = sent.replace(tzinfo=timezone.utc) if sent.tzinfo is None else sent.astimezone(timezone.utc)
        except (AttributeError, TypeError, ValueError):
            continue
        # The old scheduler only inserted a row while inside this 60 second
        # window. Seed an exact identity now, so later reschedules always get
        # a new key even if the legacy timestamp itself is retained.
        distance = (target - sent).total_seconds()
        if seconds - 60 < distance <= seconds:
            exact_key = f'{event_id}:{field}:{tag}:{target.isoformat(timespec="seconds")}'
            connection.execute(
                "INSERT OR IGNORE INTO notifications(key,sent_at,status,attempts,claimed_at,delivered_at) "
                "VALUES(?,?,'delivered',1,?,?)",
                (exact_key, row['sent_at'], row['sent_at'], row['sent_at']),
            )


def initialize_database(db_path=None):
    """Create the current schema and apply additive migrations in place."""
    with db(db_path) as connection:
        current_version = connection.execute('PRAGMA user_version').fetchone()[0]
        if current_version > 2:
            raise RuntimeError(f'Database schema version {current_version} is newer than this CHRONYX build supports')
        connection.execute('''CREATE TABLE IF NOT EXISTS competitions(
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', category TEXT NOT NULL,
            organizer TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '',
            registrationUrl TEXT NOT NULL DEFAULT '', start TEXT NOT NULL,
            end TEXT NOT NULL DEFAULT '', deadline TEXT NOT NULL DEFAULT '',
            timezone TEXT NOT NULL, status TEXT NOT NULL, priority TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '', created TEXT NOT NULL)''')
        connection.execute('''CREATE TABLE IF NOT EXISTS notifications(
            key TEXT PRIMARY KEY, sent_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'delivered',
            attempts INTEGER NOT NULL DEFAULT 1, claimed_at TEXT,
            delivered_at TEXT, retry_after TEXT, last_error TEXT)''')
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(notifications)')}
        migrations = {
            'status': "TEXT NOT NULL DEFAULT 'delivered'",
            'attempts': 'INTEGER NOT NULL DEFAULT 1',
            'claimed_at': 'TEXT',
            'delivered_at': 'TEXT',
            'retry_after': 'TEXT',
            'last_error': 'TEXT',
        }
        for name, declaration in migrations.items():
            if name not in columns:
                connection.execute(f'ALTER TABLE notifications ADD COLUMN {name} {declaration}')
        # The legacy implementation inserted a row before trying to show the
        # toast. Preserve those rows as delivered to avoid repeat alerts.
        connection.execute("UPDATE notifications SET delivered_at=sent_at WHERE status='delivered' AND delivered_at IS NULL")
        if current_version < 2:
            _migrate_legacy_deliveries(connection)
        connection.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        connection.execute(
            'INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',
            ('reminders', json.dumps({'7d': True, '3d': True, '1d': True, '1h': True, 'customHours': 0})),
        )
        connection.execute('PRAGMA user_version=2')


initialize_database()


def events():
    with db() as connection:
        return [dict(row) for row in connection.execute('SELECT * FROM competitions ORDER BY start')]


def _parse_instant(value, field, required=False):
    if value == '' and not required:
        return ''
    if not isinstance(value, str) or not value:
        raise ValueError(f'{field} must be an ISO 8601 timestamp')
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError(f'{field} must be a valid ISO 8601 timestamp') from error
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError(f'{field} must include a UTC offset')
    return instant.astimezone(timezone.utc).isoformat(timespec='seconds')


def validate_event(value):
    if not isinstance(value, dict):
        raise ValueError('Event must be a JSON object')
    required = ('id', 'name', 'category', 'start', 'timezone', 'status', 'priority', 'created')
    if any(not value.get(key) for key in required):
        raise ValueError('Missing required event fields')

    limits = {
        'id': 128, 'name': 200, 'description': 8000, 'category': 40,
        'organizer': 200, 'website': 2048, 'registrationUrl': 2048,
        'timezone': 128, 'status': 40, 'priority': 20, 'notes': 16000,
    }
    result = {}
    for key, limit in limits.items():
        item = value.get(key, '')
        if not isinstance(item, str) or len(item) > limit:
            raise ValueError(f'{key} must be text no longer than {limit} characters')
        result[key] = item.strip() if key in ('id', 'name', 'category', 'timezone', 'status', 'priority') else item
    if not result['name']:
        raise ValueError('Competition name cannot be blank')
    if result['category'] not in ALLOWED_CATEGORIES:
        raise ValueError('Unknown competition category')
    if result['status'] not in ALLOWED_STATUSES:
        raise ValueError('Unknown registration status')
    if result['priority'] not in ALLOWED_PRIORITIES:
        raise ValueError('Unknown priority')
    try:
        ZoneInfo(result['timezone'])
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError('Timezone must be a valid IANA timezone') from error

    result['start'] = _parse_instant(value.get('start'), 'start', required=True)
    result['end'] = _parse_instant(value.get('end', ''), 'end')
    result['deadline'] = _parse_instant(value.get('deadline', ''), 'deadline')
    result['created'] = _parse_instant(value.get('created'), 'created', required=True)
    if result['end'] and result['end'] < result['start']:
        raise ValueError('End must be at or after start')
    for key in ('website', 'registrationUrl'):
        if result[key]:
            parsed = urlsplit(result[key])
            if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                raise ValueError(f'{key} must be an http or https URL')
    for key in ('description', 'organizer', 'website', 'registrationUrl', 'notes'):
        result.setdefault(key, '')
    return result


def export_csv(items):
    """Render a quoted CSV backup while neutralizing spreadsheet formulas."""
    columns = (
        ('name', 'name'), ('category', 'category'), ('organizer', 'organizer'),
        ('description', 'description'), ('website', 'website'),
        ('registrationUrl', 'registrationUrl'), ('start', 'start'),
        ('end', 'end'), ('deadline', 'deadline'), ('timezone', 'timezone'),
        ('status', 'status'), ('priority', 'priority'), ('notes', 'notes'),
    )
    output = io.StringIO(newline='')
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow([heading for heading, _ in columns])
    for item in items:
        values = []
        for _, key in columns:
            value = str(item.get(key, '') or '')
            if value.startswith(('=', '+', '-', '@', '\t', '\r')):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return output.getvalue()


def _trusted_origin(origin, port=SERVICE_PORT):
    """Trust only this service's own loopback origin (or no Origin at all)."""
    if not origin:
        return True  # Desktop shell and local CLI clients may omit Origin.
    try:
        parsed = urlsplit(origin)
        return (
            parsed.scheme == 'http'
            and parsed.hostname in ('127.0.0.1', 'localhost')
            and parsed.port == port
            and not parsed.username and not parsed.password
            and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
        )
    except ValueError:
        return False


def _request_port(handler):
    server_address = getattr(getattr(handler, 'server', None), 'server_address', None)
    return server_address[1] if server_address else SERVICE_PORT


def frontend_file_path(request_path, root=None):
    """Resolve a static request only within dist and reject dotfiles/symlinks out."""
    root = Path(root or ROOT / 'dist').resolve()
    decoded = unquote(urlsplit(request_path).path)
    if any(part.startswith('.') for part in decoded.split('/')):
        return None
    candidate = root.joinpath(*[part for part in decoded.split('/') if part not in ('', '.', '..')]).resolve()
    return candidate if candidate.is_relative_to(root) else None


class Handler(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'dist'), **kwargs)

    def parse_request(self):
        if not super().parse_request():
            return False
        if not self._check_host():
            return False
        path = urlsplit(self.path).path
        if (path == '/api' or path.startswith('/api/')) and not self._check_origin():
            return False
        if self.command not in ('POST', 'PUT', 'PATCH') and (
            self.headers.get('Transfer-Encoding')
            or self.headers.get('Content-Length') not in (None, '', '0')
        ):
            # The remaining handlers do not consume request bodies. Close after
            # responding so an unexpected body cannot become the next request.
            self.close_connection = True
        return True

    def log_message(self, *args):
        pass

    def end_headers(self):
        if getattr(self, 'close_connection', False):
            self.send_header('Connection', 'close')
        origin = self.headers.get('Origin')
        if origin and _trusted_origin(origin, _request_port(self)):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header(
            'Content-Security-Policy',
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        if urlsplit(self.path).path in ('/', '/index.html'):
            self.send_header('Cache-Control', 'no-store, max-age=0')
        super().end_headers()

    def send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _check_host(self):
        value = self.headers.get('Host', '')
        port = _request_port(self)
        try:
            host = urlsplit(f'//{value}')
            valid = (
                host.hostname in ('127.0.0.1', 'localhost')
                and host.port == port
                and not host.username and not host.password
                and not host.path and not host.query and not host.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            self.close_connection = True
            self.send_json({'error': 'Host must be the local CHRONYX address'}, 403)
            return False
        return True

    def _check_origin(self):
        origin = self.headers.get('Origin')
        if not _trusted_origin(origin, _request_port(self)):
            self.close_connection = True
            self.send_json({'error': 'Requests must come from the local application'}, 403)
            return False
        return True

    def _read_json(self, max_bytes=MAX_REQUEST_BYTES):
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError as error:
            self.close_connection = True
            raise ValueError('Invalid Content-Length') from error
        if length < 1 or length > max_bytes:
            self.close_connection = True
            raise ValueError('Request body is empty or too large')
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                self.close_connection = True
                raise ValueError('Request body was incomplete')
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            self.close_connection = True
            raise ValueError('Request body must contain valid JSON') from error

    def _frontend_unavailable(self, head=False):
        body = b'Frontend not built. Run npm run build.\n'
        self.send_response(503)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def translate_path(self, path):
        return super().translate_path(path)

    def send_head(self):
        root = (ROOT / 'dist').resolve()
        candidate = frontend_file_path(self.path, root)
        if candidate is None:
            self.send_error(404, 'Not found')
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404, 'Directory listing disabled')
        return None

    def do_OPTIONS(self):
        if not self._check_origin():
            return
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path == '/api/export.json':
                raw = json.dumps(events(), ensure_ascii=False, indent=2).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="chronyx-competitions.json"')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == '/api/export.csv':
                raw = export_csv(events()).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="chronyx-competitions.csv"')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == '/api/events':
                return self.send_json(events())
            if path == '/api/settings':
                with db() as connection:
                    row = connection.execute('SELECT value FROM settings WHERE key=?', ('reminders',)).fetchone()
                return self.send_json(json.loads(row['value']) if row else {})
        except (sqlite3.Error, ValueError, json.JSONDecodeError):
            print('CHRONYX API: unable to read local data', flush=True)
            return self.send_json({'error': 'Unable to read local data'}, 500)
        if path == '/api' or path.startswith('/api/'):
            return self.send_json({'error': 'Not found'}, 404)
        if not (ROOT / 'dist').is_dir():
            return self._frontend_unavailable()
        return super().do_GET()

    def do_HEAD(self):
        path = urlsplit(self.path).path
        if path == '/api' or path.startswith('/api/'):
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if not (ROOT / 'dist').is_dir():
            return self._frontend_unavailable(head=True)
        return super().do_HEAD()

    def _write_event(self, created):
        if not self._check_origin():
            return
        try:
            event = validate_event(self._read_json())
            with db() as connection:
                if created:
                    connection.execute('''INSERT INTO competitions(
                        id,name,description,category,organizer,website,registrationUrl,
                        start,end,deadline,timezone,status,priority,notes,created
                    ) VALUES(:id,:name,:description,:category,:organizer,:website,:registrationUrl,
                        :start,:end,:deadline,:timezone,:status,:priority,:notes,:created)''', event)
                else:
                    cursor = connection.execute('''UPDATE competitions SET
                        name=:name,description=:description,category=:category,organizer=:organizer,
                        website=:website,registrationUrl=:registrationUrl,start=:start,end=:end,
                        deadline=:deadline,timezone=:timezone,status=:status,priority=:priority,
                        notes=:notes,created=:created WHERE id=:id''', event)
                    if cursor.rowcount == 0:
                        return self.send_json({'error': 'Competition not found'}, 404)
            return self.send_json(event, 201 if created else 200)
        except sqlite3.IntegrityError as error:
            if created:
                return self.send_json({'error': 'A competition with this ID already exists'}, 409)
            print(f'CHRONYX API: database write failed: {error}', flush=True)
            return self.send_json({'error': 'Unable to save competition'}, 500)
        except (ValueError, sqlite3.Error) as error:
            if isinstance(error, sqlite3.Error):
                print(f'CHRONYX API: database write failed: {error}', flush=True)
                return self.send_json({'error': 'Unable to save competition'}, 500)
            return self.send_json({'error': str(error)}, 400)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == '/api/events/import':
            if not self._check_origin():
                return
            try:
                payload = self._read_json(max_bytes=MAX_IMPORT_BYTES)
                if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
                    raise ValueError('Import must contain an events array')
                rows = payload['events']
                indices = payload.get('indices')
                if indices is None:
                    indices = list(range(len(rows)))
                if not isinstance(indices, list) or len(indices) != len(rows) or any(
                    isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in indices
                ):
                    raise ValueError('Import indices must match the events array')
                if len(rows) > 5000:
                    raise ValueError('An import file may contain at most 5000 events')
                valid, skipped = [], []
                for index, value in zip(indices, rows):
                    try:
                        valid.append(validate_event(value))
                    except ValueError as error:
                        name = value.get('name', '') if isinstance(value, dict) else ''
                        skipped.append({'index': index, 'name': name[:200] if isinstance(name, str) else '', 'reason': str(error)})
                if valid:
                    with db() as connection:
                        connection.executemany('''INSERT INTO competitions(
                            id,name,description,category,organizer,website,registrationUrl,
                            start,end,deadline,timezone,status,priority,notes,created
                        ) VALUES(:id,:name,:description,:category,:organizer,:website,:registrationUrl,
                            :start,:end,:deadline,:timezone,:status,:priority,:notes,:created)
                        ON CONFLICT(id) DO UPDATE SET
                            name=excluded.name,description=excluded.description,category=excluded.category,
                            organizer=excluded.organizer,website=excluded.website,registrationUrl=excluded.registrationUrl,
                            start=excluded.start,end=excluded.end,deadline=excluded.deadline,timezone=excluded.timezone,
                            status=excluded.status,priority=excluded.priority,notes=excluded.notes,created=excluded.created''', valid)
                return self.send_json({'imported': len(valid), 'skipped': skipped})
            except ValueError as error:
                return self.send_json({'error': str(error)}, 400)
            except sqlite3.Error as error:
                print(f'CHRONYX API: import transaction failed: {error}', flush=True)
                return self.send_json({'error': 'Unable to import competitions'}, 500)
        if path == '/api/open':
            if not self._check_origin():
                return
            try:
                payload = self._read_json()
                value = payload.get('url') if isinstance(payload, dict) else None
                parsed = urlsplit(value) if isinstance(value, str) else None
                if not parsed or parsed.scheme not in ('http', 'https') or not parsed.hostname:
                    raise ValueError('Only valid HTTP and HTTPS links can be opened')
                if not webbrowser.open(value, new=2):
                    return self.send_json({'error': 'Could not open the system browser'}, 500)
                return self.send_json({'ok': True})
            except ValueError as error:
                return self.send_json({'error': str(error)}, 400)
        if path != '/api/events':
            self.close_connection = True
            return self.send_json({'error': 'Not found'}, 404)
        return self._write_event(created=True)

    def do_PUT(self):
        if urlsplit(self.path).path != '/api/events':
            self.close_connection = True
            return self.send_json({'error': 'Not found'}, 404)
        return self._write_event(created=False)

    def do_PATCH(self):
        if urlsplit(self.path).path != '/api/settings':
            self.close_connection = True
            return self.send_json({'error': 'Not found'}, 404)
        if not self._check_origin():
            return
        try:
            values = self._read_json()
            if not isinstance(values, dict):
                raise ValueError('Settings must be a JSON object')
            with db() as connection:
                row = connection.execute('SELECT value FROM settings WHERE key=?', ('reminders',)).fetchone()
            try:
                existing = json.loads(row['value']) if row else {}
            except json.JSONDecodeError:
                existing = {}
            defaults = {'7d': True, '3d': True, '1d': True, '1h': True, 'customHours': 0}
            prefs = defaults.copy()
            if isinstance(existing, dict):
                for key in ('7d', '3d', '1d', '1h'):
                    if isinstance(existing.get(key), bool):
                        prefs[key] = existing[key]
                old_custom = existing.get('customHours')
                if isinstance(old_custom, int) and not isinstance(old_custom, bool) and 0 <= old_custom <= 8760:
                    prefs['customHours'] = old_custom
            for key in ('7d', '3d', '1d', '1h'):
                if key in values:
                    if not isinstance(values[key], bool):
                        raise ValueError(f'{key} must be true or false')
                    prefs[key] = values[key]
            if 'customHours' in values:
                hours = values['customHours']
                if isinstance(hours, bool) or not isinstance(hours, int) or not 0 <= hours <= 8760:
                    raise ValueError('customHours must be an integer from 0 to 8760')
                prefs['customHours'] = hours
            with db() as connection:
                connection.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', ('reminders', json.dumps(prefs)))
            return self.send_json(prefs)
        except ValueError as error:
            return self.send_json({'error': str(error)}, 400)
        except sqlite3.Error as error:
            print(f'CHRONYX API: settings write failed: {error}', flush=True)
            return self.send_json({'error': 'Unable to save settings'}, 500)

    def do_DELETE(self):
        path = urlsplit(self.path).path
        prefix = '/api/events/'
        if not path.startswith(prefix) or not path[len(prefix):] or '/' in path[len(prefix):]:
            return self.send_json({'error': 'Not found'}, 404)
        if not self._check_origin():
            return
        ident = unquote(path[len(prefix):])
        try:
            with db() as connection:
                cursor = connection.execute('DELETE FROM competitions WHERE id=?', (ident,))
            if cursor.rowcount == 0:
                return self.send_json({'error': 'Competition not found'}, 404)
            return self.send_json({'ok': True})
        except sqlite3.Error as error:
            print(f'CHRONYX API: delete failed: {error}', flush=True)
            return self.send_json({'error': 'Unable to delete competition'}, 500)


def notification_key(event_id, field, tag, scheduled_at):
    return f'{event_id}:{field}:{tag}:{scheduled_at.astimezone(timezone.utc).isoformat(timespec="seconds")}'


def notification_status(key):
    with db() as connection:
        row = connection.execute('SELECT status,retry_after,claimed_at,delivered_at,attempts,last_error FROM notifications WHERE key=?', (key,)).fetchone()
    return dict(row) if row else None


def _claim_notification(key, now):
    now_text = now.astimezone(timezone.utc).isoformat(timespec='seconds')
    with db() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT * FROM notifications WHERE key=?', (key,)).fetchone()
        if row:
            if row['status'] == 'delivered':
                return False, 0
            if row['status'] == 'pending' and row['claimed_at']:
                claimed = datetime.fromisoformat(row['claimed_at'])
                if now - claimed < NOTIFICATION_LEASE:
                    return False, row['attempts']
            if row['retry_after'] and datetime.fromisoformat(row['retry_after']) > now:
                return False, row['attempts']
            attempts = row['attempts'] + 1
            connection.execute(
                "UPDATE notifications SET status='pending',attempts=?,claimed_at=?,retry_after=NULL,last_error=NULL WHERE key=?",
                (attempts, now_text, key),
            )
            return True, attempts
        connection.execute(
            "INSERT INTO notifications(key,sent_at,status,attempts,claimed_at) VALUES(?,?,'pending',1,?)",
            (key, now_text, now_text),
        )
        return True, 1


def _finish_notification(key, now, delivered, attempts, error=None):
    now_text = now.astimezone(timezone.utc).isoformat(timespec='seconds')
    if delivered:
        with db() as connection:
            connection.execute(
                "UPDATE notifications SET status='delivered',delivered_at=?,retry_after=NULL,last_error=NULL WHERE key=?",
                (now_text, key),
            )
        return
    retry_seconds = min(3600, 60 * (2 ** min(max(attempts - 1, 0), 6)))
    retry_text = (now + timedelta(seconds=retry_seconds)).astimezone(timezone.utc).isoformat(timespec='seconds')
    message = str(error or 'Notification delivery failed')[:500]
    with db() as connection:
        connection.execute(
            "UPDATE notifications SET status='failed',retry_after=?,last_error=? WHERE key=?",
            (retry_text, message, key),
        )
    print(f'CHRONYX notification: delivery failed; retry in {retry_seconds}s ({message})', flush=True)


def _delivery_error_message(error):
    if isinstance(error, subprocess.CalledProcessError):
        detail = (error.stderr or '').strip()
        return f'notify-send exited with status {error.returncode}' + (f': {detail[:300]}' if detail else '')
    if isinstance(error, subprocess.TimeoutExpired):
        return 'notify-send timed out'
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        return 'Windows notification dependency is unavailable'
    if isinstance(error, RuntimeError):
        return str(error)
    return f'{type(error).__name__}: operating system notification request failed'


def notify(title, body, key, system=None, now=None):
    """Attempt a reminder once; return True only after the OS call succeeds."""
    now = now or datetime.now(timezone.utc)
    try:
        claimed, attempts = _claim_notification(key, now)
        if not claimed:
            return False
        if (system or os.name) == 'nt':
            from winotify import Notification
            Notification(app_id='CHRONYX Competition Tracker', title=title, msg=body).show()
        else:
            command = shutil.which('notify-send')
            if not command:
                raise RuntimeError('notify-send is not installed')
            if not (os.environ.get('DBUS_SESSION_BUS_ADDRESS') or os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY')):
                raise RuntimeError('no desktop notification session is available')
            subprocess.run(
                [command, '--app-name=CHRONYX', '--icon=dialog-information', title, body],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                timeout=15, check=True,
            )
        _finish_notification(key, now, True, attempts)
        return True
    except Exception as error:
        try:
            # If claim itself failed, attempts is not available and no row may
            # exist. Logging still makes the database problem diagnosable.
            if 'attempts' in locals() and attempts:
                _finish_notification(key, now, False, attempts, _delivery_error_message(error))
            else:
                print(f'CHRONYX notification: unable to claim delivery ({error})', flush=True)
        except Exception as persistence_error:
            print(f'CHRONYX notification: unable to persist delivery failure ({persistence_error})', flush=True)
        return False


def _reminder_preferences():
    with db() as connection:
        row = connection.execute('SELECT value FROM settings WHERE key=?', ('reminders',)).fetchone()
    try:
        value = json.loads(row['value']) if row else {}
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def format_remaining(seconds):
    """Describe an actual time-to-go, rather than the reminder window's name."""
    seconds = max(int(seconds), 0)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f'{days}d {hours}h' if hours else f'{days}d'
    if hours:
        return f'{hours}h {minutes}m' if minutes else f'{hours}h'
    return f'{max(minutes, 1)}m'


def _read_last_run():
    with db() as connection:
        row = connection.execute('SELECT value FROM settings WHERE key=?', (LAST_RUN_KEY,)).fetchone()
    if not row:
        return None
    try:
        value = datetime.fromisoformat(row['value'])
    except (TypeError, ValueError):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _write_last_run(now):
    with db() as connection:
        connection.execute(
            'INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',
            (LAST_RUN_KEY, now.astimezone(timezone.utc).isoformat(timespec='seconds')),
        )


def run_reminder_check(now=None):
    """Deliver due reminders, one catch-up after downtime, and retry failures.

    A reminder window is "new" only if it opened after the previous scheduler
    run. Events created, imported or edited inside an already-open window are
    therefore silent, while a window that opened while the app was closed gets
    exactly one catch-up (the tightest one) when the app returns.
    """
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    last_run = _read_last_run()
    baseline = last_run if last_run and last_run <= now else now - timedelta(seconds=90)
    prefs = _reminder_preferences()
    windows = [(604800, '7d'), (259200, '3d'), (86400, '1d'), (3600, '1h')]
    custom = prefs.get('customHours', 0)
    if isinstance(custom, int) and not isinstance(custom, bool) and custom > 0:
        if custom * 3600 not in {seconds for seconds, _ in windows}:
            windows.append((custom * 3600, f'{custom}h'))

    with db() as connection:
        persisted_notifications = {
            row['key']: dict(row)
            for row in connection.execute('SELECT key,sent_at,status,retry_after,claimed_at FROM notifications')
        }

    for event in events():
        if event['status'] in ('Completed', 'Cancelled'):
            continue
        for field, label in (('start', 'starts'), ('deadline', 'registration closes')):
            if not event[field]:
                continue
            try:
                target = datetime.fromisoformat(event[field].replace('Z', '+00:00'))
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                target = target.astimezone(timezone.utc)
            except (TypeError, ValueError):
                continue
            delta = (target - now).total_seconds()
            if delta <= 0:
                continue
            opened = [
                (seconds, tag) for seconds, tag in windows
                if prefs.get(tag, tag == f'{custom}h') and delta <= seconds
            ]
            if not opened:
                continue
            # The tightest opened window is the latest reminder point reached;
            # choosing it prevents a second catch-up for an older window.
            seconds, tag = min(opened, key=lambda item: item[0])
            key = notification_key(event['id'], field, tag, target)
            state = persisted_notifications.get(key)
            if state and state['status'] == 'delivered':
                continue
            if state is None and target - timedelta(seconds=seconds) <= baseline:
                continue  # Window opened before the last run: nothing was missed.
            try:
                event_time = target.astimezone(ZoneInfo(event['timezone']))
            except (ZoneInfoNotFoundError, ValueError):
                event_time = target
            display_time = event_time.strftime('%a %d %b, %H:%M %Z')
            notify(f"{event['name']} {label}", f'{format_remaining(delta)} remaining · {display_time}', key, now=now)
    _write_last_run(now)


def prune_notifications(now=None):
    """Remove delivered reminder history that can no longer suppress a reminder."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(days=30)
    with db() as connection:
        competitions = {
            row['id']: {'start': row['start'], 'deadline': row['deadline']}
            for row in connection.execute('SELECT id,start,deadline FROM competitions')
        }
        delivered = connection.execute("SELECT key FROM notifications WHERE status='delivered'").fetchall()
        remove = []
        for row in delivered:
            parsed = NOTIFICATION_KEY.match(row['key'])
            if not parsed:
                continue  # Unknown key shape: keep it rather than risk a repeat reminder.
            event = competitions.get(parsed['id'])
            if not event:
                remove.append(row['key'])
                continue
            target_text = parsed['target'] or event[parsed['field']]
            if not target_text:
                continue
            try:
                target = datetime.fromisoformat(target_text.replace('Z', '+00:00'))
                target = target.replace(tzinfo=timezone.utc) if target.tzinfo is None else target.astimezone(timezone.utc)
            except (TypeError, ValueError):
                continue
            if target < cutoff:
                remove.append(row['key'])
        if remove:
            connection.executemany('DELETE FROM notifications WHERE key=? AND status=\'delivered\'', ((key,) for key in remove))
    return len(remove)


def notification_loop():
    next_prune = 0.0
    while True:
        if time.monotonic() >= next_prune:
            try:
                prune_notifications()
            except Exception as error:
                print(f'CHRONYX notification cleanup: {error}', flush=True)
            next_prune = time.monotonic() + 24 * 60 * 60
        try:
            run_reminder_check()
        except Exception as error:
            print(f'CHRONYX reminder scheduler: {error}', flush=True)
        time.sleep(60)


class LocalHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    threading.Thread(target=notification_loop, daemon=True).start()
    print(f'CHRONYX local service · SQLite: {DB} · http://127.0.0.1:{SERVICE_PORT}', flush=True)
    LocalHTTPServer(('127.0.0.1', SERVICE_PORT), Handler).serve_forever()
