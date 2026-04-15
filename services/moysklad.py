import aiohttp
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

MOYSKLAD_BASE_URL = "https://api.moysklad.ru/api/remap/1.2"


class MoySkladService:
    def __init__(self, token: str, bonus_field_id: str = ""):
        self.token = token
        self.bonus_field_id = bonus_field_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
        }

    async def find_customer_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Telefon raqam bo'yicha mijozni topish"""
        clean = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        # Raqamni normallashtirish: faqat raqamlar
        digits = clean.replace("+", "")
        last9 = digits[-9:] if len(digits) >= 9 else digits

        # search parametri bilan qidiruv variantlari
        search_variants = [
            f"+{digits}",   # +998901234567
            digits,         # 998901234567
            last9,          # 901234567
        ]

        async with aiohttp.ClientSession() as session:
            for search_term in search_variants:
                url = f"{MOYSKLAD_BASE_URL}/entity/counterparty"
                params = {"search": search_term, "limit": 10}

                try:
                    async with session.get(url, headers=self.headers, params=params) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            logger.warning(f"MoySklad status {resp.status}: {body[:200]}")
                            continue
                        data = await resp.json()
                        rows = data.get("rows", [])
                        for row in rows:
                            row_phone = (
                                row.get("phone", "")
                                .replace("+", "").replace(" ", "")
                                .replace("-", "").replace("(", "").replace(")", "")
                            )
                            # Oxirgi 9 raqam bo'yicha solishtirish
                            if row_phone and (row_phone[-9:] == last9 or last9 in row_phone):
                                logger.info(f"✅ Mijoz topildi: {row.get('name')} (phone: {row.get('phone')})")
                                return row
                except Exception as e:
                    logger.error(f"MoySklad qidiruv xatosi ({search_term}): {e}")

        logger.warning(f"❌ Mijoz topilmadi: {phone}")
        return None

    async def get_bonus_points(self, customer_id: str) -> float:
        """Mijozning bonus ballarini olish"""
        async with aiohttp.ClientSession() as session:
            url = f"{MOYSKLAD_BASE_URL}/entity/counterparty/{customer_id}"

            try:
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Counterparty data keys: {list(data.keys())}")

                        # 1. Custom field bo'yicha tekshirish
                        if self.bonus_field_id:
                            attributes = data.get("attributes", [])
                            for attr in attributes:
                                if attr.get("id") == self.bonus_field_id:
                                    value = attr.get("value", 0)
                                    return float(value) if value else 0.0

                        # 2. MoySklad ichki bonus dasturi
                        points = data.get("bonusPoints")
                        if points is not None:
                            return float(points)

                        # 3. Attributes ichidan "bonus" nomli maydonni qidirish
                        attributes = data.get("attributes", [])
                        for attr in attributes:
                            name = attr.get("name", "").lower()
                            if "bonus" in name:
                                value = attr.get("value", 0)
                                logger.info(f"Bonus attribute topildi: {attr.get('name')} = {value}")
                                return float(value) if value else 0.0

            except Exception as e:
                logger.error(f"Bonus olish xatosi: {e}")

        return 0.0

    async def get_customer_info(self, phone: str) -> Dict[str, Any]:
        """To'liq mijoz ma'lumotlari"""
        customer = await self.find_customer_by_phone(phone)

        if not customer:
            return {
                "found": False,
                "message": "Mijoz topilmadi",
            }

        customer_id = customer.get("id", "")
        bonus_points = await self.get_bonus_points(customer_id)

        return {
            "found": True,
            "id": customer_id,
            "name": customer.get("name", "Noma'lum"),
            "phone": phone,
            "bonus_points": bonus_points,
            "email": customer.get("email", ""),
            "description": customer.get("description", ""),
        }

    async def get_purchase_history(self, customer_id: str, limit: int = 30) -> list:
        """Xaridlar tarixini olish"""
        async with aiohttp.ClientSession() as session:
            url = f"{MOYSKLAD_BASE_URL}/entity/retaildemand"
            params = {
                "filter": f"agent={MOYSKLAD_BASE_URL}/entity/counterparty/{customer_id}",
                "order": "moment,desc",
                "limit": limit,
            }

            try:
                async with session.get(url, headers=self.headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("rows", [])
            except Exception as e:
                logger.error(f"Tarix olish xatosi: {e}")

        return []

    async def get_purchases_grouped_by_date(self, customer_id: str) -> dict:
        """Xaridlarni sanalar bo'yicha guruhlash"""
        orders = await self.get_purchase_history(customer_id, limit=30)
        grouped: dict = {}
        for order in orders:
            moment = order.get("moment", "")
            date_str = moment[:10]  # "2024-01-15"
            if date_str not in grouped:
                grouped[date_str] = []
            grouped[date_str].append(order)
        return grouped

    async def get_order_positions(self, order_id: str) -> list:
        """Buyurtma mahsulotlari ro'yxatini olish"""
        async with aiohttp.ClientSession() as session:
            url = f"{MOYSKLAD_BASE_URL}/entity/retaildemand/{order_id}/positions"
            params = {"limit": 100, "expand": "assortment"}

            try:
                async with session.get(url, headers=self.headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("rows", [])
                    else:
                        logger.error(f"Positions xatosi: {resp.status}")
            except Exception as e:
                logger.error(f"Positions olish xatosi: {e}")

        return []
