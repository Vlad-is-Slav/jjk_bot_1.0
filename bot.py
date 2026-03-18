"""
Главный файл бота Jujutsu Battle
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from sqlalchemy import select

from config import ADMIN_IDS as CONFIG_ADMIN_IDS, BOT_TOKEN, EXP_PER_MESSAGE, EXP_COOLDOWN, POINTS_PER_LEVEL_UP
from models import init_db, async_session, User
from utils.card_rewards import sync_card_templates
from handlers import (
    start_router,
    profile_router,
    inventory_router,
    battle_router,
    pve_router,
    pvp_router,
    coop_pvp_router,
    tops_router,
    friends_router,
    daily_router,
    achievements_router,
    campaign_router,
    academy_router,
    promocode_router,
    admin_router,
    market_router,
    clans_router
)
from handlers.achievements import _ensure_achievement_templates
from handlers.campaign import _sync_campaign_templates

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище кулдаунов для опыта
exp_cooldowns = {}

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ADMIN_BYPASS_IDS = set(CONFIG_ADMIN_IDS + [1296861067])


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        if not from_user:
            return await handler(event, data)

        telegram_id = int(from_user.id)
        if telegram_id in ADMIN_BYPASS_IDS:
            return await handler(event, data)

        async with async_session() as session:
            result = await session.execute(
                select(User.is_banned, User.is_admin).where(User.telegram_id == telegram_id)
            )
            row = result.first()

        if not row:
            return await handler(event, data)

        is_banned, is_admin = bool(row[0]), bool(row[1])
        if is_admin or not is_banned:
            return await handler(event, data)

        text = "🚫 Твой доступ к боту ограничен администрацией."
        if isinstance(event, Message):
            await event.answer(text)
            return None

        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
            return None

        return None


ban_middleware = BanMiddleware()
dp.message.middleware(ban_middleware)
dp.callback_query.middleware(ban_middleware)

# Подключаем роутеры
dp.include_router(start_router)
dp.include_router(profile_router)
dp.include_router(inventory_router)
dp.include_router(battle_router)
dp.include_router(pve_router)
dp.include_router(pvp_router)
dp.include_router(coop_pvp_router)
dp.include_router(tops_router)
dp.include_router(friends_router)
dp.include_router(daily_router)
dp.include_router(achievements_router)
dp.include_router(campaign_router)
dp.include_router(academy_router)
dp.include_router(promocode_router)
dp.include_router(admin_router)
dp.include_router(market_router)
dp.include_router(clans_router)

async def main():
    """Главная функция"""
    # Инициализируем БД
    await init_db()
    logger.info("Database initialized")

    # Синхронизируем шаблоны карт, чтобы исправить битые имена/типы
    async with async_session() as session:
        await sync_card_templates(session)
        await _ensure_achievement_templates(session)
        await _sync_campaign_templates(session)
        await session.commit()
    
    # Удаляем вебхук и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
