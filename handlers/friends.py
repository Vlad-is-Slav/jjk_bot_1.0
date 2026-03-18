from datetime import datetime
import html

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy import select, or_, func
from sqlalchemy.orm import selectinload

from models import async_session, User, Friend
from keyboards.main_menu import get_friends_menu, get_back_button
from keyboards.pvp import get_pvp_challenge_keyboard
from handlers.pvp import pvp_challenges, active_pvp_battles

router = Router()


def _display_name(user: User) -> str:
    return user.first_name or (f"@{user.username}" if user.username else f"Игрок #{user.id}")


def _has_active_pvp_battle(telegram_id: int) -> bool:
    for battle in active_pvp_battles.values():
        if battle["player1_tg"] == telegram_id or battle["player2_tg"] == telegram_id:
            return True
    try:
        from handlers.coop_pvp import active_coop_battles
        if telegram_id in active_coop_battles:
            return True
    except Exception:
        pass
    return False


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


async def _find_target_user(session, target_raw: str) -> User | None:
    raw = (target_raw or "").strip()
    if not raw:
        return None

    if raw.startswith("@"):
        username = raw[1:].strip().lower()
        if not username:
            return None
        result = await session.execute(select(User).where(func.lower(User.username) == username))
        return result.scalar_one_or_none()

    if raw.isdigit():
        result = await session.execute(select(User).where(User.telegram_id == int(raw)))
        return result.scalar_one_or_none()

    result = await session.execute(select(User).where(func.lower(User.username) == raw.lower()))
    return result.scalar_one_or_none()


@router.message(Command("addfriend"))
async def cmd_add_friend(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer(
            "Использование:\n"
            "<code>/addfriend @username</code>\n"
            "<code>/addfriend telegram_id</code>",
            parse_mode="HTML",
        )
        return

    target_raw = args[1].strip()

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        requester = result.scalar_one_or_none()
        if not requester:
            await message.answer("Сначала используй /start")
            return

        requester.username = message.from_user.username
        requester.first_name = message.from_user.first_name or requester.first_name

        target_user = await _find_target_user(session, target_raw)
        if not target_user:
            await message.answer("Игрок не найден. Он должен сначала запустить бота через /start.")
            return

        if target_user.id == requester.id:
            await message.answer("Нельзя добавить самого себя в друзья.")
            return

        result = await session.execute(
            select(Friend).where(
                or_(
                    (Friend.requester_id == requester.id) & (Friend.addressee_id == target_user.id),
                    (Friend.requester_id == target_user.id) & (Friend.addressee_id == requester.id),
                )
            )
        )
        existing_rows = result.scalars().all()
        existing = sorted(existing_rows, key=lambda x: x.id, reverse=True)[0] if existing_rows else None

        if existing:
            if existing.status == "accepted":
                await message.answer("Вы уже друзья.")
                return
            if existing.status == "pending":
                if existing.requester_id == target_user.id and existing.addressee_id == requester.id:
                    existing.status = "accepted"
                    existing.accepted_at = datetime.utcnow()
                    await session.commit()
                    await message.answer(f"✅ Вы теперь друзья с {_display_name(target_user)}!")
                    return
                await message.answer("Заявка уже отправлена и ожидает принятия.")
                return

            existing.requester_id = requester.id
            existing.addressee_id = target_user.id
            existing.status = "pending"
            existing.created_at = datetime.utcnow()
            existing.accepted_at = None
            request_row = existing
        else:
            request_row = Friend(
                requester_id=requester.id,
                addressee_id=target_user.id,
                status="pending",
            )
            session.add(request_row)
            await session.flush()

        await session.commit()

        await message.answer(f"✅ Заявка отправлена игроку {_display_name(target_user)}.")

        try:
            await message.bot.send_message(
                target_user.telegram_id,
                "📨 <b>Новая заявка в друзья</b>\n\n"
                f"{html.escape(_display_name(requester))} хочет добавить тебя в друзья.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_friend_{request_row.id}"),
                            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_friend_{request_row.id}"),
                        ]
                    ]
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(
        f"Твой Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Друг может добавить тебя так:\n"
        f"<code>/addfriend {message.from_user.id}</code>",
        parse_mode="HTML",
    )


@router.message(Command("friends"))
async def cmd_friends(message: Message):
    await message.answer(
        "👥 <b>Друзья</b>\n\n"
        "Нажми кнопку ниже, чтобы открыть раздел друзей.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👥 Открыть друзей", callback_data="friends")]
            ]
        ),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "friends")
async def friends_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(Friend).where(
                or_(Friend.requester_id == user.id, Friend.addressee_id == user.id),
                Friend.status == "accepted",
            )
        )
        friends_count = len(result.scalars().all())

        result = await session.execute(
            select(Friend).where(
                Friend.addressee_id == user.id,
                Friend.status == "pending",
            )
        )
        requests_count = len(result.scalars().all())

        await _safe_edit_message(
            callback,
            "👥 <b>Друзья</b>\n\n"
            f"📋 Друзей: {friends_count}\n"
            f"📨 Заявок: {requests_count}\n\n"
            "Выбери действие:",
            reply_markup=get_friends_menu(),
        )
    await callback.answer()


@router.callback_query(F.data == "friends_list")
async def friends_list_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(Friend)
            .options(selectinload(Friend.requester), selectinload(Friend.addressee))
            .where(
                or_(Friend.requester_id == user.id, Friend.addressee_id == user.id),
                Friend.status == "accepted",
            )
            .order_by(Friend.accepted_at.desc())
        )
        friendships = result.scalars().all()

        if not friendships:
            await _safe_edit_message(
                callback,
                "👥 <b>Список друзей</b>\n\n"
                "У тебя пока нет друзей.\n"
                "Отправь заявку другому игроку.",
                reply_markup=get_friends_menu(),
            )
            await callback.answer()
            return

        text = "👥 <b>Твои друзья:</b>\n\n"
        buttons = []
        for friendship in friendships:
            friend = friendship.get_friend_for(user.id)
            if not friend:
                continue
            name = _display_name(friend)
            text += f"• {html.escape(name)} (Lv.{friend.level})\n"
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"⚔️ Бой с {name[:15]}",
                        callback_data=f"friend_battle_{friend.telegram_id}",
                    )
                ]
            )

        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="friends")])
        await _safe_edit_message(
            callback,
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )
    await callback.answer()


@router.callback_query(F.data == "add_friend")
async def add_friend_callback(callback: CallbackQuery):
    await _safe_edit_message(
        callback,
        "➕ <b>Добавить друга</b>\n\n"
        "Отправь команду:\n"
        "<code>/addfriend @username</code>\n\n"
        "или\n"
        "<code>/addfriend ID</code>\n\n"
        "ID можно узнать командой /myid.",
        reply_markup=get_back_button("friends"),
    )
    await callback.answer()


@router.callback_query(F.data == "friend_requests")
async def friend_requests_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(Friend)
            .options(selectinload(Friend.requester))
            .where(Friend.addressee_id == user.id, Friend.status == "pending")
            .order_by(Friend.created_at.desc())
        )
        requests = result.scalars().all()

        if not requests:
            await _safe_edit_message(
                callback,
                "📨 <b>Заявки в друзья</b>\n\n"
                "Новых заявок нет.",
                reply_markup=get_friends_menu(),
            )
            await callback.answer()
            return

        text = "📨 <b>Заявки в друзья:</b>\n\n"
        buttons = []
        for req in requests:
            requester = req.requester
            name = _display_name(requester)
            text += f"• {html.escape(name)} хочет добавить тебя в друзья\n"
            buttons.append(
                [
                    InlineKeyboardButton(text=f"✅ Принять {name[:10]}", callback_data=f"accept_friend_{req.id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_friend_{req.id}"),
                ]
            )

        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="friends")])
        await _safe_edit_message(
            callback,
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("accept_friend_"))
async def accept_friend_callback(callback: CallbackQuery):
    request_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        result = await session.execute(select(Friend).where(Friend.id == request_id))
        friendship = result.scalar_one_or_none()
        if not friendship:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        current_user = result.scalar_one_or_none()
        if not current_user or friendship.addressee_id != current_user.id:
            await callback.answer("Эта заявка адресована не тебе.", show_alert=True)
            return
        if friendship.status != "pending":
            await callback.answer("Заявка уже обработана.", show_alert=True)
            return

        friendship.status = "accepted"
        friendship.accepted_at = datetime.utcnow()
        await session.commit()

    await callback.answer("Заявка принята.")
    await friend_requests_callback(callback)


@router.callback_query(F.data.startswith("decline_friend_"))
async def decline_friend_callback(callback: CallbackQuery):
    request_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        result = await session.execute(select(Friend).where(Friend.id == request_id))
        friendship = result.scalar_one_or_none()
        if not friendship:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        current_user = result.scalar_one_or_none()
        if not current_user or friendship.addressee_id != current_user.id:
            await callback.answer("Эта заявка адресована не тебе.", show_alert=True)
            return
        if friendship.status != "pending":
            await callback.answer("Заявка уже обработана.", show_alert=True)
            return

        friendship.status = "declined"
        await session.commit()

    await callback.answer("Заявка отклонена.")
    await friend_requests_callback(callback)


@router.callback_query(F.data.startswith("friend_battle_"))
async def friend_battle_callback(callback: CallbackQuery):
    friend_tg_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        result = await session.execute(select(User).where(User.telegram_id == friend_tg_id))
        friend = result.scalar_one_or_none()
        if not user or not friend:
            await callback.answer("Игрок не найден.", show_alert=True)
            return

        result = await session.execute(
            select(Friend).where(
                or_(
                    (Friend.requester_id == user.id) & (Friend.addressee_id == friend.id),
                    (Friend.requester_id == friend.id) & (Friend.addressee_id == user.id),
                ),
                Friend.status == "accepted",
            )
        )
        if not result.scalars().first():
            await callback.answer("Можно вызывать на бой только друзей.", show_alert=True)
            return

        if not user.slot_1_card_id or not friend.slot_1_card_id:
            await callback.answer("У одного из игроков не экипирована главная карта.", show_alert=True)
            return

        if _has_active_pvp_battle(user.telegram_id) or _has_active_pvp_battle(friend.telegram_id):
            await callback.answer("Один из игроков уже находится в PvP бою.", show_alert=True)
            return

        key = (user.telegram_id, friend.telegram_id)
        pvp_challenges[key] = datetime.utcnow()

        try:
            await callback.bot.send_message(
                friend.telegram_id,
                "⚔️ <b>Тебя вызвали на PvP бой!</b>\n\n"
                f"{html.escape(_display_name(user))} хочет сразиться с тобой.",
                reply_markup=get_pvp_challenge_keyboard(user.telegram_id),
                parse_mode="HTML",
            )
        except Exception:
            pvp_challenges.pop(key, None)
            await callback.answer(
                "Не удалось отправить вызов игроку. Возможно, он не писал боту.",
                show_alert=True,
            )
            return

        await _safe_edit_message(
            callback,
            "⚔️ <b>Вызов на бой отправлен!</b>\n\n"
            f"Ожидаем ответа от {html.escape(_display_name(friend))}...",
            reply_markup=get_back_button("friends"),
        )

    await callback.answer()
