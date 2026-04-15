import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, Contact
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import settings
from database.db import get_session, get_or_create_user
from database.models import User, BonusLog
from keyboards import (
    user_main_menu, share_contact_keyboard, bonus_refresh_keyboard, back_to_menu,
    purchases_dates_keyboard, purchases_orders_keyboard, purchase_receipt_keyboard,
)
from services.moysklad import MoySkladService
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = Router()

moysklad = MoySkladService(
    token=settings.MOYSKLAD_TOKEN,
    bonus_field_id=settings.MOYSKLAD_BONUS_FIELD_ID,
)


class UserStates(StatesGroup):
    waiting_contact = State()


# ─── START ─────────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def start_command(message: Message):
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    is_master = user.role == "master"
    from keyboards import master_main_menu

    await message.answer(
        f"⚡ <b>Salom, {message.from_user.first_name}!</b>\n\n"
        f"<b>Prime Energy</b> botiga xush kelibsiz!\n\n"
        f"🔋 Elektr materiallari bo'yicha eng yaxshi yechimlar\n"
        f"🏆 Sifat va ishonchlilik garantiyasi\n\n"
        f"Quyidagi xizmatlardan foydalaning 👇",
        reply_markup=master_main_menu() if is_master else user_main_menu(),
        parse_mode="HTML"
    )


# ─── BONUS SYSTEM ──────────────────────────────────────────────────────────────

@router.message(F.text == "🎁 Bonus Ballarim")
async def check_bonus(message: Message, state: FSMContext):
    user = await get_or_create_user(telegram_id=message.from_user.id)

    # Agar telefon raqam saqlangan bo'lsa
    if user.phone:
        await show_bonus(message, user.phone)
    else:
        await state.set_state(UserStates.waiting_contact)
        await message.answer(
            "📱 <b>Bonus Ballarini Ko'rish</b>\n\n"
            "Bonus balingizni ko'rish uchun telefon raqamingizni ulashing.\n\n"
            "⬇️ Pastdagi tugmani bosing:",
            reply_markup=share_contact_keyboard(),
            parse_mode="HTML"
        )


@router.message(F.contact, StateFilter(UserStates.waiting_contact))
async def handle_contact(message: Message, state: FSMContext):
    contact: Contact = message.contact
    phone = contact.phone_number

    await state.clear()

    # Faqat o'z raqamini ulashishga ruxsat
    if contact.user_id != message.from_user.id:
        await message.answer(
            "⚠️ Faqat o'z telefon raqamingizni ulashing.",
            reply_markup=user_main_menu()
        )
        return

    # Loading
    loading_msg = await message.answer(
        "⏳ Ma'lumotlar tekshirilmoqda...",
        reply_markup=user_main_menu()
    )

    # User ni yangilash
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.phone = phone

    await loading_msg.delete()
    await show_bonus(message, phone)


@router.callback_query(F.data == "bonus:refresh")
async def refresh_bonus(callback: CallbackQuery):
    user = await get_or_create_user(telegram_id=callback.from_user.id)

    if not user.phone:
        await callback.answer("📱 Avval telefon raqamingizni ulashing")
        return

    await callback.answer("🔄 Yangilanmoqda...")
    await show_bonus(callback.message, user.phone, edit=True)


async def show_bonus(message: Message, phone: str, edit: bool = False):
    """Bonus ma'lumotlarini ko'rsatish"""
    info = await moysklad.get_customer_info(phone)

    if not info["found"]:
        text = (
            "❌ <b>Mijoz topilmadi</b>\n\n"
            f"📱 Telefon: <code>{phone}</code>\n\n"
            "Agar siz Prime Energy mijozi bo'lsangiz,\n"
            "bizga murojaat qiling:\n"
            "📞 +998 XX XXX-XX-XX"
        )
    else:
        bonus = info["bonus_points"]
        stars = "⭐" * min(int(bonus / 100), 5) if bonus > 0 else "🔘"

        text = (
            f"🎁 <b>Bonus Ma'lumotlari</b>\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"👤 Mijoz: <b>{info['name']}</b>\n"
            f"📱 Telefon: <code>{phone}</code>\n\n"
            f"💰 <b>Bonus ballar: {bonus:,.0f} ball</b>\n"
            f"{stars}\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<i>💡 1 ball = 1 so'm chegirma</i>"
        )

        # Log saqlash
        async with get_session() as session:
            log = BonusLog(
                telegram_id=message.chat.id,
                phone=phone,
                bonus_points=bonus
            )
            session.add(log)

    if edit:
        try:
            await message.edit_text(text, reply_markup=bonus_refresh_keyboard(), parse_mode="HTML")
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
    else:
        await message.answer(text, reply_markup=bonus_refresh_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "bonus:history")
async def bonus_history(callback: CallbackQuery):
    async with get_session() as session:
        result = await session.execute(
            select(BonusLog)
            .where(BonusLog.telegram_id == callback.from_user.id)
            .order_by(BonusLog.checked_at.desc())
            .limit(5)
        )
        logs = result.scalars().all()

    if not logs:
        await callback.answer("📋 Tarix bo'sh")
        return

    text = "📋 <b>Tekshirish Tarixi</b>\n━━━━━━━━━━━━━━━━\n\n"
    for log in logs:
        date_str = log.checked_at.strftime("%d.%m.%Y %H:%M")
        text += f"• {date_str}: <b>{log.bonus_points:,.0f} ball</b>\n"

    await callback.message.answer(text, parse_mode="HTML", reply_markup=back_to_menu())
    await callback.answer()


# ─── PURCHASE HISTORY ─────────────────────────────────────────────────────────

@router.message(F.text == "📦 Xaridlarim")
async def purchases_menu(message: Message):
    user = await get_or_create_user(telegram_id=message.from_user.id)

    if not user.phone:
        await message.answer(
            "📱 Xaridlaringizni ko'rish uchun avval telefon raqamingizni ulashing.\n\n"
            "👉 <b>🎁 Bonus Ballarim</b> tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=user_main_menu(),
        )
        return

    await _show_purchases_list(message, user.phone, edit=False)


@router.callback_query(F.data == "purchases:list")
async def purchases_list_callback(callback: CallbackQuery):
    user = await get_or_create_user(telegram_id=callback.from_user.id)
    if not user.phone:
        await callback.answer("📱 Avval telefon raqamingizni ulashing", show_alert=True)
        return
    await callback.answer()
    await _show_purchases_list(callback.message, user.phone, edit=True)


async def _show_purchases_list(message: Message, phone: str, edit: bool):
    customer = await moysklad.find_customer_by_phone(phone)
    if not customer:
        text = "❌ Mijoz MoySkladda topilmadi."
        if edit:
            try:
                await message.edit_text(text, reply_markup=back_to_menu())
            except TelegramBadRequest:
                pass
        else:
            await message.answer(text, reply_markup=back_to_menu())
        return

    customer_id = customer["id"]
    grouped = await moysklad.get_purchases_grouped_by_date(customer_id)

    if not grouped:
        text = "📦 <b>Xaridlar tarixi bo'sh</b>\n\nHozircha hech qanday xarid topilmadi."
        kb = back_to_menu()
    else:
        total_orders = sum(len(v) for v in grouped.values())
        text = (
            f"📦 <b>Xaridlar Tarixi</b>\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"👤 {customer.get('name', '')}\n"
            f"📊 Jami: <b>{total_orders} ta xarid</b>\n\n"
            f"Sanani tanlang:"
        )
        kb = purchases_dates_keyboard(grouped)

    if edit:
        try:
            await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("purchases:date:"))
async def purchases_by_date(callback: CallbackQuery):
    date_str = callback.data.split("purchases:date:")[1]  # "2024-01-15"
    user = await get_or_create_user(telegram_id=callback.from_user.id)
    if not user.phone:
        await callback.answer("📱 Avval telefon raqamingizni ulashing", show_alert=True)
        return

    await callback.answer()

    customer = await moysklad.find_customer_by_phone(user.phone)
    if not customer:
        await callback.message.edit_text("❌ Mijoz topilmadi.", reply_markup=back_to_menu())
        return

    grouped = await moysklad.get_purchases_grouped_by_date(customer["id"])
    orders = grouped.get(date_str, [])

    if not orders:
        await callback.message.edit_text(
            f"📅 {date_str} sanasida xarid topilmadi.",
            reply_markup=back_to_menu(),
        )
        return

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        label = dt.strftime("%d.%m.%Y")
    except Exception:
        label = date_str

    text = (
        f"📅 <b>{label}</b> — xaridlar\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"Chekni ko'rish uchun tanlang:"
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=purchases_orders_keyboard(orders, date_str),
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(F.data.startswith("purchases:order:"))
async def purchases_order_detail(callback: CallbackQuery):
    order_id = callback.data.split("purchases:order:")[1]
    await callback.answer("⏳ Yuklanmoqda...")

    positions = await moysklad.get_order_positions(order_id)

    if not positions:
        await callback.message.edit_text(
            "❌ Chek ma'lumotlari topilmadi.",
            reply_markup=purchase_receipt_keyboard(),
        )
        return

    lines = []
    total = 0.0
    for i, pos in enumerate(positions, 1):
        assortment = pos.get("assortment", {})
        name = assortment.get("name", "Noma'lum mahsulot")
        qty = pos.get("quantity", 0)
        price = pos.get("price", 0) / 100
        discount = pos.get("discount", 0)
        api_sum = pos.get("sum", 0) / 100
        pos_sum = api_sum if api_sum else qty * price * (1 - discount / 100)
        total += pos_sum

        qty_str = f"{qty:g}"
        if discount:
            lines.append(f"{i}. {name}\n   {qty_str} × {price:,.0f} (-{discount}%) = <b>{pos_sum:,.0f}</b>")
        else:
            lines.append(f"{i}. {name}\n   {qty_str} × {price:,.0f} = <b>{pos_sum:,.0f}</b>")

    items_text = "\n".join(lines)
    text = (
        f"🧾 <b>Chek</b>\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"{items_text}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Jami: {total:,.0f} so'm</b>"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=purchase_receipt_keyboard(),
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ─── INFO ──────────────────────────────────────────────────────────────────────

@router.message(F.text == "ℹ️ Ma'lumot")
async def show_info(message: Message):
    await message.answer(
        "Premium Product ⚡️\n\n"
        "💡 Prime Energy bilan uyingizni xavfsiz va yorqin qiling!\n"
        "⚡️ Elektrika va montaj uchun barcha turdagi premium tovarlar.\n"
        "🛠 Sifatli jihozlar — xavfsiz hayot garovi!\n\n"
        "📍 Radakiy 175B\n"
        "📞 +998 (91) 709-40-46 | @anvar_prime",
        reply_markup=user_main_menu()
    )
