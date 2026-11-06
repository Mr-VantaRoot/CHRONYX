import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

_download_data = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = _download_data.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desktop


class DownloadHelpersTest(unittest.TestCase):
    def test_suggested_names_are_reduced_to_a_safe_basename(self):
        self.assertEqual(desktop.safe_download_name('chronyx-competitions.json'), 'chronyx-competitions.json')
        self.assertEqual(desktop.safe_download_name('../../etc/passwd'), 'passwd')
        self.assertEqual(desktop.safe_download_name('..\\..\\evil.csv'), 'evil.csv')
        self.assertEqual(desktop.safe_download_name('a<b>:c.csv'), 'a_b__c.csv')
        for empty in ('', None, '..', '...'):
            self.assertEqual(desktop.safe_download_name(empty), 'chronyx-export')

    def test_existing_files_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            first = desktop.unique_download_path(temp, 'backup.json')
            self.assertEqual(first, Path(temp) / 'backup.json')
            first.write_text('one')
            second = desktop.unique_download_path(temp, 'backup.json')
            self.assertEqual(second, Path(temp) / 'backup (1).json')
            second.write_text('two')
            self.assertEqual(desktop.unique_download_path(temp, 'backup.json'), Path(temp) / 'backup (2).json')
            self.assertEqual(first.read_text(), 'one')

    def test_download_directory_is_created_when_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'Downloads'
            path = desktop.unique_download_path(target, 'x.csv')
            self.assertTrue(target.is_dir())
            self.assertEqual(path, target / 'x.csv')

    def test_default_download_directory_prefers_the_desktop_setting(self):
        self.assertEqual(desktop.default_download_directory('/data/Downloads'), Path('/data/Downloads'))
        self.assertEqual(desktop.default_download_directory(None, '/home/anti'), Path('/home/anti/Downloads'))

    def test_windows_shell_enables_pywebview_downloads(self):
        fake = types.ModuleType('webview')
        fake.settings = {'ALLOW_DOWNLOADS': False}
        fake.create_window = Mock()
        fake.start = Mock()
        with patch.dict(sys.modules, {'webview': fake}):
            desktop.run_windows()
        self.assertTrue(fake.settings['ALLOW_DOWNLOADS'])
        fake.create_window.assert_called_once()
        fake.start.assert_called_once()


if __name__ == '__main__':
    unittest.main()
