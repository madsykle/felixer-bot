import unittest
from unittest.mock import patch

import telegram_bot


class PaheParsingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        telegram_bot._scache._d.clear()
        telegram_bot._dcache._d.clear()

    def test_parse_dls_extracts_quality_and_hosts(self):
        html = '''
        <div class="box download">
          <b>1080p x265 DD+5.1 1.5GB</b>
          <a href="https://short.example/a" target="_blank" class="shortc-button small mg ">MG</a>
          <a href="https://short.example/b" target="_blank" class="shortc-button small pd ">PD</a>
        </div></div>
        '''
        links = telegram_bot._parse_dls(html)
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]['res'], '1080P')
        self.assertEqual(links[0]['codec'], 'HEVC')
        self.assertEqual(links[0]['audio'], 'DD+5.1')
        self.assertEqual(links[0]['name'], 'Mega')
        self.assertEqual(links[1]['name'], 'PixelDrain')

    async def test_api_search_parses_metadata(self):
        fake_posts = [{
            'id': 7,
            'title': {'rendered': 'Example Movie 2024'},
            'content': {'rendered': '<img src="https://img/x.jpg"> Rating: 8.5 / 10 action comedy'},
            'excerpt': {'rendered': '<p>Hello world</p>'},
        }]
        with patch('felixer.pahe._fetch', return_value=fake_posts):
            results = await telegram_bot.api_search('Example')

        self.assertEqual(results[0]['id'], 7)
        self.assertEqual(results[0]['year'], '2024')
        self.assertEqual(results[0]['rating'], '8.5')
        self.assertEqual(results[0]['genres'], ['Action', 'Comedy'])
        self.assertEqual(results[0]['synopsis'], 'Hello world')

    async def test_api_detail_parses_episode_groups(self):
        fake_post = {
            'title': {'rendered': 'Example Show 2023'},
            'content': {'rendered': '''
                <ul class="tabs-nav"><li>Episode 1</li><li>Episode 2</li></ul>
                <div class="pane"><div class="box download"><b>720p x264 700MB</b>
                <a href="https://short/a" target="_blank" class="shortc-button small mg ">MG</a>
                </div></div>
                <div class="pane"><div class="box download"><b>1080p x265 1.4GB</b>
                <a href="https://short/b" target="_blank" class="shortc-button small pd ">PD</a>
                </div></div>
            '''},
            'excerpt': {'rendered': '<p>Series synopsis</p>'},
        }
        with patch('felixer.pahe._fetch', return_value=fake_post):
            details = await telegram_bot.api_detail(99)

        self.assertEqual(details['year'], '2023')
        self.assertEqual(len(details['episodes']), 2)
        self.assertEqual(details['episodes'][0]['ep'], 'Episode 1')
        self.assertEqual(details['episodes'][0]['dls'][0]['name'], 'Mega')
        self.assertEqual(details['episodes'][1]['dls'][0]['name'], 'PixelDrain')


if __name__ == '__main__':
    unittest.main()
