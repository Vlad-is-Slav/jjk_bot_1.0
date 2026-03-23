from __future__ import annotations

from datetime import datetime, timedelta
import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, desc, func, select

from keyboards.clans import get_clans_menu_keyboard
from models import Clan, ClanJoinRequest, User, async_session
from utils.clan_progression import (
    CLAN_DAILY_QUESTS,
    clan_bonuses_for_level,
    get_or_create_clan,
    get_or_create_clan_daily,
)

router = Router()

CLAN_INPUT_TIMEOUT = timedelta(minutes=5)
CLAN_LIST_PAGE_SIZE = 5
CLAN_REQUESTS_PAGE_SIZE = 4

clan_create_input: dict[int, datetime] = {}
clan_invite_input: dict[int, datetime] = {}
clan_pending_invites: dict[int, dict] = {}


def _normalize_clan_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def _valid_clan_name(value: str) -> bool:
    return 3 <= len(value) <= 30


def _display_user_name(user: User | None) -> str:
    if not user:
        return "Игрок"
    return user.first_name or (f"@{user.username}" if user.username else f"Игрок #{user.id}")


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


async def _find_user_by_target(session, target_raw: str) -> User | None:
    raw = (target_raw or "").strip()
    if not raw:
        return None

    if raw.startswith("@"):
        raw = raw[1:].strip()

    if not raw:
        return None

    if raw.isdigit():
        result = await session.execute(select(User).where(User.telegram_id == int(raw)))
        user = result.scalar_one_or_none()
        if user:
            return user

    result = await session.execute(select(User).where(func.lower(User.username) == raw.lower()))
    return result.scalar_one_or_none()


async def _clan_member_count(session, clan_name: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(User.clan == clan_name)
    )
    return int(result.scalar_one() or 0)


def _active_invite_for(user_tg: int) -> dict | None:
    invite = clan_pending_invites.get(user_tg)
    if not invite:
        return None

    created_at = invite.get("created_at") or datetime.utcnow()
    if datetime.utcnow() - created_at > CLAN_INPUT_TIMEOUT:
        clan_pending_invites.pop(user_tg, None)
        return None
    return invite


async def _count_pending_requests(session, clan_name: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(ClanJoinRequest).where(ClanJoinRequest.clan_name == clan_name)
    )
    return int(result.scalar_one() or 0)


async def _get_user_pending_request(session, user_id: int) -> ClanJoinRequest | None:
    result = await session.execute(
        select(ClanJoinRequest).where(ClanJoinRequest.requester_id == user_id)
    )
    return result.scalar_one_or_none()


async def _clear_user_pending_request(session, user_id: int):
    await session.execute(delete(ClanJoinRequest).where(ClanJoinRequest.requester_id == user_id))


async def _ensure_clan_owner(session, clan: Clan) -> User | None:
    owner = None
    if clan.owner_id:
        result = await session.execute(
            select(User).where(User.id == clan.owner_id, User.clan == clan.name)
        )
        owner = result.scalar_one_or_none()
        if owner:
            return owner

    result = await session.execute(
        select(User)
        .where(User.clan == clan.name)
        .order_by(User.clan_joined_at.is_(None), User.clan_joined_at.asc(), User.id.asc())
    )
    owner = result.scalars().first()
    clan.owner_id = owner.id if owner else None
    session.add(clan)
    await session.flush()
    return owner


def _request_created_label(request: ClanJoinRequest) -> str:
    return request.created_at.strftime("%d.%m.%Y %H:%M UTC") if request.created_at else "неизвестно"


async def _render_clans_menu(callback: CallbackQuery):
    clan_create_input.pop(callback.from_user.id, None)
    clan_invite_input.pop(callback.from_user.id, None)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            return False

        user.username = callback.from_user.username
        user.first_name = callback.from_user.first_name or user.first_name

        invite = _active_invite_for(user.telegram_id)
        pending_request = await _get_user_pending_request(session, user.id)
        request_count = 0
        is_owner = False

        if user.clan and pending_request:
            await _clear_user_pending_request(session, user.id)
            pending_request = None

        if user.clan:
            clan = await get_or_create_clan(session, user.clan)
            owner = await _ensure_clan_owner(session, clan)
            members_count = await _clan_member_count(session, clan.name)
            bonuses = clan_bonuses_for_level(clan.level)
            bonus_attack = round((float(bonuses.get("attack_mult", 1.0)) - 1.0) * 100)
            bonus_regen = round((float(bonuses.get("ce_regen_mult", 1.0)) - 1.0) * 100)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            daily = await get_or_create_clan_daily(session, clan.name, today)
            is_owner = bool(owner and owner.id == user.id)
            if is_owner:
                request_count = await _count_pending_requests(session, clan.name)

            text = (
                "🏯 <b>Кланы</b>\n\n"
                f"Твой клан: <b>{html.escape(clan.name)}</b>\n"
                f"Глава: <b>{html.escape(_display_user_name(owner))}</b>\n"
                f"Уровень: <b>{int(clan.level)}</b> | Опыт: <b>{int(clan.exp)}/{int(clan.exp_to_next)}</b>\n"
                f"Участников: <b>{members_count}</b>\n"
                f"Бонусы клана: <b>+{bonus_attack}% урон</b>, <b>+{bonus_regen}% реген CE</b>\n"
            )

            if is_owner:
                text += f"Заявок на вступление: <b>{request_count}</b>\n"

            text += "\n<b>Задания клана на сегодня:</b>\n"
            for key, quest in CLAN_DAILY_QUESTS.items():
                progress = int(getattr(daily, key, 0) or 0)
                done = " ✅" if progress >= int(quest["target"]) else ""
                text += f"• {html.escape(quest['label'])}: {progress}/{int(quest['target'])}{done}\n"
        else:
            text = (
                "🏯 <b>Кланы</b>\n\n"
                "Ты пока без клана. Создай свой, прими приглашение или подай заявку.\n"
            )
            if invite:
                text += "📩 У тебя есть приглашение в клан.\n"
            if pending_request:
                text += (
                    f"📝 Текущая заявка: <b>{html.escape(pending_request.clan_name)}</b>\n"
                    f"Отправлена: <b>{_request_created_label(pending_request)}</b>\n"
                )

        await session.commit()

        await _safe_edit_message(
            callback,
            text,
            reply_markup=get_clans_menu_keyboard(
                bool(user.clan),
                has_invite=bool(invite),
                has_request=bool(pending_request),
                request_count=request_count,
                is_owner=is_owner,
            ),
        )
        return True


@router.callback_query(F.data == "clans_menu")
async def clans_menu_callback(callback: CallbackQuery):
    rendered = await _render_clans_menu(callback)
    if not rendered:
        await callback.answer("Сначала используй /start", show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "clan_create")
async def clan_create_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        if user.clan:
            await callback.answer("Сначала выйди из текущего клана.", show_alert=True)
            return

    clan_invite_input.pop(callback.from_user.id, None)
    clan_create_input[callback.from_user.id] = datetime.utcnow()
    await _safe_edit_message(
        callback,
        "➕ <b>Создание клана</b>\n\n"
        "Отправь название клана (3-30 символов).\n"
        "Пример: Tokyo Jujutsu\n\n"
        "Чтобы отменить, нажми «Назад».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")]]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "clan_invite")
async def clan_invite_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        if not user.clan:
            await callback.answer("Сначала вступи в клан или создай его.", show_alert=True)
            return

    clan_create_input.pop(callback.from_user.id, None)
    clan_invite_input[callback.from_user.id] = datetime.utcnow()
    await _safe_edit_message(
        callback,
        "📨 <b>Пригласить в клан</b>\n\n"
        "Отправь @username или telegram_id игрока, которого хочешь пригласить.\n\n"
        "Чтобы отменить, нажми «Назад».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")]]
        ),
    )
    await callback.answer()


@router.message(
    F.text,
    ~F.text.startswith("/"),
    lambda message: message.from_user.id in clan_create_input or message.from_user.id in clan_invite_input,
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
            result = await session.execute(select(User).where(User.telegram_id == user_tg))
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
            await _clear_user_pending_request(session, user.id)
            user.clan = raw_name
            user.clan_joined_at = datetime.utcnow()
            user.username = message.from_user.username
            user.first_name = message.from_user.first_name or user.first_name
            await session.commit()

        clan_create_input.pop(user_tg, None)
        await message.answer(f"✅ Клан «{raw_name}» создан!")
        return

    if user_tg not in clan_invite_input:
        return

    if now - clan_invite_input.get(user_tg, now) > CLAN_INPUT_TIMEOUT:
        clan_invite_input.pop(user_tg, None)
        return

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_tg))
        inviter = result.scalar_one_or_none()
        if not inviter:
            clan_invite_input.pop(user_tg, None)
            await message.answer("Сначала используй /start.")
            return
        if not inviter.clan:
            clan_invite_input.pop(user_tg, None)
            await message.answer("Сначала вступи в клан или создай его.")
            return

        inviter.username = message.from_user.username
        inviter.first_name = message.from_user.first_name or inviter.first_name

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
            "inviter_tg": inviter.telegram_id,
            "clan": inviter.clan,
            "created_at": datetime.utcnow(),
        }
        await session.commit()

        try:
            await message.bot.send_message(
                target.telegram_id,
                "🏯 <b>Приглашение в клан</b>\n\n"
                f"Тебя приглашает: <b>{html.escape(_display_user_name(inviter))}</b>\n"
                f"Клан: <b>{html.escape(inviter.clan)}</b>\n\n"
                "Принять приглашение?",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Вступить", callback_data="clan_invite_accept"),
                            InlineKeyboardButton(text="❌ Отклонить", callback_data="clan_invite_decline"),
                        ]
                    ]
                ),
                parse_mode="HTML",
            )
        except Exception:
            clan_pending_invites.pop(target.telegram_id, None)
            await message.answer(
                "Не удалось отправить приглашение. Возможно, игрок не писал боту."
            )
            return

    clan_invite_input.pop(user_tg, None)
    await message.answer("✅ Приглашение отправлено.")


@router.callback_query(F.data == "clan_invite_open")
async def clan_invite_open_callback(callback: CallbackQuery):
    invite = _active_invite_for(callback.from_user.id)
    if not invite:
        await callback.answer("Активных приглашений нет.", show_alert=True)
        return

    inviter_name = "Игрок"
    inviter_tg = invite.get("inviter_tg")
    if inviter_tg:
        async with async_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == inviter_tg))
            inviter = result.scalar_one_or_none()
            if inviter:
                inviter_name = _display_user_name(inviter)

    await _safe_edit_message(
        callback,
        "🏯 <b>Приглашение в клан</b>\n\n"
        f"Клан: <b>{html.escape(invite.get('clan') or '—')}</b>\n"
        f"Пригласил: <b>{html.escape(inviter_name)}</b>\n\n"
        "Принять приглашение?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Вступить", callback_data="clan_invite_accept"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data="clan_invite_decline"),
                ],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")],
            ]
        ),
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

    inviter_tg = invite.get("inviter_tg")
    clan_name = invite.get("clan")
    if not clan_name:
        clan_pending_invites.pop(callback.from_user.id, None)
        await callback.answer("Приглашение некорректно.", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        if user.clan:
            await callback.answer("Ты уже в клане.", show_alert=True)
            return

        await get_or_create_clan(session, clan_name)
        await _clear_user_pending_request(session, user.id)
        user.clan = clan_name
        user.clan_joined_at = datetime.utcnow()
        user.username = callback.from_user.username
        user.first_name = callback.from_user.first_name or user.first_name
        await session.commit()

    clan_pending_invites.pop(callback.from_user.id, None)
    await _render_clans_menu(callback)
    await callback.answer("Ты вступил в клан!", show_alert=True)

    if inviter_tg:
        try:
            await callback.bot.send_message(
                inviter_tg,
                f"✅ {callback.from_user.first_name or callback.from_user.username or 'Игрок'} "
                f"принял приглашение в клан {clan_name}.",
            )
        except Exception:
            pass


@router.callback_query(F.data == "clan_invite_decline")
async def clan_invite_decline_callback(callback: CallbackQuery):
    invite = clan_pending_invites.pop(callback.from_user.id, None)
    inviter_tg = invite.get("inviter_tg") if invite else None

    await _render_clans_menu(callback)
    await callback.answer("Приглашение отклонено.", show_alert=True)

    if inviter_tg:
        try:
            await callback.bot.send_message(
                inviter_tg,
                f"❌ {callback.from_user.first_name or callback.from_user.username or 'Игрок'} "
                "отклонил приглашение в клан.",
            )
        except Exception:
            pass


async def _render_clan_directory(callback: CallbackQuery, page: int = 0):
    page = max(0, int(page))

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            return False, "Сначала используй /start"
        if user.clan:
            return False, "Ты уже состоишь в клане."

        pending_request = await _get_user_pending_request(session, user.id)
        if pending_request:
            await session.commit()
            await _render_my_request(callback)
            return True, None

        members_count = func.count(User.id).label("members_count")
        base_query = (
            select(
                Clan.id,
                Clan.name,
                Clan.level,
                Clan.exp,
                Clan.exp_to_next,
                members_count,
            )
            .outerjoin(User, User.clan == Clan.name)
            .group_by(Clan.id)
            .having(func.count(User.id) > 0)
        )

        total_result = await session.execute(select(func.count()).select_from(base_query.subquery()))
        total = int(total_result.scalar_one() or 0)
        max_page = max(0, (total - 1) // CLAN_LIST_PAGE_SIZE) if total else 0
        page = min(page, max_page)

        result = await session.execute(
            base_query
            .order_by(desc(Clan.level), desc(members_count), Clan.name.asc())
            .offset(page * CLAN_LIST_PAGE_SIZE)
            .limit(CLAN_LIST_PAGE_SIZE)
        )
        clans = result.all()
        await session.commit()

    if not clans:
        await _safe_edit_message(
            callback,
            "📨 <b>Подача заявки в клан</b>\n\n"
            "Пока нет открытых кланов, куда можно подать заявку.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")]]
            ),
        )
        return True, None

    text = "📨 <b>Подача заявки в клан</b>\n\nВыбери клан, куда хочешь отправить заявку:\n\n"
    buttons: list[list[InlineKeyboardButton]] = []

    for clan in clans:
        text += (
            f"• <b>{html.escape(clan.name)}</b> | Ур. {int(clan.level)} | "
            f"Участников: {int(clan.members_count)} | Опыт: {int(clan.exp)}/{int(clan.exp_to_next)}\n"
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📨 {clan.name[:20]}",
                    callback_data=f"clan_apply_{int(clan.id)}_{page}",
                )
            ]
        )

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"clan_request_menu_{page - 1}")
        )
    if page < max_page:
        nav_row.append(
            InlineKeyboardButton(text="➡️", callback_data=f"clan_request_menu_{page + 1}")
        )
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")])

    await _safe_edit_message(
        callback,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    return True, None


async def _render_my_request(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            return False, "Сначала используй /start"
        if user.clan:
            await session.commit()
            await _render_clans_menu(callback)
            return True, None

        request = await _get_user_pending_request(session, user.id)
        if not request:
            await session.commit()
            await _render_clans_menu(callback)
            return True, None

        result = await session.execute(select(Clan).where(Clan.name == request.clan_name))
        clan = result.scalar_one_or_none()
        if not clan:
            await _clear_user_pending_request(session, user.id)
            await session.commit()
            await _render_clans_menu(callback)
            return True, None

        owner = await _ensure_clan_owner(session, clan)
        owner_name = _display_user_name(owner) if owner else "Не назначен"
        members_count = await _clan_member_count(session, clan.name)
        await session.commit()

    await _safe_edit_message(
        callback,
        "📝 <b>Моя заявка</b>\n\n"
        f"Клан: <b>{html.escape(request.clan_name)}</b>\n"
        f"Глава: <b>{html.escape(owner_name)}</b>\n"
        f"Участников: <b>{members_count}</b>\n"
        f"Отправлена: <b>{_request_created_label(request)}</b>\n\n"
        "Глава клана увидит её в разделе заявок и сможет принять или отклонить.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отозвать заявку", callback_data="clan_request_cancel")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")],
            ]
        ),
    )
    return True, None


async def _render_clan_requests(callback: CallbackQuery, page: int = 0):
    page = max(0, int(page))

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        current_user = result.scalar_one_or_none()
        if not current_user:
            return False, "Сначала используй /start"
        if not current_user.clan:
            return False, "Ты не состоишь в клане."

        clan = await get_or_create_clan(session, current_user.clan)
        owner = await _ensure_clan_owner(session, clan)
        if not owner or owner.id != current_user.id:
            return False, "Только глава клана может смотреть заявки."

        base_query = (
            select(ClanJoinRequest, User)
            .join(User, User.id == ClanJoinRequest.requester_id)
            .where(ClanJoinRequest.clan_name == clan.name)
        )
        total_result = await session.execute(select(func.count()).select_from(base_query.subquery()))
        total = int(total_result.scalar_one() or 0)
        max_page = max(0, (total - 1) // CLAN_REQUESTS_PAGE_SIZE) if total else 0
        page = min(page, max_page)

        result = await session.execute(
            base_query
            .order_by(ClanJoinRequest.created_at.asc(), ClanJoinRequest.id.asc())
            .offset(page * CLAN_REQUESTS_PAGE_SIZE)
            .limit(CLAN_REQUESTS_PAGE_SIZE)
        )
        requests = result.all()
        await session.commit()

    if not requests:
        await _safe_edit_message(
            callback,
            "📥 <b>Заявки в клан</b>\n\n"
            "Новых заявок пока нет.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")]]
            ),
        )
        return True, None

    text = "📥 <b>Заявки в клан</b>\n\n"
    buttons: list[list[InlineKeyboardButton]] = []
    for request, requester in requests:
        display_name = _display_user_name(requester)
        text += (
            f"• <b>{html.escape(display_name)}</b> | Lv.{int(requester.level)}\n"
            f"  Отправлена: {_request_created_label(request)}\n"
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"✅ Принять {display_name[:10]}",
                    callback_data=f"clan_request_accept_{int(request.id)}_{page}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"clan_request_reject_{int(request.id)}_{page}",
                ),
            ]
        )

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"clan_requests_{page - 1}"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"clan_requests_{page + 1}"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="clans_menu")])

    await _safe_edit_message(
        callback,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    return True, None


@router.callback_query(F.data.startswith("clan_request_menu_"))
async def clan_request_menu_callback(callback: CallbackQuery):
    try:
        page = int(callback.data.rsplit("_", 1)[1])
    except Exception:
        page = 0

    rendered, error_text = await _render_clan_directory(callback, page)
    if not rendered and error_text:
        await callback.answer(error_text, show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "clan_my_request")
async def clan_my_request_callback(callback: CallbackQuery):
    rendered, error_text = await _render_my_request(callback)
    if not rendered and error_text:
        await callback.answer(error_text, show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "clan_request_cancel")
async def clan_request_cancel_callback(callback: CallbackQuery):
    owner_tg = None

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        request = await _get_user_pending_request(session, user.id)
        if not request:
            await session.commit()
            await _render_clans_menu(callback)
            await callback.answer("Активной заявки нет.", show_alert=True)
            return

        result = await session.execute(select(Clan).where(Clan.name == request.clan_name))
        clan = result.scalar_one_or_none()
        if clan:
            owner = await _ensure_clan_owner(session, clan)
            owner_tg = owner.telegram_id if owner else None

        await _clear_user_pending_request(session, user.id)
        await session.commit()

    await _render_clans_menu(callback)
    await callback.answer("Заявка отозвана.", show_alert=True)

    if owner_tg:
        try:
            await callback.bot.send_message(
                owner_tg,
                f"📝 {callback.from_user.first_name or callback.from_user.username or 'Игрок'} "
                "отозвал заявку на вступление в твой клан.",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("clan_apply_"))
async def clan_apply_callback(callback: CallbackQuery):
    try:
        _, _, clan_id_raw, page_raw = callback.data.split("_", 3)
        clan_id = int(clan_id_raw)
        page = int(page_raw)
    except Exception:
        await callback.answer("Некорректная заявка.", show_alert=True)
        return

    owner_tg = None
    clan_name = None

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        if user.clan:
            await callback.answer("Ты уже состоишь в клане.", show_alert=True)
            return

        request = await _get_user_pending_request(session, user.id)
        if request:
            await session.commit()
            await _render_my_request(callback)
            await callback.answer("У тебя уже есть активная заявка.", show_alert=True)
            return

        result = await session.execute(select(Clan).where(Clan.id == clan_id))
        clan = result.scalar_one_or_none()
        if not clan:
            await callback.answer("Клан не найден.", show_alert=True)
            return

        members_count = await _clan_member_count(session, clan.name)
        owner = await _ensure_clan_owner(session, clan)
        if members_count <= 0 or not owner:
            await callback.answer("В этот клан сейчас нельзя подать заявку.", show_alert=True)
            return

        user.username = callback.from_user.username
        user.first_name = callback.from_user.first_name or user.first_name
        request = ClanJoinRequest(clan_name=clan.name, requester_id=user.id)
        session.add(request)
        await session.flush()
        await session.commit()

        owner_tg = owner.telegram_id
        clan_name = clan.name

    await _render_my_request(callback)
    await callback.answer("Заявка отправлена.", show_alert=True)

    if owner_tg and clan_name:
        try:
            await callback.bot.send_message(
                owner_tg,
                "📥 <b>Новая заявка в клан</b>\n\n"
                f"{html.escape(callback.from_user.first_name or callback.from_user.username or 'Игрок')} "
                f"хочет вступить в клан <b>{html.escape(clan_name)}</b>.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📥 Открыть заявки",
                                callback_data="clan_requests_0",
                            )
                        ]
                    ]
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("clan_requests_"))
async def clan_requests_callback(callback: CallbackQuery):
    try:
        page = int(callback.data.rsplit("_", 1)[1])
    except Exception:
        page = 0

    rendered, error_text = await _render_clan_requests(callback, page)
    if not rendered and error_text:
        await callback.answer(error_text, show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith("clan_request_accept_"))
async def clan_request_accept_callback(callback: CallbackQuery):
    try:
        _, _, _, request_id_raw, page_raw = callback.data.split("_", 4)
        request_id = int(request_id_raw)
        page = int(page_raw)
    except Exception:
        await callback.answer("Некорректная заявка.", show_alert=True)
        return

    requester_tg = None
    clan_name = None

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        current_user = result.scalar_one_or_none()
        if not current_user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(ClanJoinRequest, User)
            .join(User, User.id == ClanJoinRequest.requester_id)
            .where(ClanJoinRequest.id == request_id)
        )
        row = result.first()
        if not row:
            await callback.answer("Заявка не найдена.", show_alert=True)
            rendered, error_text = await _render_clan_requests(callback, page)
            if not rendered and error_text:
                await _render_clans_menu(callback)
            return

        request, requester = row
        result = await session.execute(select(Clan).where(Clan.name == request.clan_name))
        clan = result.scalar_one_or_none()
        if not clan:
            await session.execute(delete(ClanJoinRequest).where(ClanJoinRequest.id == request.id))
            await session.commit()
            await callback.answer("Клан больше не существует.", show_alert=True)
            await _render_clans_menu(callback)
            return

        owner = await _ensure_clan_owner(session, clan)
        if not owner or owner.id != current_user.id:
            await callback.answer("Только глава клана может принимать заявки.", show_alert=True)
            return

        if requester.clan:
            await session.execute(delete(ClanJoinRequest).where(ClanJoinRequest.id == request.id))
            await session.commit()
            await callback.answer("Игрок уже состоит в клане.", show_alert=True)
            await _render_clan_requests(callback, page)
            return

        requester.clan = clan.name
        requester.clan_joined_at = datetime.utcnow()
        clan_pending_invites.pop(requester.telegram_id, None)
        await session.execute(delete(ClanJoinRequest).where(ClanJoinRequest.id == request.id))
        await session.commit()

        requester_tg = requester.telegram_id
        clan_name = clan.name

    await _render_clan_requests(callback, page)
    await callback.answer("Заявка принята.", show_alert=True)

    if requester_tg and clan_name:
        try:
            await callback.bot.send_message(
                requester_tg,
                f"✅ Твоя заявка принята. Теперь ты состоишь в клане {clan_name}.",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("clan_request_reject_"))
async def clan_request_reject_callback(callback: CallbackQuery):
    try:
        _, _, _, request_id_raw, page_raw = callback.data.split("_", 4)
        request_id = int(request_id_raw)
        page = int(page_raw)
    except Exception:
        await callback.answer("Некорректная заявка.", show_alert=True)
        return

    requester_tg = None
    clan_name = None

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        current_user = result.scalar_one_or_none()
        if not current_user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(ClanJoinRequest, User)
            .join(User, User.id == ClanJoinRequest.requester_id)
            .where(ClanJoinRequest.id == request_id)
        )
        row = result.first()
        if not row:
            await callback.answer("Заявка не найдена.", show_alert=True)
            await _render_clan_requests(callback, page)
            return

        request, requester = row
        result = await session.execute(select(Clan).where(Clan.name == request.clan_name))
        clan = result.scalar_one_or_none()
        if not clan:
            await session.execute(delete(ClanJoinRequest).where(ClanJoinRequest.id == request.id))
            await session.commit()
            await callback.answer("Клан больше не существует.", show_alert=True)
            await _render_clans_menu(callback)
            return

        owner = await _ensure_clan_owner(session, clan)
        if not owner or owner.id != current_user.id:
            await callback.answer("Только глава клана может отклонять заявки.", show_alert=True)
            return

        requester_tg = requester.telegram_id
        clan_name = clan.name
        await session.execute(delete(ClanJoinRequest).where(ClanJoinRequest.id == request.id))
        await session.commit()

    await _render_clan_requests(callback, page)
    await callback.answer("Заявка отклонена.", show_alert=True)

    if requester_tg and clan_name:
        try:
            await callback.bot.send_message(
                requester_tg,
                f"❌ Твоя заявка в клан {clan_name} была отклонена.",
            )
        except Exception:
            pass


@router.callback_query(F.data == "clan_leave")
async def clan_leave_callback(callback: CallbackQuery):
    new_owner_tg = None
    left_clan = None

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        if not user.clan:
            await callback.answer("Ты не состоишь в клане.", show_alert=True)
            return

        left_clan = user.clan
        result = await session.execute(select(Clan).where(Clan.name == left_clan))
        clan = result.scalar_one_or_none()
        was_owner = bool(clan and clan.owner_id == user.id)

        user.clan = None
        user.clan_joined_at = None
        await session.flush()

        members_left = await _clan_member_count(session, left_clan)
        if clan:
            if members_left == 0:
                await session.execute(
                    delete(ClanJoinRequest).where(ClanJoinRequest.clan_name == left_clan)
                )
                await session.delete(clan)
            elif was_owner:
                new_owner = await _ensure_clan_owner(session, clan)
                if new_owner:
                    new_owner_tg = new_owner.telegram_id

        await session.commit()

    await _render_clans_menu(callback)
    await callback.answer("Ты покинул клан.", show_alert=True)

    if new_owner_tg and left_clan:
        try:
            await callback.bot.send_message(
                new_owner_tg,
                f"🏯 Теперь ты глава клана {left_clan}.",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("clan_join_"))
async def clan_legacy_join_callback(callback: CallbackQuery):
    await callback.answer(
        "Система кланов обновлена. Теперь можно подавать заявки в кланы.",
        show_alert=True,
    )
