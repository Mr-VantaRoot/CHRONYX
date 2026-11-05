import os
import tempfile
import unittest
from pathlib import Path

_test_home=tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME']=_test_home.name
from server import data_directory

class DataDirectoryTest(unittest.TestCase):
    def test_linux_uses_xdg_data_home(self):
        self.assertEqual(data_directory('posix',{'XDG_DATA_HOME':'/tmp/vanta-test'},'/home/test'),Path('/tmp/vanta-test/vanta'))

    def test_linux_defaults_to_local_share(self):
        self.assertEqual(data_directory('posix',{},'/home/test'),Path('/home/test/.local/share/vanta'))

    def test_linux_ignores_relative_xdg_path(self):
        self.assertEqual(data_directory('posix',{'XDG_DATA_HOME':'relative'},'/home/test'),Path('/home/test/.local/share/vanta'))

    def test_windows_uses_appdata(self):
        self.assertEqual(data_directory('nt',{'APPDATA':'/tmp/appdata'},'/home/test'),Path('/tmp/appdata/VANTA'))

    def test_windows_has_roaming_fallback(self):
        self.assertEqual(data_directory('nt',{},'/home/test'),Path('/home/test/AppData/Roaming/VANTA'))

if __name__=='__main__':unittest.main()
