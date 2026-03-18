from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from keyboards import get_battle_menu
from sqlalchemy.orm import selectinload

router = Router()

@router.message(Command("battle"))
async def cmd_battle(message: Message):
    """Команда /battle"""
    await message.answer(
        "⚔️ <b>Меню боев</b>\n\n"
        "Выбери тип боя:",
        reply_markup=get_battle_menu(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "battle_menu")
async def battle_menu_callback(callback: CallbackQuery):
    """Меню боев"""
    await callback.message.edit_text(
        "⚔️ <b>Меню боев</b>\n\n"
        "Выбери тип боя:\n\n"
        "👹 <b>Арена проклятий</b> - сражайся с проклятиями, получай опыт и карты\n\n"
        "⚔️ <b>PvP</b> - брось вызов другим игрокам!",
        reply_markup=get_battle_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "battle_history")
async def battle_history_callback(callback: CallbackQuery):
    """История боев"""
    from sqlalchemy import select
    from models import async_session, User, Battle
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        result = await session.execute(
            select(Battle)
            .options(
                selectinload(Battle.player1),
                selectinload(Battle.player2)
            )
            .where(
                (Battle.player1_id == user.id) | (Battle.player2_id == user.id)
            )
            .order_by(Battle.created_at.desc())
            .limit(10)
        )
        battles = result.scalars().all()
        
        if not battles:
            await callback.message.edit_text(
                "📜 <b>История боев</b>\n\n"
                "У тебя пока нет боев.",
                reply_markup=get_battle_menu(),
                parse_mode="HTML"
            )
            return
        
        history_text = "📜 <b>Последние бои:</b>\n\n"
        
        for i, battle in enumerate(battles, 1):
            opponent_name = battle.get_opponent_name(user.id)
            is_winner = battle.winner_id == user.id
            result_emoji = "🏆" if is_winner else "💀"
            battle_type = "PvP" if battle.battle_type == "pvp" else "PvE"
            
            history_text += f"{i}. {result_emoji} [{battle_type}] vs {opponent_name}\n"
        
        from keyboards.main_menu import get_back_button
        await callback.message.edit_text(
            history_text,
            reply_markup=get_back_button("battle_menu"),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "boss_battles")
async def boss_battles_callback(callback: CallbackQuery):
    """Заглушка для боев с боссами"""
    from keyboards.main_menu import get_back_button

    await callback.message.edit_text(
        "👑 <b>Бои с боссами</b>\n\n"
        "Раздел в разработке. Скоро здесь появятся специальные рейды.",
        reply_markup=get_back_button("battle_menu"),
        parse_mode="HTML"
    )
    await callback.answer()
