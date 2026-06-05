import asyncio
import hashlib
from uuid import uuid4

import database
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from felixer.pahe import api_detail, api_search


def build_menu(buttons, n_cols):
    return [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]


def reset_search_state(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Clear prior search/detail state and create a fresh flow session id."""
    for key in [
        'details', 'dls', 'groups', 'links',
        'psa_groups', 'psa_links', 'search_items', 'search_query', 'psa_urls',
    ]:
        context.user_data.pop(key, None)

    for key in list(context.user_data.keys()):
        if key.startswith('grp_') or key.startswith('psa_grp_'):
            context.user_data.pop(key, None)

    session_id = uuid4().hex[:8]
    context.user_data['search_session'] = session_id
    return session_id


async def show_pahe_details(edit_func, pid: int, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    session_id = context.user_data.get('search_session') or reset_search_state(context)
    details = await api_detail(pid)

    msg_text = f"🎬 **{details['title']}**"
    if details.get('year'):
        msg_text += f" ({details['year']})"
    if details.get('rating'):
        msg_text += f"\n⭐ Rating: {details['rating']}"
    if details.get('genres'):
        msg_text += f"\n🎭 Genres: {', '.join(details['genres'])}"
    if details.get('synopsis'):
        msg_text += f"\n\n_{details['synopsis']}_"
    if details.get('image'):
        msg_text = f"[​​​​​​​​​​​]({details['image']})" + msg_text

    if details.get('episodes'):
        context.user_data['details'] = details
        buttons = [InlineKeyboardButton(ep['ep'], callback_data=f"ep:{session_id}:{idx}") for idx, ep in enumerate(details['episodes'])]
        reply_markup = InlineKeyboardMarkup(build_menu(buttons, 2))
        await edit_func(f"{msg_text}\n\n📺 Select an episode:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return

    dls = details.get('movie_dls', [])
    if not dls:
        await edit_func('❌ No download links found for this post.')
        return

    context.user_data['dls'] = dls
    groups = {}
    for d in dls:
        key = f"{d['res']} {d['codec']} ({d['size']})".strip()
        groups.setdefault(key, []).append(d)
    context.user_data['groups'] = groups

    pref_res = await database.get_user_setting(user_id, 'pref_res', 'Ask')
    filtered_keys = [k for k in groups.keys() if pref_res == 'Ask' or pref_res in k]
    if not filtered_keys:
        filtered_keys = list(groups.keys())

    buttons = []
    for key in filtered_keys:
        digest = hashlib.md5(key.encode()).hexdigest()[:8]
        context.user_data[f'grp_{digest}'] = key
        buttons.append(InlineKeyboardButton(key, callback_data=f'qual:{session_id}:{digest}'))

    if len(filtered_keys) < len(groups.keys()):
        buttons.append(InlineKeyboardButton('🔽 Show All Qualities', callback_data=f'showallqual:{session_id}:{pid}'))

    buttons.append(InlineKeyboardButton('⬅️ Back to Search', callback_data='ignore'))
    reply_markup = InlineKeyboardMarkup(build_menu(buttons, 1))
    await edit_func(f"{msg_text}\n\n💿 Select Quality:", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await database.add_user(update.effective_user.id)

    args = context.args
    if args and args[0].startswith('pahe_'):
        pid = int(args[0].split('_')[1])
        reset_search_state(context)
        msg = await update.message.reply_text('⏳ Fetching details...')

        async def do_edit(text, **kwargs):
            await msg.edit_text(text, **kwargs)

        await show_pahe_details(do_edit, pid, context, update.effective_user.id)
        return

    msg = (
        '🎬 **Welcome to Felixer Bot!**\n\n'
        'Just **type the name of a movie or TV show** below to search for it.\n'
        "I'll give you buttons to select the quality, choose a download link, and automatically bypass the ads!"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pref_res = await database.get_user_setting(user_id, 'pref_res', 'Ask')

    options = ['2160p', '1080p', '720p', '480p', 'Ask']
    buttons = []
    for opt in options:
        prefix = '✅ ' if opt == pref_res else '❌ '
        buttons.append(InlineKeyboardButton(f'{prefix}{opt}', callback_data=f'set_res:{opt}'))

    reply_markup = InlineKeyboardMarkup(build_menu(buttons, 2))
    await update.message.reply_text(
        '⚙️ **Bot Settings**\n\n'
        '**Preferred Resolution**: Automatically filter out other resolutions when showing download options to save you clicks.\n\n'
        f'Current: `{pref_res}`',
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def progress_indicator(edit_func, base_text):
    frames = ['[■□□□□□□□□□]', '[■■□□□□□□□□]', '[■■■□□□□□□□]', '[■■■■□□□□□□]', '[■■■■■□□□□□]', '[■■■■■■□□□□]', '[■■■■■■■□□□]', '[■■■■■■■■□□]', '[■■■■■■■■■□]', '[■■■■■■■■■■]']
    i = 0
    while True:
        try:
            await asyncio.sleep(2.0)
            await edit_func(f"{base_text}\n\n`{frames[i % len(frames)]}`", parse_mode=ParseMode.MARKDOWN)
            i += 1
        except asyncio.CancelledError:
            break
        except Exception:
            pass


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return

    try:
        results = await api_search(query)
        if not results:
            await update.inline_query.answer([], cache_time=300)
            return

        inline_results = []
        bot_username = context.bot.username
        for result in results[:15]:
            title = f"{'📺' if result['is_series'] else '🎬'} {result['title']}"
            if result['year']:
                title += f" ({result['year']})"

            deep_link = f"https://t.me/{bot_username}?start=pahe_{result['id']}"
            desc = 'Search on Pahe'
            if result['rating']:
                desc = f"Rating: {result['rating']}⭐"

            msg = f"🎬 **{title}**\n\n👉 [Click here to bypass and download]({deep_link})"
            inline_results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=title,
                    description=desc,
                    input_message_content=InputTextMessageContent(msg, parse_mode=ParseMode.MARKDOWN),
                )
            )

        await update.inline_query.answer(inline_results, cache_time=300)
    except Exception:
        return


async def render_search_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    items = context.user_data.get('search_items', [])
    query = context.user_data.get('search_query', '')

    items_per_page = 8
    total_pages = max(1, (len(items) + items_per_page - 1) // items_per_page) if items else 1
    page = max(0, min(page, total_pages - 1))

    start_idx = page * items_per_page
    page_items = items[start_idx:start_idx + items_per_page]

    buttons = [[InlineKeyboardButton(item['text'], callback_data=item['callback_data'])] for item in page_items]
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton('⬅️ Prev', callback_data=f'page:{page-1}'))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton('Next ➡️', callback_data=f'page:{page+1}'))
    if nav_buttons:
        buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(buttons)
    text = f"✅ Found {len(items)} results for `{query}`.\nPage {page+1}/{total_pages}"
    if any('🟢' in item['text'] for item in items):
        text += '\n🟢 = Pahe  🟣 = PSA'

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
