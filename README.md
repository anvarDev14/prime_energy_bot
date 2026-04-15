# ⚡ Prime Energy AI Telegram Bot

**Aiogram 3.x** asosida qurilgan professional Telegram bot.

---

## 📦 Modullar

| Modul | Tavsif |
|-------|--------|
| 🟡 Admin Panel | Post yaratish, tasdiqlash, kanalga yuborish |
| 🤖 AI Content | GPT-4 yordamida avtomatik post generatsiya |
| 🔧 Usta AI | Elektr ustalar uchun AI yordamchi |
| 🎁 Bonus System | MoySklad orqali bonus ballarini ko'rish |

---

## 🚀 Ishga Tushirish

### 1. O'rnatish
```bash
git clone ...
cd prime_energy_bot
pip install -r requirements.txt
```

### 2. Sozlash
```bash
cp .env.example .env
# .env faylini to'ldiring
```

### 3. Ishga tushirish
```bash
python main.py
```

---

## ⚙️ Sozlamalar (.env)

```env
BOT_TOKEN=...          # BotFather dan
ADMIN_IDS=[123456789]  # Admin Telegram ID lari
OPENAI_API_KEY=sk-...  # GPT uchun
CHANNEL_ID=@kanal      # Post yuboriladigan kanal
MOYSKLAD_TOKEN=...     # MoySklad API token
```

---

## 👥 Foydalanuvchi Rollari

- **user** — oddiy foydalanuvchi (bonus ko'rish, savol berish)
- **master** — usta (kengaytirilgan savol-javob, FAQ)
- **admin** — admin (post boshqaruvi, statistika)

Admin qilish:
```
ADMIN_IDS=[telegram_id]  # .env da
```

Master qilish (database orqali):
```sql
UPDATE users SET role = 'master' WHERE telegram_id = 123456789;
```

---

## 📁 Loyiha Tuzilmasi

```
prime_energy_bot/
├── main.py              # Bot ishga tushirish
├── config.py            # Sozlamalar
├── requirements.txt
├── .env.example
├── database/
│   ├── models.py        # SQLAlchemy modellari
│   └── db.py            # DB ulanish va yordamchi funksiyalar
├── handlers/
│   ├── admin.py         # Admin buyruqlari
│   ├── user.py          # Foydalanuvchi (bonus tizimi)
│   └── master.py        # Usta AI agent
├── keyboards/
│   └── __init__.py      # Barcha klaviaturalar
├── services/
│   ├── ai_service.py    # OpenAI integratsiya
│   └── moysklad.py      # MoySklad API
└── middlewares/
    └── __init__.py      # User registration middleware
```

---

## 🗺 Keyingi Bosqichlar (MVP dan keyin)

- [ ] Voice savol-javob
- [ ] Post rejalashtirish (Schedule)
- [ ] Rasm AI generatsiya (DALL-E)
- [ ] SMS tasdiqlash (bonus uchun)
- [ ] Analytics dashboard
- [ ] Multi-language (UZ/RU)

---

## 🛠 Texnologiyalar

- **Python 3.11+**
- **Aiogram 3.13** — Telegram Bot framework
- **OpenAI GPT-4o-mini** — AI content & Q&A
- **SQLAlchemy + aiosqlite** — Asinxron database
- **MoySklad REST API** — CRM integratsiya
- **SerpAPI** — Web qidiruv (ixtiyoriy)
- **Unsplash API** — Rasm qidirish (ixtiyoriy)
