import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy import select, func

from config import settings
from database.db import get_session
from database.models import User
from keyboards import admin_main_menu

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


class UserMgmtStates(StatesGroup):
    waiting_user_id = State()
    waiting_broadcast = State()


# ─── USERS LIST ────────────────────────────────────────────────────────────────

@router.message(Command("users"))
async def list_users(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with get_session() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(20)
        )
        users = result.scalars().all()

        total = await session.execute(select(func.count()).select_from(User))
        total_count = total.scalar()

    if not users:
        await message.answer("👥 Foydalanuvchilar yo'q")
        return

    text = f"👥 <b>Foydalanuvchilar</b> (oxirgi 20 / jami {total_count})\n━━━━━━━━━━━━━━━━\n\n"

    role_icons = {"admin": "👑", "master": "🔧", "user": "👤"}

    for u in users:
        icon = role_icons.get(u.role, "👤")
        name = u.full_name or u.username or "Noma'lum"
        phone = f" | 📱{u.phone}" if u.phone else ""
        date = u.created_at.strftime("%d.%m.%Y")
        text += f"{icon} <b>{name}</b> (<code>{u.telegram_id}</code>){phone}\n"
        text += f"   <i>Rol: {u.role} | Sana: {date}</i>\n\n"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔧 Usta qilish", callback_data="mgmt:set_master"),
        InlineKeyboardButton(text="👤 User qilish", callback_data="mgmt:set_user"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Broadcast", callback_data="mgmt:broadcast"),
    )

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


# ─── SET MASTER ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "mgmt:set_master")
async def set_master_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(UserMgmtStates.waiting_user_id)
    await state.update_data(action="master")
    await callback.message.answer(
        "🔧 <b>Usta belgilash</b>\n\n"
        "Usta qilmoqchi bo'lgan foydalanuvchining <b>Telegram ID</b>sini yuboring:\n\n"
        "<i>ID ni /users buyrug'i orqali topishingiz mumkin</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "mgmt:set_user")
async def set_user_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(UserMgmtStates.waiting_user_id)
    await state.update_data(action="user")
    await callback.message.answer(
        "👤 <b>User belgilash</b>\n\n"
        "Rol o'zgartirmoqchi bo'lgan foydalanuvchining <b>Telegram ID</b>sini yuboring:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(StateFilter(UserMgmtStates.waiting_user_id))
async def process_role_change(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    action = data.get("action", "user")
    await state.clear()

    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Noto'g'ri ID. Raqam kiriting.")
        return

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                f"❌ Foydalanuvchi topilmadi: <code>{target_id}</code>",
                parse_mode="HTML"
            )
            return

        old_role = user.role
        user.role = action
        name = user.full_name or user.username or str(target_id)

    role_icons = {"master": "🔧", "user": "👤", "admin": "👑"}
    await message.answer(
        f"✅ <b>Rol o'zgartirildi!</b>\n\n"
        f"👤 Foydalanuvchi: <b>{name}</b>\n"
        f"📋 Eski rol: {role_icons.get(old_role, '?')} {old_role}\n"
        f"✨ Yangi rol: {role_icons.get(action, '?')} {action}",
        parse_mode="HTML",
        reply_markup=admin_main_menu()
    )

    # Foydalanuvchiga xabar yuborish
    try:
        if action == "master":
            text = (
                "🔧 <b>Tabriklaymiz!</b>\n\n"
                "Sizga <b>Usta</b> roli berildi.\n"
                "Endi AI yordamchi va kengaytirilgan FAQ ga kirish imkoniga egasiz.\n\n"
                "/start buyrug'ini bosing."
            )
        else:
            text = "ℹ️ Rolingiz o'zgartirildi. /start ni bosing."

        await message.bot.send_message(target_id, text, parse_mode="HTML")
    except Exception:
        pass


# ─── BROADCAST ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "mgmt:broadcast")
async def broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(UserMgmtStates.waiting_broadcast)
    await callback.message.answer(
        "📢 <b>Broadcast Xabar</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabarni yozing.\n\n"
        "⚠️ HTML formatlash qo'llab-quvvatlanadi:\n"
        "<code>&lt;b&gt;qalin&lt;/b&gt;</code> | <code>&lt;i&gt;kursiv&lt;/i&gt;</code>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(StateFilter(UserMgmtStates.waiting_broadcast))
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    broadcast_text = message.text
    await state.clear()

    # Confirm keyboard
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, yuborish", callback_data="broadcast:confirm"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="broadcast:cancel"),
    )

    await message.answer(
        f"📢 <b>Broadcast Preview:</b>\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{broadcast_text}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"Barcha foydalanuvchilarga yuboriladimi?",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

    # Xabarni saqlash (state da)
    # aslida FSMContext yopilgan, storage da saqlaymiz
    import json
    await message.bot.session.connector  # just to keep session alive
    # Broadcast textni admin message sifatida saqlaymiz
    setattr(message.bot, '_broadcast_text', broadcast_text)


@router.callback_query(F.data == "broadcast:confirm")
async def confirm_broadcast(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    broadcast_text = getattr(callback.bot, '_broadcast_text', None)
    if not broadcast_text:
        await callback.answer("❌ Xabar topilmadi, qayta yuboring")
        return

    await callback.answer("📤 Yuborilmoqda...")
    await callback.message.edit_reply_markup(reply_markup=None)

    status_msg = await callback.message.answer("📤 Broadcast yuborilmoqda...")

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_active == True)
        )
        users = result.scalars().all()

    success = 0
    failed = 0

    for user in users:
        try:
            await callback.bot.send_message(
                user.telegram_id,
                f"📢 <b>Prime Energy</b>\n\n{broadcast_text}",
                parse_mode="HTML"
            )
            success += 1
        except Exception:
            failed += 1
            # Bloklagan foydalanuvchilarni deactivate qilish
            async with get_session() as session:
                from sqlalchemy import update
                await session.execute(
                    update(User)
                    .where(User.telegram_id == user.telegram_id)
                    .values(is_active=False)
                )

    await status_msg.edit_text(
        f"✅ <b>Broadcast tugadi!</b>\n\n"
        f"📤 Yuborildi: <b>{success}</b>\n"
        f"❌ Xato: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_menu()
    )
    delattr(callback.bot, '_broadcast_text')


@router.callback_query(F.data == "broadcast:cancel")
async def cancel_broadcast(callback: CallbackQuery):
    await callback.answer("🚫 Bekor qilindi")
    await callback.message.edit_text("🚫 Broadcast bekor qilindi.")
    if hasattr(callback.bot, '_broadcast_text'):
        delattr(callback.bot, '_broadcast_text')
