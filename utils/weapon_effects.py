from __future__ import annotations

from typing import Any


WEAPON_EFFECTS: dict[str, dict[str, Any]] = {
    "Игривое облако": {
        "type": "basic_multiplier",
        "min": 1.2,
        "max": 1.2,
        "label": "Обычные удары: +20% к урону",
    },
    "Клинок ясности души": {
        "type": "ignore_defense",
        "label": "Игнорирует защиту цели",
    },
    "Перевернутое небесное копье": {
        "type": "basic_ignore_infinity",
        "label": "Пробивает Бесконечность только обычными ударами",
    },
    "Цепь тысячи миль": {
        "type": "ignore_dodge",
        "label": "Атаки этой цепью нельзя уклонить",
    },
    "Чёрный клинок": {
        "type": "black_flash_bonus",
        "chance_bonus": 0.12,
        "label": "Повышает шанс чёрной вспышки на 12%",
    },
    "Проклятые перчатки": {
        "type": "basic_multiplier",
        "min": 1.15,
        "max": 1.15,
        "label": "Обычные удары: +15% к физическому урону",
    },
}


def get_weapon_effect(card_or_template) -> dict[str, Any] | None:
    if not card_or_template:
        return None
    name = getattr(card_or_template, "name", None)
    if not name and getattr(card_or_template, "card_template", None):
        name = card_or_template.card_template.name
    if not name:
        return None
    return WEAPON_EFFECTS.get(name)


def is_weapon_card(card_or_template) -> bool:
    return get_weapon_effect(card_or_template) is not None
