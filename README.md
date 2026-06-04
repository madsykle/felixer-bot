# 🎬 Pahe Telegram Bot

A powerful Telegram bot designed to let you search, browse, and securely fetch direct download links for movies and TV shows from **Pahe.ink** and **PSA.wf**. Say goodbye to annoying ads, malicious pop-ups, and endless shortener loops—this bot completely bypasses them for you using headless browser automation and Cloudflare bypass techniques!

## ✨ Features
- 🔍 **Interactive Search**: Search movies/series natively in Telegram and select titles using sleek inline buttons.
- 💾 **Resolution Selection**: Shows available resolutions (720p, 1080p, 2160p), codecs (HEVC, AVC), and host options (Mega, Pixeldrain, Google Drive, etc.).
- 🚀 **Universal Ad-Bypasser**: Automatically hops through annoying interstitial links (ouo.io, teknoasian, spacetica, go2.pics, blogmystt, linegee, and more) to extract the pure final destination link.
- 🛡️ **Anti-Bot Circumvention**: Utilizes a combination of **Playwright** + Greasemonkey Userscripts + **FlareSolverr** to solve complex Cloudflare Turnstile captchas and bot protections.
- 🚦 **Concurrency Control**: Built-in async semaphore limit to prevent your server from running out of RAM/CPU during high bot traffic.
- 🔁 **Recursive Ouo.io Resolution**: Natively traces down complex multi-hop `ouo.io` and `ouo.press` links to extract the final host.

## 🛠️ Requirements
- Python 3.10+
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) running locally

## ⚙️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/pahe-telegram-bot.git
   cd pahe-telegram-bot
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
- `bypass_ouo.py` - Specifically designed to circumvent `ouo.io/press` Cloudflare protections using FlareSolverr.
- `userscripts/` - Essential Greasemonkey scripts used by Playwright to accelerate countdowns and bypass basic shorteners.

## 🤝 Contributing
Feel free to open an issue or submit a Pull Request if you'd like to add support for new shorteners or fix bugs. 

## 📝 License
This project is open-source and available under the MIT License.
