import json
import io
import os
import socket
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
        self.close_connection = False

    def send_json(self, data, status=200):
        self.result = (status, data)

    def _read_json(self, max_bytes=server.MAX_REQUEST_BYTES):
        return server.Handler._read_json(self, max_bytes)

    def _check_origin(self):
        return server.Handler._check_origin(self)

    def _write_event(self, created):
        return server.Handler._write_event(self, created)


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

    def send_error(self, status, message=''):
        self.status = status
        self.error = message

    def send_json(self, data, status=200):
        self.status = status
        self.json = data

    def _frontend_unavailable(self, head=False):
        return server.Handler._frontend_unavailable(self, head)


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
        server._write_last_run(now - timedelta(days=2))  # The app was closed when 7d and 3d opened.
        with patch('server.subprocess.run') as run, patch('server.shutil.which', return_value='/usr/bin/notify-send'), patch.dict(os.environ, {'DBUS_SESSION_BUS_ADDRESS': 'test'}):
            server.run_reminder_check(now)
            server.run_reminder_check(now + timedelta(seconds=30))
        self.assertEqual(run.call_count, 1)
        with server.db() as connection:
            key = connection.execute('SELECT key FROM notifications WHERE status=?', ('delivered',)).fetchone()['key']
        self.assertIn(':start:3d:', key)

    def test_event_created_inside_an_open_window_is_silent(self):
        now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.add_event(event_payload((now + timedelta(days=2)).isoformat()))
        server._write_last_run(now - timedelta(seconds=60))
        with patch('server.notify') as notify:
            server.run_reminder_check(now)
            server.run_reminder_check(now + timedelta(seconds=60))
        notify.assert_not_called()

    def test_first_run_without_history_does_not_replay_old_windows(self):
        now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.add_event(event_payload((now + timedelta(days=2)).isoformat()))
        with patch('server.notify') as notify:
            server.run_reminder_check(now)
        notify.assert_not_called()

    def test_window_opening_after_the_last_run_notifies_with_real_time_left(self):
        now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.add_event(event_payload((now + timedelta(days=1, seconds=-30)).isoformat()))
        server._write_last_run(now - timedelta(seconds=60))
        with patch('server.notify') as notify:
            server.run_reminder_check(now)
        notify.assert_called_once()
        self.assertTrue(notify.call_args.args[1].startswith('23h 59m remaining'))

    def test_catch_up_reports_actual_time_left_not_the_window_name(self):
        now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.add_event(event_payload((now + timedelta(days=2)).isoformat()))
        server._write_last_run(now - timedelta(days=2))
        with patch('server.notify') as notify:
            server.run_reminder_check(now)
        self.assertTrue(notify.call_args.args[1].startswith('2d remaining'))
        self.assertIn(':3d:', notify.call_args.args[2])

    def test_scheduler_records_its_last_run(self):
        now = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)
        self.assertIsNone(server._read_last_run())
        server.run_reminder_check(now)
        self.assertEqual(server._read_last_run(), now)

    def test_failed_delivery_is_still_retried_after_its_window_opened_earlier(self):
        now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        target = now + timedelta(days=2)
        self.add_event(event_payload(target.isoformat()))
        key = server.notification_key('event-1', 'start', '3d', target)
        with server.db() as connection:
            connection.execute(
                "INSERT INTO notifications(key,sent_at,status,attempts,claimed_at,retry_after) VALUES(?,?,'failed',1,?,?)",
                (key, (now - timedelta(days=1)).isoformat(), (now - timedelta(days=1)).isoformat(), (now - timedelta(hours=1)).isoformat()),
            )
        server._write_last_run(now - timedelta(seconds=60))
        with patch('server.notify') as notify:
            server.run_reminder_check(now)
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[2], key)

    def test_format_remaining_uses_the_two_largest_units(self):
        self.assertEqual(server.format_remaining(2 * 86400), '2d')
        self.assertEqual(server.format_remaining(2 * 86400 + 3 * 3600 + 59), '2d 3h')
        self.assertEqual(server.format_remaining(3600), '1h')
        self.assertEqual(server.format_remaining(5400), '1h 30m')
        self.assertEqual(server.format_remaining(20), '1m')

    def test_origin_must_match_this_services_exact_loopback_origin(self):
        for trusted in (None, '', 'http://127.0.0.1:8765', 'http://localhost:8765', 'http://localhost:8765/'):
            self.assertTrue(server._trusted_origin(trusted), trusted)
        for rejected in (
            'http://localhost:9999', 'http://127.0.0.1:5173', 'http://127.0.0.1', 'https://127.0.0.1:8765',
            'http://127.0.0.1.evil.test:8765', 'http://user@127.0.0.1:8765', 'http://127.0.0.1:8765/x',
            'null', 'http://[::1]:8765', 'http://localhost:notaport',
        ):
            self.assertFalse(server._trusted_origin(rejected), rejected)
        self.assertTrue(server._trusted_origin('http://127.0.0.1:12345', 12345))
        self.assertFalse(server._trusted_origin('http://127.0.0.1:8765', 12345))

    def test_cors_header_is_only_sent_for_the_exact_service_origin(self):
        class HeaderRecorder(server.Handler):
            def __init__(self, origin):
                self.headers = {'Origin': origin}
                self.path = '/api/events'
                self.close_connection = False
                self.request_version = 'HTTP/1.1'
                self.captured = {}
                self._headers_buffer = []
                self.wfile = io.BytesIO()

            def send_header(self, key, value):
                self.captured[key] = value
                self._headers_buffer.append(f'{key}: {value}\r\n'.encode())

        same = HeaderRecorder('http://127.0.0.1:8765')
        server.Handler.end_headers(same)
        self.assertEqual(same.captured['Access-Control-Allow-Origin'], 'http://127.0.0.1:8765')
        other = HeaderRecorder('http://localhost:9999')
        server.Handler.end_headers(other)
        self.assertNotIn('Access-Control-Allow-Origin', other.captured)

    def test_prune_supports_event_ids_that_contain_colons(self):
        now = datetime(2030, 2, 1, tzinfo=timezone.utc)
        future = now + timedelta(days=300)
        self.add_event({**event_payload(future.isoformat()), 'id': 'ctf:2030:finals'})
        key = server.notification_key('ctf:2030:finals', 'start', '1d', future)
        with server.db() as connection:
            connection.execute("INSERT INTO notifications(key,sent_at,status) VALUES(?,?,'delivered')", (key, now.isoformat()))
        self.assertEqual(server.prune_notifications(now), 0)
        with server.db() as connection:
            connection.execute('DELETE FROM competitions WHERE id=?', ('ctf:2030:finals',))
        self.assertEqual(server.prune_notifications(now), 1)

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

    def test_post_refuses_duplicate_ids_and_put_refuses_missing_ids(self):
        self.add_event()
        duplicate = HandlerRequest(json.dumps(event_payload()).encode(), '/api/events')
        server.Handler.do_POST(duplicate)
        self.assertEqual(duplicate.result[0], 409)
        self.assertEqual(server.events()[0]['name'], 'Sample CTF')

        missing = HandlerRequest(json.dumps({**event_payload(), 'id': 'not-present'}).encode(), '/api/events')
        server.Handler.do_PUT(missing)
        self.assertEqual(missing.result[0], 404)
        self.assertEqual(len(server.events()), 1)

    def test_host_and_origin_validation_close_unread_requests(self):
        request = HandlerRequest(b'', '/api/events')
        request.server = SimpleNamespace(server_address=('127.0.0.1', 12345))
        request.headers['Host'] = 'attacker.invalid:12345'
        self.assertFalse(server.Handler._check_host(request))
        self.assertTrue(request.close_connection)
        self.assertEqual(request.result[0], 403)

        request = HandlerRequest(b'', '/api/events')
        request.headers['Origin'] = 'https://attacker.invalid'
        self.assertFalse(server.Handler._check_origin(request))
        self.assertTrue(request.close_connection)
        self.assertEqual(request.result[0], 403)

        request = HandlerRequest(b'', '/not-an-api-route')
        request.close_connection = False
        server.Handler.do_POST(request)
        self.assertTrue(request.close_connection)
        self.assertEqual(request.result[0], 404)

    def test_parse_request_checks_host_and_origin_for_api_reads(self):
        def request_for(method, path, headers=''):
            request = server.Handler.__new__(server.Handler)
            request.raw_requestline = f'{method} {path} HTTP/1.1\r\n'.encode()
            request.rfile = io.BytesIO((headers + '\r\n').encode())
            request.wfile = io.BytesIO()
            request.server = SimpleNamespace(server_address=('127.0.0.1', 8765))
            request.close_connection = True
            request._headers_buffer = []
            return request

        bad_origin = request_for(
            'GET', '/api/events',
            'Host: localhost:8765\r\nOrigin: https://attacker.invalid\r\n',
        )
        self.assertFalse(server.Handler.parse_request(bad_origin))
        self.assertTrue(bad_origin.close_connection)
        self.assertIn(b'403 Forbidden', bad_origin.wfile.getvalue())

        bad_host = request_for('GET', '/index.html', 'Host: attacker.invalid:8765\r\n')
        self.assertFalse(server.Handler.parse_request(bad_host))
        self.assertTrue(bad_host.close_connection)
        self.assertIn(b'403 Forbidden', bad_host.wfile.getvalue())

    def test_security_headers_include_cross_origin_and_permissions_policies(self):
        class HeaderRecorder(server.Handler):
            def __init__(self):
                self.headers = {}
                self.path = '/'
                self.close_connection = True
                self.request_version = 'HTTP/1.1'
                self.captured = {}
                self._headers_buffer = []
                self.wfile = io.BytesIO()

            def send_header(self, key, value):
                self.captured[key] = value
                self._headers_buffer.append(f'{key}: {value}\r\n'.encode())

        request = HeaderRecorder()
        server.Handler.end_headers(request)
        self.assertEqual(request.captured['Cross-Origin-Resource-Policy'], 'same-origin')
        self.assertEqual(request.captured['Cross-Origin-Opener-Policy'], 'same-origin')
        self.assertEqual(request.captured['Permissions-Policy'], 'camera=(), microphone=(), geolocation=()')
        self.assertIn('Content-Security-Policy', request.captured)
        self.assertEqual(request.captured['Connection'], 'close')

    def test_frontend_is_confined_to_dist_without_dotfiles_or_directory_listing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'dist'
            root.mkdir()
            outside = Path(temp) / 'secret.txt'
            outside.write_text('secret')
            (root / 'link.txt').symlink_to(outside)
            (root / 'index.html').write_text('app')
            self.assertEqual(server.frontend_file_path('/index.html', root), root / 'index.html')
            self.assertIsNone(server.frontend_file_path('/.secret', root))
            self.assertIsNone(server.frontend_file_path('/link.txt', root))

        listing = HandlerGetRequest('/')
        server.Handler.list_directory(listing, '/')
        self.assertEqual(listing.status, 404)

    def test_missing_frontend_returns_actionable_503_but_missing_api_is_404(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('server.ROOT', Path(temp)):
                page = HandlerGetRequest('/index.html')
                server.Handler.do_GET(page)
                self.assertEqual(page.status, 503)
                self.assertIn(b'Frontend not built. Run npm run build', page.wfile.getvalue())

                api = HandlerGetRequest('/api/missing')
                server.Handler.do_GET(api)
                self.assertEqual(api.status, 404)

    def test_http_host_origin_and_oversize_pipeline_close_connections(self):
        try:
            httpd = server.LocalHTTPServer(('127.0.0.1', 0), server.Handler)
        except PermissionError:
            self.skipTest('Sandbox does not allow binding a local HTTP socket')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]

        def exchange(data):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=2) as client:
                    client.settimeout(2)
                    client.sendall(data)
                    chunks = []
                    while True:
                        try:
                            chunk = client.recv(4096)
                        except socket.timeout:
                            break
                        if not chunk:
                            break
                        chunks.append(chunk)
                    return b''.join(chunks)
            except PermissionError:
                self.skipTest('Sandbox does not allow local HTTP client sockets')

        try:
            bad_host = exchange(f'GET /api/events HTTP/1.1\r\nHost: attacker.invalid:{port}\r\n\r\n'.encode())
            self.assertIn(b'403 Forbidden', bad_host)
            self.assertIn(b'Connection: close', bad_host)

            bad_origin = exchange(f'GET /api/events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nOrigin: https://attacker.invalid\r\n\r\n'.encode())
            self.assertIn(b'403 Forbidden', bad_origin)
            self.assertIn(b'Connection: close', bad_origin)

            pipeline = (
                f'POST /api/events HTTP/1.1\r\nHost: localhost:{port}\r\n'
                f'Content-Length: {server.MAX_REQUEST_BYTES + 1}\r\n\r\n'
                f'GET /api/events HTTP/1.1\r\nHost: localhost:{port}\r\n\r\n'
            ).encode()
            response = exchange(pipeline)
            self.assertIn(b'400 Bad Request', response)
            self.assertIn(b'Connection: close', response)
            self.assertEqual(response.count(b'HTTP/1.1 '), 1)
        finally:
            httpd.shutdown()
            httpd.server_close()

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
