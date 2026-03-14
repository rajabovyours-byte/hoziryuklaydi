import os, re, asyncio, tempfile, logging, sqlite3, hashlib
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (Application, CommandHandler, MessageHandler,
                           CallbackQueryHandler, filters, ContextTypes)
from telegram.constants import ParseMode
import yt_dlp

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN   = os.environ.get("BOT_TOKEN",  "8771567039:AAGszNeQf63J2MEMOmpjJ1P0PLzm0CVR1Mg")
ADMIN_ID    = int(os.environ.get("ADMIN_ID", "8536828322"))
DB_PATH     = "bot_data.db"
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
URL_PATTERN = re.compile(r'https?://[^\s]+')
URL_CACHE   = {}
HEADERS     = {'User-Agent':'Mozilla/5.0','Accept-Language':'en-US,en;q=0.9'}

LANG = {
'uz':{
'welcome':"👋 *Salom, {name}!*\n\n🤖 *Men eng kuchli media botman!*\n\n🌟 *Imkoniyatlar:*\n• 📥 1000+ saytdan video/audio\n• 🎵 Videodagi musiqani aniqlash\n• 🖼 Thumbnail yuklab olish\n• 📝 Subtitles olish\n• 🎬 Sifat tanlash (360p/720p/1080p)\n• ⭐ Sevimlilar royxati\n• 📊 Batafsil shaxsiy statistika\n\n✅ Havola yuboring yoki tugma bosing!",
'choose_lang':"🌐 *Til tanlang:*",'lang_set':"✅ Til: 🇺🇿 O'zbek",
'downloading':"⏳ {platform} dan yuklanmoqda...",'uploading':"📤 Yuborilmoqda...",
'searching':"🔍 *{q}* qidirilmoqda...",'no_results':"❌ Hech narsa topilmadi.",
'too_large':"⚠️ Fayl 50MB dan katta.",'error':"❌ Xatolik:\n`{e}`",
'private':"🔒 Bu *private* video.",'not_available':"❌ Video mavjud emas.",
'login_required':"🔐 Login talab qiladi.",'copyright':"⚠️ Mualliflik huquqi bloklagan.",
'audio_dl':"🎵 Audio yuklanmoqda...",'audio_too_large':"⚠️ Audio 48MB dan katta.",
'shazam_detecting':"🎵 Musiqa aniqlanmoqda...",'shazam_not_found':"❌ Musiqa aniqlanmadi.",
'shazam_found':"🎵 *Topildi!*\n\n🎤 *Ijrochi:* {artist}\n🎵 *Nomi:* {title}\n🎸 *Janr:* {genre}",
'info_loading':"🔍 Malumot olinmoqda...",'thumb_loading':"🖼 Thumbnail olinmoqda...",
'thumb_not_found':"❌ Thumbnail topilmadi.",'subs_loading':"📝 Subtitles qidirilmoqda...",
'subs_not_found':"❌ Bu videoda subtitles yoq.",'history_empty':"📋 Tarixingiz bosh.",
'favs_empty':"⭐ Sevimlilar royxatingiz bosh.",'fav_added':"⭐ Sevimlilarga qoshildi!",
'fav_deleted':"🗑 Ochirildi!",'broadcast_done':"✅ Yuborildi!\n✅ `{ok}`\n❌ `{fail}`",
'cancel':"❌ Bekor qilindi.",'no_permission':"❌ Ruxsat yoq!",
'btn_download':"📥 Yuklash",'btn_music':"🎵 Musiqa",'btn_info':"ℹ️ Malumot",
'btn_thumb':"🖼 Thumbnail",'btn_subs':"📝 Subtitles",'btn_history':"📋 Tarix",
'btn_favs':"⭐ Sevimlilar",'btn_mystats':"📊 Statistikam",'btn_quality':"🎬 Sifat",
'btn_lang':"🌐 Til",'btn_help':"❓ Yordam",'btn_back':"◀️ Orqaga",
'btn_refresh':"🔄 Yangilash",'btn_get_audio':"🎵 Musiqa yuklab olish",
'btn_get_thumb':"🖼 Thumbnail",'btn_shazam':"🎵 Shazam — qoshiqni aniqlash",
'btn_more_info':"ℹ️ Batafsil",'btn_add_fav':"⭐ Sevimliga",'btn_download_mp3':"⬇️ MP3 yuklab olish",
'help_text':"❓ *YORDAM*\n\n📥 *Video:* Havola yuboring\n🎬 *Sifat:* `720 [havola]`\n🎵 *Musiqa:* Nom yozing yoki ovoz yuboring\n🖼 *Thumbnail:* Video tagida tugma\n📝 *Subtitles:* Ko'p tilli\n⭐ *Sevimlilar:* Saqlash\n📊 *Statistika:* Batafsil tahlil\n\n✅ YouTube, Instagram, TikTok, Twitter, Facebook, VK, Reddit va 1000+",
'quality_help':"🎬 *Sifat tanlash:*\n\n`360 [havola]` — 360p\n`720 [havola]` — 720p HD\n`1080 [havola]` — 1080p Full HD",
'mystats_title':"📊 *SIZNING STATISTIKANGIZ*",
},
'ru':{
'welcome':"👋 *Привет, {name}!*\n\n🤖 *Я самый мощный медиа-бот!*\n\n🌟 *Возможности:*\n• 📥 Видео/аудио с 1000+ сайтов\n• 🎵 Определение музыки в видео\n• 🖼 Скачать превью\n• 📝 Субтитры\n• 🎬 Выбор качества\n• ⭐ Избранное\n• 📊 Подробная статистика\n\n✅ Отправьте ссылку или нажмите кнопку!",
'choose_lang':"🌐 *Выберите язык:*",'lang_set':"✅ Язык: 🇷🇺 Русский",
'downloading':"⏳ Загрузка с {platform}...",'uploading':"📤 Отправка...",
'searching':"🔍 Поиск *{q}*...",'no_results':"❌ Ничего не найдено.",
'too_large':"⚠️ Файл больше 50MB.",'error':"❌ Ошибка:\n`{e}`",
'private':"🔒 Приватное видео.",'not_available':"❌ Видео недоступно.",
'login_required':"🔐 Требуется авторизация.",'copyright':"⚠️ Заблокировано.",
'audio_dl':"🎵 Загрузка аудио...",'audio_too_large':"⚠️ Аудио больше 48MB.",
'shazam_detecting':"🎵 Определение музыки...",'shazam_not_found':"❌ Музыка не определена.",
'shazam_found':"🎵 *Найдено!*\n\n🎤 *Исполнитель:* {artist}\n🎵 *Название:* {title}\n🎸 *Жанр:* {genre}",
'info_loading':"🔍 Загрузка информации...",'thumb_loading':"🖼 Загрузка превью...",
'thumb_not_found':"❌ Превью не найдено.",'subs_loading':"📝 Поиск субтитров...",
'subs_not_found':"❌ Субтитры не найдены.",'history_empty':"📋 История пуста.",
'favs_empty':"⭐ Избранное пусто.",'fav_added':"⭐ Добавлено в избранное!",
'fav_deleted':"🗑 Удалено!",'broadcast_done':"✅ Отправлено!\n✅ `{ok}`\n❌ `{fail}`",
'cancel':"❌ Отменено.",'no_permission':"❌ Нет доступа!",
'btn_download':"📥 Скачать",'btn_music':"🎵 Музыка",'btn_info':"ℹ️ Инфо",
'btn_thumb':"🖼 Превью",'btn_subs':"📝 Субтитры",'btn_history':"📋 История",
'btn_favs':"⭐ Избранное",'btn_mystats':"📊 Статистика",'btn_quality':"🎬 Качество",
'btn_lang':"🌐 Язык",'btn_help':"❓ Помощь",'btn_back':"◀️ Назад",
'btn_refresh':"🔄 Обновить",'btn_get_audio':"🎵 Скачать музыку",
'btn_get_thumb':"🖼 Превью",'btn_shazam':"🎵 Shazam — определить музыку",
'btn_more_info':"ℹ️ Подробнее",'btn_add_fav':"⭐ В избранное",'btn_download_mp3':"⬇️ Скачать MP3",
'help_text':"❓ *ПОМОЩЬ*\n\n📥 *Видео:* Отправьте ссылку\n🎬 *Качество:* `720 [ссылка]`\n🎵 *Музыка:* Напишите название или голосовое\n✅ YouTube, Instagram, TikTok, Twitter, Facebook, VK, Reddit и 1000+",
'quality_help':"🎬 *Выбор качества:*\n\n`360 [ссылка]` — 360p\n`720 [ссылка]` — 720p HD\n`1080 [ссылка]` — 1080p Full HD",
'mystats_title':"📊 *ВАША СТАТИСТИКА*",
},
'en':{
'welcome':"👋 *Hello, {name}!*\n\n🤖 *I'm the most powerful media bot!*\n\n🌟 *Features:*\n• 📥 Video/audio from 1000+ sites\n• 🎵 Music detection in videos\n• 🖼 Download thumbnails\n• 📝 Subtitles\n• 🎬 Quality selection\n• ⭐ Favorites\n• 📊 Detailed statistics\n\n✅ Send a link or press a button!",
'choose_lang':"🌐 *Choose language:*",'lang_set':"✅ Language: 🇬🇧 English",
'downloading':"⏳ Downloading from {platform}...",'uploading':"📤 Sending...",
'searching':"🔍 Searching *{q}*...",'no_results':"❌ Nothing found.",
'too_large':"⚠️ File exceeds 50MB.",'error':"❌ Error:\n`{e}`",
'private':"🔒 Private video.",'not_available':"❌ Video not available.",
'login_required':"🔐 Login required.",'copyright':"⚠️ Blocked by copyright.",
'audio_dl':"🎵 Downloading audio...",'audio_too_large':"⚠️ Audio exceeds 48MB.",
'shazam_detecting':"🎵 Detecting music...",'shazam_not_found':"❌ Music not detected.",
'shazam_found':"🎵 *Found!*\n\n🎤 *Artist:* {artist}\n🎵 *Title:* {title}\n🎸 *Genre:* {genre}",
'info_loading':"🔍 Loading info...",'thumb_loading':"🖼 Loading thumbnail...",
'thumb_not_found':"❌ Thumbnail not found.",'subs_loading':"📝 Searching subtitles...",
'subs_not_found':"❌ No subtitles found.",'history_empty':"📋 History is empty.",
'favs_empty':"⭐ Favorites list is empty.",'fav_added':"⭐ Added to favorites!",
'fav_deleted':"🗑 Deleted!",'broadcast_done':"✅ Sent!\n✅ `{ok}`\n❌ `{fail}`",
'cancel':"❌ Cancelled.",'no_permission':"❌ No permission!",
'btn_download':"📥 Download",'btn_music':"🎵 Music",'btn_info':"ℹ️ Info",
'btn_thumb':"🖼 Thumbnail",'btn_subs':"📝 Subtitles",'btn_history':"📋 History",
'btn_favs':"⭐ Favorites",'btn_mystats':"📊 My Stats",'btn_quality':"🎬 Quality",
'btn_lang':"🌐 Language",'btn_help':"❓ Help",'btn_back':"◀️ Back",
'btn_refresh':"🔄 Refresh",'btn_get_audio':"🎵 Download Music",
'btn_get_thumb':"🖼 Thumbnail",'btn_shazam':"🎵 Shazam — detect music",
'btn_more_info':"ℹ️ More info",'btn_add_fav':"⭐ Favorite",'btn_download_mp3':"⬇️ Download MP3",
'help_text':"❓ *HELP*\n\n📥 *Video:* Send a link\n🎬 *Quality:* `720 [link]`\n🎵 *Music:* Type name or send voice\n✅ YouTube, Instagram, TikTok, Twitter, Facebook, VK, Reddit and 1000+",
'quality_help':"🎬 *Quality:*\n\n`360 [link]` — 360p\n`720 [link]` — 720p HD\n`1080 [link]` — 1080p Full HD",
'mystats_title':"📊 *YOUR STATISTICS*",
},
}

def t(uid_or_lang, key, **kw):
    lg = uid_or_lang if uid_or_lang in LANG else get_user_lang(uid_or_lang)
    txt = LANG.get(lg, LANG['uz']).get(key, LANG['uz'].get(key, key))
    return txt.format(**kw) if kw else txt

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, joined_at TEXT, last_active TEXT, downloads INTEGER DEFAULT 0, music_searches INTEGER DEFAULT 0, lang TEXT DEFAULT 'uz', is_blocked INTEGER DEFAULT 0, quality TEXT DEFAULT 'best')''')
    c.execute('''CREATE TABLE IF NOT EXISTS downloads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, platform TEXT, url TEXT, title TEXT, type TEXT, success INTEGER, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, url TEXT, title TEXT, platform TEXT, dtype TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, url TEXT, title TEXT, platform TEXT)''')
    conn.commit(); conn.close()

def db_reg(user):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT OR IGNORE INTO users (user_id,username,full_name,joined_at,last_active) VALUES (?,?,?,?,?)', (user.id, user.username, user.full_name, now, now))
    c.execute('UPDATE users SET last_active=?,username=?,full_name=? WHERE user_id=?', (now, user.username or '', user.full_name or '', user.id))
    conn.commit(); conn.close()

def get_user_lang(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        r = c.execute('SELECT lang FROM users WHERE user_id=?', (uid,)).fetchone()
        conn.close(); return r[0] if r else 'uz'
    except: return 'uz'

def set_user_lang(uid, lang):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('UPDATE users SET lang=? WHERE user_id=?', (lang, uid)); conn.commit(); conn.close()

def get_user_quality(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        r = c.execute('SELECT quality FROM users WHERE user_id=?', (uid,)).fetchone()
        conn.close(); return r[0] if r else 'best'
    except: return 'best'

def set_user_quality(uid, quality):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('UPDATE users SET quality=? WHERE user_id=?', (quality, uid)); conn.commit(); conn.close()

def db_log(uid, platform, url, title, dtype, success):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO downloads (user_id,platform,url,title,type,success,created_at) VALUES (?,?,?,?,?,?,?)', (uid, platform, url[:200], title[:100], dtype, 1 if success else 0, now))
    if success:
        if dtype == 'music_search': c.execute('UPDATE users SET music_searches=music_searches+1 WHERE user_id=?', (uid,))
        else: c.execute('UPDATE users SET downloads=downloads+1 WHERE user_id=?', (uid,))
        c.execute('INSERT INTO history (user_id,url,title,platform,dtype,created_at) VALUES (?,?,?,?,?,?)', (uid, url[:200], title[:100], platform, dtype, now))
    conn.commit(); conn.close()

def db_mystats(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    user = c.execute('SELECT downloads,music_searches,joined_at FROM users WHERE user_id=?', (uid,)).fetchone()
    if not user: conn.close(); return None
    total_dl, total_music, joined = user
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now()-timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    month_ago = (datetime.now()-timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    dl_today  = c.execute("SELECT COUNT(*) FROM downloads WHERE user_id=? AND success=1 AND created_at LIKE ?", (uid, today+'%')).fetchone()[0]
    dl_week   = c.execute("SELECT COUNT(*) FROM downloads WHERE user_id=? AND success=1 AND created_at >= ?", (uid, week_ago)).fetchone()[0]
    dl_month  = c.execute("SELECT COUNT(*) FROM downloads WHERE user_id=? AND success=1 AND created_at >= ?", (uid, month_ago)).fetchone()[0]
    dl_video  = c.execute("SELECT COUNT(*) FROM downloads WHERE user_id=? AND success=1 AND type='video'", (uid,)).fetchone()[0]
    dl_audio  = c.execute("SELECT COUNT(*) FROM downloads WHERE user_id=? AND success=1 AND type='audio'", (uid,)).fetchone()[0]
    dl_failed = c.execute("SELECT COUNT(*) FROM downloads WHERE user_id=? AND success=0", (uid,)).fetchone()[0]
    platforms = c.execute("SELECT platform,COUNT(*) as cnt FROM downloads WHERE user_id=? AND success=1 GROUP BY platform ORDER BY cnt DESC LIMIT 5", (uid,)).fetchall()
    favs_count = c.execute('SELECT COUNT(*) FROM favorites WHERE user_id=?', (uid,)).fetchone()[0]
    hist_count = c.execute('SELECT COUNT(*) FROM history WHERE user_id=?', (uid,)).fetchone()[0]
    daily = []
    for i in range(6,-1,-1):
        day = (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")
        cnt = c.execute("SELECT COUNT(*) FROM downloads WHERE user_id=? AND success=1 AND created_at LIKE ?", (uid, day+'%')).fetchone()[0]
        daily.append((day[5:], cnt))
    peak = c.execute("SELECT strftime('%H',created_at) as hr,COUNT(*) as cnt FROM downloads WHERE user_id=? AND success=1 GROUP BY hr ORDER BY cnt DESC LIMIT 1", (uid,)).fetchone()
    conn.close()
    return {'total_dl':total_dl,'total_music':total_music,'joined':joined,'dl_today':dl_today,'dl_week':dl_week,'dl_month':dl_month,'dl_video':dl_video,'dl_audio':dl_audio,'dl_failed':dl_failed,'platforms':platforms,'favs':favs_count,'hist':hist_count,'daily':daily,'peak_hour':peak[0] if peak else '?'}

def db_global_stats():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    now = datetime.now(); today = now.strftime("%Y-%m-%d")
    w = (now-timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    m = (now-timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    s = {'total_users':c.execute('SELECT COUNT(*) FROM users').fetchone()[0],'new_today':c.execute("SELECT COUNT(*) FROM users WHERE joined_at LIKE ?",(today+'%',)).fetchone()[0],'new_week':c.execute("SELECT COUNT(*) FROM users WHERE joined_at >= ?",(w,)).fetchone()[0],'new_month':c.execute("SELECT COUNT(*) FROM users WHERE joined_at >= ?",(m,)).fetchone()[0],'active_today':c.execute("SELECT COUNT(*) FROM users WHERE last_active LIKE ?",(today+'%',)).fetchone()[0],'active_week':c.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?",(w,)).fetchone()[0],'total_dl':c.execute("SELECT COUNT(*) FROM downloads WHERE success=1").fetchone()[0],'dl_today':c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND created_at LIKE ?",(today+'%',)).fetchone()[0],'dl_week':c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND created_at >= ?",(w,)).fetchone()[0],'failed':c.execute("SELECT COUNT(*) FROM downloads WHERE success=0").fetchone()[0],'video_dl':c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND type='video'").fetchone()[0],'audio_dl':c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND type='audio'").fetchone()[0],'music_s':c.execute("SELECT COUNT(*) FROM downloads WHERE type='music_search'").fetchone()[0],'platforms':c.execute("SELECT platform,COUNT(*) FROM downloads WHERE success=1 GROUP BY platform ORDER BY 2 DESC LIMIT 5").fetchall(),'top_users':c.execute("SELECT full_name,username,downloads,music_searches FROM users ORDER BY downloads DESC LIMIT 5").fetchall(),'recent':c.execute("SELECT full_name,username,joined_at FROM users ORDER BY joined_at DESC LIMIT 5").fetchall(),'daily':[]}
    for i in range(6,-1,-1):
        day=(now-timedelta(days=i)).strftime("%Y-%m-%d")
        cnt=c.execute("SELECT COUNT(*) FROM downloads WHERE success=1 AND created_at LIKE ?",(day+'%',)).fetchone()[0]
        s['daily'].append((day[5:],cnt))
    conn.close(); return s

def db_all_users():
    conn=sqlite3.connect(DB_PATH);c=conn.cursor()
    r=[u[0] for u in c.execute('SELECT user_id FROM users WHERE is_blocked=0').fetchall()]
    conn.close();return r

def db_history(uid,limit=10):
    conn=sqlite3.connect(DB_PATH);c=conn.cursor()
    r=c.execute('SELECT title,platform,dtype,created_at FROM history WHERE user_id=? ORDER BY id DESC LIMIT ?',(uid,limit)).fetchall()
    conn.close();return r

def db_add_fav(uid,url,title,platform):
    conn=sqlite3.connect(DB_PATH);c=conn.cursor()
    c.execute('INSERT INTO favorites (user_id,url,title,platform) VALUES (?,?,?,?)',(uid,url,title,platform))
    conn.commit();conn.close()

def db_get_favs(uid):
    conn=sqlite3.connect(DB_PATH);c=conn.cursor()
    r=c.execute('SELECT id,title,url,platform FROM favorites WHERE user_id=? ORDER BY id DESC LIMIT 10',(uid,)).fetchall()
    conn.close();return r

def db_del_fav(fid):
    conn=sqlite3.connect(DB_PATH);c=conn.cursor()
    c.execute('DELETE FROM favorites WHERE id=?',(fid,));conn.commit();conn.close()

def get_cookie_opts():
    return {'cookiefile':COOKIE_FILE} if os.path.exists(COOKIE_FILE) else {}

def url_to_key(url):
    key=hashlib.md5(url.encode()).hexdigest()[:8];URL_CACHE[key]=url;return key

def key_to_url(key): return URL_CACHE.get(key,"")

def get_platform(url):
    u=url.lower()
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
    if 'soundcloud.com' in u: return '🎧 SoundCloud'
    return '🌐 Boshqa'

def bar(v,mx,l=10):
    if mx==0: return '░'*l
    f=round((v/mx)*l);return '█'*f+'░'*(l-f)

def fmt_dur(d):
    m,s=divmod(int(d or 0),60);h,m=divmod(m,60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def video_opts(tmpdir,quality='best'):
    fmts={'360p':'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]','720p':'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]','1080p':'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]','best':'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[filesize<45M]/best'}
    opts={'outtmpl':os.path.join(tmpdir,'%(title)s.%(ext)s'),'format':fmts.get(quality,fmts['best']),'merge_output_format':'mp4','quiet':True,'no_warnings':True,'noplaylist':True,'http_headers':HEADERS,'socket_timeout':30}
    opts.update(get_cookie_opts());return opts

def audio_opts(tmpdir):
    opts={'outtmpl':os.path.join(tmpdir,'%(title)s.%(ext)s'),'format':'bestaudio[filesize<45M]/bestaudio','quiet':True,'no_warnings':True,'noplaylist':True,'http_headers':HEADERS}
    opts.update(get_cookie_opts());return opts

def info_opts():
    opts={'quiet':True,'no_warnings':True,'noplaylist':True,'skip_download':True,'http_headers':HEADERS}
    opts.update(get_cookie_opts());return opts

def _dl(url,opts):
    with yt_dlp.YoutubeDL(opts) as ydl: return ydl.extract_info(url,download=True)

def _info(url):
    with yt_dlp.YoutubeDL(info_opts()) as ydl: return ydl.extract_info(url,download=False)

def _search(q,opts):
    with yt_dlp.YoutubeDL(opts) as ydl: return ydl.extract_info(q,download=False)

def main_menu_kb(lang, is_admin=False):
    """Reply Keyboard — pastda doim ko'rinib turadi"""
    rows = [
        [KeyboardButton(t(lang,'btn_download')),   KeyboardButton(t(lang,'btn_music'))],
        [KeyboardButton(t(lang,'btn_info')),        KeyboardButton(t(lang,'btn_thumb'))],
        [KeyboardButton(t(lang,'btn_subs')),        KeyboardButton(t(lang,'btn_quality'))],
        [KeyboardButton(t(lang,'btn_history')),     KeyboardButton(t(lang,'btn_favs'))],
        [KeyboardButton(t(lang,'btn_mystats')),     KeyboardButton(t(lang,'btn_lang'))],
        [KeyboardButton(t(lang,'btn_help'))],
    ]
    if is_admin:
        rows.append([KeyboardButton("🔐 Admin Panel")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, input_field_placeholder="Havola yoki qo'shiq nomi...")

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    db_reg(update.effective_user)
    uid=update.effective_user.id;lang=get_user_lang(uid)
    name=update.effective_user.first_name or "👤"
    await update.message.reply_text(
        t(lang,'welcome',name=name),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_kb(lang, uid==ADMIN_ID)
    )

async def menu_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;await q.answer()
    uid=q.from_user.id;lang=get_user_lang(uid);action=q.data
    back=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_back'),callback_data="menu_back")]])
    if action=="menu_dl":
        txt={'uz':"📥 *Video yuklash*\n\nHavola yuboring:\n• YouTube, TikTok, Instagram\n• Twitter, Facebook, VK va 1000+\n\n🎬 Sifat: `720 [havola]`",'ru':"📥 *Скачать видео*\n\nОтправьте ссылку:\n• YouTube, TikTok, Instagram\n• Twitter, Facebook, VK и 1000+\n\n🎬 Качество: `720 [ссылка]`",'en':"📥 *Download Video*\n\nSend a link:\n• YouTube, TikTok, Instagram\n• Twitter, Facebook, VK and 1000+\n\n🎬 Quality: `720 [link]`"}
        await q.edit_message_text(txt.get(lang,txt['uz']),parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="menu_music":
        txt={'uz':"🎵 *Musiqa qidirish*\n\n• Qoshiq nomini yozing\n• Ovozli xabar yuboring → Shazam!\n\nMasalan: `Eminem Lose Yourself`",'ru':"🎵 *Поиск музыки*\n\n• Напишите название\n• Голосовое → Shazam!\n\nПример: `Eminem Lose Yourself`",'en':"🎵 *Music Search*\n\n• Type song name\n• Voice message → Shazam!\n\nExample: `Eminem Lose Yourself`"}
        await q.edit_message_text(txt.get(lang,txt['uz']),parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="menu_info":
        txt={'uz':"ℹ️ Havola yuboring — malumot olaman!",'ru':"ℹ️ Отправьте ссылку — дам информацию!",'en':"ℹ️ Send a link — I'll get info!"}
        context.user_data['next_action']='info'
        await q.edit_message_text(txt.get(lang,txt['uz']),parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="menu_thumb":
        txt={'uz':"🖼 Havola yuboring — thumbnail yuklayman!",'ru':"🖼 Отправьте ссылку — скачаю превью!",'en':"🖼 Send a link — I'll download thumbnail!"}
        context.user_data['next_action']='thumb'
        await q.edit_message_text(txt.get(lang,txt['uz']),parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="menu_subs":
        txt={'uz':"📝 Havola yuboring — tillarni korsataman!",'ru':"📝 Отправьте ссылку — покажу языки!",'en':"📝 Send a link — I'll show languages!"}
        context.user_data['next_action']='subs'
        await q.edit_message_text(txt.get(lang,txt['uz']),parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="menu_quality":
        quality=get_user_quality(uid)
        txt={'uz':f"🎬 *Sifat tanlang*\n\nHozirgi: `{quality}`\n\nKeyingi barcha yuklamalar shu sifatda boladi.",'ru':f"🎬 *Выберите качество*\n\nТекущее: `{quality}`",'en':f"🎬 *Select Quality*\n\nCurrent: `{quality}`"}
        kb2=InlineKeyboardMarkup([[InlineKeyboardButton("360p",callback_data="setq_360p"),InlineKeyboardButton("720p HD ⭐",callback_data="setq_720p"),InlineKeyboardButton("1080p FHD",callback_data="setq_1080p")],[InlineKeyboardButton("🏆 Best",callback_data="setq_best")]])
        await q.edit_message_text(txt.get(lang,txt['uz']),parse_mode=ParseMode.MARKDOWN,reply_markup=kb2)
    elif action=="menu_history":
        await _show_history_edit(q,uid,lang)
    elif action=="menu_favs":
        await _show_favs_edit(q,uid,lang)
    elif action=="menu_mystats":
        await _show_mystats_edit(q,uid,lang)
    elif action=="menu_lang":
        kb2=InlineKeyboardMarkup([[InlineKeyboardButton("🇺🇿 O'zbek",callback_data="lang_uz"),InlineKeyboardButton("🇷🇺 Русский",callback_data="lang_ru"),InlineKeyboardButton("🇬🇧 English",callback_data="lang_en")]])
        await q.edit_message_text(t(lang,'choose_lang'),parse_mode=ParseMode.MARKDOWN,reply_markup=kb2)
    elif action=="menu_help":
        await q.edit_message_text(t(lang,'help_text'),parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="menu_back":
        # Inline xabarni yopamiz, reply keyboard allaqachon ko'rinib turibdi
        await q.edit_message_text("✅", parse_mode=ParseMode.MARKDOWN)

async def lang_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;await q.answer()
    uid=q.from_user.id;lang=q.data[5:]
    set_user_lang(uid,lang)
    name=q.from_user.first_name or "👤"
    # Inline xabarni yopamiz
    await q.edit_message_text(t(lang,'lang_set'), parse_mode=ParseMode.MARKDOWN)
    # Reply keyboard bilan yangi xabar
    await q.message.reply_text(
        t(lang,'welcome',name=name),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_kb(lang, uid==ADMIN_ID)
    )

async def quality_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;await q.answer()
    uid=q.from_user.id;lang=get_user_lang(uid);quality=q.data[5:]
    set_user_quality(uid,quality)
    labels={'360p':'360p','720p':'720p HD','1080p':'1080p Full HD','best':'Best'}
    msgs={'uz':f"✅ Sifat: *{labels.get(quality,quality)}*",'ru':f"✅ Качество: *{labels.get(quality,quality)}*",'en':f"✅ Quality: *{labels.get(quality,quality)}*"}
    back=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_back'),callback_data="menu_back")]])
    await q.edit_message_text(msgs.get(lang,msgs['uz']),parse_mode=ParseMode.MARKDOWN,reply_markup=back)

async def _show_mystats_edit(q,uid,lang):
    s=db_mystats(uid)
    if not s:
        await q.edit_message_text("❌ No data."); return
    total_acts=(s['total_dl']+s['total_music']) or 1
    failed_acts=s['dl_failed']
    success_rate=round(total_acts/(total_acts+failed_acts)*100) if (total_acts+failed_acts)>0 else 100
    if lang=='ru':
        text=(f"📊 *ВАША СТАТИСТИКА*\n\n"
              f"📅 В боте с: `{(s['joined'] or '')[:10]}`\n\n"
              f"━━━━━━━━━━━━━━━\n"
              f"📥 *ЗАГРУЗКИ:*\n"
              f"🎬 Видео: `{s['dl_video']}`\n"
              f"🎵 Аудио: `{s['dl_audio']}`\n"
              f"🔍 Поиск музыки: `{s['total_music']}`\n"
              f"❌ Ошибки: `{s['dl_failed']}`\n"
              f"✅ Успех: `{success_rate}%`\n\n"
              f"📅 *ПО ВРЕМЕНИ:*\n"
              f"• Сегодня: `{s['dl_today']}`\n"
              f"• Неделя: `{s['dl_week']}`\n"
              f"• Месяц: `{s['dl_month']}`\n"
              f"• Всего: `{s['total_dl']+s['total_music']}`\n\n"
              f"⏰ Пик: `{s['peak_hour']}:00`\n\n"
              f"━━━━━━━━━━━━━━━\n"
              f"🌐 *ТОП ПЛАТФОРМЫ:*\n")
        mx=s['platforms'][0][1] if s['platforms'] else 1
        for p,cnt in s['platforms']: text+=f"{p}: `{cnt}` {bar(cnt,mx,8)}\n"
        text+=f"\n📅 *7 ДНЕЙ:*\n"
        mx2=max([d[1] for d in s['daily']] or [1])
        for day,cnt in s['daily']: text+=f"`{day}` {bar(cnt,mx2,8)} `{cnt}`\n"
        text+=f"\n⭐ Избранное: `{s['favs']}`  📋 История: `{s['hist']}`"
    elif lang=='en':
        text=(f"📊 *YOUR STATISTICS*\n\n"
              f"📅 Member since: `{(s['joined'] or '')[:10]}`\n\n"
              f"━━━━━━━━━━━━━━━\n"
              f"📥 *DOWNLOADS:*\n"
              f"🎬 Video: `{s['dl_video']}`\n"
              f"🎵 Audio: `{s['dl_audio']}`\n"
              f"🔍 Music search: `{s['total_music']}`\n"
              f"❌ Failed: `{s['dl_failed']}`\n"
              f"✅ Success: `{success_rate}%`\n\n"
              f"📅 *BY TIME:*\n"
              f"• Today: `{s['dl_today']}`\n"
              f"• Week: `{s['dl_week']}`\n"
              f"• Month: `{s['dl_month']}`\n"
              f"• Total: `{s['total_dl']+s['total_music']}`\n\n"
              f"⏰ Peak hour: `{s['peak_hour']}:00`\n\n"
              f"━━━━━━━━━━━━━━━\n"
              f"🌐 *TOP PLATFORMS:*\n")
        mx=s['platforms'][0][1] if s['platforms'] else 1
        for p,cnt in s['platforms']: text+=f"{p}: `{cnt}` {bar(cnt,mx,8)}\n"
        text+=f"\n📅 *7 DAYS:*\n"
        mx2=max([d[1] for d in s['daily']] or [1])
        for day,cnt in s['daily']: text+=f"`{day}` {bar(cnt,mx2,8)} `{cnt}`\n"
        text+=f"\n⭐ Favorites: `{s['favs']}`  📋 History: `{s['hist']}`"
    else:
        text=(f"📊 *SIZNING STATISTIKANGIZ*\n\n"
              f"📅 Bot bilan: `{(s['joined'] or '')[:10]}`\n\n"
              f"━━━━━━━━━━━━━━━\n"
              f"📥 *YUKLAMALAR:*\n"
              f"🎬 Video: `{s['dl_video']}`\n"
              f"🎵 Audio: `{s['dl_audio']}`\n"
              f"🔍 Musiqa qidirish: `{s['total_music']}`\n"
              f"❌ Xatolar: `{s['dl_failed']}`\n"
              f"✅ Muvaffaqiyat: `{success_rate}%`\n\n"
              f"📅 *VAQT BOYICHA:*\n"
              f"• Bugun: `{s['dl_today']}`\n"
              f"• Hafta: `{s['dl_week']}`\n"
              f"• Oy: `{s['dl_month']}`\n"
              f"• Jami: `{s['total_dl']+s['total_music']}`\n\n"
              f"⏰ Eng faol soat: `{s['peak_hour']}:00`\n\n"
              f"━━━━━━━━━━━━━━━\n"
              f"🌐 *TOP PLATFORMALAR:*\n")
        mx=s['platforms'][0][1] if s['platforms'] else 1
        for p,cnt in s['platforms']: text+=f"{p}: `{cnt}` {bar(cnt,mx,8)}\n"
        if not s['platforms']: text+="Hali yoq\n"
        text+=f"\n📅 *7 KUNLIK:*\n"
        mx2=max([d[1] for d in s['daily']] or [1])
        for day,cnt in s['daily']: text+=f"`{day}` {bar(cnt,mx2,8)} `{cnt}`\n"
        text+=f"\n⭐ Sevimlilar: `{s['favs']}`  📋 Tarix: `{s['hist']}`"
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_refresh'),callback_data="menu_mystats"),InlineKeyboardButton(t(lang,'btn_back'),callback_data="menu_back")]])
    await q.edit_message_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=kb)

async def _show_history_edit(q,uid,lang):
    history=db_history(uid)
    back=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_back'),callback_data="menu_back")]])
    if not history:
        await q.edit_message_text(t(lang,'history_empty'),reply_markup=back);return
    icons={'video':'🎬','audio':'🎵','music_search':'🔍'}
    titles={'uz':"📋 *Sunggi yuklamalaringiz:*\n\n",'ru':"📋 *Последние загрузки:*\n\n",'en':"📋 *Recent downloads:*\n\n"}
    text=titles.get(lang,titles['uz'])
    for title,platform,dtype,date in history:
        text+=f"{icons.get(dtype,'📥')} *{title[:35]}*\n   {platform} • {date[:10]}\n\n"
    await q.edit_message_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=back)

async def _show_favs_edit(q,uid,lang):
    favs=db_get_favs(uid)
    back_kb=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_back'),callback_data="menu_back")]])
    if not favs:
        await q.edit_message_text(t(lang,'favs_empty'),reply_markup=back_kb);return
    titles={'uz':"⭐ *Sevimlilar:*\n\n",'ru':"⭐ *Избранное:*\n\n",'en':"⭐ *Favorites:*\n\n"}
    text=titles.get(lang,titles['uz']);kb=[]
    for fid,title,url,platform in favs:
        text+=f"• *{title[:35]}* — {platform}\n"
        ukey=url_to_key(url)
        kb.append([InlineKeyboardButton(f"📥 {title[:25]}",callback_data=f"dlv_{ukey}"),InlineKeyboardButton("🗑",callback_data=f"delfav_{fid}")])
    kb.append([InlineKeyboardButton(t(lang,'btn_back'),callback_data="menu_back")])
    await q.edit_message_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=InlineKeyboardMarkup(kb))

async def fav_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;uid=q.from_user.id;lang=get_user_lang(uid)
    if q.data.startswith("delfav_"):
        db_del_fav(int(q.data[7:]));await q.answer(t(lang,'fav_deleted'))
        await _show_favs_edit(q,uid,lang);return
    await q.answer()
    parts=q.data[4:].split('_',1);url=key_to_url(parts[0]);title=parts[1] if len(parts)>1 else 'Video'
    if url: db_add_fav(uid,url,title,get_platform(url));await q.answer(t(lang,'fav_added'),show_alert=True)
    else: await q.answer("❌",show_alert=True)

async def thumb_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;lang=get_user_lang(q.from_user.id);await q.answer(t(lang,'thumb_loading'))
    url=key_to_url(q.data[5:])
    if not url: await q.message.reply_text("❌");return
    try:
        loop=asyncio.get_event_loop()
        info=await loop.run_in_executor(None,lambda:_info(url))
        thumb=info.get('thumbnail','');title=(info.get('title','') or '')[:50]
        if thumb: await q.message.reply_photo(photo=thumb,caption=f"🖼 *{title}*",parse_mode=ParseMode.MARKDOWN)
        else: await q.message.reply_text(t(lang,'thumb_not_found'))
    except Exception as e: await q.message.reply_text(f"❌ `{str(e)[:100]}`",parse_mode=ParseMode.MARKDOWN)

async def download_video(update:Update,context:ContextTypes.DEFAULT_TYPE):
    db_reg(update.effective_user);uid=update.effective_user.id;lang=get_user_lang(uid)
    if uid==ADMIN_ID and context.user_data.get('broadcast_mode'):
        await broadcast_handler(update,context);return

    msg_text = update.message.text.strip()

    # Reply keyboard tugmalarini tekshirish — barcha 3 til uchun
    all_btns = {
        # UZ
        t('uz','btn_download'): 'btn_download', t('uz','btn_music'): 'btn_music',
        t('uz','btn_info'): 'btn_info',         t('uz','btn_thumb'): 'btn_thumb',
        t('uz','btn_subs'): 'btn_subs',         t('uz','btn_quality'): 'btn_quality',
        t('uz','btn_history'): 'btn_history',   t('uz','btn_favs'): 'btn_favs',
        t('uz','btn_mystats'): 'btn_mystats',   t('uz','btn_lang'): 'btn_lang',
        t('uz','btn_help'): 'btn_help',
        # RU
        t('ru','btn_download'): 'btn_download', t('ru','btn_music'): 'btn_music',
        t('ru','btn_info'): 'btn_info',         t('ru','btn_thumb'): 'btn_thumb',
        t('ru','btn_subs'): 'btn_subs',         t('ru','btn_quality'): 'btn_quality',
        t('ru','btn_history'): 'btn_history',   t('ru','btn_favs'): 'btn_favs',
        t('ru','btn_mystats'): 'btn_mystats',   t('ru','btn_lang'): 'btn_lang',
        t('ru','btn_help'): 'btn_help',
        # EN
        t('en','btn_download'): 'btn_download', t('en','btn_music'): 'btn_music',
        t('en','btn_info'): 'btn_info',         t('en','btn_thumb'): 'btn_thumb',
        t('en','btn_subs'): 'btn_subs',         t('en','btn_quality'): 'btn_quality',
        t('en','btn_history'): 'btn_history',   t('en','btn_favs'): 'btn_favs',
        t('en','btn_mystats'): 'btn_mystats',   t('en','btn_lang'): 'btn_lang',
        t('en','btn_help'): 'btn_help',
        # Admin
        '🔐 Admin Panel': 'admin_panel',
    }
    if msg_text in all_btns:
        await _handle_menu_button(update, context, uid, lang, all_btns[msg_text])
        return
    text=update.message.text.strip()
    next_action=context.user_data.pop('next_action',None)
    quality=get_user_quality(uid)
    q_map={'360':'360p','720':'720p','1080':'1080p'}
    if ' ' in text:
        prefix=text.split(' ',1)[0]
        if prefix in q_map: quality=q_map[prefix];text=text.split(' ',1)[1].strip()
    match=URL_PATTERN.search(text)
    if not match:
        await search_music(update,context,text,lang);return
    url=match.group(0);platform=get_platform(url)
    if next_action=='info': await _do_info(update.message,url,uid,lang);return
    elif next_action=='thumb': await _do_thumb(update.message,url,lang);return
    elif next_action=='subs': await _do_subs(update.message,url,uid,lang);return
    status=await update.message.reply_text(t(lang,'downloading',platform=platform))
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            loop=asyncio.get_event_loop()
            info=await loop.run_in_executor(None,lambda:_dl(url,video_opts(tmpdir,quality)))
            files=[f for f in os.listdir(tmpdir) if not f.endswith(('.part','.ytdl'))]
            if not files: raise Exception("Fayl topilmadi")
            filepath=os.path.join(tmpdir,max(files,key=lambda f:os.path.getsize(os.path.join(tmpdir,f))))
            if os.path.getsize(filepath) > get_size_limit():
                db_log(uid,platform,url,'?','video',False);await status.edit_text(t(lang,'too_large'));return
            title=(info.get('title') or 'Video')[:50];uploader=info.get('uploader','')
            duration=info.get('duration',0);views=info.get('view_count',0)
            caption=f"*{title}*"
            if uploader: caption+=f"\n👤 {uploader}"
            if duration: caption+=f"\n⏱ {fmt_dur(duration)}"
            if views: caption+=f"\n👁 {views:,}"
            caption+=f"\n{platform}"
            ukey=url_to_key(url)
            kb=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_get_audio'),callback_data=f"aud_{ukey}"),InlineKeyboardButton(t(lang,'btn_get_thumb'),callback_data=f"thmb_{ukey}")],[InlineKeyboardButton(t(lang,'btn_shazam'),callback_data=f"shaz_{ukey}")],[InlineKeyboardButton(t(lang,'btn_more_info'),callback_data=f"inf_{ukey}"),InlineKeyboardButton(t(lang,'btn_add_fav'),callback_data=f"fav_{ukey}_{title[:18]}")]])
            await status.edit_text(t(lang,'uploading'))
            with open(filepath,'rb') as f:
                await update.message.reply_video(video=f,caption=caption,parse_mode=ParseMode.MARKDOWN,supports_streaming=True,reply_markup=kb)
            await status.delete()
            db_log(uid,platform,url,title,'video',True)
    except Exception as e:
        err = str(e).lower()
        # Pinterest: video yo'q bo'lsa rasm yuboramiz
        if 'pinterest' in platform.lower() and ('no video' in err or 'no formats' in err or 'format' in err):
            try:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, lambda: _get_info(url))
                thumb = info.get('thumbnail','')
                title = (info.get('title') or 'Pinterest')[:50]
                if thumb:
                    await status.delete()
                    ukey = url_to_key(url)
                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton(t(lang,'btn_get_thumb'), callback_data=f"thmb_{ukey}"),
                        InlineKeyboardButton(t(lang,'btn_add_fav'),   callback_data=f"fav_{ukey}_{title[:15]}")
                    ]])
                    await update.message.reply_photo(
                        photo=thumb,
                        caption=f"🖼 *{title}*\n📌 Pinterest\n\n_(Bu pin rasm, video emas)_",
                        parse_mode=ParseMode.MARKDOWN, reply_markup=kb
                    )
                    db_log(uid, platform, url, title, 'video', True)
                    return
            except Exception:
                pass
        db_log(uid, platform, url, '?', 'video', False)
        if 'private' in err: msg = t(lang,'private')
        elif 'not available' in err: msg = t(lang,'not_available')
        elif 'sign in' in err or 'login' in err: msg = t(lang,'login_required')
        elif 'copyright' in err: msg = t(lang,'copyright')
        elif 'no video formats' in err or 'no formats' in err:
            msg = ("❌ Bu sahifada yuklab olinadigan video/rasm topilmadi.\n\n"
                   "💡 Manzilni to'g'ridan-to'g'ri ochib, video yoki rasmni saqlang.")
        else: msg = t(lang,'error', e=str(e)[:200])
        await status.edit_text(msg, parse_mode=ParseMode.MARKDOWN)

async def dlv_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;lang=get_user_lang(q.from_user.id);await q.answer()
    url=key_to_url(q.data[4:])
    if not url: await q.message.reply_text("❌");return
    platform=get_platform(url);status=await q.message.reply_text(t(lang,'downloading',platform=platform))
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            loop=asyncio.get_event_loop()
            info=await loop.run_in_executor(None,lambda:_dl(url,video_opts(tmpdir,get_user_quality(q.from_user.id))))
            files=[f for f in os.listdir(tmpdir) if not f.endswith(('.part','.ytdl'))]
            if not files: raise Exception("Fayl topilmadi")
            title=(info.get('title') or 'Video')[:50];ukey=url_to_key(url)
            kb=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_get_audio'),callback_data=f"aud_{ukey}")]])
            with open(os.path.join(tmpdir,files[0]),'rb') as f:
                await q.message.reply_video(video=f,caption=f"*{title}*\n{platform}",parse_mode=ParseMode.MARKDOWN,reply_markup=kb)
            await status.delete();db_log(q.from_user.id,platform,url,title,'video',True)
    except Exception as e: await status.edit_text(f"❌ `{str(e)[:150]}`",parse_mode=ParseMode.MARKDOWN)

async def audio_button(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;lang=get_user_lang(q.from_user.id);await q.answer(t(lang,'audio_dl'))
    url=key_to_url(q.data[4:])
    if not url: await q.message.reply_text("❌ Havola topilmadi.");return
    await _send_audio(q.message,url,q.from_user.id,lang)

async def dlmusic_button(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;lang=get_user_lang(q.from_user.id);await q.answer(t(lang,'audio_dl'))
    url=key_to_url(q.data[4:])
    if not url: await q.message.reply_text("❌");return
    await _send_audio(q.message,url,q.from_user.id,lang)

async def _send_audio(message,url,uid,lang):
    status=await message.reply_text(t(lang,'audio_dl'));platform=get_platform(url)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            loop=asyncio.get_event_loop()
            info=await loop.run_in_executor(None,lambda:_dl(url,audio_opts(tmpdir)))
            files=os.listdir(tmpdir)
            if not files: raise Exception("Audio topilmadi")
            filepath=max([os.path.join(tmpdir,f) for f in files],key=os.path.getsize)
            if os.path.getsize(filepath) > get_audio_size_limit():
                await status.edit_text(t(lang,'audio_too_large'));return
            title=(info.get('title') or 'Audio')[:50];uploader=info.get('uploader','');duration=info.get('duration',0)
            caption=f"🎵 *{title}*"
            if uploader: caption+=f"\n👤 {uploader}"
            if duration:
                m2,s2=divmod(int(duration),60);caption+=f"\n⏱ {m2}:{s2:02d}"
            await status.edit_text(t(lang,'uploading'))
            with open(filepath,'rb') as f:
                await message.reply_audio(audio=f,caption=caption,parse_mode=ParseMode.MARKDOWN,title=title,performer=uploader)
            await status.delete();db_log(uid,platform,url,title,'audio',True)
    except Exception as e:
        db_log(uid,platform,url,'?','audio',False)
        await status.edit_text(t(lang,'error',e=str(e)[:150]),parse_mode=ParseMode.MARKDOWN)

async def shazam_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;lang=get_user_lang(q.from_user.id);await q.answer(t(lang,'shazam_detecting'))
    url=key_to_url(q.data[5:])
    if not url: await q.message.reply_text("❌");return
    status=await q.message.reply_text(t(lang,'shazam_detecting'))
    try:
        from shazamio import Shazam
        with tempfile.TemporaryDirectory() as tmpdir:
            opts={'outtmpl':os.path.join(tmpdir,'audio.%(ext)s'),'format':'worstaudio/worst','quiet':True,'no_warnings':True,'noplaylist':True}
            opts.update(get_cookie_opts())
            loop=asyncio.get_event_loop()
            await loop.run_in_executor(None,lambda:_dl(url,opts))
            files=os.listdir(tmpdir)
            if not files: raise Exception("Audio topilmadi")
            shazam=Shazam()
            result=await shazam.recognize(os.path.join(tmpdir,files[0]))
            if result and result.get('track'):
                track=result['track'];title=track.get('title','?');artist=track.get('subtitle','?')
                genre=track.get('genres',{}).get('primary','—')
                text=t(lang,'shazam_found',artist=artist,title=title,genre=genre)
                ukey=url_to_key(f"https://youtube.com/ytsearch1:{artist} {title}")
                kb=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_download_mp3'),callback_data=f"dlm_{ukey}")]])
                await status.edit_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=kb)
            else: await status.edit_text(t(lang,'shazam_not_found'))
    except ImportError: await status.edit_text("❌ shazamio not installed")
    except Exception as e: await status.edit_text(f"❌ `{str(e)[:100]}`",parse_mode=ParseMode.MARKDOWN)

async def voice_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    db_reg(update.effective_user);uid=update.effective_user.id;lang=get_user_lang(uid)
    status=await update.message.reply_text(t(lang,'shazam_detecting'))
    try:
        from shazamio import Shazam
        voice=update.message.voice or update.message.audio
        file=await context.bot.get_file(voice.file_id)
        with tempfile.TemporaryDirectory() as tmpdir:
            path=os.path.join(tmpdir,"audio.ogg");await file.download_to_drive(path)
            shazam=Shazam();result=await shazam.recognize(path)
            if result and result.get('track'):
                track=result['track'];title=track.get('title','?');artist=track.get('subtitle','?')
                genre=track.get('genres',{}).get('primary','—')
                text=t(lang,'shazam_found',artist=artist,title=title,genre=genre)
                ukey=url_to_key(f"https://youtube.com/ytsearch1:{artist} {title}")
                kb=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_download_mp3'),callback_data=f"dlm_{ukey}")]])
                await status.edit_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=kb)
            else: await status.edit_text(t(lang,'shazam_not_found'))
    except ImportError: await status.edit_text("❌ shazamio not installed")
    except Exception: await status.edit_text(t(lang,'shazam_not_found'))

async def _do_info(message,url,uid,lang):
    status=await message.reply_text(t(lang,'info_loading'))
    try:
        loop=asyncio.get_event_loop()
        info=await loop.run_in_executor(None,lambda:_info(url))
        title=(info.get('title','?') or '')[:60];uploader=info.get('uploader','?')
        duration=info.get('duration',0);views=info.get('view_count',0);likes=info.get('like_count',0)
        date=info.get('upload_date','?')
        if date and len(date)==8: date=f"{date[6:]}.{date[4:6]}.{date[:4]}"
        fmts=info.get('formats',[]);quals=sorted(set(f.get('height') for f in fmts if f.get('height')),reverse=True)
        qual_str=', '.join(f"{q}p" for q in quals[:5]) if quals else "?"
        platform=get_platform(url)
        text=f"ℹ️ *{title}*\n\n👤 {uploader}\n⏱ {fmt_dur(duration)}\n📅 {date}\n👁 {views:,}\n❤️ {likes:,}\n🎬 {qual_str}\n{platform}"
        ukey=url_to_key(url)
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,'btn_download'),callback_data=f"dlv_{ukey}"),InlineKeyboardButton(t(lang,'btn_get_audio'),callback_data=f"aud_{ukey}")],[InlineKeyboardButton(t(lang,'btn_get_thumb'),callback_data=f"thmb_{ukey}"),InlineKeyboardButton(t(lang,'btn_add_fav'),callback_data=f"fav_{ukey}_{title[:18]}")]])
        await status.edit_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=kb)
    except Exception as e: await status.edit_text(f"❌ `{str(e)[:150]}`",parse_mode=ParseMode.MARKDOWN)

async def inf_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;await q.answer();uid=q.from_user.id;lang=get_user_lang(uid)
    url=key_to_url(q.data[4:])
    if not url: await q.message.reply_text("❌");return
    await _do_info(q.message,url,uid,lang)

async def _do_thumb(message,url,lang):
    status=await message.reply_text(t(lang,'thumb_loading'))
    try:
        loop=asyncio.get_event_loop()
        info=await loop.run_in_executor(None,lambda:_info(url))
        thumb=info.get('thumbnail','');title=(info.get('title','') or '')[:50]
        if thumb: await status.delete();await message.reply_photo(photo=thumb,caption=f"🖼 *{title}*",parse_mode=ParseMode.MARKDOWN)
        else: await status.edit_text(t(lang,'thumb_not_found'))
    except Exception as e: await status.edit_text(f"❌ `{str(e)[:100]}`",parse_mode=ParseMode.MARKDOWN)

async def _do_subs(message,url,uid,lang):
    status=await message.reply_text(t(lang,'subs_loading'))
    try:
        loop=asyncio.get_event_loop()
        info=await loop.run_in_executor(None,lambda:_info(url))
        subs=info.get('subtitles',{});auto=info.get('automatic_captions',{});all_s={**subs,**auto}
        if not all_s: await status.edit_text(t(lang,'subs_not_found'));return
        langs_list=list(all_s.keys())[:12];title=(info.get('title','') or '')[:40]
        titles={'uz':f"📝 *{title}*\n\nMavjud:\n",'ru':f"📝 *{title}*\n\nДоступны:\n",'en':f"📝 *{title}*\n\nAvailable:\n"}
        text=titles.get(lang,titles['uz'])
        for l in langs_list: text+=f"{'🤖' if l in auto else '✍️'} `{l}`\n"
        priority=['uz','ru','en','ko','ja','de','fr','ar','tr']
        show=[l for l in priority if l in langs_list]+[l for l in langs_list if l not in priority]
        ukey=url_to_key(url)
        kb=[[InlineKeyboardButton(f"⬇️ {l.upper()}",callback_data=f"sub_{ukey}_{l}")] for l in show[:6]]
        await status.edit_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e: await status.edit_text(f"❌ `{str(e)[:150]}`",parse_mode=ParseMode.MARKDOWN)

async def subs_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;lang=get_user_lang(q.from_user.id);await q.answer()
    parts=q.data[4:].split('_',1);url_key=parts[0];sub_lang=parts[1] if len(parts)>1 else 'en'
    url=key_to_url(url_key)
    if not url: await q.message.reply_text("❌");return
    status=await q.message.reply_text(f"📝 {sub_lang.upper()}...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            opts={'outtmpl':os.path.join(tmpdir,'%(title)s.%(ext)s'),'writesubtitles':True,'writeautomaticsub':True,'subtitleslangs':[sub_lang],'subtitlesformat':'srt','skip_download':True,'quiet':True}
            opts.update(get_cookie_opts())
            loop=asyncio.get_event_loop()
            info=await loop.run_in_executor(None,lambda:_dl(url,opts))
            title=(info.get('title','Video') or '')[:40]
            files=[f for f in os.listdir(tmpdir) if f.endswith(('.srt','.vtt'))]
            if not files: await status.edit_text(t(lang,'subs_not_found'));return
            with open(os.path.join(tmpdir,files[0]),'rb') as f:
                await q.message.reply_document(document=f,filename=f"{title}_{sub_lang}.srt",caption=f"📝 *{title}*\n🌐 `{sub_lang.upper()}`",parse_mode=ParseMode.MARKDOWN)
            await status.delete()
    except Exception as e: await status.edit_text(f"❌ `{str(e)[:100]}`",parse_mode=ParseMode.MARKDOWN)

async def search_music(update:Update,context:ContextTypes.DEFAULT_TYPE,query_text:str,lang:str=None):
    uid=update.effective_user.id
    if not lang: lang=get_user_lang(uid)
    status=await update.message.reply_text(t(lang,'searching',q=query_text[:30]))
    try:
        loop=asyncio.get_event_loop()
        opts={'quiet':True,'no_warnings':True,'extract_flat':True}
        results=await loop.run_in_executor(None,lambda:_search(f"ytsearch6:{query_text}",opts))
        if not results or not results.get('entries'): await status.edit_text(t(lang,'no_results'));return
        entries=[e for e in results['entries'] if e][:6]
        titles={'uz':f"🎵 *'{query_text[:30]}'* natijalari:\n\n",'ru':f"🎵 *'{query_text[:30]}'* результаты:\n\n",'en':f"🎵 *'{query_text[:30]}'* results:\n\n"}
        text=titles.get(lang,titles['uz']);kb=[]
        for i,e in enumerate(entries,1):
            title=(e.get('title') or 'Nomsiz')[:45];dur=e.get('duration',0);vid_id=e.get('id','')
            yt_url=f"https://youtube.com/watch?v={vid_id}";m2,s2=divmod(int(dur or 0),60)
            text+=f"{i}. 🎵 *{title}* `{m2}:{s2:02d}`\n"
            ukey=url_to_key(yt_url)
            kb.append([InlineKeyboardButton(f"⬇️ {i}. {title[:38]}",callback_data=f"dlm_{ukey}")])
        db_log(uid,'YouTube',query_text,query_text,'music_search',True)
        await status.edit_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e: await status.edit_text(f"❌ `{str(e)[:100]}`",parse_mode=ParseMode.MARKDOWN)

async def admin_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    if q.from_user.id!=ADMIN_ID: await q.answer("❌",show_alert=True);return
    await q.answer();action=q.data;s=db_global_stats()
    back=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga",callback_data="admin_main")]])
    if action=="admin_main":
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("👥 Users",callback_data="admin_users"),InlineKeyboardButton("📥 Downloads",callback_data="admin_dl")],[InlineKeyboardButton("📊 Full stats",callback_data="admin_full"),InlineKeyboardButton("🏆 Top users",callback_data="admin_top")],[InlineKeyboardButton("📅 Daily",callback_data="admin_daily"),InlineKeyboardButton("📢 Broadcast",callback_data="admin_broadcast")],[InlineKeyboardButton("🔄 Refresh",callback_data="admin_main"),InlineKeyboardButton("◀️ Menu",callback_data="menu_back")]])
        await q.edit_message_text(f"🔐 *ADMIN PANEL*\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n👥 Users: `{s['total_users']}`\n🟢 Active today: `{s['active_today']}`\n📥 Total DL: `{s['total_dl']}`\n📥 Today: `{s['dl_today']}`",parse_mode=ParseMode.MARKDOWN,reply_markup=kb)
    elif action=="admin_users":
        text=(f"👥 *USERS*\n\nTotal: `{s['total_users']}`\n\nNew:\n  Today: `{s['new_today']}`\n  Week: `{s['new_week']}`\n  Month: `{s['new_month']}`\n\nActive:\n  Today: `{s['active_today']}`\n  Week: `{s['active_week']}`\n\nRecent:\n")
        for name,uname,joined in s['recent']: text+=f"• {name or '—'} @{uname or '—'} {(joined or '')[:10]}\n"
        await q.edit_message_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="admin_dl":
        total=s['total_dl'] or 1
        text=(f"📥 *DOWNLOADS*\n\nTotal: `{s['total_dl']}`\nFailed: `{s['failed']}`\nToday: `{s['dl_today']}`\nWeek: `{s['dl_week']}`\n\n🎬 Video: `{s['video_dl']}` {bar(s['video_dl'],total)}\n🎵 Audio: `{s['audio_dl']}` {bar(s['audio_dl'],total)}\n🔍 Music: `{s['music_s']}`\n\nPlatforms:\n")
        mx=s['platforms'][0][1] if s['platforms'] else 1
        for p,cnt in s['platforms']: text+=f"  {p}: `{cnt}` {bar(cnt,mx)}\n"
        await q.edit_message_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="admin_full":
        tr=s['total_dl']+s['failed'];rate=round(s['total_dl']/tr*100) if tr else 0
        avg=round(s['total_dl']/s['total_users'],1) if s['total_users'] else 0
        text=f"📊 *FULL STATS*\n\n👥 `{s['total_users']}`\n📥 `{s['total_dl']}`\n✅ `{rate}%`\nAvg/user: `{avg}`\n\nWeek: `{s['new_week']}` new, `{s['dl_week']}` DL"
        await q.edit_message_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="admin_top":
        text="🏆 *TOP USERS*\n\n"
        medals=["🥇","🥈","🥉","4️⃣","5️⃣"]
        for i,(name,uname,dls,mus) in enumerate(s['top_users']): text+=f"{medals[i]} *{name or '—'}* @{uname or '—'}\n   📥{dls} 🎵{mus}\n\n"
        await q.edit_message_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="admin_daily":
        text="📅 *7 DAYS*\n\n"
        mx=max([d[1] for d in s['daily']] or [1])
        for day,cnt in s['daily']: text+=f"`{day}` {bar(cnt,mx,12)} `{cnt}`\n"
        text+=f"\nTotal: `{sum(d[1] for d in s['daily'])}`"
        await q.edit_message_text(text,parse_mode=ParseMode.MARKDOWN,reply_markup=back)
    elif action=="admin_broadcast":
        context.user_data['broadcast_mode']=True
        await q.edit_message_text("📢 *Broadcast*\n\nXabar yozing.",parse_mode=ParseMode.MARKDOWN,reply_markup=back)

async def broadcast_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    context.user_data['broadcast_mode']=False
    lang=get_user_lang(update.effective_user.id);msg=update.message.text
    if msg=='/cancel': await update.message.reply_text(t(lang,'cancel'));return
    users=db_all_users();status=await update.message.reply_text(f"📢 {len(users)}...")
    ok,fail=0,0
    for uid in users:
        try: await context.bot.send_message(uid,f"📢\n\n{msg}",parse_mode=ParseMode.MARKDOWN);ok+=1
        except: fail+=1
        await asyncio.sleep(0.05)
    await status.edit_text(t(lang,'broadcast_done',ok=ok,fail=fail),parse_mode=ParseMode.MARKDOWN)

async def cancel_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    context.user_data['broadcast_mode']=False
    await update.message.reply_text(t(get_user_lang(update.effective_user.id),'cancel'))

def main():
    init_db()

    # Local Bot API server (2GB limit!)
    LOCAL_API_URL  = os.environ.get("LOCAL_API_URL", "")   # masalan: http://telegram-bot-api:8081
    USE_LOCAL_API  = bool(LOCAL_API_URL)

    builder = Application.builder().token(BOT_TOKEN)

    if USE_LOCAL_API:
        base_url      = LOCAL_API_URL.rstrip("/") + "/bot"
        base_file_url = LOCAL_API_URL.rstrip("/") + "/file/bot"
        builder = (
            builder
            .base_url(base_url)
            .base_file_url(base_file_url)
            .local_mode(True)
        )
        logger.info(f"🔗 Local Bot API ishlatilmoqda: {LOCAL_API_URL}")
        # Local rejimda video/audio limitini 2GB ga oshiramiz
        import telegram.constants as tg_const
        try:
            tg_const.FileSizeLimit.FILESIZE_UPLOAD = 2_000_000_000
        except Exception:
            pass
    else:
        logger.info("☁️ Standart Telegram API ishlatilmoqda (50MB limit)")

    app = builder.build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("cancel",cancel_command))
    app.add_handler(CallbackQueryHandler(menu_callback,pattern=r'^menu_'))
    app.add_handler(CallbackQueryHandler(lang_callback,pattern=r'^lang_'))
    app.add_handler(CallbackQueryHandler(quality_callback,pattern=r'^setq_'))
    app.add_handler(CallbackQueryHandler(admin_callback,pattern=r'^admin_'))
    app.add_handler(CallbackQueryHandler(audio_button,pattern=r'^aud_'))
    app.add_handler(CallbackQueryHandler(dlmusic_button,pattern=r'^dlm_'))
    app.add_handler(CallbackQueryHandler(dlv_callback,pattern=r'^dlv_'))
    app.add_handler(CallbackQueryHandler(thumb_callback,pattern=r'^thmb_'))
    app.add_handler(CallbackQueryHandler(subs_callback,pattern=r'^sub_'))
    app.add_handler(CallbackQueryHandler(shazam_callback,pattern=r'^shaz_'))
    app.add_handler(CallbackQueryHandler(fav_callback,pattern=r'^fav_'))
    app.add_handler(CallbackQueryHandler(fav_callback,pattern=r'^delfav_'))
    app.add_handler(CallbackQueryHandler(inf_callback,pattern=r'^inf_'))
    app.add_handler(MessageHandler(filters.VOICE|filters.AUDIO,voice_handler))
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,download_video))
    logger.info("🚀 Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
