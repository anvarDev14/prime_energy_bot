from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from datetime import datetime


def _btn(text: str, callback_data: str, style: str = None) -> InlineKeyboardButton:
    """InlineKeyboardButton yaratish (style Telegram tomonidan qo'llab-quvvatlanmaydi)"""
    return InlineKeyboardButton(text=text, callback_data=callback_data)


# ─── ADMIN KEYBOARDS ───────────────────────────────────────────────────────────

def admin_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🟡 Post Yaratish"),
        KeyboardButton(text="📊 Statistika"),
    )
    builder.row(
        KeyboardButton(text="📢 Kanalga Post"),
        KeyboardButton(text="🔵 Vazifalar"),
    )
    builder.row(
        KeyboardButton(text="⚙️ Sozlamalar"),
        KeyboardButton(text="🚪 Chiqish"),
    )
    return builder.as_markup(resize_keyboard=True)


def post_action_keyboard(post_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        _btn("✅ Tasdiqlash", f"post:approve:{post_id}", style="success"),
        _btn("❌ Rad etish", f"post:reject:{post_id}", style="danger"),
    )
    builder.row(
        _btn("✏️ Tahrirlash", f"post:edit:{post_id}", style="secondary"),
        _btn("🔄 Qayta yaratish", f"post:regenerate:{post_id}", style="primary"),
    )
    builder.row(
        _btn("📢 Kanalga Yuborish", f"post:publish:{post_id}", style="success"),
    )
    return builder.as_markup()


def post_list_keyboard(posts: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    style_map = {
        "draft": None,
        "approved": "success",
        "rejected": "danger",
        "published": "primary",
    }
    icon_map = {
        "draft": "📝",
        "approved": "✅",
        "rejected": "❌",
        "published": "📢",
    }
    for post in posts[:10]:
        icon = icon_map.get(post.status, "📄")
        style = style_map.get(post.status)
        builder.row(
            _btn(
                text=f"{icon} #{post.id} — {post.task[:30]}...",
                callback_data=f"post:view:{post.id}",
                style=style,
            )
        )
    builder.row(_btn("🔙 Orqaga", "admin:menu", style="danger"))
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("🚫 Bekor qilish", "cancel", style="danger"))
    return builder.as_markup()


# ─── USER KEYBOARDS ────────────────────────────────────────────────────────────

def user_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🎁 Bonus Ballarim"),
        KeyboardButton(text="📦 Xaridlarim"),
    )
    builder.row(
        KeyboardButton(text="🔧 Usta AI — Savol Berish"),
        KeyboardButton(text="ℹ️ Ma'lumot"),
    )
    return builder.as_markup(resize_keyboard=True)


def share_contact_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(
            text="📱 Telefon raqamimni ulashish",
            request_contact=True
        )
    )
    builder.row(KeyboardButton(text="🔙 Orqaga"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def bonus_refresh_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        _btn("🔄 Yangilash", "bonus:refresh", style="primary"),
        _btn("📋 Tarix", "bonus:history", style="secondary"),
    )
    return builder.as_markup()


# ─── MASTER KEYBOARDS ──────────────────────────────────────────────────────────

def master_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🔧 Savol Berish"),
        KeyboardButton(text="📚 FAQ"),
    )
    builder.row(
        KeyboardButton(text="🎁 Bonus Ballarim"),
        KeyboardButton(text="📦 Xaridlarim"),
    )
    builder.row(
        KeyboardButton(text="ℹ️ Ma'lumot"),
    )
    return builder.as_markup(resize_keyboard=True)


def master_faq_keyboard(faqs: list = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    categories = [
        ("⚡ Elektr", "faq:elektr"),
        ("🔌 Kabel", "faq:kabel"),
        ("💡 Yoritish", "faq:yoritish"),
        ("🏗️ O'rnatish", "faq:ornatish"),
        ("🛡️ Xavfsizlik", "faq:xavfsizlik"),
    ]
    styles = ["primary", "success", "secondary", "primary", "success"]
    for (text, callback), style in zip(categories, styles):
        builder.row(_btn(text, callback, style=style))
    builder.adjust(2, 2, 1)
    builder.row(_btn("🔙 Orqaga", "menu:main", style="danger"))
    return builder.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("🏠 Bosh Menyu", "menu:main", style="primary"))
    return builder.as_markup()


def purchases_dates_keyboard(grouped: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for date_str in sorted(grouped.keys(), reverse=True)[:10]:
        count = len(grouped[date_str])
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            label = dt.strftime("%d.%m.%Y")
        except Exception:
            label = date_str
        builder.row(
            _btn(
                text=f"📅 {label}  ({count} ta xarid)",
                callback_data=f"purchases:date:{date_str}",
                style="primary",
            )
        )
    builder.row(_btn("🏠 Bosh Menyu", "menu:main", style="primary"))
    return builder.as_markup()


def purchases_orders_keyboard(orders: list, date_str: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order in orders:
        moment = order.get("moment", "")
        time_str = moment[11:16] if len(moment) > 15 else "--:--"
        total = order.get("sum", 0) / 100
        order_id = order.get("id", "")
        builder.row(
            _btn(
                text=f"🧾 {time_str}  —  {total:,.0f} so'm",
                callback_data=f"purchases:order:{order_id}",
                style="success",
            )
        )
    builder.row(_btn("🔙 Orqaga", "purchases:list", style="danger"))
    return builder.as_markup()


def purchase_receipt_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("🔙 Xaridlar", "purchases:list", style="danger"))
    builder.row(_btn("🏠 Bosh Menyu", "menu:main", style="primary"))
    return builder.as_markup()


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
