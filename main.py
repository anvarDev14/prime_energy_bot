import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database.db import init_db
from handlers import admin, user, master
from handlers import user_mgmt, schedule, post_edit, common
from middlewares import UserRegistrationMiddleware

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 Prime Energy Bot ishga tushmoqda...")

    # Database init
    await init_db(settings.DATABASE_URL)

    # Bot & Dispatcher
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware
    dp.message.middleware(UserRegistrationMiddleware())

    # Routerlarni qo'shish (tartibi muhim!)
    dp.include_router(common.router)       # /help, /id, error handler
    dp.include_router(admin.router)        # Admin panel, post yaratish
    dp.include_router(post_edit.router)    # Post tahrirlash
    dp.include_router(schedule.router)     # Post rejalashtirish
    dp.include_router(user_mgmt.router)    # Foydalanuvchi boshqaruvi
    dp.include_router(master.router)       # Usta AI agent
    dp.include_router(user.router)         # Bonus tizimi

    # Bot ma'lumotlari
    bot_info = await bot.get_me()
    logger.info(f"✅ Bot: @{bot_info.username} ({bot_info.full_name})")
    logger.info(f"👑 Adminlar: {settings.ADMIN_IDS}")

    # Polling boshlash
    await dp.start_polling(
        bot,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ Bot to'xtatildi")
