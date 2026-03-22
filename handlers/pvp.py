import random
from copy import deepcopy
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from models import async_session, User, UserCard, Battle, Technique, UserTechnique, Title
from keyboards.pvp import (
    get_pvp_menu,
    get_pvp_waiting_keyboard,
    get_pvp_challenge_keyboard,
    get_pvp_challenge_input_keyboard,
    get_pvp_battle_keyboard,
    get_pvp_result_keyboard,
)
from utils.daily_quest_progress import add_daily_quest_progress
from utils.pvp_progression import apply_experience_with_pvp_rolls, get_player_pvp_toolkit
from utils.weapon_effects import get_weapon_effect
from utils.pact_effects import get_pact_effect
from utils.black_flash import get_black_flash_chance
from utils.card_rewards import is_weapon_template
from utils.combat_content import (
    BATTLERDAN_DEBATES,
    BATTLE_CE_MIN,
    BATTLE_CE_REGEN_MIN,
    BATTLE_CE_REGEN_SCALE,
    BATTLE_CE_SCALE,
    BATTLE_DOMAIN_COST,
    BATTLE_MAHORAGA_COST,
    BATTLE_RCT_COST,
    MAHORAGA_REPEAT_ADAPT_BONUS,
    MAHORAGA_TURN_ADAPT_STEP,
    get_battlerdan_debate,
    get_battlerdan_option,
)
from handlers.achievements import check_achievements
from utils.clan_progression import (
    CLAN_EXP_PER_PVP_LOSS,
    CLAN_EXP_PER_PVP_WIN,
    add_clan_daily_progress,
    add_clan_exp,
    get_clan_bonuses,
)
from config import (
    DOMAIN_DOT_PER_POINT,
    DOMAIN_DAMAGE_BONUS_PER_POINT,
    RCT_HEAL_BONUS_PER_POINT,
    PVP_COOLDOWN,
    POINTS_PER_PVP_WIN,
)

router = Router()

# Хранилище активных PvP боев
active_pvp_battles = {}
pvp_matchmaking_queue = {}  # telegram_id -> {"joined_at": datetime, "user_id": int, "level": int}
pvp_challenges = {}  # (challenger_tg, accepter_tg) -> created_at
pvp_challenge_target_input = {}  # telegram_id -> created_at


DEFAULT_DOMAIN_DURATION = 3
DEFAULT_SIMPLE_DOMAIN_DURATION = 2
PVP_COOLDOWN_SECONDS = PVP_COOLDOWN
PVP_MATCHMAKING_TIMEOUT = timedelta(minutes=3)
PVP_CHALLENGE_INPUT_TIMEOUT = timedelta(minutes=5)
MAHORAGA_ADAPT_COST = BATTLE_MAHORAGA_COST
DOMAIN_UPKEEP_PER_TURN = 500


CHARACTER_PROFILES = [
    {
        "tokens": ["годжосатору", "satorugojo", "gojosatoru"],
        "domain_name": "Безграничная Пустота",
        "domain_dot_pct": 0.15,
        "domain_damage_bonus": 0.30,
        "domain_effect": "gojo_crit",
        "specials": [
            {
                "key": "blue",
                "name": "Синий",
                "icon": "🔵",
                "ce_cost": 900,
                "multiplier": 1.25,
                "flat": 120,
                "variants": {
                    "amp": {
                        "name": "Усиленный синий",
                        "ce_cost": 1500,
                        "multiplier": 1.5,
                        "flat": 220,
                        "can_dodge": False,
                        "aoe": True,
                    }
                },
            },
            {
                "key": "red",
                "name": "Красный",
                "icon": "🔴",
                "ce_cost": 2600,
                "multiplier": 1.6,
                "flat": 260,
                "variants": {
                    "amp": {
                        "name": "Усиленный красный",
                        "ce_cost": 3600,
                        "multiplier": 1.9,
                        "flat": 360,
                    }
                },
            },
            {
                "key": "purple",
                "name": "Фиолетовый",
                "icon": "🟣",
                "ce_cost": 6200,
                "multiplier": 2.7,
                "flat": 580,
                "variants": {
                    "amp": {
                        "name": "Усиленный фиолетовый",
                        "ce_cost": 9000,
                        "multiplier": 3.25,
                        "flat": 840,
                        "can_dodge": False,
                        "aoe": True,
                        "critical": True,
                        "critical_multiplier": 1.35,
                    }
                },
            },
        ],
    },
    {
        "tokens": ["сукуна", "sukuna", "ryomen"],
        "domain_name": "Храм Злобы",
        "domain_dot_pct": 0.14,
        "domain_damage_bonus": 0.28,
        "domain_effect": "sukuna_dot",
        "specials": [
            {"key": "cleave", "name": "Рассечение", "icon": "🗡", "ce_cost": 900, "multiplier": 1.25, "flat": 180},
            {"key": "dismantle", "name": "Расщепление", "icon": "⚔️", "ce_cost": 1300, "multiplier": 1.5, "flat": 260},
            {"key": "fuga", "name": "Фуга", "icon": "🔥", "ce_cost": 4500, "multiplier": 2.0, "flat": 520},
        ],
    },
    {
        "tokens": ["хигурума", "higuruma"],
        "domain_name": "Судебное Заседание",
        "domain_dot_pct": 0.14,
        "domain_damage_bonus": 0.00,
        "domain_effect": "higuruma_dot",
        "specials": [
            {"key": "gavel", "name": "Молот", "icon": "🔨", "ce_cost": 500, "multiplier": 1.25, "flat": 150},
        ],
    },
    {
        "tokens": ["итадори", "юдзи", "itadori", "yuji"],
        "domain_name": "Территория души",
        "domain_dot_pct": 0.12,
        "domain_damage_bonus": 0.20,
        "domain_effect": "soul_dot",
        "specials": [],
    },
    {
        "tokens": ["мегуми", "megumi"],
        "domain_name": "Сад Химер Теней",
        "domain_dot_pct": 0.11,
        "domain_damage_bonus": 0.18,
        "domain_effect": "slow",
        "domain_slow_pct": 0.15,
        "specials": [],
    },
    {
        "tokens": ["тоджи", "toji"],
        "domain_name": "Нулевая территория",
        "domain_dot_pct": 0.00,
        "domain_damage_bonus": 0.00,
        "domain_effect": "dot",
        "specials": [],
    },
    {
        "tokens": ["хакари", "hakari", "кинзи", "kinji"],
        "domain_name": "Частная Чистая Любовь",
        "domain_dot_pct": 0.00,
        "domain_damage_bonus": 0.00,
        "domain_effect": "hakari_jackpot",
        "specials": [],
    },
    {
        "tokens": ["баттлердан", "battlerdan"],
        "domain_name": "Дебаты",
        "domain_dot_pct": 0.00,
        "domain_damage_bonus": 0.00,
        "domain_effect": "battlerdan_debate",
        "specials": [
            {"key": "battle_blue", "name": "Синяя правда", "icon": "🔵", "ce_cost": 700, "multiplier": 1.25, "flat": 120},
            {"key": "battle_red", "name": "Красная правда", "icon": "🔴", "ce_cost": 1000, "multiplier": 1.5, "flat": 220},
            {"key": "battle_bombs", "name": "Маленькие бомбочки", "icon": "🤏💣", "ce_cost": 0, "multiplier": 0.7, "flat": 40},
        ],
    },
    {
        "tokens": ["годжослав", "godzhoslav"],
        "domain_name": "Бесконечные Бели",
        "domain_dot_pct": 0.15,
        "domain_damage_bonus": 0.30,
        "domain_effect": "gojo_crit",
        "specials": [
            {"key": "gears", "name": "Шестерёнки", "icon": "⚙️", "ce_cost": 700, "multiplier": 1.2, "flat": 120},
            {"key": "ducks", "name": "Уточки", "icon": "🦆", "ce_cost": 800, "multiplier": 0.0, "flat": 0, "effect": "duck_guard", "block_hits": 1},
            {"key": "white", "name": "Белый", "icon": "⚪", "ce_cost": 5000, "multiplier": 2.5, "flat": 500},
        ],
    },
    {
        "tokens": ["дагон", "dagon"],
        "domain_name": "Горизонт плена скандхи",
        "domain_dot_pct": 0.17,
        "domain_damage_bonus": 0.26,
        "domain_effect": "dot",
        "specials": [
            {"key": "tidal", "name": "Приливный обвал", "icon": "🌊", "ce_cost": 1700, "multiplier": 1.65, "flat": 250},
            {"key": "swarm", "name": "Стая глубин", "icon": "🦑", "ce_cost": 2600, "multiplier": 2.05, "flat": 360, "aoe": True},
        ],
    },
    {
        "tokens": ["ханами", "hanami"],
        "domain_name": "Цветущий гнев",
        "domain_dot_pct": 0.14,
        "domain_damage_bonus": 0.22,
        "domain_effect": "dot",
        "domain_slow_pct": 0.18,
        "specials": [
            {"key": "roots", "name": "Корни-ловушки", "icon": "🌿", "ce_cost": 1100, "multiplier": 1.45, "flat": 180, "can_dodge": False},
            {"key": "blossom", "name": "Цветочный обвал", "icon": "🌸", "ce_cost": 1800, "multiplier": 1.75, "flat": 260},
        ],
    },
    {
        "tokens": ["дзёго", "джого", "jogo"],
        "domain_name": "Гроб стальной горы",
        "domain_dot_pct": 0.16,
        "domain_damage_bonus": 0.28,
        "domain_effect": "gojo_crit",
        "specials": [
            {"key": "ember", "name": "Вулканический залп", "icon": "🔥", "ce_cost": 1400, "multiplier": 1.55, "flat": 220},
            {"key": "eruption", "name": "Извержение", "icon": "🌋", "ce_cost": 2400, "multiplier": 2.0, "flat": 340, "aoe": True},
        ],
    },
    {
        "tokens": ["махито", "mahito"],
        "domain_name": "Самовоплощение идеала",
        "domain_dot_pct": 0.18,
        "domain_damage_bonus": 0.31,
        "domain_effect": "soul_dot",
        "specials": [
            {"key": "idle_touch", "name": "Преобразование души", "icon": "🫳", "ce_cost": 1900, "multiplier": 1.8, "flat": 290, "can_dodge": False},
            {"key": "distortion", "name": "Искажённый обвал", "icon": "🧬", "ce_cost": 3100, "multiplier": 2.2, "flat": 420},
        ],
    },
    {
        "tokens": ["кендзяку", "kenjaku"],
        "domain_name": "Чрево поглощённых проклятий",
        "domain_dot_pct": 0.19,
        "domain_damage_bonus": 0.33,
        "domain_effect": "dot",
        "specials": [
            {"key": "gravity", "name": "Гравитационный обвал", "icon": "🪐", "ce_cost": 2200, "multiplier": 1.95, "flat": 320},
            {"key": "uzumaki", "name": "Узумаки", "icon": "🌀", "ce_cost": 3600, "multiplier": 2.45, "flat": 520, "aoe": True},
        ],
    },
    {
        "tokens": ["ураумэ", "uraume"],
        "domain_name": "Ледяная камера",
        "domain_dot_pct": 0.12,
        "domain_damage_bonus": 0.18,
        "domain_effect": "dot",
        "domain_slow_pct": 0.18,
        "specials": [
            {"key": "frost_lance", "name": "Морозное копьё", "icon": "❄️", "ce_cost": 1100, "multiplier": 1.55, "flat": 220, "can_dodge": False},
            {"key": "icefall", "name": "Ледопад", "icon": "🧊", "ce_cost": 2200, "multiplier": 1.85, "flat": 320, "aoe": True},
        ],
    },
    {
        "tokens": ["кашимо", "хадзимэ", "kashimo", "hajime"],
        "domain_name": "Поле грома",
        "domain_dot_pct": 0.13,
        "domain_damage_bonus": 0.24,
        "domain_effect": "soul_dot",
        "specials": [
            {"key": "lightning_bolt", "name": "Громовой разряд", "icon": "⚡", "ce_cost": 1000, "multiplier": 1.6, "flat": 220, "can_dodge": False},
            {"key": "amber_beast", "name": "Мифический зверь: Янтарь", "icon": "🟨", "ce_cost": 3600, "multiplier": 2.35, "flat": 480, "can_dodge": False, "critical": True, "critical_multiplier": 1.25},
        ],
    },
]


DEFAULT_PROFILE = {
    "domain_name": "Расширение территории",
    "domain_dot_pct": 0,
    "domain_damage_bonus": 0,
    "domain_effect": "dot",
    "specials": [],
}


ITADORI_TOKENS = ("итадори", "юдзи", "itadori", "yuji")
MEGUMI_TOKENS = ("мегуми", "megumi")
TOJI_TOKENS = ("тоджи", "toji")
HAKARI_TOKENS = ("хакари", "hakari", "кинзи", "kinji")
GOJO_TOKENS = ("годжосатору", "satorugojo", "gojosatoru")
BATTLERDAN_TOKENS = ("баттлердан", "battlerdan")

TECH_BLOOD = "Кровавая Магия"
TECH_SUKUNA_CURSE = "Проклятие Сукуны"
TECH_INFINITY = "Бесконечность"
TECH_SIX_EYES = "Шесть Глаз"
TECH_DOMAIN_AMPLIFICATION = "Растяжение территории"


def _find_battle_by_user_tg(telegram_id: int):
    direct = active_pvp_battles.get(telegram_id)
    if direct:
        return direct

    for battle in active_pvp_battles.values():
        if battle["player1_tg"] == telegram_id or battle["player2_tg"] == telegram_id:
            return battle
    return None


def _has_active_any_battle(telegram_id: int) -> bool:
    if _find_battle_by_user_tg(telegram_id):
        return True
    try:
        from handlers.coop_pvp import active_coop_battles  # local import to avoid circular deps
        return telegram_id in active_coop_battles
    except Exception:
        return False


def _remove_from_matchmaking_queue(*telegram_ids: int):
    for telegram_id in telegram_ids:
        pvp_matchmaking_queue.pop(telegram_id, None)


def _cleanup_matchmaking_queue():
    now = datetime.utcnow()
    stale_ids = []
    for telegram_id, payload in pvp_matchmaking_queue.items():
        joined_at = payload.get("joined_at", now)
        if now - joined_at > PVP_MATCHMAKING_TIMEOUT:
            stale_ids.append(telegram_id)
            continue
        if _has_active_any_battle(telegram_id):
            stale_ids.append(telegram_id)

    for telegram_id in stale_ids:
        pvp_matchmaking_queue.pop(telegram_id, None)


def _matchmaking_candidate_tgs(user: User) -> list[int]:
    waiting_players = [
        (telegram_id, payload)
        for telegram_id, payload in pvp_matchmaking_queue.items()
        if telegram_id != user.telegram_id
    ]
    waiting_players.sort(key=lambda item: item[1].get("joined_at", datetime.utcnow()))

    ordered = []
    used = set()
    for level_range in (5, 10, None):
        for telegram_id, payload in waiting_players:
            if telegram_id in used:
                continue
            level_diff = abs(payload.get("level", user.level) - user.level)
            if level_range is not None and level_diff > level_range:
                continue
            used.add(telegram_id)
            ordered.append(telegram_id)
    return ordered


def _get_pvp_cooldown_seconds_left(user: User) -> int:
    if not user.last_battle_time:
        return 0
    elapsed = (datetime.utcnow() - user.last_battle_time).total_seconds()
    remaining = int(PVP_COOLDOWN_SECONDS - elapsed)
    return max(0, remaining)


def _cleanup_challenge_input():
    now = datetime.utcnow()
    expired = [
        telegram_id
        for telegram_id, created_at in pvp_challenge_target_input.items()
        if now - created_at > PVP_CHALLENGE_INPUT_TIMEOUT
    ]
    for telegram_id in expired:
        pvp_challenge_target_input.pop(telegram_id, None)


async def _get_user_technique_names(session, user_id: int) -> set[str]:
    result = await session.execute(
        select(Technique.name)
        .join(UserTechnique, UserTechnique.technique_id == Technique.id)
        .where(UserTechnique.user_id == user_id)
    )
    return {row[0] for row in result if row and row[0]}


async def _find_user_by_target(session, target_raw: str) -> User | None:
    raw = (target_raw or "").strip()
    if not raw:
        return None

    if raw.startswith("@"):
        username = raw[1:].strip().lower()
        if not username:
            return None
        result = await session.execute(
            select(User).where(func.lower(User.username) == username)
        )
        return result.scalar_one_or_none()

    if raw.isdigit():
        result = await session.execute(
            select(User).where(User.telegram_id == int(raw))
        )
        return result.scalar_one_or_none()

    result = await session.execute(
        select(User).where(func.lower(User.username) == raw.lower())
    )
    return result.scalar_one_or_none()


async def _send_direct_challenge(bot, challenger: User, target: User) -> tuple[bool, str]:
    if challenger.telegram_id == target.telegram_id:
        return False, "Нельзя вызвать самого себя."

    if _has_active_any_battle(challenger.telegram_id) or _has_active_any_battle(target.telegram_id):
        return False, "Один из игроков уже находится в PvP бою."

    challenger_cd = _get_pvp_cooldown_seconds_left(challenger)
    if challenger_cd > 0:
        return False, f"Подожди {challenger_cd} сек. перед следующим PvP боем."

    target_cd = _get_pvp_cooldown_seconds_left(target)
    if target_cd > 0:
        return False, "У выбранного игрока ещё не прошёл PvP-кулдаун."

    if not challenger.slot_1_card_id:
        return False, "У тебя не экипирована главная карта."
    if not target.slot_1_card_id:
        return False, "У выбранного игрока не экипирована главная карта."

    key = (challenger.telegram_id, target.telegram_id)
    pvp_challenges[key] = datetime.utcnow()

    challenger_name = challenger.first_name or challenger.username or "грок"
    try:
        await bot.send_message(
            target.telegram_id,
            "⚔️ <b>Тебя вызвали на PvP бой!</b>\n\n"
            f"{challenger_name} отправил тебе прямой вызов.\n"
            "Нажми «Принять», чтобы начать бой.",
            reply_markup=get_pvp_challenge_keyboard(challenger.telegram_id),
            parse_mode="HTML",
        )
    except Exception:
        pvp_challenges.pop(key, None)
        return False, "Не удалось отправить вызов игроку. Возможно, он не писал боту."

    return True, f"Вызов отправлен игроку {target.first_name or target.username or target.telegram_id}."


async def _process_direct_challenge_request(message: Message, target_raw: str):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        challenger = result.scalar_one_or_none()
        if not challenger:
            await message.answer("Сначала используй /start")
            return

        target = await _find_user_by_target(session, target_raw)
        if not target:
            await message.answer("грок не найден. Укажи корректный @username или telegram_id.")
            return

        ok, response_text = await _send_direct_challenge(message.bot, challenger, target)
        await message.answer(response_text)


def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _name_has_tokens(name: str, tokens: tuple[str, ...]) -> bool:
    normalized = _normalize_name(name)
    return any(token in normalized for token in tokens)


def _is_gojo_name(name: str) -> bool:
    normalized = _normalize_name(name)
    return normalized in GOJO_TOKENS


def _get_character_profile(card_name: str) -> dict:
    normalized = _normalize_name(card_name)
    for profile in CHARACTER_PROFILES:
        if any(token in normalized for token in profile["tokens"]):
            return profile
    return DEFAULT_PROFILE


def _is_higuruma(state: dict) -> bool:
    card = state.get("main")
    template = getattr(card, "card_template", None)
    name = template.name if template else ""
    normalized = _normalize_name(name)
    return "хигурума" in normalized or "higuruma" in normalized


def _is_toji_state(state: dict) -> bool:
    return bool(state.get("is_toji"))


def _is_hakari_state(state: dict) -> bool:
    return bool(state.get("is_hakari"))


def _player_num_by_tg(battle: dict, tg_id: int) -> int:
    return 1 if battle["player1_tg"] == tg_id else 2


def _enemy_num(player_num: int) -> int:
    return 2 if player_num == 1 else 1


def _is_user_turn(battle: dict, tg_id: int) -> bool:
    return battle["current_player"] == _player_num_by_tg(battle, tg_id)


def _default_turn_flags() -> dict:
    return {
        "main_attack_used": False,
        "shikigami_attack_used": False,
        "rct_used": False,
        "mahoraga_used": False,
    }


def _get_turn_flags(battle: dict, player_num: int) -> dict:
    turn_flags = battle.setdefault("turn_flags", {})
    if player_num not in turn_flags:
        turn_flags[player_num] = _default_turn_flags()
    else:
        turn_flags[player_num].setdefault("main_attack_used", bool(turn_flags[player_num].get("attack_used", False)))
        turn_flags[player_num].setdefault("shikigami_attack_used", False)
        turn_flags[player_num].setdefault("rct_used", False)
        turn_flags[player_num].setdefault("mahoraga_used", False)
    return turn_flags[player_num]


def _reset_turn_flags(battle: dict, player_num: int):
    battle.setdefault("turn_flags", {})[player_num] = _default_turn_flags()


def _main_attack_used(flags: dict) -> bool:
    return bool(flags.get("main_attack_used", flags.get("attack_used", False)))


def _living_shikigami(state: dict) -> UserCard | None:
    shikigami = state.get("shikigami")
    if shikigami and shikigami.is_alive():
        return shikigami
    return None


def _entity_card(state: dict, unit: str = "main") -> UserCard | None:
    if unit == "shikigami":
        return _living_shikigami(state)
    return state["main"]


def _entity_name(state: dict, unit: str = "main") -> str:
    card = state.get("main") if unit == "main" else state.get("shikigami")
    if card and getattr(card, "card_template", None) and card.card_template.name:
        return card.card_template.name
    return "цель"


def _entity_display_label(state: dict, unit: str = "main") -> str:
    if unit == "shikigami":
        return f"шикигами { _entity_name(state, unit) }"
    return _entity_name(state, unit)


def _entity_speed(state: dict, unit: str = "main") -> int:
    card = _entity_card(state, unit)
    if not card:
        return 0
    return max(1, int(card.speed))


def _team_speed(state: dict) -> int:
    return max(_entity_speed(state, "main"), _entity_speed(state, "shikigami"))


def _has_active_mahoraga(state: dict) -> bool:
    if not state.get("has_mahoraga", False):
        return False
    if state.get("mahoraga_requires_shikigami") and not _living_shikigami(state):
        return False
    return True


def _pending_response_for(battle: dict, player_num: int) -> dict | None:
    pending = battle.get("pending_domain_response")
    if pending and pending.get("target") == player_num:
        return pending
    return None


def _pending_battlerdan_for(battle: dict, player_num: int) -> dict | None:
    pending = battle.get("battlerdan_pending")
    if not pending:
        return None
    if pending.get("stage") in {"topic", "choose"} and pending.get("owner") == player_num:
        return pending
    if pending.get("stage") == "guess" and pending.get("target") == player_num:
        return pending
    return None


def _pending_special_variant_for(battle: dict, player_num: int) -> str | None:
    pending = battle.get("pending_special_variant") or {}
    return pending.get(player_num)


def _set_pending_special_variant(battle: dict, player_num: int, key: str):
    battle.setdefault("pending_special_variant", {})[player_num] = key


def _clear_pending_special_variant(battle: dict, player_num: int):
    pending = battle.get("pending_special_variant")
    if not pending:
        return
    pending.pop(player_num, None)
    if not pending:
        battle["pending_special_variant"] = {}


def _pending_target_for(battle: dict, player_num: int) -> dict | None:
    pending = battle.get("pending_target") or {}
    return pending.get(player_num)


def _set_pending_target(battle: dict, player_num: int, payload: dict):
    battle.setdefault("pending_target", {})[player_num] = payload


def _clear_pending_target(battle: dict, player_num: int):
    pending = battle.get("pending_target")
    if not pending:
        return
    pending.pop(player_num, None)
    if not pending:
        battle["pending_target"] = {}


def _find_special(state: dict, key: str) -> dict | None:
    return next((sp for sp in state.get("specials", []) if sp.get("key") == key), None)


def _resolve_special_instance(special: dict, variant: str | None = None) -> dict:
    resolved = dict(special)
    if variant and variant != "base":
        payload = dict((special.get("variants") or {}).get(variant, {}))
        if payload:
            resolved.update(payload)
            resolved["variant"] = variant
    return resolved


def _mahoraga_percent(value: float) -> int:
    return int(max(0.0, min(1.0, float(value or 0.0))) * 100)


def _apply_mahoraga_turn_growth(battle: dict, player_num: int):
    state = battle["fighters"][player_num]
    if not _has_active_mahoraga(state) or not state.get("mahoraga_ready"):
        return

    adapt_map = state.setdefault("mahoraga_adapt", {})
    labels = state.setdefault("mahoraga_adapt_labels", {})
    updated = []
    for attack_key, current in list(adapt_map.items()):
        if current >= 1.0:
            continue
        new_value = min(1.0, float(current) + MAHORAGA_TURN_ADAPT_STEP)
        if new_value <= current:
            continue
        adapt_map[attack_key] = new_value
        label = labels.get(attack_key, "атака")
        updated.append(f"🌀 Адаптация Махораги к «{label}» выросла до {_mahoraga_percent(new_value)}%.")

    battle["log"].extend(updated)


def _battlerdan_topic_ids() -> list[int]:
    return [int(debate.get("id", 0)) for debate in BATTLERDAN_DEBATES]


def _battlerdan_options(topic_id: int) -> list[int]:
    debate = get_battlerdan_debate(topic_id)
    if not debate:
        return []
    return [int(option.get("id", 0)) for option in debate.get("options", [])]


def _resolve_battlerdan_guess(battle: dict, pending: dict, guessed: int):
    owner_num = pending.get("owner")
    target_num = pending.get("target")
    choice = pending.get("choice")
    topic_id = pending.get("topic_id")
    owner_state = battle["fighters"][owner_num]
    owner_name = owner_state["main"].card_template.name
    target_name = battle["fighters"][target_num]["main"].card_template.name
    guessed_option = get_battlerdan_option(topic_id, guessed)

    if guessed == choice:
        owner_state["ce"] = 0
        owner_state["ce_lock_turns"] = 3
        battle["log"].append(
            f"⚖️ Дебаты: {target_name} угадал ответ. Проклятая энергия {owner_name} запечатана на 3 хода."
        )
    else:
        owner_state["higuruma_sword_ready"] = True
        battle["log"].append(
            f"⚖️ Дебаты: {target_name} ошибся. {owner_name} раскрывает Золотую правду."
        )
        if guessed_option and guessed_option.get("refutation"):
            battle["log"].append(str(guessed_option["refutation"]))


def _get_action_state(battle: dict, player_num: int) -> dict:
    fighter_state = battle["fighters"][player_num]
    pending_special = _pending_special_variant_for(battle, player_num)
    if pending_special:
        special = _find_special(fighter_state, pending_special)
        if special and special.get("variants"):
            amp = (special.get("variants") or {}).get("amp", {})
            return {
                "force_response": True,
                "special_variant_key": special.get("key"),
                "special_variant_base_cost": int(special.get("ce_cost", 0)),
                "special_variant_amp_cost": int(amp.get("ce_cost", special.get("ce_cost", 0))),
                "show_end_turn": False,
            }
        _clear_pending_special_variant(battle, player_num)

    pending_target = _pending_target_for(battle, player_num)
    if pending_target:
        enemy_state = battle["fighters"][_enemy_num(player_num)]
        return {
            "force_response": True,
            "target_selection": True,
            "target_prompt": pending_target.get("prompt", "Выбери цель атаки."),
            "can_target_main": True,
            "can_target_shikigami": bool(_living_shikigami(enemy_state)),
            "show_end_turn": False,
        }

    pending_battlerdan = _pending_battlerdan_for(battle, player_num)
    if pending_battlerdan:
        return {
            "force_response": True,
            "battlerdan_stage": pending_battlerdan.get("stage"),
            "battlerdan_options": pending_battlerdan.get("options", [1, 2, 3, 4]),
            "show_end_turn": False,
        }
    pending = _pending_response_for(battle, player_num)
    if pending:
        can_domain = fighter_state.get("has_domain", False)
        can_simple = fighter_state.get("has_simple_domain", False) and fighter_state.get("simple_domain_turns", 0) == 0
        flags = _get_turn_flags(battle, player_num)
        can_mahoraga = _can_use_mahoraga(battle, player_num, flags)
        return {
            "force_response": True,
            "can_domain": can_domain,
            "can_simple": can_simple,
            "can_mahoraga": can_mahoraga,
            "can_skip_response": not (can_domain or can_simple or can_mahoraga),
            "show_end_turn": False,
        }

    flags = _get_turn_flags(battle, player_num)
    simple_active = fighter_state.get("simple_domain_turns", 0) > 0

    can_main_attack = not _main_attack_used(flags)
    can_special = can_main_attack and not simple_active

    can_simple = fighter_state.get("has_simple_domain", False) and not simple_active
    can_mahoraga = _can_use_mahoraga(battle, player_num, flags)
    can_sword = fighter_state.get("higuruma_sword_ready", False) and not _main_attack_used(flags)
    can_shikigami_attack = bool(_living_shikigami(fighter_state)) and not flags.get("shikigami_attack_used", False)

    return {
        "force_response": False,
        "can_main_attack": can_main_attack,
        "can_shikigami_attack": can_shikigami_attack,
        "can_special": can_special,
        "can_domain": fighter_state.get("has_domain", False),
        "can_simple": can_simple,
        "can_rct": fighter_state.get("has_reverse_ct", False) and not flags.get("rct_used", False),
        "can_mahoraga": can_mahoraga,
        "can_sword": can_sword,
        "show_end_turn": True,
    }


def _get_fighter_speed(state: dict) -> int:
    return _team_speed(state)


def _get_domain_slow_pct(battle: dict, attacker_num: int, defender_num: int) -> float:
    domain = battle.get("domain_state")
    if not domain or domain.get("owner") != attacker_num:
        return 0.0
    if domain.get("target") != defender_num:
        return 0.0
    defender_state = battle["fighters"][defender_num]
    if defender_state.get("simple_domain_turns", 0) > 0:
        return 0.0
    return float(domain.get("slow_pct", 0.0) or 0.0)


def _dodge_chance(
    battle: dict,
    attacker_state: dict,
    defender_state: dict,
    attacker_num: int,
    defender_num: int,
    attacker_unit: str = "main",
    defender_unit: str = "main",
) -> float:
    attacker_speed = max(1, _entity_speed(attacker_state, attacker_unit))
    defender_speed = _entity_speed(defender_state, defender_unit)
    slow_pct = _get_domain_slow_pct(battle, attacker_num, defender_num)
    if slow_pct:
        defender_speed = max(1, int(defender_speed * (1 - slow_pct)))
    if defender_speed <= attacker_speed:
        return 0.0
    speed_diff = defender_speed - attacker_speed
    # 1 speed point = 1% dodge chance, capped at 100%
    return min(1.0, speed_diff / 100.0)


def _is_guaranteed_hit(battle: dict, attacker_num: int, defender_num: int) -> bool:
    domain = battle.get("domain_state")
    if not domain or domain.get("owner") != attacker_num:
        return False
    if domain.get("target") != defender_num:
        return False
    defender_state = battle["fighters"][defender_num]
    if defender_state.get("simple_domain_turns", 0) > 0:
        return False
    return True


def _can_use_mahoraga(battle: dict, player_num: int, flags: dict | None = None) -> bool:
    state = battle["fighters"][player_num]
    if not _has_active_mahoraga(state):
        return False
    flags = flags or _get_turn_flags(battle, player_num)
    if flags.get("mahoraga_used", False):
        return False
    cost = state.get("mahoraga_cost", MAHORAGA_ADAPT_COST)
    if state.get("ce", 0) < cost:
        return False
    domain = battle.get("domain_state")
    if domain and domain.get("owner") != player_num and domain.get("target") == player_num:
        return True
    return not state.get("mahoraga_ready", False)


def _get_base_damage(state: dict) -> int:
    damage = int(state["main"].attack * state.get("attack_multiplier", 1.0))
    return max(1, damage)

def _domain_attack_bonus(battle: dict, attacker_num: int, defender_num: int | None = None) -> float:
    domain = battle.get("domain_state")
    if not domain or domain["owner"] != attacker_num:
        return 1.0
    if defender_num is not None:
        defender_state = battle["fighters"][defender_num]
        if defender_state.get("simple_domain_turns", 0) > 0:
            return 1.0
    return 1.0 + domain.get("damage_bonus", 0.0)


def _apply_mahoraga_adaptation(
    battle: dict,
    defender_num: int,
    attack_key: str | None,
    attack_label: str | None,
    dealt_damage: int,
):
    if not attack_key:
        return
    defender_state = battle["fighters"][defender_num]
    if not _has_active_mahoraga(defender_state) or not defender_state.get("mahoraga_ready"):
        return

    adapt_map = defender_state.setdefault("mahoraga_adapt", {})
    label_map = defender_state.setdefault("mahoraga_adapt_labels", {})
    seen_before = attack_key in adapt_map
    current = float(adapt_map.get(attack_key, 0.0))
    label = attack_label or "атака"
    label_map[attack_key] = label

    if not seen_before:
        adapt_map[attack_key] = 0.0
        battle["log"].append(f"🌀 Махорага начал анализ атаки «{label}».")
        return

    new_value = min(1.0, current + MAHORAGA_REPEAT_ADAPT_BONUS)
    adapt_map[attack_key] = new_value
    if new_value > current:
        battle["log"].append(
            f"🌀 Повтор техники ускоряет адаптацию Махораги к «{label}» до {_mahoraga_percent(new_value)}%."
        )


def _deal_damage(
    battle: dict,
    attacker_num: int,
    defender_num: int,
    raw_damage: int,
    ignore_defense: bool = False,
    ignore_infinity: bool = False,
    attack_key: str | None = None,
    attack_label: str | None = None,
    can_dodge: bool = True,
    target: str = "main",
    attacker_unit: str = "main",
) -> tuple[int, bool, float, bool]:
    attacker_state = battle["fighters"][attacker_num]
    defender_state = battle["fighters"][defender_num]
    defender_card = _entity_card(defender_state, target)
    if not defender_card or not defender_card.is_alive():
        return 0, False, 0.0, False

    mahoraga_progress = 0.0
    if attack_key and _has_active_mahoraga(defender_state) and defender_state.get("mahoraga_ready"):
        adapt_map = defender_state.setdefault("mahoraga_adapt", {})
        mahoraga_progress = float(adapt_map.get(attack_key, 0.0))
        if mahoraga_progress >= 1.0:
            label = attack_label or "атака"
            battle["log"].append(f"🌀 Махорага блокирует «{label}» (100%).")
            return 0, False, 0.0, False

    if defender_state.get("block_next_hits", 0) > 0:
        defender_state["block_next_hits"] -= 1
        return 0, False, 0.0, True

    guaranteed_hit = _is_guaranteed_hit(battle, attacker_num, defender_num)
    infinity_chance = float(defender_state.get("infinity_chance", 0.0) or 0.0)
    if target == "main" and infinity_chance > 0 and not ignore_infinity and not guaranteed_hit:
        battle["log"].append("∞ Бесконечность блокирует атаку.")
        return 0, False, 0.0, False

    if can_dodge and not guaranteed_hit:
        chance = _dodge_chance(
            battle,
            attacker_state,
            defender_state,
            attacker_num,
            defender_num,
            attacker_unit=attacker_unit,
            defender_unit=target,
        )
        if chance > 0 and random.random() < chance:
            return 0, True, chance, False

    attacker_bonus = _domain_attack_bonus(battle, attacker_num, defender_num)
    final_raw = max(1, int(raw_damage * attacker_bonus))
    if mahoraga_progress > 0:
        final_raw = max(1, int(final_raw * (1.0 - mahoraga_progress)))
    before_hp = int(defender_card.hp)
    if ignore_defense:
        dealt = defender_card.take_true_damage(final_raw)
    else:
        dealt = defender_card.take_damage(final_raw)
    if (
        target == "main"
        and defender_card.hp <= 0
        and defender_state.get("survive_lethal_available", False)
    ):
        defender_card.hp = 1
        defender_state["survive_lethal_available"] = False
        dealt = max(0, before_hp - 1)
        battle["log"].append(f"📜 Пакт выживания срабатывает: {defender_card.card_template.name} остаётся на 1 HP.")
    _apply_mahoraga_adaptation(battle, defender_num, attack_key, attack_label, dealt)
    return dealt, False, 0.0, False


def _apply_pact_attack_bonus(attacker_state: dict, raw_damage: int) -> tuple[int, float | None]:
    if not attacker_state.get("next_attack_ready", False):
        return raw_damage, None
    mult = float(attacker_state.get("next_attack_multiplier", 1.0))
    attacker_state["next_attack_ready"] = False
    attacker_state["next_attack_multiplier"] = 1.0
    if mult == 1.0:
        return raw_damage, None
    return int(raw_damage * mult), mult

def _domain_power(state: dict) -> int:
    main = state["main"]
    shikigami = _living_shikigami(state)
    support_bonus = (shikigami.attack + shikigami.defense) // 3 if shikigami else 0
    domain_level = state.get("domain_level", 0)
    return (
        main.attack
        + main.defense
        + main.speed
        + support_bonus
        + domain_level * 40
        + random.randint(0, 120)
    )


def _spend_ce(state: dict, amount: int) -> bool:
    if state["ce"] < amount:
        return False
    state["ce"] -= amount
    return True


def _format_fighter_line(prefix: str, state: dict) -> str:
    simple_left = state.get("simple_domain_turns", 0)
    simple_text = f" | 🛡 {simple_left}х" if simple_left > 0 else ""
    title = state.get("title")
    title_line = f"👑 {title.icon} {title.name}\n" if title else ""
    weapon = state.get("weapon")
    shikigami = state.get("shikigami")
    weapon2 = state.get("weapon2")
    weapon_name = weapon.card_template.name if weapon and weapon.card_template else "—"
    weapon2_name = weapon2.card_template.name if weapon2 and weapon2.card_template else "—"
    support_line = f"🗡 {weapon_name} | 🗡 {weapon2_name}" if weapon2 else f"🗡 {weapon_name}"
    text = (
        f"{prefix} {state['main'].card_template.name}\n"
        f"{title_line}"
        f"{support_line}\n"
        f"❤️ {state['main'].hp}/{state['main'].max_hp} | "
        f"💧 {state['ce']}/{state['max_ce']}{simple_text} | "
        f"⚔️ {state['main'].attack} | 🛡 {state['main'].defense} | 💨 {state['main'].speed}\n"
    )
    if shikigami and shikigami.card_template:
        if shikigami.is_alive():
            text += (
                f"🐺 {shikigami.card_template.name}\n"
                f"❤️ {shikigami.hp}/{shikigami.max_hp} | "
                f"⚔️ {shikigami.attack} | 🛡 {shikigami.defense} | 💨 {shikigami.speed}\n"
            )
        else:
            text += f"☠️ {shikigami.card_template.name} повержен\n"
    return text


def _battle_view_text(battle: dict, viewer_tg: int) -> str:
    viewer_num = _player_num_by_tg(battle, viewer_tg)
    enemy_num = _enemy_num(viewer_num)
    you = battle["fighters"][viewer_num]
    enemy = battle["fighters"][enemy_num]

    text = (
        f"⚔️ <b>PvP бой — ход {battle['turn']}</b>\n\n"
        f"<b>Ты:</b>\n{_format_fighter_line('🃏', you)}\n"
        f"<b>Противник:</b>\n{_format_fighter_line('🃏', enemy)}"
    )

    domain = battle.get("domain_state")
    if domain:
        owner_num = domain["owner"]
        owner_name = battle["fighters"][owner_num]["main"].card_template.name
        text += (
            f"\n🏯 <b>Активная территория:</b> {domain['name']}\n"
            f"Владелец: {owner_name} | Осталось: {domain['turns_left']}х"
        )

    pending = _pending_response_for(battle, viewer_num)
    if pending:
        text += "\n\n⚠️ <b>Ответ на домен:</b> выбери Расширение или Простую территорию."

    pending_special = _pending_special_variant_for(battle, viewer_num)
    if pending_special:
        special = _find_special(you, pending_special)
        if special:
            text += f"\n\n⚙️ <b>{special['name']}:</b> выбери обычный или усиленный вариант."

    pending_target = _pending_target_for(battle, viewer_num)
    if pending_target:
        text += f"\n\n🎯 <b>{pending_target.get('prompt', 'Выбери цель атаки.')}</b>"

    pending_battlerdan = _pending_battlerdan_for(battle, viewer_num)
    if pending_battlerdan:
        stage = pending_battlerdan.get("stage")
        if stage == "topic":
            themes = []
            for debate in BATTLERDAN_DEBATES:
                themes.append(f"{debate['id']}. {debate['question']}")
            text += "\n\n📚 <b>Дебаты:</b> выбери тему.\n" + "\n".join(themes)
        else:
            debate = get_battlerdan_debate(pending_battlerdan.get("topic_id"))
            if debate:
                options_text = "\n".join(
                    f"{option['id']}. {option['full_label']}" for option in debate.get("options", [])
                )
                prompt = "выбери правду" if stage == "choose" else "угадай правду"
                text += (
                    f"\n\n🗣 <b>Дебаты:</b> {debate['question']}\n"
                    f"{options_text}\n\n"
                    f"⚖️ Нужно {prompt}."
                )

    if battle["log"]:
        last_logs = battle["log"][-5:]
        text += "\n\n<b>Последние события:</b>\n" + "\n".join(f"• {line}" for line in last_logs)

    text += "\n\n⚡ <b>Твой ход!</b>" if battle["current_player"] == viewer_num else "\n⏳ <b>Ход соперника...</b>"
    return text


async def _edit_or_send_battle_message(callback: CallbackQuery, telegram_id: int, battle: dict):
    viewer_num = _player_num_by_tg(battle, telegram_id)
    is_your_turn = battle["current_player"] == viewer_num
    text = _battle_view_text(battle, telegram_id)
    action_state = _get_action_state(battle, viewer_num) if is_your_turn else None
    keyboard = get_pvp_battle_keyboard(
        is_your_turn=is_your_turn,
        fighter_state=battle["fighters"][viewer_num],
        action_state=action_state,
    )
    existing_id = battle["messages"].get(telegram_id)

    if callback.from_user.id == telegram_id and callback.message:
        try:
            edited = await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            battle["messages"][telegram_id] = edited.message_id
            return edited
        except Exception:
            pass

    if existing_id:
        try:
            edited = await callback.bot.edit_message_text(
                chat_id=telegram_id,
                message_id=existing_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            if hasattr(edited, "message_id"):
                battle["messages"][telegram_id] = edited.message_id
            return edited
        except Exception:
            pass

    try:
        sent = await callback.bot.send_message(
            telegram_id,
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        battle["messages"][telegram_id] = sent.message_id
        return sent
    except Exception:
        return None


async def _update_battle_messages(callback: CallbackQuery, battle: dict):
    await _edit_or_send_battle_message(callback, battle["player1_tg"], battle)
    await _edit_or_send_battle_message(callback, battle["player2_tg"], battle)


def _apply_start_turn_effects(battle: dict, player_num: int):
    state = battle["fighters"][player_num]

    ce_lock = int(state.get("ce_lock_turns", 0) or 0)
    if ce_lock > 0:
        state["ce"] = 0
        state["ce_lock_turns"] = ce_lock - 1
        battle["log"].append("🔒 Проклятая энергия запечатана и не восстанавливается.")
    else:
        # Реген CE
        state["ce"] = min(state["max_ce"], state["ce"] + state["ce_regen"])

    jackpot_turns = int(state.get("hakari_jackpot_turns", 0) or 0)
    if jackpot_turns > 0:
        before = state["main"].hp
        state["main"].hp = state["main"].max_hp
        healed = state["main"].hp - before
        if healed > 0:
            battle["log"].append("🎰 Джекпот: HP восстановлены до максимума.")
        state["hakari_jackpot_turns"] = jackpot_turns - 1

    _apply_mahoraga_turn_growth(battle, player_num)

    simple_active = state.get("simple_domain_turns", 0) > 0
    domain = battle.get("domain_state")
    pending_response = _pending_response_for(battle, player_num)

    if domain and domain.get("owner") == player_num:
        upkeep = int(domain.get("upkeep_cost", DOMAIN_UPKEEP_PER_TURN))
        if upkeep > 0:
            if state["ce"] >= upkeep:
                state["ce"] -= upkeep
                battle["log"].append(f"🏯 Поддержание территории: -{upkeep} CE.")
            else:
                battle["log"].append("🏯 Недостаточно CE для поддержания территории. Домен рассеялся.")
                battle["domain_state"] = None
                battle["pending_domain_response"] = None
                domain = None

    if domain and domain["target"] == player_num:
        if state.get("ignore_domain_effects"):
            if pending_response:
                battle["pending_domain_response"] = None
            battle["log"].append("🛡 Тоджи игнорирует эффекты территории.")
            domain["turns_left"] -= 1
            if domain["turns_left"] <= 0:
                battle["log"].append("🌫 Эффект территории рассеялся.")
                battle["domain_state"] = None
        elif pending_response:
            battle["log"].append("🏯 Домен активен, ожидается ответ.")
        elif simple_active:
            battle["log"].append("🛡 Простая территория блокирует эффект вражеской территории.")
        else:
            owner_state = battle["fighters"][domain["owner"]]
            effect = domain.get("effect", "dot")
            targets = [("main", state["main"])]
            shikigami = _living_shikigami(state)
            if shikigami:
                targets.append(("shikigami", shikigami))
            for unit, card in targets:
                base_raw = int(card.max_hp * domain["dot_pct"]) + int(owner_state["main"].attack * 0.25)
                if effect == "gojo_crit":
                    raw = int(base_raw * 2.0)
                    raw = int(raw * (1 + domain.get("damage_bonus", 0.0)))
                    dealt = card.take_damage(max(1, raw))
                    if unit == "main":
                        battle["log"].append(f"🏯 {domain['name']} наносит критический урон: {dealt}.")
                    else:
                        battle["log"].append(
                            f"🏯 {domain['name']} накрывает шикигами {_entity_name(state, 'shikigami')}: {dealt} критического урона."
                        )
                elif effect == "soul_dot":
                    raw = int(base_raw * (1 + domain.get("damage_bonus", 0.0)))
                    dealt = card.take_true_damage(max(1, raw))
                    if unit == "main":
                        battle["log"].append(f"🏯 {domain['name']} бьёт по душе: {dealt} урона.")
                    else:
                        battle["log"].append(
                            f"🏯 {domain['name']} задевает душу шикигами {_entity_name(state, 'shikigami')}: {dealt} урона."
                        )
                else:
                    raw = int(base_raw * (1 + domain.get("damage_bonus", 0.0)))
                    dealt = card.take_damage(max(1, raw))
                    if unit == "main":
                        battle["log"].append(f"🏯 {domain['name']} наносит {dealt} урона.")
                    else:
                        battle["log"].append(
                            f"🏯 {domain['name']} задевает шикигами {_entity_name(state, 'shikigami')}: {dealt} урона."
                        )
                if unit == "shikigami" and not card.is_alive():
                    battle["log"].append(f"☠️ Шикигами {_entity_name(state, 'shikigami')} повержен.")
            domain["turns_left"] -= 1
            if domain["turns_left"] <= 0:
                battle["log"].append("🌫 Эффект территории рассеялся.")
                battle["domain_state"] = None

    if simple_active:
        state["simple_domain_turns"] -= 1
        if state["simple_domain_turns"] == 0:
            battle["log"].append("🛡 Простая территория закончилась.")


async def _advance_turn(callback: CallbackQuery, battle: dict, acting_player_num: int):
    _clear_pending_target(battle, acting_player_num)
    _clear_pending_special_variant(battle, acting_player_num)
    next_player = _enemy_num(acting_player_num)
    battle["current_player"] = next_player
    battle["turn"] += 1
    _reset_turn_flags(battle, next_player)

    _apply_start_turn_effects(battle, next_player)
    if not battle["fighters"][next_player]["main"].is_alive():
        await end_pvp_battle(callback, battle, winner_is_player1=acting_player_num == 1)
        return

    await _update_battle_messages(callback, battle)


def _collect_weapon_effects(*weapons: UserCard | None) -> dict[str, float | bool]:
    effects: dict[str, float | bool] = {
        "basic_multiplier": 1.0,
        "ignore_defense": False,
        "ignore_infinity": False,
        "basic_ignore_infinity": False,
        "ignore_dodge": False,
        "black_flash_bonus": 0.0,
    }
    for weapon in weapons:
        effect = get_weapon_effect(weapon)
        if not effect:
            continue
        if effect.get("type") == "basic_multiplier":
            roll = random.uniform(effect.get("min", 1.0), effect.get("max", 1.0))
            effects["basic_multiplier"] = max(float(effects["basic_multiplier"]), roll)
        elif effect.get("type") == "ignore_defense":
            effects["ignore_defense"] = True
        elif effect.get("type") == "ignore_infinity":
            effects["ignore_infinity"] = True
        elif effect.get("type") == "basic_ignore_infinity":
            effects["basic_ignore_infinity"] = True
        elif effect.get("type") == "ignore_dodge":
            effects["ignore_dodge"] = True
        elif effect.get("type") == "black_flash_bonus":
            effects["black_flash_bonus"] = max(
                float(effects["black_flash_bonus"]),
                float(effect.get("chance_bonus", 0.0) or 0.0),
            )
    return effects


def _action_basic_attack(battle: dict, attacker_num: int, target: str = "main", actor: str = "main"):
    attacker = battle["fighters"][attacker_num]
    defender_num = _enemy_num(attacker_num)
    defender = battle["fighters"][defender_num]
    attacker_card = _entity_card(attacker, actor)
    if not attacker_card or not attacker_card.is_alive():
        return defender["main"].is_alive()

    target_label = _entity_display_label(defender, target)
    black_flash = False
    restore_amount = 0

    if actor == "shikigami":
        base_damage = max(1, int(attacker_card.attack * attacker.get("attack_multiplier", 1.0)))
        ignore_defense = False
        ignore_infinity = False
        can_dodge = True
        attack_key = "shikigami_basic"
        attack_label = f"атака шикигами {_entity_name(attacker, 'shikigami')}"
        attack_icon = "🐺"
    else:
        base_damage = _get_base_damage(attacker)
        weapon_effects = _collect_weapon_effects(
            attacker.get("weapon"), attacker.get("weapon2")
        )
        ignore_defense = bool(weapon_effects["ignore_defense"])
        ignore_infinity = (
            bool(weapon_effects["ignore_infinity"])
            or bool(weapon_effects["basic_ignore_infinity"])
            or bool(attacker.get("has_domain_amplification", False))
        )
        can_dodge = not bool(weapon_effects["ignore_dodge"])
        multiplier = float(weapon_effects["basic_multiplier"])
        if multiplier != 1.0:
            base_damage = int(base_damage * multiplier)
        black_flash_chance = min(
            1.0,
            float(attacker["black_flash_chance"]) + float(weapon_effects["black_flash_bonus"]),
        )
        black_flash = random.random() < black_flash_chance
        if black_flash:
            base_damage = int(base_damage * 1.10)
        base_damage, _ = _apply_pact_attack_bonus(attacker, base_damage)
        attack_key = "basic"
        attack_label = "удар рукой"
        attack_icon = "👊"

    dealt, dodged, dodge_chance, blocked = _deal_damage(
        battle,
        attacker_num,
        defender_num,
        base_damage,
        ignore_defense=ignore_defense,
        ignore_infinity=ignore_infinity,
        attack_key=attack_key,
        attack_label=attack_label,
        can_dodge=can_dodge,
        target=target,
        attacker_unit=actor,
    )
    if blocked:
        battle["log"].append("🦆 Уточки блокируют удар.")
        return defender["main"].is_alive()
    if dodged:
        dodge_pct = int(dodge_chance * 100)
        battle["log"].append(f"💨 {target_label} уклонился от атаки (шанс {dodge_pct}%).")
        return defender["main"].is_alive()
    if black_flash:
        restore_amount = min(4000, attacker["max_ce"] - attacker["ce"])
        attacker["ce"] += restore_amount
        battle["log"].append(
            f"⚫ Чёрная молния по цели {target_label}! Урон: {dealt}, восстановлено CE: {restore_amount}."
        )
    else:
        battle["log"].append(f"{attack_icon} Атака по цели {target_label} наносит {dealt} урона.")

    if target == "shikigami" and defender.get("shikigami") and not defender["shikigami"].is_alive():
        battle["log"].append(f"☠️ Шикигами { _entity_name(defender, 'shikigami') } повержен.")

    return defender["main"].is_alive()


def _action_special(
    battle: dict,
    attacker_num: int,
    key: str,
    variant: str | None = None,
    target: str = "main",
):
    attacker = battle["fighters"][attacker_num]
    defender_num = _enemy_num(attacker_num)
    defender = battle["fighters"][defender_num]

    if attacker.get("simple_domain_turns", 0) > 0:
        return False, "Во время простой территории нельзя использовать спецтехники."

    special = _find_special(attacker, key)
    if not special:
        return False, "Эта техника недоступна для твоей карты."

    special = _resolve_special_instance(special, variant)

    if not _spend_ce(attacker, int(special["ce_cost"])):
        return False, "Недостаточно CE для этой техники."

    if special.get("effect") == "duck_guard":
        block_hits = max(1, int(special.get("block_hits", 1)))
        attacker["block_next_hits"] = max(attacker.get("block_next_hits", 0), block_hits)
        battle["log"].append("🦆 Уточки перекрывают следующий удар врага.")
        return defender["main"].is_alive(), None

    raw = int(_get_base_damage(attacker) * special["multiplier"] + special.get("flat", 0))
    if special.get("critical"):
        raw = int(raw * float(special.get("critical_multiplier", 1.25)))
    raw, pact_mult = _apply_pact_attack_bonus(attacker, raw)

    weapon_effects = _collect_weapon_effects(
        attacker.get("weapon"), attacker.get("weapon2")
    )
    ignore_defense = bool(weapon_effects["ignore_defense"])
    ignore_infinity = bool(weapon_effects["ignore_infinity"])
    can_dodge = bool(special.get("can_dodge", True)) and not bool(weapon_effects["ignore_dodge"])
    if special.get("critical"):
        ignore_defense = True

    if special.get("aoe"):
        entries = []
        extra_logs = []
        for unit in ("main", "shikigami"):
            target_card = _entity_card(defender, unit)
            if not target_card:
                continue
            dealt, dodged, dodge_chance, blocked = _deal_damage(
                battle,
                attacker_num,
                defender_num,
                raw,
                ignore_defense=ignore_defense,
                ignore_infinity=ignore_infinity,
                attack_key=f"special_{special['key']}",
                attack_label=special["name"],
                can_dodge=can_dodge,
                target=unit,
                attacker_unit="main",
            )
            label = _entity_display_label(defender, unit)
            if blocked:
                entries.append(f"{label}: блок")
                continue
            if dodged:
                dodge_pct = int(dodge_chance * 100)
                entries.append(f"{label}: уклонение {dodge_pct}%")
                continue
            entries.append(f"{label}: {dealt} урона")
            if unit == "shikigami" and defender.get("shikigami") and not defender["shikigami"].is_alive():
                extra_logs.append(f"☠️ Шикигами { _entity_name(defender, 'shikigami') } повержен.")

        extra = " Критический удар." if special.get("critical") else ""
        battle["log"].append(
            f"{special['icon']} {special['name']} поражает область ({'; '.join(entries)}) "
            f"(-{special['ce_cost']} CE).{extra}"
        )
        battle["log"].extend(extra_logs)
        return defender["main"].is_alive(), None

    dealt, dodged, dodge_chance, blocked = _deal_damage(
        battle,
        attacker_num,
        defender_num,
        raw,
        ignore_defense=ignore_defense,
        ignore_infinity=ignore_infinity,
        attack_key=f"special_{special['key']}",
        attack_label=special["name"],
        can_dodge=can_dodge,
        target=target,
        attacker_unit="main",
    )
    target_label = _entity_display_label(defender, target)
    if blocked:
        battle["log"].append("🦆 Уточки блокируют удар.")
        return defender["main"].is_alive(), None
    if dodged:
        dodge_pct = int(dodge_chance * 100)
        battle["log"].append(
            f"💨 {target_label} уклонился от техники «{special['name']}» (шанс {dodge_pct}%)."
        )
        return defender["main"].is_alive(), None
    extra = " Критический удар." if special.get("critical") else ""
    battle["log"].append(
        f"{special['icon']} {special['name']} наносит {dealt} урона по цели {target_label} "
        f"(-{special['ce_cost']} CE).{extra}"
    )
    if target == "shikigami" and defender.get("shikigami") and not defender["shikigami"].is_alive():
        battle["log"].append(f"☠️ Шикигами { _entity_name(defender, 'shikigami') } повержен.")
    return defender["main"].is_alive(), None


def _apply_higuruma_domain_effect(battle: dict, attacker_num: int, defender_num: int):
    attacker = battle["fighters"][attacker_num]
    defender = battle["fighters"][defender_num]
    if defender.get("ignore_domain_effects"):
        battle["log"].append("🛡 Тоджи не подчиняется суду Хигурумы.")
        battle["domain_state"] = None
        battle["pending_domain_response"] = None
        battle["log"].append("🏯 Территория Хигурумы рассеялась.")
        return
    if random.random() < 0.5:
        defender["ce"] = 0
        defender["ce_lock_turns"] = 3
        battle["log"].append("⚖️ Суд Хигурумы: проклятая энергия цели запечатана на 3 хода.")
    else:
        attacker["higuruma_sword_ready"] = True
        defender["ce"] = 0
        defender["ce_lock_turns"] = 3
        battle["log"].append("⚖️ Суд Хигурумы: выпал Золотой меч и конфискация CE на 3 хода.")
    battle["domain_state"] = None
    battle["pending_domain_response"] = None
    battle["log"].append("🏯 Территория Хигурумы рассеялась.")


def _apply_hakari_domain_effect(battle: dict, attacker_num: int):
    attacker = battle["fighters"][attacker_num]
    chance = float(attacker.get("hakari_jackpot_chance", 0.33) or 0.33)
    if random.random() < chance:
        attacker["hakari_jackpot_turns"] = 4
        attacker["hakari_jackpot_chance"] = 0.33
        battle["log"].append("🎰 Джекпот! Хакари входит в режим автоматического лечения на 4 хода.")
    else:
        new_chance = min(1.0, chance + 0.17)
        attacker["hakari_jackpot_chance"] = new_chance
        battle["log"].append(
            f"🎰 Не повезло... шанс джекпота повышен до {int(new_chance * 100)}%."
        )
    battle["domain_state"] = None
    battle["pending_domain_response"] = None
    battle["log"].append("🏯 Территория Хакари рассеялась.")


def _action_domain(battle: dict, attacker_num: int):
    attacker = battle["fighters"][attacker_num]
    defender_num = _enemy_num(attacker_num)
    defender = battle["fighters"][defender_num]
    cost = attacker["domain_cost"]

    if not attacker.get("has_domain"):
        return False, "У тебя нет техники расширения территории."

    if not _spend_ce(attacker, cost):
        return False, "Недостаточно CE для расширения территории."

    if attacker.get("is_battlerdan") or attacker.get("domain_effect") == "battlerdan_debate":
        domain = battle.get("domain_state")
        if domain and domain.get("owner") == attacker_num:
            attacker["ce"] += cost
            return False, "Твоя территория уже активна."
        if domain and domain.get("owner") == defender_num:
            attacker_power = _domain_power(attacker)
            defender_power = _domain_power(defender)
            if attacker_power > defender_power:
                battle["log"].append("💥 Битва территорий: дебаты победили и подавили вражеский домен.")
                battle["domain_state"] = None
            elif attacker_power < defender_power:
                battle["log"].append("💥 Битва территорий: твои дебаты проиграли.")
                return True, None
            else:
                battle["log"].append("💥 Битва территорий: ничья, оба домена рассеялись.")
                battle["domain_state"] = None

        battle["battlerdan_pending"] = {
            "stage": "topic",
            "owner": attacker_num,
            "target": defender_num,
            "topic_id": None,
            "choice": None,
            "options": _battlerdan_topic_ids(),
        }
        battle["log"].append("🏯 Баттлердан открывает дебаты. Сначала выбери тему, затем истину.")
        return True, None

    domain = battle.get("domain_state")
    if domain and domain["owner"] == attacker_num:
        attacker["ce"] += cost
        return False, "Твоя территория уже активна."

    if domain and domain["owner"] == defender_num:
        # Битва территорий
        attacker_power = _domain_power(attacker)
        defender_power = _domain_power(defender)

        if attacker_power > defender_power:
            if _is_higuruma(attacker):
                battle["log"].append("💥 Битва территорий: ты победил и подавил вражеский домен.")
                _apply_higuruma_domain_effect(battle, attacker_num, defender_num)
                return True, None
            if _is_hakari_state(attacker):
                battle["log"].append("💥 Битва территорий: ты победил и подавил вражеский домен.")
                _apply_hakari_domain_effect(battle, attacker_num)
                return True, None
            battle["domain_state"] = {
                "owner": attacker_num,
                "target": defender_num,
                "name": attacker["domain_name"],
                "effect": attacker.get("domain_effect", "dot"),
                "turns_left": DEFAULT_DOMAIN_DURATION,
                "dot_pct": attacker["domain_dot_pct"],
                "damage_bonus": attacker["domain_damage_bonus"],
                "slow_pct": attacker.get("domain_slow_pct", 0.0),
                "upkeep_cost": DOMAIN_UPKEEP_PER_TURN,
            }
            battle["log"].append("💥 Битва территорий: ты победил и подавил вражеский домен.")
        elif attacker_power < defender_power:
            battle["log"].append("💥 Битва территорий: твой домен проиграл.")
        else:
            battle["domain_state"] = None
            battle["log"].append("💥 Битва территорий закончилась ничьёй. Оба домена рассеялись.")
        return True, None

    if _is_higuruma(attacker):
        _apply_higuruma_domain_effect(battle, attacker_num, defender_num)
        return True, None
    if _is_hakari_state(attacker):
        _apply_hakari_domain_effect(battle, attacker_num)
        return True, None

    battle["domain_state"] = {
        "owner": attacker_num,
        "target": defender_num,
        "name": attacker["domain_name"],
        "effect": attacker.get("domain_effect", "dot"),
        "turns_left": DEFAULT_DOMAIN_DURATION,
        "dot_pct": attacker["domain_dot_pct"],
        "damage_bonus": attacker["domain_damage_bonus"],
        "slow_pct": attacker.get("domain_slow_pct", 0.0),
        "upkeep_cost": DOMAIN_UPKEEP_PER_TURN,
    }
    battle["log"].append(f"🏯 Активирована территория: {attacker['domain_name']} (-{cost} CE).")
    return True, None


def _action_simple_domain(battle: dict, attacker_num: int):
    attacker = battle["fighters"][attacker_num]
    cost = attacker["simple_domain_cost"]

    if not attacker.get("has_simple_domain"):
        return False, "У тебя нет техники простой территории."
    if attacker.get("simple_domain_turns", 0) > 0:
        return False, "Простая территория уже активна."
    if not _spend_ce(attacker, cost):
        return False, "Недостаточно CE для простой территории."

    attacker["simple_domain_turns"] = DEFAULT_SIMPLE_DOMAIN_DURATION
    if cost:
        battle["log"].append(
            f"🛡 Простая территория активирована на {DEFAULT_SIMPLE_DOMAIN_DURATION} хода "
            f"(-{cost} CE)."
        )
    else:
        battle["log"].append(
            f"🛡 Простая территория активирована на {DEFAULT_SIMPLE_DOMAIN_DURATION} хода (бесплатно)."
        )
    return True, None


def _action_reverse_ct(battle: dict, attacker_num: int):
    attacker = battle["fighters"][attacker_num]
    cost = attacker["rct_cost"]

    if not attacker.get("has_reverse_ct"):
        return False, "У тебя нет обратной проклятой техники."
    if attacker["main"].hp >= attacker["main"].max_hp:
        return False, "HP уже полное."
    if not _spend_ce(attacker, cost):
        return False, "Недостаточно CE для лечения."

    base_heal = attacker["main"].max_hp * 0.35 + attacker["main"].defense * 0.2
    rct_bonus = attacker.get("rct_level", 0) * RCT_HEAL_BONUS_PER_POINT
    heal_amount = int(base_heal * (1 + rct_bonus))
    before = attacker["main"].hp
    attacker["main"].hp = min(attacker["main"].max_hp, attacker["main"].hp + heal_amount)
    healed = attacker["main"].hp - before
    battle["log"].append(f"♻️ Обратная техника восстановила {healed} HP (-{cost} CE).")
    return True, None


def _action_mahoraga(battle: dict, attacker_num: int):
    attacker = battle["fighters"][attacker_num]
    cost = attacker.get("mahoraga_cost", MAHORAGA_ADAPT_COST)

    if not attacker.get("has_mahoraga"):
        return False, "У тебя нет Махораги в колоде."
    domain = battle.get("domain_state")
    enemy_domain_active = bool(domain and domain.get("owner") != attacker_num and domain.get("target") == attacker_num)
    if attacker.get("mahoraga_ready") and not enemy_domain_active:
        return False, "Махорага уже готов к адаптации."
    if not _spend_ce(attacker, cost):
        return False, "Недостаточно CE для адаптации."

    if enemy_domain_active:
        domain_name = domain.get("name", "территория")
        adapt_map = attacker.setdefault("mahoraga_domain_adapt", {})
        progress = float(adapt_map.get(domain_name, 0))
        if progress >= 1.0:
            battle["domain_state"] = None
            battle["pending_domain_response"] = None
            battle["log"].append(
                f"🌀 Махорага уже адаптирован и ломает территорию «{domain_name}» (-{cost} CE)."
            )
        else:
            progress = min(1.0, progress + 0.5)
            adapt_map[domain_name] = progress
            if progress >= 1.0:
                battle["domain_state"] = None
                battle["pending_domain_response"] = None
                battle["log"].append(
                    f"🌀 Махорага полностью адаптировался к «{domain_name}» и сломал её (-{cost} CE)."
                )
            else:
                battle["log"].append(
                    f"🌀 Махорага адаптируется к территории «{domain_name}» (50%) (-{cost} CE)."
                )
    attacker["mahoraga_ready"] = True
    if not enemy_domain_active:
        battle["log"].append(f"🌀 Махорага готовится к адаптации (-{cost} CE).")
    return True, None


def _action_higuruma_sword(battle: dict, attacker_num: int, target: str = "main"):
    attacker = battle["fighters"][attacker_num]
    if not attacker.get("higuruma_sword_ready", False):
        skill_name = "Золотая правда" if attacker.get("is_battlerdan") else "Золотой меч"
        return False, f"{skill_name} сейчас недоступна."

    defender_num = _enemy_num(attacker_num)
    defender = battle["fighters"][defender_num]
    target_card = _entity_card(defender, target)
    if not target_card:
        return False, "Эта цель уже недоступна."
    target_card.hp = 0
    attacker["higuruma_sword_ready"] = False
    target_label = _entity_display_label(defender, target)
    if attacker.get("is_battlerdan"):
        battle["log"].append(f"⚖️ Золотая правда Баттлердана мгновенно сокрушает {target_label}.")
    else:
        battle["log"].append(f"⚖️ Золотой меч Хигурумы мгновенно поражает {target_label}.")
    return defender["main"].is_alive(), None

def _action_pact(battle: dict, attacker_num: int, pact_id: int):
    attacker = battle["fighters"][attacker_num]
    if attacker.get("pacts_disabled"):
        return False, "Тоджи не может использовать пакты."
    pacts = attacker.get("pacts", [])
    if not pacts:
        return False, "У тебя нет пактов."

    pact = next((p for p in pacts if getattr(p, "id", None) == pact_id), None)
    if not pact or not pact.card_template:
        return False, "Пакт не найден."

    used = attacker.setdefault("pact_used", set())
    if pact_id in used:
        return False, "Этот пакт уже использован."

    effect = get_pact_effect(pact)
    if not effect:
        return False, "Этот пакт не имеет эффекта."

    used.add(pact_id)

    next_mult = float(effect.get("next_attack_multiplier", 1.0))
    if next_mult != 1.0:
        attacker["next_attack_multiplier"] *= next_mult
        attacker["next_attack_ready"] = True

    ce_mult = float(effect.get("ce_regen_multiplier", 1.0))
    if ce_mult != 1.0:
        attacker["ce_regen"] = max(0, int(attacker["ce_regen"] * ce_mult))

    exp_mult = float(effect.get("post_battle_exp_multiplier", 1.0))
    if exp_mult > 1.0:
        attacker["post_battle_exp_multiplier"] = max(
            float(attacker.get("post_battle_exp_multiplier", 1.0)),
            exp_mult,
        )

    if effect.get("survive_lethal_once"):
        attacker["survive_lethal_available"] = True

    if effect.get("consume_after_battle"):
        attacker.setdefault("single_use_pacts_to_consume", set()).add(pact_id)

    return True, effect.get("label", "Пакт активирован.")


async def _consume_single_use_pacts(session, user: User, fighter_state: dict) -> list[str]:
    pact_ids = set(fighter_state.get("single_use_pacts_to_consume", set()) or set())
    consumed_names = []
    for pact_id in pact_ids:
        pact_card = await session.scalar(
            select(UserCard)
            .options(selectinload(UserCard.card_template))
            .where(UserCard.id == pact_id, UserCard.user_id == user.id)
        )
        if not pact_card:
            continue
        if user.slot_4_card_id == pact_id:
            user.slot_4_card_id = None
        if user.slot_5_card_id == pact_id:
            user.slot_5_card_id = None
        if pact_card.card_template and pact_card.card_template.name:
            consumed_names.append(pact_card.card_template.name)
        await session.delete(pact_card)
    return consumed_names


def _requires_target_selection(battle: dict, attacker_num: int, aoe: bool = False) -> bool:
    if aoe:
        return False
    defender = battle["fighters"][_enemy_num(attacker_num)]
    return bool(_living_shikigami(defender))


def _queue_target_selection(battle: dict, player_num: int, **payload):
    _set_pending_target(battle, player_num, payload)


def _execute_targeted_action(
    battle: dict,
    attacker_num: int,
    payload: dict,
    target: str,
) -> tuple[bool | None, str | None]:
    if target not in {"main", "shikigami"}:
        return None, "Некорректная цель."

    defender = battle["fighters"][_enemy_num(attacker_num)]
    if target == "shikigami" and not _living_shikigami(defender):
        return None, "У противника больше нет живого шикигами."

    flags = _get_turn_flags(battle, attacker_num)
    kind = payload.get("kind")

    if kind == "basic":
        actor = payload.get("actor", "main")
        if actor == "shikigami":
            if flags.get("shikigami_attack_used", False):
                return None, "Шикигами уже атаковал в этом ходу."
            defender_alive = _action_basic_attack(battle, attacker_num, target=target, actor="shikigami")
            flags["shikigami_attack_used"] = True
            return defender_alive, None

        if _main_attack_used(flags):
            return None, "Ты уже использовал атаку в этом ходу."
        defender_alive = _action_basic_attack(battle, attacker_num, target=target, actor="main")
        flags["main_attack_used"] = True
        return defender_alive, None

    if kind == "special":
        if _main_attack_used(flags):
            return None, "Ты уже использовал атаку в этом ходу."
        defender_alive, error = _action_special(
            battle,
            attacker_num,
            str(payload.get("key") or ""),
            variant=payload.get("variant"),
            target=target,
        )
        if error:
            return None, error
        flags["main_attack_used"] = True
        return defender_alive, None

    if kind == "higuruma_sword":
        if _main_attack_used(flags):
            return None, "Ты уже использовал атаку в этом ходу."
        defender_alive, error = _action_higuruma_sword(battle, attacker_num, target=target)
        if error:
            return None, error
        flags["main_attack_used"] = True
        return defender_alive, None

    return None, "Это действие нельзя направить в цель."


async def _process_action(callback: CallbackQuery, action: str):
    user_id = callback.from_user.id
    battle = _find_battle_by_user_tg(user_id)

    if not battle:
        await callback.answer("Бой не найден.", show_alert=True)
        return

    if not _is_user_turn(battle, user_id):
        await callback.answer("Сейчас не твой ход.", show_alert=True)
        return

    attacker_num = _player_num_by_tg(battle, user_id)
    defender_num = _enemy_num(attacker_num)
    attacker_user_id = battle["player1_id"] if attacker_num == 1 else battle["player2_id"]
    attacker_state = battle["fighters"][attacker_num]

    pending_target = _pending_target_for(battle, attacker_num)
    if pending_target:
        if action == "target_back":
            _clear_pending_target(battle, attacker_num)
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return
        if action not in ("target_main", "target_shikigami"):
            await callback.answer("Сначала выбери цель текущей атаки.", show_alert=True)
            return
        target = "main" if action == "target_main" else "shikigami"
        defender_alive, error = _execute_targeted_action(battle, attacker_num, pending_target, target)
        if error:
            _clear_pending_target(battle, attacker_num)
            await _update_battle_messages(callback, battle)
            await callback.answer(error, show_alert=True)
            return
        _clear_pending_target(battle, attacker_num)
        if defender_alive is False:
            await end_pvp_battle(callback, battle, winner_is_player1=attacker_num == 1)
            await callback.answer()
            return
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    pending_special = _pending_special_variant_for(battle, attacker_num)
    if pending_special:
        if action == "special_variant_back":
            _clear_pending_special_variant(battle, attacker_num)
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return
        if action.startswith("special_pick_"):
            try:
                payload = action.split("special_pick_", 1)[1]
                key, variant = payload.rsplit("_", 1)
            except ValueError:
                await callback.answer("Некорректный вариант техники.", show_alert=True)
                return
            if key != pending_special:
                await callback.answer("Сначала заверши выбор текущей техники.", show_alert=True)
                return
            flags = _get_turn_flags(battle, attacker_num)
            if _main_attack_used(flags):
                await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
                return
            special = _find_special(attacker_state, key)
            if not special:
                _clear_pending_special_variant(battle, attacker_num)
                await callback.answer("Эта техника недоступна.", show_alert=True)
                return
            resolved = _resolve_special_instance(special, variant)
            if _requires_target_selection(battle, attacker_num, aoe=bool(resolved.get("aoe"))):
                _clear_pending_special_variant(battle, attacker_num)
                _queue_target_selection(
                    battle,
                    attacker_num,
                    kind="special",
                    key=key,
                    variant=variant,
                    prompt=f"Выбери цель для техники «{resolved['name']}».",
                )
                await _update_battle_messages(callback, battle)
                await callback.answer()
                return

            defender_alive, error = _action_special(battle, attacker_num, key, variant=variant)
            if error:
                await callback.answer(error, show_alert=True)
                return
            _clear_pending_special_variant(battle, attacker_num)
            flags["main_attack_used"] = True
            if not defender_alive:
                await end_pvp_battle(callback, battle, winner_is_player1=attacker_num == 1)
                await callback.answer()
                return
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return
        await callback.answer("Сначала выбери вариант техники.", show_alert=True)
        return

    pending_battlerdan = _pending_battlerdan_for(battle, attacker_num)
    if pending_battlerdan:
        if action.startswith("battlerdan_topic_"):
            try:
                topic_id = int(action.split("battlerdan_topic_", 1)[1])
            except ValueError:
                await callback.answer("Некорректная тема.", show_alert=True)
                return
            debate = get_battlerdan_debate(topic_id)
            if not debate:
                await callback.answer("Такая тема недоступна.", show_alert=True)
                return
            pending_battlerdan["topic_id"] = topic_id
            pending_battlerdan["stage"] = "choose"
            pending_battlerdan["options"] = _battlerdan_options(topic_id)
            battle["log"].append(f"📚 Баттлердан выбирает тему: {debate['question']}")
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return

        if action.startswith("battlerdan_choose_"):
            try:
                choice = int(action.split("battlerdan_choose_", 1)[1])
            except ValueError:
                await callback.answer("Некорректный выбор.", show_alert=True)
                return
            if not get_battlerdan_option(pending_battlerdan.get("topic_id"), choice):
                await callback.answer("Такой ответ недоступен.", show_alert=True)
                return
            pending_battlerdan["choice"] = choice
            pending_battlerdan["stage"] = "guess"
            pending_battlerdan["options"] = _battlerdan_options(pending_battlerdan.get("topic_id"))
            battle["log"].append("🗣 Баттлердан выбрал истину. Противник пытается угадать...")
            await _advance_turn(callback, battle, attacker_num)
            await callback.answer()
            return

        if action.startswith("battlerdan_guess_"):
            try:
                guess = int(action.split("battlerdan_guess_", 1)[1])
            except ValueError:
                await callback.answer("Некорректный выбор.", show_alert=True)
                return
            if not get_battlerdan_option(pending_battlerdan.get("topic_id"), guess):
                await callback.answer("Такой ответ недоступен.", show_alert=True)
                return
            _resolve_battlerdan_guess(battle, pending_battlerdan, guess)
            battle["battlerdan_pending"] = None
            await _advance_turn(callback, battle, attacker_num)
            await callback.answer()
            return

        await callback.answer("Нужно сделать выбор в дебатах.", show_alert=True)
        return

    pending = _pending_response_for(battle, attacker_num)
    if pending:
        if action not in ("domain", "simple", "skip_response", "mahoraga"):
            await callback.answer("Нужно ответить на домен: расширение, простая территория или Махорага.", show_alert=True)
            return

        if action == "domain":
            ok, error = _action_domain(battle, attacker_num)
            if error:
                await callback.answer(error, show_alert=True)
                return
            await check_achievements(attacker_user_id, "territories_used", value=1)
        elif action == "simple":
            ok, error = _action_simple_domain(battle, attacker_num)
            if error:
                await callback.answer(error, show_alert=True)
                return
        elif action == "mahoraga":
            flags = _get_turn_flags(battle, attacker_num)
            if flags.get("mahoraga_used"):
                await callback.answer("Адаптация уже активирована в этом ходу.", show_alert=True)
                return
            ok, error = _action_mahoraga(battle, attacker_num)
            if error:
                await callback.answer(error, show_alert=True)
                return
            flags["mahoraga_used"] = True
        else:
            battle["log"].append("⏭ Ответ на домен пропущен.")

        battle["pending_domain_response"] = None
        await _advance_turn(callback, battle, attacker_num)
        await callback.answer()
        return

    flags = _get_turn_flags(battle, attacker_num)

    if action == "basic":
        if _main_attack_used(flags):
            await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
            return
        if _requires_target_selection(battle, attacker_num):
            _queue_target_selection(
                battle,
                attacker_num,
                kind="basic",
                actor="main",
                prompt="Выбери цель для обычной атаки.",
            )
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return
        defender_alive = _action_basic_attack(battle, attacker_num, target="main", actor="main")
        flags["main_attack_used"] = True
        if not defender_alive:
            await end_pvp_battle(callback, battle, winner_is_player1=attacker_num == 1)
            await callback.answer()
            return
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    if action == "shikigami_basic":
        if not _living_shikigami(attacker_state):
            await callback.answer("Твой шикигами уже повержен.", show_alert=True)
            return
        if flags.get("shikigami_attack_used", False):
            await callback.answer("Шикигами уже атаковал в этом ходу.", show_alert=True)
            return
        if _requires_target_selection(battle, attacker_num):
            _queue_target_selection(
                battle,
                attacker_num,
                kind="basic",
                actor="shikigami",
                prompt=f"Выбери цель для шикигами {_entity_name(attacker_state, 'shikigami')}.",
            )
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return
        defender_alive = _action_basic_attack(battle, attacker_num, target="main", actor="shikigami")
        flags["shikigami_attack_used"] = True
        if not defender_alive:
            await end_pvp_battle(callback, battle, winner_is_player1=attacker_num == 1)
            await callback.answer()
            return
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    if action == "higuruma_sword":
        if _main_attack_used(flags):
            await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
            return
        if _requires_target_selection(battle, attacker_num):
            sword_name = "Золотая правда" if attacker_state.get("is_battlerdan") else "Золотой меч"
            _queue_target_selection(
                battle,
                attacker_num,
                kind="higuruma_sword",
                prompt=f"Выбери цель для {sword_name}.",
            )
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return
        defender_alive, error = _action_higuruma_sword(battle, attacker_num, target="main")
        if error:
            await callback.answer(error, show_alert=True)
            return
        flags["main_attack_used"] = True
        if not defender_alive:
            await end_pvp_battle(callback, battle, winner_is_player1=attacker_num == 1)
            await callback.answer()
            return
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    if action.startswith("special_"):
        if _main_attack_used(flags):
            await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
            return
        special_action = action.split("special_", 1)[1]
        if special_action.startswith("menu_"):
            key = special_action.split("menu_", 1)[1]
            special = _find_special(battle["fighters"][attacker_num], key)
            if not special or not special.get("variants"):
                await callback.answer("Для этой техники нет вариантов.", show_alert=True)
                return
            _set_pending_special_variant(battle, attacker_num, key)
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return
        special = _find_special(attacker_state, special_action)
        if special and _requires_target_selection(battle, attacker_num, aoe=bool(special.get("aoe"))):
            _queue_target_selection(
                battle,
                attacker_num,
                kind="special",
                key=special_action,
                variant=None,
                prompt=f"Выбери цель для техники «{special['name']}».",
            )
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return

        defender_alive, error = _action_special(battle, attacker_num, special_action)
        if error:
            await callback.answer(error, show_alert=True)
            return
        flags["main_attack_used"] = True
        if not defender_alive:
            await end_pvp_battle(callback, battle, winner_is_player1=attacker_num == 1)
            await callback.answer()
            return
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    if action == "rct":
        if flags.get("rct_used"):
            await callback.answer("ОПТ уже использована в этом ходу.", show_alert=True)
            return
        ok, error = _action_reverse_ct(battle, attacker_num)
        if error:
            await callback.answer(error, show_alert=True)
            return
        flags["rct_used"] = True
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    if action == "mahoraga":
        if flags.get("mahoraga_used"):
            await callback.answer("Адаптация уже активирована в этом ходу.", show_alert=True)
            return
        ok, error = _action_mahoraga(battle, attacker_num)
        if error:
            await callback.answer(error, show_alert=True)
            return
        flags["mahoraga_used"] = True
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    if action.startswith("pact_"):
        try:
            pact_id = int(action.split("_", 1)[1])
        except ValueError:
            await callback.answer("Некорректный пакт.", show_alert=True)
            return
        ok, message = _action_pact(battle, attacker_num, pact_id)
        if not ok:
            await callback.answer(message, show_alert=True)
            return
        await _update_battle_messages(callback, battle)
        await callback.answer(message, show_alert=True)
        return

    if action == "domain":
        prev_domain = battle.get("domain_state")
        prev_owner = prev_domain.get("owner") if prev_domain else None
        ok, error = _action_domain(battle, attacker_num)
        if error:
            await callback.answer(error, show_alert=True)
            return
        await check_achievements(attacker_user_id, "territories_used", value=1)
        domain_state = battle.get("domain_state")
        if battle.get("battlerdan_pending"):
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return
        if prev_owner is None and domain_state and domain_state.get("owner") == attacker_num:
            battle["pending_domain_response"] = {"target": defender_num, "owner": attacker_num}
        await _advance_turn(callback, battle, attacker_num)
        await callback.answer()
        return

    if action == "simple":
        ok, error = _action_simple_domain(battle, attacker_num)
        if error:
            await callback.answer(error, show_alert=True)
            return
        await _advance_turn(callback, battle, attacker_num)
        await callback.answer()
        return

    if action == "end_turn":
        await _advance_turn(callback, battle, attacker_num)
        await callback.answer()
        return

    await callback.answer("Неизвестное действие.", show_alert=True)


@router.message(Command("pvp"))
async def cmd_pvp(message: Message):
    _remove_from_matchmaking_queue(message.from_user.id)
    pvp_challenge_target_input.pop(message.from_user.id, None)
    await message.answer(
        "⚔️ <b>PvP Арена</b>\n\nВыбери действие:",
        reply_markup=get_pvp_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "pvp_menu")
async def pvp_menu_callback(callback: CallbackQuery):
    _remove_from_matchmaking_queue(callback.from_user.id)
    pvp_challenge_target_input.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "⚔️ <b>PvP Арена</b>\n\n"
        "Сражайся с другими игроками, используй техники карт и побеждай.\n\n"
        "🏆 Победы дают опыт.",
        reply_markup=get_pvp_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "pvp_find")
async def pvp_find_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        if _has_active_any_battle(user.telegram_id):
            await callback.answer("Ты уже участвуешь в PvP бою.", show_alert=True)
            return

        cooldown_left = _get_pvp_cooldown_seconds_left(user)
        if cooldown_left > 0:
            await callback.answer(
                f"Подожди {cooldown_left} сек. перед следующим PvP боем.",
                show_alert=True,
            )
            return

        if not user.slot_1_card_id:
            await callback.answer("У тебя не экипирована главная карта.", show_alert=True)
            return

        _cleanup_matchmaking_queue()

        opponent = None
        for opponent_tg in _matchmaking_candidate_tgs(user):
            if _has_active_any_battle(opponent_tg):
                _remove_from_matchmaking_queue(opponent_tg)
                continue

            result = await session.execute(select(User).where(User.telegram_id == opponent_tg))
            candidate = result.scalar_one_or_none()
            if not candidate or not candidate.slot_1_card_id:
                _remove_from_matchmaking_queue(opponent_tg)
                continue

            if _get_pvp_cooldown_seconds_left(candidate) > 0:
                _remove_from_matchmaking_queue(opponent_tg)
                continue

            opponent = candidate
            break

        if opponent:
            _remove_from_matchmaking_queue(user.telegram_id, opponent.telegram_id)
            started = await start_pvp_battle(callback, user, opponent)
            if started:
                await callback.answer("Соперник найден! Бой начался.")
            else:
                await callback.answer("Не удалось запустить бой. Попробуй поиск ещё раз.", show_alert=True)
            return

        existing = pvp_matchmaking_queue.get(user.telegram_id, {})
        joined_at = existing.get("joined_at", datetime.utcnow())
        pvp_matchmaking_queue[user.telegram_id] = {
            "joined_at": joined_at,
            "user_id": user.id,
            "level": user.level,
        }

        wait_seconds = int((datetime.utcnow() - joined_at).total_seconds())
        opponents_waiting = max(0, len(pvp_matchmaking_queue) - 1)

        waiting_text = (
            "🔎 <b>Поиск PvP соперника</b>\n\n"
            "Матчмейкинг ищет игрока, который тоже прямо сейчас нажал поиск.\n\n"
            f"👥 В очереди сейчас: {opponents_waiting}\n"
            f"⏱ Время ожидания: {wait_seconds} сек.\n\n"
            "Бой начнётся автоматически, как только найдётся второй реальный игрок."
        )
        try:
            await callback.message.edit_text(
                waiting_text,
                reply_markup=get_pvp_waiting_keyboard(),
                parse_mode="HTML",
            )
        except Exception:
            await callback.bot.send_message(
                callback.from_user.id,
                waiting_text,
                reply_markup=get_pvp_waiting_keyboard(),
                parse_mode="HTML",
            )
        await callback.answer("Ты добавлен в очередь поиска.")


@router.callback_query(F.data == "pvp_cancel_search")
async def pvp_cancel_search_callback(callback: CallbackQuery):
    removed = callback.from_user.id in pvp_matchmaking_queue
    _remove_from_matchmaking_queue(callback.from_user.id)

    cancel_text = (
        "⚔️ <b>PvP Арена</b>\n\n"
        "Поиск соперника отменён.\n\n"
        "Нажми «Найти соперника», чтобы снова встать в очередь."
    )
    try:
        await callback.message.edit_text(
            cancel_text,
            reply_markup=get_pvp_menu(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.bot.send_message(
            callback.from_user.id,
            cancel_text,
            reply_markup=get_pvp_menu(),
            parse_mode="HTML",
        )
    await callback.answer("Поиск отменён." if removed else "Ты не находился в поиске.")


async def _load_card(session, card_id: int):
    if not card_id:
        return None
    result = await session.execute(
        select(UserCard)
        .options(selectinload(UserCard.card_template))
        .where(UserCard.id == card_id)
    )
    card = result.scalar_one_or_none()
    if card and card.card_template:
        card.recalculate_stats()
    return card


def _build_fighter_state(
    main_card: UserCard,
    weapon_card: UserCard | None,
    shikigami_card: UserCard | None,
    pact_cards: list[UserCard | None],
    toolkit: dict,
    clan_bonuses: dict | None = None,
    technique_names: set[str] | None = None,
):
    technique_names = technique_names or set()
    main_name = main_card.card_template.name if main_card.card_template else ""
    is_itadori = _name_has_tokens(main_name, ITADORI_TOKENS)
    is_megumi = _name_has_tokens(main_name, MEGUMI_TOKENS)
    is_toji = _name_has_tokens(main_name, TOJI_TOKENS)
    is_hakari = _name_has_tokens(main_name, HAKARI_TOKENS)
    is_gojo = _is_gojo_name(main_name)
    is_battlerdan = _name_has_tokens(main_name, BATTLERDAN_TOKENS)

    profile = _get_character_profile(main_name)
    specials = [deepcopy(sp) for sp in profile.get("specials", [])]

    def _extend_specials(items: list[dict]):
        existing = {sp.get("key") for sp in specials}
        for sp in items:
            if sp.get("key") in existing:
                continue
            specials.append(sp)
            existing.add(sp.get("key"))

    if is_itadori and TECH_BLOOD in technique_names:
        _extend_specials([
            {"key": "blood_spear", "name": "Копьё крови", "icon": "🩸", "ce_cost": 1100, "multiplier": 1.6, "flat": 220},
        ])
    if is_itadori and TECH_SUKUNA_CURSE in technique_names:
        _extend_specials([
            {"key": "yuji_cleave", "name": "Рассечение", "icon": "🗡", "ce_cost": 800, "multiplier": 1.35, "flat": 150},
            {"key": "yuji_dismantle", "name": "Расщепление", "icon": "⚔️", "ce_cost": 1100, "multiplier": 1.55, "flat": 220},
        ])

    weapon2 = None
    if is_toji and shikigami_card and shikigami_card.card_template and is_weapon_template(shikigami_card.card_template):
        weapon2 = shikigami_card
        shikigami_card = None

    max_ce = max(BATTLE_CE_MIN, main_card.max_ce * BATTLE_CE_SCALE)
    ce_regen = max(BATTLE_CE_REGEN_MIN, main_card.get_ce_regen() * BATTLE_CE_REGEN_SCALE)

    if is_toji:
        max_ce = 0
        ce_regen = 0

    domain_level = getattr(main_card, "domain_level", 0) or 0
    rct_level = getattr(main_card, "rct_level", 0) or 0
    domain_dot_pct = profile["domain_dot_pct"] + domain_level * DOMAIN_DOT_PER_POINT
    domain_damage_bonus = profile["domain_damage_bonus"] + domain_level * DOMAIN_DAMAGE_BONUS_PER_POINT

    has_mahoraga = False
    mahoraga_requires_shikigami = False
    if shikigami_card and shikigami_card.card_template:
        has_mahoraga = _normalize_name(shikigami_card.card_template.name) == "махорага"
        mahoraga_requires_shikigami = has_mahoraga
    if is_megumi:
        has_mahoraga = True

    mahoraga_cost = MAHORAGA_ADAPT_COST
    if is_megumi:
        mahoraga_cost = int(MAHORAGA_ADAPT_COST * 0.6)

    attack_multiplier = 1.0
    clan_bonuses = clan_bonuses or {}
    if clan_bonuses.get("attack_mult"):
        attack_multiplier *= float(clan_bonuses["attack_mult"])
    if clan_bonuses.get("ce_regen_mult"):
        ce_regen = int(ce_regen * float(clan_bonuses["ce_regen_mult"]))

    has_domain = toolkit.get("has_domain", False)
    has_simple_domain = toolkit.get("has_simple_domain", False)
    has_reverse_ct = toolkit.get("has_reverse_ct", False)
    if is_toji:
        has_domain = False
        has_simple_domain = False
        has_reverse_ct = False

    state = {
        "main": main_card,
        "weapon": weapon_card,
        "weapon2": weapon2,
        "shikigami": shikigami_card,
        "pacts": [] if is_toji else [p for p in (pact_cards or []) if p],
        "specials": specials,
        "domain_name": profile["domain_name"],
        "domain_effect": profile.get("domain_effect", "dot"),
        "domain_dot_pct": domain_dot_pct,
        "domain_damage_bonus": domain_damage_bonus,
        "domain_slow_pct": profile.get("domain_slow_pct", 0.0),
        "ce": max_ce,
        "max_ce": max_ce,
        "ce_regen": ce_regen,
        "has_domain": has_domain,
        "has_simple_domain": has_simple_domain,
        "has_reverse_ct": has_reverse_ct,
        "domain_cost": BATTLE_DOMAIN_COST,
        "simple_domain_cost": 0,
        "rct_cost": BATTLE_RCT_COST,
        "simple_domain_turns": 0,
        "black_flash_chance": get_black_flash_chance(main_name),
        "domain_level": domain_level,
        "rct_level": rct_level,
        "next_attack_multiplier": 1.0,
        "next_attack_ready": False,
        "pact_used": set(),
        "has_mahoraga": has_mahoraga,
        "mahoraga_requires_shikigami": mahoraga_requires_shikigami,
        "mahoraga_ready": False,
        "mahoraga_adapt": {},
        "mahoraga_domain_adapt": {},
        "mahoraga_cost": mahoraga_cost,
        "higuruma_sword_ready": False,
        "ce_lock_turns": 0,
        "attack_multiplier": attack_multiplier,
        "post_battle_exp_multiplier": 1.0,
        "single_use_pacts_to_consume": set(),
        "survive_lethal_available": False,
        "pacts_disabled": is_toji,
        "ignore_domain_effects": is_toji,
        "is_battlerdan": is_battlerdan,
        "infinity_chance": 1.0 if is_gojo and TECH_INFINITY in technique_names else 0.0,
        "has_domain_amplification": (
            toolkit.get("has_domain_amplification", False)
            or TECH_DOMAIN_AMPLIFICATION in technique_names
        ),
        "hakari_jackpot_turns": 0,
        "hakari_jackpot_chance": 0.33,
        "is_toji": is_toji,
        "is_hakari": is_hakari,
    }

    if is_gojo and TECH_SIX_EYES in technique_names:
        discount = 0.5
        state["domain_cost"] = int(state["domain_cost"] * discount)
        state["simple_domain_cost"] = int(state["simple_domain_cost"] * discount)
        state["rct_cost"] = int(state["rct_cost"] * discount)
        state["mahoraga_cost"] = int(state["mahoraga_cost"] * discount)
        for sp in state["specials"]:
            sp["ce_cost"] = int(sp.get("ce_cost", 0) * discount)
            for variant in (sp.get("variants") or {}).values():
                variant["ce_cost"] = int(variant.get("ce_cost", 0) * discount)

    return state


async def start_pvp_battle(callback: CallbackQuery, player1: User, player2: User, is_rematch: bool = False) -> bool:
    async with async_session() as session:
        _remove_from_matchmaking_queue(player1.telegram_id, player2.telegram_id)

        p1_main = await _load_card(session, player1.slot_1_card_id)
        p1_weapon = await _load_card(session, player1.slot_2_card_id)
        p1_shikigami = await _load_card(session, player1.slot_3_card_id)
        p1_pact1 = await _load_card(session, player1.slot_4_card_id)
        p1_pact2 = await _load_card(session, player1.slot_5_card_id)
        p2_main = await _load_card(session, player2.slot_1_card_id)
        p2_weapon = await _load_card(session, player2.slot_2_card_id)
        p2_shikigami = await _load_card(session, player2.slot_3_card_id)
        p2_pact1 = await _load_card(session, player2.slot_4_card_id)
        p2_pact2 = await _load_card(session, player2.slot_5_card_id)

        if not p1_main or not p2_main:
            await callback.answer("У одного из игроков не экипирована главная карта.", show_alert=True)
            return False

        p1_main.heal()
        p2_main.heal()
        if p1_weapon:
            p1_weapon.heal()
        if p1_shikigami:
            p1_shikigami.heal()
        if p1_pact1:
            p1_pact1.heal()
        if p1_pact2:
            p1_pact2.heal()
        if p2_weapon:
            p2_weapon.heal()
        if p2_shikigami:
            p2_shikigami.heal()
        if p2_pact1:
            p2_pact1.heal()
        if p2_pact2:
            p2_pact2.heal()

        p1_toolkit = await get_player_pvp_toolkit(session, player1.id)
        p2_toolkit = await get_player_pvp_toolkit(session, player2.id)
        p1_techniques = await _get_user_technique_names(session, player1.id)
        p2_techniques = await _get_user_technique_names(session, player2.id)
        p1_title = None
        p2_title = None
        if player1.equipped_title_id:
            p1_title = await session.scalar(select(Title).where(Title.id == player1.equipped_title_id))
        if player2.equipped_title_id:
            p2_title = await session.scalar(select(Title).where(Title.id == player2.equipped_title_id))

        p1_clan_bonuses = await get_clan_bonuses(session, player1.clan)
        p2_clan_bonuses = await get_clan_bonuses(session, player2.clan)

        fighters = {
            1: _build_fighter_state(
                p1_main,
                p1_weapon,
                p1_shikigami,
                [p1_pact1, p1_pact2],
                p1_toolkit,
                clan_bonuses=p1_clan_bonuses,
                technique_names=p1_techniques,
            ),
            2: _build_fighter_state(
                p2_main,
                p2_weapon,
                p2_shikigami,
                [p2_pact1, p2_pact2],
                p2_toolkit,
                clan_bonuses=p2_clan_bonuses,
                technique_names=p2_techniques,
            ),
        }

        battle_id = f"pvp_{player1.id}_{player2.id}_{datetime.utcnow().timestamp()}"
        current_player = 1
        if _team_speed(fighters[2]) > _team_speed(fighters[1]):
            current_player = 2
        first_turn_card = fighters[current_player]["main"].card_template.name

        battle = {
            "battle_id": battle_id,
            "player1_id": player1.id,
            "player1_tg": player1.telegram_id,
            "player2_id": player2.id,
            "player2_tg": player2.telegram_id,
            "fighters": fighters,
            "turn": 1,
            "current_player": current_player,
            "domain_state": None,
            "pending_domain_response": None,
            "battlerdan_pending": None,
            "pending_special_variant": {},
            "pending_target": {},
            "turn_flags": {
                1: _default_turn_flags(),
                2: _default_turn_flags(),
            },
            "log": [
                f"⚡ Первый ход за картой {first_turn_card} (преимущество скорости)."
            ],
            "messages": {},
        }

        battle["fighters"][1]["title"] = p1_title
        battle["fighters"][2]["title"] = p2_title
        active_pvp_battles[player1.telegram_id] = battle
        active_pvp_battles[player2.telegram_id] = battle

        await _update_battle_messages(callback, battle)
        return True


@router.callback_query(F.data.startswith("pvp_action_"))
async def pvp_action_callback(callback: CallbackQuery):
    action = callback.data.split("pvp_action_", 1)[1]
    await _process_action(callback, action)


# Legacy callbacks from old keyboards
@router.callback_query(F.data == "pvp_attack")
async def legacy_pvp_attack_callback(callback: CallbackQuery):
    await _process_action(callback, "basic")


@router.callback_query(F.data == "pvp_special")
async def legacy_pvp_special_callback(callback: CallbackQuery):
    await callback.answer("Теперь спецтехники выбираются отдельными кнопками в PvP.", show_alert=True)


@router.callback_query(F.data == "pvp_defend")
async def legacy_pvp_defend_callback(callback: CallbackQuery):
    await callback.answer("Защита удалена из PvP. спользуй Простую территорию или ОПТ.", show_alert=True)


async def end_pvp_battle(callback: CallbackQuery, battle: dict, winner_is_player1: bool):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == battle["player1_id"]))
        player1 = result.scalar_one()
        result = await session.execute(select(User).where(User.id == battle["player2_id"]))
        player2 = result.scalar_one()

        winner = player1 if winner_is_player1 else player2
        loser = player2 if winner_is_player1 else player1
        winner_num = 1 if winner_is_player1 else 2
        loser_num = 2 if winner_is_player1 else 1
        winner_state = battle["fighters"][winner_num]
        loser_state = battle["fighters"][loser_num]

        winner.pvp_wins += 1
        winner.total_battles += 1
        winner.last_battle_time = datetime.utcnow()
        await add_daily_quest_progress(session, winner.id, "pvp_wins", amount=1)
        await add_daily_quest_progress(session, winner.id, "pvp_battles", amount=1)

        loser.pvp_losses += 1
        loser.total_battles += 1
        loser.last_battle_time = datetime.utcnow()
        await add_daily_quest_progress(session, loser.id, "pvp_battles", amount=1)

        exp_gained = 50
        points_gained = 0

        level_diff = loser.level - winner.level
        if level_diff > 0:
            exp_gained += level_diff * 10

        winner_exp_mult = max(1.0, float(winner_state.get("post_battle_exp_multiplier", 1.0) or 1.0))
        exp_gained = int(exp_gained * winner_exp_mult)

        leveled_up, actual_exp, unlocked_from_level = await apply_experience_with_pvp_rolls(
            session, winner, exp_gained
        )

        winner_consumed_pacts = await _consume_single_use_pacts(session, winner, winner_state)
        loser_consumed_pacts = await _consume_single_use_pacts(session, loser, loser_state)

        if winner.clan:
            await add_clan_exp(session, winner.clan, CLAN_EXP_PER_PVP_WIN)
            await add_clan_daily_progress(session, winner.clan, pvp_win=1, battle=1)
        if loser.clan:
            await add_clan_exp(session, loser.clan, CLAN_EXP_PER_PVP_LOSS)
            await add_clan_daily_progress(session, loser.clan, battle=1)

        battle_record = Battle(
            battle_type="pvp",
            player1_id=player1.id,
            player2_id=player2.id,
            winner_id=winner.id,
            battle_log="\\n".join(battle["log"]),
            exp_gained=actual_exp,
            points_gained=points_gained,
        )
        session.add(battle_record)
        await session.flush()

        await check_achievements(winner.id, "pvp_wins", value=1, session=session)

        result = await session.execute(
            select(Battle)
            .where(
                Battle.battle_type.in_(["pvp", "pvp_coop"]),
                (Battle.player1_id == winner.id) | (Battle.player2_id == winner.id),
            )
            .order_by(Battle.created_at.desc())
            .limit(20)
        )
        streak = 0
        for record in result.scalars().all():
            if record.winner_id == winner.id:
                streak += 1
            else:
                break
        await check_achievements(winner.id, "pvp_streak", value=streak, absolute=True, session=session)

        await check_achievements(winner.id, "level", value=winner.level, absolute=True, session=session)
        if winner.hardcore_mode:
            await check_achievements(winner.id, "hardcore_level", value=winner.level, absolute=True, session=session)

        result = await session.execute(
            select(func.count(UserTechnique.id)).where(UserTechnique.user_id == winner.id)
        )
        technique_count = int(result.scalar() or 0)
        await check_achievements(
            winner.id,
            "techniques_obtained",
            value=technique_count,
            absolute=True,
            session=session,
        )

        result = await session.execute(
            select(func.count(UserCard.id)).where(UserCard.user_id == winner.id)
        )
        card_count = int(result.scalar() or 0)
        await check_achievements(
            winner.id,
            "cards_collected",
            value=card_count,
            absolute=True,
            session=session,
        )

        await session.commit()

        winner_text = (
            f"🏆 <b>Победа!</b>\n\n"
            f"😵 Побежден {loser.first_name or 'противник'}!\n\n"
            f"⭐ Опыт: +{actual_exp}\n"
        )
        if winner_exp_mult > 1.0:
            winner_text += f"📜 <b>Пакт опыта:</b> x{winner_exp_mult:.1f}\n"
        if leveled_up:
            winner_text += f"🎉 <b>Новый уровень! Теперь ты {winner.level} уровень!</b>\n"
        if unlocked_from_level:
            unlocked_names = ", ".join(t.name for t in unlocked_from_level)
            winner_text += f"🆕 <b>Новые PvP-техники:</b> {unlocked_names}\n"
        if winner_consumed_pacts:
            winner_text += f"🕯 <b>Израсходованы пакты:</b> {', '.join(winner_consumed_pacts)}\n"

        loser_text = (
            "💀 <b>Поражение...</b>\n\n"
            f"{winner.first_name or 'Противник'} одержал победу.\n\n"
            "Попробуй снова и станешь сильнее."
        )
        if loser_consumed_pacts:
            loser_text += f"\n\n🕯 Израсходованы пакты: {', '.join(loser_consumed_pacts)}"

        try:
            await callback.bot.send_message(
                winner.telegram_id,
                winner_text,
                reply_markup=get_pvp_result_keyboard(True),
                parse_mode="HTML",
            )
        except Exception:
            pass

        try:
            await callback.bot.send_message(
                loser.telegram_id,
                loser_text,
                reply_markup=get_pvp_result_keyboard(False),
                parse_mode="HTML",
            )
        except Exception:
            pass

    for uid, existing in list(active_pvp_battles.items()):
        if existing["battle_id"] == battle["battle_id"]:
            del active_pvp_battles[uid]


@router.callback_query(F.data == "pvp_history")
async def pvp_history_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(Battle)
            .options(
                selectinload(Battle.player1),
                selectinload(Battle.player2),
            )
            .where(
                Battle.battle_type == "pvp",
                (Battle.player1_id == user.id) | (Battle.player2_id == user.id),
            )
            .order_by(Battle.created_at.desc())
            .limit(10)
        )
        battles = result.scalars().all()

        if not battles:
            await callback.message.edit_text(
                "📜 <b>стория PvP</b>\n\nУ тебя пока нет PvP-боёв.",
                reply_markup=get_pvp_menu(),
                parse_mode="HTML",
            )
            return

        history_text = "📜 <b>Последние PvP бои:</b>\n\n"
        for i, item in enumerate(battles, 1):
            opponent_name = item.get_opponent_name(user.id)
            is_winner = item.winner_id == user.id
            result_emoji = "🏆" if is_winner else "💀"
            history_text += f"{i}. {result_emoji} vs {opponent_name}\n"

        from keyboards.main_menu import get_back_button

        await callback.message.edit_text(
            history_text,
            reply_markup=get_back_button("pvp_menu"),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "pvp_challenge")
async def pvp_challenge_callback(callback: CallbackQuery):
    _cleanup_challenge_input()
    pvp_challenge_target_input[callback.from_user.id] = datetime.utcnow()
    await callback.message.edit_text(
        "🎯 <b>Вызов игрока</b>\n\n"
        "Отправь следующим сообщением <b>@username</b> или <b>telegram_id</b> игрока,\n"
        "которому хочешь кинуть вызов.\n\n"
        "Пример:\n"
        "<code>@player_name</code>\n"
        "<code>123456789</code>\n\n"
        "Также можно использовать команду:\n"
        "<code>/challenge @username</code>",
        reply_markup=get_pvp_challenge_input_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "pvp_cancel_challenge_input")
async def pvp_cancel_challenge_input_callback(callback: CallbackQuery):
    pvp_challenge_target_input.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "⚔️ <b>PvP Арена</b>\n\n"
        "Ввод цели для вызова отменён.",
        reply_markup=get_pvp_menu(),
        parse_mode="HTML",
    )
    await callback.answer("Отменено.")


@router.message(Command("challenge"))
async def challenge_command(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer(
            "спользование:\n"
            "<code>/challenge @username</code>\n"
            "<code>/challenge telegram_id</code>",
            parse_mode="HTML",
        )
        return

    pvp_challenge_target_input.pop(message.from_user.id, None)
    await _process_direct_challenge_request(message, args[1].strip())


@router.message(F.text, ~F.text.startswith("/"), lambda message: message.from_user.id in pvp_challenge_target_input)
async def pvp_challenge_target_input_handler(message: Message):
    _cleanup_challenge_input()

    created_at = pvp_challenge_target_input.get(message.from_user.id)
    if not created_at:
        return

    if message.text.strip().startswith("/"):
        pvp_challenge_target_input.pop(message.from_user.id, None)
        return

    pvp_challenge_target_input.pop(message.from_user.id, None)
    await _process_direct_challenge_request(message, message.text.strip())


@router.callback_query(F.data == "pvp_rematch")
async def pvp_rematch_callback(callback: CallbackQuery):
    await pvp_find_callback(callback)


@router.callback_query(F.data.startswith("pvp_accept_"))
async def pvp_accept_callback(callback: CallbackQuery):
    challenger_tg = int(callback.data.split("_")[2])
    accepter_tg = callback.from_user.id
    key = (challenger_tg, accepter_tg)

    created_at = pvp_challenges.get(key)
    if not created_at:
        await callback.answer("Вызов не найден или уже неактуален.", show_alert=True)
        return

    if datetime.utcnow() - created_at > timedelta(minutes=10):
        pvp_challenges.pop(key, None)
        await callback.answer("Вызов истёк. Отправьте новый.", show_alert=True)
        return

    if _has_active_any_battle(challenger_tg) or _has_active_any_battle(accepter_tg):
        pvp_challenges.pop(key, None)
        await callback.answer("Один из игроков уже находится в бою.", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == challenger_tg))
        challenger = result.scalar_one_or_none()
        result = await session.execute(select(User).where(User.telegram_id == accepter_tg))
        accepter = result.scalar_one_or_none()

        if not challenger or not accepter:
            pvp_challenges.pop(key, None)
            await callback.answer("Один из игроков не найден.", show_alert=True)
            return

        if not challenger.slot_1_card_id or not accepter.slot_1_card_id:
            pvp_challenges.pop(key, None)
            await callback.answer("У одного из игроков не экипирована главная карта.", show_alert=True)
            return

        pvp_challenges.pop(key, None)
        started = await start_pvp_battle(callback, challenger, accepter)
        if started:
            await callback.answer("Вызов принят, бой начался!")
        else:
            await callback.answer("Не удалось начать бой. Попробуйте снова.", show_alert=True)


@router.callback_query(F.data.startswith("pvp_decline_"))
async def pvp_decline_callback(callback: CallbackQuery):
    challenger_tg = int(callback.data.split("_")[2])
    accepter_tg = callback.from_user.id
    key = (challenger_tg, accepter_tg)
    existed = pvp_challenges.pop(key, None)

    if existed:
        try:
            await callback.bot.send_message(challenger_tg, "❌ Твой PvP-вызов был отклонён.")
        except Exception:
            pass

    await callback.answer("Вызов отклонён.", show_alert=True)
