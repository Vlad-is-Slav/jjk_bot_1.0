from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime

from models import async_session, User, PromoCode, UserPromoCode, Technique, UserTechnique, UserCard
from utils.technique_data import ALL_TECHNIQUES
from utils.pvp_progression import apply_experience_with_pvp_rolls
from utils.card_rewards import get_card_data_by_name, grant_card_to_user
from handlers.achievements import check_achievements

router = Router()
ADMIN_ID = 1296861067

@router.message(Command("promo"))
async def cmd_promo(message: Message):
    """Использовать промокод"""
    args = message.text.split()[1:]
    
    if not args:
        await message.answer(
            "🎁 <b>Промокоды</b>\n\n"
            "Использование:\n"
            "<code>/promo КОД</code>\n\n"
            "Введи промокод, чтобы получить награду!",
            parse_mode="HTML"
        )
        return
    
    code = args[0].upper()
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Сначала используй /start")
            return
        
        # Ищем промокод
        result = await session.execute(
            select(PromoCode).where(
                PromoCode.code == code,
                PromoCode.is_active == True
            )
        )
        promo = result.scalar_one_or_none()
        
        if not promo:
            await message.answer(
                "❌ <b>Промокод не найден или истек!</b>\n\n"
                "Проверь правильность ввода.",
                parse_mode="HTML"
            )
            return
        
        # Проверяем срок действия
        if promo.expires_at and promo.expires_at < datetime.utcnow():
            await message.answer(
                "❌ <b>Промокод истек!</b>\n\n"
                "Этот код больше не действителен.",
                parse_mode="HTML"
            )
            return
        
        # Проверяем количество использований
        if promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
            await message.answer(
                "❌ <b>Промокод исчерпан!</b>\n\n"
                "Достигнут лимит использований.",
                parse_mode="HTML"
            )
            return
        
        # Проверяем, использовал ли пользователь
        result = await session.execute(
            select(UserPromoCode).where(
                UserPromoCode.user_id == user.id,
                UserPromoCode.promo_code_id == promo.id
            )
        )
        used = result.scalar_one_or_none()
        
        if used:
            await message.answer(
                "❌ <b>Ты уже использовал этот промокод!</b>\n\n"
                "Каждый код можно использовать только один раз.",
                parse_mode="HTML"
            )
            return
        
        # Выдаем награды
        reward_text = f"🎉 <b>Промокод активирован!</b>\n\n"
        reward_text += f"<i>{promo.description or 'Награды:'}</i>\n\n"
        
        unlocked_from_level = []
        if promo.exp_reward > 0:
            _, actual_exp, unlocked_from_level = await apply_experience_with_pvp_rolls(
                session, user, promo.exp_reward
            )
            reward_text += f"⭐ Опыт: +{actual_exp}\n"
        
        if promo.coins_reward > 0:
            user.coins += promo.coins_reward
            reward_text += f"🪙 Монеты: +{promo.coins_reward}\n"
        
        # Карта
        if promo.card_reward:
            card_data = get_card_data_by_name(promo.card_reward)
            
            if card_data:
                await grant_card_to_user(session, user.id, card_data, level=1)
                reward_text += f"🎴 Карта: <b>{card_data['name']}</b>\n"
        
        # Техника
        if promo.technique_reward:
            tech_data = None
            for t in ALL_TECHNIQUES:
                if t["name"] == promo.technique_reward:
                    tech_data = t
                    break
            
            if tech_data:
                result = await session.execute(
                    select(Technique).where(Technique.name == tech_data["name"])
                )
                tech_template = result.scalar_one_or_none()
                
                if not tech_template:
                    tech_template = Technique(
                        name=tech_data["name"],
                        description=tech_data["description"],
                        technique_type=tech_data["technique_type"],
                        ce_cost=tech_data.get("ce_cost", 0),
                        effect_type=tech_data.get("effect_type"),
                        effect_value=tech_data.get("effect_value", 0),
                        icon=tech_data["icon"],
                        rarity=tech_data["rarity"]
                    )
                    session.add(tech_template)
                    await session.flush()
                
                user_tech = UserTechnique(
                    user_id=user.id,
                    technique_id=tech_template.id,
                    level=1,
                    is_equipped=False
                )
                session.add(user_tech)
                
                reward_text += f"✨ Техника: <b>{tech_data['name']}</b>\n"
        
        # Записываем использование
        usage = UserPromoCode(
            user_id=user.id,
            promo_code_id=promo.id
        )
        session.add(usage)
        
        # Увеличиваем счетчик
        promo.current_uses += 1
        
        await check_achievements(user.id, "level", value=user.level, absolute=True, session=session)
        if user.hardcore_mode:
            await check_achievements(user.id, "hardcore_level", value=user.level, absolute=True, session=session)

        result = await session.execute(
            select(func.count(UserTechnique.id)).where(UserTechnique.user_id == user.id)
        )
        technique_count = int(result.scalar() or 0)
        await check_achievements(user.id, "techniques_obtained", value=technique_count, absolute=True, session=session)

        result = await session.execute(
            select(func.count(UserCard.id)).where(UserCard.user_id == user.id)
        )
        card_count = int(result.scalar() or 0)
        await check_achievements(user.id, "cards_collected", value=card_count, absolute=True, session=session)

        await check_achievements(user.id, "coins_collected", value=user.coins, absolute=True, session=session)
        await session.commit()
        
        if unlocked_from_level:
            unlocked_names = ", ".join(t.name for t in unlocked_from_level)
            reward_text += f"\n✨ Новые PvP-техники: {unlocked_names}\n"
        
        reward_text += "\n✅ <b>Награды начислены!</b>"
        
        await message.answer(reward_text, parse_mode="HTML")


# Админ команда для создания промокода
@router.message(Command("createpromo"))
async def cmd_create_promo(message: Message):
    """Создать промокод (только для админов)"""
    args = message.text.split()[1:]
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if message.from_user.id != ADMIN_ID and (not user or not user.is_admin):
            await message.answer("❌ У тебя нет прав для этой команды!")
            return
        
        if len(args) < 2:
            await message.answer(
                "🎁 <b>Создание промокода</b>\n\n"
                "Использование:\n"
                "<code>/createpromo КОД ОПИСАНИЕ [награды...]</code>\n\n"
                "Примеры:\n"
                "<code>/createpromo STARTER 'Стартовый бонус' exp=100 coins=500</code>\n"
                "<code>/createpromo LEGENDARY 'Легендарная карта' card=Годжо_Сатору</code>\n"
                "<code>/createpromo TECH 'Техника' technique=Красный</code>\n\n"
                "Параметры:\n"
                "- exp=N - опыт\n"
                "- points=N - очки\n"
                "- coins=N - монеты\n"
                "- card=НАЗВАНИЕ - карта\n"
                "- technique=НАЗВАНИЕ - техника\n"
                "- uses=N - количество использований (по умолчанию 1)\n"
                "- days=N - срок действия в днях",
                parse_mode="HTML"
            )
            return
        
        code = args[0].upper()
        description = args[1]
        
        # Парсим параметры
        exp_reward = 0
        points_reward = 0
        coins_reward = 0
        card_reward = None
        technique_reward = None
        max_uses = 1
        days_valid = 7
        
        for arg in args[2:]:
            if arg.startswith("exp="):
                exp_reward = int(arg.split("=")[1])
            elif arg.startswith("points="):
                points_reward = int(arg.split("=")[1])
            elif arg.startswith("coins="):
                coins_reward = int(arg.split("=")[1])
            elif arg.startswith("card="):
                card_reward = arg.split("=")[1].replace("_", " ")
            elif arg.startswith("technique="):
                technique_reward = arg.split("=")[1].replace("_", " ")
            elif arg.startswith("uses="):
                max_uses = int(arg.split("=")[1])
            elif arg.startswith("days="):
                days_valid = int(arg.split("=")[1])
        
        # Проверяем, существует ли код
        result = await session.execute(
            select(PromoCode).where(PromoCode.code == code)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            await message.answer(f"❌ Промокод '{code}' уже существует!")
            return
        
        # Создаем промокод
        expires_at = datetime.utcnow() + timedelta(days=days_valid) if days_valid > 0 else None
        
        promo = PromoCode(
            code=code,
            description=description,
            exp_reward=exp_reward,
            points_reward=points_reward,
            coins_reward=coins_reward,
            card_reward=card_reward,
            technique_reward=technique_reward,
            max_uses=max_uses,
            expires_at=expires_at,
            is_active=True
        )
        session.add(promo)
        await session.commit()
        
        await message.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"Код: <code>{code}</code>\n"
            f"Описание: {description}\n"
            f"Использований: {max_uses}\n"
            f"Срок: {days_valid} дней\n\n"
            f"Награды:\n"
            f"⭐ {exp_reward} опыта\n"
            f"💎 {points_reward} очков\n"
            f"🪙 {coins_reward} монет\n"
            f"🎴 Карта: {card_reward or 'Нет'}\n"
            f"✨ Техника: {technique_reward or 'Нет'}",
            parse_mode="HTML"
        )


from datetime import timedelta
