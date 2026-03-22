import html
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from models import async_session, User, UserCard, UserProfile, UserQuote, UserAchievement, Title
from utils.achievement_data import ACHIEVEMENTS
from keyboards import get_profile_menu, get_deck_keyboard, get_difficulty_menu
from utils.card_rewards import (
    is_character_template,
    is_weapon_template,
    is_shikigami_template,
    is_pact_template,
)
from utils.weapon_effects import get_weapon_effect
from utils.pact_effects import get_pact_effect
from utils.quote_rewards import ensure_quotes_for_owned_cards

router = Router()
PROFILE_PAGE_SIZE = 6
QUOTE_PAGE_SIZE = 5
CARD_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp")
CARD_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "cards"
TOJI_TOKENS = ("тоджи", "toji")
AVATAR_UPLOAD_TIMEOUT = timedelta(minutes=5)
profile_avatar_upload_waiting: dict[int, datetime] = {}


def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _is_toji_name(name: str) -> bool:
    normalized = _normalize_name(name)
    return any(token in normalized for token in TOJI_TOKENS)


def _is_shikigami_or_weapon(card_template) -> bool:
    return is_shikigami_template(card_template) or is_weapon_template(card_template)


async def _get_or_create_user_profile(session, user_id: int) -> UserProfile:
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile_settings = result.scalars().first()
    if profile_settings:
        return profile_settings

    profile_settings = UserProfile(user_id=user_id)
    session.add(profile_settings)
    await session.flush()
    return profile_settings


async def _load_profile_state(session, user: User):
    profile_settings = await _get_or_create_user_profile(session, user.id)
    avatar_card = None
    changed = False

    if profile_settings.avatar_card_id:
        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(
                UserCard.id == profile_settings.avatar_card_id,
                UserCard.user_id == user.id,
            )
        )
        avatar_card = result.scalar_one_or_none()

        if (
            not avatar_card
            or not avatar_card.card_template
            or not is_character_template(avatar_card.card_template)
        ):
            profile_settings.avatar_card_id = None
            avatar_card = None
            changed = True

    favorite_quote = (profile_settings.favorite_quote or "").strip() or None
    return profile_settings, avatar_card, favorite_quote, changed


def _quote_preview(quote: str, max_len: int = 80) -> str:
    if len(quote) <= max_len:
        return quote
    return quote[: max_len - 1].rstrip() + "…"


def _card_image_variants(card_name: str) -> list[str]:
    base = (card_name or "").strip()
    if not base:
        return []

    normalized_space = " ".join(base.split())
    variants = {
        normalized_space,
        normalized_space.replace(" ", "_"),
        normalized_space.replace(" ", "-"),
        normalized_space.replace("ё", "е").replace("Ё", "Е"),
    }
    variants.update({
        name.replace(" ", "_")
        for name in list(variants)
    })
    variants.update({
        name.replace(" ", "-")
        for name in list(variants)
    })
    return [name for name in variants if name]


def _resolve_avatar_image_path(avatar_card: UserCard | None) -> Path | None:
    if not avatar_card or not avatar_card.card_template:
        return None
    if not CARD_ASSETS_DIR.exists():
        return None

    for base_name in _card_image_variants(avatar_card.card_template.name):
        for ext in CARD_IMAGE_EXTENSIONS:
            candidate = CARD_ASSETS_DIR / f"{base_name}.{ext}"
            if candidate.exists():
                return candidate
    return None


def _profile_customization_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🖼 Выбрать аватар", callback_data="profile_avatar_menu_0"),
                InlineKeyboardButton(text="💬 Выбрать цитату", callback_data="profile_quote_menu_0"),
            ],
            [
                InlineKeyboardButton(text="📷 Загрузить аватар", callback_data="profile_avatar_upload"),
            ],
            [
                InlineKeyboardButton(text="♻️ Сбросить аватар", callback_data="profile_avatar_clear"),
                InlineKeyboardButton(text="♻️ Сбросить цитату", callback_data="profile_quote_clear"),
            ],
            [InlineKeyboardButton(text="🏷 Титулы", callback_data="my_titles")],
            [InlineKeyboardButton(text="🔙 В профиль", callback_data="profile")],
        ]
    )


async def _render_profile_customization(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        granted_quotes = await ensure_quotes_for_owned_cards(session, user.id)
        profile_settings, avatar_card, favorite_quote, changed = await _load_profile_state(session, user)
        if granted_quotes or changed:
            await session.commit()

        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.user_id == user.id)
        )
        all_cards = result.scalars().all()
        character_count = len([card for card in all_cards if card.card_template and is_character_template(card.card_template)])

        result = await session.execute(
            select(UserQuote).where(UserQuote.user_id == user.id)
        )
        unlocked_quotes = result.scalars().all()

        has_custom_avatar = bool(profile_settings.avatar_file_id)
        avatar_name = (
            "Загруженный"
            if has_custom_avatar
            else (avatar_card.card_template.name if avatar_card and avatar_card.card_template else "Стандартный")
        )
        quote_text = f"«{html.escape(_quote_preview(favorite_quote))}»" if favorite_quote else "не выбрана"
        avatar_image_path = _resolve_avatar_image_path(avatar_card)
        avatar_file_status = "загружен" if has_custom_avatar else ("найден" if avatar_image_path else "не найден")

        text = (
            "🖼️ <b>Оформление профиля</b>\n\n"
            "Здесь можно менять только безопасные элементы:\n"
            "• аватар только из твоих карт-персонажей\n"
            "• цитату только из открытых цитат\n\n"
            f"🖼 Текущий аватар: <b>{html.escape(avatar_name)}</b>\n"
            f"💬 Текущая цитата: {quote_text}\n\n"
            f"🎴 Доступно карт-персонажей: <b>{character_count}</b>\n"
            f"📜 Открыто цитат: <b>{len(unlocked_quotes)}</b>\n"
            f"🗂 Файл аватара: <b>{avatar_file_status}</b>"
        )

        await callback.message.edit_text(
            text,
            reply_markup=_profile_customization_keyboard(),
            parse_mode="HTML",
        )


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Команда /profile"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Сначала используй /start")
            return

        profile_settings, avatar_card, favorite_quote, changed = await _load_profile_state(session, user)
        if changed:
            await session.commit()

        result = await session.execute(
            select(func.count(UserAchievement.id)).where(
                UserAchievement.user_id == user.id,
                UserAchievement.completed == True,
            )
        )
        completed_achievements = int(result.scalar() or 0)
        total_achievements = len(ACHIEVEMENTS)

        title_line = "Без титула"
        if user.equipped_title_id:
            result = await session.execute(
                select(Title).where(Title.id == user.equipped_title_id)
            )
            title = result.scalar_one_or_none()
            if title:
                title_line = f"{title.icon} {title.name}"

        has_custom_avatar = bool(profile_settings.avatar_file_id)
        avatar_name = (
            "Загруженный"
            if has_custom_avatar
            else (avatar_card.card_template.name if avatar_card and avatar_card.card_template else "Стандартный")
        )
        quote_line = f"«{html.escape(_quote_preview(favorite_quote))}»" if favorite_quote else "не выбрана"
        avatar_image_path = _resolve_avatar_image_path(avatar_card)
        avatar_file_line = "есть" if (has_custom_avatar or avatar_image_path) else "не найден"

        profile_text = (
            f"👤 <b>Профиль: {user.first_name or 'Маг'}</b>\n\n"
            f"⭐ Уровень: {user.level}\n"
            f"📈 Опыт: {user.experience}/{user.experience_to_next}\n"
            f"💎 Очки: {user.points}\n"
            f"🪙 Монеты: {user.coins}\n\n"
            f"🏆 Достижения: {completed_achievements}/{total_achievements}\n"
            f"👑 Титул: {title_line}\n\n"
            f"🖼 Аватар: {html.escape(avatar_name)}\n"
            f"💬 Цитата: {quote_line}\n"
            f"🗂 Файл аватара: {avatar_file_line}"
        )

        if profile_settings.avatar_file_id:
            await message.answer_photo(
                profile_settings.avatar_file_id,
                caption=profile_text,
                reply_markup=get_profile_menu(),
                parse_mode="HTML",
            )
        elif avatar_image_path:
            await message.answer_photo(
                FSInputFile(avatar_image_path),
                caption=profile_text,
                reply_markup=get_profile_menu(),
                parse_mode="HTML",
            )
        else:
            await message.answer(profile_text, reply_markup=get_profile_menu(), parse_mode="HTML")

@router.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    """Профиль игрока"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        # Получаем экипированные карты
        main_card = None
        weapon_card = None
        shikigami_card = None
        pact_card_1 = None
        pact_card_2 = None

        if user.slot_1_card_id:
            result = await session.execute(
                select(UserCard)
                .options(selectinload(UserCard.card_template))
                .where(UserCard.id == user.slot_1_card_id)
            )
            main_card = result.scalar_one_or_none()
            if main_card and main_card.card_template:
                main_card.recalculate_stats()

        if user.slot_2_card_id:
            result = await session.execute(
                select(UserCard)
                .options(selectinload(UserCard.card_template))
                .where(UserCard.id == user.slot_2_card_id)
            )
            weapon_card = result.scalar_one_or_none()
            if weapon_card and weapon_card.card_template:
                weapon_card.recalculate_stats()

        if user.slot_3_card_id:
            result = await session.execute(
                select(UserCard)
                .options(selectinload(UserCard.card_template))
                .where(UserCard.id == user.slot_3_card_id)
            )
            shikigami_card = result.scalar_one_or_none()
            if shikigami_card and shikigami_card.card_template:
                shikigami_card.recalculate_stats()

        if user.slot_4_card_id:
            result = await session.execute(
                select(UserCard)
                .options(selectinload(UserCard.card_template))
                .where(UserCard.id == user.slot_4_card_id)
            )
            pact_card_1 = result.scalar_one_or_none()
            if pact_card_1 and pact_card_1.card_template:
                pact_card_1.recalculate_stats()

        if user.slot_5_card_id:
            result = await session.execute(
                select(UserCard)
                .options(selectinload(UserCard.card_template))
                .where(UserCard.id == user.slot_5_card_id)
            )
            pact_card_2 = result.scalar_one_or_none()
            if pact_card_2 and pact_card_2.card_template:
                pact_card_2.recalculate_stats()

        # Рассчитываем общую силу
        total_power = 0
        for card in (main_card, weapon_card, shikigami_card, pact_card_1, pact_card_2):
            if card:
                total_power += card.get_total_power()
        
        
        result = await session.execute(
            select(func.count(UserAchievement.id)).where(
                UserAchievement.user_id == user.id,
                UserAchievement.completed == True,
            )
        )
        completed_achievements = int(result.scalar() or 0)
        total_achievements = len(ACHIEVEMENTS)

        title_line = "Без титула"
        if user.equipped_title_id:
            result = await session.execute(
                select(Title).where(Title.id == user.equipped_title_id)
            )
            title = result.scalar_one_or_none()
            if title:
                title_line = f"{title.icon} {title.name}"
        profile_text = (
            f"👤 <b>Профиль: {user.first_name or 'Маг'}</b>\n"
            f"@{user.username or 'Нет username'}\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"⭐ Уровень: {user.level}\n"
            f"📈 Опыт: {user.experience}/{user.experience_to_next}\n"
            f"💎 Очки: {user.points}\n"
            f"💪 Общая сила: {total_power}\n"
            f"🏆 Достижения: {completed_achievements}/{total_achievements}\n"
            f"🏷 Титул: {html.escape(title_line)}\n"
            f"⚔️ <b>Боевая статистика:</b>\n"
            f"🏆 PvP побед: {user.pvp_wins}\n"
            f"💀 PvP поражений: {user.pvp_losses}\n"
            f"📊 Winrate: {user.get_win_rate()}%\n"
            f"👹 PvE побед: {user.pve_wins}\n"
            f"📊 Всего боев: {user.total_battles}\n\n"
            f"🎴 <b>Колода:</b>\n"
        )
        
        if main_card and main_card.card_template:
            profile_text += f"👑 {main_card.card_template.name} (Lv.{main_card.level})\n"
        else:
            profile_text += "👑 Не выбрано\n"

        if weapon_card and weapon_card.card_template:
            profile_text += f"🗡️ {weapon_card.card_template.name} (Lv.{weapon_card.level})\n"
        else:
            profile_text += "🗡️ Не выбрано\n"

        if shikigami_card and shikigami_card.card_template:
            profile_text += f"🐺 {shikigami_card.card_template.name} (Lv.{shikigami_card.level})\n"
        else:
            profile_text += "🐺 Не выбрано\n"

        if pact_card_1 and pact_card_1.card_template:
            profile_text += f"📜 {pact_card_1.card_template.name} (Lv.{pact_card_1.level})\n"
        else:
            profile_text += "📜 Пакт 1: не выбран\n"

        if pact_card_2 and pact_card_2.card_template:
            profile_text += f"📜 {pact_card_2.card_template.name} (Lv.{pact_card_2.level})\n"
        else:
            profile_text += "📜 Пакт 2: не выбран\n"

        profile_settings, avatar_card, favorite_quote, changed = await _load_profile_state(session, user)
        if changed:
            await session.commit()

        result = await session.execute(
            select(func.count(UserAchievement.id)).where(
                UserAchievement.user_id == user.id,
                UserAchievement.completed == True,
            )
        )
        completed_achievements = int(result.scalar() or 0)
        total_achievements = len(ACHIEVEMENTS)

        title_line = "Без титула"
        if user.equipped_title_id:
            result = await session.execute(
                select(Title).where(Title.id == user.equipped_title_id)
            )
            title = result.scalar_one_or_none()
            if title:
                title_line = f"{title.icon} {title.name}"

        has_custom_avatar = bool(profile_settings.avatar_file_id)
        avatar_name = (
            "Загруженный"
            if has_custom_avatar
            else (avatar_card.card_template.name if avatar_card and avatar_card.card_template else "Стандартный")
        )
        quote_line = f"«{html.escape(_quote_preview(favorite_quote))}»" if favorite_quote else "не выбрана"
        avatar_image_path = _resolve_avatar_image_path(avatar_card)
        avatar_file_line = "есть" if (has_custom_avatar or avatar_image_path) else "не найден"
        profile_text += (
            "\n🖼 <b>Оформление:</b>\n"
            f"Аватар: {html.escape(avatar_name)}\n"
            f"Цитата: {quote_line}\n"
            f"Файл аватара: {avatar_file_line}"
        )

        await callback.message.edit_text(profile_text, reply_markup=get_profile_menu(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "profile_stats")
async def profile_stats_callback(callback: CallbackQuery):
    """Детальная статистика"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        stats_text = (
            f"📊 <b>Детальная статистика</b>\n\n"
            f"<b>Основное:</b>\n"
            f"⭐ Уровень: {user.level}\n"
            f"📈 Опыт: {user.experience}/{user.experience_to_next}\n"
            f"💎 Очки: {user.points}\n"
            f"📅 Зарегистрирован: {user.created_at.strftime('%d.%m.%Y') if user.created_at else 'Неизвестно'}\n\n"
            f"<b>PvP:</b>\n"
            f"🏆 Побед: {user.pvp_wins}\n"
            f"💀 Поражений: {user.pvp_losses}\n"
            f"📊 Winrate: {user.get_win_rate()}%\n\n"
            f"<b>PvE:</b>\n"
            f"👹 Побед: {user.pve_wins}\n"
            f"💀 Поражений: {user.pve_losses}\n\n"
            f"<b>Общее:</b>\n"
            f"⚔️ Всего боев: {user.total_battles}"
        )
        
        from keyboards.main_menu import get_back_button
        await callback.message.edit_text(stats_text, reply_markup=get_back_button("profile"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "my_deck")
async def my_deck_callback(callback: CallbackQuery):
    """Моя колода"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        # Получаем экипированные карты
        main_card = None
        weapon_card = None
        shikigami_card = None
        pact_card_1 = None
        pact_card_2 = None

        if user.slot_1_card_id:
            result = await session.execute(
                select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.id == user.slot_1_card_id)
            )
            main_card = result.scalar_one_or_none()
            if main_card and main_card.card_template:
                main_card.recalculate_stats()

        if user.slot_2_card_id:
            result = await session.execute(
                select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.id == user.slot_2_card_id)
            )
            weapon_card = result.scalar_one_or_none()
            if weapon_card and weapon_card.card_template:
                weapon_card.recalculate_stats()

        if user.slot_3_card_id:
            result = await session.execute(
                select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.id == user.slot_3_card_id)
            )
            shikigami_card = result.scalar_one_or_none()
            if shikigami_card and shikigami_card.card_template:
                shikigami_card.recalculate_stats()

        if user.slot_4_card_id:
            result = await session.execute(
                select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.id == user.slot_4_card_id)
            )
            pact_card_1 = result.scalar_one_or_none()
            if pact_card_1 and pact_card_1.card_template:
                pact_card_1.recalculate_stats()

        if user.slot_5_card_id:
            result = await session.execute(
                select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.id == user.slot_5_card_id)
            )
            pact_card_2 = result.scalar_one_or_none()
            if pact_card_2 and pact_card_2.card_template:
                pact_card_2.recalculate_stats()

        deck_text = "🎴 <b>Моя колода</b>\n\n"

        if main_card and main_card.card_template:
            deck_text += (
                f"👑 <b>Главный персонаж:</b>\n"
                f"{main_card.card_template.name} (Lv.{main_card.level})\n"
                f"❤️ HP: {main_card.max_hp} | ⚔️ АТК: {main_card.attack}\n"
                f"🛡️ ЗЩТ: {main_card.defense} | 💨 СКР: {main_card.speed}\n\n"
            )
        else:
            deck_text += "👑 <b>Главный персонаж:</b> Не выбран\n\n"

        if weapon_card and weapon_card.card_template:
            effect = get_weapon_effect(weapon_card)
            effect_line = f"Эффект: {effect.get('label')}\n" if effect else ""
            deck_text += (
                f"🗡️ <b>Оружие:</b>\n"
                f"{weapon_card.card_template.name} (Lv.{weapon_card.level})\n"
                f"{effect_line}\n"
            )
        else:
            deck_text += "🗡️ <b>Оружие:</b> Не выбрано\n\n"

        if shikigami_card and shikigami_card.card_template:
            deck_text += (
                f"🐺 <b>Шикигами:</b>\n"
                f"{shikigami_card.card_template.name} (Lv.{shikigami_card.level})\n"
                f"❤️ HP: {shikigami_card.max_hp} | ⚔️ АТК: {shikigami_card.attack}\n"
                f"🛡️ ЗЩТ: {shikigami_card.defense} | 💨 СКР: {shikigami_card.speed}\n\n"
            )
        else:
            deck_text += "🐺 <b>Шикигами:</b> Не выбран\n\n"

        if pact_card_1 and pact_card_1.card_template:
            effect = get_pact_effect(pact_card_1)
            effect_line = f"Эффект: {effect.get('label')}\n" if effect else ""
            deck_text += (
                f"📜 <b>Пакт 1:</b>\n"
                f"{pact_card_1.card_template.name} (Lv.{pact_card_1.level})\n"
                f"{effect_line}\n"
            )
        else:
            deck_text += "📜 <b>Пакт 1:</b> Не выбран\n\n"

        if pact_card_2 and pact_card_2.card_template:
            effect = get_pact_effect(pact_card_2)
            effect_line = f"Эффект: {effect.get('label')}\n" if effect else ""
            deck_text += (
                f"📜 <b>Пакт 2:</b>\n"
                f"{pact_card_2.card_template.name} (Lv.{pact_card_2.level})\n"
                f"{effect_line}\n"
            )
        else:
            deck_text += "📜 <b>Пакт 2:</b> Не выбран\n\n"

        if any([main_card, weapon_card, shikigami_card, pact_card_1, pact_card_2]):
            total_power = 0
            for card in (main_card, weapon_card, shikigami_card, pact_card_1, pact_card_2):
                if card:
                    total_power += card.get_total_power()
            deck_text += f"💪 <b>Общая сила колоды:</b> {total_power}"

        await callback.message.edit_text(
            deck_text,
            reply_markup=get_deck_keyboard(main_card, weapon_card, shikigami_card, pact_card_1, pact_card_2),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("select_main_card"))
async def select_main_card_callback(callback: CallbackQuery):
    """Выбор главной карты"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        # Получаем все карты пользователя
        result = await session.execute(
            select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.user_id == user.id)
        )
        cards = result.scalars().all()
        
        # Фильтруем только персонажей
        character_cards = [c for c in cards if c.card_template and is_character_template(c.card_template)]
        
        if not character_cards:
            await callback.answer("У тебя нет карт персонажей!", show_alert=True)
            return
        
        from keyboards.cards import get_card_selection_keyboard
        await callback.message.edit_text(
            "👑 <b>Выбери главного персонажа:</b>",
            reply_markup=get_card_selection_keyboard(character_cards, "main"),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("select_weapon_card"))
async def select_weapon_card_callback(callback: CallbackQuery):
    """Выбор оружия"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.user_id == user.id)
        )
        cards = result.scalars().all()

        weapon_cards = [c for c in cards if c.card_template and is_weapon_template(c.card_template)]
        if not weapon_cards:
            await callback.answer("У тебя нет оружия!", show_alert=True)
            return

        from keyboards.cards import get_card_selection_keyboard
        await callback.message.edit_text(
            "🗡️ <b>Выбери оружие:</b>",
            reply_markup=get_card_selection_keyboard(cards, "weapon"),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("select_shikigami_card"))
async def select_shikigami_card_callback(callback: CallbackQuery):
    """Выбор шикигами"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.user_id == user.id)
        )
        cards = result.scalars().all()

        main_card = None
        if user.slot_1_card_id:
            result = await session.execute(
                select(UserCard)
                .options(selectinload(UserCard.card_template))
                .where(UserCard.id == user.slot_1_card_id)
            )
            main_card = result.scalar_one_or_none()

        is_toji = bool(main_card and main_card.card_template and _is_toji_name(main_card.card_template.name))
        slot_type = "shikigami_weapon" if is_toji else "shikigami"

        if is_toji:
            shikigami_cards = [
                c for c in cards
                if c.card_template and _is_shikigami_or_weapon(c.card_template)
            ]
            if not shikigami_cards:
                await callback.answer("У тебя нет шикигами или оружия для второго слота!", show_alert=True)
                return
        else:
            shikigami_cards = [c for c in cards if c.card_template and is_shikigami_template(c.card_template)]
            if not shikigami_cards:
                await callback.answer("У тебя нет шикигами!", show_alert=True)
                return

        from keyboards.cards import get_card_selection_keyboard
        await callback.message.edit_text(
            "🐺 <b>Выбери шикигами:</b>" if not is_toji else "🗡️🐺 <b>Выбери шикигами или оружие:</b>",
            reply_markup=get_card_selection_keyboard(cards, slot_type),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("select_pact1_card"))


async def select_pact1_card_callback(callback: CallbackQuery):
    """Выбор пакта для 1 слота"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.user_id == user.id)
        )
        cards = result.scalars().all()

        pact_cards = [c for c in cards if c.card_template and is_pact_template(c.card_template)]
        if not pact_cards:
            await callback.answer("У тебя нет пактов!", show_alert=True)
            return

        from keyboards.cards import get_card_selection_keyboard
        await callback.message.edit_text(
            "📜 <b>Выбери пакт (слот 1):</b>",
            reply_markup=get_card_selection_keyboard(cards, "pact1"),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("select_pact2_card"))
async def select_pact2_card_callback(callback: CallbackQuery):
    """Выбор пакта для 2 слота"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.user_id == user.id)
        )
        cards = result.scalars().all()

        pact_cards = [c for c in cards if c.card_template and is_pact_template(c.card_template)]
        if not pact_cards:
            await callback.answer("У тебя нет пактов!", show_alert=True)
            return

        from keyboards.cards import get_card_selection_keyboard
        await callback.message.edit_text(
            "📜 <b>Выбери пакт (слот 2):</b>",
            reply_markup=get_card_selection_keyboard(cards, "pact2"),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("select_card_"))
async def confirm_card_selection_callback(callback: CallbackQuery):
    """Подтверждение выбора карты"""
    parts = callback.data.split("_")
    slot_type = parts[2]
    card_id = int(parts[3])
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        # Проверяем, что карта принадлежит пользователю
        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == card_id, UserCard.user_id == user.id)
        )
        card = result.scalar_one_or_none()
        
        if not card:
            await callback.answer("Карта не найдена!", show_alert=True)
            return
        
        slot_config = {
            "main": ("slot_1_card_id", 1, is_character_template, "Главный персонаж выбран!"),
            "weapon": ("slot_2_card_id", 2, is_weapon_template, "Оружие выбрано!"),
            "shikigami": ("slot_3_card_id", 3, is_shikigami_template, "Шикигами выбран!"),
            "shikigami_weapon": ("slot_3_card_id", 3, _is_shikigami_or_weapon, "Шикигами/оружие выбраны!"),
            "pact1": ("slot_4_card_id", 4, is_pact_template, "Пакт 1 выбран!"),
            "pact2": ("slot_5_card_id", 5, is_pact_template, "Пакт 2 выбран!"),
        }

        if slot_type not in slot_config:
            await callback.answer("Некорректный слот.", show_alert=True)
            return
        if slot_type == "shikigami_weapon":
            main_card = None
            if user.slot_1_card_id:
                result = await session.execute(
                    select(UserCard)
                    .options(selectinload(UserCard.card_template))
                    .where(UserCard.id == user.slot_1_card_id)
                )
                main_card = result.scalar_one_or_none()

            is_toji = bool(main_card and main_card.card_template and _is_toji_name(main_card.card_template.name))
            if not is_toji:
                await callback.answer("Этот слот доступен только для Тоджи.", show_alert=True)
                return

        slot_attr, slot_number, validator, success_text = slot_config[slot_type]
        if not card.card_template or not validator(card.card_template):
            await callback.answer("Эта карта не подходит для выбранного слота.", show_alert=True)
            return

        # Снимаем экипировку с предыдущей карты в выбранном слоте
        old_slot_card_id = getattr(user, slot_attr)
        if old_slot_card_id and old_slot_card_id != card.id:
            result = await session.execute(
                select(UserCard).where(UserCard.id == old_slot_card_id)
            )
            old_card = result.scalar_one_or_none()
            if old_card:
                old_card.is_equipped = False
                old_card.slot_number = None

        # Если карта уже экипирована в другом слоте — снимаем её
        if card.is_equipped and card.slot_number:
            if card.slot_number == 1:
                user.slot_1_card_id = None
            elif card.slot_number == 2:
                user.slot_2_card_id = None
            elif card.slot_number == 3:
                user.slot_3_card_id = None
            elif card.slot_number == 4:
                user.slot_4_card_id = None
            elif card.slot_number == 5:
                user.slot_5_card_id = None
            card.is_equipped = False
            card.slot_number = None

        # Экипируем новую карту
        card.is_equipped = True
        card.slot_number = slot_number
        setattr(user, slot_attr, card_id)

        await session.commit()

        await callback.answer(success_text)
        
        # Обновляем отображение колоды
        await my_deck_callback(callback)


@router.callback_query(F.data.startswith("select_page_"))
async def select_page_callback(callback: CallbackQuery):
    """Пагинация выбора карты для слота"""
    parts = callback.data.split("_")
    slot_type = parts[2]
    page = int(parts[3])

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(UserCard).options(selectinload(UserCard.card_template)).where(UserCard.user_id == user.id)
        )
        cards = result.scalars().all()

        from keyboards.cards import get_card_selection_keyboard
        title_map = {
            "main": "👑 <b>Выбери главного персонажа:</b>",
            "weapon": "🗡️ <b>Выбери оружие:</b>",
            "shikigami": "🐺 <b>Выбери шикигами:</b>",
            "shikigami_weapon": "🗡️🐺 <b>Выбери шикигами или оружие:</b>",
            "pact1": "📜 <b>Выбери пакт (слот 1):</b>",
            "pact2": "📜 <b>Выбери пакт (слот 2):</b>",
        }
        title = title_map.get(slot_type, "🎴 <b>Выбери карту:</b>")
        await callback.message.edit_text(
            title,
            reply_markup=get_card_selection_keyboard(cards, slot_type, page),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("unequip_card_"))
async def unequip_card_callback(callback: CallbackQuery):
    """Снять карту"""
    card_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        result = await session.execute(
            select(UserCard).where(UserCard.id == card_id, UserCard.user_id == user.id)
        )
        card = result.scalar_one_or_none()
        
        if card:
            card.is_equipped = False
            card.slot_number = None
            
            if user.slot_1_card_id == card_id:
                user.slot_1_card_id = None
            elif user.slot_2_card_id == card_id:
                user.slot_2_card_id = None
            elif user.slot_3_card_id == card_id:
                user.slot_3_card_id = None
            elif user.slot_4_card_id == card_id:
                user.slot_4_card_id = None
            elif user.slot_5_card_id == card_id:
                user.slot_5_card_id = None
            
            await session.commit()
            await callback.answer("Карта снята!")
        
        await my_deck_callback(callback)

@router.callback_query(F.data == "difficulty_menu")
async def difficulty_menu_callback(callback: CallbackQuery):
    """Меню выбора сложности"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        diff_emojis = {
            "easy": "🟢",
            "normal": "🔵",
            "hard": "🟠",
            "hardcore": "🔴"
        }
        
        current = diff_emojis.get(user.difficulty, "🔵")
        
        await callback.message.edit_text(
            f"⚙️ <b>Уровень Сложности</b>\n\n"
            f"Текущий: {current} <b>{user.difficulty.upper()}</b>\n"
            f"Множитель наград: {user.get_difficulty_multiplier()}x\n\n"
            f"🟢 <b>Легкий</b> - 0.5x награды, нет штрафов\n"
            f"🔵 <b>Нормальный</b> - 1x награды (стандарт)\n"
            f"🟠 <b>Сложный</b> - 1.5x награды, сильные враги\n"
            f"🔴 <b>Хардкор</b> - 2x награды, смерть = конец\n\n"
            f"Выбери новый уровень:",
            reply_markup=get_difficulty_menu(),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("set_difficulty_"))
async def set_difficulty_callback(callback: CallbackQuery):
    """Установить уровень сложности"""
    difficulty = callback.data.split("_")[2]
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        user.difficulty = difficulty
        user.hardcore_mode = (difficulty == "hardcore")
        
        await session.commit()
        
        await callback.answer(f"Сложность изменена на {difficulty.upper()}!")
        await difficulty_menu_callback(callback)


def _profile_avatar_keyboard(cards: list[UserCard], current_avatar_id: int | None, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(cards) + PROFILE_PAGE_SIZE - 1) // PROFILE_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PROFILE_PAGE_SIZE
    end = start + PROFILE_PAGE_SIZE
    page_cards = cards[start:end]

    rows = []
    for card in page_cards:
        if not card.card_template:
            continue
        marker = "✅ " if current_avatar_id == card.id else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker}{card.card_template.name} (Lv.{card.level})",
                    callback_data=f"profile_set_avatar_{card.id}_{page}",
                )
            ]
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"profile_avatar_menu_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"profile_avatar_menu_{page + 1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton(text="♻️ Сбросить аватар", callback_data="profile_avatar_clear")])
    rows.append([InlineKeyboardButton(text="🔙 К оформлению", callback_data="profile_customization")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _profile_quotes_keyboard(quotes: list[UserQuote], selected_quote: str | None, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(quotes) + QUOTE_PAGE_SIZE - 1) // QUOTE_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * QUOTE_PAGE_SIZE
    end = start + QUOTE_PAGE_SIZE
    page_quotes = quotes[start:end]

    rows = []
    for quote in page_quotes:
        marker = "✅ " if selected_quote and selected_quote == quote.quote_text else ""
        preview = _quote_preview(quote.quote_text, max_len=50)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker}{preview}",
                    callback_data=f"profile_set_quote_{quote.id}_{page}",
                )
            ]
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"profile_quote_menu_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"profile_quote_menu_{page + 1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton(text="♻️ Сбросить цитату", callback_data="profile_quote_clear")])
    rows.append([InlineKeyboardButton(text="🔙 К оформлению", callback_data="profile_customization")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_avatar_menu(callback: CallbackQuery, page: int):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        profile_settings, _, _, changed = await _load_profile_state(session, user)
        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.user_id == user.id)
        )
        all_cards = result.scalars().all()
        character_cards = [card for card in all_cards if card.card_template and is_character_template(card.card_template)]
        character_cards.sort(key=lambda card: (card.level, card.id), reverse=True)

        if changed:
            await session.commit()

        if not character_cards:
            await callback.answer("У тебя нет карт персонажей для аватарки.", show_alert=True)
            await _render_profile_customization(callback)
            return

        current_avatar_name = "Стандартный"
        if profile_settings.avatar_file_id:
            current_avatar_name = "Загруженный"
        elif profile_settings.avatar_card_id:
            current_avatar = next((c for c in character_cards if c.id == profile_settings.avatar_card_id), None)
            if current_avatar and current_avatar.card_template:
                current_avatar_name = current_avatar.card_template.name

        await callback.message.edit_text(
            "🖼 <b>Выбор аватара</b>\n\n"
            "Можно поставить только персонажа, который уже есть у тебя в инвентаре.\n\n"
            f"Текущий аватар: <b>{html.escape(current_avatar_name)}</b>\n"
            f"Доступно персонажей: <b>{len(character_cards)}</b>",
            reply_markup=_profile_avatar_keyboard(character_cards, profile_settings.avatar_card_id, page),
            parse_mode="HTML",
        )


async def _render_quote_menu(callback: CallbackQuery, page: int):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        granted_quotes = await ensure_quotes_for_owned_cards(session, user.id)
        profile_settings, _, _, changed = await _load_profile_state(session, user)
        result = await session.execute(
            select(UserQuote)
            .where(UserQuote.user_id == user.id)
            .order_by(UserQuote.obtained_at.desc(), UserQuote.id.desc())
        )
        quotes = result.scalars().all()

        if granted_quotes or changed:
            await session.commit()

        if not quotes:
            await callback.answer("Пока нет открытых цитат. Получай карты и уровни.", show_alert=True)
            await _render_profile_customization(callback)
            return

        selected_quote = (profile_settings.favorite_quote or "").strip() or None
        selected_preview = html.escape(_quote_preview(selected_quote)) if selected_quote else "не выбрана"

        await callback.message.edit_text(
            "💬 <b>Выбор цитаты</b>\n\n"
            "Выбери одну из открытых цитат. Свой текст вводить нельзя.\n\n"
            f"Текущая цитата: {selected_preview if selected_quote else 'не выбрана'}\n"
            f"Открыто цитат: <b>{len(quotes)}</b>",
            reply_markup=_profile_quotes_keyboard(quotes, selected_quote, page),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "profile_customization")
async def profile_customization_callback(callback: CallbackQuery):
    await _render_profile_customization(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("profile_avatar_menu_"))
async def profile_avatar_menu_callback(callback: CallbackQuery):
    try:
        page = int(callback.data.rsplit("_", 1)[1])
    except ValueError:
        page = 0
    await _render_avatar_menu(callback, page)
    await callback.answer()


@router.callback_query(F.data.startswith("profile_set_avatar_"))
async def profile_set_avatar_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Некорректный выбор аватара.", show_alert=True)
        return

    try:
        card_id = int(parts[3])
        page = int(parts[4])
    except ValueError:
        await callback.answer("Некорректный выбор аватара.", show_alert=True)
        return

    async with async_session() as session:
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
            .where(UserCard.id == card_id, UserCard.user_id == user.id)
        )
        selected_card = result.scalar_one_or_none()
        if not selected_card or not selected_card.card_template or not is_character_template(selected_card.card_template):
            await callback.answer("Для аватара можно выбрать только свою карту персонажа.", show_alert=True)
            return

        profile_settings = await _get_or_create_user_profile(session, user.id)
        profile_settings.avatar_card_id = selected_card.id
        profile_settings.avatar_file_id = None
        profile_settings.avatar_file_unique_id = None
        await session.commit()

    await _render_avatar_menu(callback, page)
    await callback.answer("Аватар обновлён.")


@router.callback_query(F.data == "profile_avatar_clear")
async def profile_avatar_clear_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        profile_settings = await _get_or_create_user_profile(session, user.id)
        profile_settings.avatar_card_id = None
        profile_settings.avatar_file_id = None
        profile_settings.avatar_file_unique_id = None
        await session.commit()

    await _render_profile_customization(callback)
    await callback.answer("Аватар сброшен.")


@router.callback_query(F.data == "profile_avatar_upload")
async def profile_avatar_upload_callback(callback: CallbackQuery):
    profile_avatar_upload_waiting[callback.from_user.id] = datetime.utcnow()
    await callback.message.edit_text(
        "📷 <b>Загрузка аватара</b>\n\n"
        "Отправь фото, которое хочешь использовать как аватар.\n"
        "Поддерживаются обычные изображения (не документы).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="profile_avatar_upload_cancel")],
        ]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "profile_show_avatar")
async def profile_show_avatar_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        profile_settings, avatar_card, _, changed = await _load_profile_state(session, user)
        if changed:
            await session.commit()

        if profile_settings.avatar_file_id:
            await callback.bot.send_photo(
                callback.from_user.id,
                profile_settings.avatar_file_id,
                caption=f"🖼 <b>Аватар {html.escape(user.first_name or 'Игрок')}</b>",
                parse_mode="HTML",
            )
            await callback.answer()
            return

        avatar_image_path = _resolve_avatar_image_path(avatar_card)
        if avatar_image_path:
            await callback.bot.send_photo(
                callback.from_user.id,
                FSInputFile(avatar_image_path),
                caption=f"🖼 <b>Аватар {html.escape(user.first_name or 'Игрок')}</b>",
                parse_mode="HTML",
            )
            await callback.answer()
            return

        await callback.answer("Аватар не установлен.", show_alert=True)


@router.callback_query(F.data == "profile_avatar_upload_cancel")
async def profile_avatar_upload_cancel_callback(callback: CallbackQuery):
    profile_avatar_upload_waiting.pop(callback.from_user.id, None)
    await _render_profile_customization(callback)
    await callback.answer("Загрузка отменена.")


@router.message(F.photo, lambda message: message.from_user.id in profile_avatar_upload_waiting)
async def profile_avatar_upload_message(message: Message):
    created_at = profile_avatar_upload_waiting.get(message.from_user.id)
    if not created_at:
        return
    if datetime.utcnow() - created_at > AVATAR_UPLOAD_TIMEOUT:
        profile_avatar_upload_waiting.pop(message.from_user.id, None)
        await message.answer("Время ожидания истекло. Попробуй снова через меню профиля.")
        return

    photo = message.photo[-1]
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("Сначала используй /start")
            return

        profile_settings = await _get_or_create_user_profile(session, user.id)
        profile_settings.avatar_file_id = photo.file_id
        profile_settings.avatar_file_unique_id = photo.file_unique_id
        profile_settings.avatar_card_id = None
        await session.commit()

    profile_avatar_upload_waiting.pop(message.from_user.id, None)
    await message.answer("✅ Аватар обновлён!")


@router.message(F.document, lambda message: message.from_user.id in profile_avatar_upload_waiting)
async def profile_avatar_upload_document(message: Message):
    created_at = profile_avatar_upload_waiting.get(message.from_user.id)
    if not created_at:
        return
    if datetime.utcnow() - created_at > AVATAR_UPLOAD_TIMEOUT:
        profile_avatar_upload_waiting.pop(message.from_user.id, None)
        await message.answer(
            "Время ожидания истекло. Попробуй снова через меню профиля."
        )
        return

    document = message.document
    if not document or not (document.mime_type or "").startswith("image/"):
        await message.answer("Пожалуйста, отправь изображение файлом.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("Сначала используй /start")
            return

        profile_settings = await _get_or_create_user_profile(session, user.id)
        profile_settings.avatar_file_id = document.file_id
        profile_settings.avatar_file_unique_id = document.file_unique_id
        profile_settings.avatar_card_id = None
        await session.commit()

    profile_avatar_upload_waiting.pop(message.from_user.id, None)
    await message.answer("✅ Аватар обновлён!")


@router.callback_query(F.data.startswith("profile_quote_menu_"))
async def profile_quote_menu_callback(callback: CallbackQuery):
    try:
        page = int(callback.data.rsplit("_", 1)[1])
    except ValueError:
        page = 0
    await _render_quote_menu(callback, page)
    await callback.answer()


@router.callback_query(F.data.startswith("profile_set_quote_"))
async def profile_set_quote_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Некорректный выбор цитаты.", show_alert=True)
        return

    try:
        quote_id = int(parts[3])
        page = int(parts[4])
    except ValueError:
        await callback.answer("Некорректный выбор цитаты.", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(UserQuote).where(UserQuote.id == quote_id, UserQuote.user_id == user.id)
        )
        selected_quote = result.scalar_one_or_none()
        if not selected_quote:
            await callback.answer("Цитата недоступна.", show_alert=True)
            return

        profile_settings = await _get_or_create_user_profile(session, user.id)
        profile_settings.favorite_quote = selected_quote.quote_text
        await session.commit()

    await _render_quote_menu(callback, page)
    await callback.answer("Цитата обновлена.")


@router.callback_query(F.data == "profile_quote_clear")
async def profile_quote_clear_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        profile_settings = await _get_or_create_user_profile(session, user.id)
        profile_settings.favorite_quote = None
        await session.commit()

    await _render_profile_customization(callback)
    await callback.answer("Цитата сброшена.")
