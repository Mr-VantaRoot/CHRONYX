import os
import tempfile
import unittest
from pathlib import Path

_test_home = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = _test_home.name
from server import data_directory, legacy_data_directory


class DataDirectoryTest(unittest.TestCase):
    def test_linux_uses_xdg_data_home(self):
        self.assertEqual(
            data_directory('posix', {'XDG_DATA_HOME': '/tmp/chronyx-test'}, '/home/test'),
            Path('/tmp/chronyx-test/chronyx'),
        )

    def test_linux_defaults_to_local_share(self):
        self.assertEqual(data_directory('posix', {}, '/home/test'), Path('/home/test/.local/share/chronyx'))

    def test_linux_ignores_relative_xdg_path(self):
        self.assertEqual(
            data_directory('posix', {'XDG_DATA_HOME': 'relative'}, '/home/test'),
            Path('/home/test/.local/share/chronyx'),
        )

    def test_windows_uses_appdata(self):
        self.assertEqual(data_directory('nt', {'APPDATA': '/tmp/appdata'}, '/home/test'), Path('/tmp/appdata/CHRONYX'))

    def test_windows_has_roaming_fallback(self):
        self.assertEqual(data_directory('nt', {}, '/home/test'), Path('/home/test/AppData/Roaming/CHRONYX'))

    def test_legacy_directories_match_the_vanta_named_releases(self):
        self.assertEqual(legacy_data_directory('posix', {}, '/home/test'), Path('/home/test/.local/share/vanta'))
        self.assertEqual(
            legacy_data_directory('posix', {'XDG_DATA_HOME': '/data'}, '/home/test'), Path('/data/vanta')
        )
        self.assertEqual(legacy_data_directory('nt', {'APPDATA': '/tmp/appdata'}, '/h'), Path('/tmp/appdata/VANTA'))
        self.assertEqual(legacy_data_directory('nt', {}, '/home/test'), Path('/home/test/AppData/Roaming/VANTA'))


if __name__ == '__main__':
    unittest.main()
