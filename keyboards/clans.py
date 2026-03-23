from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_clans_menu_keyboard(
    in_clan: bool,
    has_invite: bool = False,
    has_request: bool = False,
    request_count: int = 0,
    is_owner: bool = False,
):
    rows = []

    if has_invite and not in_clan:
        rows.append([InlineKeyboardButton(text="📩 Приглашение", callback_data="clan_invite_open")])

    if in_clan:
        if is_owner:
            label = "📥 Заявки"
            if request_count > 0:
                label = f"📥 Заявки ({request_count})"
            rows.append([InlineKeyboardButton(text=label, callback_data="clan_requests_0")])
        rows.append([InlineKeyboardButton(text="📨 Пригласить в клан", callback_data="clan_invite")])
        rows.append([InlineKeyboardButton(text="🚪 Покинуть клан", callback_data="clan_leave")])
    else:
        rows.append([
            InlineKeyboardButton(text="➕ Создать клан", callback_data="clan_create"),
            InlineKeyboardButton(
                text="📝 Моя заявка" if has_request else "📨 Подать заявку",
                callback_data="clan_my_request" if has_request else "clan_request_menu_0",
            ),
        ])

    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=rows)
