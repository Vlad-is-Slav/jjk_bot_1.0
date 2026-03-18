from datetime import datetime, timedelta
import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from models import DailyQuest, DailyReward, User, UserDailyQuest, UserStats, UserCard, UserTechnique, async_session
from utils.card_rewards import grant_random_card
from utils.daily_quest_data import get_random_quests
from utils.pvp_progression import apply_experience_with_pvp_rolls, roll_pvp_technique_drop
from handlers.achievements import check_achievements

router = Router()
MOJIBAKE_MARKERS = set("ЃЉЊЋЏђѓєѕіїјљњћќЎўҐґ�")


def _has_garbled_text(value: str) -> bool:
    if not value:
        return False
    return any(ch in value for ch in MOJIBAKE_MARKERS)


def get_daily_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎁 Ежедневная награда", callback_data="daily_reward"),
                InlineKeyboardButton(text="📋 Задания", callback_data="daily_quests"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ]
    )


@router.message(Command("daily"))
async def cmd_daily(message: Message):
    await message.answer(
        "📅 <b>Ежедневные активности</b>\n\n"
        "Открой награду и задания:",
        reply_markup=get_daily_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "daily_menu")
async def daily_menu_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(DailyReward).where(DailyReward.user_id == user.id)
        )
        daily = result.scalar_one_or_none()

        if not daily:
            daily = DailyReward(user_id=user.id)
            session.add(daily)
            await session.commit()

        can_claim = daily.can_claim()
        reward = daily.get_today_reward()
        status_text = "✅ Доступно" if can_claim else "⏳ Уже забрано"

        menu_text = (
            "📅 <b>Ежедневные награды</b>\n\n"
            f"🔥 Текущий стрик: <b>{daily.current_streak}</b> дней\n"
            f"🏆 Максимальный стрик: <b>{daily.max_streak}</b> дней\n\n"
            f"🎁 <b>Награда сегодня ({reward['name']}):</b>\n"
            f"⭐ Опыт: {reward['exp']}\n"
            f"🪙 Монеты: {reward['coins']}\n"
        )

        if reward.get("card_chance"):
            menu_text += "🎴 Шанс на карту: да\n"

        menu_text += f"\nСтатус: {status_text}"

        if not can_claim and daily.last_claim_date:
            next_claim = daily.last_claim_date + timedelta(days=1)
            time_left = next_claim - datetime.utcnow()
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            menu_text += f"\n\n⏳ Следующая награда через: {hours}ч {minutes}м"

        await callback.message.edit_text(
            menu_text,
            reply_markup=get_daily_menu_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "daily_reward")
async def daily_reward_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(DailyReward).where(DailyReward.user_id == user.id)
        )
        daily = result.scalar_one_or_none()
        if not daily:
            daily = DailyReward(user_id=user.id)
            session.add(daily)
            await session.commit()

        if not daily.can_claim():
            await callback.answer("Награда уже забрана. Приходи завтра.", show_alert=True)
            return

        reward = daily.claim()
        if not reward:
            await callback.answer("Не удалось выдать награду.", show_alert=True)
            return

        _, actual_exp, unlocked_from_level = await apply_experience_with_pvp_rolls(
            session, user, reward["exp"]
        )
        user.coins += reward["coins"]

        card_dropped_name = None
        if reward.get("card_chance") and random.random() < 0.3:
            dropped_card = await grant_random_card(session, user.id, only_characters=False, level=1)
            if dropped_card and dropped_card.card_template:
                card_dropped_name = dropped_card.card_template.name

        await check_achievements(user.id, "daily_streak", value=daily.current_streak, absolute=True, session=session)
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

        result_text = (
            "🎉 <b>Награда получена!</b>\n\n"
            f"⭐ Опыт: +{actual_exp}\n"
            f"🪙 Монеты: +{reward['coins']}\n"
        )

        if card_dropped_name:
            result_text += f"🎴 <b>Выпала карта:</b> {card_dropped_name}\n"

        if unlocked_from_level:
            unlocked_names = ", ".join(t.name for t in unlocked_from_level)
            result_text += f"✨ <b>Новые PvP-техники:</b> {unlocked_names}\n"

        result_text += f"\n🔥 Стрик: {daily.current_streak} дней"
        if daily.current_streak == 7:
            result_text += "\n\n🎊 <b>Поздравляем! 7 дней подряд!</b>"

        await callback.answer(result_text, show_alert=True)
        await daily_menu_callback(callback)


@router.callback_query(F.data == "daily_quests")
async def daily_quests_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(UserDailyQuest)
            .options(selectinload(UserDailyQuest.quest))
            .where(UserDailyQuest.user_id == user.id)
            .order_by(UserDailyQuest.assigned_date.desc())
        )
        existing_quests = result.scalars().all()
        today_quests = [q for q in existing_quests if q.is_today()]
        has_broken_today_quests = any(
            (not q.quest) or _has_garbled_text(q.quest.name) or _has_garbled_text(q.quest.description)
            for q in today_quests
        )

        if has_broken_today_quests:
            for broken in today_quests:
                await session.delete(broken)
            await session.commit()
            today_quests = []

        if not today_quests:
            quests_data = get_random_quests(4)
            for quest_data in quests_data:
                result = await session.execute(
                    select(DailyQuest).where(DailyQuest.name == quest_data["name"])
                )
                quest_template = result.scalar_one_or_none()

                if not quest_template:
                    quest_template = DailyQuest(
                        name=quest_data["name"],
                        description=quest_data["description"],
                        quest_type=quest_data["quest_type"],
                        requirement=quest_data["requirement"],
                        exp_reward=quest_data["exp_reward"],
                        points_reward=quest_data["points_reward"],
                        coins_reward=quest_data["coins_reward"],
                        difficulty=quest_data["difficulty"],
                    )
                    session.add(quest_template)
                    await session.flush()

                session.add(
                    UserDailyQuest(
                        user_id=user.id,
                        quest_id=quest_template.id,
                        progress=0,
                        completed=False,
                        claimed=False,
                        assigned_date=datetime.utcnow(),
                    )
                )

            await session.commit()

            result = await session.execute(
                select(UserDailyQuest)
                .options(selectinload(UserDailyQuest.quest))
                .where(UserDailyQuest.user_id == user.id)
                .order_by(UserDailyQuest.assigned_date.desc())
            )
            today_quests = [q for q in result.scalars().all() if q.is_today()][:4]

        quests_text = "📋 <b>Ежедневные задания</b>\n\n"
        buttons = []

        for i, uq in enumerate(today_quests, 1):
            quest = uq.quest
            status = "✅" if uq.completed else "⏳"
            reward_status = "💰" if uq.completed and not uq.claimed else ""
            difficulty_emoji = {
                "easy": "🟢",
                "medium": "🟡",
                "hard": "🔴",
            }.get(quest.difficulty, "⚪")

            quests_text += (
                f"{i}. {status} {difficulty_emoji} <b>{quest.name}</b> {reward_status}\n"
                f"   {quest.description}\n"
                f"   Прогресс: {uq.progress}/{quest.requirement}\n"
                f"   🎁 Награда: {quest.exp_reward} опыта, {quest.coins_reward} монет\n\n"
            )

            if uq.completed and not uq.claimed:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"💰 Забрать награду: {quest.name[:15]}",
                            callback_data=f"claim_quest_{uq.id}",
                        )
                    ]
                )

        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="daily_menu")])

        await callback.message.edit_text(
            quests_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("claim_quest_"))
async def claim_quest_reward_callback(callback: CallbackQuery):
    quest_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(UserDailyQuest)
            .options(selectinload(UserDailyQuest.quest))
            .where(UserDailyQuest.id == quest_id, UserDailyQuest.user_id == user.id)
        )
        user_quest = result.scalar_one_or_none()

        if not user_quest:
            await callback.answer("Задание не найдено.", show_alert=True)
            return
        if not user_quest.completed:
            await callback.answer("Задание еще не выполнено.", show_alert=True)
            return
        if user_quest.claimed:
            await callback.answer("Награда уже забрана.", show_alert=True)
            return

        quest = user_quest.quest
        _, actual_exp, unlocked_from_level = await apply_experience_with_pvp_rolls(
            session, user, quest.exp_reward
        )
        unlocked_from_quest = await roll_pvp_technique_drop(
            session, user, source="quest", attempts=1
        )
        user.coins += quest.coins_reward
        user_quest.claimed = True
        user_quest.completed_at = datetime.utcnow()

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

        unlocked_all = unlocked_from_level + unlocked_from_quest
        unlocked_part = ""
        if unlocked_all:
            unlocked_names = ", ".join(t.name for t in unlocked_all)
            unlocked_part = f"\n\n✨ Новые PvP-техники: {unlocked_names}"

        await callback.answer(
            "🎉 Награда получена!\n\n"
            f"⭐ Опыт: +{actual_exp}\n"
            f"🪙 Монеты: +{quest.coins_reward}"
            f"{unlocked_part}",
            show_alert=True,
        )

        await daily_quests_callback(callback)
