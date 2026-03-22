from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from models import async_session, User
from keyboards import get_main_menu
from utils.card_rewards import grant_random_card
from config import ADMIN_IDS

router = Router()
pending_feedback_users: set[int] = set()

@router.message(Command("start"))
async def cmd_start(message: Message):
    pending_feedback_users.discard(message.from_user.id)
    """Обработчик команды /start"""
    async with async_session() as session:
        # Проверяем, есть ли пользователь в БД
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        is_new_user = False
        starter_card = None
        
        if not user:
            # Создаем нового пользователя
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
            session.add(user)
            await session.flush()  # Получаем ID пользователя
            
            # Выдаем стартовую карту-персонажа
            user_card = await grant_random_card(session, user.id, only_characters=True, level=1)
            user_card.is_equipped = True
            user_card.slot_number = 1
            await session.flush()
            
            user.slot_1_card_id = user_card.id
            
            await session.commit()
            
            is_new_user = True
            starter_card = user_card.card_template
        
        # Приветственное сообщение
        if is_new_user:
            rarity_emojis = {
                "common": "⚪",
                "rare": "🔵",
                "epic": "🟣",
                "legendary": "🟡",
                "mythical": "🔴"
            }
            rarity = starter_card.rarity
            emoji = rarity_emojis.get(rarity, "⚪")
            
            welcome_text = (
                f"🎌 <b>Добро пожаловать в мир Магической Битвы!</b>\n\n"
                f"Ты стал магом и получаешь свою первую карту:\n\n"
                f"{emoji} <b>{starter_card.name}</b>\n"
                f"📊 Редкость: {rarity.upper()}\n"
                f"❤️ HP: {starter_card.base_hp}\n"
                f"⚔️ Атака: {starter_card.base_attack}\n"
                f"🛡️ Защита: {starter_card.base_defense}\n"
                f"💨 Скорость: {starter_card.base_speed}\n\n"
                f"<i>{starter_card.description}</i>\n\n"
                f"Используй меню ниже, чтобы начать своё путешествие!"
            )
        else:
            welcome_text = (
                f"👋 <b>С возвращением, {user.first_name or 'Маг'}!</b>\n\n"
                f"📊 Уровень: {user.level}\n"
                f"⭐ Опыт: {user.experience}/{user.experience_to_next}\n"
                f"💎 Очки: {user.points}\n\n"
                f"Выбери действие в меню ниже:"
            )
        
        await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="HTML")

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    pending_feedback_users.discard(callback.from_user.id)
    """Возврат в главное меню"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            text = (
                f"👋 <b>Привет, {user.first_name or 'Маг'}!</b>\n\n"
                f"📊 Уровень: {user.level}\n"
                f"⭐ Опыт: {user.experience}/{user.experience_to_next}\n"
                f"💎 Очки: {user.points}\n\n"
                f"Выбери действие:"
            )
        else:
            text = "👋 <b>Главное меню</b>\n\nВыбери действие:"
        
        await callback.message.edit_text(text, reply_markup=get_main_menu(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    """Помощь"""
    help_text = (
        "📚 <b>Помощь по игре</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Начать игру\n"
        "/profile - Твой профиль\n"
        "/inventory - Твои карты\n"
        "/battle - Меню боев\n\n"
        
        "<b>Как играть:</b>\n"
        "1️⃣ Получи стартовую карту при регистрации\n"
        "2️⃣ Экипируй карты в колоду (1 персонаж + оружие + шикигами + 2 пакта)\n"
        "3️⃣ Сражайся на арене проклятий для прокачки\n"
        "4️⃣ Используй очки для улучшения карт\n"
        "5️⃣ Бросай вызов другим игрокам в PvP!\n\n"
        
        "<b>Система боя:</b>\n"
        "• Первым атакует тот, у кого больше скорости\n"
        "• Атака уменьшается защитой противника\n"
        "• Побеждает тот, кто first опустит HP врага до 0\n\n"
        
        "<b>Прокачка:</b>\n"
        "• Опыт дается за бои и сообщения\n"
        "• Очки даются только за повышение уровня\n"
        "• Улучшай карты за очки!"
    )
    
    from keyboards.main_menu import get_back_button
    await callback.message.edit_text(help_text, reply_markup=get_back_button(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "feedback_menu")
async def feedback_menu_callback(callback: CallbackQuery):
    if not ADMIN_IDS:
        await callback.answer("Сейчас обратная связь недоступна: не задан ADMIN_IDS.", show_alert=True)
        return

    pending_feedback_users.add(callback.from_user.id)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="feedback_cancel")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
        ]
    )
    await callback.message.edit_text(
        "💬 <b>Обратная связь</b>\n\n"
        "Напиши одним сообщением баг, идею для обновления или пожелание.\n"
        "Текст будет отправлен администраторам в личные сообщения.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "feedback_cancel")
async def feedback_cancel_callback(callback: CallbackQuery):
    pending_feedback_users.discard(callback.from_user.id)
    await main_menu_callback(callback)


@router.message(F.text, ~F.text.startswith("/"), lambda message: message.from_user.id in pending_feedback_users)
async def feedback_input_handler(message: Message):
    pending_feedback_users.discard(message.from_user.id)
    text = (message.text or "").strip()
    if not text:
        await message.answer("Сообщение пустое. Попробуй ещё раз через кнопку обратной связи.")
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "без username"
    payload = (
        "💬 <b>Новое сообщение из обратной связи</b>\n\n"
        f"👤 Пользователь: {message.from_user.first_name or 'Игрок'}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n"
        f"🔗 Username: {username}\n\n"
        f"📝 Текст:\n{text}"
    )

    delivered = 0
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, payload, parse_mode="HTML")
            delivered += 1
        except Exception:
            continue

    if delivered:
        await message.answer(
            "✅ Сообщение отправлено. Спасибо, это поможет быстрее ловить баги и собирать идеи.",
            reply_markup=get_main_menu(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "⚠️ Не удалось доставить сообщение администраторам. Попробуй чуть позже.",
            reply_markup=get_main_menu(),
            parse_mode="HTML",
        )
