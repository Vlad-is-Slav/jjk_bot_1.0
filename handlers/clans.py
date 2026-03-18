from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from models import async_session, User, Clan
from keyboards.clans import get_clans_menu_keyboard
from utils.clans import get_clan_label
from utils.clan_progression import (
    CLAN_DAILY_QUESTS,
    clan_bonuses_for_level,
    get_or_create_clan,
    get_or_create_clan_daily,
)

router = Router()

CLAN_INPUT_TIMEOUT = timedelta(minutes=5)
clan_create_input: dict[int, datetime] = {}
clan_invite_input: dict[int, datetime] = {}
clan_pending_invites: dict[int, dict] = {}


def _display_user_name(user: User) -> str:
    return user.first_name or user.username or f"ID {user.telegram_id}"


def _normalize_clan_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def _valid_clan_name(value: str) -> bool:
    length = len(value)
    return 3 <= length <= 30


async def _find_user_by_target(session, target_raw: str) -> User | None:
    raw = (target_raw or "").strip()
    if not raw:
        return None

    if raw.startswith("@"):
        username = raw[1:].strip().lower()
        if not username:
            return None
        result = await session.execute(
            select(User).where(func.lower(User.username) == username)
        )
        return result.scalar_one_or_none()

    if raw.isdigit():
        result = await session.execute(
            select(User).where(User.telegram_id == int(raw))
        )
        return result.scalar_one_or_none()

    result = await session.execute(
        select(User).where(func.lower(User.username) == raw.lower())
    )
    return result.scalar_one_or_none()


async def _clan_member_count(session, clan_name: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(User.clan == clan_name)
    )
    return int(result.scalar_one() or 0)


@router.callback_query(F.data == "clans_menu")
async def clans_menu_callback(callback: CallbackQuery):
    clan_create_input.pop(callback.from_user.id, None)
    clan_invite_input.pop(callback.from_user.id, None)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        clan_label = get_clan_label(user.clan)
        has_invite = callback.from_user.id in clan_pending_invites
        text = "🏯 <b>Кланы</b>\n\n"

        if user.clan:
            clan = await get_or_create_clan(session, user.clan)
            members = await _clan_member_count(session, user.clan)
            bonus = clan_bonuses_for_level(clan.level)
            attack_pct = int((bonus.get("attack_mult", 1.0) - 1.0) * 100)
            ce_pct = int((bonus.get("ce_regen_mult", 1.0) - 1.0) * 100)
            text += (
                f"Твой клан: <b>{clan_label}</b>\n"
                f"Уровень: <b>{clan.level}</b> | Опыт: <b>{clan.exp}/{clan.exp_to_next}</b>\n"
                f"Участников: <b>{members}</b>\n"
                f"Бонусы клана: <b>+{attack_pct}% урон</b>, <b>+{ce_pct}% реген CE</b>\n"
            )

            today = datetime.utcnow().strftime("%Y-%m-%d")
            daily = await get_or_create_clan_daily(session, user.clan, today)
            text += "\n<b>Задания клана на сегодня:</b>\n"
            for key, quest in CLAN_DAILY_QUESTS.items():
                progress = getattr(daily, key)
                target = quest["target"]
                done = "✅" if progress >= target else ""
                text += f"• {quest['label']}: {progress}/{target} {done}\n"
        else:
            text += "Ты пока без клана. Создай свой или прими приглашение.\n"
            if has_invite:
                text += "📩 У тебя есть приглашение в клан.\n"

        await callback.message.edit_text(
            text,
            reply_markup=get_clans_menu_keyboard(in_clan=bool(user.clan), has_invite=has_invite),
            parse_mode="HTML",
        )

    await callback.answer()


@router.callback_query(F.data == "clan_create")
async def clan_create_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        if user.clan:
            await callback.answer("Сначала выйди из текущего клана.", show_alert=True)
            return

        clan_create_input[callback.from_user.id] = datetime.utcnow()

        await callback.message.edit_text(
            "➕ <b>Создание клана</b>\n\n"
            "Отправь название клана (3-30 символов).\n"
            "Пример: Tokyo Jujutsu\n\n"
            "Чтобы отменить, нажми «Назад».",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")]
            ]),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("clan_join_"))
async def clan_legacy_join_callback(callback: CallbackQuery):
    await callback.answer("Система кланов обновлена. Создай свой клан или прими приглашение.", show_alert=True)
    await clans_menu_callback(callback)


@router.callback_query(F.data == "clan_invite")
async def clan_invite_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        if not user.clan:
            await callback.answer("Сначала вступи в клан или создай его.", show_alert=True)
            return

        clan_invite_input[callback.from_user.id] = datetime.utcnow()

        await callback.message.edit_text(
            "📨 <b>Пригласить в клан</b>\n\n"
            "Отправь @username или telegram_id игрока, которого хочешь пригласить.\n\n"
            "Чтобы отменить, нажми «Назад».",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")]
            ]),
            parse_mode="HTML",
        )
    await callback.answer()


@router.message(
    F.text,
    ~F.text.startswith("/"),
    lambda message: message.from_user.id in clan_create_input
    or message.from_user.id in clan_invite_input,
)
async def clan_text_input_handler(message: Message):
    user_tg = message.from_user.id
    now = datetime.utcnow()

    if user_tg in clan_create_input:
        if now - clan_create_input.get(user_tg, now) > CLAN_INPUT_TIMEOUT:
            clan_create_input.pop(user_tg, None)
            return

        raw_name = _normalize_clan_name(message.text or "")
        if not _valid_clan_name(raw_name):
            await message.answer("Название должно быть от 3 до 30 символов.")
            return

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_tg)
            )
            user = result.scalar_one_or_none()
            if not user:
                clan_create_input.pop(user_tg, None)
                await message.answer("Сначала используй /start.")
                return
            if user.clan:
                clan_create_input.pop(user_tg, None)
                await message.answer("Сначала выйди из текущего клана.")
                return

            result = await session.execute(
                select(Clan).where(func.lower(Clan.name) == raw_name.lower())
            )
            exists = result.scalar_one_or_none()
            if exists:
                await message.answer("Клан с таким названием уже существует. Попробуй другое.")
                return

            await get_or_create_clan(session, raw_name, owner_id=user.id)
            user.clan = raw_name
            user.clan_joined_at = datetime.utcnow()
            await session.commit()

        clan_create_input.pop(user_tg, None)
        await message.answer(f"✅ Клан «{raw_name}» создан!")
        return

    if user_tg in clan_invite_input:
        if now - clan_invite_input.get(user_tg, now) > CLAN_INPUT_TIMEOUT:
            clan_invite_input.pop(user_tg, None)
            return

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_tg)
            )
            inviter = result.scalar_one_or_none()
            if not inviter:
                clan_invite_input.pop(user_tg, None)
                await message.answer("Сначала используй /start.")
                return
            if not inviter.clan:
                clan_invite_input.pop(user_tg, None)
                await message.answer("Сначала вступи в клан или создай его.")
                return

            target = await _find_user_by_target(session, message.text or "")
            if not target:
                await message.answer("Игрок не найден. Укажи @username или telegram_id.")
                return
            if target.telegram_id == inviter.telegram_id:
                await message.answer("Нельзя пригласить самого себя.")
                return
            if target.clan:
                await message.answer("Игрок уже состоит в клане.")
                return

            clan_pending_invites[target.telegram_id] = {
                "clan": inviter.clan,
                "inviter_tg": inviter.telegram_id,
                "created_at": datetime.utcnow(),
            }

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Вступить", callback_data="clan_invite_accept"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data="clan_invite_decline"),
                ]
            ])

            inviter_name = _display_user_name(inviter)
            try:
                await message.bot.send_message(
                    target.telegram_id,
                    "🏯 <b>Приглашение в клан</b>\n\n"
                    f"Тебя приглашает: <b>{inviter_name}</b>\n"
                    f"Клан: <b>{inviter.clan}</b>\n\n"
                    "Принять приглашение?",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except Exception:
                clan_pending_invites.pop(target.telegram_id, None)
                await message.answer("Не удалось отправить приглашение. Возможно, игрок не писал боту.")
                return

        clan_invite_input.pop(user_tg, None)
        await message.answer("✅ Приглашение отправлено.")
        return


@router.callback_query(F.data == "clan_invite_open")
async def clan_invite_open_callback(callback: CallbackQuery):
    invite = clan_pending_invites.get(callback.from_user.id)
    if not invite:
        await callback.answer("Активных приглашений нет.", show_alert=True)
        return

    inviter_name = "Игрок"
    inviter_tg = invite.get("inviter_tg")
    if inviter_tg:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == inviter_tg)
            )
            inviter = result.scalar_one_or_none()
            if inviter:
                inviter_name = _display_user_name(inviter)

    clan_name = invite.get("clan", "—")
    await callback.message.edit_text(
        "🏯 <b>Приглашение в клан</b>\n\n"
        f"Клан: <b>{clan_name}</b>\n"
        f"Пригласил: <b>{inviter_name}</b>\n\n"
        "Принять приглашение?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Вступить", callback_data="clan_invite_accept"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data="clan_invite_decline"),
            ]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data == "clan_invite_accept")
async def clan_invite_accept_callback(callback: CallbackQuery):
    invite = clan_pending_invites.get(callback.from_user.id)
    if not invite:
        await callback.answer("Приглашение не найдено.", show_alert=True)
        return

    if datetime.utcnow() - invite.get("created_at", datetime.utcnow()) > CLAN_INPUT_TIMEOUT:
        clan_pending_invites.pop(callback.from_user.id, None)
        await callback.answer("Приглашение истекло.", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        if user.clan:
            await callback.answer("Ты уже в клане.", show_alert=True)
            return

        clan_name = invite.get("clan")
        if not clan_name:
            await callback.answer("Приглашение некорректно.", show_alert=True)
            return

        await get_or_create_clan(session, clan_name)

        user.clan = clan_name
        user.clan_joined_at = datetime.utcnow()
        await session.commit()

    clan_pending_invites.pop(callback.from_user.id, None)
    await callback.answer("Ты вступил в клан!", show_alert=True)

    inviter_tg = invite.get("inviter_tg")
    if inviter_tg:
        try:
            await callback.bot.send_message(
                inviter_tg,
                f"✅ {callback.from_user.first_name or callback.from_user.username or 'Игрок'} принял приглашение в клан {clan_name}.",
            )
        except Exception:
            pass


@router.callback_query(F.data == "clan_invite_decline")
async def clan_invite_decline_callback(callback: CallbackQuery):
    invite = clan_pending_invites.pop(callback.from_user.id, None)
    await callback.answer("Приглашение отклонено.", show_alert=True)
    if invite and invite.get("inviter_tg"):
        try:
            await callback.bot.send_message(
                invite["inviter_tg"],
                f"❌ {callback.from_user.first_name or callback.from_user.username or 'Игрок'} отклонил приглашение в клан.",
            )
        except Exception:
            pass


@router.callback_query(F.data == "clan_leave")
async def clan_leave_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        if not user.clan:
            await callback.answer("Ты не состоишь в клане.", show_alert=True)
            return

        left_clan = user.clan
        user.clan = None
        user.clan_joined_at = None
        await session.commit()

        if left_clan:
            members_left = await _clan_member_count(session, left_clan)
            if members_left == 0:
                result = await session.execute(
                    select(Clan).where(Clan.name == left_clan)
                )
                clan = result.scalar_one_or_none()
                if clan:
                    await session.delete(clan)
                    await session.commit()

    await callback.answer("Ты покинул клан.", show_alert=True)
    await clans_menu_callback(callback)
