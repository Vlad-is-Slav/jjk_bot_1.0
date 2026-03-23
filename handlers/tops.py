import html

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, func, desc, case, cast, Integer

from models import async_session, User, UserCard, Clan
from keyboards.main_menu import get_tops_menu, get_back_button
from config import EXP_TO_NEXT_BASE, EXP_TO_NEXT_MULTIPLIER, EXP_TO_NEXT_FLAT

router = Router()
TOP_LIMIT = 10


def _total_exp(user: User) -> int:
    exp = 0
    exp_to_next = EXP_TO_NEXT_BASE
    for _ in range(1, max(1, int(user.level))):
        exp += exp_to_next
        exp_to_next = int(exp_to_next * EXP_TO_NEXT_MULTIPLIER) + EXP_TO_NEXT_FLAT
    exp += int(user.experience or 0)
    return exp


def _rank_badge(position: int) -> str:
    return "🥇" if position == 1 else "🥈" if position == 2 else "🥉" if position == 3 else f"{position}."


def _display_user_name(first_name: str | None, username: str | None, user_id: int) -> str:
    if first_name:
        return html.escape(first_name)
    if username:
        return f"@{html.escape(username)}"
    return f"Игрок #{user_id}"


def _equipped_power_expr():
    return (
        UserCard.attack
        + UserCard.defense
        + UserCard.speed
        + cast(UserCard.max_hp / 10, Integer)
        + cast(UserCard.max_ce / 20, Integer)
    )


@router.message(Command("tops"))
async def cmd_tops(message: Message):
    """Команда /tops"""
    await message.answer(
        "🏆 <b>Топы игроков</b>\n\n"
        "Выбери категорию:",
        reply_markup=get_tops_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "tops")
async def tops_callback(callback: CallbackQuery):
    """Меню топов"""
    await callback.message.edit_text(
        "🏆 <b>Топы игроков</b>\n\n"
        "Выбери категорию:",
        reply_markup=get_tops_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "top_level")
async def top_level_callback(callback: CallbackQuery):
    """Топ по уровню"""
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .order_by(desc(User.level), desc(User.experience), desc(User.id))
            .limit(TOP_LIMIT)
        )
        users = result.scalars().all()

        top_text = "🏆 <b>Топ игроков по уровню:</b>\n\n"
        if not users:
            top_text += "Пока в топе никого нет."
        else:
            for i, user in enumerate(users, 1):
                top_text += f"{_rank_badge(i)} {_display_user_name(user.first_name, user.username, user.id)} - Уровень {user.level}\n"

        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "top_pvp")
async def top_pvp_callback(callback: CallbackQuery):
    """Топ по PvP"""
    async with async_session() as session:
        total_pvp = User.pvp_wins + User.pvp_losses
        winrate_expr = case(
            (total_pvp > 0, (User.pvp_wins * 100.0) / total_pvp),
            else_=0.0,
        )
        result = await session.execute(
            select(User)
            .where(User.pvp_wins > 0)
            .order_by(desc(User.pvp_wins), desc(winrate_expr), desc(User.level), desc(User.id))
            .limit(TOP_LIMIT)
        )
        users = result.scalars().all()

        top_text = "⚔️ <b>Топ PvP игроков:</b>\n\n"
        if not users:
            top_text += "Пока никто не участвовал в PvP боях."
        else:
            for i, user in enumerate(users, 1):
                top_text += (
                    f"{_rank_badge(i)} {_display_user_name(user.first_name, user.username, user.id)} - "
                    f"{user.pvp_wins} побед ({user.get_win_rate()}%)\n"
                )

        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "top_exp")
async def top_exp_callback(callback: CallbackQuery):
    """Топ по опыту"""
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .order_by(desc(User.level), desc(User.experience), desc(User.id))
            .limit(TOP_LIMIT)
        )
        users = result.scalars().all()

        top_text = "⭐ <b>Топ игроков по опыту:</b>\n\n"
        if not users:
            top_text += "Пока в топе никого нет."
        else:
            for i, user in enumerate(users, 1):
                top_text += f"{_rank_badge(i)} {_display_user_name(user.first_name, user.username, user.id)} - {_total_exp(user)} опыта\n"

        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "top_power")
async def top_power_callback(callback: CallbackQuery):
    """Топ по силе колоды"""
    async with async_session() as session:
        power_expr = _equipped_power_expr()
        user_power = (
            select(
                UserCard.user_id.label("user_id"),
                func.coalesce(func.sum(power_expr), 0).label("total_power"),
            )
            .where(UserCard.is_equipped.is_(True))
            .group_by(UserCard.user_id)
            .subquery()
        )
        result = await session.execute(
            select(
                User.id,
                User.first_name,
                User.username,
                User.level,
                User.experience,
                user_power.c.total_power,
            )
            .join(user_power, user_power.c.user_id == User.id)
            .where(user_power.c.total_power > 0)
            .order_by(desc(user_power.c.total_power), desc(User.level), desc(User.experience), desc(User.id))
            .limit(TOP_LIMIT)
        )
        rows = result.all()

        top_text = "💪 <b>Топ игроков по силе колоды:</b>\n\n"
        if not rows:
            top_text += "Пока никто не собрал боевую колоду."
        else:
            for i, row in enumerate(rows, 1):
                top_text += f"{_rank_badge(i)} {_display_user_name(row.first_name, row.username, row.id)} - Сила {int(row.total_power or 0)}\n"

        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "top_clans")
async def top_clans_callback(callback: CallbackQuery):
    """Топ кланов по силе участников"""
    async with async_session() as session:
        power_expr = _equipped_power_expr()
        user_power = (
            select(
                UserCard.user_id.label("user_id"),
                func.coalesce(func.sum(power_expr), 0).label("total_power"),
            )
            .where(UserCard.is_equipped.is_(True))
            .group_by(UserCard.user_id)
            .subquery()
        )
        clan_power = func.coalesce(func.sum(func.coalesce(user_power.c.total_power, 0)), 0).label("clan_power")
        members_count = func.count(func.distinct(User.id)).label("members_count")

        result = await session.execute(
            select(
                User.clan.label("clan_name"),
                func.coalesce(Clan.level, 1).label("clan_level"),
                members_count,
                clan_power,
            )
            .select_from(User)
            .outerjoin(Clan, Clan.name == User.clan)
            .outerjoin(user_power, user_power.c.user_id == User.id)
            .where(User.clan.isnot(None))
            .group_by(User.clan, Clan.level)
            .order_by(desc(clan_power), desc(members_count), User.clan)
            .limit(TOP_LIMIT)
        )
        rows = result.all()

        if not rows:
            await callback.message.edit_text(
                "🏯 <b>Топ кланов</b>\n\nПока нет созданных кланов.",
                reply_markup=get_back_button("tops"),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        top_text = "🏯 <b>Топ кланов по силе:</b>\n\n"
        for i, row in enumerate(rows, 1):
            clan_name = html.escape(row.clan_name or "Безымянный клан")
            top_text += (
                f"{_rank_badge(i)} {clan_name} - Уровень {int(row.clan_level or 1)}, "
                f"Сила {int(row.clan_power or 0)} (участников {int(row.members_count or 0)})\n"
            )

        await callback.message.edit_text(
            top_text,
            reply_markup=get_back_button("tops"),
            parse_mode="HTML",
        )
    await callback.answer()
