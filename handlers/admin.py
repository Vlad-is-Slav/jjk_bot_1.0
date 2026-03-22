from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, func, or_, select, update

from config import ADMIN_IDS as CONFIG_ADMIN_IDS
from models import (
    async_session,
    Battle,
    Clan,
    CoinTransaction,
    DailyReward,
    Friend,
    MarketListing,
    Technique,
    Title,
    TradeOffer,
    User,
    UserAchievement,
    UserAcademyVisit,
    UserBossAttempt,
    UserCampaignProgress,
    UserCard,
    UserDailyQuest,
    UserProfile,
    UserPromoCode,
    UserQuote,
    UserStats,
    UserTechnique,
    UserTitle,
)
from utils.achievement_data import TITLES
from utils.card_data import ALL_CARDS
from utils.card_rewards import get_or_create_card_template
from utils.pvp_progression import apply_experience_with_pvp_rolls
from utils.technique_data import ALL_TECHNIQUES

router = Router()

# Запасной bootstrap-админ на случай пустого ADMIN_IDS в .env
ADMIN_IDS = set(CONFIG_ADMIN_IDS + [1296861067])


def _admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎴 Выдать карту", callback_data="admin_give_card"),
                InlineKeyboardButton(text="✨ Выдать технику", callback_data="admin_give_tech"),
            ],
            [
                InlineKeyboardButton(text="💰 Выдать валюту", callback_data="admin_give_currency"),
                InlineKeyboardButton(text="👑 Выдать титул", callback_data="admin_give_title"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton(text="🔧 Настройки", callback_data="admin_settings"),
            ],
        ]
    )


def _display_name(user: User) -> str:
    if user.first_name:
        return user.first_name
    if user.username:
        return f"@{user.username}"
    return str(user.telegram_id)


async def _resolve_user(session, target_raw: str) -> User | None:
    target = (target_raw or "").strip()
    if not target:
        return None

    if target.startswith("@"):
        username = target[1:].strip().lower()
        if not username:
            return None
        result = await session.execute(
            select(User).where(func.lower(User.username) == username)
        )
        return result.scalar_one_or_none()

    if target.isdigit():
        result = await session.execute(
            select(User).where(User.telegram_id == int(target))
        )
        return result.scalar_one_or_none()

    result = await session.execute(
        select(User).where(func.lower(User.username) == target.lower())
    )
    return result.scalar_one_or_none()


def _find_card_data(card_name: str) -> dict | None:
    normalized = (card_name or "").strip().lower()
    for card in ALL_CARDS:
        if card["name"].lower() == normalized:
            return card
    return None


def _find_tech_data(tech_name: str) -> dict | None:
    normalized = (tech_name or "").strip().lower()
    for tech in ALL_TECHNIQUES:
        if tech["name"].lower() == normalized:
            return tech
    return None


def _find_title_data(title_name: str) -> dict | None:
    normalized = (title_name or "").strip().lower()
    for title in TITLES:
        if title["name"].lower() == normalized:
            return title
    return None


def _parse_name_and_optional_level(raw_args: list[str]) -> tuple[str, int]:
    level = 1
    parts = list(raw_args)
    if parts and parts[-1].isdigit():
        level = int(parts[-1])
        parts = parts[:-1]
    name = " ".join(parts).replace("_", " ").strip()
    return name, level


async def _notify_user_safe(message: Message, user: User, text: str):
    try:
        await message.bot.send_message(user.telegram_id, text, parse_mode="HTML")
    except Exception:
        pass


def _kick_from_active_battles(telegram_id: int) -> bool:
    """Удалить пользователя из активных боёв, чтобы бан/сброс применился сразу."""
    kicked = False

    try:
        from handlers.pve import active_pve_battles

        if telegram_id in active_pve_battles:
            del active_pve_battles[telegram_id]
            kicked = True
    except Exception:
        pass

    try:
        from handlers.pvp import active_pvp_battles

        battle = active_pvp_battles.get(telegram_id)
        if battle:
            battle_id = battle.get("battle_id")
            for uid, existing in list(active_pvp_battles.items()):
                if existing.get("battle_id") == battle_id:
                    del active_pvp_battles[uid]
                    kicked = True
        elif telegram_id in active_pvp_battles:
            del active_pvp_battles[telegram_id]
            kicked = True
    except Exception:
        pass

    try:
        from handlers.coop_pvp import active_coop_battles

        battle = active_coop_battles.get(telegram_id)
        if battle:
            battle_id = battle.get("battle_id")
            for uid, existing in list(active_coop_battles.items()):
                if existing.get("battle_id") == battle_id:
                    del active_coop_battles[uid]
                    kicked = True
        elif telegram_id in active_coop_battles:
            del active_coop_battles[telegram_id]
            kicked = True
    except Exception:
        pass

    return kicked


async def _wipe_user_account(session, target_user: User):
    """Полностью удалить игрока и связанные записи."""
    target_user_id = int(target_user.id)
    target_tg = int(target_user.telegram_id)

    _kick_from_active_battles(target_tg)

    await session.execute(update(Clan).where(Clan.owner_id == target_user_id).values(owner_id=None))

    await session.execute(delete(Friend).where(or_(Friend.requester_id == target_user_id, Friend.addressee_id == target_user_id)))
    await session.execute(delete(Battle).where(or_(Battle.player1_id == target_user_id, Battle.player2_id == target_user_id, Battle.winner_id == target_user_id)))
    await session.execute(delete(MarketListing).where(or_(MarketListing.seller_id == target_user_id, MarketListing.buyer_id == target_user_id)))
    await session.execute(delete(TradeOffer).where(or_(TradeOffer.sender_id == target_user_id, TradeOffer.receiver_id == target_user_id)))
    await session.execute(delete(CoinTransaction).where(CoinTransaction.user_id == target_user_id))

    await session.execute(delete(UserCard).where(UserCard.user_id == target_user_id))
    await session.execute(delete(UserTechnique).where(UserTechnique.user_id == target_user_id))
    await session.execute(delete(UserTitle).where(UserTitle.user_id == target_user_id))
    await session.execute(delete(UserAchievement).where(UserAchievement.user_id == target_user_id))
    await session.execute(delete(UserDailyQuest).where(UserDailyQuest.user_id == target_user_id))
    await session.execute(delete(DailyReward).where(DailyReward.user_id == target_user_id))
    await session.execute(delete(UserStats).where(UserStats.user_id == target_user_id))
    await session.execute(delete(UserCampaignProgress).where(UserCampaignProgress.user_id == target_user_id))
    await session.execute(delete(UserBossAttempt).where(UserBossAttempt.user_id == target_user_id))
    await session.execute(delete(UserPromoCode).where(UserPromoCode.user_id == target_user_id))
    await session.execute(delete(UserAcademyVisit).where(UserAcademyVisit.user_id == target_user_id))
    await session.execute(delete(UserProfile).where(UserProfile.user_id == target_user_id))
    await session.execute(delete(UserQuote).where(UserQuote.user_id == target_user_id))

    await session.delete(target_user)


async def is_admin(telegram_id: int) -> bool:
    if telegram_id in ADMIN_IDS:
        return True

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        return bool(user and user.is_admin)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет прав администратора!")
        return

    await message.answer(
        "🔧 <b>Админ панель</b>\n\nВыбери действие:",
        reply_markup=_admin_panel_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("givecard"))
async def cmd_give_card(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.answer(
            "🎴 <b>Выдача карты</b>\n\n"
            "Использование:\n"
            "<code>/givecard @username Название_Карты [уровень]</code>\n"
            "<code>/givecard ID Название_Карты [уровень]</code>\n\n"
            "Примеры:\n"
            "<code>/givecard @user Годжо_Сатору 10</code>\n"
            "<code>/givecard 123456789 Рёмен_Сукуна</code>",
            parse_mode="HTML",
        )
        return

    target_raw = args[0]
    card_name, level = _parse_name_and_optional_level(args[1:])
    if not card_name:
        await message.answer("❌ Укажи название карты.")
        return
    if level < 1:
        await message.answer("❌ Уровень карты должен быть >= 1.")
        return

    card_data = _find_card_data(card_name)
    if not card_data:
        await message.answer(f"❌ Карта '{card_name}' не найдена.")
        return

    async with async_session() as session:
        target_user = await _resolve_user(session, target_raw)
        if not target_user:
            await message.answer("❌ Игрок не найден.")
            return

        card_template = await get_or_create_card_template(session, card_data)

        user_card = UserCard(
            user_id=target_user.id,
            card_id=card_template.id,
            level=level,
        )
        user_card.recalculate_stats()
        session.add(user_card)
        await session.commit()

        await message.answer(
            "✅ <b>Карта выдана!</b>\n\n"
            f"Игрок: {_display_name(target_user)}\n"
            f"Карта: {card_data['name']}\n"
            f"Уровень: {level}\n"
            f"Редкость: {card_data['rarity']}",
            parse_mode="HTML",
        )
        await _notify_user_safe(
            message,
            target_user,
            "🎁 <b>Тебе выдали карту!</b>\n\n"
            f"Карта: {card_data['name']}\n"
            f"Уровень: {level}",
        )


@router.message(Command("givetech"))
async def cmd_give_tech(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.answer(
            "✨ <b>Выдача техники</b>\n\n"
            "Использование:\n"
            "<code>/givetech @username Название_Техники</code>\n"
            "<code>/givetech ID Название_Техники</code>\n\n"
            "Пример:\n"
            "<code>/givetech @user Шесть_Глаз</code>",
            parse_mode="HTML",
        )
        return

    target_raw = args[0]
    tech_name = " ".join(args[1:]).replace("_", " ").strip()
    if not tech_name:
        await message.answer("❌ Укажи название техники.")
        return

    tech_data = _find_tech_data(tech_name)
    if not tech_data:
        await message.answer(f"❌ Техника '{tech_name}' не найдена.")
        return

    async with async_session() as session:
        target_user = await _resolve_user(session, target_raw)
        if not target_user:
            await message.answer("❌ Игрок не найден.")
            return

        result = await session.execute(
            select(Technique).where(Technique.name == tech_data["name"])
        )
        tech_template = result.scalar_one_or_none()

        if not tech_template:
            tech_template = Technique(
                name=tech_data["name"],
                description=tech_data.get("description"),
                technique_type=tech_data["technique_type"],
                ce_cost=tech_data.get("ce_cost", 0),
                effect_type=tech_data.get("effect_type"),
                effect_value=tech_data.get("effect_value", 0),
                trigger_chance=tech_data.get("trigger_chance", 0),
                duration=tech_data.get("duration", 0),
                icon=tech_data.get("icon", "✨"),
                rarity=tech_data.get("rarity", "common"),
            )
            session.add(tech_template)
            await session.flush()

        result = await session.execute(
            select(UserTechnique).where(
                UserTechnique.user_id == target_user.id,
                UserTechnique.technique_id == tech_template.id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await message.answer("❌ У игрока уже есть эта техника.")
            return

        session.add(
            UserTechnique(
                user_id=target_user.id,
                technique_id=tech_template.id,
                level=1,
                is_equipped=False,
            )
        )
        await session.commit()

        await message.answer(
            "✅ <b>Техника выдана!</b>\n\n"
            f"Игрок: {_display_name(target_user)}\n"
            f"Техника: {tech_data['name']}\n"
            f"Тип: {tech_data['technique_type']}\n"
            f"Редкость: {tech_data['rarity']}",
            parse_mode="HTML",
        )
        await _notify_user_safe(
            message,
            target_user,
            "🎁 <b>Тебе выдали технику!</b>\n\n"
            f"Техника: {tech_data['name']}",
        )


@router.message(Command("givecurrency"))
async def cmd_give_currency(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return

    args = message.text.split()[1:]
    if len(args) < 3:
        await message.answer(
            "💰 <b>Выдача валюты</b>\n\n"
            "Использование:\n"
            "<code>/givecurrency @username coins|points|exp КОЛИЧЕСТВО</code>",
            parse_mode="HTML",
        )
        return

    target_raw = args[0]
    currency_type = args[1].lower().strip()
    try:
        amount = int(args[2])
    except ValueError:
        await message.answer("❌ Количество должно быть числом.")
        return

    if amount <= 0:
        await message.answer("❌ Количество должно быть больше 0.")
        return

    async with async_session() as session:
        target_user = await _resolve_user(session, target_raw)
        if not target_user:
            await message.answer("❌ Игрок не найден.")
            return

        if currency_type == "coins":
            target_user.coins += amount
            granted_label = f"{amount} монет"
        elif currency_type == "points":
            target_user.points += amount
            granted_label = f"{amount} очков"
        elif currency_type == "exp":
            _, actual_exp, unlocked = await apply_experience_with_pvp_rolls(session, target_user, amount)
            granted_label = f"{actual_exp} опыта"
            if unlocked:
                granted_label += f"\nНовые PvP-техники: {', '.join(t.name for t in unlocked)}"
        else:
            await message.answer("❌ Неверный тип. Допустимо: coins, points, exp.")
            return

        await session.commit()

        await message.answer(
            "✅ <b>Валюта выдана!</b>\n\n"
            f"Игрок: {_display_name(target_user)}\n"
            f"Выдано: {granted_label}",
            parse_mode="HTML",
        )
        await _notify_user_safe(
            message,
            target_user,
            "🎁 <b>Тебе выдали награду от администратора!</b>\n\n"
            f"{granted_label}",
        )


@router.message(Command("givetitle"))
async def cmd_give_title(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.answer(
            "👑 <b>Выдача титула</b>\n\n"
            "Использование:\n"
            "<code>/givetitle @username Название_Титула</code>\n"
            "<code>/givetitle ID Название_Титула</code>\n\n"
            "Пример:\n"
            "<code>/givetitle @user Король_Проклятий</code>",
            parse_mode="HTML",
        )
        return

    target_raw = args[0]
    title_name = " ".join(args[1:]).replace("_", " ").strip()
    if not title_name:
        await message.answer("❌ Укажи название титула.")
        return

    async with async_session() as session:
        target_user = await _resolve_user(session, target_raw)
        if not target_user:
            await message.answer("❌ Игрок не найден.")
            return

        result = await session.execute(
            select(Title).where(func.lower(Title.name) == title_name.lower())
        )
        title_template = result.scalar_one_or_none()

        if not title_template:
            title_data = _find_title_data(title_name)
            if title_data:
                title_template = Title(
                    name=title_data["name"],
                    description=title_data.get("description"),
                    attack_bonus=title_data.get("attack_bonus", 0),
                    defense_bonus=title_data.get("defense_bonus", 0),
                    speed_bonus=title_data.get("speed_bonus", 0),
                    hp_bonus=title_data.get("hp_bonus", 0),
                    icon=title_data.get("icon", "👑"),
                    requirement=title_data.get("requirement", "Админ-выдача"),
                )
            else:
                title_template = Title(
                    name=title_name,
                    description="Титул, выданный администратором.",
                    icon="👑",
                    requirement="Админ-выдача",
                )
            session.add(title_template)
            await session.flush()

        result = await session.execute(
            select(UserTitle).where(
                UserTitle.user_id == target_user.id,
                UserTitle.title_id == title_template.id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await message.answer("❌ У игрока уже есть этот титул.")
            return

        session.add(
            UserTitle(
                user_id=target_user.id,
                title_id=title_template.id,
                is_equipped=False,
            )
        )
        await session.commit()

        await message.answer(
            "✅ <b>Титул выдан!</b>\n\n"
            f"Игрок: {_display_name(target_user)}\n"
            f"Титул: {title_template.icon} {title_template.name}",
            parse_mode="HTML",
        )
        await _notify_user_safe(
            message,
            target_user,
            "👑 <b>Тебе выдали титул!</b>\n\n"
            f"{title_template.icon} {title_template.name}",
        )


@router.message(Command("setadmin"))
async def cmd_set_admin(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return

    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: <code>/setadmin @username</code> или <code>/setadmin ID</code>", parse_mode="HTML")
        return

    async with async_session() as session:
        target_user = await _resolve_user(session, args[0])
        if not target_user:
            await message.answer("❌ Игрок не найден.")
            return

        target_user.is_admin = True
        await session.commit()

        await message.answer(f"✅ {_display_name(target_user)} теперь администратор!")


@router.message(Command("ban"))
async def cmd_ban_user(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer(
            "🚫 <b>Бан игрока</b>\n\n"
            "Использование:\n"
            "<code>/ban @username [причина]</code>\n"
            "<code>/ban ID [причина]</code>",
            parse_mode="HTML",
        )
        return

    target_raw = args[1].strip()
    reason = args[2].strip() if len(args) > 2 else "Причина не указана."

    async with async_session() as session:
        target_user = await _resolve_user(session, target_raw)
        if not target_user:
            await message.answer("❌ Игрок не найден.")
            return

        if target_user.telegram_id == message.from_user.id:
            await message.answer("❌ Нельзя забанить самого себя.")
            return

        if target_user.telegram_id in ADMIN_IDS or target_user.is_admin:
            await message.answer("❌ Нельзя забанить администратора.")
            return

        if target_user.is_banned:
            await message.answer(f"ℹ️ Игрок {_display_name(target_user)} уже забанен.")
            return

        target_user.is_banned = True
        await session.commit()

    kicked = _kick_from_active_battles(target_user.telegram_id)
    kicked_note = "\n⚔️ Игрок удалён из активного боя." if kicked else ""

    await message.answer(
        "✅ <b>Игрок забанен.</b>\n\n"
        f"Игрок: {_display_name(target_user)}\n"
        f"Причина: {reason}{kicked_note}",
        parse_mode="HTML",
    )

    try:
        await message.bot.send_message(
            target_user.telegram_id,
            "🚫 <b>Ты забанен в боте.</b>\n\n"
            f"Причина: {reason}\n"
            "Если считаешь, что это ошибка — свяжись с администратором.",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("resetuser"))
async def cmd_reset_user(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return

    args = message.text.split()[1:]
    if not args:
        await message.answer(
            "🧹 <b>Сброс игрока</b>\n\n"
            "Полностью удаляет аккаунт игрока из базы.\n"
            "При следующем <code>/start</code> он начнёт с нуля.\n\n"
            "Использование:\n"
            "<code>/resetuser @username</code>\n"
            "<code>/resetuser ID</code>",
            parse_mode="HTML",
        )
        return

    async with async_session() as session:
        target_user = await _resolve_user(session, args[0])
        if not target_user:
            await message.answer("❌ Игрок не найден.")
            return

        if target_user.telegram_id == message.from_user.id:
            await message.answer("❌ Нельзя сбросить самого себя этой командой.")
            return

        if target_user.telegram_id in ADMIN_IDS or target_user.is_admin:
            await message.answer("❌ Нельзя сбрасывать администратора.")
            return

        target_tg = int(target_user.telegram_id)
        target_name = _display_name(target_user)

        await _wipe_user_account(session, target_user)
        await session.commit()

    await message.answer(
        "✅ <b>Игрок полностью сброшен.</b>\n\n"
        f"Игрок: {target_name}\n"
        "Аккаунт удалён из БД. Следующий /start создаст нового персонажа с нуля.",
        parse_mode="HTML",
    )

    try:
        await message.bot.send_message(
            target_tg,
            "🧹 <b>Твой аккаунт был сброшен администратором.</b>\n\n"
            "Напиши /start, чтобы начать заново.",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("resetme"))
async def cmd_reset_me(message: Message):
    args = message.text.split()[1:]
    if not args or args[0].strip().upper() != "CONFIRM":
        await message.answer(
            "⚠️ <b>Самосброс аккаунта</b>\n\n"
            "Эта команда полностью удаляет твой профиль из БД: карты, прогресс, статистику и инвентарь.\n"
            "Откатить это действие нельзя.\n\n"
            "Для подтверждения отправь:\n"
            "<code>/resetme CONFIRM</code>",
            parse_mode="HTML",
        )
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        target_user = result.scalar_one_or_none()
        if not target_user:
            await message.answer(
                "ℹ️ Профиль в БД не найден. Если ты еще не начинал игру, просто используй /start."
            )
            return

        await _wipe_user_account(session, target_user)
        await session.commit()

    await message.answer(
        "✅ <b>Аккаунт сброшен.</b>\n\n"
        "Твой профиль удален из базы. Напиши /start, чтобы начать игру с нуля.",
        parse_mode="HTML",
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("Использование: <code>/broadcast ТЕКСТ</code>", parse_mode="HTML")
        return

    text = args[1].strip()

    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    sent = 0
    failed = 0
    for user in users:
        try:
            await message.bot.send_message(
                user.telegram_id,
                f"📢 <b>Сообщение от администрации:</b>\n\n{text}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        "✅ Рассылка завершена!\n"
        f"Отправлено: {sent}\n"
        f"Не удалось: {failed}"
    )


@router.callback_query(F.data.in_({
    "admin_give_card",
    "admin_give_tech",
    "admin_give_currency",
    "admin_give_title",
    "admin_stats",
    "admin_settings",
}))
async def admin_panel_callback(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав администратора!", show_alert=True)
        return

    if callback.data == "admin_give_card":
        await callback.answer("/givecard @username Название_Карты [уровень]", show_alert=True)
        return

    if callback.data == "admin_give_tech":
        await callback.answer("/givetech @username Название_Техники", show_alert=True)
        return

    if callback.data == "admin_give_currency":
        await callback.answer("/givecurrency @username coins|points|exp количество", show_alert=True)
        return

    if callback.data == "admin_give_title":
        await callback.answer("/givetitle @username Название_Титула", show_alert=True)
        return

    if callback.data == "admin_stats":
        async with async_session() as session:
            users_count = await session.scalar(select(func.count(User.id))) or 0
            admins_count = await session.scalar(select(func.count(User.id)).where(User.is_admin.is_(True))) or 0
            battles_count = await session.scalar(select(func.count(Battle.id))) or 0

        await callback.answer(
            f"Игроков: {users_count} | Админов: {admins_count} | Боёв: {battles_count}",
            show_alert=True,
        )
        return

    if callback.data == "admin_settings":
        env_admins = ", ".join(str(admin_id) for admin_id in sorted(ADMIN_IDS)) or "не заданы"
        await callback.answer(
            f"ADMIN_IDS: {env_admins}",
            show_alert=True,
        )
        return
