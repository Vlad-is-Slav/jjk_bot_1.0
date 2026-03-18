import html
import random
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from models import (
    async_session,
    User,
    UserCard,
    UserTechnique,
    CampaignSeason,
    CampaignLevel,
    UserCampaignProgress,
)
from utils.campaign_data import CAMPAIGN_SEASONS, get_season_levels
from utils.card_rewards import get_card_data_by_name, grant_card_to_user
from utils.daily_quest_progress import add_daily_quest_progress
from utils.pvp_progression import apply_experience_with_pvp_rolls
from handlers.achievements import check_achievements

router = Router()


def _campaign_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Открыть кампанию", callback_data="campaign")]
        ]
    )


async def _safe_edit_message(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        try:
            await callback.bot.send_message(
                callback.from_user.id,
                text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        except Exception:
            pass


async def _sync_campaign_templates(session):
    """Create/update campaign templates to overwrite old corrupted text in DB."""
    for season_data in CAMPAIGN_SEASONS:
        result = await session.execute(
            select(CampaignSeason).where(CampaignSeason.season_number == season_data["season_number"])
        )
        season = result.scalar_one_or_none()
        if not season:
            season = CampaignSeason(season_number=season_data["season_number"])
            session.add(season)
            await session.flush()

        season.name = season_data["name"]
        season.description = season_data["description"]
        season.required_level = season_data["required_level"]
        season.exp_reward = season_data["exp_reward"]
        season.points_reward = season_data["points_reward"]
        season.card_reward = season_data.get("card_reward")
        season.is_active = True
        await session.flush()

        levels_data = get_season_levels(season_data["season_number"])
        result = await session.execute(
            select(CampaignLevel).where(CampaignLevel.season_id == season.id)
        )
        existing_level_rows = result.scalars().all()
        grouped = {}
        for lvl in existing_level_rows:
            grouped.setdefault(lvl.level_number, []).append(lvl)

        existing_levels = {}
        for level_number, rows in grouped.items():
            rows_sorted = sorted(rows, key=lambda row: row.id)
            existing_levels[level_number] = rows_sorted[0]
            for duplicate in rows_sorted[1:]:
                await session.delete(duplicate)

        for idx, level_data in enumerate(levels_data, start=1):
            level = existing_levels.get(idx)
            if not level:
                level = CampaignLevel(season_id=season.id, level_number=idx)
                session.add(level)

            level.name = level_data["name"]
            level.description = level_data["description"]
            level.level_type = level_data["level_type"]
            level.enemy_name = level_data.get("enemy_name")
            level.enemy_attack = level_data.get("enemy_attack", 10)
            level.enemy_defense = level_data.get("enemy_defense", 10)
            level.enemy_speed = level_data.get("enemy_speed", 10)
            level.enemy_hp = level_data.get("enemy_hp", 100)
            level.exp_reward = level_data["exp_reward"]
            level.points_reward = level_data["points_reward"]
            level.coins_reward = level_data["coins_reward"]
            level.card_drop_chance = level_data.get("card_drop_chance", 0)
            level.card_drop_name = level_data.get("card_drop_name")

    await session.commit()


@router.message(Command("campaign"))
async def cmd_campaign(message: Message):
    await message.answer(
        "📖 <b>Сюжетная кампания</b>\n\n"
        "Нажми кнопку ниже, чтобы открыть кампанию.",
        reply_markup=_campaign_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "campaign")
async def campaign_menu_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        await _sync_campaign_templates(session)

        result = await session.execute(
            select(CampaignSeason)
            .options(selectinload(CampaignSeason.levels))
            .order_by(CampaignSeason.season_number)
        )
        seasons = result.scalars().all()

        result = await session.execute(
            select(UserCampaignProgress).where(UserCampaignProgress.user_id == user.id)
        )
        completed_level_ids = {p.level_id for p in result.scalars().all() if p.completed}

        text = (
            f"📖 <b>Сюжетная кампания</b>\n\n"
            f"👤 Твой уровень: <b>{user.level}</b>\n\n"
            "<b>Доступные сезоны:</b>\n\n"
        )
        buttons = []

        for season in seasons:
            season_levels = list(season.levels)
            completed_in_season = len([lvl for lvl in season_levels if lvl.id in completed_level_ids])
            total_in_season = len(season_levels)

            if user.level >= season.required_level:
                icon = "✅" if total_in_season > 0 and completed_in_season == total_in_season else "🟢"
                text += (
                    f"{icon} <b>{html.escape(season.name)}</b>\n"
                    f"   Прогресс: {completed_in_season}/{total_in_season}\n"
                )
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"▶️ {season.name[:24]}",
                            callback_data=f"season_{season.id}",
                        )
                    ]
                )
            else:
                text += (
                    f"🔒 <b>{html.escape(season.name)}</b> "
                    f"(нужен уровень {season.required_level})\n"
                )

        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
        await _safe_edit_message(
            callback,
            text,
            InlineKeyboardMarkup(inline_keyboard=buttons),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("season_"))
async def season_detail_callback(callback: CallbackQuery):
    season_id = int(callback.data.split("_")[1])

    async with async_session() as session:
        result = await session.execute(
            select(CampaignSeason)
            .options(selectinload(CampaignSeason.levels))
            .where(CampaignSeason.id == season_id)
        )
        season = result.scalar_one_or_none()
        if not season:
            await callback.answer("Сезон не найден.", show_alert=True)
            return

        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        if user.level < season.required_level:
            await callback.answer(
                f"Нужен уровень {season.required_level} для этого сезона.",
                show_alert=True,
            )
            return

        result = await session.execute(
            select(UserCampaignProgress)
            .where(UserCampaignProgress.user_id == user.id)
        )
        progress_map = {p.level_id: p for p in result.scalars().all()}

        levels_sorted = sorted(season.levels, key=lambda lvl: lvl.level_number)
        text = (
            f"📚 <b>{html.escape(season.name)}</b>\n\n"
            f"<i>{html.escape(season.description or '')}</i>\n\n"
            "🎁 Награда за сезон:\n"
            f"⭐ {season.exp_reward} опыта\n"
        )
        if season.card_reward:
            text += f"🎴 Карта: {html.escape(season.card_reward)}\n"

        text += "\n<b>Уровни:</b>\n"
        buttons = []

        for level in levels_sorted:
            level_progress = progress_map.get(level.id)
            completed = bool(level_progress and level_progress.completed)
            prev_levels = [lv for lv in levels_sorted if lv.level_number < level.level_number]
            unlocked = level.level_number == 1 or all(
                progress_map.get(prev.id) and progress_map[prev.id].completed for prev in prev_levels
            )

            if completed:
                status = "✅"
            elif unlocked:
                status = "🟢"
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"▶️ {level.level_number}. {level.name[:22]}",
                            callback_data=f"campaign_level_{level.id}",
                        )
                    ]
                )
            else:
                status = "🔒"

            text += f"{status} {level.level_number}. {html.escape(level.name)}\n"

        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="campaign")])
        await _safe_edit_message(
            callback,
            text,
            InlineKeyboardMarkup(inline_keyboard=buttons),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("campaign_level_"))
async def campaign_level_callback(callback: CallbackQuery):
    level_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        result = await session.execute(
            select(CampaignLevel)
            .options(selectinload(CampaignLevel.season).selectinload(CampaignSeason.levels))
            .where(CampaignLevel.id == level_id)
        )
        level = result.scalar_one_or_none()
        if not level:
            await callback.answer("Уровень не найден.", show_alert=True)
            return

        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == user.slot_1_card_id, UserCard.user_id == user.id)
        )
        main_card = result.scalar_one_or_none()
        if not main_card or not main_card.card_template:
            await callback.answer("Экипируй главную карту перед боем.", show_alert=True)
            return

        season_levels = sorted(level.season.levels, key=lambda lvl: lvl.level_number)
        result = await session.execute(
            select(UserCampaignProgress)
            .where(UserCampaignProgress.user_id == user.id)
        )
        progress_map = {p.level_id: p for p in result.scalars().all()}

        prev_levels = [lv for lv in season_levels if lv.level_number < level.level_number]
        unlocked = level.level_number == 1 or all(
            progress_map.get(prev.id) and progress_map[prev.id].completed for prev in prev_levels
        )
        if not unlocked:
            await callback.answer("Сначала пройди предыдущие уровни сезона.", show_alert=True)
            return

        # Simple auto-battle for campaign encounter.
        player_hp = main_card.max_hp
        enemy_hp = level.enemy_hp
        player_speed = main_card.speed
        enemy_speed = level.enemy_speed

        while player_hp > 0 and enemy_hp > 0:
            if player_speed >= enemy_speed:
                enemy_hp -= max(1, main_card.attack - level.enemy_defense // 2)
                if enemy_hp <= 0:
                    break
                player_hp -= max(1, level.enemy_attack - main_card.defense // 2)
            else:
                player_hp -= max(1, level.enemy_attack - main_card.defense // 2)
                if player_hp <= 0:
                    break
                enemy_hp -= max(1, main_card.attack - level.enemy_defense // 2)

        won = player_hp > 0

        result = await session.execute(
            select(UserCampaignProgress).where(
                UserCampaignProgress.user_id == user.id,
                UserCampaignProgress.level_id == level.id,
            )
        )
        progress = result.scalar_one_or_none()
        if not progress:
            progress = UserCampaignProgress(user_id=user.id, level_id=level.id)
            session.add(progress)

        progress.attempts = int(progress.attempts or 0) + 1

        level_exp = 0
        level_points = 0
        level_coins = 0
        season_exp = 0
        season_points = 0
        dropped_card_name = None
        season_card_name = None
        unlocked_techniques = []
        season_completed_now = False
        sukuna_defeated = False

        if won:
            completed_before = {lid for lid, p in progress_map.items() if p.completed}
            first_clear = not progress.completed
            if first_clear:
                progress.completed = True
                progress.completed_at = datetime.utcnow()
                completed_after = set(completed_before)
                completed_after.add(level.id)
            else:
                completed_after = completed_before

            # Reward every victory (fixes "reward not credited"), first clear is still tracked separately.
            _, level_exp, unlocked_from_level = await apply_experience_with_pvp_rolls(
                session, user, int(level.exp_reward)
            )
            unlocked_techniques.extend(unlocked_from_level)
            level_points = 0
            level_coins = int(level.coins_reward)
            user.coins += level_coins

            await add_daily_quest_progress(session, user.id, "campaign_levels", amount=1)

            if level.card_drop_name and random.random() * 100 < float(level.card_drop_chance or 0):
                card_data = get_card_data_by_name(level.card_drop_name)
                if card_data:
                    await grant_card_to_user(session, user.id, card_data, level=1)
                    dropped_card_name = level.card_drop_name

            season_level_ids = [lvl.id for lvl in season_levels]
            was_complete_before = all(lid in completed_before for lid in season_level_ids)
            is_complete_after = all(lid in completed_after for lid in season_level_ids)
            season_completed_now = is_complete_after and not was_complete_before

            if season_completed_now:
                _, season_exp, unlocked_from_season = await apply_experience_with_pvp_rolls(
                    session, user, int(level.season.exp_reward)
                )
                unlocked_techniques.extend(unlocked_from_season)
                season_points = 0

                if level.season.card_reward:
                    season_card_data = get_card_data_by_name(level.season.card_reward)
                    if season_card_data:
                        await grant_card_to_user(session, user.id, season_card_data, level=1)
                        season_card_name = level.season.card_reward

        if won and level.season and level.season.season_number == 7:
            last_level = max((lvl.level_number for lvl in season_levels), default=level.level_number)
            if level.level_number == last_level:
                sukuna_defeated = True

        if won and season_completed_now:
            await check_achievements(user.id, "campaign_seasons", value=1, session=session)
        if won and sukuna_defeated:
            await check_achievements(user.id, "sukuna_defeated", value=1, session=session)

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

        if won:
            text = (
                "🏆 <b>Победа!</b>\n\n"
                f"Ты победил <b>{html.escape(level.enemy_name or 'врага')}</b>.\n\n"
                f"⭐ Опыт: +{level_exp}\n"
                f"🪙 Монеты: +{level_coins}\n"
            )
            if dropped_card_name:
                text += f"🎴 Дроп карты: <b>{html.escape(dropped_card_name)}</b>\n"
            if season_completed_now:
                text += (
                    f"\n🎉 <b>Сезон «{html.escape(level.season.name)}» пройден!</b>\n"
                    f"⭐ Бонус опыта: +{season_exp}\n"
                )
                if season_card_name:
                    text += f"🎴 Карта за сезон: <b>{html.escape(season_card_name)}</b>\n"
            if unlocked_techniques:
                names = ", ".join(sorted({tech.name for tech in unlocked_techniques}))
                text += f"\n✨ Новые PvP-техники: {html.escape(names)}\n"
        else:
            text = (
                "💀 <b>Поражение</b>\n\n"
                f"{html.escape(level.enemy_name or 'Враг')} оказался сильнее.\n"
                "Прокачай карты и попробуй снова."
            )

        text += f"\n\n📊 Попыток на уровне: {progress.attempts}"

        await _safe_edit_message(
            callback,
            text,
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📚 К сезону", callback_data=f"season_{level.season_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ]
            ),
        )
    await callback.answer()
