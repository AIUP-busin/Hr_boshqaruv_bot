import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Mini App sozlamalari
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
# DEV_MODE yoqilganda mini ilovani Telegram tashqarisida (oddiy brauzerda)
# ?tg_id=... parametri orqali sinash mumkin. Productionda albatta False qiling.
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# Webhook rejimi: production'da (masalan Render'da) WEBHOOK_URL beriladi,
# bot shu manzilga Telegram'dan kelayotgan yangilanishlarni qabul qiladi.
# Bo'sh bo'lsa, bot lokal uzun-so'rov (long polling) rejimida ishlaydi.
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "hrbotwebhook")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env faylini tekshiring (.env.example dan nusxa oling).")

if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS topilmadi. .env faylida kamida bitta HR/admin Telegram ID kiriting.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL topilmadi. .env faylida PostgreSQL ulanish manzilini kiriting.")
