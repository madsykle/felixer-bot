import unittest
from unittest.mock import AsyncMock, patch

import telegram_bot


class FakeApp:
    def __init__(self):
        self.handlers = []
        self.allowed_updates = None

    def add_handler(self, handler):
        self.handlers.append(handler)

    def run_polling(self, allowed_updates=None):
        self.allowed_updates = allowed_updates


class FakeBuilder:
    def __init__(self):
        self.app = FakeApp()
        self.token_value = None
        self.post_init_fn = None

    def token(self, value):
        self.token_value = value
        return self

    def post_init(self, fn):
        self.post_init_fn = fn
        return self

    def build(self):
        return self.app


class AppWiringTests(unittest.IsolatedAsyncioTestCase):
    def test_main_registers_handlers_and_allowed_updates(self):
        builder = FakeBuilder()
        with patch.object(telegram_bot, 'ApplicationBuilder', return_value=builder):
            with patch.object(telegram_bot, 'BOT_TOKEN', 'token-123'):
                telegram_bot.main()

        self.assertEqual(builder.token_value, 'token-123')
        self.assertIs(builder.post_init_fn, telegram_bot.post_init)
        self.assertEqual(len(builder.app.handlers), 7)
        self.assertEqual(builder.app.allowed_updates, ['message', 'callback_query', 'inline_query'])

    async def test_post_init_initializes_database(self):
        with patch.object(telegram_bot.database, 'init_db', new=AsyncMock()) as init_db:
            await telegram_bot.post_init(object())
        init_db.assert_awaited_once()

    def test_do_smart_bypass_exists(self):
        self.assertTrue(callable(telegram_bot.do_smart_bypass))


if __name__ == '__main__':
    unittest.main()
