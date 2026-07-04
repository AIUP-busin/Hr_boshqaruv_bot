# HR Boshqaruv Boti

Telegram orqali ishlaydigan HR boshqaruv boti. Python (aiogram 3) + FastAPI + PostgreSQL asosida qurilgan, HR admin va xodimlar uchun Telegram Mini App bilan birga keladi.

## Imkoniyatlar

- **Xodimlar bazasi** — xodim o'zi `/start` bosib ro'yxatdan o'tadi (ism + telefon), HR admin tasdiqlaydi/rad etadi yoki xodimni Mini App orqali to'g'ridan-to'g'ri qo'shadi.
- **Davomat nazorati** — xodim "✅ Keldim" / "🚪 Ketdim" tugmalari orqali ish vaqtini belgilaydi.
- **Ta'til so'rovlari** — xodim so'rov yuboradi (tur, sana, sabab), HR tasdiqlaydi yoki rad etadi.
- **E'lonlar** — HR barcha tasdiqlangan xodimlarga bir zumda xabar yuboradi.
- **Vazifalar** — HR xodimga vazifa beradi (nom, tavsif, muddat), xodim bajarilgach "Bajarildi" deb belgilaydi.
- **Ish haqi** — HR har bir xodimga maosh belgilaydi, xodim o'z maoshini ko'ra oladi.
- **Boshqaruv paneli (Mini App)** — statistika kartalari, so'nggi faoliyat lentasi, xodim qo'shish, e'lon yuborish — barchasi chiroyli grafik interfeysda.

## Arxitektura

- **Bot + Mini App bitta jarayonda** (`webapp/main.py`) — FastAPI ilova ham `/api/*` so'rovlarini, ham Telegram webhook yangilanishlarini (`/webhook/<secret>`) qabul qiladi. Bu bitta bepul Render "Web Service"da ikkalasini birga ishlatish imkonini beradi.
- **Ma'lumotlar bazasi: PostgreSQL** (masalan [Neon](https://neon.tech), bepul va doimiy) — `asyncpg` orqali. SQLite ishlatilmaydi, chunki bepul hosting xizmatlarining fayl tizimi doimiy emas.
- **Lokal ishlab chiqish uchun** `bot.py` alohida ishga tushirilishi mumkin — u uzun-so'rov (long polling) rejimida ishlaydi, webhook talab qilmaydi.

## O'rnatish (lokal)

1. Python 3.11+ o'rnatilgan bo'lishi kerak.
2. Loyiha papkasida virtual muhit yarating va kutubxonalarni o'rnating:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. `.env.example` faylidan nusxa olib `.env` yarating va to'ldiring:
   - `BOT_TOKEN` — [@BotFather](https://t.me/BotFather) orqali olingan bot tokeni.
   - `ADMIN_IDS` — HR/admin Telegram ID raqamlari, vergul bilan ajratilgan. O'z ID'ingizni [@userinfobot](https://t.me/userinfobot) orqali bilib olasiz.
   - `DATABASE_URL` — PostgreSQL ulanish manzili (bepul olish uchun quyidagi "Ma'lumotlar bazasi" bo'limiga qarang).

## Ishga tushirish (lokal, polling rejimida)

```bash
.venv\Scripts\activate
python bot.py
```

Mini App'ni alohida sinash uchun (brauzerda, `DEV_MODE=true` bilan):

```bash
uvicorn webapp.main:app --host 127.0.0.1 --port 8000
```

va brauzerda `http://127.0.0.1:8000/?tg_id=<Telegram ID>` ni oching.

## Ma'lumotlar bazasi (Neon PostgreSQL, bepul)

1. [neon.tech](https://neon.tech) da (GitHub orqali) ro'yxatdan o'ting, yangi loyiha yarating.
2. Dashboard'dan **"Connection string"**ni oling. Muhim: Neon ikki xil manzil beradi —
   - `...-pooler.xxx.neon.tech` (PgBouncer, ko'p vaqtinchalik ulanishlar uchun)
   - `...xxx.neon.tech` (to'g'ridan-to'g'ri)

   **To'g'ridan-to'g'ri (pooler'siz)** manzilni ishlating — `asyncpg` o'zi connection pool qiladi, ikkalasini birga ishlatish xatoga olib keladi.
3. Shu manzilni `.env` dagi `DATABASE_URL` ga qo'ying.

Jadvallar birinchi ishga tushishda avtomatik yaratiladi (`database.py` dagi `init_db()`).

## Productionga joylashtirish (Render, bepul)

Render'ning bepul rejasi faqat HTTP so'rovlarga javob beruvchi **Web Service**ni qo'llab-quvvatlaydi (alohida fon-jarayon uchun pullik reja kerak). Shu sababli bot **webhook** rejimida ishlaydi — Telegram yangilanishlarni to'g'ridan-to'g'ri shu web-xizmatga yuboradi.

1. Kodni GitHub'ga push qiling.
2. [render.com](https://render.com) da **New +** → **Web Service** → GitHub repongizni tanlang.
3. Render loyihadagi `render.yaml` faylini avtomatik aniqlaydi (Build: `pip install -r requirements.txt`, Start: `uvicorn webapp.main:app --host 0.0.0.0 --port $PORT`).
4. Quyidagi environment o'zgaruvchilarni kiriting (Render dashboard → Environment):
   - `BOT_TOKEN`, `ADMIN_IDS`, `DATABASE_URL` — yuqoridagidek.
   - `WEBHOOK_URL` — Render bergan manzil, masalan `https://hr-boshqaruv-bot.onrender.com` (birinchi deploydan keyin ma'lum bo'ladi, keyin qo'shib qayta deploy qilasiz).
   - `WEBAPP_URL` — xuddi shu manzil (Mini App tugmasi shu yerga ishora qiladi).
   - `WEBHOOK_SECRET` — o'zingiz o'ylab topgan maxfiy so'z (masalan tasodifiy harflar).
   - `DEV_MODE=false` — **productionda albatta shunday bo'lishi shart**.
5. Deploy tugagach, bot avtomatik webhookni o'rnatadi (`webapp/main.py` startup jarayonida). Qo'lda tekshirish uchun: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`.

**Eslatma:** Render bepul rejasida servis ~15 daqiqa faolsiz qolsa "uxlab qoladi" va keyingi so'rovda ~30-60 soniya kechikish bilan uyg'onadi. Bu bepul reja uchun normal holat — doimiy tezkor javob kerak bo'lsa, pullik rejaga o'tish kerak bo'ladi.

## Ishlash tartibi

1. Yangi xodim botga `/start` yozadi → ism va telefon raqamini yuboradi (yoki admin uni Mini App'dan to'g'ridan-to'g'ri qo'shadi).
2. HR adminga so'rov keladi, u tasdiqlasa — lavozim, bo'lim, maoshni kiritadi.
3. Xodim tasdiqlangach, botdan yoki Mini App'dan foydalanadi (davomat, ta'til, vazifalar, maosh, profil).
4. HR Mini App'ning "🏠 Bosh sahifa"sidan umumiy holatni, so'nggi faoliyatni kuzatadi, "👥 Xodimlar"dan boshqaradi.

## Loyiha tuzilishi

```
hr-boshqaruv-bot/
├── bot_core.py          # Bot va Dispatcher (bot.py va webapp/main.py birga ishlatadi)
├── bot.py               # Faqat lokal polling rejimi uchun
├── config.py            # .env dan sozlamalarni o'qish
├── database.py          # PostgreSQL (asyncpg) bilan ishlovchi barcha funksiyalar
├── states.py            # FSM holatlari (ko'p bosqichli suhbatlar uchun)
├── keyboards.py         # Reply va inline klaviaturalar
├── handlers/
│   ├── registration.py  # Ro'yxatdan o'tish va tasdiqlash
│   ├── employee.py      # Xodim menyusi (davomat, ta'til, vazifa, maosh)
│   └── admin.py         # HR menyusi (xodimlar, e'lon, vazifa)
├── webapp/
│   ├── main.py           # FastAPI: /api/* + Telegram webhook + statik fayllar
│   ├── auth.py           # Telegram initData ni tekshirish (HMAC)
│   └── static/           # Mini App frontend (HTML/CSS/JS)
├── render.yaml           # Render deploy konfiguratsiyasi
├── requirements.txt
└── .env.example
```

## Kengaytirish g'oyalari

- Excel/PDF formatda hisobot eksport qilish.
- Har oy uchun avtomatik davomat hisobotini adminga yuborish (scheduler).
- Ko'p tilli interfeys (o'zbek/rus/ingliz).
