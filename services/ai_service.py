import logging
import aiohttp
import anthropic
from typing import Optional

logger = logging.getLogger(__name__)


CONTENT_SYSTEM_PROMPT = """Sen Prime Energy kompaniyasi uchun professional SMM manager va elektr mahsulotlari mutaxassisisan.

Post yaratishda quyidagi formatga amal qil:

🔥 **[SARLAVHA]** (qisqa, jozibador, emoji bilan)

[KIRISH] - 1-2 jumla, diqqat tortuvchi

[ASOSIY QISM] - 3-5 bullet point yoki qisqa paragraf
• Muhim fakt/foyda
• Texnik ma'lumot
• Nima uchun kerak?

[CTA] - Harakatga chaqiruv
📞 +998 XX XXX-XX-XX | 🌐 prime-energy.uz

Qoidalar:
- O'zbek tilida yoz
- Sodda va tushunarli til
- Emoji lar bilan vizual rang qo'sh
- 150-250 so'z (Telegram uchun optimal)
- Sotuvga yo'naltirilgan"""

MASTER_SYSTEM_PROMPT = """Sen Prime Energy kompaniyasining tajribali elektr ustasisisan va texnik maslahatchi.

Quyidagi qoidalarga rioya qil:
- Savollarga qisqa va aniq javob ber (50-100 so'z)
- Amaliy va xavfsiz maslahat ber
- Elektr xavfsizligini doimo ta'kidla
- Kerak bo'lsa, mutaxassisga murojaat qilishni tavsiya et
- O'zbek tilida yoz, texnik terminlarni tushuntir

Agar savol xavfli bo'lsa, DOIMO mutaxassisga murojaat qilishni tavsiya et."""


class AIContentService:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else None

    async def generate_post(self, task: str, context: str = "") -> str:
        """Task asosida post yaratish"""
        if not self.client:
            return self._mock_post(task)

        prompt = f"Vazifa: {task}"
        if context:
            prompt += f"\n\nQo'shimcha ma'lumot:\n{context}"

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=600,
                system=CONTENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Post yaratish xatosi: {e}")
            return self._mock_post(task)

    async def answer_master_question(self, question: str) -> str:
        """Usta savoliga javob berish"""
        if not self.client:
            return self._mock_master_answer(question)

        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                system=MASTER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": question}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"AI javob xatosi: {e}")
            return "❌ Hozirda AI xizmat mavjud emas. Iltimos, keyinroq urinib ko'ring."

    async def search_web_context(self, query: str, serp_api_key: str) -> str:
        """SerpAPI orqali ma'lumot yig'ish"""
        if not serp_api_key:
            return ""

        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "q": query,
                    "api_key": serp_api_key,
                    "num": 3,
                    "hl": "uz",
                }
                async with session.get(
                    "https://serpapi.com/search",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("organic_results", [])[:3]
                        context = "\n".join([
                            f"- {r.get('title', '')}: {r.get('snippet', '')}"
                            for r in results
                        ])
                        return context
        except Exception as e:
            logger.warning(f"Web qidirish xatosi: {e}")

        return ""

    async def get_image_url(self, query: str, unsplash_key: str) -> Optional[str]:
        """Unsplash dan rasm URL olish"""
        if not unsplash_key:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "query": f"electricity energy {query}",
                    "per_page": 1,
                    "orientation": "landscape",
                }
                headers = {"Authorization": f"Client-ID {unsplash_key}"}

                async with session.get(
                    "https://api.unsplash.com/search/photos",
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            return results[0]["urls"]["regular"]
        except Exception as e:
            logger.warning(f"Rasm olish xatosi: {e}")

        return None

    def _mock_post(self, task: str) -> str:
        return f"""⚡ **Prime Energy — Yangi Post**

Vazifa: {task}

🔋 Prime Energy — O'zbekistonning ishonchli elektr materiallari yetkazib beruvchisi.

• Yuqori sifatli mahsulotlar
• Tezkor yetkazib berish
• Professional maslahat

📞 Biz bilan bog'laning!
☎️ +998 XX XXX-XX-XX | 🌐 prime-energy.uz

#PrimeEnergy #Elektr #Sifat"""

    def _mock_master_answer(self, question: str) -> str:
        return f"""🔧 Savolingiz qabul qilindi.

Savol: {question}

⚠️ AI xizmati hozirda sozlanmoqda. Iltimos, to'g'ridan-to'g'ri mutaxassis bilan bog'laning.

📞 +998 XX XXX-XX-XX"""
