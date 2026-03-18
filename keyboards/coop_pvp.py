from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def _format_ce_cost(cost: int) -> str:
    return "бесплатно" if not cost else f"{cost} CE"


def get_coop_menu_keyboard(has_team: bool, is_leader: bool, is_queued: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if not has_team:
        rows.append([InlineKeyboardButton(text="➕ Создать команду", callback_data="coop_create_team")])
    else:
        if is_leader:
            rows.append([InlineKeyboardButton(text="➕ Пригласить игрока", callback_data="coop_invite")])
            if is_queued:
                rows.append([InlineKeyboardButton(text="❌ Выйти из очереди", callback_data="coop_cancel_queue")])
            else:
                rows.append([InlineKeyboardButton(text="🔎 Поиск боя", callback_data="coop_queue")])
            rows.append([InlineKeyboardButton(text="❌ Распустить команду", callback_data="coop_leave_team")])
        else:
            rows.append([InlineKeyboardButton(text="❌ Покинуть команду", callback_data="coop_leave_team")])

    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="pvp_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_coop_invite_input_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="coop_cancel_invite_input")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="pvp_coop_menu")],
    ])


def get_coop_invite_keyboard(leader_tg: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"coop_accept_{leader_tg}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"coop_decline_{leader_tg}"),
        ]
    ])


def get_coop_waiting_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="pvp_coop_menu"),
            InlineKeyboardButton(text="❌ Выйти из очереди", callback_data="coop_cancel_queue"),
        ]
    ])


def get_coop_battle_keyboard(
    is_your_turn: bool = True,
    fighter_state: dict | None = None,
    action_state: dict | None = None,
) -> InlineKeyboardMarkup:
    if not is_your_turn:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Ход другого игрока...", callback_data="noop")]
        ])

    action_state = action_state or {}
    force_response = action_state.get("force_response", False)
    rows = []

    if force_response:
        battlerdan_stage = action_state.get("battlerdan_stage")
        if battlerdan_stage:
            options = action_state.get("battlerdan_options", [1, 2, 3])
            prefix = "coop_action_battlerdan_choose" if battlerdan_stage == "choose" else "coop_action_battlerdan_guess"
            label = "🗣 Выбери аргумент" if battlerdan_stage == "choose" else "❓ Угадай ответ"
            rows.append([InlineKeyboardButton(text=label, callback_data="noop")])
            rows.append([
                InlineKeyboardButton(text="1️⃣", callback_data=f"{prefix}_1"),
                InlineKeyboardButton(text="2️⃣", callback_data=f"{prefix}_2"),
                InlineKeyboardButton(text="3️⃣", callback_data=f"{prefix}_3"),
            ])
            return InlineKeyboardMarkup(inline_keyboard=rows)

        response_buttons = []
        if action_state.get("can_domain"):
            response_buttons.append(
                InlineKeyboardButton(
                    text=f"🏯 Расширение ({_format_ce_cost(fighter_state.get('domain_cost', 4000))})",
                    callback_data="coop_action_domain",
                )
            )
        if action_state.get("can_simple"):
            response_buttons.append(
                InlineKeyboardButton(
                    text=f"🛡 Простая тер. ({_format_ce_cost(fighter_state.get('simple_domain_cost', 1500))})",
                    callback_data="coop_action_simple",
                )
            )
        if action_state.get("can_mahoraga") and fighter_state and fighter_state.get("has_mahoraga"):
            response_buttons.append(
                InlineKeyboardButton(
                    text=f"🌀 Махорага ({fighter_state.get('mahoraga_cost', 2000)} CE)",
                    callback_data="coop_action_mahoraga",
                )
            )

        if response_buttons:
            rows.append(response_buttons)
        elif action_state.get("can_skip_response"):
            rows.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data="coop_action_skip_response")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    if action_state.get("can_attack", True):
        rows.append([InlineKeyboardButton(text="👊 Удар рукой", callback_data="coop_action_basic")])

    if action_state.get("can_sword", False):
        rows.append([InlineKeyboardButton(text="⚖️ Золотой меч", callback_data="coop_action_higuruma_sword")])

    if action_state.get("can_special", True):
        specials = (fighter_state or {}).get("specials", [])
        for special in specials:
            rows.append([
                InlineKeyboardButton(
                    text=f"{special['icon']} {special['name']} ({special['ce_cost']} CE)",
                    callback_data=f"coop_action_special_{special['key']}",
                )
            ])

    pacts = (fighter_state or {}).get("pacts", [])
    used_pacts = (fighter_state or {}).get("pact_used", set()) or set()
    for pact in pacts:
        if not pact or not getattr(pact, "card_template", None):
            continue
        pact_id = getattr(pact, "id", None)
        if pact_id is None:
            continue
        pact_name = pact.card_template.name
        if pact_id in used_pacts:
            rows.append([InlineKeyboardButton(text=f"📜 {pact_name} (исп.)", callback_data="noop")])
        else:
            rows.append([InlineKeyboardButton(text=f"📜 {pact_name}", callback_data=f"coop_action_pact_{pact_id}")])

    utility_buttons = []
    if action_state.get("can_domain", False) and fighter_state and fighter_state.get("has_domain"):
        utility_buttons.append(
            InlineKeyboardButton(
                text=f"🏯 Расширение ({_format_ce_cost(fighter_state.get('domain_cost', 4000))})",
                callback_data="coop_action_domain",
            )
        )
    if action_state.get("can_simple", False) and fighter_state and fighter_state.get("has_simple_domain"):
        utility_buttons.append(
            InlineKeyboardButton(
                text=f"🛡 Простая тер. ({_format_ce_cost(fighter_state.get('simple_domain_cost', 1500))})",
                callback_data="coop_action_simple",
            )
        )
    if action_state.get("can_rct", False) and fighter_state and fighter_state.get("has_reverse_ct"):
        utility_buttons.append(
            InlineKeyboardButton(
                text=f"♻️ ОПТ ({fighter_state.get('rct_cost', 2500)} CE)",
                callback_data="coop_action_rct",
            )
        )
    if action_state.get("can_mahoraga", False) and fighter_state and fighter_state.get("has_mahoraga"):
        utility_buttons.append(
            InlineKeyboardButton(
                text=f"🌀 Махорага ({fighter_state.get('mahoraga_cost', 2000)} CE)",
                callback_data="coop_action_mahoraga",
            )
        )

    if utility_buttons:
        rows.append(utility_buttons[:2])
        if len(utility_buttons) > 2:
            rows.append(utility_buttons[2:])

    if action_state.get("show_end_turn", False):
        rows.append([InlineKeyboardButton(text="✅ Завершить ход", callback_data="coop_action_end_turn")])

    return InlineKeyboardMarkup(inline_keyboard=rows)
