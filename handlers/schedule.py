import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy import select

from config import settings
from database.db import get_session
from database.models import Post

logger = logging.getLogger(__name__)
router = Router()

# Scheduled vazifalar (in-memory, production uchun Redis/Celery ishlatiladi)
_scheduled_tasks: dict = {}


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


class ScheduleStates(StatesGroup):
    waiting_time = State()


def schedule_keyboard(post_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏱ 30 daqiqa", callback_data=f"sched:{post_id}:30m"),
        InlineKeyboardButton(text="🕐 1 soat", callback_data=f"sched:{post_id}:1h"),
    )
    builder.row(
        InlineKeyboardButton(text="🕕 6 soat", callback_data=f"sched:{post_id}:6h"),
        InlineKeyboardButton(text="🌅 Ertaga", callback_data=f"sched:{post_id}:tomorrow"),
    )
    builder.row(
        InlineKeyboardButton(text="⌨️ Vaqt kiritish", callback_data=f"sched:{post_id}:custom"),
        InlineKeyboardButton(text="❌ Bekor", callback_data=f"sched:{post_id}:cancel"),
    )
    return builder.as_markup()


@router.message(F.text == "🔵 Vazifalar")
async def show_tasks(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with get_session() as session:
        result = await session.execute(
            select(Post)
            .where(Post.status.in_(["draft", "approved"]))
            .order_by(Post.created_at.desc())
            .limit(10)
        )
        posts = result.scalars().all()

    if not posts:
        await message.answer(
            "📋 <b>Kutayotgan Postlar</b>\n\n"
            "Hozirda kutayotgan post yo'q.\n"
            "🟡 Post Yaratish orqali yangi post qo'shing.",
            parse_mode="HTML"
        )
        return

    text = f"📋 <b>Kutayotgan Postlar</b> ({len(posts)} ta)\n━━━━━━━━━━━━━━━━\n\n"

    builder = InlineKeyboardBuilder()
    status_icons = {"draft": "📝", "approved": "✅"}

    for post in posts:
        icon = status_icons.get(post.status, "📄")
        date = post.created_at.strftime("%d.%m %H:%M")
        text += f"{icon} <b>#{post.id}</b> — {post.task[:40]}...\n"
        text += f"   <i>Status: {post.status} | {date}</i>\n\n"

        builder.row(
            InlineKeyboardButton(
                text=f"{icon} #{post.id} — Ko'rish",
                callback_data=f"task:view:{post.id}"
            )
        )

    # Scheduled tasks ko'rsatish
    if _scheduled_tasks:
        text += "⏰ <b>Rejalashtirilgan:</b>\n"
        for pid, info in _scheduled_tasks.items():
            send_time = info['send_at'].strftime("%d.%m.%Y %H:%M")
            text += f"  • Post #{pid} → {send_time}\n"

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("task:view:"))
async def view_task_post(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    post_id = int(callback.data.split(":")[2])

    async with get_session() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()

    if not post:
        await callback.answer("❌ Post topilmadi")
        return

    from keyboards import post_action_keyboard

    text = (
        f"📄 <b>Post #{post.id}</b>\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"{post.content}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 Status: {post.status}\n"
        f"📅 Yaratilgan: {post.created_at.strftime('%d.%m.%Y %H:%M')}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Hozir Yuborish", callback_data=f"post:publish:{post.id}"),
        InlineKeyboardButton(text="⏰ Rejalashtirish", callback_data=f"schedule:post:{post.id}"),
    )
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"post:approve:{post.id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"post:reject:{post.id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="tasks:list"),
    )

    if post.image_url:
        await callback.message.answer_photo(
            photo=post.image_url,
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("schedule:post:"))
async def schedule_post_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    post_id = int(callback.data.split(":")[2])
    await callback.message.answer(
        f"⏰ <b>Post #{post_id} — Rejalashtirish</b>\n\n"
        f"Qachon kanalga yuborilsin?",
        reply_markup=schedule_keyboard(post_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sched:"))
async def handle_schedule(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    post_id = int(parts[1])
    option = parts[2]

    now = datetime.now()

    if option == "cancel":
        if post_id in _scheduled_tasks:
            _scheduled_tasks[post_id]['task'].cancel()
            del _scheduled_tasks[post_id]
            await callback.answer("🚫 Rejalashtirish bekor qilindi")
        else:
            await callback.answer("Rejalashtirilgan vazifa yo'q")
        return

    if option == "custom":
        await state.set_state(ScheduleStates.waiting_time)
        await state.update_data(post_id=post_id)
        await callback.message.answer(
            "⌨️ <b>Vaqt kiriting</b>\n\n"
            "Format: <code>DD.MM.YYYY HH:MM</code>\n"
            "Misol: <code>25.03.2025 14:30</code>",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    delay_map = {
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "tomorrow": timedelta(days=1),
    }

    delay = delay_map.get(option, timedelta(hours=1))
    send_at = now + delay
    await _schedule_post(callback.bot, post_id, send_at, callback.message)
    await callback.answer(f"⏰ Rejalashtirildi: {send_at.strftime('%d.%m.%Y %H:%M')}")


@router.message(StateFilter(ScheduleStates.waiting_time))
async def process_custom_time(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    await state.clear()

    try:
        send_at = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        if send_at <= datetime.now():
            await message.answer("❌ Vaqt o'tib ketgan. Kelajakdagi vaqt kiriting.")
            return

        await _schedule_post(message.bot, post_id, send_at, message)
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format.\n"
            "Misol: <code>25.03.2025 14:30</code>",
            parse_mode="HTML"
        )


async def _schedule_post(bot: Bot, post_id: int, send_at: datetime, reply_to: Message):
    """Postni rejalashtirilgan vaqtda yuborish"""
    delay_seconds = (send_at - datetime.now()).total_seconds()

    if post_id in _scheduled_tasks:
        _scheduled_tasks[post_id]['task'].cancel()

    async def _send():
        await asyncio.sleep(delay_seconds)
        async with get_session() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()

            if not post or post.status == "published":
                return

            try:
                if post.image_url:
                    sent = await bot.send_photo(
                        chat_id=settings.CHANNEL_ID,
                        photo=post.image_url,
                        caption=post.content,
                        parse_mode="HTML"
                    )
                else:
                    sent = await bot.send_message(
                        chat_id=settings.CHANNEL_ID,
                        text=post.content,
                        parse_mode="HTML"
                    )

                post.status = "published"
                post.channel_message_id = sent.message_id
                post.published_at = datetime.utcnow()

                # Admin ga xabar
                for admin_id in settings.ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"📢 <b>Post #{post_id} rejalashtirilgan vaqtda kanalga yuborildi!</b>\n"
                            f"🕐 Vaqt: {send_at.strftime('%d.%m.%Y %H:%M')}",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"Scheduled post xatosi: {e}")

        if post_id in _scheduled_tasks:
            del _scheduled_tasks[post_id]

    task = asyncio.create_task(_send())
    _scheduled_tasks[post_id] = {'task': task, 'send_at': send_at}

    await reply_to.answer(
        f"⏰ <b>Post #{post_id} rejalashtirildi!</b>\n\n"
        f"📅 Yuborish vaqti: <b>{send_at.strftime('%d.%m.%Y %H:%M')}</b>\n"
        f"⏱ Qoldi: {int(delay_seconds // 60)} daqiqa",
        parse_mode="HTML"
    )
