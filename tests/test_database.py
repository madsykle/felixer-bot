import tempfile
import unittest
from unittest.mock import patch

import database


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.old_path = database.DB_PATH
        database.DB_PATH = self.tmp.name
        await database.init_db()

    async def asyncTearDown(self):
        database.DB_PATH = self.old_path

    async def test_cache_round_trip_and_expiration(self):
        created_at = 2_000_000_000
        with patch('database.time.time', return_value=created_at):
            await database.put_cached_link('orig', 'final')
        self.assertEqual(await database.get_cached_link('orig'), 'final')

        with patch('database.time.time', return_value=created_at + database.EXPIRATION_SECONDS + 1):
            self.assertIsNone(await database.get_cached_link('orig'))

    async def test_stats_users_and_settings(self):
        await database.increment_stat('searches')
        await database.increment_stat('searches')
        await database.add_user(123)
        await database.add_user(123)
        await database.set_user_setting(123, 'pref_res', '720p')

        stats = await database.get_all_stats()
        self.assertEqual(stats['searches'], 2)
        self.assertEqual(stats['users'], 1)
        self.assertEqual(await database.get_user_setting(123, 'pref_res'), '720p')
        self.assertEqual(await database.get_user_setting(999, 'pref_res'), 'Ask')


if __name__ == '__main__':
    unittest.main()
