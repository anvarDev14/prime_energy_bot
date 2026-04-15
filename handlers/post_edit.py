import logging
from aiogram import Router, F
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
from keyboards import post_action_keyboard

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


class EditStates(StatesGroup):
    editing_content = State()
    editing_image = State()


def edit_menu_keyboard(post_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Matnni Tahrirlash", callback_data=f"edit:text:{post_id}"),
        InlineKeyboardButton(text="🖼 Rasm O'zgartirish", callback_data=f"edit:image:{post_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"edit:back:{post_id}"),
    )
    return builder.as_markup()


@router.callback_query(F.data.startswith("post:edit:"))
async def edit_post_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    post_id = int(callback.data.split(":")[2])
    await callback.message.answer(
        f"✏️ <b>Post #{post_id} — Tahrirlash</b>\n\n"
        f"Nima tahrirlaysiz?",
        reply_markup=edit_menu_keyboard(post_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit:text:"))
async def edit_text_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    post_id = int(callback.data.split(":")[2])

    async with get_session() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()

    if not post:
        await callback.answer("❌ Post topilmadi")
        return

    await state.set_state(EditStates.editing_content)
    await state.update_data(post_id=post_id)

    await callback.message.answer(
        f"✏️ <b>Matnni Tahrirlash</b>\n\n"
        f"Joriy matn:\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{post.content[:500]}{'...' if len(post.content) > 500 else ''}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"Yangi matni yuboring:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(StateFilter(EditStates.editing_content))
async def save_edited_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    await state.clear()

    new_content = message.text.strip()

    async with get_session() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()

        if not post:
            await message.answer("❌ Post topilmadi")
            return

        post.content = new_content
        post.status = "draft"

    await message.answer(
        f"✅ <b>Post #{post_id} yangilandi!</b>\n\n"
        f"{new_content[:200]}{'...' if len(new_content) > 200 else ''}",
        reply_markup=post_action_keyboard(post_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("edit:image:"))
async def edit_image_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    post_id = int(callback.data.split(":")[2])
    await state.set_state(EditStates.editing_image)
    await state.update_data(post_id=post_id)

    await callback.message.answer(
        f"🖼 <b>Rasm O'zgartirish</b>\n\n"
        f"Yangi rasm URL ni yuboring:\n"
        f"<i>Misol: https://unsplash.com/photos/...</i>\n\n"
        f"Yoki rasmsiz davom etish uchun <code>remove</code> yozing",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(StateFilter(EditStates.editing_image))
async def save_edited_image(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    await state.clear()

    new_url = None if message.text.strip().lower() == "remove" else message.text.strip()

    async with get_session() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()

        if not post:
            await message.answer("❌ Post topilmadi")
            return

        post.image_url = new_url

    status = "O'chirildi" if not new_url else "Yangilandi"
    await message.answer(
        f"✅ <b>Rasm {status}!</b> — Post #{post_id}",
        reply_markup=post_action_keyboard(post_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("edit:back:"))
async def back_from_edit(callback: CallbackQuery):
    post_id = int(callback.data.split(":")[2])
    await callback.message.edit_reply_markup(reply_markup=post_action_keyboard(post_id))
    await callback.answer()
