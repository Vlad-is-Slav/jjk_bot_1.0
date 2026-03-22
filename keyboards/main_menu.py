from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu():
    """Главное меню бота."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"),
            ],
            [
                InlineKeyboardButton(text="⚔️ Бои", callback_data="battle_menu"),
                InlineKeyboardButton(text="📖 Кампания", callback_data="campaign"),
            ],
            [
                InlineKeyboardButton(text="🗓 Ежедневные", callback_data="daily_menu"),
                InlineKeyboardButton(text="🏆 Топы", callback_data="tops"),
            ],
            [
                InlineKeyboardButton(text="🏫 Техникум", callback_data="academy"),
                InlineKeyboardButton(text="🏪 Рынок", callback_data="market"),
            ],
            [
                InlineKeyboardButton(text="👥 Друзья", callback_data="friends"),
                InlineKeyboardButton(text="🏯 Кланы", callback_data="clans_menu"),
            ],
            [
                InlineKeyboardButton(text="💬 Обратная связь", callback_data="feedback_menu"),
                InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
            ],
        ]
    )
    return keyboard


def get_profile_menu():
    """Меню профиля."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="profile_stats"),
                InlineKeyboardButton(text="🎴 Моя колода", callback_data="my_deck"),
            ],
            [
                InlineKeyboardButton(text="🏆 Достижения", callback_data="achievements"),
                InlineKeyboardButton(text="🏷 Титулы", callback_data="my_titles"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Сложность", callback_data="difficulty_menu"),
                InlineKeyboardButton(text="🖼 Аватар", callback_data="profile_show_avatar"),
            ],
            [InlineKeyboardButton(text="🖼 Оформление", callback_data="profile_customization")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ]
    )
    return keyboard


def get_inventory_menu():
    """Меню инвентаря."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎴 Все карты", callback_data="all_cards"),
                InlineKeyboardButton(text="⭐ Персонажи", callback_data="character_cards"),
            ],
            [
                InlineKeyboardButton(text="🛡️ Поддержка", callback_data="support_cards"),
                InlineKeyboardButton(text="✨ Техники", callback_data="my_techniques"),
            ],
            [
                InlineKeyboardButton(text="🎴 Колода", callback_data="my_deck"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
            ],
        ]
    )
    return keyboard


def get_battle_menu():
    """Меню боёв."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👹 Арена проклятий", callback_data="pve_arena"),
                InlineKeyboardButton(text="⚔️ PvP Бой", callback_data="pvp_menu"),
            ],
            [
                InlineKeyboardButton(text="🧿 Боссы", callback_data="boss_battles"),
                InlineKeyboardButton(text="📜 История", callback_data="battle_history"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ]
    )
    return keyboard


def get_tops_menu():
    """Меню топов."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 По уровню", callback_data="top_level"),
                InlineKeyboardButton(text="⚔️ По PvP", callback_data="top_pvp"),
            ],
            [
                InlineKeyboardButton(text="📈 По опыту", callback_data="top_exp"),
                InlineKeyboardButton(text="💪 По силе", callback_data="top_power"),
            ],
            [
                InlineKeyboardButton(text="🏯 По кланам", callback_data="top_clans"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ]
    )
    return keyboard


def get_friends_menu():
    """Меню друзей."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Список друзей", callback_data="friends_list"),
                InlineKeyboardButton(text="➕ Добавить", callback_data="add_friend"),
            ],
            [
                InlineKeyboardButton(text="📨 Заявки", callback_data="friend_requests"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
            ],
        ]
    )
    return keyboard


def get_difficulty_menu():
    """Меню выбора сложности."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Легкий", callback_data="set_difficulty_easy"),
                InlineKeyboardButton(text="🔵 Средний", callback_data="set_difficulty_normal"),
            ],
            [
                InlineKeyboardButton(text="🟠 Сложный", callback_data="set_difficulty_hard"),
                InlineKeyboardButton(text="🔴 Хардкор", callback_data="set_difficulty_hardcore"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")],
        ]
    )
    return keyboard


def get_back_button(callback_data="main_menu"):
    """Кнопка назад."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)]]
    )
