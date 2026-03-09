# 🤖 Social Media Video Downloader Bot

## Qo'llab-quvvatlanadigan saytlar
- YouTube, Instagram, TikTok, Twitter/X, Facebook
- Pinterest, Twitch, Vimeo, Dailymotion va 1000+ sayt

---

## 🚀 Railway.app ga Deploy qilish (BEPUL, 24/7)

### 1-qadam: GitHub ga yuklash
1. https://github.com ga boring va akkaunt oching
2. "New repository" bosing → nom bering (masalan: `my-video-bot`)
3. "Create repository" bosing
4. Quyidagi fayllarni yuklang:
   - `bot.py`
   - `requirements.txt`
   - `Procfile`
   - `railway.toml`

### 2-qadam: Railway ga ulanish
1. https://railway.app ga boring
2. "Login with GitHub" bosing
3. "New Project" → "Deploy from GitHub repo"
4. O'zingizning repo ni tanlang

### 3-qadam: Environment Variable qo'shish (MUHIM!)
1. Railway dashboard da loyihangizni oching
2. "Variables" tabiga bosing
3. "+ New Variable" bosing:
   - Key: `BOT_TOKEN`
   - Value: `8771567039:AAGszNeQf63J2MEMOmpjJ1P0PLzm0CVR1Mg`
4. "Add" bosing

### 4-qadam: Deploy!
Railway avtomatik deploy qiladi. 2-3 daqiqa kuting.
"Active" yashil ko'rsatsa — bot ishlayapti! ✅

---

## 📱 Telegram da sinash
Botingizni toping va `/start` yuboring, keyin video havolasi yuboring.

---

## ⚠️ Muhim eslatmalar
- Video 50MB dan katta bo'lsa, bot havola yuboradi
- Instagram private postlari yuklanmaydi
- Railway bepul planda oyiga 500 soat ishlaydi (yetarli)
