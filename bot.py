import os
import re
import asyncio
import tempfile
import logging
import sqlite3
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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

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

    # Top platforms
    top_platforms = c.execute('''SELECT platform, COUNT(*) as cnt FROM downloads
                                  WHERE success=1 GROUP BY platform ORDER BY cnt DESC LIMIT 5''').fetchall()

    # Top users
    top_users = c.execute('''SELECT full_name, username, downloads, music_searches
                               FROM users ORDER BY downloads DESC LIMIT 5''').fetchall()

    # Recent users
    recent_users = c.execute('''SELECT full_name, username, joined_at
                                  FROM users ORDER BY joined_at DESC LIMIT 5''').fetchall()

    # Daily activity last 7 days
    daily = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        cnt = c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND created_at LIKE ?", (day+'%',)).fetchone()[0]
        daily.append((day[5:], cnt))  # MM-DD format

    conn.close()
    return {
        "total_users": total_users,
        "new_today": new_today,
        "new_week": new_week,
        "new_month": new_month,
        "active_today": active_today,
        "active_week": active_week,
        "total_dl": total_dl,
        "dl_today": dl_today,
        "dl_week": dl_week,
        "failed_total": failed_total,
        "video_dl": video_dl,
        "audio_dl": audio_dl,
        "music_searches": music_searches,
        "top_platforms": top_platforms,
        "top_users": top_users,
        "recent_users": recent_users,
        "daily": daily,
    }

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
    url = url.lower()
    if 'youtube.com' in url or 'youtu.be' in url: return '🎬 YouTube'
    if 'instagram.com' in url: return '📸 Instagram'
    if 'tiktok.com' in url: return '🎵 TikTok'
    if 'twitter.com' in url or 'x.com' in url: return '🐦 Twitter/X'
    if 'facebook.com' in url or 'fb.watch' in url: return '👥 Facebook'
    if 'pinterest.com' in url: return '📌 Pinterest'
    if 'vk.com' in url: return '💙 VK'
    if 'reddit.com' in url: return '🤖 Reddit'
    if 'twitch.tv' in url: return '🎮 Twitch'
    if 'vimeo.com' in url: return '🎞 Vimeo'
    return '🌐 Boshqa'

def bar(value, max_val, length=10):
    if max_val == 0: return '░' * length
    filled = round((value / max_val) * length)
    return '█' * filled + '░' * (length - filled)

def video_opts(tmpdir):
    return {
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'format': 'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<45M]/best',
        'merge_output_format': 'mp4',
        'quiet': True, 'no_warnings': True, 'noplaylist': True,
        'http_headers': HEADERS, 'socket_timeout': 30,
    }

def audio_opts(tmpdir):
    return {
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'quiet': True, 'no_warnings': True, 'noplaylist': True,
        'http_headers': HEADERS,
    }

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
    extra = "\n\n🔐 *Admin:* /stats — statistika" if uid == ADMIN_ID else ""
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

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="stats|users"),
         InlineKeyboardButton("📥 Yuklamalar", callback_data="stats|downloads")],
        [InlineKeyboardButton("📊 Batafsil statistika", callback_data="stats|full"),
         InlineKeyboardButton("🏆 Top foydalanuvchilar", callback_data="stats|top")],
        [InlineKeyboardButton("📅 Kunlik faollik", callback_data="stats|daily"),
         InlineKeyboardButton("📢 Xabar yuborish", callback_data="stats|broadcast")],
        [InlineKeyboardButton("🔄 Yangilash", callback_data="stats|refresh")]
    ])

    s = db_get_stats()
    text = (
        "📊 *BOT STATISTIKASI — Bosh sahifa*\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"👥 *Jami foydalanuvchilar:* `{s['total_users']}`\n"
        f"🟢 *Bugun faol:* `{s['active_today']}`\n"
        f"📥 *Jami yuklamalar:* `{s['total_dl']}`\n"
        f"📥 *Bugun yuklamalar:* `{s['dl_today']}`\n\n"
        "👇 Batafsil bo'lim tanlang:"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await query.answer()

    action = query.data.split("|")[1]
    s = db_get_stats()

    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="stats|back")]])

    if action == "back" or action == "refresh":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="stats|users"),
             InlineKeyboardButton("📥 Yuklamalar", callback_data="stats|downloads")],
            [InlineKeyboardButton("📊 Batafsil statistika", callback_data="stats|full"),
             InlineKeyboardButton("🏆 Top foydalanuvchilar", callback_data="stats|top")],
            [InlineKeyboardButton("📅 Kunlik faollik", callback_data="stats|daily"),
             InlineKeyboardButton("📢 Xabar yuborish", callback_data="stats|broadcast")],
            [InlineKeyboardButton("🔄 Yangilash", callback_data="stats|refresh")]
        ])
        text = (
            "📊 *BOT STATISTIKASI — Bosh sahifa*\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"👥 *Jami foydalanuvchilar:* `{s['total_users']}`\n"
            f"🟢 *Bugun faol:* `{s['active_today']}`\n"
            f"📥 *Jami yuklamalar:* `{s['total_dl']}`\n"
            f"📥 *Bugun yuklamalar:* `{s['dl_today']}`\n\n"
            "👇 Batafsil bo'lim tanlang:"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    elif action == "users":
        text = (
            "👥 *FOYDALANUVCHILAR STATISTIKASI*\n\n"
            f"📌 *Jami:* `{s['total_users']}` ta\n\n"
            f"🆕 *Yangi qo'shilganlar:*\n"
            f"  • Bugun: `{s['new_today']}`\n"
            f"  • Bu hafta: `{s['new_week']}`\n"
            f"  • Bu oy: `{s['new_month']}`\n\n"
            f"🟢 *Faol foydalanuvchilar:*\n"
            f"  • Bugun: `{s['active_today']}`\n"
            f"  • Bu hafta: `{s['active_week']}`\n\n"
            f"🕐 *So'nggi qo'shilganlar:*\n"
        )
        for name, uname, joined in s['recent_users']:
            uname_str = f"@{uname}" if uname else "username yo'q"
            date_str = joined[:10] if joined else "?"
            text += f"  • {name or 'Nomsiz'} ({uname_str}) — {date_str}\n"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn)

    elif action == "downloads":
        total = s['total_dl'] or 1
        text = (
            "📥 *YUKLAMALAR STATISTIKASI*\n\n"
            f"📊 *Jami muvaffaqiyatli:* `{s['total_dl']}`\n"
            f"❌ *Muvaffaqiyatsiz:* `{s['failed_total']}`\n\n"
            f"📅 *Vaqt bo'yicha:*\n"
            f"  • Bugun: `{s['dl_today']}`\n"
            f"  • Bu hafta: `{s['dl_week']}`\n\n"
            f"🎬 *Tur bo'yicha:*\n"
            f"  • Video: `{s['video_dl']}` {bar(s['video_dl'], total)}\n"
            f"  • Audio: `{s['audio_dl']}` {bar(s['audio_dl'], total)}\n"
            f"  • Musiqa qidirish: `{s['music_searches']}`\n\n"
            f"🌐 *Platform bo'yicha:*\n"
        )
        max_p = s['top_platforms'][0][1] if s['top_platforms'] else 1
        for plat, cnt in s['top_platforms']:
            text += f"  {plat}: `{cnt}` {bar(cnt, max_p)}\n"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn)

    elif action == "full":
        success_rate = round((s['total_dl'] / (s['total_dl'] + s['failed_total'])) * 100) if (s['total_dl'] + s['failed_total']) > 0 else 0
        avg_per_user = round(s['total_dl'] / s['total_users'], 1) if s['total_users'] > 0 else 0
        text = (
            "📊 *TO'LIQ STATISTIKA*\n\n"
            f"👥 *Foydalanuvchilar:* `{s['total_users']}`\n"
            f"📥 *Jami yuklamalar:* `{s['total_dl']}`\n"
            f"✅ *Muvaffaqiyat darajasi:* `{success_rate}%`\n"
            f"📈 *Foydalanuvchi boshiga:* `{avg_per_user}` ta yuklama\n\n"
            f"🎬 Video: `{s['video_dl']}` | 🎵 Audio: `{s['audio_dl']}`\n"
            f"🔍 Musiqa qidirish: `{s['music_searches']}`\n\n"
            f"📅 *Haftalik o'sish:*\n"
            f"  Yangi foydalanuvchilar: `{s['new_week']}`\n"
            f"  Yuklamalar: `{s['dl_week']}`\n\n"
            f"🕐 Hisobot vaqti: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn)

    elif action == "top":
        text = "🏆 *TOP FOYDALANUVCHILAR*\n\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (name, uname, dls, musics) in enumerate(s['top_users']):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            uname_str = f"@{uname}" if uname else ""
            text += f"{medal} *{name or 'Nomsiz'}* {uname_str}\n"
            text += f"     📥 {dls} yuklama | 🎵 {musics} musiqa\n\n"
        if not s['top_users']:
            text += "Hali ma'lumot yo'q."
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn)

    elif action == "daily":
        text = "📅 *SO'NGGI 7 KUNLIK FAOLLIK*\n\n"
        max_day = max([d[1] for d in s['daily']] or [1])
        for day, cnt in s['daily']:
            b = bar(cnt, max_day, 12)
            text += f"`{day}` {b} `{cnt}`\n"
        text += f"\n📊 Jami 7 kunda: `{sum(d[1] for d in s['daily'])}` ta yuklama"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn)

    elif action == "broadcast":
        context.user_data['broadcast_mode'] = True
        await query.edit_message_text(
            "📢 *Xabar yuborish rejimi*\n\n"
            "Barcha foydalanuvchilarga yuboriladigan xabarni yozing.\n"
            "❌ Bekor qilish uchun /cancel yozing.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_btn
        )

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.user_data.get('broadcast_mode'):
        return

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
            await context.bot.send_message(uid, f"📢 *Yangilik:*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
            success += 1
        except:
            failed += 1
        await asyncio.sleep(0.05)

    await status.edit_text(
        f"✅ *Xabar yuborildi!*\n\n"
        f"✅ Muvaffaqiyatli: `{success}`\n"
        f"❌ Yuborib bo'lmadi: `{failed}`",
        parse_mode=ParseMode.MARKDOWN
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['broadcast_mode'] = False
    await update.message.reply_text("❌ Bekor qilindi.")

# ═══════════════════════════════════════════════════════
#  VIDEO / AUDIO DOWNLOAD
# ═══════════════════════════════════════════════════════

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_register(update.effective_user)

    # Broadcast mode check
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
            files = [f for f in os.listdir(tmpdir) if not f.endswith(('.part', '.ytdl'))]
            if not files: raise Exception("Fayl topilmadi")

            filepath = os.path.join(tmpdir, files[0])
            size = os.path.getsize(filepath)

            if size > 50 * 1024 * 1024:
                db_log(update.effective_user.id, platform, url, 'video', False)
                await status.edit_text(f"⚠️ Video 50MB dan katta.\nHavola: {url}")
                return

            title = (info.get('title') or 'Video')[:50]
            uploader = info.get('uploader', '')
            duration = info.get('duration', 0)

            caption = f"*{title}*"
            if uploader: caption += f"\n👤 {uploader}"
            if duration:
                m, s = divmod(int(duration), 60)
                caption += f"\n⏱ {m}:{s:02d}"
            caption += f"\n{platform}"

            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🎵 Musiqa yuklab olish", callback_data=f"aud|{url}")
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
        elif 'copyright' in err: msg = "⚠️ Mualliflik huquqi tufayli bloklanган."
        else: msg = f"❌ Yuklab bo'lmadi:\n`{str(e)[:200]}`"
        await status.edit_text(msg, parse_mode=ParseMode.MARKDOWN)

async def audio_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Musiqa yuklanmoqda...")
    url = query.data[4:]
    await _send_audio(query.message, url, query.from_user.id)

async def dlmusic_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Yuklanmoqda...")
    url = query.data[8:]
    await _send_audio(query.message, url, query.from_user.id)

async def _send_audio(message, url, user_id):
    status = await message.reply_text("🎵 MP3 yuklanmoqda...")
    platform = get_platform(url)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: _download(url, audio_opts(tmpdir)))
            files = [f for f in os.listdir(tmpdir) if f.endswith('.mp3')]
            if not files: files = os.listdir(tmpdir)
            if not files: raise Exception("Audio topilmadi")

            filepath = os.path.join(tmpdir, files[0])
            title = (info.get('title') or 'Audio')[:50]
            uploader = info.get('uploader', '')
            duration = info.get('duration', 0)

            caption = f"🎵 *{title}*"
            if uploader: caption += f"\n👤 {uploader}"
            if duration:
                m, s = divmod(int(duration), 60)
                caption += f"\n⏱ {m}:{s:02d}"

            with open(filepath, 'rb') as f:
                await message.reply_audio(audio=f, caption=caption, parse_mode=ParseMode.MARKDOWN,
                                           title=title, performer=uploader)
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
    status = await update.message.reply_text(f"🔍 *{query_text}* qidirilmoqda...")
    try:
        loop = asyncio.get_event_loop()
        opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
        results = await loop.run_in_executor(None, lambda: _search(f"ytsearch6:{query_text}", opts))

        if not results or not results.get('entries'):
            await status.edit_text("❌ Hech narsa topilmadi.")
            return

        entries = [e for e in results['entries'] if e][:6]
        text = f"🎵 *'{query_text}'* natijalari:\n\n"
        keyboard = []

        for i, e in enumerate(entries, 1):
            title = (e.get('title') or 'Nomsiz')[:45]
            dur = e.get('duration', 0)
            vid_id = e.get('id', '')
            url = f"https://youtube.com/watch?v={vid_id}"
            m, s = divmod(int(dur or 0), 60)
            time_str = f"{m}:{s:02d}" if dur else "?"
            text += f"{i}. 🎵 *{title}* `{time_str}`\n"
            keyboard.append([InlineKeyboardButton(
                f"⬇️ {i}. {title[:38]}",
                callback_data=f"dlmusic|{url}"
            )])

        db_log(update.effective_user.id, 'YouTube', query_text, 'music_search', True)
        await status.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                                reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await status.edit_text(f"❌ Xatolik: `{str(e)[:100]}`", parse_mode=ParseMode.MARKDOWN)

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
                title = track.get('title', '?')
                artist = track.get('subtitle', '?')
                text = f"🎵 *Topildi!*\n\n🎤 *{artist}*\n🎵 *{title}*"
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬇️ MP3 yuklab olish",
                                         callback_data=f"dlmusic|ytsearch1:{artist} {title}")
                ]])
                await status.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            else:
                await status.edit_text("❌ Aniqlanmadi. `/music qo'shiq nomi` bilan qidiring.", parse_mode=ParseMode.MARKDOWN)
    except ImportError:
        await status.edit_text("🎤 `/music qo'shiq nomi` bilan qidiring.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await status.edit_text(f"❌ Aniqlanmadi. `/music nomi` ishlating.", parse_mode=ParseMode.MARKDOWN)

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
    app.add_handler(CallbackQueryHandler(stats_callback, pattern=r'^stats\|'))
    app.add_handler(CallbackQueryHandler(audio_button, pattern=r'^aud\|'))
    app.add_handler(CallbackQueryHandler(dlmusic_button, pattern=r'^dlmusic\|'))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    logger.info("Bot ishga tushdi 🚀")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
