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
    boxes = re.findall(r'<div class="box download[^"]*">.*?</div>\s*</div>', content, re.DOTALL)
    if not boxes:
        boxes = [p for p in re.split(r"\s*</div>\s*</div>", content)
                 if "box download" in p and "e3lan" not in p]

    for box in boxes:
        if "e3lan" in box or "atOptions" in box:
            continue
            
        chunks = re.split(r"(?:&nbsp;\s*<br\s*/?>\s*)+", box)
        
        for chunk in chunks:
            if "shortc-button" not in chunk:
                if "<b>" in chunk:
                    subchunks = chunk.split("<b>")
                    for seg in subchunks:
                        if not seg.strip() or "</b>" not in seg: continue
                        chunks.append(seg.replace("</b>", ""))
                continue
                
            head = chunk.split("<a href")[0]
            qt = re.sub(r"<[^>]+>", "", head).strip()
            
            sm = re.search(r"(\d+\.?\d*\s*(?:GB|MB|KB))", qt, re.I)
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
                r'<a href="([^"]+)" target="_blank" class="shortc-button small \w+\s*">([^<]+)</a>', chunk
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
UNIVERSAL_USERSCRIPT_DOMAINS = [
    "-appz.eu",
    "-mail.com",
    "-paw.net",
    "-soft.com",
    "10beasts.biz",
    "10short.com",
    "14xpics.space",
    "1bitspace.com",
    "1fichier.com",
    "1ink.cc",
    "1link.club",
    "1link.vip",
    "1minx.com",
    "1short.io",
    "1shortlink.com",
    "1v.to",
    "2i.cz",
    "2i.sk",
    "2linkes.com",
    "2the.space",
    "2unlock.com",
    "3minx.com",
    "3xplanet.com",
    "3xplanet.net",
    "4ace.online",
    "4fnet.org",
    "4fuk.me",
    "4hi.in",
    "4link.com",
    "555fap.com",
    "7misr4day.com",
    "8tm.net",
    "a2zapk.io",
    "a4a.site",
    "ac.totsugeki.com",
    "acorta2.com",
    "acortaphd.live",
    "acorte.xyz",
    "adbtc.top",
    "adbypass.org",
    "adfoc.us",
    "adoc.pub",
    "adpayl.ink",
    "adsafelink.com",
    "adsense.tupaste",
    "adshnk.com",
    "adshrink.it",
    "adtival.network",
    "adurl.io",
    "advisecreate.fun",
    "adz7short.space",
    "ai18.pics",
    "aipebel.com",
    "ak.sv",
    "akash.classicoder",
    "almontsf.com",
    "alorra.com",
    "altearnativasa.com",
    "amanguides.com",
    "anchoreth.com",
    "anime-jav.com",
    "animesgd.net",
    "anmolbetiyojana.in",
    "anonym.ninja",
    "anonymfile.com",
    "antonimos.de",
    "api.gplinks.com",
    "api.php",
    "apkadmin.com",
    "apkw.ru",
    "aplicacionpara.org",
    "app.khaddavi",
    "app.link",
    "app2.olamovies",
    "apunkasoftware.net",
    "article24.online",
    "aryx.xyz",
    "ashrfd.xyz",
    "asideway.com",
    "askerlikforum.com",
    "askpaccosi.com",
    "atglinks.com",
    "atomicatlas.xyz",
    "autodime.com",
    "autofaucet.dutchycorp.space",
    "ay.live",
    "aylink.co",
    "aysodamag.com",
    "azmath.info",
    "aztravels.net",
    "bangclinic.life",
    "bayimg.com",
    "bcvc.ink",
    "bebkub.com",
    "beeimg.com",
    "beinglink.in",
    "besargaji.com",
    "bestfonts.pro",
    "bewbin.com",
    "bgmiaimassist.in",
    "bigbtc.win",
    "biharkhabar.net",
    "binbox.io",
    "biovetro.net",
    "birdurls.com",
    "bit4me.info",
    "bitcotasks.com",
    "bitcotrade.net",
    "bjp.org",
    "blackwidof.org",
    "blitly.io",
    "blog.adscryp",
    "blog.bloggerishyt",
    "blog.disheye",
    "blog.filepresident",
    "blog.graphicuv",
    "blog.klublog.com",
    "blog.yurasu.xyz",
    "bloggerishyt.in",
    "bloggerpemula.pythonanywhere.com",
    "blogging.techworldx",
    "bloggingwow.store",
    "blogmado.com",
    "boiscd.com",
    "bookszone.in",
    "boost.ink",
    "bowfile.com",
    "btcon.online",
    "buzzheavier.com",
    "bypass.city",
    "camdigest.com",
    "camnangvay.com",
    "cashgrowth.online",
    "casimages.com",
    "cekip.site",
    "cgsonglyricz.in",
    "chinese-pics.com",
    "chinese-pics.vip",
    "claimcrypto.cc",
    "click.convertkit",
    "clik.pw",
    "clk.kim",
    "clk.sh",
    "cloudgallery.net",
    "cn-av.com",
    "cnpics.org",
    "cnxx.me",
    "cnxxx.org",
    "co.in",
    "coinclix.co",
    "coincroco.com",
    "coinhub.wiki",
    "coinilium.net",
    "coinscap.info",
    "coinsrev.com",
    "cointox.net",
    "com.in",
    "comohoy.com",
    "comomedir.com",
    "constanteonline.com",
    "cookad.net",
    "cosplay18.pics",
    "cosplaytele.vip",
    "count.vipurl",
    "courselinkfree.us",
    "cpmlink.net",
    "cpmlink.pro",
    "creditsgoal.com",
    "crm.cekresi",
    "croea.com",
    "cryptings.in",
    "cryptly.site",
    "crypto-fi.net",
    "cryptoinsights.site",
    "cryptomonitor.in",
    "cryptonews.faucetbin",
    "cryptonewssite.rf.gd",
    "cryptorex.net",
    "cryptorotator.website",
    "cshort.org",
    "cubeupload.com",
    "curto.win",
    "cutelink.in",
    "cutnet.net",
    "cutpaid.com",
    "cuturl.cc",
    "dailyjobposting.xyz",
    "dailyuploads.net",
    "dataupload.net",
    "dayuploads.com",
    "dbree.me",
    "dddrive.me",
    "ddownload.com",
    "dear-lottery.org",
    "defencewallah.in",
    "dekhe.click",
    "delpez.com",
    "deltabtc.xyz",
    "depic.me",
    "desiupload.co",
    "devuploads.com",
    "dhamakamusic.ink",
    "dietadisociada.info",
    "digiztechno.com",
    "dinheiromoney.com",
    "directupload.eu",
    "disheye.com",
    "dixva.com",
    "djbassking.live",
    "docadvice.eu",
    "dogefury.com",
    "doodrive.com",
    "douploads.net",
    "dow-dow-dow-dow-dow.xyz",
    "down.fast",
    "down.mdiaload",
    "downfile.site",
    "downloadani.me",
    "downloader.tips",
    "dpic.me",
    "dramaday.me",
    "drinkspartner.com",
    "drop.download",
    "dropgalaxy.com",
    "droplink.co",
    "dsmusic.in",
    "dutchycorp.ovh",
    "dutchycorp.space",
    "dw-anime.net",
    "dz4link.com",
    "earnbee.xyz",
    "earnbox.sattakingcharts",
    "earningtime.in",
    "earnmoneyyt.com",
    "easy4skip.com",
    "easylink.gamingwithtr.com",
    "easyupload.io",
    "eldiario24hrs.com",
    "empebau.eu",
    "encurtads.net",
    "enlacito.com",
    "epicload.com",
    "eternalcbse.i",
    "eu.org",
    "evegor.net",
    "ewall.biz",
    "exactpay.online",
    "exblog.jp",
    "exe-links.com",
    "exe-urls.com",
    "exe.io",
    "exego.app",
    "exeo.app",
    "exeygo.com",
    "ez4mods.com",
    "ez4short.com",
    "f2h.io",
    "falpus.com",
    "fansonlinehub.com",
    "fappic.com",
    "fastpic.org",
    "faucetsatoshi.site",
    "fbol.top",
    "fc-lc.com",
    "fc-lc.xyz",
    "fc.lc",
    "fc2ppv.me",
    "fc2ppv.stream",
    "fikfok.net",
    "file-upload.net",
    "file-upload.org",
    "filedm.com",
    "filemoon.sx",
    "fileresources.net",
    "files.fm",
    "filespayouts.com",
    "financacerta.com",
    "financedoze.com",
    "financenova.online",
    "financenuz.com",
    "financeyogi.net",
    "financialstudy.me",
    "finish.wlink",
    "fir3.net",
    "firefaucet.win",
    "fishingbreeze.com",
    "fitdynamos.com",
    "fiuxy2.co",
    "flamebook.eu.org",
    "flash.getpczone",
    "flickr.com",
    "flyad.vip",
    "flycutlink.com",
    "foodtechnos.in",
    "forex-22.com",
    "forex-trnd.com",
    "fotosik.pl",
    "frdl.is",
    "freeat30.org",
    "freemodsapp.in",
    "freepreset.net",
    "gadgetsweb.xyz",
    "gadifeed.in",
    "gally.shop",
    "gamcabd.org",
    "gamechilly.online",
    "gamerking.shop",
    "gamezigg.com",
    "gdflix.dad",
    "gdslink.xyz",
    "get-click2.blogspot.com",
    "get-to.link",
    "get.cloudfam",
    "get.instantearn",
    "get.megaurl",
    "get.rahim",
    "getpdf.net",
    "getunic.info",
    "gitlink.pro",
    "gkfun.xyz",
    "go.bloggingaro",
    "go.linkify",
    "go.moonlinks",
    "go.paylinks.cloud",
    "go.php",
    "go.tnshort",
    "go.zovo",
    "go2.pics",
    "gocmod.com",
    "gofile.download",
    "gofile.io",
    "gofile.to",
    "gold-24.net",
    "golink.bloggerishyt",
    "gomob.xyz",
    "goo.st",
    "gplinks.co",
    "greenmountmotors.com",
    "gyanigurus.net",
    "gyanitheme.com",
    "hamody.pro",
    "handydecor.com",
    "haxi.online",
    "hdpastes.com",
    "headlinerpost.com",
    "healthvainsure.site",
    "hen-tay.net",
    "hentai-manga.org",
    "hentai-sub.com",
    "hentai4f.com",
    "hentaicovid.com",
    "hentaicovid.org",
    "hentaicovid.vip",
    "hentaipig.com",
    "hentaixnx.com",
    "highkeyfinance.com",
    "hitfile.net",
    "hostpic.org",
    "hubdrive.me",
    "hypershort.com",
    "ibb.co",
    "iconicblogger.com",
    "icutlink.com",
    "idol69.net",
    "ielts-isa.edu",
    "ify.ac",
    "iir.la",
    "ikramlar.online",
    "im.ge",
    "imagebam.com",
    "imageban.ru",
    "imagehaha.com",
    "imagehost.at",
    "imagenetz.de",
    "imagenpic.com",
    "imagereviser.com",
    "imageshack.com",
    "imageshimage.com",
    "imagetwist.com",
    "imagetwist.netlify.app",
    "imageup.ru",
    "imagevenue.com",
    "imagexport.com",
    "imgadult.com",
    "imgair.net",
    "imgbase.ru",
    "imgbb.com",
    "imgblaze.net",
    "imgbox.com",
    "imgcloud.pw",
    "imgdawgknuttz.com",
    "imgdrive.net",
    "imgfira.cc",
    "imgflip.com",
    "imgfrost.net",
    "imghit.com",
    "imgo.info",
    "imgouhmde.sbs",
    "imgouskel.sbs",
    "imgpulse.top",
    "imgpv.com",
    "imgtaxi.com",
    "imgtraffic.com",
    "imgwallet.com",
    "imgxxt.in",
    "importantclass.com",
    "imx.to",
    "index.php",
    "indianshortner.com",
    "indishare.org",
    "indobo.com",
    "infidrive.net",
    "infonerd.org",
    "inicerita.online",
    "inshortnote.com",
    "instander.me",
    "instanders.app",
    "instaserve.net",
    "insurancegold.in",
    "ipamod.com",
    "itijobalert.in",
    "jameen.xyz",
    "japanpaw.com",
    "jav-load.com",
    "javball.com",
    "javbee.co",
    "javlibrary.com",
    "javring.com",
    "javstore.net",
    "javsunday.com",
    "javtele.net",
    "javtenshi.com",
    "jioupload.com",
    "jioupload.icu",
    "jobinmeghalaya.in",
    "jobzhub.store",
    "jobzspk.xyz",
    "jrlinks.in",
    "k2s.cc",
    "kaomojihub.com",
    "karanpc.com",
    "karyawan.co.id",
    "katfile.com",
    "katfile.vip",
    "kbconlinegame.com",
    "keedabankingnews.com",
    "keeplinks.org",
    "keptarolo.hu",
    "kimochi.info",
    "kin8-av.com",
    "kin8-jav.com",
    "kingofshrink.com",
    "kingshortener.com",
    "kisalt.com",
    "kisalt.digital",
    "knowiz0.blogspot.com",
    "kr-av.com",
    "krakenfiles.com",
    "kut.li",
    "kvkparbhani.org",
    "labgame.io",
    "lajangspot.web.id",
    "land.povathemes",
    "lanza.me",
    "largestpanel.in",
    "learnmany.in",
    "librolandia.cc",
    "librospdfgratismundo.net",
    "lifgam.online",
    "linegee.net",
    "link.manudatos",
    "link.paid",
    "link.theflash",
    "link.unlockner",
    "link.whf",
    "link4earn.com",
    "link4earn.in",
    "linkbox.to",
    "linkforearn.com",
    "linkjust.com",
    "linkmo.net",
    "linkpoi.me",
    "links-loot.com",
    "links.cuevana",
    "links.kmhd",
    "linkshortify.in",
    "linkshrink.net",
    "linksloot.net",
    "linksly.co",
    "linkspy.cc",
    "linkvertise.com",
    "linx.cc",
    "litecoin.host",
    "lkfms.pro",
    "lksfy.com",
    "lksfy.in",
    "lnbz.la",
    "lnk.news",
    "lnk2.cc",
    "lnks.primarchweb",
    "loaninsurehub.com",
    "loanoffer.cc",
    "lolinez.com",
    "lookmyimg.com",
    "loot-link.com",
    "loot-links.com",
    "lootdest.org",
    "lootlink.org",
    "lootlinks.co",
    "lopteapi.com",
    "m.flyad.vip",
    "main.php",
    "maloma3arbi.blogspot.com",
    "manga4nx.site",
    "mangalist.org",
    "manishclasses.in",
    "mastramstories.com",
    "mayas.travel",
    "mazen-ve3.com",
    "mbantul.my",
    "mboost.me",
    "mdsuuniversity.org",
    "mediafire.com",
    "mega4upload.net",
    "megafly.in",
    "megalink.pro",
    "megalinks.info",
    "megaup.net",
    "megaupto.com",
    "mendationforc.info",
    "metasafelink.site",
    "mexa.sh",
    "mh.gourlpro",
    "michaelemad.com",
    "minhapostagem.top",
    "minimilionario.com",
    "mirrored.to",
    "misterio.ro",
    "mitly.us",
    "mixrootmod.com",
    "mkvmoviespoint.casa",
    "mobiend.com",
    "mobilenagari.com",
    "modcombo.com",
    "modijiurl.com",
    "modmania.eu",
    "modsbase.com",
    "modsfire.com",
    "mohtawaa.com",
    "money.hustlershub",
    "moneyblink.com",
    "monoschinos.club",
    "moonplusnews.com",
    "motakhokhara.blogspot",
    "mp4upload.com",
    "mphealth.online",
    "mrproblogger.com",
    "mtmanagers.pro",
    "multiup.io",
    "mundopolo.net",
    "musicc.xyz",
    "myfirstdollar.net",
    "myscheme.org",
    "myshrinker.com",
    "network-loop.com",
    "neverdims.com",
    "newassets.hcaptcha.com",
    "newsminer.uno",
    "newzwala.co",
    "nidbd.me",
    "nishankhatri.xyz",
    "nmac.to",
    "noelshack.com",
    "noodlemagazine.com",
    "noticia.php",
    "nyushuemu.com",
    "nzarticles.pro",
    "o-pro.online",
    "ocultandoo.blogspot",
    "oei.la",
    "offerboom.top",
    "offerwall.me",
    "ofilmetorrent.com",
    "oii.io",
    "oii.la",
    "oii.si",
    "oke.io",
    "oko.sh",
    "old-young.net",
    "olhonagrana.com",
    "onlinetechsolution.link",
    "onlinetntextbooks.com",
    "onlypc.net",
    "ontechhindi.com",
    "orangepix.is",
    "otomi-games.com",
    "ouo.io",
    "ouo.press",
    "ovabee.com",
    "owllink.net",
    "owoanime.com",
    "oydir.com",
    "pahe.plus",
    "pahe.win",
    "pallabmobile.in",
    "pandagamepad.co",
    "pandaznetwork.com",
    "panyhealth.com",
    "passivecryptos.xyz",
    "paste.japan",
    "pastebin.com",
    "paster.gg",
    "pastescript.com",
    "pastesmkv.xyz",
    "payalgaming.co",
    "paycut.pro",
    "payskip.org",
    "pdfcoffee.com",
    "pelistop.xyz",
    "petly.lat",
    "pic-upload.de",
    "picforall.ru",
    "picstate.com",
    "pig69.com",
    "pilot007.org",
    "pimpandhost.com",
    "pixhost.to",
    "pixxxels.cc",
    "platinsport.com",
    "playnano.online",
    "playonpc.online",
    "playpaste.com",
    "playpastelinks.com",
    "porn-pig.com",
    "porn4f.com",
    "porn4f.org",
    "posicionamientoweb.click",
    "posterify.net",
    "postimg.cc",
    "privatenudes.com",
    "prnt.sc",
    "programasvirtualespc.net",
    "psa.wf",
    "psccapk.in",
    "pubghighdamage.com",
    "pwrpa.cc",
    "pxanimeurdu.com",
    "qiwi.gg",
    "quesignifi.ca",
    "quickeemail.com",
    "rapidgator.net",
    "raretoonsindia.rtilinks",
    "ravellawfirm.com",
    "rcccn.in",
    "readytechflip.com",
    "rekonise.com",
    "relampagomovies.com",
    "reminimod.co",
    "render-state.to",
    "revlink.pro",
    "revly.click",
    "rfaucet.com",
    "rg.sattakingcharts",
    "rintor.space",
    "rlu.ru",
    "rocklinks.in",
    "rodimalam.com",
    "rokni.xyz",
    "rotizer.net",
    "rtilinks.com",
    "ryuugames.com",
    "s-porn.com",
    "safe.php",
    "safez.es",
    "sastainsurance.xyz",
    "secure.bgmiupdate",
    "secure.moderngyan",
    "segurosdevida.site",
    "send.now",
    "seriezloaded.com",
    "servicemassar.ma",
    "set.seturl",
    "setroom.biz",
    "seulink.digital",
    "seulink.online",
    "sewdamp3.com",
    "sexyforums.com",
    "sfile.mobi",
    "sfl.gl",
    "share4u.men",
    "sharefile.co",
    "sharemods.com",
    "sharetext.me",
    "shareus.io",
    "sharphindi.in",
    "shentai-anime.com",
    "sheralinks.com",
    "shon.xyz",
    "shopizo.fun",
    "short-info.link",
    "short-ly.co",
    "short-url.link",
    "short.am",
    "short.croclix",
    "shortex.in",
    "shortfaster.net",
    "shortie.sbs",
    "shortit.pw",
    "shortlinks2btc.somee.com",
    "shortmoz.link",
    "shortxlinks.com",
    "shotcan.com",
    "shrink-service.it",
    "shrinke.me",
    "shrinkforearn.in",
    "shrinkme.click",
    "shrs.link",
    "shrtbr.com",
    "shrtslug.biz",
    "sht-link.com",
    "similarsites.com",
    "sinsitio.site",
    "skillheadlines.in",
    "skyfreecoins.top",
    "skyve.io",
    "slink.bid",
    "smallshorts.com",
    "social-unlock.com",
    "socialwolvez.com",
    "solidcoins.net",
    "sololevelingmanga.pics",
    "spacetica.com",
    "spaste.com",
    "speedynews.xyz",
    "sphinxanime.com",
    "sproutworkers.co",
    "srt.am",
    "ss7.info",
    "starkroboticsfrc.com",
    "starsddl.me",
    "stfly.me",
    "stfly.xyz",
    "stly.link",
    "stockinsights.in",
    "stockmarg.com",
    "sub2get.com",
    "subtituladas.com",
    "subtituladas.org",
    "sunci.net",
    "supercheats.com",
    "surflink.tech",
    "surl.gd",
    "surl.li",
    "sweetie-fox.com",
    "swzz.xyz",
    "taiyxd.net",
    "takefile.link",
    "tawda.xyz",
    "tech.hipsonyc",
    "tech5s.co",
    "techarmor.xyz",
    "techfizia.com",
    "techhype.in",
    "techkhulasha.com",
    "techmize.net",
    "technons.com",
    "techrayzer.com",
    "techreviewhub.store",
    "techsl.online",
    "techtnet.com",
    "techxploitz.eu.org",
    "techy.veganab",
    "techyblogs.in",
    "teknoasian.com",
    "tempatwisata.pro",
    "test.shrinkurl",
    "tfly.link",
    "thanks.tinygo",
    "the2.link",
    "theapknews.shop",
    "thecryptoworld.site",
    "thefileslocker.net",
    "thegadgetking.in",
    "theglobaldiary.com",
    "thelatintwistcafe.com",
    "themezon.net",
    "thepragatishilclasses.com",
    "thinfi.com",
    "thotpacks.xyz",
    "thunder-appz.eu",
    "tii.la",
    "tiktokcounter.net",
    "tiktokrealtime.com",
    "tmearn.net",
    "toilaquantri.com",
    "toonhub4u.net",
    "topshare.in",
    "tournguide.com",
    "tpayr.xyz",
    "tpi.li",
    "trafficimage.club",
    "trangchu.news",
    "travelinian.com",
    "trendzguruji.me",
    "trendzilla.club",
    "tribuntekno.com",
    "triggeredplay.com",
    "trimorspacks.com",
    "try2link.com",
    "tucinehd.com",
    "tuconstanteonline.com",
    "tulink.org",
    "tumangasdd.com",
    "turbobit.net",
    "turboimagehost.com",
    "turkdown.com",
    "tutwuri.id",
    "tvi.la",
    "udrop.com",
    "uiil.ink",
    "unblockedgames.world",
    "uncenav.com",
    "up-4ever.net",
    "up-load.io",
    "updrop.link",
    "upfiles.app",
    "upfion.com",
    "upload.ee",
    "uploadev.org",
    "uploadhaven.com",
    "uploadrar.com",
    "uploady.io",
    "uprwssp.org",
    "upshrink.com",
    "uptomega.me",
    "uqozy.com",
    "urlcash.com",
    "urlgalleries.net",
    "urls.cx",
    "urlx.one",
    "usandoapp.com",
    "usersdrive.com",
    "vbnmx.online",
    "veganab.co",
    "verpeliculasonline.org",
    "vi-music.app",
    "videolyrics.in",
    "vidhidepro.com",
    "vipr.im",
    "viralmp3.com",
    "vosan.co",
    "vplink.in",
    "w.linkspoint",
    "waezf.xyz",
    "wastenews.xyz",
    "web.admoneyclick",
    "web1s.asia",
    "web1s.com",
    "whatgame.xyz",
    "wii.si",
    "woowebtools.com",
    "wordcount.im",
    "wordcounter.icu",
    "work.ink",
    "workupload.com",
    "worldwallpaper.top",
    "wp.thunder",
    "wp2host.com",
    "writedroid.eu",
    "writedroid.in",
    "writeprofit.org",
    "www.akcartoons",
    "www.go",
    "www.gtaall",
    "www.itscybertech",
    "www.lanoticia",
    "www.mirrored",
    "www.ovagames",
    "www.saferoms",
    "www.spaste",
    "www.techhubcap",
    "www.udlinks",
    "www.yitarx",
    "xcamcovid.com",
    "xonnews.net",
    "xpshort.com",
    "xtrabits.click",
    "xxpics.org",
    "xxxwebdlxxx.org",
    "xxxwebdlxxx.top",
    "yitarx.com",
    "yoshare.net",
    "yrtourguide.com",
    "zaku.pro",
    "zegtrends.com",
    "zippynest.online",
    "zshort.io",
]


ALL_SHORTLINK_DOMAINS = (
    TEKNOASIAN_DOMAINS + BLOGMYSTT_DOMAINS + GETLINK_DOMAINS +
    LINEGEE_DOMAINS + SPACETICA_DOMAINS + WORDCOUNTER_DOMAINS + UNIVERSAL_USERSCRIPT_DOMAINS
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
            sel = "#startButton, a#startButton, #getnewlink, button#getnewlink, #lite-start-sora-a, #generater, .humanVerify .verify, #lite-human-verif-button, .Skipper .skipcontent, .skipcontent, #showlink, #lite-end-sora-button, .postnext, a.skip-ad, a.skip-btn, button.skip-btn, #continue, #btn-main, #btn6"
            await page.wait_for_selector(sel, timeout=8000)
            
            action = await page.evaluate(f"""
                (() => {{
                    if (document.querySelector('.postnext')) return 'postnext';
                    if (document.querySelector('#showlink, #lite-end-sora-button')) return 'showlink';
                    if (document.querySelector('.Skipper .skipcontent, .skipcontent')) return 'skipcontent';
                    if (document.querySelector('.humanVerify .verify, #lite-human-verif-button')) return 'verify';
                    if (document.querySelector('#getnewlink, button#getnewlink')) return 'getnewlink';
                    if (document.querySelector('a.skip-ad, a.skip-btn, button.skip-btn')) return 'skip';
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
                await page.wait_for_load_state("domcontentloaded", timeout=4000)
                await asyncio.sleep(0.5)
            except Exception:
                await asyncio.sleep(1)
                
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
        # Wait for it to become enabled (userscript logic)
        captcha_btn = await page.wait_for_selector("#invisibleCaptchaShortlink:not([disabled]):not(.disabled)", timeout=10000)
        if captcha_btn:
            # Force click just in case
            await captcha_btn.click(force=True)
            log.info("  ✓ clicked #invisibleCaptchaShortlink")
            await asyncio.sleep(3)
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

                # Block images, fonts, css to speed up loading significantly
                async def intercept_route(route):
                    if route.request.resource_type in ["image", "stylesheet", "font", "media", "other"]:
                        await route.abort()
                    else:
                        await route.continue_()
                await ctx.route("**/*", intercept_route)

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
                        direct_result = await _bypass_blogmystt(page)
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
                        direct_result = await _bypass_blogmystt(page)

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


async def do_smart_bypass(url: str) -> str:
    """Ultimate bypass flow: loops between native and Playwright bypasses until terminal."""
    current_url = url
    visited = set([current_url])
    
    for _ in range(5):  # Max 5 major hops
        log.info("Smart Bypass loop processing: %s", current_url)
        # Try native bypass first
        next_url = await do_psa_bypass(current_url)
        
        if any(d in next_url for d in TERMINAL_DOMAINS):
            return next_url
            
        # If native didn't finish it, and it's still a shortlink
        if _match_domain(next_url, ALL_SHORTLINK_DOMAINS):
            log.info("Native bypass incomplete, trying Playwright for: %s", next_url)
            next_url = await do_bypass(next_url)
            
            if any(d in next_url for d in TERMINAL_DOMAINS):
                return next_url
                
        # If we didn't make any progress, break out
        if next_url in visited or next_url == current_url:
            log.info("Bypass loop stuck at: %s", next_url)
            return next_url
            
        current_url = next_url
        visited.add(current_url)
        
    return current_url

async def handle_text(
update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if query.startswith('/'): return
    
    if query.startswith("http://") or query.startswith("https://"):
        await update.message.reply_text(f"🔗 Detected a link. Attempting bypass...", parse_mode=ParseMode.MARKDOWN)
        try:
            await update.message.reply_text(f"🚀 Processing link...", parse_mode=ParseMode.MARKDOWN)
            final_link = await do_smart_bypass(query)
                    
            if not any(d in final_link for d in TERMINAL_DOMAINS):
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔐 Solve in Browser", url=final_link)]])
                await update.message.reply_text(
                    f"⚠️ **Action Required!**\n\n"
                    f"This link is protected by Cloudflare or requires a timer.\n\n"
                    f"1. Tap the button below to open your standard browser.\n"
                    f"2. Solve any captchas and **wait for all timers/redirects** to finish.\n"
                    f"3. Once you reach the **FINAL destination** (like get-to.link, mega.nz, pixeldrain), copy that URL and paste it here.\n\n"
                    f"🔗 `{final_link}`",
                    parse_mode=ParseMode.MARKDOWN, reply_markup=btn
                )
            else:
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Open Link", url=final_link)]])
                await update.message.reply_text(
                    f"✅ Bypassed Link:\n\n{final_link}",
                    reply_markup=btn,
                    disable_web_page_preview=True
                )
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

import base64
import html
import re
import urllib.parse
from urllib.parse import urlparse, unquote


async def _bypass_base64_leak(url: str) -> str:
    """Extract base64 links leaked in the HTML of certain shorteners."""
    if not any(d in url for d in ["tpi.li", "oii.la", "tii.la", "oei.la", "iir.la", "tvi.la", "lnbz.la"]):
        return url
        
    try:
        import requests as sync_requests
        import base64
        import re
        FLARESOLVERR_URL = "http://localhost:8191/v1"
        payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}
        res = await asyncio.to_thread(
            sync_requests.post, FLARESOLVERR_URL, json=payload,
            headers={"Content-Type": "application/json"}
        )
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "ok":
                html_content = data.get("solution", {}).get("response", "")
                matches = re.findall(r"aHR0cHM6[^\'\"\\\s]+", html_content)
                if matches:
                    b64_id = matches[0]
                    b64_id += "=" * ((4 - len(b64_id) % 4) % 4)
                    decoded = base64.b64decode(b64_id).decode('utf-8')
                    if decoded and (decoded.startswith("http://") or decoded.startswith("https://")):
                        log.info("  ✓ Base64 leak bypass → %s", decoded[:80])
                        return decoded
    except Exception as e:
        log.error("Base64 leak bypass error: %s", e)
    return url

async def _decode_go2pics(url: str) -> str:

    """Decode go2.pics base64-encoded URLs."""
    if "go2.pics/go2?id=" not in url:
        return url
    try:
        b64_id = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("id", [""])[0]
        if b64_id:
            b64_id += "=" * ((4 - len(b64_id) % 4) % 4)
            decoded = base64.b64decode(b64_id).decode('utf-8')
            log.info("go2.pics decoded → %s", decoded)
            return decoded
    except Exception as e:
        log.error("go2.pics decode error: %s", e)
    return url


async def _bypass_redirect_page(url: str) -> str:
    """Bypass redirect pages (starkroboticsfrc.com, cashgrowth.online, etc)
    by using their session PATCH API to get the real destination URL."""
    import requests as sync_requests
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    ssid = urllib.parse.parse_qs(parsed.query).get("ssid", [""])[0]
    if not ssid:
        return url

    log.info("Redirect page bypass: ssid=%s on %s", ssid, parsed.netloc)

    def _do_patch():
        s = sync_requests.Session()
        s.headers.update({"User-Agent": UA})
        # Load page for CSRF token
        r = s.get(url, timeout=20)
        csrf_match = re.search(r'csrf[_-]?token["\s:=]+["\']([^"\']+)', r.text, re.I)
        csrf = csrf_match.group(1) if csrf_match else ""
        # PATCH to complete session and get redirect URL
        ip_data = {"currentIp": "1.2.3.4", "ipType": "IPv4",
                    "ipv4": "1.2.3.4", "ipv6": None, "hcaptchaToken": None}
        r2 = s.patch(
            f"{base}/api/session/{ssid}", json=ip_data,
            headers={"Content-Type": "application/json",
                      "X-CSRF-Token": csrf,
                      "Origin": base, "Referer": url},
            timeout=20,
        )
        if r2.status_code == 200:
            data = r2.json()
            if data.get("success") and data.get("redirect"):
                return data["redirect"]
        return None

    redirect = await asyncio.to_thread(_do_patch)
    if redirect:
        log.info("Redirect page API → %s", redirect)
        def _follow(u=redirect):
            import requests as rq
            import re
            import html
            import urllib.parse
            max_redirects = 5
            curr_url = u
            for _ in range(max_redirects):
                r = rq.get(curr_url, headers={"User-Agent": UA}, allow_redirects=True, timeout=20)
                # Check for meta refresh
                meta_match = re.search(r'(?i)<meta\s+http-equiv=["\']refresh["\']\s+content=["\']\d+;\s*url=([^"\']+)["\']', r.text)
                if meta_match:
                    next_url = html.unescape(meta_match.group(1)).strip()
                    next_url = urllib.parse.urljoin(r.url, next_url)
                    if next_url != curr_url:
                        curr_url = next_url
                        continue
                # Check for location.replace
                replace_match = re.search(r'location\.replace\(["\']([^"\']+)["\']\)', r.text)
                if replace_match:
                    next_url = replace_match.group(1).replace(r'\/', '/').replace(r'\\/', '/').strip()
                    next_url = urllib.parse.urljoin(r.url, next_url)
                    if next_url != curr_url:
                        curr_url = next_url
                        continue
                return r.url
            return curr_url
        final = await asyncio.to_thread(_follow)
        log.info("Followed redirect → %s", final)
        return final
    return url


async def _follow_astro_island(url: str, max_hops: int = 10) -> str:
    """Follow astro-island chains (ravellawfirm, cashgrowth, etc)
    to extract finalDestination or predictableArticle links."""
    import requests as sync_requests
    for hop in range(max_hops):
        log.info("Astro-island hop %d: %s", hop, url[:80])

        def _fetch(u=url):
            return sync_requests.get(u, headers={"User-Agent": UA}, timeout=20)

        r = await asyncio.to_thread(_fetch)
        text = html.unescape(r.text)

        # Check for finalDestination
        m_final = re.search(r'"finalDestination":\[\d+,"([^"]+)"\]', text)
        if m_final:
            dest = m_final.group(1)
            log.info("Astro-island finalDestination → %s", dest[:80])
            return await _decode_go2pics(dest)

        # Check for predictableArticle (intermediate hop)
        m_next = re.search(
            r'"predictableArticle":\[\d+,\{"id":\[\d+,"[^"]+"\],"url":\[\d+,"([^"]+)"\]', text)
        if m_next:
            parsed = urllib.parse.urlparse(url)
            url = f"{parsed.scheme}://{parsed.netloc}{m_next.group(1)}"
            continue

        break  # No more patterns found
    return url


# Known redirect page domains (sites that use the session PATCH API)
REDIRECT_PAGE_DOMAINS = [
    "starkroboticsfrc.com", "cashgrowth.online",
]

# Known astro-island domains
ASTRO_ISLAND_DOMAINS = [
    "ravellawfirm.com", "cashgrowth.online",
]

# Known ShrinkMe domains
SHRINKME_DOMAINS = [
    "shrinkme.click", "shrinkme.io", "shrinkme.us", "shrinkme.site",
    "shrinkme.cc", "shrinkme.vip", "shrinkme.dev", "shrinkme.ink",
]

# Terminal destinations — stop bypassing when we reach these
TERMINAL_DOMAINS = [
    "mega.nz", "drive.google.com", "pixeldrain.com", "get-to.link",
    "gofile.io", "1drv.ms", "1fichier.com", "buzzheavier.com",
    "mediafire.com", "qiwi.gg",
]


async def _bypass_shrinkme(url: str) -> str:
    """Bypass shrinkme.click / shrinkme.io links natively in Python."""
    import requests as sync_requests
    import bs4
    import urllib.parse
    import re
    import html

    # Parse alias
    parsed = urllib.parse.urlparse(url)
    alias = parsed.path.strip("/")
    if not alias:
        return url

    log.info("Bypassing ShrinkMe: alias=%s", alias)

    def _do_bypass():
        s = sync_requests.Session()
        s.headers.update({"User-Agent": UA})

        # 1. GET themezon link.php
        themezon_link = f"https://themezon.net/link.php?link={alias}"
        r1 = s.get(themezon_link, headers={"Referer": url}, timeout=20)
        
        # Extract random post redirect
        m = re.search(r'url=(https://themezon\.net/[^&\"\']+)', r1.text)
        if not m:
            log.error("Could not find themezon random post redirect")
            return url
        redirect_url = m.group(1)

        log.info("Themezon intermediate post → %s", redirect_url[:80])

        # 2. GET the random post
        r2 = s.get(redirect_url, headers={"Referer": themezon_link}, timeout=20)

        # 3. POST to redirect_to=random
        r3 = s.post(
            "https://themezon.net/?redirect_to=random",
            data={"newwpsafelink": alias},
            headers={"Referer": redirect_url},
            allow_redirects=True,
            timeout=20
        )

        # 4. Parse final page for nextPage link (mrproblogger)
        soup = bs4.BeautifulSoup(r3.text, "html.parser")
        next_page_div = soup.find(id="nextPage")
        if not next_page_div:
            log.error("Could not find nextPage div on themezon final page")
            return url
        
        next_link_a = next_page_div.find("a")
        if not next_link_a:
            log.error("Could not find a tag in nextPage div")
            return url
        
        mrproblogger_url = next_link_a.get("href")
        log.info("MrProBlogger URL → %s", mrproblogger_url[:80])

        # 5. GET mrproblogger URL
        r4 = s.get(mrproblogger_url, headers={"Referer": r3.url}, timeout=20)

        # 6. Parse form fields
        soup2 = bs4.BeautifulSoup(r4.text, "html.parser")
        form = soup2.find("form", id="go-link")
        if not form:
            log.error("Could not find form#go-link on mrproblogger")
            return url
        
        action = form.get("action", "/links/go")
        action_url = urllib.parse.urljoin(mrproblogger_url, action)

        data = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if name:
                data[name] = urllib.parse.unquote(inp.get("value", ""))

        # 7. Sleep for 15 seconds countdown (required by server check)
        log.info("Waiting 15 seconds for mrproblogger countdown...")
        time.sleep(15)

        # 8. POST to mrproblogger links/go
        log.info("Sending mrproblogger AJAX POST...")
        r5 = s.post(
            action_url,
            data=data,
            headers={
                "Referer": mrproblogger_url,
                "X-Requested-With": "XMLHttpRequest"
            },
            timeout=20
        )

        try:
            res_json = r5.json()
            if res_json.get("status") == "success" and res_json.get("url"):
                return res_json["url"]
            else:
                log.error("MrProBlogger error response: %s", r5.text[:200])
        except Exception as e:
            log.error("MrProBlogger non-JSON or decode error: %s", e)

        return url

    result = await asyncio.to_thread(_do_bypass)
    return result


async def do_psa_bypass(url: str) -> str:
    """Bypass PSA shortlinks using native Python (no browser needed)."""
    c = _bcache.get(url)
    if c is not None:
        return c

    original_url = url
    log.info("PSA Bypassing: %s", url)

    # We run in a loop to handle multi-step bypasses
    for step in range(5):
        # Decode go2.pics if present
        url = await _decode_go2pics(url)
        if any(d in url for d in TERMINAL_DOMAINS):
            break

        # Check if ShrinkMe
        if any(d in url for d in SHRINKME_DOMAINS):
            try:
                url = await _bypass_shrinkme(url)
                continue
            except Exception as e:
                log.error("ShrinkMe bypass error: %s", e)
                break


        # Check if tpi.li / oii.la base64 leak
        leaked = await _bypass_base64_leak(url)
        if leaked != url:
            url = leaked
            continue

        # Check if redirect page (starkroboticsfrc etc)

        if any(d in url for d in REDIRECT_PAGE_DOMAINS) and "ssid=" in url:
            try:
                url = await _bypass_redirect_page(url)
                continue
            except Exception as e:
                log.error("Redirect page bypass error: %s", e)
                break

        # Check if astro-island chain
        if any(d in url for d in ASTRO_ISLAND_DOMAINS):
            try:
                url = await _follow_astro_island(url)
                continue
            except Exception as e:
                log.error("Astro-island bypass error: %s", e)
                break

        # If it's a psa.wf goto link, we resolve it via FlareSolverr
        if "psa.wf" in url and "goto" in url:
            try:
                import requests as sync_requests
                FLARESOLVERR_URL = "http://localhost:8191/v1"
                payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}
                res = await asyncio.to_thread(
                    sync_requests.post, FLARESOLVERR_URL, json=payload,
                    headers={"Content-Type": "application/json"})
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "ok":
                        flare_url = data["solution"]["url"]
                        if flare_url != url:
                            url = flare_url
                            log.info("FlareSolverr resolved → %s", url[:80])
                            continue
            except Exception as e:
                log.error("FlareSolverr error: %s", e)
            break

        # If no domain matched and not a goto link, stop
        break

    # Final decode check just in case
    url = await _decode_go2pics(url)

    if any(d in url for d in TERMINAL_DOMAINS):
        log.info("✅ PSA bypass success → %s", url[:80])
        _bcache.put(original_url, url)
        return url

    log.info("⚠️ PSA bypass ended at non-terminal URL: %s", url[:80])
    return url

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
                final_url = await do_smart_bypass(link['url'])
                
                buttons = [[InlineKeyboardButton(f"📥 Open in {link['name']}", url=final_url)]]
                reply_markup = InlineKeyboardMarkup(buttons)
                
                await query.edit_message_text(
                    f"✅ **Success!**\n\n"
                    f"🎬 Quality: {link['res']} {link['codec']}\n"
                    f"💾 Size: {link['size']}\n"
                    f"🔗 Host: {link['name']}\n\n"
                    f"{final_url}",
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
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
                
                if not any(d in final_url for d in TERMINAL_DOMAINS):
                    btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔐 Solve in Browser", url=final_url)]])
                    await query.edit_message_text(
                        f"⚠️ **Action Required!**\n\n"
                        f"This link is protected by Cloudflare or requires a timer.\n\n"
                        f"1. Tap the button below to open your standard browser.\n"
                        f"2. Solve any captchas and **wait for all timers/redirects** to finish.\n"
                        f"3. Once you reach the **FINAL destination** (like get-to.link, mega.nz, pixeldrain), copy that URL and paste it here.\n\n"
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
                        f"{final_url}",
                        reply_markup=reply_markup,
                        disable_web_page_preview=True,
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
