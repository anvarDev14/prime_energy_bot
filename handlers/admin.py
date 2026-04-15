import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, desc

from config import settings
from database.db import get_session
from database.models import Post, Task
from keyboards import (
    admin_main_menu, post_action_keyboard, post_list_keyboard,
    cancel_keyboard, back_to_menu
)
from services.ai_service import AIContentService

logger = logging.getLogger(__name__)
router = Router()

ai_service = AIContentService(settings.ANTHROPIC_API_KEY)


class AdminStates(StatesGroup):
    waiting_task = State()
    editing_post = State()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


# ─── START ─────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Ruxsat yo'q.")
        return

    await message.answer(
        "👑 <b>Admin Panel</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_main_menu(),
        parse_mode="HTML"
    )


@router.message(F.text == "🟡 Post Yaratish")
async def start_post_creation(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.waiting_task)
    await message.answer(
        "✍️ <b>Post Yaratish</b>\n\n"
        "Post uchun vazifa/tema yuboring.\n\n"
        "<i>Misol: \"LED chirog'larning afzalliklari haqida post yozing\"</i>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(StateFilter(AdminStates.waiting_task))
async def process_task(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    task = message.text.strip()
    await state.clear()

    # Processing xabari
    processing_msg = await message.answer(
        "⏳ <b>AI post yaratmoqda...</b>\n\n"
        "🔍 Ma'lumot yig'ilmoqda\n"
        "✍️ Post yozilmoqda\n"
        "🖼 Rasm qidirilmoqda",
        parse_mode="HTML"
    )

    # Web context olish (agar SerpAPI bo'lsa)
    context = await ai_service.search_web_context(task, settings.SERP_API_KEY)

    # Post generatsiya
    content = await ai_service.generate_post(task, context)

    # Rasm URL olish
    image_url = await ai_service.get_image_url(task, settings.UNSPLASH_ACCESS_KEY)

    # Database ga saqlash
    async with get_session() as session:
        post = Post(
            task=task,
            content=content,
            image_url=image_url,
            admin_id=message.from_user.id,
            status="draft"
        )
        session.add(post)
        await session.flush()
        post_id = post.id

    # Processing xabarini o'chirish
    await processing_msg.delete()

    # Preview ko'rsatish
    preview_text = (
        f"📋 <b>POST PREVIEW</b> — #{post_id}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{content}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🖼 Rasm: {'✅ Topildi' if image_url else '❌ Topilmadi'}"
    )

    if image_url:
        await message.answer_photo(
            photo=image_url,
            caption=preview_text,
            reply_markup=post_action_keyboard(post_id),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            preview_text,
            reply_markup=post_action_keyboard(post_id),
            parse_mode="HTML"
        )


# ─── POST CALLBACKS ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("post:approve:"))
async def approve_post(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    post_id = int(callback.data.split(":")[2])

    async with get_session() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        if post:
            post.status = "approved"

    await callback.answer("✅ Post tasdiqlandi!")
    try:
        await callback.message.edit_reply_markup(
            reply_markup=post_action_keyboard(post_id)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.message.answer(
        f"✅ <b>Post #{post_id} tasdiqlandi!</b>\n\n"
        f"Kanalga yuborish uchun <b>📢 Kanalga Yuborish</b> tugmasini bosing.",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("post:reject:"))
async def reject_post(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    post_id = int(callback.data.split(":")[2])

    async with get_session() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        if post:
            post.status = "rejected"

    await callback.answer("❌ Post rad etildi")
    await callback.message.answer(
        f"❌ <b>Post #{post_id} rad etildi.</b>\n\n"
        f"Yangi post yaratish uchun 🟡 Post Yaratish ni bosing.",
        parse_mode="HTML",
        reply_markup=admin_main_menu()
    )


@router.callback_query(F.data.startswith("post:publish:"))
async def publish_post(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    post_id = int(callback.data.split(":")[2])

    async with get_session() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()

        if not post:
            await callback.answer("❌ Post topilmadi")
            return

        if post.status not in ["draft", "approved"]:
            await callback.answer("⚠️ Bu post allaqachon yuborilgan")
            return

        # Kanalga yuborish
        try:
            bot = callback.bot
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
            from datetime import datetime
            post.published_at = datetime.utcnow()

            await callback.answer("📢 Post kanalga yuborildi!")
            await callback.message.answer(
                f"📢 <b>Post #{post_id} kanalga muvaffaqiyatli yuborildi!</b>",
                parse_mode="HTML",
                reply_markup=admin_main_menu()
            )

        except Exception as e:
            logger.error(f"Kanal xatosi: {e}")
            await callback.answer("❌ Xato! Kanal sozlamalarini tekshiring.")
            await callback.message.answer(
                f"❌ <b>Xato:</b> {str(e)}\n\n"
                f"Kanal ID ni tekshiring: <code>{settings.CHANNEL_ID}</code>",
                parse_mode="HTML"
            )


@router.callback_query(F.data.startswith("post:regenerate:"))
async def regenerate_post(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    post_id = int(callback.data.split(":")[2])

    async with get_session() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()

        if not post:
            await callback.answer("❌ Post topilmadi")
            return

        task = post.task

    await callback.answer("🔄 Qayta yaratilmoqda...")
    await callback.message.answer("⏳ AI qayta post yaratmoqda...")

    content = await ai_service.generate_post(task)

    async with get_session() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        if post:
            post.content = content
            post.status = "draft"

    preview_text = (
        f"📋 <b>YANGI PREVIEW</b> — #{post_id}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{content}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    await callback.message.answer(
        preview_text,
        reply_markup=post_action_keyboard(post_id),
        parse_mode="HTML"
    )


# ─── STATISTIKA ────────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with get_session() as session:
        from sqlalchemy import func
        from database.models import User, BonusLog

        user_count_result = await session.execute(select(func.count()).select_from(User))
        user_count = user_count_result.scalar()

        post_count_result = await session.execute(
            select(func.count()).select_from(Post).where(Post.status == "published")
        )
        post_count = post_count_result.scalar()

        draft_count_result = await session.execute(
            select(func.count()).select_from(Post).where(Post.status == "draft")
        )
        draft_count = draft_count_result.scalar()

    await message.answer(
        "📊 <b>Statistika</b>\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"👥 Foydalanuvchilar: <b>{user_count}</b>\n"
        f"📢 E'lon qilingan postlar: <b>{post_count}</b>\n"
        f"📝 Kutayotgan postlar: <b>{draft_count}</b>\n",
        parse_mode="HTML",
        reply_markup=admin_main_menu()
    )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("🚫 Bekor qilindi")
    if is_admin(callback.from_user.id):
        await callback.message.answer("Admin menyuga qaytildi.", reply_markup=admin_main_menu())
