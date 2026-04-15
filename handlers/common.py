import logging
from aiogram import Router, F
from aiogram.types import Message, ErrorEvent
from aiogram.filters import Command

from config import settings
from keyboards import user_main_menu, admin_main_menu

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(Command("help"))
async def help_command(message: Message):
    if is_admin(message.from_user.id):
        text = (
            "📖 <b>Admin Buyruqlar</b>\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "🟡 <b>Post boshqaruvi:</b>\n"
            "  • /admin — Admin panel\n"
            "  • 🟡 Post Yaratish — AI bilan post\n"
            "  • 🔵 Vazifalar — Kutayotgan postlar\n"
            "  • 🟢 Kanalga Post — Tasdiqlangan postlar\n\n"
            "👥 <b>Foydalanuvchilar:</b>\n"
            "  • /users — Ro'yxat va boshqaruv\n"
            "  • 📢 Broadcast — Hammaga xabar\n\n"
            "📊 <b>Statistika:</b>\n"
            "  • 📊 Statistika — Umumiy ma'lumot\n\n"
            "⚙️ <b>Sozlamalar:</b>\n"
            "  • ADMIN_IDS, CHANNEL_ID .env da\n"
            "  • MoySklad token .env da"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=admin_main_menu())
    else:
        text = (
            "📖 <b>Prime Energy Bot — Yordam</b>\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "🎁 <b>Bonus Ballarim</b>\n"
            "  Telefon raqamingiz orqali bonus\n"
            "  balingizni ko'ring\n\n"
            "🔧 <b>Savol Berish</b>\n"
            "  Elektr bo'yicha savollarni\n"
            "  AI ustaga yuboring\n\n"
            "📚 <b>FAQ</b>\n"
            "  Ko'p so'raladigan savollar\n\n"
            "ℹ️ <b>Ma'lumot</b>\n"
            "  Kompaniya haqida ma'lumot\n\n"
            "📞 Muammo bo'lsa: +998 XX XXX-XX-XX"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=user_main_menu())


@router.message(Command("id"))
async def get_id(message: Message):
    """Telegram ID ni ko'rsatish"""
    await message.answer(
        f"🆔 <b>Telegram ID:</b> <code>{message.from_user.id}</code>\n"
        f"👤 Ism: {message.from_user.full_name}\n"
        f"🔤 Username: @{message.from_user.username or 'yoq'}",
        parse_mode="HTML"
    )


@router.error()
async def error_handler(event: ErrorEvent):
    """Global xato ushlagich"""
    logger.error(f"Global xato: {event.exception}", exc_info=event.exception)

    # Admin ga xabar
    if settings.ADMIN_IDS:
        try:
            for admin_id in settings.ADMIN_IDS[:1]:  # faqat birinchi admin
                await event.update.bot.send_message(
                    admin_id,
                    f"⚠️ <b>Bot xatosi!</b>\n\n"
                    f"<code>{str(event.exception)[:300]}</code>",
                    parse_mode="HTML"
                )
        except Exception:
            pass
