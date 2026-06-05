import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PAHE_WP = 'https://pahe.ink/wp-json/wp/v2/posts'
UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/125.0.0.0 Safari/537.36'
)
SHORTLINK_HOSTS = ['teknoasian.com', 'intercelestial.com', 'go.kashtbhanjandev.in']

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logging.INFO)
log = logging.getLogger('pahe')

PLAYWRIGHT_SEM = asyncio.Semaphore(3)
