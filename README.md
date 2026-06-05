# 🎬 Felixer Bot

> **Note:** 🤖 **Vibecoded & Human-Tested**
> I built this mostly through "vibecoding" with AI, but I've personally run the code, tested it heavily, and made sure it's actually stable for production.

I got tired of clicking through ten pages of ads and CAPTCHAs just to get a download link from Pahe or PSA. So I made a Telegram bot that does the dirty work. 

You just search for a movie or show in Telegram. The bot hits **Pahe.ink** or **PSA.wf**, scrapes the releases, and lets you pick your resolution. Once you pick a link, it spins up a headless browser (Playwright), punches through Cloudflare using FlareSolverr, runs a few userscripts to skip the countdowns, and hands you the clean Mega or Pixeldrain link. No pop-ups. No redirect loops.

## What it actually does
- **Searches inline**: Find stuff directly in Telegram.
- **Grabs the real links**: It chews through `ouo.io`, `teknoasian`, `spacetica`, and all those other annoying shorteners. If a link has three redirects nested inside each other, the bot just follows them until it hits the actual filehost.
- **Bypasses Cloudflare**: PSA and Pahe love to block bots. We get around this using FlareSolverr and Playwright stealth.
- **Won't crash your server**: It uses an async semaphore so you don't accidentally spawn 50 headless Chrome instances and blow up your RAM.

## 🛠️ Requirements
- Python 3.10+
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) running locally

## ⚙️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/madsykle/felixer-bot.git
   cd felixer-bot
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright Browsers:**
   ```bash
   playwright install chromium
   ```

4. **Start FlareSolverr:**
   The easiest way is via Docker. Leave it running on the default port `8191`.
   ```bash
   docker run -d \
     --name=flaresolverr \
     -p 8191:8191 \
     -e LOG_LEVEL=info \
     --restart unless-stopped \
     ghcr.io/flaresolverr/flaresolverr:latest
   ```

5. **Configure Environment:**
   Copy the example environment file and insert your bot token.
   ```bash
   cp .env.example .env
   # Edit .env and paste your TELEGRAM_BOT_TOKEN
   ```

## 🚀 Running the Bot
Run the bot directly via Python:
```bash
python telegram_bot.py
```
Or run it in the background using `nohup`:
```bash
nohup python telegram_bot.py > bot.log 2>&1 &
```

## 📂 Project Structure
- `telegram_bot.py` - The core asynchronous Telegram bot loop and Playwright bypass orchestrator.
- `psa_core.py` - Module for parsing and scraping search results and release qualities from `psa.wf`.
- `universal_domains.py` - A massive, maintained list of shortener domains imported to dynamically route pages.

## 🤝 Contributing
Feel free to open an issue or submit a Pull Request if you'd like to add support for new shorteners or fix bugs. 

## 📝 License
This project is open-source and available under the MIT License.
