from aiogram import Router, F

from pathlib import Path

from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from models import async_session, User, UserCard, UserTechnique, MarketListing, TradeOffer, UserProfile
from keyboards import get_inventory_menu, get_card_list_keyboard, get_card_detail_keyboard, get_upgrade_keyboard, get_back_button
from config import (
    STAT_UPGRADE_COST,
    STAT_UPGRADE_VALUES,
    DOMAIN_DOT_PER_POINT,
    DOMAIN_DAMAGE_BONUS_PER_POINT,
    RCT_HEAL_BONUS_PER_POINT,
)
from utils.card_rewards import (
    get_card_data_by_name,
    is_character_template,
    is_support_template,
    is_weapon_template,
    is_pact_template,
    is_shikigami_template,
)
from utils.weapon_effects import get_weapon_effect
from utils.pact_effects import get_pact_effect
from utils.card_images import resolve_card_image_source
from utils.daily_quest_progress import add_daily_quest_progress
from handlers.achievements import check_achievements

router = Router()


async def _render_inventory_message(
    callback: CallbackQuery,
    text: str,
    reply_markup,
    photo_source: str | Path | None = None,
):
    chat_id = callback.message.chat.id
    current_has_photo = bool(getattr(callback.message, "photo", None))

    if photo_source:
        try:
            await callback.message.delete()
        except Exception:
            pass

        photo = FSInputFile(photo_source) if isinstance(photo_source, Path) else photo_source
        await callback.bot.send_photo(
            chat_id,
            photo,
            caption=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return

    if current_has_photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.bot.send_message(
            chat_id,
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return

    await callback.message.edit_text(
        text,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )

@router.message(Command("inventory"))
async def cmd_inventory(message: Message):
    """Команда /inventory"""
    await message.answer(
        "🎒 <b>инвентарь</b>\n\n"
        "Выбери категорию:",
        reply_markup=get_inventory_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """Пустой callback для неактивных кнопок"""
    await callback.answer()

@router.callback_query(F.data == "inventory")
async def inventory_callback(callback: CallbackQuery):
    """инвентарь"""
    await _render_inventory_message(
        callback,
        "🎒 <b>инвентарь</b>\n\n"
        "Выбери категорию:",
        reply_markup=get_inventory_menu(),
    )
    await callback.answer()

@router.callback_query(F.data == "all_cards")
async def all_cards_callback(callback: CallbackQuery):
    """Все карты"""
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
            .where(UserCard.user_id == user.id)
            .order_by(UserCard.level.desc())
        )
        cards = result.scalars().all()
        
        if not cards:
            await _render_inventory_message(
                callback,
                "🎒 <b>У тебя пока нет карт!</b>\n\n"
                "Сражайся на арене, чтобы получить новые карты.",
                reply_markup=get_inventory_menu(),
            )
            return
        
        await _render_inventory_message(
            callback,
            f"🎴 <b>Твои карты ({len(cards)}):</b>\n\n"
            "Выбери карту для просмотра:",
            reply_markup=get_card_list_keyboard(list(cards)),
        )
    await callback.answer()

@router.callback_query(F.data.startswith("cards_page_"))
async def cards_page_callback(callback: CallbackQuery):
    """Пагинация списка карт"""
    page = int(callback.data.split("_")[2])
    
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
            .where(UserCard.user_id == user.id)
            .order_by(UserCard.level.desc())
        )
        cards = result.scalars().all()
        
        await _render_inventory_message(
            callback,
            f"🎴 <b>Твои карты ({len(cards)}):</b>\n\n"
            "Выбери карту для просмотра:",
            reply_markup=get_card_list_keyboard(list(cards), page),
        )
    await callback.answer()

@router.callback_query(F.data.startswith("card_detail_"))
async def card_detail_callback(callback: CallbackQuery):
    """Детали карты"""
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
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == card_id, UserCard.user_id == user.id)
        )
        card = result.scalar_one_or_none()
        
        if not card or not card.card_template:
            await callback.answer("Карта не найдена!", show_alert=True)
            return
        card.recalculate_stats()
        card_data = get_card_data_by_name(card.card_template.name) or {}

        rarity_emojis = {
            "common": "⚪",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡",
            "mythical": "🔴"
        }
        
        rarity = card.card_template.rarity
        emoji = rarity_emojis.get(rarity, "⚪")
        
        card_text = (
            f"{emoji} <b>{card.card_template.name}</b>\n"
            f" : {rarity.upper()}\n"
            f" : {card.level}\n"
            f" : {card.get_total_power()}\n\n"
            f"<i>{card.card_template.description}</i>\n\n"
            f"❤️: {card.max_hp}\n"
            f"⚔️: {card.attack}\n"
            f"🛡️: {card.defense}\n"
            f"💨: {card.speed}\n"
            f" CE: {card.max_ce}\n"
            f"  CE: {card.get_ce_regen()}\n"
        )

        effect = get_weapon_effect(card)
        if effect:
            card_text += f"⚙️ Эффект оружия: {effect.get('label', '')}\n"

        pact_effect = get_pact_effect(card)
        if pact_effect:
            card_text += f"📜 Эффект пакта: {pact_effect.get('label', '')}\n"

        if is_character_template(card.card_template):
            innate_technique = (
                getattr(card.card_template, "innate_technique", None)
                or card_data.get("innate_technique")
            )
            if innate_technique:
                card_text += f"✨ Врождённая техника: {innate_technique}\n"

            domain_name = card_data.get("domain_name")
            if domain_name:
                card_text += f"🏯 Территория: {domain_name}\n"

            abilities = card.get_abilities()
            if not abilities:
                fallback_abilities = card_data.get("abilities") or []
                if isinstance(fallback_abilities, str):
                    abilities = [fallback_abilities]
                else:
                    abilities = list(fallback_abilities)
            if abilities:
                ability_names = []
                for ability in abilities:
                    if isinstance(ability, dict):
                        name = ability.get("name")
                    else:
                        name = str(ability)
                    if name:
                        ability_names.append(name)
                if ability_names:
                    card_text += f"🌀 Способности: {', '.join(ability_names)}\n"

            card_text += (
                f"🏯 Домен: Lv.{card.domain_level or 0}\n"
                f"♻️ ОПТ: Lv.{card.rct_level or 0}\n"
            )

        card_text += "\n"
        
        if card.is_equipped:
            slot_names = {
                1: "Главный",
                2: "Оружие",
                3: "Шикигами",
                4: "Пакт 1",
                5: "Пакт 2",
            }
            slot_name = slot_names.get(card.slot_number, "Слот")
            card_text += f"✅ <b>Экипировано</b> ({slot_name})\n"

        can_upgrade = not (is_weapon_template(card.card_template) or is_pact_template(card.card_template))
        if can_upgrade:
            card_text += f"⬆️ Стоимость прокачки: {STAT_UPGRADE_COST} очко"
        else:
            card_text += "🔒 Прокачка недоступна для этого типа карты"

        photo_source = resolve_card_image_source(card.card_template, card_data)
        await _render_inventory_message(
            callback,
            card_text,
            reply_markup=get_card_detail_keyboard(card_id, card.is_equipped, can_upgrade=can_upgrade),
            photo_source=photo_source,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("salvage_card_"))
async def salvage_card_callback(callback: CallbackQuery):
    """Подтверждение утилизации карты."""
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
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == card_id, UserCard.user_id == user.id)
        )
        card = result.scalar_one_or_none()

        if not card or not card.card_template:
            await callback.answer("Карта не найдена!", show_alert=True)
            return

        result = await session.execute(
            select(MarketListing).where(
                MarketListing.listing_type == "card",
                MarketListing.item_id == card.id,
                MarketListing.seller_id == user.id,
                MarketListing.sold == False
            )
        )
        active_listing = result.scalar_one_or_none()
        if active_listing:
            await callback.answer("Эта карта выставлена на рынке. Сними лот перед утилизацией.", show_alert=True)
            return

        result = await session.execute(
            select(TradeOffer).where(
                TradeOffer.status == "pending",
                or_(
                    (TradeOffer.sender_id == user.id) & (TradeOffer.sender_card_id == card.id),
                    (TradeOffer.receiver_id == user.id) & (TradeOffer.requested_card_id == card.id),
                )
            )
        )
        active_trade = result.scalar_one_or_none()
        if active_trade:
            await callback.answer("Эта карта участвует в активном обмене. Отмени обмен перед утилизацией.", show_alert=True)
            return

        warning = "♻️ <b>Утилизировать карту</b>\n\n"
        warning += f"Ты собираешься удалить карту <b>{card.card_template.name}</b> (Lv.{card.level}).\n"
        if card.is_equipped:
            warning += "Карта сейчас экипирована и будет снята.\n"
        warning += "\n⚠️ Это действие нельзя отменить."

        confirm_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Утилизировать", callback_data=f"confirm_salvage_{card.id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"card_detail_{card.id}")],
            ]
        )

        await _render_inventory_message(
            callback,
            warning,
            reply_markup=confirm_keyboard,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_salvage_"))
async def confirm_salvage_callback(callback: CallbackQuery):
    """Утилизация карты."""
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
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == card_id, UserCard.user_id == user.id)
        )
        card = result.scalar_one_or_none()

        if not card or not card.card_template:
            await callback.answer("Карта не найдена!", show_alert=True)
            return

        result = await session.execute(
            select(MarketListing).where(
                MarketListing.listing_type == "card",
                MarketListing.item_id == card.id,
                MarketListing.seller_id == user.id,
                MarketListing.sold == False
            )
        )
        active_listing = result.scalar_one_or_none()
        if active_listing:
            await callback.answer("Эта карта выставлена на рынке. Сними лот перед утилизацией.", show_alert=True)
            return

        result = await session.execute(
            select(TradeOffer).where(
                TradeOffer.status == "pending",
                or_(
                    (TradeOffer.sender_id == user.id) & (TradeOffer.sender_card_id == card.id),
                    (TradeOffer.receiver_id == user.id) & (TradeOffer.requested_card_id == card.id),
                )
            )
        )
        active_trade = result.scalar_one_or_none()
        if active_trade:
            await callback.answer("Эта карта участвует в активном обмене. Отмени обмен перед утилизацией.", show_alert=True)
            return

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

        result = await session.execute(
            select(UserProfile).where(UserProfile.user_id == user.id)
        )
        profile = result.scalar_one_or_none()
        if profile and profile.avatar_card_id == card.id:
            profile.avatar_card_id = None

        await session.delete(card)
        await session.commit()

        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.user_id == user.id)
            .order_by(UserCard.level.desc())
        )
        cards = result.scalars().all()

        if not cards:
            await _render_inventory_message(
                callback,
                "✅ <b>Карта утилизирована.</b>\n\n"
                "🎒 <b>У тебя пока нет карт!</b>\n\n"
                "Сражайся на арене, чтобы получить новые карты.",
                reply_markup=get_inventory_menu(),
            )
        else:
            await _render_inventory_message(
                callback,
                f"✅ <b>Карта утилизирована.</b>\n\n"
                f"🎴 <b>Твои карты ({len(cards)}):</b>\n\n"
                "Выбери карту для просмотра:",
                reply_markup=get_card_list_keyboard(list(cards)),
            )
    await callback.answer()

@router.callback_query(F.data.startswith("upgrade_card_"))
async def upgrade_card_callback(callback: CallbackQuery):
    """Меню прокачки карты"""
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
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == card_id, UserCard.user_id == user.id)
        )
        card = result.scalar_one_or_none()
        
        if not card:
            await callback.answer("Карта не найдена!", show_alert=True)
            return

        if card.card_template and (is_weapon_template(card.card_template) or is_pact_template(card.card_template)):
            await callback.answer("Эта карта не прокачивается.", show_alert=True)
            return
        
        can_upgrade = user.points >= STAT_UPGRADE_COST
        
        upgrade_text = (
            f"⬆️ <b>Прокачка карты</b>\n\n"
            f"🎴 {card.card_template.name} (Lv.{card.level})\n\n"
            f"📊 <b>Текущие характеристики:</b>\n"
            f"❤️ HP: {card.max_hp}\n"
            f"⚔️ Атака: {card.attack}\n"
            f"🛡️ Защита: {card.defense}\n"
            f"💨 Скорость: {card.speed}\n"
            f" CE: {card.max_ce}\n"
            f"  CE: {card.get_ce_regen()}\n\n"
            f"💎 <b>Твои очки:</b> {user.points}\n"
            f"💰 <b>Стоимость:</b> {STAT_UPGRADE_COST} очко\n\n"
        )
        
        upgrade_text += (
            "📈 <b>Доступные улучшения (за 1 очко):</b>\n"
            f"⚔️ Атака: +{STAT_UPGRADE_VALUES['attack']}\n"
            f"🛡️ Защита: +{STAT_UPGRADE_VALUES['defense']}\n"
            f"💨 Скорость: +{STAT_UPGRADE_VALUES['speed']}\n"
            f"❤️ HP: +{STAT_UPGRADE_VALUES['hp']}\n"
            f"💧 CE: +{STAT_UPGRADE_VALUES['ce']}\n"
            f"  CE: +{STAT_UPGRADE_VALUES['ce_regen']}\n"
        )

        if is_character_template(card.card_template):
            domain_pct = int(DOMAIN_DOT_PER_POINT * 1000) / 10
            dmg_pct = int(DOMAIN_DAMAGE_BONUS_PER_POINT * 1000) / 10
            rct_pct = int(RCT_HEAL_BONUS_PER_POINT * 100)
            upgrade_text += (
                f"🏯 Домен: +{domain_pct}% DOT и +{dmg_pct}% к урону\n"
                f"♻️ ОПТ: +{rct_pct}% к исцелению\n"
            )

        if not can_upgrade:
            upgrade_text += "\n❌ <b>Недостаточно очков!</b>"
        
        await _render_inventory_message(
            callback,
            upgrade_text,
            reply_markup=get_upgrade_keyboard(card_id, user.points, is_character_template(card.card_template)),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("equip_card_"))
async def equip_card_callback(callback: CallbackQuery):
    """Быстро экипировать карту в подходящий слот"""
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
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == card_id, UserCard.user_id == user.id)
        )
        card = result.scalar_one_or_none()

        if not card or not card.card_template:
            await callback.answer("Карта не найдена!", show_alert=True)
            return

        slot_attr = None
        slot_number = None
        slot_label = None

        if is_character_template(card.card_template):
            slot_attr = "slot_1_card_id"
            slot_number = 1
            slot_label = "главный слот"
        elif is_weapon_template(card.card_template):
            slot_attr = "slot_2_card_id"
            slot_number = 2
            slot_label = "слот оружия"
        elif is_shikigami_template(card.card_template):
            slot_attr = "slot_3_card_id"
            slot_number = 3
            slot_label = "слот шикигами"
        elif is_pact_template(card.card_template):
            if not user.slot_4_card_id:
                slot_attr = "slot_4_card_id"
                slot_number = 4
                slot_label = "пакт 1"
            elif not user.slot_5_card_id:
                slot_attr = "slot_5_card_id"
                slot_number = 5
                slot_label = "пакт 2"
            else:
                slot_attr = "slot_4_card_id"
                slot_number = 4
                slot_label = "пакт 1"
        else:
            await callback.answer("Эту карту нельзя экипировать в колоду.", show_alert=True)
            return

        old_slot_card_id = getattr(user, slot_attr)
        if old_slot_card_id and old_slot_card_id != card.id:
            result = await session.execute(
                select(UserCard).where(UserCard.id == old_slot_card_id, UserCard.user_id == user.id)
            )
            old_card = result.scalar_one_or_none()
            if old_card:
                old_card.is_equipped = False
                old_card.slot_number = None

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

        card.is_equipped = True
        card.slot_number = slot_number
        setattr(user, slot_attr, card.id)

        await session.commit()

        await callback.answer(f"Карта экипирована в {slot_label}!")
        await card_detail_callback(callback)

@router.callback_query(F.data.startswith("confirm_upgrade_"))
async def confirm_upgrade_callback(callback: CallbackQuery):
    """Подтверждение прокачки"""
    await callback.answer("спользуй кнопки характеристик для прокачки.", show_alert=True)


@router.callback_query(F.data.startswith("upgrade_stat_"))
async def upgrade_stat_callback(callback: CallbackQuery):
    """Прокачка конкретного стата"""
    parts = callback.data.split("_", 3)
    if len(parts) < 4:
        await callback.answer("Некорректная команда.", show_alert=True)
        return

    try:
        card_id = int(parts[2])
    except ValueError:
        await callback.answer("Некорректная карта.", show_alert=True)
        return

    stat = parts[3]

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
        card = result.scalar_one_or_none()

        if not card or not card.card_template:
            await callback.answer("Карта не найдена!", show_alert=True)
            return

        if user.points < STAT_UPGRADE_COST:
            await callback.answer("Недостаточно очков!", show_alert=True)
            return

        if stat in ("domain", "rct") and not is_character_template(card.card_template):
            await callback.answer("Эти улучшения доступны только для персонажей.", show_alert=True)
            return

        amount = STAT_UPGRADE_VALUES.get(stat)
        if stat in ("domain", "rct"):
            amount = 1

        if amount is None:
            await callback.answer("Неизвестный стат.", show_alert=True)
            return

        if not card.apply_stat_upgrade(stat, amount):
            await callback.answer("Не удалось улучшить стат.", show_alert=True)
            return

        user.points -= STAT_UPGRADE_COST
        await add_daily_quest_progress(session, user.id, "upgrade_cards", amount=1)
        result = await session.execute(
            select(func.max(UserCard.level)).where(UserCard.user_id == user.id)
        )
        max_level = int(result.scalar() or 0)
        await check_achievements(user.id, "card_max_level", value=max_level, absolute=True, session=session)
        await session.commit()

        await callback.answer("✅ Стат улучшен!", show_alert=True)
        await card_detail_callback(callback)
@router.callback_query(F.data == "character_cards")
async def character_cards_callback(callback: CallbackQuery):
    """Только карты персонажей"""
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
            .where(UserCard.user_id == user.id)
            .order_by(UserCard.level.desc())
        )
        cards = result.scalars().all()
        
        character_cards = [c for c in cards if c.card_template and is_character_template(c.card_template)]
        
        if not character_cards:
            await _render_inventory_message(
                callback,
                "🎴 <b>У тебя нет карт персонажей!</b>\n\n"
                "Сражайся на арене, чтобы получить их.",
                reply_markup=get_inventory_menu(),
            )
            return
        
        await _render_inventory_message(
            callback,
            f"⭐ <b>Карты персонажей ({len(character_cards)}):</b>\n\n"
            "Выбери карту для просмотра:",
            reply_markup=get_card_list_keyboard(
                character_cards,
                page_callback_prefix="character_page",
                back_callback="inventory",
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("character_page_"))
async def character_cards_page_callback(callback: CallbackQuery):
    """Пагинация списка карт персонажей"""
    page = int(callback.data.split("_")[2])

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
            .where(UserCard.user_id == user.id)
            .order_by(UserCard.level.desc())
        )
        cards = result.scalars().all()

        character_cards = [c for c in cards if c.card_template and is_character_template(c.card_template)]

        await _render_inventory_message(
            callback,
            f"⭐ <b>Карты персонажей ({len(character_cards)}):</b>\n\n"
            "Выбери карту для просмотра:",
            reply_markup=get_card_list_keyboard(
                character_cards,
                page,
                page_callback_prefix="character_page",
                back_callback="inventory",
            ),
        )
    await callback.answer()

@router.callback_query(F.data == "support_cards")
async def support_cards_callback(callback: CallbackQuery):
    """Только карты поддержки"""
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
            .where(UserCard.user_id == user.id)
            .order_by(UserCard.level.desc())
        )
        cards = result.scalars().all()
        
        support_cards = [c for c in cards if c.card_template and is_support_template(c.card_template)]
        
        if not support_cards:
            await _render_inventory_message(
                callback,
                "🛡️ <b>У тебя нет карт поддержки!</b>\n\n"
                "Сражайся на арене, чтобы получить их.",
                reply_markup=get_inventory_menu(),
            )
            return
        
        await _render_inventory_message(
            callback,
            f"🛡️ <b>Карты поддержки ({len(support_cards)}):</b>\n\n"
            "Выбери карту для просмотра:",
            reply_markup=get_card_list_keyboard(
                support_cards,
                page_callback_prefix="support_page",
                back_callback="inventory",
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("support_page_"))
async def support_cards_page_callback(callback: CallbackQuery):
    """Пагинация списка карт поддержки"""
    page = int(callback.data.split("_")[2])

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
            .where(UserCard.user_id == user.id)
            .order_by(UserCard.level.desc())
        )
        cards = result.scalars().all()

        support_cards = [c for c in cards if c.card_template and is_support_template(c.card_template)]

        await _render_inventory_message(
            callback,
            f"🛡️ <b>Карты поддержки ({len(support_cards)}):</b>\n\n"
            "Выбери карту для просмотра:",
            reply_markup=get_card_list_keyboard(
                support_cards,
                page,
                page_callback_prefix="support_page",
                back_callback="inventory",
            ),
        )
    await callback.answer()

@router.callback_query(F.data == "my_techniques")
async def my_techniques_callback(callback: CallbackQuery):
    """Показать техники пользователя"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        result = await session.execute(
            select(UserTechnique)
            .options(selectinload(UserTechnique.technique))
            .where(UserTechnique.user_id == user.id)
        )
        techniques = result.scalars().all()
        
        if not techniques:
            await _render_inventory_message(
                callback,
                "✨ <b>У тебя пока нет техник!</b>\n\n"
                "Посещай Техникум, чтобы получить новые техники.",
                reply_markup=get_back_button("inventory"),
            )
            return
        
        tech_text = "✨ <b>Твои техники:</b>\n\n"
        
        for ut in techniques:
            tech = ut.technique
            status = "✅" if ut.is_equipped else ""
            tech_text += (
                f"{status} {tech.icon} <b>{tech.name}</b> (Lv.{ut.level})\n"
                f"   Тип: {tech.technique_type}\n"
                f"   Редкость: {tech.rarity}\n\n"
            )
        
        await _render_inventory_message(
            callback,
            tech_text,
            reply_markup=get_back_button("inventory"),
        )
    await callback.answer()
