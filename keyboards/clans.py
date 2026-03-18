from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_clans_menu_keyboard(in_clan: bool, has_invite: bool = False):
    rows = []

    if has_invite and not in_clan:
        rows.append([InlineKeyboardButton(text="📩 Приглашение", callback_data="clan_invite_open")])

    if in_clan:
        rows.append([InlineKeyboardButton(text="📨 Пригласить в клан", callback_data="clan_invite")])
        rows.append([InlineKeyboardButton(text="🚪 Покинуть клан", callback_data="clan_leave")])
    else:
        rows.append([InlineKeyboardButton(text="➕ Создать клан", callback_data="clan_create")])

    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=rows)
