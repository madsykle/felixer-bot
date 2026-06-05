import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import telegram_bot


class UIHelperTests(unittest.IsolatedAsyncioTestCase):
    async def test_show_pahe_details_filters_to_preferred_resolution(self):
        context = SimpleNamespace(user_data={})
        edit = AsyncMock()
        details = {
            'id': 5,
            'title': 'Movie Title',
            'year': '2024',
            'rating': '8.1',
            'genres': ['Action'],
            'image': '',
            'synopsis': 'Hi',
            'episodes': [],
            'movie_dls': [
                {'res': '1080P', 'codec': 'HEVC', 'size': '1GB', 'ico': '🔴', 'name': 'Mega', 'url': 'u1'},
                {'res': '720P', 'codec': 'AVC', 'size': '700MB', 'ico': '🟣', 'name': 'PixelDrain', 'url': 'u2'},
            ],
        }
        with patch('felixer.ui.api_detail', AsyncMock(return_value=details)):
            with patch.object(telegram_bot.database, 'get_user_setting', AsyncMock(return_value='720P')):
                await telegram_bot.show_pahe_details(edit, 5, context, 1)

        self.assertIn('groups', context.user_data)
        self.assertEqual(list(context.user_data['groups'].keys()), ['1080P HEVC (1GB)', '720P AVC (700MB)'])
        text = edit.await_args.args[0]
        markup = edit.await_args.kwargs['reply_markup']
        labels = [btn.text for row in markup.inline_keyboard for btn in row]
        self.assertIn('Movie Title', text)
        self.assertIn('720P AVC (700MB)', labels)
        self.assertNotIn('1080P HEVC (1GB)', labels)


if __name__ == '__main__':
    unittest.main()
