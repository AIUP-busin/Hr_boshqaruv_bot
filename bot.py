import asyncio
import logging

from bot_core import bot, dp
from database import init_db


async def main() -> None:
    """Faqat lokal ishlab chiqish (development) uchun: uzun-so'rov (long polling) rejimi.

    Productionda (Render va h.k.) buni ishlatmang — o'rniga webapp/main.py
    yagona xizmat sifatida webhook orqali ishlaydi (rejimlar bir vaqtda ishlay olmaydi).
    """
    logging.basicConfig(level=logging.INFO)

    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")
