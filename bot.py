import os
import re
import asyncio
import tempfile
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import yt_dlp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8771567039:AAGszNeQf63J2MEMOmpjJ1P0PLzm0CVR1Mg")

URL_PATTERN = re.compile(
    r'https?://[^\s]+'
)

SUPPORTED_SITES = [
    "youtube.com", "youtu.be",
    "instagram.com",
    "tiktok.com",
    "twitter.com", "x.com",
    "facebook.com", "fb.watch",
    "vk.com",
    "reddit.com",
    "pinterest.com",
    "twitch.tv",
    "dailymotion.com",
    "vimeo.com",
    "ok.ru",
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Salom! Men Social Media Video Downloader botman!*\n\n"
        "📥 Quyidagi saytlardan video yuklab beraman:\n\n"
        "• 🎬 YouTube\n"
        "• 📸 Instagram (Reels, Posts, Stories)\n"
        "• 🎵 TikTok\n"
        "• 🐦 Twitter / X\n"
        "• 👥 Facebook\n"
        "• 📌 Pinterest\n"
        "• 🎮 Twitch\n"
        "• 🎞 Vimeo, Dailymotion\n"
        "• va boshqa 1000+ sayt!\n\n"
        "✅ *Ishlatish:* Shunchaki havola yuboring!\n"
        "Masalan: `https://www.instagram.com/reel/...`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ *Yordam*\n\n"
        "1. Video havolasini menga yuboring\n"
        "2. Men avtomatik aniqlab yuklab beraman\n"
        "3. Video 50MB dan katta bo'lsa, havola shaklida yuboraman\n\n"
        "❓ Muammo bo'lsa: @admin ga murojaat qiling"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

def is_url(text):
    return bool(URL_PATTERN.search(text))

def extract_url(text):
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text

    if not is_url(message_text):
        await update.message.reply_text(
            "❌ Havola topilmadi.\nIltimos, to'g'ri URL yuboring.\nMasalan: `https://instagram.com/reel/...`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    url = extract_url(message_text)

    status_msg = await update.message.reply_text("⏳ Yuklanmoqda... Iltimos kuting!")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'format': 'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<45M]/best[filesize<45M]/best',
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
            }

            loop = asyncio.get_event_loop()

            def do_download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info

            info = await loop.run_in_executor(None, do_download)

            # Find downloaded file
            files = os.listdir(tmpdir)
            if not files:
                raise Exception("Fayl topilmadi")

            video_file = os.path.join(tmpdir, files[0])
            file_size = os.path.getsize(video_file)
            title = info.get('title', 'Video')[:50]
            uploader = info.get('uploader', '')
            duration = info.get('duration', 0)

            # 50MB limit for Telegram
            if file_size > 50 * 1024 * 1024:
                caption = (
                    f"⚠️ *Video hajmi katta (50MB dan oshdi)*\n\n"
                    f"📎 To'g'ridan-to'g'ri havola:\n{url}"
                )
                await status_msg.edit_text(caption, parse_mode=ParseMode.MARKDOWN)
                return

            caption_text = f"🎬 *{title}*"
            if uploader:
                caption_text += f"\n👤 {uploader}"
            if duration:
                mins = int(duration) // 60
                secs = int(duration) % 60
                caption_text += f"\n⏱ {mins}:{secs:02d}"
            caption_text += f"\n\n📥 @{context.bot.username}"

            await status_msg.edit_text("📤 Telegram ga yuklanyapti...")

            with open(video_file, 'rb') as vf:
                await update.message.reply_video(
                    video=vf,
                    caption=caption_text,
                    parse_mode=ParseMode.MARKDOWN,
                    supports_streaming=True
                )

            await status_msg.delete()

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Private" in error_msg or "private" in error_msg:
            msg = "🔒 Bu video *private* (yopiq). Ochiq videolarni yuklash mumkin."
        elif "not available" in error_msg.lower():
            msg = "❌ Bu video mavjud emas yoki o'chirilgan."
        elif "instagram" in error_msg.lower():
            msg = "📸 Instagram uchun cookie kerak bo'lishi mumkin. Ochiq postlarni sinab ko'ring."
        else:
            msg = f"❌ Yuklab bo'lmadi.\nSabab: {error_msg[:200]}"
        await status_msg.edit_text(msg, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(
            f"❌ Xatolik yuz berdi.\nIltimos qayta urinib ko'ring.\n\n`{str(e)[:150]}`",
            parse_mode=ParseMode.MARKDOWN
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    logger.info("Bot ishga tushdi! 🚀")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
