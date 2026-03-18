import random

from sqlalchemy import select, update

from models import Card, UserCard
from utils.card_data import ALL_CARDS, CHARACTER_CARDS, WEAPON_CARDS, PACT_CARDS, RARITY_CHANCES
from utils.daily_quest_progress import add_daily_quest_progress
from utils.quote_rewards import grant_quote_for_card


def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


CHARACTER_CARD_NAMES = {card["name"] for card in CHARACTER_CARDS}
CHARACTER_CARD_NORMALIZED = {_normalize_name(card["name"]) for card in CHARACTER_CARDS}
WEAPON_CARD_NORMALIZED = {_normalize_name(card["name"]) for card in WEAPON_CARDS}
PACT_CARD_NORMALIZED = {_normalize_name(card["name"]) for card in PACT_CARDS}


def get_card_data_by_name(name: str):
    normalized = _normalize_name(name)
    for card in ALL_CARDS:
        if _normalize_name(card["name"]) == normalized:
            return card
    return None


def get_card_type_by_name(card_name: str) -> str:
    normalized = _normalize_name(card_name)
    if normalized in CHARACTER_CARD_NORMALIZED:
        return "character"
    if normalized in WEAPON_CARD_NORMALIZED:
        return "weapon"
    if normalized in PACT_CARD_NORMALIZED:
        return "pact"
    return "support"


def is_character_template(card_template) -> bool:
    if not card_template:
        return False
    if _normalize_name(card_template.name) in CHARACTER_CARD_NORMALIZED:
        return True
    return card_template.card_type == "character"

def is_weapon_template(card_template) -> bool:
    if not card_template:
        return False
    if _normalize_name(card_template.name) in WEAPON_CARD_NORMALIZED:
        return True
    return card_template.card_type == "weapon"


def is_pact_template(card_template) -> bool:
    if not card_template:
        return False
    if _normalize_name(card_template.name) in PACT_CARD_NORMALIZED:
        return True
    return card_template.card_type == "pact"


def is_shikigami_template(card_template) -> bool:
    if not card_template:
        return False
    if _normalize_name(card_template.name) in CHARACTER_CARD_NORMALIZED:
        return False
    if card_template.card_type == "character":
        return False
    if is_weapon_template(card_template) or is_pact_template(card_template):
        return False
    return card_template.card_type == "support"


def is_support_template(card_template) -> bool:
    if not card_template:
        return False
    if _normalize_name(card_template.name) in CHARACTER_CARD_NORMALIZED:
        return False
    if card_template.card_type == "character":
        return False
    if is_pact_template(card_template):
        return False
    return True


def roll_random_card_data(only_characters: bool = False):
    pool = CHARACTER_CARDS if only_characters else ALL_CARDS
    rand = random.uniform(0, 100)
    cumulative = 0.0
    selected_rarity = "common"

    for rarity, chance in RARITY_CHANCES.items():
        cumulative += float(chance)
        if rand <= cumulative:
            selected_rarity = rarity
            break

    cards_of_rarity = [card for card in pool if card["rarity"] == selected_rarity]
    if not cards_of_rarity:
        cards_of_rarity = [card for card in pool if card["rarity"] == "common"] or pool
    return random.choice(cards_of_rarity)


async def get_or_create_card_template(session, card_data: dict):
    result = await session.execute(
        select(Card).where(Card.name == card_data["name"])
    )
    card_template = result.scalar_one_or_none()

    expected_type = get_card_type_by_name(card_data["name"])
    if card_template:
        # Исправляем старые шаблоны, где тип мог быть определен неверно.
        if card_template.card_type != expected_type:
            card_template.card_type = expected_type
        if "base_ce" in card_data:
            card_template.base_ce = int(card_data.get("base_ce", 0))
        if "ce_regen" in card_data:
            card_template.ce_regen = int(card_data.get("ce_regen", 0))
        return card_template

    card_template = Card(
        name=card_data["name"],
        description=card_data.get("description"),
        card_type=expected_type,
        rarity=card_data["rarity"],
        base_attack=card_data["base_attack"],
        base_defense=card_data["base_defense"],
        base_speed=card_data["base_speed"],
        base_hp=card_data["base_hp"],
        base_ce=card_data.get("base_ce", 100),
        ce_regen=card_data.get("ce_regen", 10),
        growth_multiplier=card_data["growth_multiplier"],
    )
    session.add(card_template)
    await session.flush()
    return card_template


async def grant_card_to_user(session, user_id: int, card_data: dict, level: int = 1):
    card_template = await get_or_create_card_template(session, card_data)

    user_card = UserCard(
        user_id=user_id,
        card_id=card_template.id,
        level=max(1, int(level)),
    )
    user_card.card_template = card_template
    user_card.recalculate_stats()
    session.add(user_card)

    await grant_quote_for_card(session, user_id, card_template.name)
    await add_daily_quest_progress(session, user_id, "obtain_cards", amount=1)
    return user_card


async def grant_random_card(session, user_id: int, only_characters: bool = False, level: int = 1):
    card_data = roll_random_card_data(only_characters=only_characters)
    user_card = await grant_card_to_user(session, user_id, card_data, level=level)
    return user_card


def _card_data_key(card_data: dict) -> tuple:
    return (
        int(card_data.get("base_attack", 0)),
        int(card_data.get("base_defense", 0)),
        int(card_data.get("base_speed", 0)),
        int(card_data.get("base_hp", 0)),
        int(card_data.get("base_ce", 100)),
        int(card_data.get("ce_regen", 10)),
        str(card_data.get("rarity", "")).lower(),
    )


def _template_key(template: Card) -> tuple:
    return (
        int(getattr(template, "base_attack", 0) or 0),
        int(getattr(template, "base_defense", 0) or 0),
        int(getattr(template, "base_speed", 0) or 0),
        int(getattr(template, "base_hp", 0) or 0),
        int(getattr(template, "base_ce", 100) or 0),
        int(getattr(template, "ce_regen", 10) or 0),
        str(getattr(template, "rarity", "") or "").lower(),
    )


def _is_corrupted_name(name: str) -> bool:
    if not name:
        return True
    if "?" in name:
        return True
    return _normalize_name(name) == ""


async def sync_card_templates(session):
    """Синхронизировать шаблоны карт с card_data и починить битые имена/типы."""
    result = await session.execute(select(Card))
    templates = result.scalars().all()
    by_name = {t.name: t for t in templates if t.name}

    canonical_by_key: dict[tuple, Card] = {}
    canonical_names = set()

    for card_data in ALL_CARDS:
        expected_type = get_card_type_by_name(card_data["name"])
        template = by_name.get(card_data["name"])
        if not template:
            template = Card(
                name=card_data["name"],
                description=card_data.get("description"),
                card_type=expected_type,
                rarity=card_data["rarity"],
                base_attack=card_data["base_attack"],
                base_defense=card_data["base_defense"],
                base_speed=card_data["base_speed"],
                base_hp=card_data["base_hp"],
                base_ce=card_data.get("base_ce", 100),
                ce_regen=card_data.get("ce_regen", 10),
                growth_multiplier=card_data["growth_multiplier"],
            )
            session.add(template)
            await session.flush()
            by_name[template.name] = template
        else:
            template.description = card_data.get("description")
            template.card_type = expected_type
            template.rarity = card_data["rarity"]
            template.base_attack = card_data["base_attack"]
            template.base_defense = card_data["base_defense"]
            template.base_speed = card_data["base_speed"]
            template.base_hp = card_data["base_hp"]
            template.base_ce = card_data.get("base_ce", 100)
            template.ce_regen = card_data.get("ce_regen", 10)
            template.growth_multiplier = card_data["growth_multiplier"]

        key = _card_data_key(card_data)
        canonical_by_key[key] = template
        canonical_names.add(template.name)

    await session.flush()

    # Перепривязываем карты с битым именем к каноническим шаблонам.
    result = await session.execute(select(Card))
    templates = result.scalars().all()
    for template in templates:
        if template.name in canonical_names:
            continue
        if not _is_corrupted_name(template.name):
            continue
        key = _template_key(template)
        canonical = canonical_by_key.get(key)
        if not canonical or canonical.id == template.id:
            continue

        await session.execute(
            update(UserCard)
            .where(UserCard.card_id == template.id)
            .values(card_id=canonical.id)
        )
        await session.delete(template)

    await session.flush()
