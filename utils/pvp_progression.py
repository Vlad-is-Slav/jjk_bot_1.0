import random
from typing import List

from sqlalchemy import select

from models import Technique, UserTechnique
from utils.card_rewards import grant_random_card


PVP_CORE_TECHNIQUES = [
    {
        "name": "Расширение территории",
        "description": "Позволяет раскрыть свою территорию в PvP и навязать противнику эффект домена.",
        "technique_type": "domain",
        "ce_cost": 4000,
        "effect_type": "buff",
        "effect_value": 30,
        "duration": 3,
        "icon": "🏯",
        "rarity": "epic",
    },
    {
        "name": "Простая территория",
        "description": "Временно нейтрализует вражескую территорию, но блокирует твои спецтехники.",
        "technique_type": "simple",
        "ce_cost": 0,
        "effect_type": "counter",
        "effect_value": 100,
        "duration": 2,
        "icon": "🛡️",
        "rarity": "rare",
    },
    {
        "name": "Обратная проклятая техника",
        "description": "Конвертирует проклятую энергию в восстановление HP в бою.",
        "technique_type": "reverse",
        "ce_cost": 2500,
        "effect_type": "heal",
        "effect_value": 35,
        "duration": 0,
        "icon": "♻️",
        "rarity": "epic",
    },
]

DROP_CHANCES = {
    "level_up": 0.18,
    "quest": 0.22,
    "academy": 0.35,
}
CARDS_PER_LEVEL_UP = 1


async def _get_or_create_template(session, technique_data: dict) -> Technique:
    result = await session.execute(
        select(Technique).where(Technique.name == technique_data["name"])
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    created = Technique(
        name=technique_data["name"],
        description=technique_data["description"],
        technique_type=technique_data["technique_type"],
        ce_cost=technique_data["ce_cost"],
        effect_type=technique_data["effect_type"],
        effect_value=technique_data["effect_value"],
        duration=technique_data["duration"],
        icon=technique_data["icon"],
        rarity=technique_data["rarity"],
    )
    session.add(created)
    await session.flush()
    return created


async def roll_pvp_technique_drop(session, user, source: str, attempts: int = 1) -> List[Technique]:
    if not user or attempts <= 0:
        return []

    drop_chance = DROP_CHANCES.get(source, 0.0)
    if drop_chance <= 0:
        return []

    result = await session.execute(
        select(Technique.name)
        .join(UserTechnique, UserTechnique.technique_id == Technique.id)
        .where(
            UserTechnique.user_id == user.id,
            Technique.name.in_([tech["name"] for tech in PVP_CORE_TECHNIQUES]),
        )
    )
    owned_names = set(result.scalars().all())
    unlocked = []

    for _ in range(attempts):
        if random.random() > drop_chance:
            continue

        available = [tech for tech in PVP_CORE_TECHNIQUES if tech["name"] not in owned_names]
        if not available:
            break

        picked = random.choice(available)
        template = await _get_or_create_template(session, picked)

        session.add(
            UserTechnique(
                user_id=user.id,
                technique_id=template.id,
                level=1,
                is_equipped=False,
            )
        )
        owned_names.add(picked["name"])
        unlocked.append(template)

    return unlocked


async def apply_experience_with_pvp_rolls(session, user, exp_amount: int):
    old_level = user.level
    leveled_up, actual_exp = user.add_experience(exp_amount)
    level_gain = max(0, user.level - old_level)
    unlocked = await roll_pvp_technique_drop(session, user, source="level_up", attempts=level_gain)

    # За каждый новый уровень игрок получает новую карту в инвентарь.
    for _ in range(level_gain * CARDS_PER_LEVEL_UP):
        await grant_random_card(session, user.id, only_characters=False, level=1)

    return leveled_up, actual_exp, unlocked


async def get_player_pvp_toolkit(session, user_id: int) -> dict:
    result = await session.execute(
        select(Technique.technique_type)
        .join(UserTechnique, UserTechnique.technique_id == Technique.id)
        .where(UserTechnique.user_id == user_id)
    )
    owned_types = set(result.scalars().all())

    return {
        "has_domain": "domain" in owned_types,
        "has_simple_domain": "simple" in owned_types,
        "has_reverse_ct": bool(owned_types.intersection({"reverse", "reverse_ct", "rct"})),
    }
