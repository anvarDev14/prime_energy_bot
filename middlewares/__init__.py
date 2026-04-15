from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from typing import Callable, Any, Awaitable, Dict
from database.db import get_or_create_user


class UserRegistrationMiddleware(BaseMiddleware):
    """Har bir xabarda foydalanuvchini avtomatik ro'yxatdan o'tkazish"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
            await get_or_create_user(
                telegram_id=user.id,
                username=user.username,
                full_name=user.full_name,
            )

        return await handler(event, data)
