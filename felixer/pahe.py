import html
import re

import httpx

from felixer.cache import Cache
from felixer.config import PAHE_WP, UA

SVC = {
    'PD': ('PixelDrain', '🟣'), 'VF': ('Vofile', '🔵'),
    'GD': ('GoogleDrive', '🟢'), 'MG': ('Mega', '🔴'),
    '1F': ('1Fichier', '🟠'), '1D': ('1Download', '🟤'),
    'UTB': ('Utombox', '⚪'), 'SD': ('SolidFiles', '🟡'),
}

_scache = Cache(300)
_dcache = Cache(600)


async def _fetch(url: str, params: dict = None) -> dict | list:
    async with httpx.AsyncClient(headers={'User-Agent': UA}, timeout=25, follow_redirects=True) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def api_search(query: str) -> list[dict]:
    key = query.lower().strip()
    cached = _scache.get(key)
    if cached is not None:
        return cached

    posts = await _fetch(PAHE_WP, {
        'search': query.strip(), 'per_page': 20,
        '_fields': 'id,title,link,content,excerpt',
    })

    out = []
    for post in posts:
        title = html.unescape(post.get('title', {}).get('rendered', ''))
        content = post.get('content', {}).get('rendered', '')
        year_match = re.search(r'\b((?:19|20)\d{2})\b', title)
        rating_match = re.search(r'Rating:\s*([\d.]+)\s*/\s*10', content)
        image_match = re.search(r'<img[^>]+src="([^">]+)"', content)
        excerpt = html.unescape(post.get('excerpt', {}).get('rendered', ''))
        excerpt = re.sub(r'<[^>]+>', '', excerpt).strip()

        genres = [
            genre.title() for genre in [
                'action', 'adventure', 'sci-fi', 'drama', 'comedy', 'horror',
                'thriller', 'romance', 'mystery', 'crime', 'animation', 'fantasy',
            ] if genre in content.lower()
        ]
        out.append({
            'id': post.get('id'),
            'title': title,
            'year': year_match.group(1) if year_match else '',
            'rating': rating_match.group(1) if rating_match else '',
            'image': image_match.group(1) if image_match else '',
            'synopsis': excerpt,
            'genres': genres[:3],
            'is_series': 'tabs-nav' in content or bool(re.search(r'Episode\s+\d+', content)),
        })

    _scache.put(key, out)
    return out


def _parse_dls(content: str) -> list[dict]:
    downloads = []
    boxes = re.findall(r'<div class="box download[^"]*">.*?</div>\s*</div>', content, re.DOTALL)
    if not boxes:
        boxes = [part for part in re.split(r'\s*</div>\s*</div>', content) if 'box download' in part and 'e3lan' not in part]

    for box in boxes:
        if 'e3lan' in box or 'atOptions' in box:
            continue

        chunks = re.split(r'(?:&nbsp;\s*<br\s*/?>\s*)+', box)
        for chunk in chunks:
            if 'shortc-button' not in chunk:
                if '<b>' in chunk:
                    for segment in chunk.split('<b>'):
                        if segment.strip() and '</b>' in segment:
                            chunks.append(segment.replace('</b>', ''))
                continue

            head = chunk.split('<a href')[0]
            quality_text = re.sub(r'<[^>]+>', '', head).strip()
            size_match = re.search(r'(\d+\.?\d*\s*(?:GB|MB|KB))', quality_text, re.I)
            resolution_match = re.search(r'(\d+p)', quality_text, re.I)
            size = size_match.group(1).strip() if size_match else ''
            resolution = resolution_match.group(1).upper() if resolution_match else ''

            codec = ''
            if 'x265' in quality_text.lower():
                codec = 'HEVC'
            elif 'x264' in quality_text.lower():
                codec = 'AVC'
            if 'hdr' in quality_text.lower():
                codec = (codec + ' HDR').strip()

            audio = ''
            for candidate in ['DD+7.1', 'DD+5.1', 'DD5.1', 'Atmos', 'TrueHD', 'DTS-HD', 'DTS', '6CH']:
                if candidate.lower() in quality_text.lower():
                    audio = candidate
                    break

            for url, service_code in re.findall(
                r'<a href="([^"]+)" target="_blank" class="shortc-button small \w+\s*">([^<]+)</a>', chunk
            ):
                code = service_code.strip().upper()
                name, icon = SVC.get(code, (code, '🔗'))
                downloads.append({
                    'svc': code,
                    'name': name,
                    'ico': icon,
                    'url': url,
                    'res': resolution,
                    'size': size,
                    'codec': codec,
                    'audio': audio,
                })
    return downloads


async def api_detail(post_id: int) -> dict:
    cached = _dcache.get(post_id)
    if cached is not None:
        return cached

    post = await _fetch(f'https://pahe.ink/wp-json/wp/v2/posts/{post_id}', {'_fields': 'id,title,link,content,excerpt'})
    title = html.unescape(post.get('title', {}).get('rendered', ''))
    content = post.get('content', {}).get('rendered', '')
    year_match = re.search(r'\b((?:19|20)\d{2})\b', title)
    rating_match = re.search(r'Rating:\s*([\d.]+)\s*/\s*10', content)
    image_match = re.search(r'<img[^>]+src="([^">]+)"', content)
    excerpt = html.unescape(post.get('excerpt', {}).get('rendered', ''))
    excerpt = re.sub(r'<[^>]+>', '', excerpt).strip()

    genres = [
        genre.title() for genre in [
            'action', 'adventure', 'sci-fi', 'drama', 'comedy', 'horror',
            'thriller', 'romance', 'mystery', 'crime', 'animation', 'fantasy',
        ] if genre in content.lower()
    ]

    episodes = []
    if 'tabs-nav' in content:
        nav_match = re.search(r'<ul class="tabs-nav">(.*?)</ul>', content, re.DOTALL)
        headers = re.findall(r'<li>([^<]+)</li>', nav_match.group(1)) if nav_match else []
        panes = re.findall(r'<div class="pane">.*?(?=<div class="pane">|$)', content, re.DOTALL)
        for index, pane in enumerate(panes):
            episode_number = headers[index].strip() if index < len(headers) else str(index + 1)
            episode_downloads = _parse_dls(pane)
            if episode_downloads:
                episodes.append({'ep': episode_number, 'dls': episode_downloads})

    movie_downloads = [] if episodes else _parse_dls(content)
    out = {
        'id': post_id,
        'title': title,
        'year': year_match.group(1) if year_match else '',
        'rating': rating_match.group(1) if rating_match else '',
        'genres': genres[:4],
        'image': image_match.group(1) if image_match else '',
        'synopsis': excerpt,
        'episodes': episodes,
        'movie_dls': movie_downloads,
    }
    _dcache.put(post_id, out)
    return out
