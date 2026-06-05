from universal_domains import UNIVERSAL_USERSCRIPT_DOMAINS

TEKNOASIAN_DOMAINS = ['teknoasian.com']
BLOGMYSTT_DOMAINS = [
    'blogmystt.com', 'wp2hostt.com', 'intercelestial.com', 'hosttbuzz.com',
    'policiesreview.com', 'healthylifez.com', 'insurancemyst.com',
    'hostingbixby.com', 'policiesbuzzz.com', 'hostingzbuzz.com',
    'bixbyfortech.com', 'serverguidez.com', 'comparepolicyy.com',
    'cheaplann.com', 'vpshostplans.com', 'ensureguide.com',
    'fitnessplanss.com', 'sharedwebs.com', 'hostserverz.com',
    'cloudhostingz.com', 'carensureplan.com', 'playareaz.com',
    'fitnesstipz.com', 'ensuretips.com', 'softdevelopp.com',
    'vpzserver.com', 'tophostdeal.com', 'evensuregd.com',
    'bestensuree.com', 'hostzteam.com',
]
GETLINK_DOMAINS = ['pahe.plus', 'oii.la', 'tpi.li', 'old.pahe.plus']
LINEGEE_DOMAINS = ['linegee.net']
SPACETICA_DOMAINS = ['spacetica.com']
WORDCOUNTER_DOMAINS = ['wordcounter.icu']
ALL_SHORTLINK_DOMAINS = (
    TEKNOASIAN_DOMAINS + BLOGMYSTT_DOMAINS + GETLINK_DOMAINS +
    LINEGEE_DOMAINS + SPACETICA_DOMAINS + WORDCOUNTER_DOMAINS + UNIVERSAL_USERSCRIPT_DOMAINS
)

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

REDIRECT_PAGE_DOMAINS = [
    'starkroboticsfrc.com', 'tech5s.co', 'free4u.nurul-huda.or.id', 'inside.warsly.com',
    'insurancexguide.com', 'techanhplus.com', 'cuturl.co.in', 'safelink.rmj.my.id',
]
ASTRO_ISLAND_DOMAINS = [
    'astro-island.life', 'sub2unlock.pro', 'rekonise.com', 'financeandinsurance.xyz',
    'faucetcrypto.cfd', 'gamingwithtr.com',
]
SHRINKME_DOMAINS = [
    'en.shrinke.me', 'shrinke.me', 'smoner.com', 'shrinkforearn.in', 'clk.sh',
]
TERMINAL_DOMAINS = [
    'mega.nz', 'pixeldrain.com', 'drive.google.com', '1fichier.com', 'krakenfiles.com',
    'vofile.net', '1download.to', 'files.fm', 'upload.ee', 'qiwi.gg', 'buzzheavier.com',
]


def match_domain(url: str, domains: list[str]) -> bool:
    return any(domain in url for domain in domains)
