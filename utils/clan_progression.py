from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from models import Clan, ClanDaily

CLAN_EXP_BASE = 1000
CLAN_EXP_MULT = 1.5
CLAN_BONUS_PER_LEVEL = 0.01
CLAN_BONUS_CAP = 0.20

CLAN_EXP_PER_PVE_WIN = 50
CLAN_EXP_PER_PVP_WIN = 100
CLAN_EXP_PER_PVP_LOSS = 30

CLAN_DAILY_QUESTS = {
    "pve_wins": {"label": "Победы в PvE", "target": 5, "reward_exp": 300},
    "pvp_wins": {"label": "Победы в PvP", "target": 3, "reward_exp": 500},
    "battles": {"label": "Любые бои", "target": 10, "reward_exp": 200},
}


def clan_exp_to_next(level: int) -> int:
    level = max(1, int(level))
    exp = CLAN_EXP_BASE
    for _ in range(1, level):
        exp = int(exp * CLAN_EXP_MULT)
    return exp


def clan_bonuses_for_level(level: int) -> dict[str, float]:
    level = max(1, int(level))
    bonus = min(CLAN_BONUS_CAP, CLAN_BONUS_PER_LEVEL * (level - 1))
    return {
        "attack_mult": 1.0 + bonus,
        "ce_regen_mult": 1.0 + bonus,
    }


async def get_or_create_clan(session, clan_name: str, owner_id: int | None = None) -> Clan:
    result = await session.execute(select(Clan).where(Clan.name == clan_name))
    clan = result.scalar_one_or_none()
    if clan:
        return clan

    clan = Clan(
        name=clan_name,
        owner_id=owner_id,
        level=1,
        exp=0,
        exp_to_next=clan_exp_to_next(1),
    )
    session.add(clan)
    await session.flush()
    return clan


async def get_clan_bonuses(session, clan_name: str | None) -> dict[str, float]:
    if not clan_name:
        return {}
    clan = await get_or_create_clan(session, clan_name)
    return clan_bonuses_for_level(clan.level)


async def add_clan_exp(session, clan_name: str | None, amount: int) -> Clan | None:
    if not clan_name or amount <= 0:
        return None
    clan = await get_or_create_clan(session, clan_name)

    clan.exp += int(amount)
    leveled_up = False
    while clan.exp >= clan.exp_to_next:
        clan.exp -= clan.exp_to_next
        clan.level += 1
        clan.exp_to_next = clan_exp_to_next(clan.level)
        leveled_up = True

    if leveled_up:
        session.add(clan)
    return clan


async def get_or_create_clan_daily(session, clan_name: str, date_str: str) -> ClanDaily:
    result = await session.execute(
        select(ClanDaily).where(ClanDaily.clan_name == clan_name, ClanDaily.date == date_str)
    )
    daily = result.scalar_one_or_none()
    if daily:
        return daily

    daily = ClanDaily(
        clan_name=clan_name,
        date=date_str,
        pve_wins=0,
        pvp_wins=0,
        battles=0,
        claimed_pve=False,
        claimed_pvp=False,
        claimed_battles=False,
    )
    session.add(daily)
    await session.flush()
    return daily


async def add_clan_daily_progress(
    session,
    clan_name: str | None,
    pve_win: int = 0,
    pvp_win: int = 0,
    battle: int = 0,
) -> ClanDaily | None:
    if not clan_name:
        return None

    today = datetime.utcnow().strftime("%Y-%m-%d")
    daily = await get_or_create_clan_daily(session, clan_name, today)

    daily.pve_wins += int(pve_win)
    daily.pvp_wins += int(pvp_win)
    daily.battles += int(battle)

    if not daily.claimed_pve and daily.pve_wins >= CLAN_DAILY_QUESTS["pve_wins"]["target"]:
        daily.claimed_pve = True
        await add_clan_exp(session, clan_name, CLAN_DAILY_QUESTS["pve_wins"]["reward_exp"])

    if not daily.claimed_pvp and daily.pvp_wins >= CLAN_DAILY_QUESTS["pvp_wins"]["target"]:
        daily.claimed_pvp = True
        await add_clan_exp(session, clan_name, CLAN_DAILY_QUESTS["pvp_wins"]["reward_exp"])

    if not daily.claimed_battles and daily.battles >= CLAN_DAILY_QUESTS["battles"]["target"]:
        daily.claimed_battles = True
        await add_clan_exp(session, clan_name, CLAN_DAILY_QUESTS["battles"]["reward_exp"])

    session.add(daily)
    return daily
