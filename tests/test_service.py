import json, os, tempfile, unittest
import sys, types
from pathlib import Path
import sys
_test_data=tempfile.TemporaryDirectory();os.environ['XDG_DATA_HOME']=_test_data.name
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from unittest.mock import patch

class ServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();server.DB=Path(cls.temp.name)/'test.sqlite3'
        with server.db() as c:
            c.execute('''CREATE TABLE competitions(id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',category TEXT NOT NULL,organizer TEXT NOT NULL DEFAULT '',website TEXT NOT NULL DEFAULT '',registrationUrl TEXT NOT NULL DEFAULT '',start TEXT NOT NULL,end TEXT NOT NULL DEFAULT '',deadline TEXT NOT NULL DEFAULT '',timezone TEXT NOT NULL,status TEXT NOT NULL,priority TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',created TEXT NOT NULL)''')
            c.execute('CREATE TABLE notifications(key TEXT PRIMARY KEY,sent_at TEXT NOT NULL)')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_crud_and_persistence(self):
        event={'id':'abc','name':'Sample CTF','description':'','category':'CTF','organizer':'','website':'','registrationUrl':'','start':'2030-01-01T00:00:00+00:00','end':'','deadline':'','timezone':'UTC','status':'Interested','priority':'High','notes':'','created':'2026-01-01T00:00:00+00:00'}
        with server.db() as c:c.execute('INSERT INTO competitions(id,name,category,start,timezone,status,priority,created) VALUES(:id,:name,:category,:start,:timezone,:status,:priority,:created)',event)
        self.assertEqual(server.events()[0]['name'],'Sample CTF')
        with server.db() as c:c.execute('UPDATE competitions SET name=? WHERE id=?',('Edited CTF','abc'))
        self.assertEqual(server.events()[0]['name'],'Edited CTF')
        with server.db() as c:c.execute('DELETE FROM competitions WHERE id=?',('abc',))
        self.assertEqual(server.events(),[])
    def test_reminder_deduplication(self):
        with patch('subprocess.Popen') as popen, patch('server.shutil.which',return_value='/usr/bin/notify-send'), patch.dict(os.environ,{'DBUS_SESSION_BUS_ADDRESS':'test'}):
            server.notify('Reminder','Test','unique-reminder');server.notify('Reminder','Test','unique-reminder')
            self.assertEqual(popen.call_count,1)
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM notifications WHERE key=?',('unique-reminder',)).fetchone()[0],1)
    def test_windows_toast_branch_and_deduplication(self):
        toast=types.SimpleNamespace(show=unittest.mock.Mock())
        notification=unittest.mock.Mock(return_value=toast)
        winotify=types.ModuleType('winotify');winotify.Notification=notification
        with patch.dict(sys.modules,{'winotify':winotify}):
            server.notify('Windows reminder','Test toast','windows-reminder',system='nt')
            server.notify('Windows reminder','Test toast','windows-reminder',system='nt')
        self.assertEqual(notification.call_count,1)
        toast.show.assert_called_once()

if __name__=='__main__':unittest.main()
