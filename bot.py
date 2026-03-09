import os
import re
import asyncio
import tempfile
import logging
import sqlite3
import hashlib
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
import yt_dlp

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8771567039:AAGszNeQf63J2MEMOmpjJ1P0PLzm0CVR1Mg")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8536828322"))
DB_PATH = "bot_data.db"
URL_PATTERN = re.compile(r'https?://[^\s]+')

COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')

def get_cookie_opts():
    if os.path.exists(COOKIE_FILE):
        return {'cookiefile': COOKIE_FILE}
    return {}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# URL cache — qisqa kalit bilan saqlash
URL_CACHE = {}

def url_to_key(url):
    """URL ni 8 belgili qisqa kalitga aylantirish"""
    key = hashlib.md5(url.encode()).hexdigest()[:8]
    URL_CACHE[key] = url
    return key

def key_to_url(key):
    """Qisqa kalitdan URL ni olish"""
    return URL_CACHE.get(key, "")

# ═══════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id     INTEGER PRIMARY KEY,
        username    TEXT,
        full_name   TEXT,
        joined_at   TEXT,
        last_active TEXT,
        downloads   INTEGER DEFAULT 0,
        music_searches INTEGER DEFAULT 0,
        is_blocked  INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS downloads (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        platform    TEXT,
        url         TEXT,
        type        TEXT,
        success     INTEGER,
        created_at  TEXT
    )''')
    conn.commit()
    conn.close()

def db_register(user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at, last_active)
                 VALUES (?,?,?,?,?)''',
              (user.id, user.username, user.full_name, now, now))
    c.execute('UPDATE users SET last_active=?, username=?, full_name=? WHERE user_id=?',
              (now, user.username or '', user.full_name or '', user.id))
    conn.commit()
    conn.close()

def db_log(user_id, platform, url, dtype, success):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO downloads (user_id,platform,url,type,success,created_at) VALUES (?,?,?,?,?,?)',
              (user_id, platform, url[:200], dtype, 1 if success else 0, now))
    if success:
        if dtype == 'music_search':
            c.execute('UPDATE users SET music_searches=music_searches+1 WHERE user_id=?', (user_id,))
        else:
            c.execute('UPDATE users SET downloads=downloads+1 WHERE user_id=?', (user_id,))
    conn.commit()
    conn.close()

def db_get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now()
    today     = now.strftime("%Y-%m-%d")
    week_ago  = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    total_users    = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    new_today      = c.execute("SELECT COUNT(*) FROM users WHERE joined_at LIKE ?", (today+'%',)).fetchone()[0]
    new_week       = c.execute("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (week_ago,)).fetchone()[0]
    new_month      = c.execute("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (month_ago,)).fetchone()[0]
    active_today   = c.execute("SELECT COUNT(*) FROM users WHERE last_active LIKE ?", (today+'%',)).fetchone()[0]
    active_week    = c.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (week_ago,)).fetchone()[0]
    total_dl       = c.execute("SELECT COUNT(*) FROM downloads WHERE success=1").fetchone()[0]
    dl_today       = c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND created_at LIKE ?", (today+'%',)).fetchone()[0]
    dl_week        = c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND created_at >= ?", (week_ago,)).fetchone()[0]
    failed_total   = c.execute("SELECT COUNT(*) FROM downloads WHERE success=0").fetchone()[0]
    video_dl       = c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND type='video'").fetchone()[0]
    audio_dl       = c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND type='audio'").fetchone()[0]
    music_searches = c.execute("SELECT COUNT(*) FROM downloads WHERE type='music_search'").fetchone()[0]
    top_platforms  = c.execute('''SELECT platform, COUNT(*) as cnt FROM downloads
                                  WHERE success=1 GROUP BY platform ORDER BY cnt DESC LIMIT 5''').fetchall()
    top_users      = c.execute('''SELECT full_name, username, downloads, music_searches
                                   FROM users ORDER BY downloads DESC LIMIT 5''').fetchall()
    recent_users   = c.execute('''SELECT full_name, username, joined_at
                                    FROM users ORDER BY joined_at DESC LIMIT 5''').fetchall()
    daily = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        cnt = c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND created_at LIKE ?", (day+'%',)).fetchone()[0]
        daily.append((day[5:], cnt))

    conn.close()
    return dict(total_users=total_users, new_today=new_today, new_week=new_week, new_month=new_month,
                active_today=active_today, active_week=active_week, total_dl=total_dl, dl_today=dl_today,
                dl_week=dl_week, failed_total=failed_total, video_dl=video_dl, audio_dl=audio_dl,
                music_searches=music_searches, top_platforms=top_platforms, top_users=top_users,
                recent_users=recent_users, daily=daily)

def db_get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    users = c.execute('SELECT user_id FROM users WHERE is_blocked=0').fetchall()
    conn.close()
    return [u[0] for u in users]

# ═══════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════

def get_platform(url):
    u = url.lower()
    if 'youtube.com' in u or 'youtu.be' in u: return '🎬 YouTube'
    if 'instagram.com' in u: return '📸 Instagram'
    if 'tiktok.com' in u: return '🎵 TikTok'
    if 'twitter.com' in u or 'x.com' in u: return '🐦 Twitter/X'
    if 'facebook.com' in u or 'fb.watch' in u: return '👥 Facebook'
    if 'pinterest.com' in u: return '📌 Pinterest'
    if 'vk.com' in u: return '💙 VK'
    if 'reddit.com' in u: return '🤖 Reddit'
    if 'twitch.tv' in u: return '🎮 Twitch'
    if 'vimeo.com' in u: return '🎞 Vimeo'
    return '🌐 Boshqa'

def bar(value, max_val, length=10):
    if max_val == 0: return '░' * length
    filled = round((value / max_val) * length)
    return '█' * filled + '░' * (length - filled)

def video_opts(tmpdir):
    opts = {
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'format': 'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<45M]/best[filesize<45M]/best',
        'merge_output_format': 'mp4',
        'quiet': True, 'no_warnings': True, 'noplaylist': True,
        'http_headers': HEADERS, 'socket_timeout': 30,
    }
    opts.update(get_cookie_opts())
    return opts

def audio_opts(tmpdir):
    opts = {
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'format': 'bestaudio[filesize<45M]/bestaudio',
        'quiet': True, 'no_warnings': True, 'noplaylist': True,
        'http_headers': HEADERS,
    }
    opts.update(get_cookie_opts())
    return opts

def _download(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)

def _search(query, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(query, download=False)

# ═══════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_register(update.effective_user)
    uid = update.effective_user.id
    extra = "\n\n🔐 *Admin:* /stats — statistika paneli" if uid == ADMIN_ID else ""
    await update.message.reply_text(
        "👋 *Salom! Men kuchli Video & Musiqa botman!*\n\n"
        "📥 *Imkoniyatlar:*\n"
        "• YouTube, TikTok, Instagram, Twitter, Facebook va 1000+ saytdan video\n"
        "• Video tagida 🎵 *Musiqa yuklab olish* tugmasi\n"
        "• Qo'shiq nomini yozsangiz — topib MP3 beraman!\n"
        "• Ovozli xabar — qo'shiqni aniqlayman 🎤\n\n"
        "✅ *Ishlatish:*\n"
        "• Havola yuboring → video yuklanadi\n"
        "• Qo'shiq nomi yozing → topib beraman\n"
        "• `/music Eminem Lose Yourself`" + extra,
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════
#  STATS
# ═══════════════════════════════════════════════════════

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return

    s = db_get_stats()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="st_users"),
         InlineKeyboardButton("📥 Yuklamalar", callback_data="st_downloads")],
        [InlineKeyboardButton("📊 Batafsil", callback_data="st_full"),
         InlineKeyboardButton("🏆 Top users", callback_data="st_top")],
        [InlineKeyboardButton("📅 Kunlik grafik", callback_data="st_daily"),
         InlineKeyboardButton("📢 Broadcast", callback_data="st_broadcast")],
        [InlineKeyboardButton("🔄 Yangilash", callback_data="st_main")]
    ])
    text = (
        "📊 *BOT STATISTIKASI*\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"👥 Jami foydalanuvchilar: `{s['total_users']}`\n"
        f"🟢 Bugun faol: `{s['active_today']}`\n"
        f"📥 Jami yuklamalar: `{s['total_dl']}`\n"
        f"📥 Bugun: `{s['dl_today']}`\n\n"
        "👇 Bo'lim tanlang:"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await query.answer()

    action = query.data
    s = db_get_stats()
    back = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="st_main")]])

    if action == "st_main":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="st_users"),
             InlineKeyboardButton("📥 Yuklamalar", callback_data="st_downloads")],
            [InlineKeyboardButton("📊 Batafsil", callback_data="st_full"),
             InlineKeyboardButton("🏆 Top users", callback_data="st_top")],
            [InlineKeyboardButton("📅 Kunlik grafik", callback_data="st_daily"),
             InlineKeyboardButton("📢 Broadcast", callback_data="st_broadcast")],
            [InlineKeyboardButton("🔄 Yangilash", callback_data="st_main")]
        ])
        text = (
            "📊 *BOT STATISTIKASI*\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"👥 Jami foydalanuvchilar: `{s['total_users']}`\n"
            f"🟢 Bugun faol: `{s['active_today']}`\n"
            f"📥 Jami yuklamalar: `{s['total_dl']}`\n"
            f"📥 Bugun: `{s['dl_today']}`\n\n"
            "👇 Bo'lim tanlang:"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    elif action == "st_users":
        text = (
            "👥 *FOYDALANUVCHILAR*\n\n"
            f"📌 Jami: `{s['total_users']}`\n\n"
            f"🆕 Yangilar:\n"
            f"  • Bugun: `{s['new_today']}`\n"
            f"  • Hafta: `{s['new_week']}`\n"
            f"  • Oy: `{s['new_month']}`\n\n"
            f"🟢 Faollar:\n"
            f"  • Bugun: `{s['active_today']}`\n"
            f"  • Hafta: `{s['active_week']}`\n\n"
            f"🕐 So'nggi qo'shilganlar:\n"
        )
        for name, uname, joined in s['recent_users']:
            u = f"@{uname}" if uname else "—"
            d = joined[:10] if joined else "?"
            text += f"  • {name or 'Nomsiz'} ({u}) {d}\n"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif action == "st_downloads":
        total = s['total_dl'] or 1
        text = (
            "📥 *YUKLAMALAR*\n\n"
            f"✅ Jami: `{s['total_dl']}`\n"
            f"❌ Xato: `{s['failed_total']}`\n\n"
            f"📅 Vaqt:\n"
            f"  • Bugun: `{s['dl_today']}`\n"
            f"  • Hafta: `{s['dl_week']}`\n\n"
            f"🎬 Video: `{s['video_dl']}` {bar(s['video_dl'], total)}\n"
            f"🎵 Audio: `{s['audio_dl']}` {bar(s['audio_dl'], total)}\n"
            f"🔍 Musiqa qidirish: `{s['music_searches']}`\n\n"
            f"🌐 *Platformalar:*\n"
        )
        max_p = s['top_platforms'][0][1] if s['top_platforms'] else 1
        for plat, cnt in s['top_platforms']:
            text += f"  {plat}: `{cnt}` {bar(cnt, max_p)}\n"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif action == "st_full":
        total_req = s['total_dl'] + s['failed_total']
        rate = round((s['total_dl'] / total_req) * 100) if total_req > 0 else 0
        avg = round(s['total_dl'] / s['total_users'], 1) if s['total_users'] > 0 else 0
        text = (
            "📊 *TO'LIQ STATISTIKA*\n\n"
            f"👥 Foydalanuvchilar: `{s['total_users']}`\n"
            f"📥 Jami yuklamalar: `{s['total_dl']}`\n"
            f"✅ Muvaffaqiyat: `{rate}%`\n"
            f"📈 O'rtacha/foydalanuvchi: `{avg}`\n\n"
            f"🎬 Video: `{s['video_dl']}` | 🎵 Audio: `{s['audio_dl']}`\n"
            f"🔍 Musiqa: `{s['music_searches']}`\n\n"
            f"📅 Haftalik:\n"
            f"  👥 Yangi: `{s['new_week']}`\n"
            f"  📥 Yuklamalar: `{s['dl_week']}`\n\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif action == "st_top":
        text = "🏆 *TOP FOYDALANUVCHILAR*\n\n"
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
        for i, (name, uname, dls, musics) in enumerate(s['top_users']):
            m = medals[i] if i < 5 else f"{i+1}."
            u = f"@{uname}" if uname else ""
            text += f"{m} *{name or 'Nomsiz'}* {u}\n"
            text += f"     📥 {dls} ta | 🎵 {musics} ta\n\n"
        if not s['top_users']:
            text += "Hali ma'lumot yo'q."
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif action == "st_daily":
        text = "📅 *SO'NGGI 7 KUN*\n\n"
        max_day = max([d[1] for d in s['daily']] or [1])
        for day, cnt in s['daily']:
            b = bar(cnt, max_day, 12)
            text += f"`{day}` {b} `{cnt}`\n"
        text += f"\n📊 Jami 7 kunda: `{sum(d[1] for d in s['daily'])}`"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back)

    elif action == "st_broadcast":
        context.user_data['broadcast_mode'] = True
        await query.edit_message_text(
            "📢 *Broadcast rejimi*\n\nBarcha foydalanuvchilarga xabar yozing.\n/cancel — bekor qilish",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back
        )

# ═══════════════════════════════════════════════════════
#  VIDEO DOWNLOAD
# ═══════════════════════════════════════════════════════

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_register(update.effective_user)

    if update.effective_user.id == ADMIN_ID and context.user_data.get('broadcast_mode'):
        await broadcast_handler(update, context)
        return

    text = update.message.text
    match = URL_PATTERN.search(text)
    if not match:
        await search_music(update, context, text)
        return

    url = match.group(0)
    platform = get_platform(url)
    status = await update.message.reply_text(f"⏳ {platform} dan yuklanmoqda...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: _download(url, video_opts(tmpdir)))
            files = [f for f in os.listdir(tmpdir) if not f.endswith(('.part','.ytdl'))]
            if not files: raise Exception("Fayl topilmadi")

            filepath = os.path.join(tmpdir, files[0])
            size = os.path.getsize(filepath)

            if size > 50 * 1024 * 1024:
                db_log(update.effective_user.id, platform, url, 'video', False)
                await status.edit_text(f"⚠️ Video 50MB dan katta.\nHavola: {url}")
                return

            title = (info.get('title') or 'Video')[:50]
            uploader = info.get('uploader','')
            duration = info.get('duration', 0)

            caption = f"*{title}*"
            if uploader: caption += f"\n👤 {uploader}"
            if duration:
                m, s2 = divmod(int(duration), 60)
                caption += f"\n⏱ {m}:{s2:02d}"
            caption += f"\n{platform}"

            # URL ni qisqa kalitga aylantirish (64 belgi limit uchun)
            url_key = url_to_key(url)
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🎵 Musiqa yuklab olish", callback_data=f"aud_{url_key}")
            ]])

            await status.edit_text("📤 Yuborilmoqda...")
            with open(filepath, 'rb') as f:
                await update.message.reply_video(
                    video=f, caption=caption, parse_mode=ParseMode.MARKDOWN,
                    supports_streaming=True, reply_markup=keyboard
                )
            await status.delete()
            db_log(update.effective_user.id, platform, url, 'video', True)

    except Exception as e:
        db_log(update.effective_user.id, platform, url, 'video', False)
        err = str(e).lower()
        if 'private' in err: msg = "🔒 Bu *private* video."
        elif 'not available' in err: msg = "❌ Video mavjud emas."
        elif 'sign in' in err or 'login' in err: msg = "🔐 Login talab qiladi."
        elif 'copyright' in err: msg = "⚠️ Mualliflik huquqi tufayli bloklangan."
        else: msg = f"❌ Yuklab bo'lmadi:\n`{str(e)[:200]}`"
        await status.edit_text(msg, parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════
#  AUDIO DOWNLOAD
# ═══════════════════════════════════════════════════════

async def audio_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Musiqa yuklanmoqda...")
    url_key = query.data[4:]  # "aud_" dan keyin
    url = key_to_url(url_key)
    if not url:
        await query.message.reply_text("❌ Havola topilmadi. Qayta video yuboring.")
        return
    await _send_audio(query.message, url, query.from_user.id)

async def dlmusic_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Yuklanmoqda...")
    url_key = query.data[4:]  # "dlm_" dan keyin
    url = key_to_url(url_key)
    if not url:
        await query.message.reply_text("❌ Havola topilmadi.")
        return
    await _send_audio(query.message, url, query.from_user.id)

async def _send_audio(message, url, user_id):
    status = await message.reply_text("🎵 Audio yuklanmoqda...")
    platform = get_platform(url)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: _download(url, audio_opts(tmpdir)))

            files = os.listdir(tmpdir)
            if not files: raise Exception("Audio topilmadi")

            # eng katta faylni ol
            filepath = max([os.path.join(tmpdir, f) for f in files], key=os.path.getsize)
            
            # Fayl hajmini tekshirish
            size = os.path.getsize(filepath)
            if size > 48 * 1024 * 1024:
                await status.edit_text("⚠️ Audio fayl juda katta (48MB+). Telegram chegarasidan oshadi.")
                db_log(user_id, platform, url, 'audio', False)
                return

            title = (info.get('title') or 'Audio')[:50]
            uploader = info.get('uploader','')
            duration = info.get('duration', 0)

            caption = f"🎵 *{title}*"
            if uploader: caption += f"\n👤 {uploader}"
            if duration:
                m, s2 = divmod(int(duration), 60)
                caption += f"\n⏱ {m}:{s2:02d}"

            await status.edit_text("📤 Yuborilmoqda...")
            with open(filepath, 'rb') as f:
                await message.reply_audio(
                    audio=f, caption=caption, parse_mode=ParseMode.MARKDOWN,
                    title=title, performer=uploader
                )
            await status.delete()
            db_log(user_id, platform, url, 'audio', True)
    except Exception as e:
        db_log(user_id, platform, url, 'audio', False)
        await status.edit_text(f"❌ Audio yuklab bo'lmadi:\n`{str(e)[:150]}`", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════
#  MUSIC SEARCH
# ═══════════════════════════════════════════════════════

async def music_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_register(update.effective_user)
    if not context.args:
        await update.message.reply_text(
            "🎵 Ishlatish: `/music qo'shiq nomi`\nMasalan: `/music Adele Hello`",
            parse_mode=ParseMode.MARKDOWN)
        return
    await search_music(update, context, ' '.join(context.args))

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str):
    status = await update.message.reply_text(f"🔍 *{query_text[:30]}* qidirilmoqda...")
    try:
        loop = asyncio.get_event_loop()
        opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
        results = await loop.run_in_executor(None, lambda: _search(f"ytsearch6:{query_text}", opts))

        if not results or not results.get('entries'):
            await status.edit_text("❌ Hech narsa topilmadi.")
            return

        entries = [e for e in results['entries'] if e][:6]
        text = f"🎵 *'{query_text[:30]}'* natijalari:\n\n"
        keyboard = []

        for i, e in enumerate(entries, 1):
            title = (e.get('title') or 'Nomsiz')[:45]
            dur = e.get('duration', 0)
            vid_id = e.get('id','')
            yt_url = f"https://youtube.com/watch?v={vid_id}"
            m, s2 = divmod(int(dur or 0), 60)
            time_str = f"{m}:{s2:02d}" if dur else "?"
            text += f"{i}. 🎵 *{title}* `{time_str}`\n"

            # URL ni qisqa kalitga aylantirish
            url_key = url_to_key(yt_url)
            keyboard.append([InlineKeyboardButton(
                f"⬇️ {i}. {title[:38]}",
                callback_data=f"dlm_{url_key}"
            )])

        db_log(update.effective_user.id, 'YouTube', query_text, 'music_search', True)
        await status.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                                reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await status.edit_text(f"❌ Xatolik: `{str(e)[:100]}`", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════
#  VOICE
# ═══════════════════════════════════════════════════════

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_register(update.effective_user)
    status = await update.message.reply_text("🎤 Qo'shiq aniqlanmoqda...")
    try:
        from shazamio import Shazam
        voice = update.message.voice or update.message.audio
        file = await context.bot.get_file(voice.file_id)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "audio.ogg")
            await file.download_to_drive(path)
            shazam = Shazam()
            result = await shazam.recognize(path)
            if result and result.get('track'):
                track = result['track']
                title = track.get('title','?')
                artist = track.get('subtitle','?')
                text = f"🎵 *Topildi!*\n\n🎤 *{artist}*\n🎵 *{title}*"
                yt_url = f"https://youtube.com/ytsearch1:{artist} {title}"
                url_key = url_to_key(yt_url)
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬇️ MP3 yuklab olish", callback_data=f"dlm_{url_key}")
                ]])
                await status.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            else:
                await status.edit_text("❌ Aniqlanmadi. `/music qo'shiq nomi` bilan qidiring.", parse_mode=ParseMode.MARKDOWN)
    except ImportError:
        await status.edit_text("🎵 `/music qo'shiq nomi` bilan qidiring.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await status.edit_text("❌ Aniqlanmadi. `/music nomi` ishlating.", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════
#  BROADCAST
# ═══════════════════════════════════════════════════════

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['broadcast_mode'] = False
    msg = update.message.text
    if msg == '/cancel':
        await update.message.reply_text("❌ Bekor qilindi.")
        return
    users = db_get_all_users()
    status = await update.message.reply_text(f"📢 {len(users)} ta foydalanuvchiga yuborilmoqda...")
    success, failed = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 *Xabar:*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
            success += 1
        except: failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"✅ Yuborildi!\n\n✅ Muvaffaqiyatli: `{success}`\n❌ Yuborilmadi: `{failed}`",
        parse_mode=ParseMode.MARKDOWN
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['broadcast_mode'] = False
    await update.message.reply_text("❌ Bekor qilindi.")

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("music", music_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(stats_callback, pattern=r'^st_'))
    app.add_handler(CallbackQueryHandler(audio_button, pattern=r'^aud_'))
    app.add_handler(CallbackQueryHandler(dlmusic_button, pattern=r'^dlm_'))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    logger.info("Bot ishga tushdi 🚀")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
