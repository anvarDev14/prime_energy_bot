import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import settings
from database.db import get_session, get_or_create_user
from database.models import MasterQuestion
from keyboards import master_main_menu, master_faq_keyboard, back_to_menu
from services.ai_service import AIContentService

logger = logging.getLogger(__name__)
router = Router()

ai_service = AIContentService(settings.ANTHROPIC_API_KEY)


class MasterStates(StatesGroup):
    waiting_question = State()


FAQ_DATA = {
    "elektr": [
        ("⚡ Uy uchun qancha amper kerak?", "Standart uy uchun 25-40A, katta uylar uchun 50-63A kifoya qiladi."),
        ("🔌 RCD nima?", "RCD (Residual Current Device) — odam hayotini elektr tokidan himoya qiluvchi qurilma."),
        ("💡 Fazalar qanday tekshiriladi?", "Multimetr yoki indikator otvertka bilan. 220V faza-nol, 380V faza-faza."),
    ],
    "kabel": [
        ("🔶 Kabel kesimini qanday tanlash?", "1 mm² ≈ 10A. 16A uchun 1.5mm², 25A uchun 2.5mm² ishlatiladi."),
        ("🌡️ VVG vs NYM kabel farqi?", "NYM — nam joylarga, VVG — quruq joylarga mo'ljallangan."),
        ("📏 Kabel uzunligi ta'sir qiladimi?", "Ha! Uzun kabelda kuchlanish tushishi bo'ladi. 20m+ uchun kesimni oshiring."),
    ],
    "yoritish": [
        ("💡 LED quvvat hisobi?", "LED: 1W ≈ 100 lumen. 25m² xona uchun ≈ 2500 lumen (25W LED) kerak."),
        ("🌈 Rang temperaturasi?", "2700K — issiq sariq (yotoqxona), 4000K — oq (ish xonasi), 6500K — sovuq oq."),
        ("🔦 LED va galogen farqi?", "LED 80% kam elektr sarflaydi, 25x uzoqroq ishlaydi."),
    ],
    "ornatish": [
        ("🔧 Rozetka balandligi?", "Standart: poldan 30cm. Oshxona: ish stoli balandligidan 10-15cm yuqori."),
        ("📐 Kabel chuqurligi?", "Devor ichida: 10-15mm. To'g'ri burchakda burilish — kabelga zarar."),
        ("🏠 Qo'ng'iroq sxemasi?", "220V 2-sim: faza pushti/qizil (L), nol ko'k (N). Earth (PE) sariq-yashil."),
    ],
    "xavfsizlik": [
        ("⚠️ Asosiy xavfsizlik qoidalari?", "Doim quvvatni o'chiring! Quruq qo'l, izolyatsion asboblar, ko'zoynak."),
        ("🚫 Suvli xonada nima mumkin emas?", "Tashqi rozetka va kalitlar yo'q, IP44+ himoya darajasi, RCD majburiy."),
        ("🆘 Elektr urganida nima qilish?", "Avval quvvatni o'chiring, shunda yordam bering. 103 (Tez Yordam) tering."),
    ],
}


@router.message(F.text == "🔧 Usta AI — Savol Berish")
@router.message(F.text == "🔧 Savol Berish")
async def start_question(message: Message, state: FSMContext):
    await state.set_state(MasterStates.waiting_question)
    await message.answer(
        "🔧 <b>Usta AI Yordamchi</b>\n\n"
        "Elektr o'rnatish, kabel tanlash, xavfsizlik va boshqa savollarga javob beraman.\n\n"
        "✍️ Savolingizni yozing:",
        parse_mode="HTML"
    )


@router.message(StateFilter(MasterStates.waiting_question), F.text)
async def handle_question(message: Message, state: FSMContext):
    question = message.text.strip()
    await state.clear()

    # Saqlash
    async with get_session() as session:
        q = MasterQuestion(
            user_id=message.from_user.id,
            question=question
        )
        session.add(q)
        await session.flush()
        q_id = q.id

    # Loading
    loading_msg = await message.answer("🤔 AI javob tayyorlamoqda...")

    # AI javob
    answer = await ai_service.answer_master_question(question)

    # Javobni saqlash
    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(MasterQuestion).where(MasterQuestion.id == q_id)
        )
        q = result.scalar_one_or_none()
        if q:
            q.answer = answer

    await loading_msg.delete()

    await message.answer(
        f"🔧 <b>Javob:</b>\n\n"
        f"{answer}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<i>⚠️ Murakkab ishlarni faqat mutaxassis bajarsin</i>",
        parse_mode="HTML",
        reply_markup=master_faq_keyboard()
    )


@router.message(F.text == "📚 FAQ")
async def show_faq(message: Message):
    await message.answer(
        "📚 <b>Ko'p So'raladigan Savollar</b>\n\n"
        "Kategoriyani tanlang:",
        reply_markup=master_faq_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("faq:"))
async def show_faq_category(callback: CallbackQuery):
    category = callback.data.split(":")[1]

    faqs = FAQ_DATA.get(category, [])
    if not faqs:
        await callback.answer("❌ Ma'lumot topilmadi")
        return

    category_names = {
        "elektr": "⚡ Elektr",
        "kabel": "🔌 Kabel",
        "yoritish": "💡 Yoritish",
        "ornatish": "🏗️ O'rnatish",
        "xavfsizlik": "🛡️ Xavfsizlik",
    }

    text = f"📚 <b>{category_names.get(category, 'FAQ')}</b>\n━━━━━━━━━━━━━━━━\n\n"
    for i, (question, answer) in enumerate(faqs, 1):
        text += f"<b>{i}. {question}</b>\n{answer}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=back_to_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery):
    user = await get_or_create_user(telegram_id=callback.from_user.id)
    from keyboards import user_main_menu
    markup = master_main_menu() if user.role == "master" else user_main_menu()

    await callback.message.answer(
        "🏠 <b>Bosh Menyu</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )
    await callback.answer()
