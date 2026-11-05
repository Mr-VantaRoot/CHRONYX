import io
import json
import os
import ctypes
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

_desktop_data = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = _desktop_data.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desktop


class DesktopStartupTest(unittest.TestCase):
    def test_windows_instance_mutex_is_retained_or_duplicate_handle_closed(self):
        kernel = Mock()
        kernel.CreateMutexW.return_value = 123
        with patch.object(desktop.ctypes, 'WinDLL', return_value=kernel, create=True), \
             patch.object(desktop.ctypes, 'get_last_error', return_value=0, create=True):
            self.assertTrue(desktop.acquire_windows_instance())
        self.assertEqual(desktop._windows_mutex, (kernel, 123))

        kernel.CloseHandle.reset_mock()
        with patch.object(desktop.ctypes, 'WinDLL', return_value=kernel, create=True), \
             patch.object(desktop.ctypes, 'get_last_error', return_value=183, create=True):
            self.assertFalse(desktop.acquire_windows_instance())
        kernel.CloseHandle.assert_called_once_with(123)

    def test_second_launch_attaches_without_starting_a_duplicate_scheduler(self):
        response = io.BytesIO(json.dumps([]).encode())
        with patch('desktop.LocalHTTPServer', side_effect=OSError('port already in use')):
            with patch('desktop.urlopen', return_value=response):
                with patch('desktop.threading.Thread') as thread:
                    self.assertIsNone(desktop.start_or_attach_service())
        thread.assert_not_called()

    def test_port_owned_by_an_unrelated_service_is_rejected(self):
        response = io.BytesIO(json.dumps({'not': 'events'}).encode())
        with patch('desktop.LocalHTTPServer', side_effect=OSError('port already in use')):
            with patch('desktop.urlopen', return_value=response):
                with self.assertRaisesRegex(RuntimeError, 'not a CHRONYX service'):
                    desktop.start_or_attach_service()

    def test_owned_service_starts_api_and_single_scheduler_threads(self):
        service = Mock()
        with patch('desktop.LocalHTTPServer', return_value=service):
            with patch('desktop.threading.Thread') as thread:
                self.assertIs(desktop.start_or_attach_service(), service)
        self.assertEqual(thread.call_count, 2)
        self.assertEqual(thread.call_args_list[0].kwargs['target'], service.serve_forever)


if __name__ == '__main__':
    unittest.main()
