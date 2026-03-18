from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from models import async_session, User, UserCard, Clan
from keyboards.main_menu import get_tops_menu, get_back_button
from config import EXP_TO_NEXT_BASE, EXP_TO_NEXT_MULTIPLIER, EXP_TO_NEXT_FLAT

router = Router()


def _total_exp(user: User) -> int:
    exp = 0
    exp_to_next = EXP_TO_NEXT_BASE
    for _ in range(1, max(1, int(user.level))):
        exp += exp_to_next
        exp_to_next = int(exp_to_next * EXP_TO_NEXT_MULTIPLIER) + EXP_TO_NEXT_FLAT
    exp += int(user.experience or 0)
    return exp

@router.message(Command("tops"))
async def cmd_tops(message: Message):
    """Команда /tops"""
    await message.answer(
        "🏆 <b>Топы игроков</b>\n\n"
        "Выбери категорию:",
        reply_markup=get_tops_menu(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "tops")
async def tops_callback(callback: CallbackQuery):
    """Меню топов"""
    await callback.message.edit_text(
        "🏆 <b>Топы игроков</b>\n\n"
        "Выбери категорию:",
        reply_markup=get_tops_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "top_level")
async def top_level_callback(callback: CallbackQuery):
    """Топ по уровню"""
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .order_by(desc(User.level), desc(User.experience))
            .limit(10)
        )
        users = result.scalars().all()
        
        top_text = "🏆 <b>Топ игроков по уровню:</b>\n\n"
        
        for i, user in enumerate(users, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            name = user.first_name or user.username or f"Игрок #{user.id}"
            top_text += f"{medal} {name} - Уровень {user.level}\n"
        
        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "top_pvp")
async def top_pvp_callback(callback: CallbackQuery):
    """Топ по PvP"""
    async with async_session() as session:
        # Сортируем по количеству побед
        result = await session.execute(
            select(User)
            .where(User.pvp_wins > 0)
            .order_by(desc(User.pvp_wins), desc(User.pvp_wins / (User.pvp_wins + User.pvp_losses)))
            .limit(10)
        )
        users = result.scalars().all()
        
        top_text = "⚔️ <b>Топ PvP игроков:</b>\n\n"
        
        if not users:
            top_text += "Пока никто не участвовал в PvP боях."
        else:
            for i, user in enumerate(users, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                name = user.first_name or user.username or f"Игрок #{user.id}"
                winrate = user.get_win_rate()
                top_text += f"{medal} {name} - {user.pvp_wins} побед ({winrate}%)\n"
        
        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "top_exp")
async def top_exp_callback(callback: CallbackQuery):
    """Топ по опыту"""
    async with async_session() as session:
        # Рассчитываем общий опыт по новой кривой
        result = await session.execute(
            select(User)
            .order_by(desc(User.level), desc(User.experience))
            .limit(10)
        )
        users = result.scalars().all()
        
        top_text = "⭐ <b>Топ игроков по опыту:</b>\n\n"
        
        for i, user in enumerate(users, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            name = user.first_name or user.username or f"Игрок #{user.id}"
            total_exp = _total_exp(user)
            top_text += f"{medal} {name} - {total_exp} опыта\n"
        
        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "top_power")
async def top_power_callback(callback: CallbackQuery):
    """Топ по силе колоды"""
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.cards).selectinload(UserCard.card_template))
            .limit(50)  # Берем больше для фильтрации
        )
        users = result.scalars().all()
        
        # Считаем силу колоды для каждого
        user_powers = []
        for user in users:
            total_power = 0
            for card in user.cards:
                if card.is_equipped:
                    total_power += card.get_total_power()
            user_powers.append((user, total_power))
        
        # Сортируем по силе
        user_powers.sort(key=lambda x: x[1], reverse=True)
        user_powers = user_powers[:10]
        
        top_text = "💪 <b>Топ игроков по силе колоды:</b>\n\n"
        
        for i, (user, power) in enumerate(user_powers, 1):
            if power == 0:
                continue
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            name = user.first_name or user.username or f"Игрок #{user.id}"
            top_text += f"{medal} {name} - Сила {power}\n"
        
        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "top_clans")
async def top_clans_callback(callback: CallbackQuery):
    """Топ кланов по силе участников"""
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.cards).selectinload(UserCard.card_template))
            .where(User.clan.isnot(None))
        )
        users = result.scalars().all()

        if not users:
            await callback.message.edit_text(
                "🏯 <b>Топ кланов</b>\n\nПока нет созданных кланов.",
                reply_markup=get_back_button("tops"),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        clan_stats: dict[str, dict[str, int]] = {}
        for user in users:
            clan_name = user.clan
            if not clan_name:
                continue
            power = 0
            for card in user.cards:
                if card.is_equipped:
                    power += card.get_total_power()
            stats = clan_stats.setdefault(clan_name, {"power": 0, "members": 0})
            stats["power"] += power
            stats["members"] += 1

        ranking = sorted(clan_stats.items(), key=lambda item: item[1]["power"], reverse=True)[:10]
        clan_names = [name for name, _ in ranking]
        clan_levels = {}
        if clan_names:
            result = await session.execute(
                select(Clan).where(Clan.name.in_(clan_names))
            )
            for clan in result.scalars().all():
                clan_levels[clan.name] = clan.level

        top_text = "🏯 <b>Топ кланов по силе:</b>\n\n"
        for i, (clan_name, stats) in enumerate(ranking, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            level = clan_levels.get(clan_name, 1)
            top_text += (
                f"{medal} {clan_name} — Уровень {level}, Сила {stats['power']} "
                f"(участников {stats['members']})\n"
            )

        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML",
        )
    await callback.answer()
