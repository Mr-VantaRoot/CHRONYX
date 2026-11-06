import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_migration_home = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = _migration_home.name
import server


def make_legacy_database(path, names=('Legacy CTF',), wal=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    if wal:
        connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('CREATE TABLE competitions(id TEXT PRIMARY KEY, name TEXT)')
    connection.execute('CREATE TABLE notifications(key TEXT PRIMARY KEY, status TEXT)')
    connection.executemany('INSERT INTO competitions VALUES(?,?)', [(f'id-{i}', name) for i, name in enumerate(names)])
    connection.execute("INSERT INTO notifications VALUES('id-0:start:1d:2030','delivered')")
    connection.commit()
    return connection


class LegacyMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.legacy = Path(self.temp.name) / 'vanta'
        self.data = Path(self.temp.name) / 'chronyx'
        self.data.mkdir()

    def rows(self, path, table='competitions'):
        with sqlite3.connect(path) as connection:
            return connection.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall()

    def test_copies_the_old_database_and_leaves_the_old_folder_untouched(self):
        make_legacy_database(self.legacy / 'vanta.sqlite3', ('A', 'B')).close()
        before = (self.legacy / 'vanta.sqlite3').read_bytes()
        self.assertEqual(server.migrate_legacy_data(self.data, self.legacy), 'migrated')
        self.assertEqual(self.rows(self.data / 'chronyx.sqlite3'), [('id-0', 'A'), ('id-1', 'B')])
        self.assertEqual(self.rows(self.data / 'chronyx.sqlite3', 'notifications'), [('id-0:start:1d:2030', 'delivered')])
        self.assertTrue((self.data / '.migrated-from-vanta').exists())
        self.assertEqual((self.legacy / 'vanta.sqlite3').read_bytes(), before)
        self.assertEqual(list(self.data.glob('.*.migrating')), [])

    def test_includes_uncheckpointed_write_ahead_log_data(self):
        open_connection = make_legacy_database(self.legacy / 'vanta.sqlite3', ('Only in WAL',), wal=True)
        try:
            self.assertEqual(server.migrate_legacy_data(self.data, self.legacy), 'migrated')
        finally:
            open_connection.close()
        self.assertEqual(self.rows(self.data / 'chronyx.sqlite3'), [('id-0', 'Only in WAL')])

    def test_runs_only_once_even_if_the_new_database_is_removed(self):
        make_legacy_database(self.legacy / 'vanta.sqlite3').close()
        self.assertEqual(server.migrate_legacy_data(self.data, self.legacy), 'migrated')
        (self.data / 'chronyx.sqlite3').unlink()
        self.assertEqual(server.migrate_legacy_data(self.data, self.legacy), 'skipped')
        self.assertFalse((self.data / 'chronyx.sqlite3').exists())

    def test_never_overwrites_an_existing_new_database(self):
        make_legacy_database(self.legacy / 'vanta.sqlite3', ('Old',)).close()
        make_legacy_database(self.data / 'chronyx.sqlite3', ('New',)).close()
        self.assertEqual(server.migrate_legacy_data(self.data, self.legacy), 'skipped')
        self.assertEqual(self.rows(self.data / 'chronyx.sqlite3'), [('id-0', 'New')])

    def test_nothing_to_migrate_on_a_fresh_install(self):
        self.assertEqual(server.migrate_legacy_data(self.data, self.legacy), 'skipped')
        self.assertEqual(list(self.data.iterdir()), [])

    def test_a_corrupt_old_database_fails_safely_without_partial_files(self):
        self.legacy.mkdir()
        (self.legacy / 'vanta.sqlite3').write_bytes(b'this is not a sqlite database' * 100)
        self.assertEqual(server.migrate_legacy_data(self.data, self.legacy), 'failed')
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertEqual((self.legacy / 'vanta.sqlite3').read_bytes(), b'this is not a sqlite database' * 100)

    def test_an_unwritable_destination_reports_failure(self):
        make_legacy_database(self.legacy / 'vanta.sqlite3').close()
        with patch('server.os.replace', side_effect=OSError('disk full')):
            self.assertEqual(server.migrate_legacy_data(self.data, self.legacy), 'failed')
        self.assertEqual(list(self.data.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
