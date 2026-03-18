from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List

from config import (
    STAT_UPGRADE_COST,
    STAT_UPGRADE_VALUES,
    DOMAIN_DOT_PER_POINT,
    DOMAIN_DAMAGE_BONUS_PER_POINT,
    RCT_HEAL_BONUS_PER_POINT,
)
from utils.card_rewards import (
    is_character_template,
    is_support_template,
    is_weapon_template,
    is_shikigami_template,
    is_pact_template,
)

def get_card_list_keyboard(
    cards: List,
    page: int = 0,
    cards_per_page: int = 5,
    page_callback_prefix: str = "cards_page",
    back_callback: str = "inventory",
):
    """Клавиатура списка карт с пагинацией."""
    buttons = []
    
    # Карты на текущей странице
    start = page * cards_per_page
    end = start + cards_per_page
    page_cards = cards[start:end]
    
    for card in page_cards:
        card_name = card.card_template.name if card.card_template else "Unknown"
        rarity_emoji = {
            "common": "⚪",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡",
            "mythical": "🔴"
        }.get(card.card_template.rarity, "⚪") if card.card_template else "⚪"
        
        buttons.append([
            InlineKeyboardButton(
                text=f"{rarity_emoji} {card_name} (Lv.{card.level})",
                callback_data=f"card_detail_{card.id}"
            )
        ])
    
    # Кнопки пагинации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"{page_callback_prefix}_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}", callback_data="noop"))
    if end < len(cards):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"{page_callback_prefix}_{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Кнопка назад
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_card_detail_keyboard(card_id: int, is_equipped: bool = False, can_upgrade: bool = True):
    """Клавиатура деталей карты"""
    buttons = []
    
    if not is_equipped:
        buttons.append([
            InlineKeyboardButton(text="🎒 Экипировать", callback_data=f"equip_card_{card_id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="❌ Снять", callback_data=f"unequip_card_{card_id}")
        ])
    
    if can_upgrade:
        buttons.append([
            InlineKeyboardButton(text="⬆️ Прокачать", callback_data=f"upgrade_card_{card_id}")
        ])

    buttons.append([
        InlineKeyboardButton(text="♻️ Утилизировать", callback_data=f"salvage_card_{card_id}")
    ])

    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="all_cards")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_upgrade_keyboard(card_id: int, player_points: int, is_character: bool = True):
    """Клавиатура прокачки карты по статам."""
    can_upgrade = player_points >= STAT_UPGRADE_COST

    rows = [
        [
            InlineKeyboardButton(
                text=f"❤️ HP +{STAT_UPGRADE_VALUES['hp']}",
                callback_data=f"upgrade_stat_{card_id}_hp" if can_upgrade else "noop",
            ),
            InlineKeyboardButton(
                text=f"⚔️ Атака +{STAT_UPGRADE_VALUES['attack']}",
                callback_data=f"upgrade_stat_{card_id}_attack" if can_upgrade else "noop",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🛡️ Защита +{STAT_UPGRADE_VALUES['defense']}",
                callback_data=f"upgrade_stat_{card_id}_defense" if can_upgrade else "noop",
            ),
            InlineKeyboardButton(
                text=f"💨 Скорость +{STAT_UPGRADE_VALUES['speed']}",
                callback_data=f"upgrade_stat_{card_id}_speed" if can_upgrade else "noop",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f" CE +{STAT_UPGRADE_VALUES['ce']}",
                callback_data=f"upgrade_stat_{card_id}_ce" if can_upgrade else "noop",
            ),
            InlineKeyboardButton(
                text=f"  CE +{STAT_UPGRADE_VALUES['ce_regen']}",
                callback_data=f"upgrade_stat_{card_id}_ce_regen" if can_upgrade else "noop",
            ),
        ],    ]

    if is_character:
        domain_pct = int(DOMAIN_DOT_PER_POINT * 1000) / 10
        dmg_pct = int(DOMAIN_DAMAGE_BONUS_PER_POINT * 1000) / 10
        rct_pct = int(RCT_HEAL_BONUS_PER_POINT * 100)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🏯 Домен +{domain_pct}%",
                    callback_data=f"upgrade_stat_{card_id}_domain" if can_upgrade else "noop",
                ),
                InlineKeyboardButton(
                    text=f"♻️ ОПТ +{rct_pct}%",
                    callback_data=f"upgrade_stat_{card_id}_rct" if can_upgrade else "noop",
                ),
            ]
        )

    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"card_detail_{card_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_deck_keyboard(
    main_card=None,
    weapon_card=None,
    shikigami_card=None,
    pact_card_1=None,
    pact_card_2=None,
):
    """Клавиатура управления колодой"""
    buttons = []
    
    if main_card:
        card_name = main_card.card_template.name if main_card.card_template else "Unknown"
        buttons.append([
            InlineKeyboardButton(text=f"👑 Главная: {card_name}", callback_data=f"card_detail_{main_card.id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="➕ Выбрать главную карту", callback_data="select_main_card")
        ])
    
    if weapon_card:
        card_name = weapon_card.card_template.name if weapon_card.card_template else "Unknown"
        buttons.append([
            InlineKeyboardButton(text=f"🗡️ Оружие: {card_name}", callback_data=f"card_detail_{weapon_card.id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="➕ Выбрать оружие", callback_data="select_weapon_card")
        ])

    if shikigami_card:
        card_name = shikigami_card.card_template.name if shikigami_card.card_template else "Unknown"
        buttons.append([
            InlineKeyboardButton(text=f"🐺 Шикигами: {card_name}", callback_data=f"card_detail_{shikigami_card.id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="➕ Выбрать шикигами", callback_data="select_shikigami_card")
        ])

    if pact_card_1:
        card_name = pact_card_1.card_template.name if pact_card_1.card_template else "Unknown"
        buttons.append([
            InlineKeyboardButton(text=f"📜 Пакт 1: {card_name}", callback_data=f"card_detail_{pact_card_1.id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="➕ Выбрать пакт 1", callback_data="select_pact1_card")
        ])

    if pact_card_2:
        card_name = pact_card_2.card_template.name if pact_card_2.card_template else "Unknown"
        buttons.append([
            InlineKeyboardButton(text=f"📜 Пакт 2: {card_name}", callback_data=f"card_detail_{pact_card_2.id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="➕ Выбрать пакт 2", callback_data="select_pact2_card")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="profile")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_card_selection_keyboard(cards: List, slot_type: str = "main", page: int = 0):
    """Клавиатура выбора карты для колоды"""
    buttons = []
    cards_per_page = 5
    
    # Фильтруем карты по типу
    if slot_type == "main":
        filtered_cards = [c for c in cards if c.card_template and is_character_template(c.card_template)]
    elif slot_type == "weapon":
        filtered_cards = [c for c in cards if c.card_template and is_weapon_template(c.card_template)]
    elif slot_type == "shikigami_weapon":
        filtered_cards = [
            c for c in cards
            if c.card_template and (is_shikigami_template(c.card_template) or is_weapon_template(c.card_template))
        ]
    elif slot_type == "shikigami":
        filtered_cards = [c for c in cards if c.card_template and is_shikigami_template(c.card_template)]
    elif slot_type in {"pact1", "pact2"}:
        filtered_cards = [c for c in cards if c.card_template and is_pact_template(c.card_template)]
    else:
        filtered_cards = [c for c in cards if c.card_template and is_support_template(c.card_template)]
    
    start = page * cards_per_page
    end = start + cards_per_page
    page_cards = filtered_cards[start:end]
    
    for card in page_cards:
        card_name = card.card_template.name if card.card_template else "Unknown"
        buttons.append([
            InlineKeyboardButton(
                text=f"{card_name} (Lv.{card.level})",
                callback_data=f"select_card_{slot_type}_{card.id}"
            )
        ])
    
    # Пагинация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"select_page_{slot_type}_{page-1}"))
    if end < len(filtered_cards):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"select_page_{slot_type}_{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_deck")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

