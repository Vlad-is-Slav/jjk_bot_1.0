from __future__ import annotations

from typing import Any

CLANS: dict[str, dict[str, Any]] = {
    "gojo": {
        "name": "Клан Годзё",
        "short": "Годзё",
        "emoji": "🔵",
        "bonus_label": "",
        "bonuses": {},
    },
    "zenin": {
        "name": "Клан Зенин",
        "short": "Зенин",
        "emoji": "🟢",
        "bonus_label": "",
        "bonuses": {},
    },
}


def get_clan_info(clan_key: str | None) -> dict[str, Any] | None:
    if not clan_key:
        return None
    return CLANS.get(clan_key)


def get_clan_label(clan_key: str | None) -> str:
    if not clan_key:
        return "Без клана"
    info = get_clan_info(clan_key)
    return info["name"] if info else clan_key


def get_clan_bonuses(clan_key: str | None) -> dict[str, Any]:
    return {}


def get_clan_bonus_label(clan_key: str | None) -> str:
    return ""


def list_clans() -> list[dict[str, Any]]:
    return list(CLANS.values())
