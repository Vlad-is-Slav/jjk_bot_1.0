
import random
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from models import async_session, User, UserCard, Curse, Battle, Technique, UserTechnique
from keyboards.pve import (
    get_pve_menu,
    get_pve_battle_keyboard,
    get_pve_result_keyboard,
    get_pve_start_keyboard,
    get_pve_active_keyboard,
)
from utils.curse_data import CURSES
from utils.daily_quest_progress import add_daily_quest_progress
from utils.pvp_progression import apply_experience_with_pvp_rolls, get_player_pvp_toolkit
from utils.weapon_effects import get_weapon_effect
from utils.pact_effects import get_pact_effect
from utils.black_flash import get_black_flash_chance
from utils.card_rewards import is_weapon_template
from handlers.achievements import check_achievements
from utils.clan_progression import (
    CLAN_EXP_PER_PVE_WIN,
    add_clan_daily_progress,
    add_clan_exp,
    get_clan_bonuses,
)
from config import (
    PVE_COOLDOWN,
    DOMAIN_DOT_PER_POINT,
    DOMAIN_DAMAGE_BONUS_PER_POINT,
    RCT_HEAL_BONUS_PER_POINT,
)

router = Router()

# Активные PvE бои
active_pve_battles: dict[int, dict] = {}
last_pve_difficulty: dict[int, str] = {}
last_pve_strategy: dict[int, str] = {}

DEFAULT_DOMAIN_DURATION = 3
DEFAULT_SIMPLE_DOMAIN_DURATION = 2
MAHORAGA_ADAPT_COST = 2000
DOMAIN_UPKEEP_PER_TURN = 500
AUTO_BATTLE_TURN_CAP = 200
PVE_ENEMY_BASIC_MAX_HIT_PCT = 0.45
PVE_ENEMY_SPECIAL_MAX_HIT_PCT = 0.62
PVE_ENEMY_DOMAIN_MAX_HIT_PCT = 0.38

PVE_DIFFICULTY_CONFIG = {
    "easy": {
        "label": "Легкая",
        "stat_range": (0.80, 0.92),
        "spike_chance": 0.20,
        "spike_range": (0.98, 1.06),
        "reward_mult": 0.75,
        "drop_mult": 0.8,
        "run_stat_step": 0.025,
        "run_reward_step": 0.08,
        "run_drop_step": 0.05,
        "ce_mult": 0.88,
        "special_count": (0, 1),
        "domain_chance": 0.25,
        "toolkit": {"has_domain": False, "has_simple_domain": False, "has_reverse_ct": False},
        "enemy_bias": {"special": -0.18, "domain": -0.20, "heal": -0.08},
    },
    "medium": {
        "label": "Средняя",
        "stat_range": (0.95, 1.05),
        "spike_chance": 0.12,
        "spike_range": (1.05, 1.15),
        "reward_mult": 1.0,
        "drop_mult": 1.0,
        "run_stat_step": 0.05,
        "run_reward_step": 0.10,
        "run_drop_step": 0.06,
        "ce_mult": 1.0,
        "special_count": (1, 2),
        "domain_chance": 0.5,
        "toolkit": {"has_domain": True, "has_simple_domain": True, "has_reverse_ct": True},
        "enemy_bias": {"special": 0.0, "domain": 0.0, "heal": 0.0},
    },
    "hard": {
        "label": "Сложная",
        "stat_range": (1.12, 1.28),
        "spike_chance": 0.25,
        "spike_range": (1.28, 1.45),
        "reward_mult": 1.35,
        "drop_mult": 1.25,
        "run_stat_step": 0.08,
        "run_reward_step": 0.15,
        "run_drop_step": 0.08,
        "ce_mult": 1.12,
        "special_count": (2, 3),
        "domain_chance": 0.7,
        "toolkit": {"has_domain": True, "has_simple_domain": True, "has_reverse_ct": True},
        "enemy_bias": {"special": 0.16, "domain": 0.18, "heal": 0.10},
    },
}

PVE_DIFFICULTY_ALIASES = {
    "normal": "medium",
    "hardcore": "hard",
    "disaster": "hard",
}

USER_TO_PVE_DIFFICULTY = {
    "easy": "easy",
    "normal": "medium",
    "medium": "medium",
    "hard": "hard",
    "hardcore": "hard",
}

PVE_DEFAULT_STRATEGY = "balanced"
PVE_STRATEGIES = {
    "balanced": {
        "label": "Баланс",
        "attack_mult": 1.0,
        "defense_mult": 1.0,
        "hp_mult": 1.0,
        "ce_mult": 1.0,
        "ce_regen_mult": 1.0,
        "special_bias": 0.0,
        "domain_bias": 0.0,
        "heal_bias": 0.0,
    },
    "aggressive": {
        "label": "Атака",
        "attack_mult": 1.12,
        "defense_mult": 0.92,
        "hp_mult": 0.96,
        "ce_mult": 1.0,
        "ce_regen_mult": 0.95,
        "special_bias": 0.12,
        "domain_bias": 0.10,
        "heal_bias": -0.10,
    },
    "defensive": {
        "label": "Защита",
        "attack_mult": 0.93,
        "defense_mult": 1.12,
        "hp_mult": 1.08,
        "ce_mult": 1.0,
        "ce_regen_mult": 1.08,
        "special_bias": -0.10,
        "domain_bias": -0.08,
        "heal_bias": 0.12,
    },
}

AUTO_POWER_WIN_THRESHOLD = 1.15

ENEMY_SPECIAL_POOL = [
    {"key": "claw", "name": "Когти", "icon": "🦴", "ce_cost": 700, "multiplier": 1.3, "flat": 120},
    {"key": "burst", "name": "Проклятый залп", "icon": "💢", "ce_cost": 900, "multiplier": 1.5, "flat": 170},
    {"key": "slam", "name": "Сокрушение", "icon": "🪨", "ce_cost": 1200, "multiplier": 1.75, "flat": 240},
]

CHARACTER_PROFILES = [
    {
        "tokens": ["годжосатору", "satorugojo", "gojosatoru"],
        "domain_name": "Безграничная Пустота",
        "domain_dot_pct": 0.15,
        "domain_damage_bonus": 0.30,
        "domain_effect": "gojo_crit",
        "specials": [
            {"key": "blue", "name": "Синий", "icon": "🔵", "ce_cost": 700, "multiplier": 1.25, "flat": 120},
            {"key": "red", "name": "Красный", "icon": "🔴", "ce_cost": 1000, "multiplier": 1.55, "flat": 220},
            {"key": "purple", "name": "Фиолетовый", "icon": "🟣", "ce_cost": 5000, "multiplier": 2.6, "flat": 500},
        ],
    },
    {
        "tokens": ["сукуна", "sukuna", "ryomen"],
        "domain_name": "Храм Злобы",
        "domain_dot_pct": 0.14,
        "domain_damage_bonus": 0.28,
        "domain_effect": "sukuna_dot",
        "specials": [
            {"key": "cleave", "name": "Рассечение", "icon": "🗡", "ce_cost": 900, "multiplier": 1.45, "flat": 180},
            {"key": "dismantle", "name": "Расщепление", "icon": "⚔️", "ce_cost": 1300, "multiplier": 1.7, "flat": 260},
            {"key": "fuga", "name": "Фуга", "icon": "🔥", "ce_cost": 4500, "multiplier": 2.45, "flat": 520},
        ],
    },
    {
        "tokens": ["хигурума", "higuruma"],
        "domain_name": "Судебное Заседание",
        "domain_dot_pct": 0.14,
        "domain_damage_bonus": 0.00,
        "domain_effect": "higuruma_dot",
        "specials": [
            {"key": "gavel", "name": "Молот", "icon": "🔨", "ce_cost": 500, "multiplier": 1.45, "flat": 150},
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
            {"key": "battle_blue", "name": "Синие клинья", "icon": "🔵", "ce_cost": 700, "multiplier": 1.25, "flat": 120},
            {"key": "battle_red", "name": "Красный ключ", "icon": "🔴", "ce_cost": 1000, "multiplier": 1.55, "flat": 220},
            {"key": "battle_bombs", "name": "Маленькие бомбочки", "icon": "💣", "ce_cost": 0, "multiplier": 0.7, "flat": 40},
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
            {"key": "white", "name": "Белый", "icon": "⚪", "ce_cost": 5000, "multiplier": 2.6, "flat": 500},
        ],
    },
]

DEFAULT_PROFILE = {
    "domain_name": "Расширение территории",
    "domain_dot_pct": 0.10,
    "domain_damage_bonus": 0.20,
    "domain_effect": "dot",
    "specials": [
        {"key": "burst", "name": "Выброс CE", "icon": "💥", "ce_cost": 900, "multiplier": 1.35, "flat": 150},
    ],
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


@dataclass
class SimpleTemplate:
    name: str
    description: str = ""


class SimpleCard:
    def __init__(
        self,
        name: str,
        attack: int,
        defense: int,
        speed: int,
        hp: int,
        max_ce: int,
        ce_regen: int,
        description: str = "",
        domain_level: int = 0,
        rct_level: int = 0,
    ):
        self.card_template = SimpleTemplate(name=name, description=description)
        self.attack = attack
        self.defense = defense
        self.speed = speed
        self.max_hp = hp
        self.hp = hp
        self.max_ce = max_ce
        self._ce_regen = ce_regen
        self.domain_level = domain_level
        self.rct_level = rct_level

    def heal(self):
        self.hp = self.max_hp

    def get_ce_regen(self) -> int:
        return int(self._ce_regen)

    def take_damage(self, damage: int):
        actual_damage = max(1, int(damage - self.defense))
        self.hp = max(0, self.hp - actual_damage)
        return actual_damage

    def take_true_damage(self, damage: int):
        actual_damage = max(1, int(damage))
        self.hp = max(0, self.hp - actual_damage)
        return actual_damage

    def is_alive(self):
        return self.hp > 0


def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _get_strategy(strategy_key: str | None) -> dict:
    key = (strategy_key or "").strip().lower()
    return PVE_STRATEGIES.get(key, PVE_STRATEGIES[PVE_DEFAULT_STRATEGY])


def _strategy_label(strategy_key: str | None) -> str:
    strategy = _get_strategy(strategy_key)
    return strategy.get("label", PVE_STRATEGIES[PVE_DEFAULT_STRATEGY]["label"])


def _battle_rng(battle: dict):
    return battle.get("rng") or random


def _refresh_battle_rng(battle: dict):
    curse = battle.get("curse")
    curse_name = getattr(curse, "name", "") if curse else ""
    difficulty = _normalize_pve_difficulty(battle.get("difficulty"))
    seed = f"{battle.get('user_id')}|{difficulty}|{battle.get('stage')}|{curse_name}|{battle.get('strategy')}"
    battle["rng"] = random.Random(seed)
    battle["rng_seed"] = seed


def _strategy_bias(state: dict, key: str) -> float:
    bias = (state.get("strategy_bias") or {}).get(key, 0.0)
    try:
        return float(bias)
    except Exception:
        return 0.0


def _apply_strategy_to_state(state: dict, strategy_key: str | None):
    if not state:
        return
    strategy = _get_strategy(strategy_key)
    main = state.get("main")
    if not main:
        return

    base = state.get("base_stats")
    if not base:
        base = {
            "attack": int(getattr(main, "attack", 0) or 0),
            "defense": int(getattr(main, "defense", 0) or 0),
            "speed": int(getattr(main, "speed", 0) or 0),
            "max_hp": int(getattr(main, "max_hp", 0) or 0),
            "max_ce": int(state.get("max_ce", 0) or 0),
            "ce_regen": int(state.get("ce_regen", 0) or 0),
        }
        state["base_stats"] = base

    base_attack_mult = float(state.get("base_attack_multiplier", state.get("attack_multiplier", 1.0)))

    main.defense = max(1, int(base["defense"] * float(strategy.get("defense_mult", 1.0))))
    main.max_hp = max(1, int(base["max_hp"] * float(strategy.get("hp_mult", 1.0))))
    if getattr(main, "hp", 0) > main.max_hp:
        main.hp = main.max_hp

    state["max_ce"] = max(0, int(base["max_ce"] * float(strategy.get("ce_mult", 1.0))))
    state["ce"] = min(int(state.get("ce", state["max_ce"])), int(state["max_ce"]))
    state["ce_regen"] = max(0, int(base["ce_regen"] * float(strategy.get("ce_regen_mult", 1.0))))
    state["attack_multiplier"] = base_attack_mult * float(strategy.get("attack_mult", 1.0))
    state["strategy"] = strategy_key or PVE_DEFAULT_STRATEGY
    state["strategy_bias"] = {
        "special": float(strategy.get("special_bias", 0.0)),
        "domain": float(strategy.get("domain_bias", 0.0)),
        "heal": float(strategy.get("heal_bias", 0.0)),
    }


def _name_has_tokens(name: str, tokens: tuple[str, ...]) -> bool:
    normalized = _normalize_name(name)
    return any(token in normalized for token in tokens)


def _is_gojo_name(name: str) -> bool:
    normalized = _normalize_name(name)
    return normalized in GOJO_TOKENS


def _try_fix_mojibake(value: str | None) -> str | None:
    if not value:
        return value
    try:
        return value.encode("cp1251").decode("utf-8")
    except Exception:
        return value


def _normalize_pve_difficulty(value: str | None) -> str:
    key = (value or "").strip().lower()
    key = PVE_DIFFICULTY_ALIASES.get(key, key)
    if key not in PVE_DIFFICULTY_CONFIG:
        return "medium"
    return key


def _get_pve_config(difficulty: str | None) -> dict:
    return PVE_DIFFICULTY_CONFIG[_normalize_pve_difficulty(difficulty)]


def _resolve_user_pve_difficulty(user_difficulty: str | None) -> str:
    key = (user_difficulty or "").strip().lower()
    return _normalize_pve_difficulty(USER_TO_PVE_DIFFICULTY.get(key, key))


def _format_multiplier(value: float) -> str:
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


async def _get_user_technique_names(session, user_id: int) -> set[str]:
    result = await session.execute(
        select(Technique.name)
        .join(UserTechnique, UserTechnique.technique_id == Technique.id)
        .where(UserTechnique.user_id == user_id)
    )
    return {row[0] for row in result if row and row[0]}


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


def _get_enemy_profile(difficulty: str, seed_tag: str | None = None) -> dict:
    difficulty = _normalize_pve_difficulty(difficulty)
    cfg = _get_pve_config(difficulty)
    count_min, count_max = cfg["special_count"]
    rng = random.Random(seed_tag) if seed_tag else random
    count = rng.randint(count_min, count_max)
    specials = rng.sample(ENEMY_SPECIAL_POOL, k=min(count, len(ENEMY_SPECIAL_POOL)))
    is_hard = difficulty == "hard"

    return {
        "domain_name": "Проклятая клетка",
        "domain_dot_pct": 0.10 + (0.025 if is_hard else 0.0),
        "domain_damage_bonus": 0.18 + (0.08 if is_hard else 0.0),
        "domain_effect": "dot",
        "specials": specials,
    }


def _seeded_ratio(seed: str, low: float, high: float) -> float:
    if not seed:
        return (low + high) / 2
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return low + (high - low) * value


def _scale_stat(base: int, cfg: dict, seed: str | None = None) -> int:
    low, high = cfg["stat_range"]
    ratio = _seeded_ratio(seed or "", low, high)
    value = base * ratio
    return max(1, int(value))


def _player_baseline(main_card: UserCard, shikigami_card: UserCard | None) -> dict:
    attack = main_card.attack + (shikigami_card.attack // 2 if shikigami_card else 0)
    defense = main_card.defense + (shikigami_card.defense // 2 if shikigami_card else 0)
    speed = main_card.speed + (shikigami_card.speed if shikigami_card else 0)
    hp = main_card.max_hp + (shikigami_card.max_hp // 2 if shikigami_card else 0)
    support_ce_bonus = shikigami_card.max_ce * 30 if shikigami_card else 0
    ce = max(3000, main_card.max_ce * 100 + support_ce_bonus)
    ce_regen = max(300, main_card.get_ce_regen() * 100)

    return {
        "attack": attack,
        "defense": defense,
        "speed": speed,
        "hp": hp,
        "ce": ce,
        "ce_regen": ce_regen,
    }


def _select_curse(difficulty: str, player_level: int) -> dict:
    difficulty = _normalize_pve_difficulty(difficulty)
    if difficulty == "easy":
        available = [c for c in CURSES if c["grade"] <= 3]
    elif difficulty == "medium":
        available = [c for c in CURSES if 3 <= c["grade"] <= 6]
    else:
        available = [c for c in CURSES if c["grade"] >= 6]

    suitable = [c for c in available if c["grade"] <= player_level + 2]
    if not suitable:
        suitable = available or CURSES

    curse_data = random.choice(suitable)
    curse_data = dict(curse_data)
    curse_data["name"] = _try_fix_mojibake(curse_data.get("name")) or curse_data.get("name", "Проклятие")
    curse_data["description"] = _try_fix_mojibake(curse_data.get("description")) or ""
    return curse_data


def _build_enemy_card(
    curse_data: dict,
    baseline: dict,
    difficulty: str,
    progress_mult: float = 1.0,
    seed_tag: str | None = None,
) -> SimpleCard:
    difficulty = _normalize_pve_difficulty(difficulty)
    cfg = _get_pve_config(difficulty)

    scaled = {
        key: max(1, int(value * progress_mult))
        for key, value in baseline.items()
    }

    seed_base = seed_tag or curse_data.get("name", "")
    attack = _scale_stat(scaled["attack"], cfg, seed=f"{seed_base}|attack")
    defense = _scale_stat(scaled["defense"], cfg, seed=f"{seed_base}|defense")
    speed = _scale_stat(scaled["speed"], cfg, seed=f"{seed_base}|speed")
    hp = _scale_stat(scaled["hp"], cfg, seed=f"{seed_base}|hp")

    desired_max_ce = max(3000, int(scaled["ce"] * cfg["ce_mult"]))
    desired_regen = max(300, int(scaled["ce_regen"] * cfg["ce_mult"]))

    base_ce_stat = max(1, desired_max_ce // 100)
    base_regen_stat = max(1, desired_regen // 100)

    return SimpleCard(
        name=curse_data["name"],
        description=curse_data.get("description", ""),
        attack=attack,
        defense=defense,
        speed=speed,
        hp=hp,
        max_ce=base_ce_stat,
        ce_regen=base_regen_stat,
    )


def _stage_multiplier(stage: int, step: float) -> float:
    step = max(0.0, float(step))
    return 1.0 + max(0, int(stage) - 1) * step


def _enemy_progress_multiplier(cfg: dict, stage: int) -> float:
    return _stage_multiplier(stage, cfg.get("run_stat_step", 0.0))


def _reward_multiplier(cfg: dict, stage: int) -> float:
    return _stage_multiplier(stage, cfg.get("run_reward_step", 0.0))


def _drop_multiplier(cfg: dict, stage: int) -> float:
    return _stage_multiplier(stage, cfg.get("run_drop_step", 0.0))

def _pending_response_for(battle: dict, player_num: int) -> dict | None:
    pending = battle.get("pending_domain_response")
    if pending and pending.get("target") == player_num:
        return pending
    return None


def _pending_battlerdan_for(battle: dict, player_num: int) -> dict | None:
    pending = battle.get("battlerdan_pending")
    if not pending:
        return None
    if pending.get("stage") == "choose" and pending.get("owner") == player_num:
        return pending
    if pending.get("stage") == "guess" and pending.get("target") == player_num:
        return pending
    return None


def _resolve_battlerdan_guess(battle: dict, pending: dict, guessed: int):
    owner_num = pending.get("owner")
    target_num = pending.get("target")
    choice = pending.get("choice")
    owner_state = battle["fighters"][owner_num]
    owner_name = owner_state["main"].card_template.name
    target_name = battle["fighters"][target_num]["main"].card_template.name

    if guessed == choice:
        owner_state["ce"] = 0
        owner_state["ce_lock_turns"] = 3
        battle["log"].append(
            f"⚖️ Дебаты: {target_name} угадал ответ. Проклятая энергия {owner_name} запечатана на 3 хода."
        )
    else:
        owner_state["higuruma_sword_ready"] = True
        battle["log"].append(
            f"⚖️ Дебаты: {target_name} ошибся. {owner_name} получает Золотой меч."
        )


def _get_turn_flags(battle: dict, player_num: int) -> dict:
    turn_flags = battle.setdefault("turn_flags", {})
    if player_num not in turn_flags:
        turn_flags[player_num] = {"attack_used": False, "rct_used": False, "mahoraga_used": False}
    return turn_flags[player_num]


def _reset_turn_flags(battle: dict, player_num: int):
    battle.setdefault("turn_flags", {})[player_num] = {"attack_used": False, "rct_used": False, "mahoraga_used": False}


def _get_action_state(battle: dict, player_num: int) -> dict:
    fighter_state = battle["fighters"][player_num]
    pending_battlerdan = _pending_battlerdan_for(battle, player_num)
    if pending_battlerdan:
        return {
            "force_response": True,
            "battlerdan_stage": pending_battlerdan.get("stage"),
            "battlerdan_options": pending_battlerdan.get("options", [1, 2, 3]),
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

    can_attack = not flags.get("attack_used", False)
    can_special = can_attack and not simple_active

    can_simple = fighter_state.get("has_simple_domain", False) and not simple_active
    can_mahoraga = _can_use_mahoraga(battle, player_num, flags)
    can_sword = fighter_state.get("higuruma_sword_ready", False) and not flags.get("attack_used", False)

    return {
        "force_response": False,
        "can_attack": can_attack,
        "can_special": can_special,
        "can_domain": fighter_state.get("has_domain", False),
        "can_simple": can_simple,
        "can_rct": fighter_state.get("has_reverse_ct", False) and not flags.get("rct_used", False),
        "can_mahoraga": can_mahoraga,
        "can_sword": can_sword,
        "show_end_turn": True,
    }


def _get_fighter_speed(state: dict) -> int:
    main = state["main"]
    shikigami = state.get("shikigami")
    return int(main.speed + (shikigami.speed if shikigami else 0))


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
) -> float:
    attacker_speed = max(1, _get_fighter_speed(attacker_state))
    defender_speed = _get_fighter_speed(defender_state)
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
    if not state.get("has_mahoraga", False):
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
    damage = state["main"].attack
    shikigami = state.get("shikigami")
    if shikigami:
        shikigami_mult = float(state.get("shikigami_damage_mult", 0.5))
        damage += int(shikigami.attack * shikigami_mult)
    damage = int(damage * state.get("attack_multiplier", 1.0))
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
    if not defender_state.get("has_mahoraga") or not defender_state.get("mahoraga_ready"):
        return

    adapt_map = defender_state.setdefault("mahoraga_adapt", {})
    current = float(adapt_map.get(attack_key, 0))
    label = attack_label or "атака"
    main = defender_state["main"]

    if current <= 0:
        heal = int(dealt_damage * 0.5)
        main.hp = min(main.max_hp, main.hp + heal)
        adapt_map[attack_key] = 0.5
        battle["log"].append(
            f"🌀 Махорага адаптируется к атаке «{label}»: -50% урона."
        )
    elif current < 1.0:
        heal = int(dealt_damage)
        main.hp = min(main.max_hp, main.hp + heal)
        adapt_map[attack_key] = 1.0
        battle["log"].append(
            f"🌀 Махорага полностью адаптировался к «{label}» (100%)."
        )
    else:
        heal = int(dealt_damage)
        main.hp = min(main.max_hp, main.hp + heal)
        battle["log"].append(
            f"🌀 Махорага блокирует «{label}» (100%)."
        )


def _enemy_damage_cap(defender, attack_key: str | None) -> int:
    key = str(attack_key or "")
    if key.startswith("special_"):
        ratio = PVE_ENEMY_SPECIAL_MAX_HIT_PCT
    elif key.startswith("domain"):
        ratio = PVE_ENEMY_DOMAIN_MAX_HIT_PCT
    else:
        ratio = PVE_ENEMY_BASIC_MAX_HIT_PCT
    return max(1, int(defender.max_hp * ratio))


def _apply_enemy_burst_cap(
    battle: dict,
    attacker_num: int,
    defender_num: int,
    defender,
    before_hp: int,
    dealt: int,
    attack_key: str | None,
) -> int:
    if attacker_num != 2 or defender_num != 1:
        return dealt
    defender_state = battle["fighters"].get(defender_num, {})
    if not defender_state.get("is_player", False):
        return dealt

    actual_loss = max(0, before_hp - defender.hp)
    cap = min(before_hp, _enemy_damage_cap(defender, attack_key))
    if actual_loss > cap:
        defender.hp = max(0, before_hp - cap)
        battle["log"].append(f"🛡 Антиваншот: урон врага ограничен до {cap}.")
        return cap
    return actual_loss


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
) -> tuple[int, bool, float, bool]:
    attacker_state = battle["fighters"][attacker_num]
    defender_state = battle["fighters"][defender_num]
    rng = _battle_rng(battle)

    if attack_key and defender_state.get("has_mahoraga") and defender_state.get("mahoraga_ready"):
        adapt_map = defender_state.setdefault("mahoraga_adapt", {})
        current = float(adapt_map.get(attack_key, 0))
        if current >= 1.0:
            label = attack_label or "атака"
            battle["log"].append(f"🌀 Махорага блокирует «{label}» (100%).")
            return 0, False, 0.0, False

    if defender_state.get("block_next_hits", 0) > 0:
        defender_state["block_next_hits"] -= 1
        return 0, False, 0.0, True

    infinity_chance = float(defender_state.get("infinity_chance", 0.0) or 0.0)
    if infinity_chance > 0 and not ignore_infinity:
        if rng.random() < infinity_chance:
            battle["log"].append("∞ Бесконечность блокирует атаку.")
            return 0, False, 0.0, False

    if can_dodge and not _is_guaranteed_hit(battle, attacker_num, defender_num):
        chance = _dodge_chance(battle, attacker_state, defender_state, attacker_num, defender_num)
        if chance > 0 and rng.random() < chance:
            return 0, True, chance, False

    attacker_bonus = _domain_attack_bonus(battle, attacker_num, defender_num)
    final_raw = max(1, int(raw_damage * attacker_bonus))
    defender = defender_state["main"]
    before_hp = int(defender.hp)
    if ignore_defense:
        dealt = defender.take_true_damage(final_raw)
    else:
        dealt = defender.take_damage(final_raw)
    dealt = _apply_enemy_burst_cap(
        battle=battle,
        attacker_num=attacker_num,
        defender_num=defender_num,
        defender=defender,
        before_hp=before_hp,
        dealt=dealt,
        attack_key=attack_key,
    )
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


def _domain_power(state: dict, rng) -> int:
    main = state["main"]
    shikigami = state.get("shikigami")
    support_bonus = (shikigami.attack + shikigami.defense) // 3 if shikigami else 0
    domain_level = state.get("domain_level", 0)
    return (
        main.attack
        + main.defense
        + main.speed
        + support_bonus
        + domain_level * 40
        + rng.randint(0, 120)
    )


def _spend_ce(state: dict, amount: int) -> bool:
    if state["ce"] < amount:
        return False
    state["ce"] -= amount
    return True


def _format_fighter_line(prefix: str, state: dict) -> str:
    simple_left = state.get("simple_domain_turns", 0)
    simple_text = f" | 🛡 {simple_left}х" if simple_left > 0 else ""
    weapon = state.get("weapon")
    shikigami = state.get("shikigami")
    weapon2 = state.get("weapon2")
    weapon_name = weapon.card_template.name if weapon and weapon.card_template else "—"
    shikigami_name = shikigami.card_template.name if shikigami and shikigami.card_template else "—"
    weapon2_name = weapon2.card_template.name if weapon2 and weapon2.card_template else "—"
    support_line = f"🗡 {weapon_name} | 🗡 {weapon2_name}" if weapon2 else f"🗡 {weapon_name} | 🐺 {shikigami_name}"
    power = _state_power(state)
    return (
        f"{prefix} {state['main'].card_template.name}\n"
        f"{support_line}\n"
        f"❤️ {state['main'].hp}/{state['main'].max_hp} | "
        f"💧 {state['ce']}/{state['max_ce']}{simple_text}\n"
        f"💪 Сила: {power}\n"
    )


def _fighter_name(state: dict) -> str:
    main = state.get("main")
    template = getattr(main, "card_template", None)
    return getattr(template, "name", None) or "Боец"


def _fighter_tag(battle: dict, fighter_num: int) -> str:
    icon = "👑" if fighter_num == 1 else "👹"
    state = battle["fighters"].get(fighter_num, {})
    return f"{icon} {_fighter_name(state)}"


def _state_power(state: dict) -> int:
    main = state["main"]
    shikigami = state.get("shikigami")
    attack = main.attack + (shikigami.attack // 2 if shikigami else 0)
    defense = main.defense + (shikigami.defense // 2 if shikigami else 0)
    speed = main.speed + (shikigami.speed if shikigami else 0)
    hp = main.max_hp + (shikigami.max_hp // 2 if shikigami else 0)
    max_ce = int(state.get("max_ce", main.max_ce))
    return int(attack + defense + speed + hp // 10 + max_ce // 20)


def _defense_reduction_pct(attacker_state: dict, defender_state: dict) -> int:
    base_damage = max(1, _get_base_damage(attacker_state))
    defense = max(0, int(defender_state["main"].defense))
    actual = max(1, base_damage - defense)
    reduction = 1.0 - (actual / base_damage)
    return max(0, min(99, int(reduction * 100)))


async def _ensure_curse(session, curse_data: dict, enemy_card: SimpleCard) -> Curse:
    result = await session.execute(
        select(Curse).where(Curse.name == curse_data["name"])
    )
    curse = result.scalar_one_or_none()
    if not curse:
        curse = Curse(
            name=curse_data["name"],
            description=curse_data.get("description"),
            grade=curse_data.get("grade", 1),
            curse_type=curse_data.get("curse_type", "normal"),
            attack=enemy_card.attack,
            defense=enemy_card.defense,
            speed=enemy_card.speed,
            hp=enemy_card.max_hp,
            max_hp=enemy_card.max_hp,
            exp_reward=curse_data.get("exp_reward", 20),
            points_reward=curse_data.get("points_reward", 1),
            card_drop_chance=curse_data.get("card_drop_chance", 1.0),
        )
        session.add(curse)
        await session.flush()
    return curse


async def _prepare_enemy(
    session,
    battle: dict,
    stage: int,
    player_level: int,
) -> tuple[Curse, dict]:
    difficulty = _normalize_pve_difficulty(battle.get("difficulty"))
    battle["difficulty"] = difficulty
    cfg = _get_pve_config(difficulty)
    baseline = battle["baseline"]

    curse_data = _select_curse(difficulty, player_level)
    progress_mult = _enemy_progress_multiplier(cfg, stage)
    seed_tag = f"{curse_data.get('name', 'curse')}|{difficulty}|{stage}"
    enemy_card = _build_enemy_card(
        curse_data,
        baseline,
        difficulty,
        progress_mult=progress_mult,
        seed_tag=seed_tag,
    )
    enemy_profile = _get_enemy_profile(difficulty, seed_tag=seed_tag)
    enemy_toolkit = cfg["toolkit"]

    enemy_state = _build_fighter_state(
        enemy_card,
        None,
        None,
        [],
        enemy_toolkit,
        profile_override=enemy_profile,
    )
    enemy_state["strategy_bias"] = dict(cfg.get("enemy_bias", {}))
    enemy_card.heal()

    curse = await _ensure_curse(session, curse_data, enemy_card)
    return curse, enemy_state


def _pve_preview_text(battle: dict) -> str:
    player_state = battle["fighters"][1]
    enemy_state = battle["fighters"][2]
    stage = battle.get("stage", 1)
    difficulty = _normalize_pve_difficulty(battle.get("difficulty"))
    cfg = _get_pve_config(difficulty)
    label = cfg["label"]
    strategy_label = _strategy_label(battle.get("strategy"))

    text = (
        "👹 <b>Арена проклятий</b>\n\n"
        f"⚙️ Сложность: <b>{label}</b>\n"
        f"🧠 Стиль: <b>{strategy_label}</b>\n"
        f"🏁 Этап: <b>{stage}</b>\n\n"
        "<b>Твоя команда:</b>\n"
        f"{_format_fighter_line('👑', player_state)}\n"
        "<b>Противник:</b>\n"
        f"{_format_fighter_line('👹', enemy_state)}\n"
    )

    player_def_pct = _defense_reduction_pct(enemy_state, player_state)
    enemy_def_pct = _defense_reduction_pct(player_state, enemy_state)
    player_dodge_pct = int(_dodge_chance(battle, enemy_state, player_state, 2, 1) * 100)
    enemy_dodge_pct = int(_dodge_chance(battle, player_state, enemy_state, 1, 2) * 100)
    player_power = _state_power(player_state)
    enemy_power = _state_power(enemy_state)
    ratio = player_power / max(1, enemy_power)
    if ratio >= 1.20:
        forecast = "Сильное преимущество"
    elif ratio >= 1.05:
        forecast = "Небольшой перевес"
    elif ratio <= 0.83:
        forecast = "Очень опасно"
    elif ratio <= 0.95:
        forecast = "Сложный бой"
    else:
        forecast = "Равный бой"

    text += (
        "📊 <b>Боевая сводка:</b>\n"
        f"🛡 Твоя защита: ~{player_def_pct}% снижения базового урона\n"
        f"🛡 Защита врага: ~{enemy_def_pct}% снижения твоего базового урона\n"
        f"💨 Твой шанс уклонения: {player_dodge_pct}%\n"
        f"💨 Уклонение врага: {enemy_dodge_pct}%\n"
        f"🎁 База наград: x{_format_multiplier(cfg['reward_mult'])} опыта, "
        f"x{_format_multiplier(cfg['drop_mult'])} к шансу карты\n\n"
        f"💡 Прогноз: {forecast}\n\n"
        "Тактический бой: комбинируй удары, техники, домен и лечение."
    )
    return text


async def _send_pve_preview(callback: CallbackQuery, battle: dict):
    text = _pve_preview_text(battle)
    keyboard = get_pve_start_keyboard(battle.get("strategy", PVE_DEFAULT_STRATEGY))
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )


async def _send_active_run_prompt(callback: CallbackQuery, battle: dict):
    stage = int(battle.get("stage", 1))
    player_state = battle["fighters"][1]
    hp_line = f"{player_state['main'].hp}/{player_state['main'].max_hp}"

    awaiting = bool(battle.get("awaiting_continue"))
    if awaiting:
        text = (
            "🏁 <b>У тебя уже есть активный PvE забег</b>\n\n"
            f"Этап: <b>{stage}</b>\n"
            f"HP: <b>{hp_line}</b>\n\n"
            "Продолжить забег?"
        )
    else:
        text = _pve_preview_text(battle)

    can_heal = False
    if player_state.get("has_reverse_ct") and player_state["main"].hp < player_state["main"].max_hp:
        can_heal = True

    keyboard = get_pve_active_keyboard(
        awaiting_continue=awaiting,
        can_heal=can_heal,
        heal_cost=int(player_state.get("rct_cost", 2500)),
        strategy=battle.get("strategy", PVE_DEFAULT_STRATEGY),
    )

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

def _run_auto_battle(battle: dict) -> bool:
    battle["log"] = []
    battle["turn"] = 1

    player_state = battle["fighters"][1]
    enemy_state = battle["fighters"][2]

    player_power = _state_power(player_state)
    enemy_power = _state_power(enemy_state)
    if player_power >= enemy_power * AUTO_POWER_WIN_THRESHOLD:
        battle["log"].append("💥 Ты значительно сильнее противника. Победа за явным преимуществом.")
        enemy_state["main"].hp = 0
        return True
    if enemy_power >= player_power * AUTO_POWER_WIN_THRESHOLD:
        battle["log"].append("💥 Противник значительно сильнее. Поражение неизбежно.")
        player_state["main"].hp = 0
        return False

    player_speed = _get_fighter_speed(player_state)
    enemy_speed = _get_fighter_speed(enemy_state)

    if enemy_speed > player_speed:
        attacker = 2
        battle["log"].append("👹 Проклятие атакует первым (скорость выше).")
    else:
        attacker = 1
        battle["log"].append("⚡ Ты атакуешь первым (скорость выше).")

    battle["current_player"] = attacker
    rounds = 0

    while player_state["main"].is_alive() and enemy_state["main"].is_alive():
        _reset_turn_flags(battle, attacker)
        _apply_start_turn_effects(battle, attacker)
        if not battle["fighters"][attacker]["main"].is_alive():
            break

        defender_alive = _auto_take_turn(battle, attacker)
        if not defender_alive:
            break

        attacker = 2 if attacker == 1 else 1
        battle["current_player"] = attacker
        battle["turn"] += 1
        rounds += 1

        if rounds >= AUTO_BATTLE_TURN_CAP:
            player_hp = player_state["main"].hp
            enemy_hp = enemy_state["main"].hp
            if player_hp >= enemy_hp:
                enemy_state["main"].hp = 0
                battle["log"].append("⚠️ Бой затянулся. Победа по оставшемуся HP.")
            else:
                player_state["main"].hp = 0
                battle["log"].append("⚠️ Бой затянулся. Поражение по оставшемуся HP.")
            break

    return player_state["main"].is_alive()


async def _start_auto_battle(callback: CallbackQuery, battle: dict):
    battle["awaiting_continue"] = False
    won = _run_auto_battle(battle)
    await end_pve_battle(callback, battle["user_id"], won)


async def _start_tactical_battle(callback: CallbackQuery, battle: dict):
    battle["awaiting_continue"] = False
    battle["auto"] = False
    battle["in_battle"] = True
    battle["log"] = []
    battle["turn"] = 1
    battle["domain_state"] = None
    battle["pending_domain_response"] = None
    battle["battlerdan_pending"] = None
    battle["turn_flags"] = {
        1: {"attack_used": False, "rct_used": False, "mahoraga_used": False},
        2: {"attack_used": False, "rct_used": False, "mahoraga_used": False},
    }

    player_state = battle["fighters"][1]
    enemy_state = battle["fighters"][2]
    player_speed = _get_fighter_speed(player_state)
    enemy_speed = _get_fighter_speed(enemy_state)

    if enemy_speed > player_speed:
        battle["current_player"] = 2
        battle["log"].append("👹 Проклятие начинает бой первым.")
        await _process_enemy_turn(callback, battle)
        return

    battle["current_player"] = 1
    battle["log"].append("⚡ Ты начинаешь бой первым.")
    await _update_battle_message(callback, battle)


def _battle_view_text(battle: dict) -> str:
    player_state = battle["fighters"][1]
    enemy_state = battle["fighters"][2]

    text = f"👹 <b>PvE бой — ход {battle['turn']}</b>\n\n"
    text += "<b>Твоя команда:</b>\n"
    text += _format_fighter_line("👑", player_state)
    text += "\n<b>Противник:</b>\n"
    text += _format_fighter_line("👹", enemy_state)

    if battle.get("difficulty"):
        difficulty = _normalize_pve_difficulty(battle.get("difficulty"))
        label = _get_pve_config(difficulty)["label"]
        text += f"\n⚙️ Сложность: <b>{label}</b>\n"

    if battle.get("log"):
        tail = battle["log"][-5:]
        text += "\n📜 <b>Последние события:</b>\n" + "\n".join(tail)

    pending_battlerdan = _pending_battlerdan_for(battle, 1)
    if pending_battlerdan:
        if pending_battlerdan.get("stage") == "choose":
            text += "\n\n🗣 <b>Дебаты:</b> выбери аргумент."
        elif pending_battlerdan.get("stage") == "guess":
            text += "\n\n❓ <b>Дебаты:</b> угадай аргумент."

    if battle["current_player"] == 1:
        text += "\n\n⚡ <b>Твой ход!</b>"
    else:
        text += "\n\n⏳ <b>Ход противника...</b>"
    return text


def _build_fighter_state(
    main_card: UserCard | SimpleCard,
    weapon_card: UserCard | None,
    shikigami_card: UserCard | None,
    pact_cards: list[UserCard | None],
    toolkit: dict,
    profile_override: dict | None = None,
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

    profile = profile_override or _get_character_profile(main_name)
    specials = [dict(sp) for sp in profile.get("specials", [])]

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

    support_ce_bonus = shikigami_card.max_ce * 30 if shikigami_card else 0
    max_ce = max(3000, main_card.max_ce * 100 + support_ce_bonus)
    ce_regen = max(300, main_card.get_ce_regen() * 100)

    if is_toji:
        max_ce = 0
        ce_regen = 0

    domain_level = getattr(main_card, "domain_level", 0) or 0
    rct_level = getattr(main_card, "rct_level", 0) or 0
    domain_dot_pct = profile["domain_dot_pct"] + domain_level * DOMAIN_DOT_PER_POINT
    domain_damage_bonus = profile["domain_damage_bonus"] + domain_level * DOMAIN_DAMAGE_BONUS_PER_POINT

    has_mahoraga = False
    if shikigami_card and shikigami_card.card_template:
        has_mahoraga = _normalize_name(shikigami_card.card_template.name) == "махорага"
    if is_megumi:
        has_mahoraga = True

    mahoraga_cost = MAHORAGA_ADAPT_COST
    shikigami_damage_mult = 0.5
    if is_megumi:
        mahoraga_cost = int(MAHORAGA_ADAPT_COST * 0.6)
        shikigami_damage_mult = 0.7

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

    is_player = isinstance(main_card, UserCard)
    black_flash_chance = (
        get_black_flash_chance(main_name) if is_player else 0.0
    )

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
        "domain_cost": 4000,
        "simple_domain_cost": 0,
        "rct_cost": 2500,
        "simple_domain_turns": 0,
        "black_flash_chance": black_flash_chance,
        "domain_level": domain_level,
        "rct_level": rct_level,
        "next_attack_multiplier": 1.0,
        "next_attack_ready": False,
        "pact_used": set(),
        "domain_used": False,
        "has_mahoraga": has_mahoraga,
        "mahoraga_ready": False,
        "mahoraga_adapt": {},
        "mahoraga_domain_adapt": {},
        "mahoraga_cost": mahoraga_cost,
        "higuruma_sword_ready": False,
        "ce_lock_turns": 0,
        "attack_multiplier": attack_multiplier,
        "is_player": is_player,
        "shikigami_damage_mult": shikigami_damage_mult,
        "pacts_disabled": is_toji,
        "ignore_domain_effects": is_toji,
        "is_battlerdan": is_battlerdan,
        "infinity_chance": 0.8 if is_gojo and TECH_INFINITY in technique_names else 0.0,
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

    state["base_attack_multiplier"] = float(state.get("attack_multiplier", 1.0))
    state["base_stats"] = {
        "attack": int(getattr(main_card, "attack", 0) or 0),
        "defense": int(getattr(main_card, "defense", 0) or 0),
        "speed": int(getattr(main_card, "speed", 0) or 0),
        "max_hp": int(getattr(main_card, "max_hp", 0) or 0),
        "max_ce": int(state.get("max_ce", 0) or 0),
        "ce_regen": int(state.get("ce_regen", 0) or 0),
    }

    return state


def _find_active_pve_battle(user_id_or_tg: int) -> tuple[dict | None, int | None]:
    battle = active_pve_battles.get(user_id_or_tg)
    if battle:
        return battle, user_id_or_tg

    for tg_id, stored in active_pve_battles.items():
        if stored.get("user_id") == user_id_or_tg or stored.get("player_tg") == user_id_or_tg:
            return stored, tg_id

    return None, None

def _apply_start_turn_effects(battle: dict, player_num: int):
    state = battle["fighters"][player_num]

    ce_lock = int(state.get("ce_lock_turns", 0) or 0)
    if ce_lock > 0:
        state["ce"] = 0
        state["ce_lock_turns"] = ce_lock - 1
        battle["log"].append("🔒 Проклятая энергия запечатана и не восстанавливается.")
    else:
        state["ce"] = min(state["max_ce"], state["ce"] + state["ce_regen"])

    jackpot_turns = int(state.get("hakari_jackpot_turns", 0) or 0)
    if jackpot_turns > 0:
        before = state["main"].hp
        state["main"].hp = state["main"].max_hp
        healed = state["main"].hp - before
        if healed > 0:
            battle["log"].append("🎰 Джекпот: HP восстановлены до максимума.")
        state["hakari_jackpot_turns"] = jackpot_turns - 1

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
        owner_num = int(domain.get("owner", 0) or 0)
        owner_tag = _fighter_tag(battle, owner_num) if owner_num in battle.get("fighters", {}) else "👹 Владелец домена"
        target_tag = _fighter_tag(battle, player_num)
        if state.get("ignore_domain_effects"):
            if pending_response:
                battle["pending_domain_response"] = None
            battle["log"].append(f"🛡 {target_tag} игнорирует эффекты территории {owner_tag}.")
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
            base_raw = int(state["main"].max_hp * domain["dot_pct"]) + int(owner_state["main"].attack * 0.25)
            effect = domain.get("effect", "dot")
            if effect == "gojo_crit":
                raw = int(base_raw * 2.0)
                raw = int(raw * (1 + domain.get("damage_bonus", 0.0)))
                before_hp = int(state["main"].hp)
                dealt = state["main"].take_damage(max(1, raw))
                dealt = _apply_enemy_burst_cap(
                    battle=battle,
                    attacker_num=int(domain.get("owner", 0) or 0),
                    defender_num=player_num,
                    defender=state["main"],
                    before_hp=before_hp,
                    dealt=dealt,
                    attack_key="domain_gojo_crit",
                )
                battle["log"].append(
                    f"🏯 {owner_tag}: {domain['name']} наносит критический урон по {target_tag}: {dealt}."
                )
            elif effect == "soul_dot":
                raw = int(base_raw * (1 + domain.get("damage_bonus", 0.0)))
                before_hp = int(state["main"].hp)
                dealt = state["main"].take_true_damage(max(1, raw))
                dealt = _apply_enemy_burst_cap(
                    battle=battle,
                    attacker_num=int(domain.get("owner", 0) or 0),
                    defender_num=player_num,
                    defender=state["main"],
                    before_hp=before_hp,
                    dealt=dealt,
                    attack_key="domain_soul",
                )
                battle["log"].append(
                    f"🏯 {owner_tag}: {domain['name']} бьёт по душе {target_tag}: {dealt} урона."
                )
            else:
                raw = int(base_raw * (1 + domain.get("damage_bonus", 0.0)))
                before_hp = int(state["main"].hp)
                dealt = state["main"].take_damage(max(1, raw))
                dealt = _apply_enemy_burst_cap(
                    battle=battle,
                    attacker_num=int(domain.get("owner", 0) or 0),
                    defender_num=player_num,
                    defender=state["main"],
                    before_hp=before_hp,
                    dealt=dealt,
                    attack_key="domain_dot",
                )
                battle["log"].append(
                    f"🏯 {owner_tag}: {domain['name']} наносит {dealt} урона по {target_tag}."
                )
            domain["turns_left"] -= 1
            if domain["turns_left"] <= 0:
                battle["log"].append("🌫 Эффект территории рассеялся.")
                battle["domain_state"] = None

    if simple_active:
        state["simple_domain_turns"] -= 1
        if state["simple_domain_turns"] == 0:
            battle["log"].append("🛡 Простая территория закончилась.")


def _collect_weapon_effects(rng, *weapons: UserCard | None) -> tuple[float, bool, bool]:
    multiplier = 1.0
    ignore_defense = False
    ignore_infinity = False
    for weapon in weapons:
        effect = get_weapon_effect(weapon)
        if not effect:
            continue
        if effect.get("type") == "basic_multiplier":
            roll = rng.uniform(effect.get("min", 1.0), effect.get("max", 1.0))
            multiplier = max(multiplier, roll)
        elif effect.get("type") == "ignore_defense":
            ignore_defense = True
        elif effect.get("type") == "ignore_infinity":
            ignore_infinity = True
    return multiplier, ignore_defense, ignore_infinity


def _action_basic_attack(battle: dict, attacker_num: int):
    attacker = battle["fighters"][attacker_num]
    defender_num = 2 if attacker_num == 1 else 1
    defender = battle["fighters"][defender_num]
    rng = _battle_rng(battle)
    attacker_tag = _fighter_tag(battle, attacker_num)
    defender_tag = _fighter_tag(battle, defender_num)

    base_damage = _get_base_damage(attacker)
    multiplier, ignore_defense, ignore_infinity = _collect_weapon_effects(
        rng,
        attacker.get("weapon"), attacker.get("weapon2")
    )
    if multiplier != 1.0:
        base_damage = int(base_damage * multiplier)
    black_flash = rng.random() < attacker["black_flash_chance"]

    if black_flash:
        base_damage = int(base_damage * 1.10)

    base_damage, pact_mult = _apply_pact_attack_bonus(attacker, base_damage)

    dealt, dodged, dodge_chance, blocked = _deal_damage(
        battle,
        attacker_num,
        defender_num,
        base_damage,
        ignore_defense=ignore_defense,
        ignore_infinity=ignore_infinity,
        attack_key="basic",
        attack_label="удар рукой",
    )
    if blocked:
        battle["log"].append(f"🦆 {defender_tag} блокирует удар от {attacker_tag}.")
        return defender["main"].is_alive()
    if dodged:
        dodge_pct = int(dodge_chance * 100)
        battle["log"].append(
            f"💨 {defender_tag} уклоняется от атаки {attacker_tag} (шанс {dodge_pct}%)."
        )
        return defender["main"].is_alive()
    if black_flash:
        restore_amount = min(4000, attacker["max_ce"] - attacker["ce"])
        attacker["ce"] += restore_amount
        battle["log"].append(
            f"⚫ {attacker_tag} активирует Чёрную молнию по {defender_tag}: "
            f"{dealt} урона, CE +{restore_amount}."
        )
    else:
        battle["log"].append(
            f"👊 {attacker_tag} наносит обычной атакой {dealt} урона по {defender_tag}."
        )

    return defender["main"].is_alive()


def _action_special(battle: dict, attacker_num: int, key: str):
    attacker = battle["fighters"][attacker_num]
    defender_num = 2 if attacker_num == 1 else 1
    defender = battle["fighters"][defender_num]
    rng = _battle_rng(battle)
    attacker_tag = _fighter_tag(battle, attacker_num)
    defender_tag = _fighter_tag(battle, defender_num)

    if attacker.get("simple_domain_turns", 0) > 0:
        return False, "Во время простой территории нельзя использовать спецтехники."

    special = next((sp for sp in attacker["specials"] if sp["key"] == key), None)
    if not special:
        return False, "Эта техника недоступна."

    if not _spend_ce(attacker, special["ce_cost"]):
        return False, "Недостаточно CE для этой техники."

    if special.get("effect") == "duck_guard":
        block_hits = max(1, int(special.get("block_hits", 1)))
        attacker["block_next_hits"] = max(attacker.get("block_next_hits", 0), block_hits)
        battle["log"].append("🦆 Уточки перекрывают следующий удар врага.")
        return defender["main"].is_alive(), None

    raw = int(_get_base_damage(attacker) * special["multiplier"] + special.get("flat", 0))
    raw, pact_mult = _apply_pact_attack_bonus(attacker, raw)

    _, ignore_defense, ignore_infinity = _collect_weapon_effects(
        rng,
        attacker.get("weapon"), attacker.get("weapon2")
    )

    dealt, dodged, dodge_chance, blocked = _deal_damage(
        battle,
        attacker_num,
        defender_num,
        raw,
        ignore_defense=ignore_defense,
        ignore_infinity=ignore_infinity,
        attack_key=f"special_{special['key']}",
        attack_label=special["name"],
    )
    if blocked:
        battle["log"].append(f"🦆 {defender_tag} блокирует технику от {attacker_tag}.")
        return defender["main"].is_alive(), None
    if dodged:
        dodge_pct = int(dodge_chance * 100)
        battle["log"].append(
            f"💨 {defender_tag} уклоняется от техники «{special['name']}» "
            f"от {attacker_tag} (шанс {dodge_pct}%)."
        )
        return defender["main"].is_alive(), None
    battle["log"].append(
        f"{special['icon']} {attacker_tag} применяет «{special['name']}» по {defender_tag}: "
        f"{dealt} урона (-{special['ce_cost']} CE)."
    )
    return defender["main"].is_alive(), None


def _apply_higuruma_domain_effect(battle: dict, attacker_num: int, defender_num: int):
    attacker = battle["fighters"][attacker_num]
    defender = battle["fighters"][defender_num]
    rng = _battle_rng(battle)
    if defender.get("ignore_domain_effects"):
        battle["log"].append("🛡 Тоджи не подчиняется суду Хигурумы.")
        battle["domain_state"] = None
        battle["pending_domain_response"] = None
        battle["log"].append("🏯 Территория Хигурумы рассеялась.")
        return
    if rng.random() < 0.5:
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
    rng = _battle_rng(battle)
    chance = float(attacker.get("hakari_jackpot_chance", 0.33) or 0.33)
    if rng.random() < chance:
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
    defender_num = 2 if attacker_num == 1 else 1
    defender = battle["fighters"][defender_num]
    cost = attacker["domain_cost"]
    rng = _battle_rng(battle)

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
            attacker_power = _domain_power(attacker, rng)
            defender_power = _domain_power(defender, rng)
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
            "stage": "choose",
            "owner": attacker_num,
            "target": defender_num,
            "choice": None,
            "options": [1, 2, 3],
        }
        battle["log"].append("🏯 Баттлердан открывает дебаты. Выбери аргумент.")
        return True, None

    domain = battle.get("domain_state")
    if domain and domain["owner"] == attacker_num:
        attacker["ce"] += cost
        return False, "Твоя территория уже активна."

    if domain and domain["owner"] == defender_num:
        attacker_power = _domain_power(attacker, rng)
        defender_power = _domain_power(defender, rng)

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
            f"🛡 Простая территория активирована на {DEFAULT_SIMPLE_DOMAIN_DURATION} хода (-{cost} CE)."
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


def _action_higuruma_sword(battle: dict, attacker_num: int):
    attacker = battle["fighters"][attacker_num]
    if not attacker.get("higuruma_sword_ready", False):
        return False, "Золотой меч сейчас недоступен."

    defender_num = 2 if attacker_num == 1 else 1
    defender = battle["fighters"][defender_num]
    defender["main"].hp = 0
    attacker["higuruma_sword_ready"] = False
    battle["log"].append("⚖️ Золотой меч Хигурумы сразил врага мгновенно.")
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

    return True, effect.get("label", "Пакт активирован.")


def _choose_best_special(state: dict) -> dict | None:
    specials = state.get("specials", [])
    if not specials:
        return None
    base = _get_base_damage(state)
    best = None
    best_score = -1
    for sp in specials:
        if state.get("ce", 0) < sp["ce_cost"]:
            continue
        score = base * float(sp.get("multiplier", 1.0)) + float(sp.get("flat", 0))
        if score > best_score:
            best_score = score
            best = sp
    return best


def _enemy_choose_special(enemy: dict) -> dict | None:
    return _choose_best_special(enemy)


def _can_use_domain(state: dict, battle: dict, player_num: int) -> bool:
    if not state.get("has_domain", False):
        return False
    if state.get("ce", 0) < state.get("domain_cost", 0):
        return False
    domain = battle.get("domain_state")
    if domain and domain.get("owner") == player_num:
        return False
    return True


def _can_enemy_use_domain(enemy: dict, battle: dict) -> bool:
    return _can_use_domain(enemy, battle, 2)


def _should_enemy_heal(enemy: dict) -> bool:
    if not enemy.get("has_reverse_ct", False):
        return False
    if enemy.get("ce", 0) < enemy.get("rct_cost", 0):
        return False
    hp_ratio = enemy["main"].hp / max(1, enemy["main"].max_hp)
    bias = _strategy_bias(enemy, "heal")
    threshold = 0.35 + bias
    threshold = min(0.75, max(0.15, threshold))
    return hp_ratio <= threshold


def _hp_ratio(state: dict) -> float:
    return state["main"].hp / max(1, state["main"].max_hp)


def _should_use_special(state: dict, special: dict) -> bool:
    if state.get("simple_domain_turns", 0) > 0:
        return False
    if state.get("ce", 0) < special.get("ce_cost", 0):
        return False
    base = _get_base_damage(state)
    expected = base * float(special.get("multiplier", 1.0)) + float(special.get("flat", 0))
    bias = _strategy_bias(state, "special")
    min_gain = min(1.3, max(0.9, 1.1 - bias))
    ce_floor = min(0.9, max(0.3, 0.6 - bias))
    if expected <= base * min_gain and state.get("ce", 0) < state.get("max_ce", 1) * ce_floor:
        return False
    return True


def _estimated_special_damage(state: dict, defender_state: dict, special: dict) -> int:
    raw = int(
        _get_base_damage(state) * float(special.get("multiplier", 1.0))
        + float(special.get("flat", 0))
    )
    defense = int(defender_state["main"].defense)
    return max(1, raw - defense)


def _choose_finisher_special(state: dict, defender_state: dict) -> dict | None:
    defender_hp = int(defender_state["main"].hp)
    if defender_hp <= 0:
        return None

    candidate = None
    candidate_damage = 0
    for special in state.get("specials", []):
        cost = int(special.get("ce_cost", 0))
        if state.get("ce", 0) < cost:
            continue
        damage = _estimated_special_damage(state, defender_state, special)
        if damage > candidate_damage and defender_hp <= int(damage * 1.10):
            candidate = special
            candidate_damage = damage
    return candidate


def _should_use_domain_auto(battle: dict, player_num: int) -> bool:
    state = battle["fighters"][player_num]
    if state.get("domain_used"):
        return False
    if not _can_use_domain(state, battle, player_num):
        return False
    defender = battle["fighters"][2 if player_num == 1 else 1]
    bias = _strategy_bias(state, "domain")
    hp_trigger = min(0.9, max(0.5, 0.7 + bias))
    defender_trigger = min(0.85, max(0.45, 0.65 - bias))
    ce_trigger = min(0.98, max(0.75, 0.9 - bias * 0.5))
    if _hp_ratio(state) <= hp_trigger or _hp_ratio(defender) >= defender_trigger or state.get("ce", 0) >= state.get("max_ce", 1) * ce_trigger:
        state["domain_used"] = True
        return True
    return False


def _auto_take_turn(battle: dict, player_num: int) -> bool:
    state = battle["fighters"][player_num]
    defender_num = 2 if player_num == 1 else 1
    defender = battle["fighters"][defender_num]
    flags = _get_turn_flags(battle, player_num)
    rng = _battle_rng(battle)

    pending_battlerdan = _pending_battlerdan_for(battle, player_num)
    if pending_battlerdan:
        if pending_battlerdan.get("stage") == "choose":
            choice = rng.randint(1, 3)
            pending_battlerdan["choice"] = choice
            pending_battlerdan["stage"] = "guess"
            battle["log"].append("🗣 Баттлердан выбрал аргумент. Противник пытается угадать...")
            return battle["fighters"][defender_num]["main"].is_alive()
        if pending_battlerdan.get("stage") == "guess":
            guess = rng.randint(1, 3)
            _resolve_battlerdan_guess(battle, pending_battlerdan, guess)
            battle["battlerdan_pending"] = None
            return battle["fighters"][defender_num]["main"].is_alive()

    if _pending_response_for(battle, player_num):
        if state.get("has_domain") and state.get("ce", 0) >= state.get("domain_cost", 0):
            _action_domain(battle, player_num)
            if player_num == 1:
                battle["pending_achievement_domain"] = True
        elif state.get("has_simple_domain") and state.get("simple_domain_turns", 0) == 0:
            _action_simple_domain(battle, player_num)
        elif _can_use_mahoraga(battle, player_num, flags):
            _action_mahoraga(battle, player_num)
            flags["mahoraga_used"] = True
        else:
            battle["log"].append("⏭ Нет ответа на домен.")
        battle["pending_domain_response"] = None
        return battle["fighters"][defender_num]["main"].is_alive()

    finisher = _choose_finisher_special(state, defender)
    if finisher and not flags.get("attack_used"):
        defender_alive, _ = _action_special(battle, player_num, finisher["key"])
        flags["attack_used"] = True
        return defender_alive

    if _should_enemy_heal(state) and not flags.get("rct_used"):
        _action_reverse_ct(battle, player_num)
        flags["rct_used"] = True
        return battle["fighters"][defender_num]["main"].is_alive()

    if _should_use_domain_auto(battle, player_num):
        prev_domain = battle.get("domain_state")
        prev_owner = prev_domain.get("owner") if prev_domain else None
        _action_domain(battle, player_num)
        if player_num == 1:
            battle["pending_achievement_domain"] = True
        pending_battlerdan = battle.get("battlerdan_pending")
        if pending_battlerdan and pending_battlerdan.get("owner") == player_num and pending_battlerdan.get("stage") == "choose":
            choice = rng.randint(1, 3)
            pending_battlerdan["choice"] = choice
            pending_battlerdan["stage"] = "guess"
            battle["log"].append("🗣 Баттлердан выбрал аргумент. Противник пытается угадать...")
            return battle["fighters"][defender_num]["main"].is_alive()
        domain_state = battle.get("domain_state")
        if prev_owner is None and domain_state and domain_state.get("owner") == player_num:
            battle["pending_domain_response"] = {"target": defender_num, "owner": player_num}
        return battle["fighters"][defender_num]["main"].is_alive()

    special = _choose_best_special(state)
    if special and _should_use_special(state, special):
        defender_alive, _ = _action_special(battle, player_num, special["key"])
    else:
        defender_alive = _action_basic_attack(battle, player_num)

    flags["attack_used"] = True
    return defender_alive


async def _update_battle_message(callback: CallbackQuery, battle: dict):
    text = _battle_view_text(battle)
    is_your_turn = battle["current_player"] == 1
    action_state = _get_action_state(battle, 1) if is_your_turn else None
    keyboard = get_pve_battle_keyboard(
        is_your_turn=is_your_turn,
        fighter_state=battle["fighters"][1],
        action_state=action_state,
    )

    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            return
        except Exception:
            pass

    await callback.bot.send_message(
        callback.from_user.id,
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def _advance_turn(callback: CallbackQuery, battle: dict, acting_player_num: int):
    next_player = 2 if acting_player_num == 1 else 1
    battle["current_player"] = next_player
    battle["turn"] += 1
    _reset_turn_flags(battle, next_player)

    if acting_player_num == 1 and battle.pop("pending_achievement_domain", False):
        await check_achievements(battle["user_id"], "territories_used", value=1)

    _apply_start_turn_effects(battle, next_player)
    if not battle["fighters"][next_player]["main"].is_alive():
        await end_pve_battle(callback, battle["user_id"], won=acting_player_num == 1)
        return

    if next_player == 2:
        await _process_enemy_turn(callback, battle)
        return

    await _update_battle_message(callback, battle)


async def _process_enemy_turn(callback: CallbackQuery, battle: dict):
    if battle.get("enemy_busy"):
        return

    battle["enemy_busy"] = True
    try:
        defender_alive = _auto_take_turn(battle, 2)
        if not defender_alive:
            await end_pve_battle(callback, battle["user_id"], won=False)
            return

        await _advance_turn(callback, battle, 2)
    except Exception:
        battle["log"].append("⚠️ Проклятие запуталось и пропустило ход.")
        await _advance_turn(callback, battle, 2)
    finally:
        battle["enemy_busy"] = False


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

@router.callback_query(F.data == "pve_arena")
async def pve_arena_callback(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        if not user.slot_1_card_id:
            await callback.message.edit_text(
                "⚔️ <b>Арена проклятий</b>\n\n"
                "❌ <b>У тебя нет экипированного персонажа!</b>\n\n"
                "Сначала выбери главную карту в профиле.",
                reply_markup=get_pve_menu(),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        difficulty = _resolve_user_pve_difficulty(user.difficulty)
        cfg = _get_pve_config(difficulty)
        hardcore_note = ""
        if (user.difficulty or "").strip().lower() == "hardcore":
            hardcore_note = "\n\nℹ️ В PvE «Хардкор» использует шкалу «Сложная»."

        await callback.message.edit_text(
            "👹 <b>Арена проклятий</b>\n\n"
            "Здесь одна арена, а сложность берётся из настроек профиля.\n\n"
            f"⚙️ Текущая сложность: <b>{cfg['label']}</b>\n"
            f"🎁 База наград: x{_format_multiplier(cfg['reward_mult'])} опыта, "
            f"x{_format_multiplier(cfg['drop_mult'])} к шансу карты"
            f"{hardcore_note}\n\n"
            "Чтобы изменить врагов и награды, поменяй сложность в профиле.",
            reply_markup=get_pve_menu(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.in_({"pve_start", "pve_easy", "pve_medium", "pve_hard", "pve_disaster"}))
async def pve_start_callback(callback: CallbackQuery):
    user_tg = callback.from_user.id

    existing_battle, existing_tg = _find_active_pve_battle(user_tg)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_tg)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        difficulty = _resolve_user_pve_difficulty(user.difficulty)

        if existing_battle:
            created_at = existing_battle.get("created_at")
            if created_at and datetime.utcnow() - created_at > timedelta(hours=6):
                if existing_tg is not None and existing_tg in active_pve_battles:
                    del active_pve_battles[existing_tg]
                existing_battle = None
            else:
                existing_battle["difficulty"] = difficulty
                existing_battle["restart_difficulty"] = difficulty
                if not existing_battle.get("in_battle") and not existing_battle.get("awaiting_continue"):
                    curse, enemy_state = await _prepare_enemy(
                        session,
                        existing_battle,
                        stage=int(existing_battle.get("stage", 1)),
                        player_level=user.level,
                    )
                    existing_battle["fighters"][2] = enemy_state
                    existing_battle["curse"] = curse
                _refresh_battle_rng(existing_battle)
                if existing_battle.get("in_battle"):
                    await _update_battle_message(callback, existing_battle)
                    await callback.answer("У тебя уже идёт бой.", show_alert=True)
                    return
                await _send_active_run_prompt(callback, existing_battle)
                await callback.answer("У тебя уже есть активный PvE забег.", show_alert=True)
                return

        if user.last_pve_battle_time:
            time_passed = datetime.utcnow() - user.last_pve_battle_time
            if time_passed < timedelta(seconds=PVE_COOLDOWN):
                remaining = max(0, PVE_COOLDOWN - int(time_passed.total_seconds()))
                await callback.answer(
                    f"Подожди {remaining} секунд перед следующим боем!",
                    show_alert=True,
                )
                return

        main_card = await _load_card(session, user.slot_1_card_id)
        weapon_card = await _load_card(session, user.slot_2_card_id)
        shikigami_card = await _load_card(session, user.slot_3_card_id)
        pact_card_1 = await _load_card(session, user.slot_4_card_id)
        pact_card_2 = await _load_card(session, user.slot_5_card_id)

        if not main_card:
            await callback.answer("У тебя нет экипированной карты!", show_alert=True)
            return

        main_card.heal()
        if weapon_card:
            weapon_card.heal()
        if shikigami_card:
            shikigami_card.heal()
        if pact_card_1:
            pact_card_1.heal()
        if pact_card_2:
            pact_card_2.heal()

        toolkit = await get_player_pvp_toolkit(session, user.id)
        clan_bonuses = await get_clan_bonuses(session, user.clan)
        player_techniques = await _get_user_technique_names(session, user.id)

        player_state = _build_fighter_state(
            main_card,
            weapon_card,
            shikigami_card,
            [pact_card_1, pact_card_2],
            toolkit,
            clan_bonuses=clan_bonuses,
            technique_names=player_techniques,
        )
        baseline = _player_baseline(main_card, shikigami_card)
        strategy_key = last_pve_strategy.get(user_tg, PVE_DEFAULT_STRATEGY)
        _apply_strategy_to_state(player_state, strategy_key)

        battle_id = f"pve_{user.id}_{datetime.utcnow().timestamp()}"
        battle = {
            "battle_id": battle_id,
            "user_id": user.id,
            "player_tg": user.telegram_id,
            "fighters": {1: player_state},
            "turn": 1,
            "current_player": 1,
            "domain_state": None,
            "pending_domain_response": None,
            "battlerdan_pending": None,
            "turn_flags": {
                1: {"attack_used": False, "rct_used": False, "mahoraga_used": False},
                2: {"attack_used": False, "rct_used": False, "mahoraga_used": False},
            },
            "log": [],
            "difficulty": difficulty,
            "baseline": baseline,
            "stage": 1,
            "awaiting_continue": False,
            "auto": False,
            "in_battle": False,
            "created_at": datetime.utcnow(),
            "restart_difficulty": difficulty,
            "strategy": strategy_key,
        }
        curse, enemy_state = await _prepare_enemy(session, battle, stage=1, player_level=user.level)
        battle["fighters"][2] = enemy_state
        battle["curse"] = curse
        _refresh_battle_rng(battle)

        active_pve_battles[user_tg] = battle
        last_pve_difficulty[user_tg] = difficulty

        await _send_active_run_prompt(callback, battle)

    await callback.answer()


@router.callback_query(F.data.startswith("pve_strategy_"))
async def pve_strategy_callback(callback: CallbackQuery):
    strategy_key = callback.data.split("_", 2)[2]
    if strategy_key not in PVE_STRATEGIES:
        await callback.answer("Неизвестная стратегия.", show_alert=True)
        return

    battle, _ = _find_active_pve_battle(callback.from_user.id)
    if not battle:
        last_pve_strategy[callback.from_user.id] = strategy_key
        await callback.answer("Стратегия сохранена. Запусти PvE на арене.", show_alert=True)
        return

    battle["strategy"] = strategy_key
    last_pve_strategy[callback.from_user.id] = strategy_key
    _apply_strategy_to_state(battle["fighters"][1], strategy_key)
    _refresh_battle_rng(battle)

    if battle.get("awaiting_continue"):
        await _send_active_run_prompt(callback, battle)
    else:
        await _send_pve_preview(callback, battle)
    await callback.answer()


@router.callback_query(F.data.startswith("pve_action_"))
async def pve_action_callback(callback: CallbackQuery):
    action = callback.data.split("pve_action_", 1)[1]
    user_id = callback.from_user.id
    battle = active_pve_battles.get(user_id)

    if not battle:
        await callback.answer("Бой не найден.", show_alert=True)
        return

    if battle["current_player"] != 1:
        await callback.answer("Сейчас не твой ход.", show_alert=True)
        return

    attacker_num = 1
    defender_num = 2
    attacker_user_id = battle["user_id"]

    pending_battlerdan = _pending_battlerdan_for(battle, attacker_num)
    if pending_battlerdan:
        if action.startswith("battlerdan_choose_"):
            try:
                choice = int(action.split("battlerdan_choose_", 1)[1])
            except ValueError:
                await callback.answer("Некорректный выбор.", show_alert=True)
                return
            pending_battlerdan["choice"] = choice
            pending_battlerdan["stage"] = "guess"
            battle["log"].append("🗣 Баттлердан выбрал аргумент. Противник пытается угадать...")
            await _advance_turn(callback, battle, attacker_num)
            await callback.answer()
            return

        if action.startswith("battlerdan_guess_"):
            try:
                guess = int(action.split("battlerdan_guess_", 1)[1])
            except ValueError:
                await callback.answer("Некорректный выбор.", show_alert=True)
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
        if flags.get("attack_used"):
            await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
            return
        defender_alive = _action_basic_attack(battle, attacker_num)
        flags["attack_used"] = True
        if not defender_alive:
            await end_pve_battle(callback, battle["user_id"], won=True)
            await callback.answer()
            return
        await _update_battle_message(callback, battle)
        await callback.answer()
        return

    if action.startswith("special_"):
        if flags.get("attack_used"):
            await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
            return
        key = action.split("special_", 1)[1]
        defender_alive, error = _action_special(battle, attacker_num, key)
        if error:
            await callback.answer(error, show_alert=True)
            return
        flags["attack_used"] = True
        if not defender_alive:
            await end_pve_battle(callback, battle["user_id"], won=True)
            await callback.answer()
            return
        await _update_battle_message(callback, battle)
        await callback.answer()
        return

    if action == "higuruma_sword":
        if flags.get("attack_used"):
            await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
            return
        defender_alive, error = _action_higuruma_sword(battle, attacker_num)
        if error:
            await callback.answer(error, show_alert=True)
            return
        flags["attack_used"] = True
        if not defender_alive:
            await end_pve_battle(callback, battle["user_id"], won=True)
            await callback.answer()
            return
        await _update_battle_message(callback, battle)
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
        await _update_battle_message(callback, battle)
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
        await _update_battle_message(callback, battle)
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
        await _update_battle_message(callback, battle)
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
            await _update_battle_message(callback, battle)
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

    if action == "skip_response":
        battle["log"].append("⏭ Ответ на домен пропущен.")
        battle["pending_domain_response"] = None
        await _advance_turn(callback, battle, attacker_num)
        await callback.answer()
        return

    await callback.answer("Неизвестное действие.", show_alert=True)


@router.callback_query(F.data == "pve_fight")
async def pve_fight_callback(callback: CallbackQuery):
    battle, _ = _find_active_pve_battle(callback.from_user.id)
    if not battle:
        await callback.answer("Активный бой не найден.", show_alert=True)
        return
    if battle.get("awaiting_continue"):
        await callback.answer("Сначала выбери «Сражаться дальше» или выйди.", show_alert=True)
        return
    if battle.get("in_battle"):
        await callback.answer("Бой уже идёт.", show_alert=True)
        return
    try:
        await _start_tactical_battle(callback, battle)
    except Exception:
        await callback.answer("Не удалось запустить бой. Попробуй ещё раз.", show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "pve_next")
async def pve_next_callback(callback: CallbackQuery):
    battle, _ = _find_active_pve_battle(callback.from_user.id)
    if not battle:
        await callback.answer("Активный бой не найден.", show_alert=True)
        return
    if not battle.get("awaiting_continue"):
        await callback.answer("Сейчас нельзя начать следующий бой.", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        battle["difficulty"] = _resolve_user_pve_difficulty(user.difficulty)
        battle["restart_difficulty"] = battle["difficulty"]
        battle["stage"] = int(battle.get("stage", 1)) + 1
        battle["domain_state"] = None
        battle["pending_domain_response"] = None
        battle["battlerdan_pending"] = None
        battle["log"] = []
        battle["auto"] = False
        battle["in_battle"] = False
        battle["turn_flags"] = {
            1: {"attack_used": False, "rct_used": False, "mahoraga_used": False},
            2: {"attack_used": False, "rct_used": False, "mahoraga_used": False},
        }

        curse, enemy_state = await _prepare_enemy(
            session,
            battle,
            stage=battle["stage"],
            player_level=user.level,
        )
        battle["fighters"][2] = enemy_state
        battle["curse"] = curse
        _refresh_battle_rng(battle)

    battle["awaiting_continue"] = False
    await _send_active_run_prompt(callback, battle)
    await callback.answer("Подготовлен следующий бой.")


@router.callback_query(F.data.in_({"pve_flee", "pve_leave"}))
async def pve_flee_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    battle, battle_tg = _find_active_pve_battle(user_id)
    if battle_tg is not None and battle_tg in active_pve_battles:
        del active_pve_battles[battle_tg]

    await callback.message.edit_text(
        "🏃 <b>Ты покинул арену.</b>\n\n"
        "Возвращайся, когда будешь готов продолжить.",
        reply_markup=get_pve_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "pve_reset")
async def pve_reset_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    battle, battle_tg = _find_active_pve_battle(user_id)
    if not battle or battle_tg is None:
        await callback.answer("Активный бой не найден.", show_alert=True)
        return

    del active_pve_battles[battle_tg]

    callback.data = "pve_start"
    await pve_start_callback(callback)


@router.callback_query(F.data == "pve_heal")
async def pve_heal_callback(callback: CallbackQuery):
    battle, _ = _find_active_pve_battle(callback.from_user.id)
    if not battle:
        await callback.answer("Активный бой не найден.", show_alert=True)
        return

    ok, error = _action_reverse_ct(battle, 1)
    if not ok:
        await callback.answer(error, show_alert=True)
        return

    await _send_active_run_prompt(callback, battle)
    await callback.answer("HP восстановлено.")


async def end_pve_battle(callback: CallbackQuery, user_id: int, won: bool):
    battle, battle_tg = _find_active_pve_battle(user_id)
    if not battle:
        return
    battle["in_battle"] = False
    rng = _battle_rng(battle)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == battle["user_id"])
        )
        user = result.scalar_one_or_none()

        if user:
            user.last_pve_battle_time = datetime.utcnow()
            user.total_battles += 1
            await add_daily_quest_progress(session, user.id, "pve_battles", amount=1)

            difficulty = _normalize_pve_difficulty(battle.get("difficulty"))
            cfg = _get_pve_config(difficulty)
            curse = battle["curse"]
            stage = int(battle.get("stage", 1))
            reward_mult = _reward_multiplier(cfg, stage)
            drop_mult = _drop_multiplier(cfg, stage)

            exp_gained = 0
            points_gained = 0
            actual_exp = 0
            leveled_up = False
            unlocked_from_level = []
            card_dropped_name = None

            if won:
                user.pve_wins += 1
                await add_daily_quest_progress(session, user.id, "pve_wins", amount=1)
                if (user.difficulty or "").strip().lower() == "hardcore":
                    await add_daily_quest_progress(session, user.id, "disaster_wins", amount=1)

                base_exp = curse.exp_reward if curse else 20
                exp_gained = int(base_exp * cfg["reward_mult"] * reward_mult)
                leveled_up, actual_exp, unlocked_from_level = await apply_experience_with_pvp_rolls(
                    session, user, exp_gained
                )

                drop_chance = (curse.card_drop_chance if curse else 1.0) * cfg["drop_mult"] * drop_mult
                if rng.random() * 100 < drop_chance:
                    from utils.card_rewards import grant_random_card

                    dropped_card = await grant_random_card(session, user.id, only_characters=False, level=1)
                    if dropped_card and dropped_card.card_template:
                        card_dropped_name = dropped_card.card_template.name

                if user.clan:
                    await add_clan_exp(session, user.clan, CLAN_EXP_PER_PVE_WIN)
                    await add_clan_daily_progress(session, user.clan, pve_win=1, battle=1)
            else:
                user.pve_losses += 1
                if user.clan:
                    await add_clan_daily_progress(session, user.clan, battle=1)

            battle_record = Battle(
                battle_type="pve",
                player1_id=user.id,
                curse_id=curse.id if curse else None,
                curse_name=curse.name if curse else "Проклятие",
                winner_id=user.id if won else None,
                battle_log="\\n".join(battle["log"]),
                exp_gained=exp_gained if won else 0,
                points_gained=points_gained if won else 0,
            )
            session.add(battle_record)
            await session.flush()

            if won:
                await check_achievements(user.id, "pve_wins", value=1, session=session)
                if (user.difficulty or "").strip().lower() == "hardcore":
                    await check_achievements(user.id, "disaster_wins", value=1, session=session)

            await check_achievements(user.id, "level", value=user.level, absolute=True, session=session)
            if user.hardcore_mode:
                await check_achievements(user.id, "hardcore_level", value=user.level, absolute=True, session=session)

            result = await session.execute(
                select(func.count(UserTechnique.id)).where(UserTechnique.user_id == user.id)
            )
            technique_count = int(result.scalar() or 0)
            await check_achievements(
                user.id,
                "techniques_obtained",
                value=technique_count,
                absolute=True,
                session=session,
            )

            result = await session.execute(
                select(func.count(UserCard.id)).where(UserCard.user_id == user.id)
            )
            card_count = int(result.scalar() or 0)
            await check_achievements(
                user.id,
                "cards_collected",
                value=card_count,
                absolute=True,
                session=session,
            )

            await session.commit()

            player_name = _fighter_name(battle["fighters"].get(1, {}))
            enemy_name = _fighter_name(battle["fighters"].get(2, {}))

            if won:
                result_text = (
                    f"🏆 <b>Победа!</b>\n"
                    f"📍 Этап: <b>{stage}</b>\n"
                    f"👑 Твоя карта: <b>{player_name}</b>\n"
                    f"👹 Проклятие: <b>{enemy_name}</b>\n\n"
                    f"⭐ Опыт: +{actual_exp}\n"
                )

                if leveled_up:
                    result_text += f"🎉 <b>Новый уровень! Теперь ты {user.level} уровень!</b>\n"

                if unlocked_from_level:
                    unlocked_names = ", ".join(t.name for t in unlocked_from_level)
                    result_text += f"🆕 <b>Новые техники:</b> {unlocked_names}\n"

                if card_dropped_name:
                    result_text += f"🎁 <b>Выпала новая карта:</b> {card_dropped_name}\n"

                result_text += "\n💪 Так держать!"
            else:
                result_text = (
                    f"💀 <b>Поражение...</b>\n"
                    f"📍 Этап: <b>{stage}</b>\n"
                    f"👑 Твоя карта: <b>{player_name}</b>\n"
                    f"👹 Победившее проклятие: <b>{enemy_name}</b>\n\n"
                    f"😓 Не сдавайся! Тренируйся и возвращайся сильнее."
                )

            if won:
                battle["awaiting_continue"] = True
            else:
                battle["awaiting_continue"] = False

            try:
                await callback.message.edit_text(
                    result_text,
                    reply_markup=get_pve_result_keyboard(won, can_continue=won),
                    parse_mode="HTML",
                )
            except Exception:
                await callback.bot.send_message(
                    callback.from_user.id,
                    result_text,
                    reply_markup=get_pve_result_keyboard(won, can_continue=won),
                    parse_mode="HTML",
                )

    if not won and battle_tg is not None and battle_tg in active_pve_battles:
        del active_pve_battles[battle_tg]


@router.callback_query(F.data == "pve_menu")
async def pve_menu_callback(callback: CallbackQuery):
    await pve_arena_callback(callback)



