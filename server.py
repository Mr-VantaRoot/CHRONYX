#!/usr/bin/env python3
"""CHRONYX's local SQLite API and desktop reminder service."""

import ipaddress
import csv
import io
import json
import os
import shutil
import sqlite3
import subprocess
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
MAX_REQUEST_BYTES = 256 * 1024
MAX_IMPORT_BYTES = 4 * 1024 * 1024
NOTIFICATION_LEASE = timedelta(minutes=2)
ALLOWED_CATEGORIES = {
    'CTF', 'Hackathon', 'AI / ML', 'Robotics', 'Programming',
    'Scholarship', 'Technology', 'Other',
}
ALLOWED_STATUSES = {
    'Interested', 'Registered', 'Registration closed', 'Participating',
    'Completed', 'Cancelled',
}
ALLOWED_PRIORITIES = {'Low', 'Medium', 'High', 'Critical'}


def data_directory(system=None, environ=None, home=None):
    system = system or os.name
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    if system == 'nt':
        roaming = Path(environ.get('APPDATA') or '')
        if not roaming.is_absolute():
            roaming = home / 'AppData' / 'Roaming'
        return roaming / 'VANTA'
    xdg_home = Path(environ.get('XDG_DATA_HOME') or '')
    if not xdg_home.is_absolute():
        xdg_home = home / '.local/share'
    return xdg_home / 'vanta'


DATA = data_directory()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'vanta.sqlite3'


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


def _trusted_origin(origin):
    if not origin:
        return True  # Desktop shell and local CLI clients may omit Origin.
    try:
        parsed = urlsplit(origin)
        hostname = parsed.hostname
        return parsed.scheme in ('http', 'https') and bool(hostname) and (
            hostname.lower() == 'localhost' or ipaddress.ip_address(hostname).is_loopback
        )
    except ValueError:
        return False


class Handler(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'dist' if (ROOT / 'dist').exists() else ROOT), **kwargs)

    def log_message(self, *args):
        pass

    def end_headers(self):
        origin = self.headers.get('Origin')
        if origin and _trusted_origin(origin):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
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

    def _check_origin(self):
        origin = self.headers.get('Origin')
        if not _trusted_origin(origin):
            self.send_json({'error': 'Requests must come from the local application'}, 403)
            return False
        return True

    def _read_json(self, max_bytes=MAX_REQUEST_BYTES):
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError as error:
            raise ValueError('Invalid Content-Length') from error
        if length < 1 or length > max_bytes:
            raise ValueError('Request body is empty or too large')
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError('Request body must contain valid JSON') from error

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
                self.send_header('Content-Disposition', 'attachment; filename="vanta-competitions.json"')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == '/api/export.csv':
                raw = export_csv(events()).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="vanta-competitions.csv"')
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
        return super().do_GET()

    def _write_event(self, created):
        if not self._check_origin():
            return
        try:
            event = validate_event(self._read_json())
            with db() as connection:
                connection.execute('''INSERT OR REPLACE INTO competitions(
                    id,name,description,category,organizer,website,registrationUrl,
                    start,end,deadline,timezone,status,priority,notes,created
                ) VALUES(:id,:name,:description,:category,:organizer,:website,:registrationUrl,
                    :start,:end,:deadline,:timezone,:status,:priority,:notes,:created)''', event)
            return self.send_json(event, 201 if created else 200)
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
            return self.send_json({'error': 'Not found'}, 404)
        return self._write_event(created=True)

    def do_PUT(self):
        if urlsplit(self.path).path != '/api/events':
            return self.send_json({'error': 'Not found'}, 404)
        return self._write_event(created=False)

    def do_PATCH(self):
        if urlsplit(self.path).path != '/api/settings':
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


def run_reminder_check(now=None):
    """Deliver one active or missed reminder per event field, and retry failures."""
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
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
            enabled = [
                (seconds, tag) for seconds, tag in windows
                if prefs.get(tag, tag == f'{custom}h') and delta <= seconds
            ]
            if not enabled:
                continue
            # The smallest elapsed window is the latest reminder point missed.
            # Selecting it first prevents a later scheduler tick from sending
            # a second catch-up for an older window after this one was delivered.
            seconds, tag = min(enabled, key=lambda item: item[0])
            key = notification_key(event['id'], field, tag, target)
            state = persisted_notifications.get(key)
            if state and state['status'] == 'delivered':
                continue
            try:
                event_time = target.astimezone(ZoneInfo(event['timezone']))
            except (ZoneInfoNotFoundError, ValueError):
                event_time = target
            display_time = event_time.strftime('%a %d %b, %H:%M %Z')
            notify(f"{event['name']} {label}", f'{tag} remaining · {display_time}', key, now=now)


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
            parts = row['key'].split(':')
            event_id = parts[0] if parts else ''
            event = competitions.get(event_id)
            if not event:
                remove.append(row['key'])
                continue
            field = parts[1] if len(parts) > 1 else ''
            if field not in ('start', 'deadline'):
                continue
            target_text = ':'.join(parts[3:]) if len(parts) > 3 else event[field]
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
    print(f'CHRONYX local service · SQLite: {DB} · http://127.0.0.1:8765', flush=True)
    LocalHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
