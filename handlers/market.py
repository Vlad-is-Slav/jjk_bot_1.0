from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from config import MIN_PRICE, MAX_PRICE
from models import async_session, User, MarketListing, UserCard, Card, TradeOffer
from handlers.achievements import check_achievements

router = Router()

#      ( )
market_sell_price_inputs = {}  # telegram_id -> {"card_id": int, "created_at": datetime}
trade_create_state = {}  # telegram_id -> {"stage": str, ...}
TRADE_INPUT_TIMEOUT = timedelta(minutes=5)
SELL_INPUT_TIMEOUT = timedelta(minutes=5)

@router.message(Command("market"))
async def cmd_market(message: Message):
    """Команда /market"""
    await message.answer(
        "🏪 <b>Рынок</b>\n\n"
        "Нажми кнопку, чтобы открыть рынок.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏪 Открыть рынок", callback_data="market")]
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "market")
async def market_menu_callback(callback: CallbackQuery):
    """Меню рынка"""
    market_sell_price_inputs.pop(callback.from_user.id, None)
    trade_create_state.pop(callback.from_user.id, None)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Купить карту", callback_data="market_buy"),
            InlineKeyboardButton(text="📤 Продать карту", callback_data="market_sell")
        ],
        [
            InlineKeyboardButton(text="🔄 Обмен", callback_data="market_trade"),
            InlineKeyboardButton(text="📋 Мои лоты", callback_data="my_listings")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
        ]
    ])
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        await callback.message.edit_text(
            f"🏪 <b>Рынок Карт</b>\n\n"
            f"💰 Твои монеты: <b>{user.coins if user else 0}</b>\n\n"
            f"Здесь ты можешь:\n"
            f"🛒 Купить карты у других игроков\n"
            f"📤 Продать свои карты\n"
            f"🔄 Обмениваться картами",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "market_buy")
async def market_buy_callback(callback: CallbackQuery):
    """Показать лоты на продажу"""
    async with async_session() as session:
        result = await session.execute(
            select(MarketListing)
            .options(selectinload(MarketListing.seller))
            .where(MarketListing.sold == False)
            .order_by(desc(MarketListing.created_at))
            .limit(20)
        )
        listings = result.scalars().all()
        
        if not listings:
            await callback.message.edit_text(
                "🏪 <b>Рынок</b>\n\n"
                "Пока нет активных лотов.\n"
                "Загляни позже или продай свою карту!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="market")]
                ]),
                parse_mode="HTML"
            )
            return
        
        listings_text = "🏪 <b>Доступные карты:</b>\n\n"
        buttons = []
        
        for listing in listings:
            rarity_emoji = {
                "common": "⚪",
                "rare": "🔵",
                "epic": "🟣",
                "legendary": "🟡",
                "mythical": "🔴"
            }.get(listing.item_rarity, "⚪")

            listings_text += (
                f"{rarity_emoji} <b>{listing.item_name}</b> (Lv.{listing.item_level})\n"
                f"   💰 Цена: {listing.price} монет\n"
                f"   👤 Продавец: {listing.seller.first_name or 'Игрок'}\n\n"
            )

            buttons.append([
                InlineKeyboardButton(
                    text=f"🛒 Купить {listing.item_name[:15]} ({listing.price}🪙)",
                    callback_data=f"buy_listing_{listing.id}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market")])
        
        await callback.message.edit_text(
            listings_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("buy_listing_"))
async def buy_listing_callback(callback: CallbackQuery):
    """Купить лот"""
    listing_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        buyer = result.scalar_one_or_none()
        
        if not buyer:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        result = await session.execute(
            select(MarketListing)
            .options(selectinload(MarketListing.seller))
            .where(MarketListing.id == listing_id, MarketListing.sold == False)
        )
        listing = result.scalar_one_or_none()
        
        if not listing:
            await callback.answer("Лот не найден или уже продан!", show_alert=True)
            return
        
        if listing.seller_id == buyer.id:
            await callback.answer("Нельзя купить свой лот!", show_alert=True)
            return
        
        if buyer.coins < listing.price:
            await callback.answer("Недостаточно монет!", show_alert=True)
            return
        
        # Переводим монеты
        buyer.coins -= listing.price
        listing.seller.coins += listing.price
        
        # Передаем карту
        result = await session.execute(
            select(UserCard).where(UserCard.id == listing.item_id)
        )
        card = result.scalar_one_or_none()
        
        if card:
            card.user_id = buyer.id
            card.is_equipped = False
            card.slot_number = None
        
        # Обновляем лот
        listing.sold = True
        listing.sold_at = datetime.utcnow()
        listing.buyer_id = buyer.id
        
        await check_achievements(listing.seller_id, "market_sales", value=1, session=session)
        await check_achievements(listing.seller_id, "coins_collected", value=listing.seller.coins, absolute=True, session=session)

        result = await session.execute(
            select(func.count(UserCard.id)).where(UserCard.user_id == buyer.id)
        )
        card_count = int(result.scalar() or 0)
        await check_achievements(buyer.id, "cards_collected", value=card_count, absolute=True, session=session)
        await session.commit()
        
        await callback.answer(
            f"✅ Покупка совершена!\n\n"
            f"Карта: {listing.item_name}\n"
            f"Потрачено: {listing.price} монет",
            show_alert=True
        )
        
        await market_buy_callback(callback)

@router.callback_query(F.data == "market_sell")
async def market_sell_callback(callback: CallbackQuery):
    """Продать карту"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        market_sell_price_inputs.pop(callback.from_user.id, None)

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(
                UserCard.user_id == user.id,
                UserCard.is_equipped == False
            )
        )
        cards = result.scalars().all()
        
        if not cards:
            await callback.message.edit_text(
                "📤 <b>Продажа карты</b>\n\n"
                "У тебя нет неэкипированных карт для продажи.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="market")]
                ]),
                parse_mode="HTML"
            )
            return
        
        cards_text = "📤 <b>Выбери карту для продажи:</b>\n\n"
        buttons = []
        
        for card in cards:
            card_name = card.card_template.name if card.card_template else "Unknown"
            rarity = card.card_template.rarity if card.card_template else "common"
            
            rarity_emoji = {
                "common": "⚪",
                "rare": "🔵",
                "epic": "🟣",
                "legendary": "🟡",
                "mythical": "🔴"
            }.get(rarity, "⚪")
            
            cards_text += f"{rarity_emoji} {card_name} (Lv.{card.level})\n"
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"💰 Продать {card_name[:15]}",
                    callback_data=f"sell_card_{card.id}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market")])
        
        await callback.message.edit_text(
            cards_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("sell_card_"))
async def sell_card_price_callback(callback: CallbackQuery):
    """Установить цену продажи"""
    card_id = int(callback.data.split("_")[2])
    
    # Здесь нужно запросить цену у пользователя
    # Для простоты установим рекомендуемую цену
    
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
        
        # Рекомендуемая цена
        base_price = {
            "common": 100,
            "rare": 500,
            "epic": 2000,
            "legendary": 10000,
            "mythical": 50000
        }.get(card.card_template.rarity, 100)
        
        level_multiplier = 1 + (card.level - 1) * 0.1
        recommended_price = int(base_price * level_multiplier)
        

        market_sell_price_inputs[callback.from_user.id] = {
            "card_id": card.id,
            "created_at": datetime.utcnow(),
        }
        await callback.message.edit_text(
            f"💰 <b>Продажа карты</b>\n\n"
            f"Карта: <b>{card.card_template.name}</b>\n"
            f"Уровень: {card.level}\n"
            f"Редкость: {card.card_template.rarity}\n\n"
            f"Рекомендуемая цена: <b>{recommended_price}</b> монет\n\n"
            f"Отправь цену в чат (только число, {MIN_PRICE}-{MAX_PRICE}):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💰 По рекомендации ({recommended_price})", callback_data=f"confirm_sell_{card.id}_{recommended_price}")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="market_sell")]
            ]),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_sell_"))
async def confirm_sell_callback(callback: CallbackQuery):
    """Подтвердить продажу"""
    market_sell_price_inputs.pop(callback.from_user.id, None)
    parts = callback.data.split("_")
    card_id = int(parts[2])
    price = int(parts[3])
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == card_id, UserCard.user_id == user.id)
        )
        card = result.scalar_one_or_none()
        
        if not card:
            await callback.answer("Карта не найдена!", show_alert=True)
            return

        result = await session.execute(
            select(MarketListing).where(
                MarketListing.item_id == card.id,
                MarketListing.seller_id == user.id,
                MarketListing.sold == False
            )
        )
        existing_listing = result.scalar_one_or_none()
        if existing_listing:
            await callback.answer("Эта карта уже выставлена на рынок!", show_alert=True)
            return
        
        # Создаем лот
        listing = MarketListing(
            seller_id=user.id,
            listing_type="card",
            item_id=card.id,
            item_name=card.card_template.name,
            item_level=card.level,
            item_rarity=card.card_template.rarity,
            price=price
        )
        session.add(listing)
        await check_achievements(listing.seller_id, "market_sales", value=1, session=session)
        await check_achievements(listing.seller_id, "coins_collected", value=listing.seller.coins, absolute=True, session=session)

        result = await session.execute(
            select(func.count(UserCard.id)).where(UserCard.user_id == buyer.id)
        )
        card_count = int(result.scalar() or 0)
        await check_achievements(buyer.id, "cards_collected", value=card_count, absolute=True, session=session)
        await session.commit()
        
        await callback.answer(
            f"✅ Карта выставлена на продажу!\n\n"
            f"{card.card_template.name} - {price} монет",
            show_alert=True
        )
        
        await market_menu_callback(callback)


@router.callback_query(F.data == "my_listings")
async def my_listings_callback(callback: CallbackQuery):
    """Показать лоты текущего игрока"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(MarketListing)
            .where(MarketListing.seller_id == user.id)
            .order_by(desc(MarketListing.created_at))
            .limit(20)
        )
        listings = result.scalars().all()

        if not listings:
            await callback.message.edit_text(
                "📋 <b>Мои лоты</b>\n\n"
                "У тебя пока нет лотов на рынке.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="market")]
                ]),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        text = "📋 <b>Мои лоты</b>\n\n"
        for listing in listings:
            status = "✅ Продан" if listing.sold else "🟢 Активен"
            text += f"{status} {listing.item_name} (Lv.{listing.item_level}) - {listing.price}🪙\n"

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="market")]
            ]),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "market_trade")
async def market_trade_callback(callback: CallbackQuery):
    """Меню обмена картами"""
    market_sell_price_inputs.pop(callback.from_user.id, None)
    trade_create_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "🔄 <b>Обмен картами</b>\n\nВыбери действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать обмен", callback_data="trade_create")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="market")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


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


@router.message(
    F.text,
    ~F.text.startswith("/"),
    lambda message: message.from_user.id in market_sell_price_inputs
    or message.from_user.id in trade_create_state,
)
async def market_text_input_handler(message: Message):
    user_tg = message.from_user.id
    now = datetime.utcnow()

    sell_state = market_sell_price_inputs.get(user_tg)
    if sell_state:
        if now - sell_state.get("created_at", now) > SELL_INPUT_TIMEOUT:
            market_sell_price_inputs.pop(user_tg, None)
            return

        raw = (message.text or "").strip()
        try:
            price = int(raw)
        except (TypeError, ValueError):
            await message.answer("Отправь только число (цена).")
            return

        if price < MIN_PRICE or price > MAX_PRICE:
            await message.answer(
                f"Цена должна быть в диапазоне {MIN_PRICE}-{MAX_PRICE} монет."
            )
            return

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_tg)
            )
            user = result.scalar_one_or_none()
            if not user:
                market_sell_price_inputs.pop(user_tg, None)
                await message.answer("Сначала используй /start.")
                return

            result = await session.execute(
                select(UserCard)
                .options(selectinload(UserCard.card_template))
                .where(UserCard.id == sell_state["card_id"], UserCard.user_id == user.id)
            )
            card = result.scalar_one_or_none()
            if not card or not card.card_template:
                market_sell_price_inputs.pop(user_tg, None)
                await message.answer("Карта не найдена.")
                return

            if card.is_equipped:
                await message.answer("Сначала сними карту с экипировки.")
                return

            result = await session.execute(
                select(MarketListing).where(
                    MarketListing.item_id == card.id,
                    MarketListing.seller_id == user.id,
                    MarketListing.sold == False
                )
            )
            existing_listing = result.scalar_one_or_none()
            if existing_listing:
                await message.answer("Эта карта уже выставлена на рынке.")
                market_sell_price_inputs.pop(user_tg, None)
                return

            listing = MarketListing(
                seller_id=user.id,
                listing_type="card",
                item_id=card.id,
                item_name=card.card_template.name,
                item_level=card.level,
                item_rarity=card.card_template.rarity,
                price=price,
            )
            session.add(listing)
            await session.commit()

        market_sell_price_inputs.pop(user_tg, None)
        await message.answer(
            f"✅ Карта выставлена на продажу: {card.card_template.name} за {price} монет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏪 К рынку", callback_data="market")]
            ]),
            parse_mode="HTML",
        )
        return

    trade_state = trade_create_state.get(user_tg)
    if not trade_state:
        return

    if now - trade_state.get("created_at", now) > TRADE_INPUT_TIMEOUT:
        trade_create_state.pop(user_tg, None)
        return

    if trade_state.get("stage") != "await_target":
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_tg)
        )
        user = result.scalar_one_or_none()
        if not user:
            trade_create_state.pop(user_tg, None)
            await message.answer("Сначала используй /start.")
            return

        sender_card_id = trade_state.get("sender_card_id")
        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == sender_card_id, UserCard.user_id == user.id)
        )
        sender_card = result.scalar_one_or_none()
        if not sender_card or not sender_card.card_template:
            trade_create_state.pop(user_tg, None)
            await message.answer("Карта для обмена не найдена.")
            return

        if sender_card.is_equipped:
            trade_create_state.pop(user_tg, None)
            await message.answer("Сначала сними карту с экипировки.")
            return

        result = await session.execute(
            select(MarketListing).where(
                MarketListing.item_id == sender_card.id,
                MarketListing.sold == False
            )
        )
        if result.scalar_one_or_none():
            trade_create_state.pop(user_tg, None)
            await message.answer("Эта карта выставлена на рынке. Сними лот для обмена.")
            return

        target = await _find_user_by_target(session, message.text)
        if not target:
            await message.answer("Игрок не найден. Укажи @username или telegram_id.")
            return

        if target.id == user.id:
            await message.answer("Нельзя обмениваться с самим собой.")
            return

        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.user_id == target.id, UserCard.is_equipped == False)
        )
        target_cards = result.scalars().all()

        if not target_cards:
            await message.answer("У игрока нет доступных карт для обмена.")
            return

        result = await session.execute(
            select(MarketListing.item_id).where(
                MarketListing.seller_id == target.id,
                MarketListing.sold == False
            )
        )
        listed_ids = {row[0] for row in result}
        target_cards = [c for c in target_cards if c.id not in listed_ids]

        if not target_cards:
            await message.answer("У игрока нет доступных карт для обмена.")
            return

        trade_state["stage"] = "await_requested_card"
        trade_state["target_user_id"] = target.id
        trade_state["created_at"] = datetime.utcnow()

        text = (
            "🔄 <b>Выбери карту игрока для обмена:</b>\n\n"
            f"Игрок: {target.first_name or target.username or target.telegram_id}\n"
            f"Твоя карта: {sender_card.card_template.name}\n\n"
        )

        buttons = []
        for card in target_cards[:20]:
            card_name = card.card_template.name if card.card_template else "Unknown"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{card_name} (Lv.{card.level})",
                    callback_data=f"trade_request_{card.id}"
                )
            ])

        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="trade_cancel")])

        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "trade_create")
async def trade_create_callback(callback: CallbackQuery):
    """Создать обмен: выбор своей карты."""
    trade_create_state.pop(callback.from_user.id, None)
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
            .where(UserCard.user_id == user.id, UserCard.is_equipped == False)
        )
        cards = result.scalars().all()

        if not cards:
            await callback.message.edit_text(
                "🔄 <b>Обмен</b>\n\nУ тебя нет доступных карт для обмена.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="market_trade")]
                ]),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        result = await session.execute(
            select(MarketListing.item_id).where(
                MarketListing.seller_id == user.id,
                MarketListing.sold == False
            )
        )
        listed_ids = {row[0] for row in result}
        cards = [c for c in cards if c.id not in listed_ids]

        if not cards:
            await callback.message.edit_text(
                "🔄 <b>Обмен</b>\n\nУ тебя нет доступных карт для обмена.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="market_trade")]
                ]),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        text = "🔄 <b>Выбери свою карту для обмена:</b>\n\n"
        buttons = []
        for card in cards[:20]:
            card_name = card.card_template.name if card.card_template else "Unknown"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{card_name} (Lv.{card.level})",
                    callback_data=f"trade_offer_{card.id}"
                )
            ])

        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market_trade")])

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("trade_offer_"))
async def trade_offer_callback(callback: CallbackQuery):
    """Выбор своей карты для обмена."""
    card_id = int(callback.data.split("_")[2])

    trade_create_state[callback.from_user.id] = {
        "stage": "await_target",
        "sender_card_id": card_id,
        "created_at": datetime.utcnow(),
    }

    await callback.message.edit_text(
        "🔄 <b>Обмен</b>\n\nОтправь @username или telegram_id игрока для обмена.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="trade_cancel")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("trade_request_"))
async def trade_request_callback(callback: CallbackQuery):
    """Выбор карты соперника и создание оффера."""
    user_tg = callback.from_user.id
    trade_state = trade_create_state.get(user_tg)
    if not trade_state or trade_state.get("stage") != "await_requested_card":
        await callback.answer("Сначала создай обмен.", show_alert=True)
        return

    target_card_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_tg)
        )
        sender = result.scalar_one_or_none()
        if not sender:
            trade_create_state.pop(user_tg, None)
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        sender_card_id = trade_state.get("sender_card_id")
        target_user_id = trade_state.get("target_user_id")

        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == sender_card_id, UserCard.user_id == sender.id)
        )
        sender_card = result.scalar_one_or_none()

        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == target_card_id, UserCard.user_id == target_user_id)
        )
        target_card = result.scalar_one_or_none()

        if not sender_card or not target_card:
            trade_create_state.pop(user_tg, None)
            await callback.answer("Карты для обмена не найдены.", show_alert=True)
            return

        if sender_card.is_equipped or target_card.is_equipped:
            trade_create_state.pop(user_tg, None)
            await callback.answer("Сними карты с экипировки перед обменом.", show_alert=True)
            return

        result = await session.execute(
            select(MarketListing).where(
                MarketListing.item_id.in_([sender_card.id, target_card.id]),
                MarketListing.sold == False
            )
        )
        if result.scalar_one_or_none():
            trade_create_state.pop(user_tg, None)
            await callback.answer("Одна из карт выставлена на рынке.", show_alert=True)
            return

        offer = TradeOffer(
            sender_id=sender.id,
            receiver_id=target_user_id,
            sender_card_id=sender_card.id,
            requested_card_id=target_card.id,
            status="pending",
        )
        session.add(offer)
        await session.commit()

        trade_create_state.pop(user_tg, None)

        sender_name = sender.first_name or sender.username or "Игрок"
        result = await session.execute(
            select(User).where(User.id == target_user_id)
        )
        receiver_user = result.scalar_one_or_none()

        if receiver_user:
            try:
                await callback.bot.send_message(
                    receiver_user.telegram_id,
                    "🔄 <b>Новый обмен</b>\n\n"
                    f"{sender_name} предлагает карту: <b>{sender_card.card_template.name}</b>\n"
                    f"Взамен хочет: <b>{target_card.card_template.name}</b>\n\n"
                    "Принять обмен?",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Принять", callback_data=f"trade_accept_{offer.id}"),
                            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"trade_decline_{offer.id}"),
                        ]
                    ]),
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await callback.message.edit_text(
            "✅ Предложение обмена отправлено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="market_trade")]
            ]),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("trade_accept_"))
async def trade_accept_callback(callback: CallbackQuery):
    offer_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        result = await session.execute(
            select(TradeOffer)
            .where(TradeOffer.id == offer_id)
        )
        offer = result.scalar_one_or_none()
        if not offer or offer.status != "pending":
            await callback.answer("Обмен не найден.", show_alert=True)
            return

        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        receiver = result.scalar_one_or_none()
        if not receiver or receiver.id != offer.receiver_id:
            await callback.answer("Это не твой обмен.", show_alert=True)
            return

        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == offer.sender_card_id)
        )
        sender_card = result.scalar_one_or_none()

        result = await session.execute(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == offer.requested_card_id)
        )
        receiver_card = result.scalar_one_or_none()

        if not sender_card or not receiver_card:
            offer.status = "cancelled"
            offer.responded_at = datetime.utcnow()
            await session.commit()
            await callback.answer("Обмен отменён: карты не найдены.", show_alert=True)
            return

        if sender_card.is_equipped or receiver_card.is_equipped:
            offer.status = "cancelled"
            offer.responded_at = datetime.utcnow()
            await session.commit()
            await callback.answer("Обмен отменён: карта экипирована.", show_alert=True)
            return

        result = await session.execute(
            select(MarketListing).where(
                MarketListing.item_id.in_([sender_card.id, receiver_card.id]),
                MarketListing.sold == False
            )
        )
        if result.scalar_one_or_none():
            offer.status = "cancelled"
            offer.responded_at = datetime.utcnow()
            await session.commit()
            await callback.answer("Обмен отменён: карта на рынке.", show_alert=True)
            return

        if sender_card.user_id != offer.sender_id or receiver_card.user_id != offer.receiver_id:
            offer.status = "cancelled"
            offer.responded_at = datetime.utcnow()
            await session.commit()
            await callback.answer("Обмен отменён: владелец изменился.", show_alert=True)
            return

        # Обмен карт
        sender_card.user_id, receiver_card.user_id = receiver_card.user_id, sender_card.user_id
        sender_card.is_equipped = False
        receiver_card.is_equipped = False
        sender_card.slot_number = None
        receiver_card.slot_number = None

        offer.status = "accepted"
        offer.responded_at = datetime.utcnow()
        await session.commit()

        await callback.answer("✅ Обмен принят!")

        result = await session.execute(
            select(User).where(User.id == offer.sender_id)
        )
        sender = result.scalar_one_or_none()
        if sender:
            try:
                await callback.bot.send_message(
                    sender.telegram_id,
                    "✅ Обмен принят. Карты обменены.",
                )
            except Exception:
                pass


@router.callback_query(F.data.startswith("trade_decline_"))
async def trade_decline_callback(callback: CallbackQuery):
    offer_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        result = await session.execute(
            select(TradeOffer).where(TradeOffer.id == offer_id)
        )
        offer = result.scalar_one_or_none()
        if not offer or offer.status != "pending":
            await callback.answer("Обмен не найден.", show_alert=True)
            return

        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        receiver = result.scalar_one_or_none()
        if not receiver or receiver.id != offer.receiver_id:
            await callback.answer("Это не твой обмен.", show_alert=True)
            return

        offer.status = "declined"
        offer.responded_at = datetime.utcnow()
        await session.commit()

        await callback.answer("Обмен отклонён.")

        result = await session.execute(
            select(User).where(User.id == offer.sender_id)
        )
        sender = result.scalar_one_or_none()
        if sender:
            try:
                await callback.bot.send_message(
                    sender.telegram_id,
                    "❌ Обмен отклонён.",
                )
            except Exception:
                pass


@router.callback_query(F.data == "trade_cancel")
async def trade_cancel_callback(callback: CallbackQuery):
    trade_create_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "Обмен отменён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="market_trade")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()
