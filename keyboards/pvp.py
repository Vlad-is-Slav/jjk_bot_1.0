from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def _format_ce_cost(cost: int) -> str:
    return "бесплатно" if not cost else f"{cost} CE"


def _number_emoji(value: int) -> str:
    return {
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
    }.get(int(value), str(value))


def _choice_rows(prefix: str, options: list[int]) -> list[list[InlineKeyboardButton]]:
    buttons = [
        InlineKeyboardButton(text=_number_emoji(option), callback_data=f"{prefix}_{option}")
        for option in options
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for index in range(0, len(buttons), 2):
        rows.append(buttons[index:index + 2])
    return rows


def get_pvp_menu():
    """Меню PvP."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Найти соперника", callback_data="pvp_find"),
            InlineKeyboardButton(text="🎯 Вызвать игрока", callback_data="pvp_challenge"),
        ],
        [
            InlineKeyboardButton(text="🤝 Кооператив PvP", callback_data="pvp_coop_menu"),
            InlineKeyboardButton(text="📜 История PvP", callback_data="pvp_history"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="battle_menu"),
        ],
    ])


def get_pvp_search_keyboard():
    """Клавиатура поиска соперника."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Искать снова", callback_data="pvp_find"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="pvp_menu"),
        ]
    ])


def get_pvp_waiting_keyboard():
    """Клавиатура ожидания real-time соперника."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить поиск", callback_data="pvp_find"),
            InlineKeyboardButton(text="❌ Отменить поиск", callback_data="pvp_cancel_search"),
        ]
    ])


def get_pvp_challenge_keyboard(target_id: int):
    """Клавиатура вызова на бой."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Принять", callback_data=f"pvp_accept_{target_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pvp_decline_{target_id}"),
        ]
    ])


def get_pvp_challenge_input_keyboard():
    """Клавиатура ввода цели для прямого вызова."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="pvp_cancel_challenge_input"),
            InlineKeyboardButton(text="🔙 В PvP меню", callback_data="pvp_menu"),
        ]
    ])


def get_pvp_battle_keyboard(
    is_your_turn: bool = True,
    fighter_state: dict | None = None,
    action_state: dict | None = None,
):
    """Клавиатура PvP во время боя."""
    if not is_your_turn:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Ход соперника...", callback_data="noop")]
        ])

    action_state = action_state or {}
    force_response = action_state.get("force_response", False)

    rows = []

    if force_response:
        if action_state.get("target_selection"):
            rows.append([
                InlineKeyboardButton(
                    text=action_state.get("target_prompt", "🎯 Выбери цель атаки"),
                    callback_data="noop",
                )
            ])
            target_buttons = []
            if action_state.get("can_target_main", True):
                target_buttons.append(
                    InlineKeyboardButton(text="🃏 Главная карта", callback_data="pvp_action_target_main")
                )
            if action_state.get("can_target_shikigami", False):
                target_buttons.append(
                    InlineKeyboardButton(text="🐺 Шикигами", callback_data="pvp_action_target_shikigami")
                )
            if target_buttons:
                rows.append(target_buttons[:2])
                if len(target_buttons) > 2:
                    rows.append(target_buttons[2:])
            rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="pvp_action_target_back")])
            return InlineKeyboardMarkup(inline_keyboard=rows)

        if action_state.get("special_variant_key"):
            rows.append([InlineKeyboardButton(text="⚙️ Выбери вариант техники", callback_data="noop")])
            rows.append([
                InlineKeyboardButton(
                    text=f"⚪ Обычный ({action_state.get('special_variant_base_cost', 0)} CE)",
                    callback_data=f"pvp_action_special_pick_{action_state['special_variant_key']}_base",
                ),
                InlineKeyboardButton(
                    text=f"⚡ Усиленный ({action_state.get('special_variant_amp_cost', 0)} CE)",
                    callback_data=f"pvp_action_special_pick_{action_state['special_variant_key']}_amp",
                ),
            ])
            rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="pvp_action_special_variant_back")])
            return InlineKeyboardMarkup(inline_keyboard=rows)

        battlerdan_stage = action_state.get("battlerdan_stage")
        if battlerdan_stage:
            options = action_state.get("battlerdan_options", [1, 2, 3, 4])
            if battlerdan_stage == "topic":
                prefix = "pvp_action_battlerdan_topic"
                label = "📚 Выбери тему"
            elif battlerdan_stage == "choose":
                prefix = "pvp_action_battlerdan_choose"
                label = "🗣 Выбери правду"
            else:
                prefix = "pvp_action_battlerdan_guess"
                label = "❓ Угадай ответ"
            rows.append([InlineKeyboardButton(text=label, callback_data="noop")])
            rows.extend(_choice_rows(prefix, options))
            return InlineKeyboardMarkup(inline_keyboard=rows)

        response_buttons = []
        if action_state.get("can_domain"):
            response_buttons.append(
                InlineKeyboardButton(
                    text=f"🏯 Расширение ({_format_ce_cost(fighter_state.get('domain_cost', 4000))})",
                    callback_data="pvp_action_domain",
                )
            )
        if action_state.get("can_simple"):
            response_buttons.append(
                InlineKeyboardButton(
                    text=f"🛡 Простая тер. ({_format_ce_cost(fighter_state.get('simple_domain_cost', 1500))})",
                    callback_data="pvp_action_simple",
                )
            )
        if action_state.get("can_mahoraga") and fighter_state and fighter_state.get("has_mahoraga"):
            response_buttons.append(
                InlineKeyboardButton(
                    text=f"🌀 Махорага ({fighter_state.get('mahoraga_cost', 2000)} CE)",
                    callback_data="pvp_action_mahoraga",
                )
            )

        if response_buttons:
            rows.append(response_buttons)
        elif action_state.get("can_skip_response"):
            rows.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data="pvp_action_skip_response")])

        return InlineKeyboardMarkup(inline_keyboard=rows)

    if action_state.get("can_main_attack", True):
        rows.append([InlineKeyboardButton(text="👊 Удар рукой", callback_data="pvp_action_basic")])

    if action_state.get("can_shikigami_attack", False):
        shikigami = (fighter_state or {}).get("shikigami")
        shikigami_name = (
            shikigami.card_template.name
            if shikigami and getattr(shikigami, "card_template", None)
            else "Шикигами"
        )
        rows.append([
            InlineKeyboardButton(
                text=f"🐺 Атака {shikigami_name}",
                callback_data="pvp_action_shikigami_basic",
            )
        ])

    if action_state.get("can_sword", False):
        sword_name = "Золотая правда" if fighter_state and fighter_state.get("is_battlerdan") else "Золотой меч"
        rows.append([InlineKeyboardButton(text=f"⚖️ {sword_name}", callback_data="pvp_action_higuruma_sword")])

    if action_state.get("can_special", True):
        specials = (fighter_state or {}).get("specials", [])
        for special in specials:
            if special.get("variants"):
                rows.append([
                    InlineKeyboardButton(
                        text=f"{special['icon']} {special['name']}",
                        callback_data=f"pvp_action_special_menu_{special['key']}",
                    )
                ])
                continue
            rows.append([
                InlineKeyboardButton(
                    text=f"{special['icon']} {special['name']} ({special['ce_cost']} CE)",
                    callback_data=f"pvp_action_special_{special['key']}",
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
            rows.append([InlineKeyboardButton(text=f"📜 {pact_name}", callback_data=f"pvp_action_pact_{pact_id}")])

    utility_buttons = []
    if action_state.get("can_domain", False) and fighter_state and fighter_state.get("has_domain"):
        utility_buttons.append(
            InlineKeyboardButton(
                text=f"🏯 Расширение ({_format_ce_cost(fighter_state.get('domain_cost', 4000))})",
                callback_data="pvp_action_domain",
            )
        )
    if action_state.get("can_simple", False) and fighter_state and fighter_state.get("has_simple_domain"):
        utility_buttons.append(
            InlineKeyboardButton(
                text=f"🛡 Простая тер. ({_format_ce_cost(fighter_state.get('simple_domain_cost', 1500))})",
                callback_data="pvp_action_simple",
            )
        )
    if action_state.get("can_rct", False) and fighter_state and fighter_state.get("has_reverse_ct"):
        utility_buttons.append(
            InlineKeyboardButton(
                text=f"♻️ ОПТ ({fighter_state.get('rct_cost', 2500)} CE)",
                callback_data="pvp_action_rct",
            )
        )
    if action_state.get("can_mahoraga", False) and fighter_state and fighter_state.get("has_mahoraga"):
        utility_buttons.append(
            InlineKeyboardButton(
                text=f"🌀 Махорага ({fighter_state.get('mahoraga_cost', 2000)} CE)",
                callback_data="pvp_action_mahoraga",
            )
        )

    if utility_buttons:
        rows.append(utility_buttons[:2])
        if len(utility_buttons) > 2:
            rows.append(utility_buttons[2:])

    if action_state.get("show_end_turn", False):
        rows.append([InlineKeyboardButton(text="✅ Завершить ход", callback_data="pvp_action_end_turn")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_pvp_result_keyboard(won: bool):
    """Клавиатура результата PvP."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Реванш", callback_data="pvp_rematch"),
            InlineKeyboardButton(text="🔙 В меню PvP", callback_data="pvp_menu"),
        ],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])
