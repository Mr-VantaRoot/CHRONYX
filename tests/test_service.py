import json
import io
import os
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import MethodType, SimpleNamespace
from pathlib import Path
from unittest.mock import patch

_test_data = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = _test_data.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


def event_payload(start='2030-01-01T00:00:00Z'):
    return {
        'id': 'event-1', 'name': 'Sample CTF', 'description': 'Description',
        'category': 'CTF', 'organizer': 'Org', 'website': '', 'registrationUrl': '',
        'start': start, 'end': '', 'deadline': '', 'timezone': 'UTC',
        'status': 'Interested', 'priority': 'High', 'notes': '',
        'created': '2026-01-01T00:00:00Z',
    }


class HandlerRequest:
    def __init__(self, body, path):
        self.headers = {'Content-Length': str(len(body))}
        self.rfile = io.BytesIO(body)
        self.path = path
        self.result = None

    def send_json(self, data, status=200):
        self.result = (status, data)

    def _read_json(self, max_bytes=server.MAX_REQUEST_BYTES):
        return server.Handler._read_json(self, max_bytes)

    def _check_origin(self):
        return server.Handler._check_origin(self)


class HandlerGetRequest:
    def __init__(self, path):
        self.path = path
        self.headers = {}
        self.wfile = io.BytesIO()
        self.status = None
        self.response_headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass

    def send_json(self, data, status=200):
        self.status = status
        self.json = data


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db = server.DB
        server.DB = Path(self.temp.name) / 'test.sqlite3'
        server.initialize_database()

    def tearDown(self):
        server.DB = self.previous_db
        self.temp.cleanup()

    def add_event(self, payload=None):
        item = server.validate_event(payload or event_payload())
        with server.db() as connection:
            connection.execute('''INSERT INTO competitions(
                id,name,description,category,organizer,website,registrationUrl,
                start,end,deadline,timezone,status,priority,notes,created
            ) VALUES(:id,:name,:description,:category,:organizer,:website,:registrationUrl,
                :start,:end,:deadline,:timezone,:status,:priority,:notes,:created)''', item)
        return item

    def test_crud_and_persistence(self):
        self.add_event()
        self.assertEqual(server.events()[0]['name'], 'Sample CTF')
        with server.db() as connection:
            connection.execute('UPDATE competitions SET name=? WHERE id=?', ('Edited CTF', 'event-1'))
        self.assertEqual(server.events()[0]['name'], 'Edited CTF')
        with server.db() as connection:
            connection.execute('DELETE FROM competitions WHERE id=?', ('event-1',))
        self.assertEqual(server.events(), [])

    def test_migrates_legacy_notification_table_without_losing_rows(self):
        legacy_path = Path(self.temp.name) / 'legacy.sqlite3'
        with sqlite3.connect(legacy_path) as connection:
            connection.execute('CREATE TABLE competitions(id TEXT PRIMARY KEY,start TEXT NOT NULL,deadline TEXT NOT NULL DEFAULT "")')
            connection.execute('INSERT INTO competitions(id,start) VALUES(?,?)', ('event-1', '2030-01-01T00:00:00+00:00'))
            connection.execute('CREATE TABLE notifications(key TEXT PRIMARY KEY,sent_at TEXT NOT NULL)')
            connection.execute('INSERT INTO notifications VALUES(?,?)', ('event-1:start:1d', '2029-12-31T00:00:00+00:00'))
        server.initialize_database(legacy_path)
        with sqlite3.connect(legacy_path) as connection:
            rows = connection.execute('SELECT key,sent_at,status,attempts,delivered_at FROM notifications ORDER BY key').fetchall()
            preserved_event = connection.execute('SELECT id,start FROM competitions').fetchone()
            version = connection.execute('PRAGMA user_version').fetchone()[0]
        self.assertEqual(rows[0], ('event-1:start:1d', '2029-12-31T00:00:00+00:00', 'delivered', 1, '2029-12-31T00:00:00+00:00'))
        self.assertEqual(rows[1], ('event-1:start:1d:2030-01-01T00:00:00+00:00', '2029-12-31T00:00:00+00:00', 'delivered', 1, '2029-12-31T00:00:00+00:00'))
        self.assertEqual(preserved_event, ('event-1', '2030-01-01T00:00:00+00:00'))
        self.assertEqual(version, 2)

    def test_refuses_a_newer_schema_without_mutating_it(self):
        newer_path = Path(self.temp.name) / 'newer.sqlite3'
        with sqlite3.connect(newer_path) as connection:
            connection.execute('PRAGMA user_version=3')
        with self.assertRaisesRegex(RuntimeError, 'newer than this CHRONYX build supports'):
            server.initialize_database(newer_path)
        with sqlite3.connect(newer_path) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])

    def test_notification_delivery_is_deduplicated_after_success(self):
        now = datetime(2029, 12, 31, tzinfo=timezone.utc)
        with patch('server.subprocess.run') as run, patch('server.shutil.which', return_value='/usr/bin/notify-send'), patch.dict(os.environ, {'DBUS_SESSION_BUS_ADDRESS': 'test'}):
            self.assertTrue(server.notify('Reminder', 'Test', 'unique-reminder', system='posix', now=now))
            self.assertFalse(server.notify('Reminder', 'Test', 'unique-reminder', system='posix', now=now))
        self.assertEqual(run.call_count, 1)
        state = server.notification_status('unique-reminder')
        self.assertEqual(state['status'], 'delivered')

    def test_concurrent_reminder_workers_claim_a_key_once(self):
        now = datetime(2029, 12, 31, tzinfo=timezone.utc)
        def delayed_delivery(*args, **kwargs):
            time.sleep(0.05)
            return None
        with patch('server.subprocess.run', side_effect=delayed_delivery) as run, patch('server.shutil.which', return_value='/usr/bin/notify-send'), patch.dict(os.environ, {'DBUS_SESSION_BUS_ADDRESS': 'test'}):
            with ThreadPoolExecutor(max_workers=6) as workers:
                results = list(workers.map(lambda _: server.notify('Reminder', 'Test', 'concurrent-key', system='posix', now=now), range(6)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(run.call_count, 1)

    def test_failed_delivery_is_retried_and_then_marked_delivered(self):
        now = datetime(2029, 12, 31, tzinfo=timezone.utc)
        failure = subprocess_error()
        with patch('server.subprocess.run', side_effect=[failure, None]) as run, patch('server.shutil.which', return_value='/usr/bin/notify-send'), patch.dict(os.environ, {'DBUS_SESSION_BUS_ADDRESS': 'test'}):
            self.assertFalse(server.notify('Reminder', 'Test', 'retry-me', system='posix', now=now))
            self.assertEqual(server.notification_status('retry-me')['status'], 'failed')
            self.assertTrue(server.notify('Reminder', 'Test', 'retry-me', system='posix', now=now + timedelta(seconds=60)))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(server.notification_status('retry-me')['status'], 'delivered')

    def test_missing_linux_notifier_is_recorded_as_failed_not_delivered(self):
        with patch('server.shutil.which', return_value=None):
            self.assertFalse(server.notify('Reminder', 'Test', 'missing-tool', system='posix'))
        state = server.notification_status('missing-tool')
        self.assertEqual(state['status'], 'failed')
        self.assertIsNone(state['delivered_at'])

    def test_windows_toast_failure_is_retryable_and_success_is_deduplicated(self):
        now = datetime(2029, 12, 31, tzinfo=timezone.utc)
        failed_winotify = types.ModuleType('winotify')
        failed_winotify.Notification = lambda **kwargs: types.SimpleNamespace(show=lambda: (_ for _ in ()).throw(RuntimeError('toast failed')))
        with patch.dict(sys.modules, {'winotify': failed_winotify}):
            self.assertFalse(server.notify('Reminder', 'Test', 'windows-retry', system='nt', now=now))
        self.assertEqual(server.notification_status('windows-retry')['status'], 'failed')

        toast = types.SimpleNamespace(show=unittest.mock.Mock())
        notification = unittest.mock.Mock(return_value=toast)
        winotify = types.ModuleType('winotify')
        winotify.Notification = notification
        with patch.dict(sys.modules, {'winotify': winotify}):
            self.assertTrue(server.notify('Windows reminder', 'Test toast', 'windows-retry', system='nt', now=now + timedelta(seconds=60)))
            self.assertFalse(server.notify('Windows reminder', 'Test toast', 'windows-retry', system='nt', now=now + timedelta(seconds=120)))
        notification.assert_called_once()
        toast.show.assert_called_once()

    def test_rescheduled_event_uses_a_distinct_reminder_identity(self):
        now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        first = now + timedelta(days=1, seconds=-30)
        self.add_event(event_payload(first.isoformat()))
        with server.db() as connection:
            connection.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps({'1d': True}), 'reminders'))
        with patch('server.notify') as notify:
            server.run_reminder_check(now)
            second_now = now + timedelta(hours=1)
            second = second_now + timedelta(days=1, seconds=-30)
            with server.db() as connection:
                connection.execute('UPDATE competitions SET start=? WHERE id=?', (second.isoformat(), 'event-1'))
            server.run_reminder_check(second_now)
        keys = [call.args[2] for call in notify.call_args_list]
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])

    def test_notification_time_text_uses_event_timezone(self):
        target = datetime(2030, 1, 2, tzinfo=timezone.utc)
        item = event_payload(target.isoformat())
        item['timezone'] = 'Africa/Nairobi'
        self.add_event(item)
        with server.db() as connection:
            connection.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps({'1d': True}), 'reminders'))
        with patch('server.notify') as notify:
            server.run_reminder_check(target - timedelta(days=1) + timedelta(seconds=30))
        self.assertIn('03:00 EAT', notify.call_args.args[1])

    def test_missed_reminder_sends_only_the_tightest_catch_up_and_deduplicates(self):
        now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.add_event(event_payload((now + timedelta(days=2)).isoformat()))
        with server.db() as connection:
            connection.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps({'7d': True, '3d': True, '1d': True, '1h': True}), 'reminders'))
        with patch('server.subprocess.run') as run, patch('server.shutil.which', return_value='/usr/bin/notify-send'), patch.dict(os.environ, {'DBUS_SESSION_BUS_ADDRESS': 'test'}):
            server.run_reminder_check(now)
            server.run_reminder_check(now + timedelta(seconds=30))
        self.assertEqual(run.call_count, 1)
        with server.db() as connection:
            key = connection.execute('SELECT key FROM notifications WHERE status=?', ('delivered',)).fetchone()['key']
        self.assertIn(':start:3d:', key)

    def test_notification_pruning_removes_orphans_and_delivered_targets_over_30_days(self):
        now = datetime(2030, 2, 1, tzinfo=timezone.utc)
        old_target = now - timedelta(days=31)
        recent_target = now - timedelta(days=29)
        self.add_event(event_payload(old_target.isoformat()))
        with server.db() as connection:
            for target, key, status in (
                (old_target, server.notification_key('event-1', 'start', '7d', old_target), 'delivered'),
                (recent_target, server.notification_key('event-1', 'start', '3d', recent_target), 'delivered'),
                (old_target, server.notification_key('missing-event', 'start', '7d', old_target), 'delivered'),
                (old_target, server.notification_key('missing-event', 'start', '1d', old_target), 'failed'),
            ):
                connection.execute('INSERT INTO notifications(key,sent_at,status) VALUES(?,?,?)', (key, now.isoformat(), status))
        self.assertEqual(server.prune_notifications(now), 2)
        with server.db() as connection:
            rows = {row['status'] for row in connection.execute('SELECT status FROM notifications')}
            keys = {row['key'] for row in connection.execute('SELECT key FROM notifications')}
        self.assertEqual(len(keys), 2)
        self.assertIn('failed', rows)
        self.assertIn(server.notification_key('event-1', 'start', '3d', recent_target), keys)

    def test_notification_loop_prunes_at_startup_and_daily(self):
        class StopLoop(Exception):
            pass
        with patch('server.time.monotonic', side_effect=[0, 1, 86401, 86402]), \
             patch('server.time.sleep', side_effect=[None, StopLoop]), \
             patch('server.prune_notifications') as prune, \
             patch('server.run_reminder_check'):
            with self.assertRaises(StopLoop):
                server.notification_loop()
        self.assertEqual(prune.call_count, 2)

    def test_api_validates_event_and_origin_and_delete_errors(self):
        def handler(body, origin=None, path='/api/events'):
            request = server.Handler.__new__(server.Handler)
            request.headers = {'Content-Length': str(len(body))}
            if origin:
                request.headers['Origin'] = origin
            request.rfile = io.BytesIO(body)
            request.path = path
            request.result = None
            request.send_json = MethodType(lambda self, data, status=200: setattr(self, 'result', (status, data)), request)
            request._read_json = MethodType(server.Handler._read_json, request)
            request._check_origin = MethodType(server.Handler._check_origin, request)
            return request

        invalid = handler(json.dumps(event_payload(start='2030-01-01T00:00:00')).encode())
        server.Handler._write_event(invalid, created=True)
        self.assertEqual(invalid.result[0], 400)

        foreign = handler(json.dumps(event_payload()).encode(), 'https://attacker.invalid')
        server.Handler._write_event(foreign, created=True)
        self.assertEqual(foreign.result[0], 403)

        valid = handler(json.dumps(event_payload()).encode())
        server.Handler._write_event(valid, created=True)
        self.assertEqual(valid.result[0], 201)
        self.assertEqual(server.events()[0]['name'], 'Sample CTF')

        missing = handler(b'', path='/api/events/missing')
        server.Handler.do_DELETE(missing)
        self.assertEqual(missing.result[0], 404)

        invalid_settings = handler(json.dumps({'customHours': 9000}).encode(), path='/api/settings')
        server.Handler.do_PATCH(invalid_settings)
        self.assertEqual(invalid_settings.result[0], 400)

        valid_settings = handler(json.dumps({'1d': False, 'customHours': 12}).encode(), path='/api/settings')
        server.Handler.do_PATCH(valid_settings)
        self.assertEqual(valid_settings.result[0], 200)
        self.assertEqual(valid_settings.result[1], {'7d': True, '3d': True, '1d': False, '1h': True, 'customHours': 12})

        external = handler(json.dumps({'url': 'https://example.com/event'}).encode(), path='/api/open')
        with patch('server.webbrowser.open', return_value=True) as open_browser:
            server.Handler.do_POST(external)
        self.assertEqual(external.result[0], 200)
        open_browser.assert_called_once_with('https://example.com/event', new=2)

        rejected = handler(json.dumps({'url': 'file:///etc/passwd'}).encode(), path='/api/open')
        server.Handler.do_POST(rejected)
        self.assertEqual(rejected.result[0], 400)

    def test_batch_import_reports_invalid_entries_and_upserts_in_one_request(self):
        self.add_event()
        rows = [
            event_payload(start='2030-01-02T00:00:00Z'),
            {**event_payload(), 'id': 'bad-event', 'category': 'Unknown'},
        ]
        body = json.dumps({'events': rows, 'indices': [4, 7]}).encode()
        request = HandlerRequest(body, '/api/events/import')
        server.Handler.do_POST(request)
        self.assertEqual(request.result[0], 200)
        self.assertEqual(request.result[1]['imported'], 1)
        self.assertEqual(request.result[1]['skipped'], [{'index': 7, 'name': 'Sample CTF', 'reason': 'Unknown competition category'}])
        self.assertEqual(server.events()[0]['start'], '2030-01-02T00:00:00+00:00')
        self.assertEqual(len(server.events()), 1)

    def test_batch_import_invalid_only_does_not_change_database(self):
        self.add_event()
        request = HandlerRequest(json.dumps({'events': [{'name': 'bad'}], 'indices': [0]}).encode(), '/api/events/import')
        server.Handler.do_POST(request)
        self.assertEqual(request.result[1]['imported'], 0)
        self.assertEqual(len(request.result[1]['skipped']), 1)
        self.assertEqual(len(server.events()), 1)

    def test_batch_import_rolls_back_all_rows_when_database_write_fails(self):
        with server.db() as connection:
            connection.execute('''CREATE TRIGGER reject_import BEFORE INSERT ON competitions
                WHEN NEW.id='reject' BEGIN SELECT RAISE(ABORT, 'blocked'); END''')
        rows = [event_payload(), {**event_payload(), 'id': 'reject'}]
        request = HandlerRequest(json.dumps({'events': rows, 'indices': [0, 1]}).encode(), '/api/events/import')
        server.Handler.do_POST(request)
        self.assertEqual(request.result[0], 500)
        self.assertEqual(server.events(), [])

    def test_csv_export_quotes_fields_and_neutralizes_spreadsheet_formulas(self):
        from csv import reader
        csv_text = server.export_csv([{
            'name': '=1+1', 'category': '+cmd', 'organizer': '-2+3',
            'description': '@SUM(A1:A2)', 'website': '\t=HYPERLINK("x")',
            'registrationUrl': 'https://example.test', 'start': '2030-01-01T00:00:00Z',
            'end': '', 'deadline': '', 'timezone': 'UTC', 'status': 'Interested',
            'priority': 'Low', 'notes': '\r=1+1',
        }])
        rows = list(reader(io.StringIO(csv_text, newline='')))
        self.assertEqual(rows[0], ['name', 'category', 'organizer', 'description', 'website', 'registrationUrl', 'start', 'end', 'deadline', 'timezone', 'status', 'priority', 'notes'])
        self.assertEqual(rows[1][0:5], ["'=1+1", "'+cmd", "'-2+3", "'@SUM(A1:A2)", "'\t=HYPERLINK(\"x\")"])
        self.assertEqual(rows[1][-1], "'\r=1+1")

    def test_export_endpoints_set_attachment_headers(self):
        self.add_event()
        for extension, mime in [('json', 'application/json; charset=utf-8'), ('csv', 'text/csv; charset=utf-8')]:
            request = HandlerGetRequest(f'/api/export.{extension}')
            server.Handler.do_GET(request)
            self.assertEqual(request.status, 200)
            self.assertEqual(request.response_headers['Content-Type'], mime)
            self.assertIn('attachment; filename=', request.response_headers['Content-Disposition'])
            self.assertEqual(int(request.response_headers['Content-Length']), len(request.wfile.getvalue()))


def subprocess_error():
    import subprocess
    return subprocess.CalledProcessError(1, ['notify-send'], stderr='session bus unavailable')


if __name__ == '__main__':
    unittest.main()
