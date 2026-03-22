from __future__ import annotations

from typing import Any


def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _try_fix_mojibake(value: str) -> str | None:
    if not value:
        return None
    try:
        return value.encode("cp1251").decode("utf-8")
    except Exception:
        return None


PACT_EFFECTS: dict[str, dict[str, Any]] = {
    "Пакт силы": {
        "next_attack_multiplier": 1.5,
        "ce_regen_multiplier": 0.6,
        "label": "Следующая атака +50%, CE реген -40%",
    },
    "Пакт усердия": {
        "post_battle_exp_multiplier": 1.5,
        "consume_after_battle": True,
        "label": "После боя получишь +50% опыта. Пакт исчезнет по завершении боя.",
    },
    "Пакт прорыва": {
        "post_battle_exp_multiplier": 2.0,
        "consume_after_battle": True,
        "label": "После боя получишь +100% опыта. Пакт исчезнет по завершении боя.",
    },
    "Пакт просветления": {
        "post_battle_exp_multiplier": 2.5,
        "consume_after_battle": True,
        "label": "После боя получишь +150% опыта. Пакт исчезнет по завершении боя.",
    },
    "Пакт выживания": {
        "survive_lethal_once": True,
        "label": "Следующий смертельный удар оставит тебя на 1 HP.",
    },
}

PACT_EFFECTS_NORMALIZED = {
    _normalize_name(name): effect for name, effect in PACT_EFFECTS.items()
}


def get_pact_effect(card_or_template) -> dict[str, Any] | None:
    if not card_or_template:
        return None
    name = getattr(card_or_template, "name", None)
    if not name and getattr(card_or_template, "card_template", None):
        name = card_or_template.card_template.name
    if not name:
        return None

    # Direct match
    effect = PACT_EFFECTS.get(name)
    if effect:
        return effect

    # Normalized match
    effect = PACT_EFFECTS_NORMALIZED.get(_normalize_name(name))
    if effect:
        return effect

    # Try to fix mojibake and match again
    fixed = _try_fix_mojibake(name)
    if fixed:
        effect = PACT_EFFECTS.get(fixed)
        if effect:
            return effect
        return PACT_EFFECTS_NORMALIZED.get(_normalize_name(fixed))

    return None


def is_pact_card(card_or_template) -> bool:
    return get_pact_effect(card_or_template) is not None
