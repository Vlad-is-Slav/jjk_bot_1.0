from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models import async_session, User, Achievement, UserAchievement, Title, UserTitle
from utils.achievement_data import ACHIEVEMENTS, TITLES, get_title_by_name
from utils.pvp_progression import apply_experience_with_pvp_rolls

router = Router()


async def _ensure_achievement_templates(session):
    result = await session.execute(select(Achievement))
    existing = {ach.name: ach for ach in result.scalars().all() if ach.name}

    for ach_data in ACHIEVEMENTS:
        ach = existing.get(ach_data["name"])
        if not ach:
            ach = Achievement(
                name=ach_data["name"],
                description=ach_data["description"],
                achievement_type=ach_data["achievement_type"],
                requirement_value=ach_data["requirement_value"],
                exp_reward=ach_data["exp_reward"],
                points_reward=ach_data["points_reward"],
                title_reward=ach_data.get("title_reward"),
                icon=ach_data["icon"],
                rarity=ach_data["rarity"],
            )
            session.add(ach)
        else:
            ach.description = ach_data["description"]
            ach.achievement_type = ach_data["achievement_type"]
            ach.requirement_value = ach_data["requirement_value"]
            ach.exp_reward = ach_data["exp_reward"]
            ach.points_reward = ach_data["points_reward"]
            ach.title_reward = ach_data.get("title_reward")
            ach.icon = ach_data["icon"]
            ach.rarity = ach_data["rarity"]

    result = await session.execute(select(Title))
    existing_titles = {title.name: title for title in result.scalars().all() if title.name}
    for title_data in TITLES:
        title = existing_titles.get(title_data["name"])
        if not title:
            title = Title(
                name=title_data["name"],
                description=title_data.get("description"),
                attack_bonus=title_data.get("attack_bonus", 0),
                defense_bonus=title_data.get("defense_bonus", 0),
                speed_bonus=title_data.get("speed_bonus", 0),
                hp_bonus=title_data.get("hp_bonus", 0),
                icon=title_data.get("icon", "👑"),
                requirement=title_data.get("requirement", ""),
            )
            session.add(title)
        else:
            title.description = title_data.get("description")
            title.attack_bonus = title_data.get("attack_bonus", 0)
            title.defense_bonus = title_data.get("defense_bonus", 0)
            title.speed_bonus = title_data.get("speed_bonus", 0)
            title.hp_bonus = title_data.get("hp_bonus", 0)
            title.icon = title_data.get("icon", "👑")
            title.requirement = title_data.get("requirement", "")


async def _ensure_user_achievements(session, user_id: int):
    await _ensure_achievement_templates(session)

    result = await session.execute(select(Achievement))
    templates = result.scalars().all()

    result = await session.execute(
        select(UserAchievement).where(UserAchievement.user_id == user_id)
    )
    existing = {ua.achievement_id for ua in result.scalars().all()}

    for ach in templates:
        if ach.id in existing:
            continue
        session.add(
            UserAchievement(
                user_id=user_id,
                achievement_id=ach.id,
                progress=0,
                completed=False,
            )
        )

@router.message(Command("achievements"))
async def cmd_achievements(message: Message):
    """Команда /achievements"""
    await message.answer(
        "🏆 <b>Достижения и титулы</b>\n\n"
        "Нажми кнопку, чтобы открыть раздел.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏆 Открыть достижения", callback_data="achievements")]
            ]
        ),
        parse_mode="HTML",
    )
@router.callback_query(F.data == "achievements")
async def achievements_menu_callback(callback: CallbackQuery):
    """Меню достижений"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Мои достижения", callback_data="my_achievements"),
                InlineKeyboardButton(text="🏷 Титулы", callback_data="my_titles"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")],
        ]
    )

    await callback.message.edit_text(
        "🏆 <b>Достижения и титулы</b>\n\n"
        "Здесь ты можешь посмотреть свои достижения и управлять титулами.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()
@router.callback_query(F.data == "my_achievements")
async def my_achievements_callback(callback: CallbackQuery):
    """Показать мои достижения"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        await _ensure_user_achievements(session, user.id)
        await session.commit()

        result = await session.execute(
            select(UserAchievement)
            .options(selectinload(UserAchievement.achievement))
            .where(UserAchievement.user_id == user.id)
        )
        user_achievements = result.scalars().all()

        completed = [ua for ua in user_achievements if ua.completed]
        in_progress = [ua for ua in user_achievements if not ua.completed][:5]

        achievements_text = (
            f"🏆 <b>Мои достижения</b>\n\n"
            f"✅ Завершено: <b>{len(completed)}</b>/{len(ACHIEVEMENTS)}\n"
            f"🕒 В процессе: <b>{len([ua for ua in user_achievements if not ua.completed])}</b>\n\n"
        )

        if completed:
            achievements_text += "<b>Недавние достижения:</b>\n"
            for ua in sorted(completed, key=lambda x: x.completed_at or datetime.min, reverse=True)[:3]:
                ach = ua.achievement
                achievements_text += f"{ach.icon} {ach.name}\n"
            achievements_text += "\n"

        if in_progress:
            achievements_text += "<b>В процессе:</b>\n"
            for ua in in_progress:
                ach = ua.achievement
                progress_pct = min(100, int((ua.progress / ach.requirement_value) * 100))
                bar = "█" * (progress_pct // 10) + "░" * (10 - progress_pct // 10)
                achievements_text += (
                    f"{ach.icon} {ach.name}\n"
                    f"[{bar}] {ua.progress}/{ach.requirement_value}\n\n"
                )

        await callback.message.edit_text(
            achievements_text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="achievements")]]
            ),
            parse_mode="HTML",
        )
    await callback.answer()
@router.callback_query(F.data == "my_titles")
async def my_titles_callback(callback: CallbackQuery):
    """Показать титулы пользователя"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        # Получаем титулы пользователя
        result = await session.execute(
            select(UserTitle)
            .options(selectinload(UserTitle.title))
            .where(UserTitle.user_id == user.id)
        )
        user_titles = result.scalars().all()

        # Инициализируем стартовый титул если нет
        if not user_titles:
            result = await session.execute(
                select(Title).where(Title.name == "Новичок")
            )
            title_template = result.scalar_one_or_none()

            if not title_template:
                title_template = Title(
                    name="Новичок",
                    description="Только начинаешь свой путь",
                    icon="🌱",
                    requirement="Стартовый титул",
                )
                session.add(title_template)
                await session.flush()

            user_title = UserTitle(
                user_id=user.id,
                title_id=title_template.id,
                is_equipped=True
            )
            session.add(user_title)
            user.equipped_title_id = title_template.id
            await session.commit()

            # Перезагружаем
            result = await session.execute(
                select(UserTitle)
                .options(selectinload(UserTitle.title))
                .where(UserTitle.user_id == user.id)
            )
            user_titles = result.scalars().all()

        # Получаем экипированный титул
        equipped = [ut for ut in user_titles if ut.is_equipped]
        equipped_title = equipped[0].title if equipped else None

        titles_text = (
            f"🏷 <b>Мои титулы</b>\n\n"
            f"📊 Всего: <b>{len(user_titles)}</b>\n"
        )

        if equipped_title:
            titles_text += f"✅ Экипирован: <b>{equipped_title.icon} {equipped_title.name}</b>\n\n"
            if equipped_title.attack_bonus > 0:
                titles_text += f"⚔️ Атака: +{equipped_title.attack_bonus}\n"
            if equipped_title.defense_bonus > 0:
                titles_text += f"🛡️ Защита: +{equipped_title.defense_bonus}\n"
            if equipped_title.speed_bonus > 0:
                titles_text += f"💨 Скорость: +{equipped_title.speed_bonus}\n"
            if equipped_title.hp_bonus > 0:
                titles_text += f"❤️ HP: +{equipped_title.hp_bonus}\n"

        titles_text += "\n<b>Доступные титулы:</b>\n"

        buttons = []
        for ut in user_titles:
            title = ut.title
            status = "✅" if ut.is_equipped else ""
            titles_text += f"{status} {title.icon} {title.name}\n"

            if not ut.is_equipped:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"🏷 Надеть: {title.name}",
                        callback_data=f"equip_title_{ut.id}"
                    )
                ])

        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="achievements")])

        await callback.message.edit_text(
            titles_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    await callback.answer()
@router.callback_query(F.data.startswith("equip_title_"))
async def equip_title_callback(callback: CallbackQuery):
    """Экипировать титул"""
    title_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return
        
        # Снимаем текущий титул
        result = await session.execute(
            select(UserTitle).where(
                UserTitle.user_id == user.id,
                UserTitle.is_equipped == True
            )
        )
        current = result.scalar_one_or_none()
        if current:
            current.is_equipped = False
        
        # Экипируем новый
        result = await session.execute(
            select(UserTitle)
            .options(selectinload(UserTitle.title))
            .where(
                UserTitle.id == title_id,
                UserTitle.user_id == user.id
            )
        )
        new_title = result.scalar_one_or_none()
        
        if new_title:
            new_title.is_equipped = True
            user.equipped_title_id = new_title.title_id
            await session.commit()
            
            await callback.answer(f"Титул '{new_title.title.name}' экипирован!")
        
        await my_titles_callback(callback)

# Функция для проверки и выдачи достижений
async def _check_achievements_with_session(
    session,
    user_id: int,
    achievement_type: str,
    value: int = 1,
    absolute: bool = False,
):
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        return []

    await _ensure_user_achievements(session, user_id)
    await session.flush()

    result = await session.execute(
        select(UserAchievement)
        .options(selectinload(UserAchievement.achievement))
        .where(
            UserAchievement.user_id == user_id,
            UserAchievement.completed == False,
        )
    )
    user_achievements = result.scalars().all()

    unlocked = []

    for ua in user_achievements:
        if ua.achievement.achievement_type != achievement_type:
            continue

        if absolute:
            ua.progress = max(int(ua.progress or 0), int(value))
        else:
            ua.progress = int(ua.progress or 0) + int(value)

        if ua.progress < ua.achievement.requirement_value:
            continue

        ua.completed = True
        ua.completed_at = datetime.utcnow()

        if ua.achievement.exp_reward:
            await apply_experience_with_pvp_rolls(session, user, ua.achievement.exp_reward)

        # Очки выдаются только за повышение уровня.

        if ua.achievement.title_reward:
            title = await session.scalar(
                select(Title).where(Title.name == ua.achievement.title_reward)
            )

            if not title:
                title_data = get_title_by_name(ua.achievement.title_reward)
                if title_data:
                    title = Title(
                        name=title_data["name"],
                        description=title_data.get("description"),
                        attack_bonus=title_data.get("attack_bonus", 0),
                        defense_bonus=title_data.get("defense_bonus", 0),
                        speed_bonus=title_data.get("speed_bonus", 0),
                        hp_bonus=title_data.get("hp_bonus", 0),
                        icon=title_data.get("icon", "🏷"),
                        requirement=title_data.get("requirement", ""),
                    )
                else:
                    title = Title(
                        name=ua.achievement.title_reward,
                        description=ua.achievement.description,
                        attack_bonus=0,
                        defense_bonus=0,
                        speed_bonus=0,
                        hp_bonus=0,
                        icon=ua.achievement.icon or "🏷",
                        requirement=f"Получено за достижение: {ua.achievement.name}",
                    )
                session.add(title)
                await session.flush()

            if title:
                existing = await session.scalar(
                    select(UserTitle).where(
                        UserTitle.user_id == user_id,
                        UserTitle.title_id == title.id,
                    )
                )
                if not existing:
                    session.add(
                        UserTitle(
                            user_id=user_id,
                            title_id=title.id,
                            is_equipped=False,
                        )
                    )

        unlocked.append(ua.achievement)

    return unlocked


# Функция для проверки и выдачи достижений
async def check_achievements(
    user_id: int,
    achievement_type: str,
    value: int = 1,
    *,
    absolute: bool = False,
    session=None,
):
    """Проверить и выдать достижения"""
    if session is None:
        async with async_session() as session:
            unlocked = await _check_achievements_with_session(
                session,
                user_id,
                achievement_type,
                value=value,
                absolute=absolute,
            )
            await session.commit()
            return unlocked

    return await _check_achievements_with_session(
        session,
        user_id,
        achievement_type,
        value=value,
        absolute=absolute,
    )
