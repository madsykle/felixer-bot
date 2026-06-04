"""
Felixer Bot - Interactive Button Flow
"""
import asyncio
import hashlib
import html
import logging
import re
import time
import traceback
from typing import Dict, List

import psa_core
import httpx
from playwright.async_api import async_playwright
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# ━━━━━━━━━━━━━━━━━━━ Config ━━━━━━━━━━━━━━━━━━━━

import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PAHE_WP = "https://pahe.ink/wp-json/wp/v2/posts"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
SHORTLINK_HOSTS = ["teknoasian.com", "intercelestial.com", "go.kashtbhanjandev.in"]

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger("pahe")

PLAYWRIGHT_SEM = asyncio.Semaphore(3)

# ━━━━━━━━━━━━━━━━━━━ Cache ━━━━━━━━━━━━━━━━━━━━━

class Cache:
    def __init__(self, ttl=600):
        self._d: dict = {}
        self._ttl = ttl

    def get(self, k):
        if k in self._d:
            ts, v = self._d[k]
            if time.time() - ts < self._ttl:
                return v
            del self._d[k]
        return None

    def put(self, k, v):
        self._d[k] = (time.time(), v)

_scache = Cache(300)
_dcache = Cache(600)
_bcache = Cache(3600)


from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ━━━━━━━━━━━━━━━━━━━ Cache ━━━━━━━━━━━━━━━━━━━━━
# Kept from old
SVC = {
    "PD": ("PixelDrain", "🟣"), "VF": ("Vofile", "🔵"),
    "GD": ("GoogleDrive", "🟢"), "MG": ("Mega", "🔴"),
    "1F": ("1Fichier", "🟠"), "1D": ("1Download", "🟤"),
    "UTB": ("Utombox", "⚪"), "SD": ("SolidFiles", "🟡"),
}

# ━━━━━━━━━━━━━━ Pahe.ink helpers ━━━━━━━━━━━━━━━━

async def _fetch(url: str, params: dict = None) -> dict | list:
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=25, follow_redirects=True) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def api_search(q: str) -> list[dict]:
    key = q.lower().strip()
    c = _scache.get(key)
    if c is not None:
        return c

    posts = await _fetch(PAHE_WP, {
        "search": q.strip(), "per_page": 20,
        "_fields": "id,title,link,content,excerpt",
    })

    out = []
    for p in posts:
        title = html.unescape(p.get("title", {}).get("rendered", ""))
        content = p.get("content", {}).get("rendered", "")
        yr = re.search(r"\b((?:19|20)\d{2})\b", title)
        rt = re.search(r"Rating:\s*([\d.]+)\s*/\s*10", content)
        genres = [g.title() for g in
                  ["action","adventure","sci-fi","drama","comedy","horror",
                   "thriller","romance","mystery","crime","animation","fantasy"]
                  if g in content.lower()]
        is_series = "tabs-nav" in content or bool(re.search(r"Episode\s+\d+", content))
        out.append({
            "id": p.get("id"), "title": title,
            "year": yr.group(1) if yr else "",
            "rating": rt.group(1) if rt else "",
            "genres": genres[:3], "is_series": is_series,
        })

    _scache.put(key, out)
    return out


def _parse_dls(content: str) -> list[dict]:
    dls = []
    boxes = re.findall(r'<div class="box download[^"]*">.*?</div>\s*</div></div>', content, re.DOTALL)
    if not boxes:
        boxes = [p for p in re.split(r"\s*</div>\s*</div>", content)
                 if "box download" in p and "e3lan" not in p]

    for box in boxes:
        if "e3lan" in box or "atOptions" in box:
            continue
        for seg in box.split("<b>"):
            if not seg.strip() or "</b>" not in seg:
                continue
            head, rest = seg.split("</b>", 1)
            qt = re.sub(r"<[^>]+>", "", head).strip()
            sm = re.search(r"^\s*\|?\s*(\d+\.?\d*\s*(?:GB|MB|KB))", rest, re.I)
            size = sm.group(1).strip() if sm else ""
            rm = re.search(r"(\d+p)", qt, re.I)
            res = rm.group(1).upper() if rm else ""
            codec = ""
            if "x265" in qt.lower(): codec = "HEVC"
            elif "x264" in qt.lower(): codec = "AVC"
            if "hdr" in qt.lower(): codec = (codec + " HDR").strip()
            audio = ""
            for a in ["DD+7.1","DD+5.1","DD5.1","Atmos","TrueHD","DTS-HD","DTS","6CH"]:
                if a.lower() in qt.lower():
                    audio = a; break
            for url, sc in re.findall(
                r'<a href="([^"]+)" target="_blank" class="shortc-button small \w+\s*">([^<]+)</a>', rest
            ):
                s = sc.strip().upper()
                name, ico = SVC.get(s, (s, "🔗"))
                dls.append({"svc": s, "name": name, "ico": ico, "url": url,
                            "res": res, "size": size, "codec": codec, "audio": audio})
    return dls


async def api_detail(pid: int) -> dict:
    c = _dcache.get(pid)
    if c is not None:
        return c

    p = await _fetch(f"https://pahe.ink/wp-json/wp/v2/posts/{pid}",
                     {"_fields": "id,title,link,content,excerpt"})

    title = html.unescape(p.get("title", {}).get("rendered", ""))
    content = p.get("content", {}).get("rendered", "")
    yr = re.search(r"\b((?:19|20)\d{2})\b", title)
    rt = re.search(r"Rating:\s*([\d.]+)\s*/\s*10", content)
    genres = [g.title() for g in
              ["action","adventure","sci-fi","drama","comedy","horror",
               "thriller","romance","mystery","crime","animation","fantasy"]
              if g in content.lower()]

    episodes = []
    if "tabs-nav" in content:
        ul_match = re.search(r'<ul class="tabs-nav">(.*?)</ul>', content, re.DOTALL)
        if ul_match:
            headers = re.findall(r"<li>([^<]+)</li>", ul_match.group(1))
        else:
            headers = []
        panes = re.findall(r'<div class="pane">.*?(?=<div class="pane">|$)', content, re.DOTALL)
        for i, pane in enumerate(panes):
            num = headers[i].strip() if i < len(headers) else str(i + 1)
            edl = _parse_dls(pane)
            if edl:
                episodes.append({"ep": num, "dls": edl})

    movie_dls = [] if episodes else _parse_dls(content)

    out = {"id": pid, "title": title, "year": yr.group(1) if yr else "",
           "rating": rt.group(1) if rt else "", "genres": genres[:4],
           "episodes": episodes, "movie_dls": movie_dls}
    _dcache.put(pid, out)
    return out

# All domains the Pahe bypass userscript handles
TEKNOASIAN_DOMAINS = ["teknoasian.com"]
BLOGMYSTT_DOMAINS = [
    "blogmystt.com", "wp2hostt.com", "intercelestial.com", "hosttbuzz.com",
    "policiesreview.com", "healthylifez.com", "insurancemyst.com",
    "hostingbixby.com", "policiesbuzzz.com", "hostingzbuzz.com",
    "bixbyfortech.com", "serverguidez.com", "comparepolicyy.com",
    "cheaplann.com", "vpshostplans.com", "ensureguide.com",
    "fitnessplanss.com", "sharedwebs.com", "hostserverz.com",
    "cloudhostingz.com", "carensureplan.com", "playareaz.com",
    "fitnesstipz.com", "ensuretips.com", "softdevelopp.com",
    "vpzserver.com", "tophostdeal.com", "evensuregd.com",
    "bestensuree.com", "hostzteam.com",
]
GETLINK_DOMAINS = ["pahe.plus", "oii.la", "tpi.li", "old.pahe.plus"]
LINEGEE_DOMAINS = ["linegee.net"]
SPACETICA_DOMAINS = ["spacetica.com"]
WORDCOUNTER_DOMAINS = ["wordcounter.icu"]

ALL_SHORTLINK_DOMAINS = (
    TEKNOASIAN_DOMAINS + BLOGMYSTT_DOMAINS + GETLINK_DOMAINS +
    LINEGEE_DOMAINS + SPACETICA_DOMAINS + WORDCOUNTER_DOMAINS
)

# JS to speed up all timers by 100x (same as the userscript)
SPEEDUP_JS = """
(() => {
    const host = window.location.hostname;
    if (host.includes("pahe.plus") || host.includes("oii.la") || host.includes("linegee.net") || host.includes("tpi.li")) {
        return;
    }
    const origTimeout = window.setTimeout;
    const origInterval = window.setInterval;
    window.setTimeout = (cb, delay, ...args) => origTimeout(cb, (delay||0)/100, ...args);
    window.setInterval = (cb, delay, ...args) => origInterval(cb, (delay||0)/100, ...args);
})();
"""


def _match_domain(url: str, domains: list[str]) -> bool:
    for d in domains:
        if d in url:
            return True
    return False


async def _bypass_teknoasian(page) -> str | None:
    """teknoasian.com: verify → skipcontent → form.submit()"""
    log.info("  ↳ teknoasian flow")
    
    for step in range(10):  # max 10 steps
        log.info("  ↳ teknoasian step %d: %s", step, page.url)
        try:
            # Wait for any of the 3 buttons to appear
            btn = await page.wait_for_selector(
                ".humanVerify .verify, .Skipper .skipcontent, .skipcontent, .postnext", 
                timeout=10000
            )
            
            # Check which button it is by evaluating in browser
            action = await page.evaluate("""
                (() => {
                    if (document.querySelector('.humanVerify .verify')) return 'verify';
                    if (document.querySelector('.Skipper .skipcontent, .skipcontent')) return 'skipcontent';
                    if (document.querySelector('.postnext')) return 'postnext';
                    return null;
                })()
            """)
            
            if action == 'verify':
                await page.click(".humanVerify .verify")
                log.info("  ✓ clicked verify")
            elif action == 'skipcontent':
                await asyncio.sleep(1)
                await page.click(".Skipper .skipcontent, .skipcontent")
                log.info("  ✓ clicked skipcontent")
            elif action == 'postnext':
                await asyncio.sleep(1)
                await page.evaluate("""
                    (() => {
                        const btn = document.querySelector('.postnext');
                        if (btn) {
                            const form = btn.closest('form');
                            if (form) { form.submit(); }
                            else { btn.click(); }
                        }
                    })()
                """)
                log.info("  ✓ submitted postnext form")
            
            # Wait for navigation after click
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                await asyncio.sleep(3)
                
        except Exception:
            # If no button found, maybe we reached the final page or a redirect happened automatically
            break

    return None


async def _bypass_blogmystt(page) -> str | None:
    """blogmystt / intercelestial / wp2hostt etc: startButton → getnewlink → verify → skipcontent → postnext"""
    log.info("  ↳ blogmystt flow")

    for step in range(10):
        log.info("  ↳ blogmystt step %d: %s", step, page.url)
        try:
            sel = "#startButton, a#startButton, #getnewlink, button#getnewlink, #lite-start-sora-a, #generater, .humanVerify .verify, #lite-human-verif-button, .Skipper .skipcontent, .skipcontent, #showlink, #lite-end-sora-button, .postnext"
            await page.wait_for_selector(sel, timeout=8000)
            
            action = await page.evaluate(f"""
                (() => {{
                    if (document.querySelector('.postnext')) return 'postnext';
                    if (document.querySelector('#showlink, #lite-end-sora-button')) return 'showlink';
                    if (document.querySelector('.Skipper .skipcontent, .skipcontent')) return 'skipcontent';
                    if (document.querySelector('.humanVerify .verify, #lite-human-verif-button')) return 'verify';
                    if (document.querySelector('#getnewlink, button#getnewlink')) return 'getnewlink';
                    const el = document.querySelector('{sel}');
                    return el ? 'other' : null;
                }})()
            """)
            
            if not action:
                break
                
            if action == 'postnext':
                await page.evaluate("""
                    (() => {
                        const btn = document.querySelector('.postnext');
                        if (btn && btn.closest('form')) { btn.closest('form').submit(); }
                        else { btn.click(); }
                    })()
                """)
                log.info("  ✓ submitted postnext")
            else:
                # Just click whatever was found
                await page.evaluate(f"""
                    (() => {{
                        const el = document.querySelector('{sel}');
                        if (el) el.click();
                    }})()
                """)
                log.info("  ✓ clicked %s", action)
            
            # Wait for navigation
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                await asyncio.sleep(3)
                
        except Exception:
            break

    return None


async def _bypass_getlink(page) -> str | None:
    """pahe.plus / oii.la / tpi.li: wait for .get-link:not(.disabled) and follow href"""
    log.info("  ↳ getlink flow")

    # Some of these have a form with a button first
    try:
        form_btn = await page.query_selector("form:not(.td-search-form):not(.go-link) button")
        if form_btn:
            await form_btn.click()
            log.info("  ✓ clicked form button")
            await asyncio.sleep(3)
    except Exception:
        pass

    # Check for #invisibleCaptchaShortlink (used by pahe.plus)
    try:
        captcha_btn = await page.wait_for_selector("#invisibleCaptchaShortlink", timeout=5000, state="attached")
        if captcha_btn:
            log.info("  ⚠️ pahe.plus requires manual hCaptcha solve. Aborting wait.")
            return None
    except Exception:
        pass

    # Check for actual visible captchas
    has_captcha = await page.evaluate("""
        (() => {
            return document.querySelector('.h-captcha, .g-recaptcha, iframe[src*="hcaptcha.com"], iframe[src*="recaptcha"]') !== null;
        })();
    """)
    if has_captcha:
        log.info("  ⚠️ Found human captcha. Aborting wait.")
        return None

    # Wait for the final get-link to appear
    for _ in range(60):
        try:
            href = await page.evaluate("""
                (() => {
                    const el = document.querySelector('a.get-link[href]:not(.disabled)');
                    return el ? el.href : null;
                })()
            """)
            if href and href != "javascript:void(0)" and "about:blank" not in href:
                log.info("  ✓ got getlink href: %s", href[:60])
                return href
        except Exception:
            pass
        await asyncio.sleep(0.5)

    return None


async def _bypass_linegee(page) -> str | None:
    """linegee.net: extract base64-encoded URL from inline script"""
    log.info("  ↳ linegee flow")

    try:
        # The userscript extracts base64 from: location.href = ... atob('BASE64')
        result = await page.evaluate("""
            (() => {
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    const m = s.textContent.match(/location\\.href.*atob\\(['"]([^'"]+)['"]/);
                    if (m) return atob(m[1]);
                }
                return null;
            })()
        """)
        if result:
            final = page.url + result
            log.info("  ✓ decoded linegee URL")
            return final
    except Exception:
        pass

    # Fallback: click the .btn
    try:
        await page.click(".btn")
        await asyncio.sleep(3)
    except Exception:
        pass

    return None


async def _bypass_wordcounter(page) -> str | None:
    """wordcounter.icu: click captcha shortlink → get-link"""
    log.info("  ↳ wordcounter flow")

    try:
        await page.wait_for_selector("#invisibleCaptchaShortlink, button#getlink", timeout=8000)
        await page.click("#invisibleCaptchaShortlink, button#getlink")
        log.info("  ✓ clicked captcha/getlink")
        await asyncio.sleep(3)
    except Exception:
        pass

    for _ in range(40):
        try:
            href = await page.evaluate("""
                (() => {
                    const el = document.querySelector('a.get-link[href]:not(.disabled)');
                    return el ? el.href : null;
                })()
            """)
            if href and "about:blank" not in href:
                return href
        except Exception:
            pass
        await asyncio.sleep(0.5)

    return None


async def _bypass_spacetica(page) -> str | None:
    """spacetica.com / old.pahe.plus: click .btn-primary then follow redirect"""
    log.info("  ↳ spacetica flow")

    try:
        await page.wait_for_selector(".btn.btn-primary.btn-xs, a:has(button)", timeout=8000)
        await page.click(".btn.btn-primary.btn-xs, a:has(button)")
        log.info("  ✓ clicked button")
        await asyncio.sleep(3)
    except Exception:
        pass

    return None


async def do_bypass(url: str) -> str:
    """Master bypass: detect domain and route to the right handler."""
    c = _bcache.get(url)
    if c is not None:
        log.info("Bypass cache hit")
        return c

    log.info("Bypassing: %s", url[:80])
    try:
        async with PLAYWRIGHT_SEM:
            async with async_playwright() as pw:
                br = await pw.chromium.launch(headless=True)
                ctx = await br.new_context(user_agent=UA)
                page = await ctx.new_page()

                # Inject timer speedup BEFORE navigation (like the userscript)
                # The JS itself checks the hostname to avoid breaking specific sites
                await page.add_init_script(SPEEDUP_JS)

                await page.goto(url, wait_until="load", timeout=30000)

                # Route to the correct bypass handler, allowing for multiple domain hops
                for hop in range(5):
                    cur = page.url
                    if not _match_domain(cur, ALL_SHORTLINK_DOMAINS):
                        break
                    
                    log.info("  ↳ hop %d: %s", hop, cur)
                    direct_result = None
                    if _match_domain(cur, TEKNOASIAN_DOMAINS):
                        direct_result = await _bypass_teknoasian(page)
                    elif _match_domain(cur, BLOGMYSTT_DOMAINS):
                        direct_result = await _bypass_blogmystt(page)
                    elif _match_domain(cur, GETLINK_DOMAINS):
                        direct_result = await _bypass_getlink(page)
                    elif _match_domain(cur, LINEGEE_DOMAINS):
                        direct_result = await _bypass_linegee(page)
                    elif _match_domain(cur, WORDCOUNTER_DOMAINS):
                        direct_result = await _bypass_wordcounter(page)
                    elif _match_domain(cur, SPACETICA_DOMAINS):
                        direct_result = await _bypass_spacetica(page)
                    else:
                        log.info("  ↳ unknown domain, trying generic flow")
                        direct_result = await _bypass_teknoasian(page)

                    if direct_result:
                        if not _match_domain(direct_result, ALL_SHORTLINK_DOMAINS):
                            await br.close()
                            _bcache.put(url, direct_result)
                            log.info("  ✅ bypass → %s", direct_result[:80])
                            return direct_result
                        else:
                            # Follow the extracted link for the next hop
                            log.info("  ↳ navigating to extracted link: %s", direct_result)
                            await page.goto(direct_result, wait_until="load")
                            continue

                    # Wait for the current handler to cause a redirect away from the current domain
                    current_domain_match = next((d for d in ALL_SHORTLINK_DOMAINS if d in cur), None)
                    redirected = False
                    for _ in range(40):
                        new_url = page.url
                        if current_domain_match and current_domain_match not in new_url:
                            redirected = True
                            break
                        await asyncio.sleep(0.5)
                
                    if not redirected:
                        break # stuck

                # Final check
                for _ in range(30):
                    cur = page.url
                    if not _match_domain(cur, ALL_SHORTLINK_DOMAINS) and "about:blank" not in cur:
                        await br.close()
                        _bcache.put(url, cur)
                        log.info("  ✅ redirect → %s", cur[:80])
                        return cur
                    await asyncio.sleep(0.5)

                final = page.url
                await br.close()
                _bcache.put(url, final)
                log.info("  ⚠️ final (may be incomplete): %s", final[:80])
                return final

    except Exception as e:
        log.error("Bypass error: %s\n%s", e, traceback.format_exc())
        return url

# ━━━━━━━━━━━━━━━━━ Send helper ━━━━━━━━━━━━━━━━━━

E = html.escape


# ━━━━━━━━━━━━━━━━━━━ Telegram UI Flow ━━━━━━━━━━━━━━

def _build_menu(buttons, n_cols):
    return [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎬 **Welcome to Felixer Bot!**\n\n"
        "Just **type the name of a movie or TV show** below to search for it.\n"
        "I'll give you buttons to select the quality, choose a download link, and automatically bypass the ads!"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if query.startswith('/'): return
    
    if query.startswith("http://") or query.startswith("https://"):
        await update.message.reply_text(f"🔗 Detected a link. Attempting bypass...", parse_mode=ParseMode.MARKDOWN)
        try:
            # We use do_psa_bypass because it has FlareSolverr and Playwright + userscripts
            # It will bypass shortlinks like psa.pm and sh.psa.wf easily!
            final_link = await do_psa_bypass(query)
            if final_link == query:
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open Link", url=final_link)]])
                await update.message.reply_text(f"⚠️ Could not bypass the link further:\n`{final_link}`", parse_mode=ParseMode.MARKDOWN, reply_markup=btn)
            else:
                await update.message.reply_text(f"✅ Bypassed Link:\n`{final_link}`", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to bypass: {e}")
        return

    buttons = [
        InlineKeyboardButton("Search Pahe.ink", callback_data=f"src_pahe:{query[:50]}"),
        InlineKeyboardButton("Search PSA.wf", callback_data=f"src_psa:{query[:50]}")
    ]
    reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 2))
    await update.message.reply_text(f"🔍 Where do you want to search for `{query}`?", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def perform_pahe_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    query_obj = update.callback_query
    await query_obj.edit_message_text(f"🔍 Searching Pahe.ink for `{query}`...", parse_mode=ParseMode.MARKDOWN)
    
    try:
        results = await api_search(query)
        if not results:
            await query_obj.edit_message_text(f"❌ No results found on Pahe for `{query}`.", parse_mode=ParseMode.MARKDOWN)
            return
            
        buttons = []
        for r in results[:10]:
            text = f"{'📺' if r['is_series'] else '🎬'} {r['title']}"
            if r['year']: text += f" ({r['year']})"
            if r['rating']: text += f" - {r['rating']}⭐"
            buttons.append(InlineKeyboardButton(text, callback_data=f"sel:{r['id']}"))
            
        reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 1))
        await query_obj.edit_message_text(f"✅ Found {len(results)} results on Pahe for `{query}`.\nSelect one:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"Search error: {traceback.format_exc()}")
        await query_obj.edit_message_text(f"❌ Error searching Pahe: {e}")

async def do_psa_bypass(url: str) -> str:
    """Bypass PSA shortlinks using FlareSolverr + provided userscripts."""
    c = _bcache.get(url)
    if c is not None:
        return c

    log.info("PSA Bypassing: %s", url)
    final_url = url
    try:
        # Step 1: Use FlareSolverr to resolve the goto link
        import requests
        FLARESOLVERR_URL = "http://localhost:8191/v1"
        payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}
        
        res = await asyncio.to_thread(requests.post, FLARESOLVERR_URL, json=payload, headers={"Content-Type": "application/json"})
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "ok":
                flare_url = data["solution"]["url"]
                if "goto" not in flare_url:
                    final_url = flare_url
                    log.info("FlareSolverr resolved goto link: %s", final_url)
    except Exception as e:
        log.error("FlareSolverr error: %s", e)

    # Step 2: Use Playwright + userscripts to bypass the shortlink
    try:
        import os
        async with PLAYWRIGHT_SEM:
            async with async_playwright() as pw:
                br = await pw.chromium.launch(headless=True)
                ctx = await br.new_context(user_agent=UA)
                page = await ctx.new_page()

                # Load bypass userscripts
                script_path = "userscripts/Bypass All Shortlinks Debloated.user.js"
                if os.path.exists(script_path):
                    with open(script_path, "r", encoding="utf-8") as f:
                        script_text = f.read()
                        polyfill = """
                        window.GM_getValue = function() { return null; };
                        window.GM_setValue = function() {};
                        window.GM_xmlhttpRequest = function() {};
                        window.GM_registerMenuCommand = function() {};
                        window.GM_addStyle = function() {};
                        var GM_info = {};
                        """
                        monkey_config_script = ""
                        monkey_config_path = "userscripts/MonkeyConfig.js"
                        if os.path.exists(monkey_config_path):
                            with open(monkey_config_path, "r", encoding="utf-8") as fm:
                                monkey_config_script = fm.read()
                    
                        await page.add_init_script(polyfill + "\n" + monkey_config_script + "\n" + script_text)
                        log.info("Loaded Bypass All Shortlinks script in Playwright context")
                    
                script_path2 = "userscripts/AdsBypasser.user.js"
                if os.path.exists(script_path2):
                    with open(script_path2, "r", encoding="utf-8") as f:
                        script_text = f.read()
                        await page.add_init_script(polyfill + script_text)
                        log.info("Loaded AdsBypasser script in Playwright context")

                try:
                    await page.goto(final_url, wait_until="load", timeout=30000)
                except Exception:
                    pass

                original_domain = final_url.split("/")[2] if len(final_url.split("/")) > 2 else ""
                last_url = final_url
                unchanged_count = 0

                for _ in range(40):
                    current = page.url
                    if current != last_url:
                        last_url = current
                        unchanged_count = 0
                    else:
                        unchanged_count += 1

                    if any(x in current for x in ["mega.nz", "pixeldrain.com", "gofile.io", "drive.google", "qiwi", "1drv.ms", "1fichier", "buzzheavier", "mediafire.com"]):
                        await br.close()
                        _bcache.put(url, current)
                        return current
                
                    if "ouo.io" in current or "ouo.press" in current:
                        log.info(f"Intercepted ouo link: {current}")
                        await br.close()
                    
                        import bypass_ouo
                        final_ouo = await asyncio.to_thread(bypass_ouo.bypass_ouo, current)
                        if final_ouo:
                            # Sometimes ouo returns go2.pics with base64 id
                            if "go2.pics/go2?id=" in final_ouo:
                                import base64
                                import urllib.parse
                                b64_id = urllib.parse.parse_qs(urllib.parse.urlparse(final_ouo).query).get('id', [''])[0]
                                if b64_id:
                                    try:
                                        final_ouo = base64.b64decode(b64_id).decode('utf-8')
                                    except Exception:
                                        pass
                            _bcache.put(url, final_ouo)
                            return final_ouo
                        return current
                    
                    current_domain = current.split("/")[2] if len(current.split("/")) > 2 else ""
                    if unchanged_count >= 10 and current_domain != original_domain and "psa.wf" not in current and "psa.pm" not in current and "about:blank" not in current:
                        await br.close()
                        _bcache.put(url, current)
                        return current
                
                    await asyncio.sleep(0.5)

                current = page.url
                await br.close()
                return current
    except Exception as e:
        log.error("PSA bypass error: %s", e)
        return final_url

async def perform_psa_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    query_obj = update.callback_query
    await query_obj.edit_message_text(f"🔍 Searching PSA.wf for `{query}`...", parse_mode=ParseMode.MARKDOWN)
    
    try:
        import psa_core
        results = await asyncio.to_thread(psa_core.search_psa, query)
        if not results:
            await query_obj.edit_message_text(f"❌ No results found on PSA for `{query}`.", parse_mode=ParseMode.MARKDOWN)
            return
            
        buttons = []
        for r in results[:10]:
            text = f"🎬 {r['title'][:40]}"
            idx = len(context.user_data.get('psa_urls', []))
            if 'psa_urls' not in context.user_data:
                context.user_data['psa_urls'] = []
            context.user_data['psa_urls'].append(r['link'])
            buttons.append(InlineKeyboardButton(text, callback_data=f"psa_sel:{idx}"))
            
        reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 1))
        await query_obj.edit_message_text(f"✅ Found {len(results)} results on PSA for `{query}`.\nSelect one:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"PSA Search error: {traceback.format_exc()}")
        await query_obj.edit_message_text(f"❌ Error searching PSA: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    try:
        if data.startswith("src_"):
            if data.startswith("src_pahe:"):
                await perform_pahe_search(update, context, data.split(":", 1)[1])
            elif data.startswith("src_psa:"):
                await perform_psa_search(update, context, data.split(":", 1)[1])
            return

        if data.startswith("sel:"):
            pid = int(data.split(":")[1])
            await query.edit_message_text("⏳ Fetching details...")
            details = await api_detail(pid)
            
            if details.get("episodes"):
                context.user_data['details'] = details
                buttons = []
                for idx, ep in enumerate(details["episodes"]):
                    buttons.append(InlineKeyboardButton(ep["ep"], callback_data=f"ep:{idx}"))
                
                reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 2))
                await query.edit_message_text(f"📺 {details['title']}\nSelect an option:", reply_markup=reply_markup)
                return

            # Group qualities for movies
            dls = details.get("movie_dls", [])
            if not dls:
                await query.edit_message_text("❌ No download links found for this post.")
                return
                
            context.user_data['dls'] = dls  # Store in context for next steps
            
            # Group by resolution/codec
            groups = {}
            for d in dls:
                k = f"{d['res']} {d['codec']} ({d['size']})".strip()
                if k not in groups:
                    groups[k] = []
                groups[k].append(d)
                
            context.user_data['groups'] = groups
            
            buttons = []
            for k in groups.keys():
                # use md5 hash for callback data to avoid 64 byte limit
                h = hashlib.md5(k.encode()).hexdigest()[:8]
                context.user_data[f"grp_{h}"] = k
                buttons.append(InlineKeyboardButton(k, callback_data=f"qual:{h}"))
                
            buttons.append(InlineKeyboardButton("⬅️ Back to Search (Type new name)", callback_data="ignore"))
            reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 1))
            
            text = f"🎬 {details['title']}\nSelect quality:"
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

        elif data.startswith("ep:"):
            ep_idx = int(data.split(":")[1])
            details = context.user_data.get('details')
            if not details:
                await query.edit_message_text("❌ Session expired. Please search again.")
                return
            
            ep_data = details["episodes"][ep_idx]
            dls = ep_data["dls"]
            if not dls:
                await query.edit_message_text("❌ No download links found for this selection.")
                return
                
            context.user_data['dls'] = dls
            
            groups = {}
            for d in dls:
                k = f"{d['res']} {d['codec']} ({d['size']})".strip()
                if k not in groups:
                    groups[k] = []
                groups[k].append(d)
                
            context.user_data['groups'] = groups
            
            buttons = []
            for k in groups.keys():
                h = hashlib.md5(k.encode()).hexdigest()[:8]
                context.user_data[f"grp_{h}"] = k
                buttons.append(InlineKeyboardButton(k, callback_data=f"qual:{h}"))
                
            buttons.append(InlineKeyboardButton("⬅️ Back to Episodes", callback_data=f"sel:{details['id']}"))
            reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 1))
            await query.edit_message_text(f"📺 {details['title']} - {ep_data['ep']}\nSelect quality:", reply_markup=reply_markup)

            
        elif data.startswith("qual:"):
            h = data.split(":")[1]
            k = context.user_data.get(f"grp_{h}")
            if not k:
                await query.edit_message_text("❌ Session expired. Please search again.")
                return
                
            links = context.user_data['groups'][k]
            context.user_data['links'] = links
            
            buttons = []
            for idx, d in enumerate(links):
                buttons.append(InlineKeyboardButton(f"{d['ico']} {d['name']}", callback_data=f"host:{idx}"))
                
            buttons.append(InlineKeyboardButton("⬅️ Back to Qualities", callback_data="back_qual"))
            reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 2))
            
            await query.edit_message_text(f"💾 Quality: *{k}*\n\nSelect Host:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        elif data == "back_qual":
            groups = context.user_data.get('groups', {})
            if not groups:
                await query.edit_message_text("❌ Session expired. Please search again.")
                return
            buttons = []
            for h, k in [(k, v) for k, v in context.user_data.items() if k.startswith("grp_")]:
                buttons.append(InlineKeyboardButton(k, callback_data=f"qual:{h.replace('grp_','')}"))
            reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 1))
            await query.edit_message_text("Select Quality:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        elif data.startswith("host:"):
            idx = int(data.split(":")[1])
            links = context.user_data.get('links', [])
            if idx >= len(links):
                await query.edit_message_text("❌ Session expired. Please search again.")
                return
                
            link = links[idx]
            
            await query.edit_message_text(f"⏳ Bypassing link for **{link['name']}**... Please wait ~10s", parse_mode=ParseMode.MARKDOWN)
            
            try:
                final_url = await do_bypass(link['url'])
                
                buttons = [[InlineKeyboardButton(f"📥 Open in {link['name']}", url=final_url)]]
                reply_markup = InlineKeyboardMarkup(buttons)
                
                await query.edit_message_text(
                    f"✅ **Success!**\n\n"
                    f"🎬 Quality: {link['res']} {link['codec']}\n"
                    f"💾 Size: {link['size']}\n"
                    f"🔗 Host: {link['name']}\n\n"
                    f"`{final_url}`",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                log.error(f"Bypass error: {traceback.format_exc()}")
                buttons = [[InlineKeyboardButton("🔗 Try Manual Link", url=link['url'])]]
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.edit_message_text(f"❌ Bypass failed: {e}\nYou can try manually below.", reply_markup=reply_markup)
                
        elif data.startswith("psa_sel:"):
            idx = int(data.split(":")[1])
            urls = context.user_data.get('psa_urls', [])
            if idx >= len(urls):
                await query.edit_message_text("❌ Session expired. Please search again.")
                return
                
            url = urls[idx]
            await query.edit_message_text("⏳ Fetching PSA details via FlareSolverr...")
            
            details = await asyncio.to_thread(psa_core.get_psa_details, url)
            qualities = details.get("qualities", {})
            
            if not qualities:
                await query.edit_message_text("❌ No download links found for this post.")
                return
                
            context.user_data['psa_groups'] = qualities
            
            buttons = []
            for k in qualities.keys():
                h = hashlib.md5(k.encode()).hexdigest()[:8]
                context.user_data[f"psa_grp_{h}"] = k
                buttons.append(InlineKeyboardButton(k[:40], callback_data=f"psa_qual:{h}"))
                
            buttons.append(InlineKeyboardButton("⬅️ Back to Search (Type new name)", callback_data="ignore"))
            reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 1))
            
            text = f"🎬 Select quality from PSA:"
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        elif data.startswith("psa_qual:"):
            h = data.split(":")[1]
            k = context.user_data.get(f"psa_grp_{h}")
            if not k:
                await query.edit_message_text("❌ Session expired. Please search again.")
                return
                
            links = context.user_data['psa_groups'][k]
            context.user_data['psa_links'] = links
            
            buttons = []
            for idx, d in enumerate(links):
                buttons.append(InlineKeyboardButton(f"🔗 {d['name'][:20]}", callback_data=f"psa_host:{idx}"))
                
            buttons.append(InlineKeyboardButton("⬅️ Back", callback_data="ignore"))
            reply_markup = InlineKeyboardMarkup(_build_menu(buttons, 2))
            
            await query.edit_message_text(f"💾 Quality: *{k}*\n\nSelect Link:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            
        elif data.startswith("psa_host:"):
            idx = int(data.split(":")[1])
            links = context.user_data.get('psa_links', [])
            if idx >= len(links):
                await query.edit_message_text("❌ Session expired. Please search again.")
                return
                
            link = links[idx]
            await query.edit_message_text(f"⏳ Bypassing PSA link for **{link['name']}**... Please wait ~20s", parse_mode=ParseMode.MARKDOWN)
            
            try:
                final_url = await do_psa_bypass(link['url'])
                
                if "goto" in final_url or final_url == link['url']:
                    btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔐 Solve Captcha", url=final_url)]])
                    await query.edit_message_text(
                        f"⚠️ **Cloudflare Protected!**\n\n"
                        f"Mini Apps hide the URL, so that won't work! I've switched the button back to a **standard link**.\n\n"
                        f"Tap it to open your standard browser, click the Turnstile checkbox, and once the page redirects, **copy the URL from your address bar** and paste it here.\n\n"
                        f"🔗 `{final_url}`",
                        reply_markup=btn,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    buttons = [[InlineKeyboardButton(f"📥 Open in {link['name']}", url=final_url)]]
                    reply_markup = InlineKeyboardMarkup(buttons)
                    
                    await query.edit_message_text(
                        f"✅ **Success!**\n\n"
                        f"🔗 Host: {link['name']}\n\n"
                        f"`{final_url}`",
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as e:
                log.error(f"PSA Bypass error: {traceback.format_exc()}")
                buttons = [[InlineKeyboardButton("🔗 Try Manual Link", url=link['url'])]]
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.edit_message_text(f"❌ Bypass failed: {e}\nYou can try manually below.", reply_markup=reply_markup)
            
    except Exception as e:
        log.error(f"Callback error: {traceback.format_exc()}")
        await query.edit_message_text("❌ An internal error occurred.")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("search", handle_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    log.info("🚀 Bot starting with interactive buttons...")
    # Explicitly allow callback_query updates
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
