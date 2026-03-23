
import random
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from models import async_session, User, UserCard, Battle, Technique, UserTechnique, Title
from keyboards.coop_pvp import (
    get_coop_menu_keyboard,
    get_coop_invite_input_keyboard,
    get_coop_invite_keyboard,
    get_coop_waiting_keyboard,
    get_coop_battle_keyboard,
)
from utils.daily_quest_progress import add_daily_quest_progress
from utils.pvp_progression import apply_experience_with_pvp_rolls, get_player_pvp_toolkit
from utils.weapon_effects import get_weapon_effect
from utils.pact_effects import get_pact_effect
from utils.black_flash import get_black_flash_chance
from utils.card_rewards import is_weapon_template
from utils.character_content import get_character_profile as get_shared_character_profile
from utils.clan_progression import get_clan_bonuses
from handlers.achievements import check_achievements
from config import (
    DOMAIN_DOT_PER_POINT,
    DOMAIN_DAMAGE_BONUS_PER_POINT,
    RCT_HEAL_BONUS_PER_POINT,
    PVP_COOLDOWN,
)

router = Router()

# Team/queue state
coop_teams = {}  # leader_tg -> {leader_tg, members: [tg], created_at}
coop_team_by_user = {}  # telegram_id -> leader_tg
coop_team_invites = {}  # (leader_tg, target_tg) -> created_at
coop_team_invite_input = {}  # leader_tg -> created_at
coop_matchmaking_queue = {}  # leader_tg -> {joined_at}

# Active battles
active_coop_battles = {}  # telegram_id -> battle dict

TEAM_MAX_SIZE = 3
INVITE_TIMEOUT = timedelta(minutes=10)
QUEUE_TIMEOUT = timedelta(minutes=5)

DEFAULT_DOMAIN_DURATION = 3
DEFAULT_SIMPLE_DOMAIN_DURATION = 2
MAHORAGA_ADAPT_COST = 2000
DOMAIN_UPKEEP_PER_TURN = 500
PVP_COOLDOWN_SECONDS = PVP_COOLDOWN

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
        "domain_name": "Гробница Зла",
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
            {"key": "battle_blue", "name": "Синяя правда", "icon": "🔵", "ce_cost": 700, "multiplier": 1.25, "flat": 120},
            {"key": "battle_red", "name": "Красная правда", "icon": "🔴", "ce_cost": 1000, "multiplier": 1.55, "flat": 220},
            {"key": "battle_bombs", "name": "Маленькие бомбочки", "icon": "🤏💣", "ce_cost": 0, "multiplier": 1, "flat": 40},
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
    {
        "tokens": ["дагон", "dagon"],
        "domain_name": "Горизонт плена скандхи",
        "domain_dot_pct": 0.17,
        "domain_damage_bonus": 0.26,
        "domain_effect": "dot",
        "specials": [
            {"key": "tidal", "name": "Приливный обвал", "icon": "🌊", "ce_cost": 1700, "multiplier": 1.65, "flat": 250},
            {"key": "swarm", "name": "Стая глубин", "icon": "🦑", "ce_cost": 2600, "multiplier": 2.05, "flat": 360},
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
            {"key": "roots", "name": "Корни-ловушки", "icon": "🌿", "ce_cost": 1100, "multiplier": 1.45, "flat": 180},
            {"key": "blossom", "name": "Цветочный обвал", "icon": "🌸", "ce_cost": 1800, "multiplier": 1.75, "flat": 260},
        ],
    },
    {
        "tokens": ["дзёго", "джого", "jogo"],
        "domain_name": "Пылающий кратер",
        "domain_dot_pct": 0.16,
        "domain_damage_bonus": 0.28,
        "domain_effect": "gojo_crit",
        "specials": [
            {"key": "ember", "name": "Вулканический залп", "icon": "🔥", "ce_cost": 1400, "multiplier": 1.55, "flat": 220},
            {"key": "eruption", "name": "Извержение", "icon": "🌋", "ce_cost": 2400, "multiplier": 2.0, "flat": 340},
        ],
    },
    {
        "tokens": ["махито", "mahito"],
        "domain_name": "Мгновенное воплощение совершенства",
        "domain_dot_pct": 0.18,
        "domain_damage_bonus": 0.31,
        "domain_effect": "soul_dot",
        "specials": [
            {"key": "idle_touch", "name": "Преобразование души", "icon": "🫳", "ce_cost": 1900, "multiplier": 1.8, "flat": 290},
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
            {"key": "uzumaki", "name": "Узумаки", "icon": "🌀", "ce_cost": 3600, "multiplier": 2.45, "flat": 520},
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
            {"key": "frost_lance", "name": "Морозное копьё", "icon": "❄️", "ce_cost": 1100, "multiplier": 1.55, "flat": 220},
            {"key": "icefall", "name": "Ледопад", "icon": "🧊", "ce_cost": 2200, "multiplier": 1.85, "flat": 320},
        ],
    },
    {
        "tokens": ["кашимо", "хадзимэ", "kashimo", "hajime"],
        "domain_name": "Поле грома",
        "domain_dot_pct": 0.13,
        "domain_damage_bonus": 0.24,
        "domain_effect": "soul_dot",
        "specials": [
            {"key": "lightning_bolt", "name": "Громовой разряд", "icon": "⚡", "ce_cost": 1000, "multiplier": 1.6, "flat": 220},
            {"key": "amber_beast", "name": "Мифический зверь: Янтарь", "icon": "🟨", "ce_cost": 3600, "multiplier": 2.35, "flat": 480},
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

TECH_BLOOD = "Кровавая Магия"
TECH_SUKUNA_CURSE = "Проклятие Сукуны"
TECH_INFINITY = "Бесконечность"
TECH_SIX_EYES = "Шесть Глаз"


# -----------------------------
# Team helpers
# -----------------------------

def _display_name(user: User) -> str:
    return user.first_name or (f"@{user.username}" if user.username else f"Игрок #{user.id}")


def _get_team_for_user(telegram_id: int):
    leader_tg = coop_team_by_user.get(telegram_id)
    if not leader_tg:
        return None
    return coop_teams.get(leader_tg)


def _is_leader(team: dict, telegram_id: int) -> bool:
    return team and team.get("leader_tg") == telegram_id


def _team_full(team: dict) -> bool:
    return len(team.get("members", [])) >= TEAM_MAX_SIZE


def _remove_from_queue(leader_tg: int):
    coop_matchmaking_queue.pop(leader_tg, None)


def _cleanup_queue():
    now = datetime.utcnow()
    stale = [
        leader_tg
        for leader_tg, payload in coop_matchmaking_queue.items()
        if now - payload.get("joined_at", now) > QUEUE_TIMEOUT
    ]
    for leader_tg in stale:
        coop_matchmaking_queue.pop(leader_tg, None)


def _has_active_any_battle(telegram_id: int) -> bool:
    if telegram_id in active_coop_battles:
        return True
    try:
        from handlers.pvp import active_pvp_battles
        return telegram_id in active_pvp_battles
    except Exception:
        return False


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


def _get_pvp_cooldown_seconds_left(user: User) -> int:
    if not user.last_battle_time:
        return 0
    elapsed = (datetime.utcnow() - user.last_battle_time).total_seconds()
    remaining = int(PVP_COOLDOWN_SECONDS - elapsed)
    return max(0, remaining)


async def _render_coop_menu(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        team = _get_team_for_user(user.telegram_id)
        has_team = bool(team)
        is_leader = _is_leader(team, user.telegram_id) if team else False
        is_queued = bool(team and team.get("leader_tg") in coop_matchmaking_queue)

        if not has_team:
            text = (
                "🤝 <b>Кооператив PvP</b>\n\n"
                "У тебя нет команды. Создай её и пригласи до двух игроков."
            )
        else:
            member_ids = team.get("members", [])
            result = await session.execute(select(User).where(User.telegram_id.in_(member_ids)))
            members = result.scalars().all()
            members_map = {u.telegram_id: u for u in members}
            lines = []
            for idx, tg in enumerate(member_ids, 1):
                member = members_map.get(tg)
                label = _display_name(member) if member else f"Игрок {tg}"
                if tg == team.get("leader_tg"):
                    label += " (лидер)"
                lines.append(f"{idx}. {label}")

            queue_text = "\n\n🔎 Команда в очереди поиска." if is_queued else ""
            text = (
                "🤝 <b>Кооператив PvP</b>\n\n"
                "<b>Твоя команда:</b>\n" + "\n".join(lines) + queue_text
            )

        try:
            await callback.message.edit_text(
                text,
                reply_markup=get_coop_menu_keyboard(has_team, is_leader, is_queued),
                parse_mode="HTML",
            )
        except Exception:
            await callback.bot.send_message(
                callback.from_user.id,
                text,
                reply_markup=get_coop_menu_keyboard(has_team, is_leader, is_queued),
                parse_mode="HTML",
            )
    await callback.answer()


# -----------------------------
# Coop menu handlers
# -----------------------------

@router.callback_query(F.data == "pvp_coop_menu")
async def coop_menu_callback(callback: CallbackQuery):
    await _render_coop_menu(callback)


@router.callback_query(F.data == "coop_create_team")
async def coop_create_team(callback: CallbackQuery):
    if _get_team_for_user(callback.from_user.id):
        await callback.answer("Ты уже в команде.", show_alert=True)
        await _render_coop_menu(callback)
        return

    team = {
        "leader_tg": callback.from_user.id,
        "members": [callback.from_user.id],
        "created_at": datetime.utcnow(),
    }
    coop_teams[callback.from_user.id] = team
    coop_team_by_user[callback.from_user.id] = callback.from_user.id

    await _render_coop_menu(callback)


@router.callback_query(F.data == "coop_invite")
async def coop_invite_callback(callback: CallbackQuery):
    team = _get_team_for_user(callback.from_user.id)
    if not team:
        await callback.answer("Сначала создай команду.", show_alert=True)
        return
    if not _is_leader(team, callback.from_user.id):
        await callback.answer("Приглашать может только лидер.", show_alert=True)
        return
    if _team_full(team):
        await callback.answer("Команда уже заполнена (3 человека).", show_alert=True)
        return

    coop_team_invite_input[callback.from_user.id] = datetime.utcnow()
    await callback.message.edit_text(
        "➕ <b>Приглашение в команду</b>\n\n"
        "Отправь @username или telegram_id игрока.\n"
        "Пример: <code>@player</code> или <code>123456789</code>.",
        reply_markup=get_coop_invite_input_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "coop_cancel_invite_input")
async def coop_cancel_invite_input(callback: CallbackQuery):
    coop_team_invite_input.pop(callback.from_user.id, None)
    await _render_coop_menu(callback)


@router.message(F.text, ~F.text.startswith("/"), lambda message: message.from_user.id in coop_team_invite_input)
async def coop_invite_input_handler(message: Message):
    created_at = coop_team_invite_input.get(message.from_user.id)
    if not created_at:
        return

    coop_team_invite_input.pop(message.from_user.id, None)

    async with async_session() as session:
        leader = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        if not leader:
            await message.answer("Сначала используй /start")
            return

        team = _get_team_for_user(leader.telegram_id)
        if not team or not _is_leader(team, leader.telegram_id):
            await message.answer("Команда не найдена или ты не лидер.")
            return

        if _team_full(team):
            await message.answer("Команда уже заполнена (3 человека).")
            return

        target = await _find_user_by_target(session, message.text.strip())
        if not target:
            await message.answer("Игрок не найден. Он должен запустить бота через /start.")
            return

        if target.telegram_id == leader.telegram_id:
            await message.answer("Нельзя пригласить самого себя.")
            return

        if _get_team_for_user(target.telegram_id):
            await message.answer("Этот игрок уже в другой команде.")
            return

        if _has_active_any_battle(target.telegram_id):
            await message.answer("Этот игрок уже участвует в бою.")
            return

        key = (leader.telegram_id, target.telegram_id)
        coop_team_invites[key] = datetime.utcnow()

        try:
            await message.bot.send_message(
                target.telegram_id,
                "🤝 <b>Приглашение в кооп-команду</b>\n\n"
                f"{_display_name(leader)} приглашает тебя в команду.\n"
                "Нажми «Принять», чтобы вступить.",
                reply_markup=get_coop_invite_keyboard(leader.telegram_id),
                parse_mode="HTML",
            )
        except Exception:
            coop_team_invites.pop(key, None)
            await message.answer("Не удалось отправить приглашение игроку.")
            return

        await message.answer(f"Приглашение отправлено игроку {_display_name(target)}.")


@router.callback_query(F.data.startswith("coop_accept_"))
async def coop_accept_callback(callback: CallbackQuery):
    leader_tg = int(callback.data.split("_")[2])
    key = (leader_tg, callback.from_user.id)
    created_at = coop_team_invites.get(key)

    if not created_at:
        await callback.answer("Приглашение не найдено или уже неактуально.", show_alert=True)
        return

    if datetime.utcnow() - created_at > INVITE_TIMEOUT:
        coop_team_invites.pop(key, None)
        await callback.answer("Приглашение истекло.", show_alert=True)
        return

    team = coop_teams.get(leader_tg)
    if not team:
        coop_team_invites.pop(key, None)
        await callback.answer("Команда больше не существует.", show_alert=True)
        return

    if _team_full(team):
        coop_team_invites.pop(key, None)
        await callback.answer("Команда уже заполнена.", show_alert=True)
        return

    if _get_team_for_user(callback.from_user.id):
        coop_team_invites.pop(key, None)
        await callback.answer("Ты уже в другой команде.", show_alert=True)
        return

    team["members"].append(callback.from_user.id)
    coop_team_by_user[callback.from_user.id] = leader_tg
    coop_team_invites.pop(key, None)

    try:
        await callback.bot.send_message(leader_tg, f"✅ Игрок {callback.from_user.id} вступил в команду.")
    except Exception:
        pass

    await callback.answer("Ты вступил в команду.", show_alert=True)


@router.callback_query(F.data.startswith("coop_decline_"))
async def coop_decline_callback(callback: CallbackQuery):
    leader_tg = int(callback.data.split("_")[2])
    key = (leader_tg, callback.from_user.id)
    existed = coop_team_invites.pop(key, None)

    if existed:
        try:
            await callback.bot.send_message(leader_tg, "❌ Приглашение в команду было отклонено.")
        except Exception:
            pass

    await callback.answer("Приглашение отклонено.", show_alert=True)


@router.callback_query(F.data == "coop_leave_team")
async def coop_leave_team(callback: CallbackQuery):
    team = _get_team_for_user(callback.from_user.id)
    if not team:
        await callback.answer("Ты не в команде.", show_alert=True)
        return

    leader_tg = team.get("leader_tg")
    if callback.from_user.id == leader_tg:
        # Disband team
        for member_tg in list(team.get("members", [])):
            coop_team_by_user.pop(member_tg, None)
            if member_tg != leader_tg:
                try:
                    await callback.bot.send_message(member_tg, "Команда распущена лидером.")
                except Exception:
                    pass
        coop_teams.pop(leader_tg, None)
        _remove_from_queue(leader_tg)
    else:
        team["members"] = [tg for tg in team.get("members", []) if tg != callback.from_user.id]
        coop_team_by_user.pop(callback.from_user.id, None)

    await _render_coop_menu(callback)


@router.callback_query(F.data == "coop_queue")
async def coop_queue_callback(callback: CallbackQuery):
    team = _get_team_for_user(callback.from_user.id)
    if not team:
        await callback.answer("Сначала создай команду.", show_alert=True)
        return
    if not _is_leader(team, callback.from_user.id):
        await callback.answer("Встать в очередь может только лидер.", show_alert=True)
        return

    if team.get("leader_tg") in coop_matchmaking_queue:
        await callback.answer("Команда уже в очереди.", show_alert=True)
        await _render_coop_menu(callback)
        return

    async with async_session() as session:
        member_ids = team.get("members", [])
        result = await session.execute(select(User).where(User.telegram_id.in_(member_ids)))
        members = result.scalars().all()

        if any(_has_active_any_battle(member.telegram_id) for member in members):
            await callback.answer("Один из игроков уже участвует в бою.", show_alert=True)
            return

        for member in members:
            if not member.slot_1_card_id:
                await callback.answer("У одного из игроков не экипирована главная карта.", show_alert=True)
                return
            if _get_pvp_cooldown_seconds_left(member) > 0:
                await callback.answer("У одного из игроков ещё не прошёл PvP-кулдаун.", show_alert=True)
                return

    coop_matchmaking_queue[team["leader_tg"]] = {"joined_at": datetime.utcnow()}
    _cleanup_queue()

    # Try to match with another team
    opponent_leader = None
    for leader_tg, payload in sorted(
        coop_matchmaking_queue.items(),
        key=lambda item: item[1].get("joined_at", datetime.utcnow()),
    ):
        if leader_tg != team["leader_tg"]:
            opponent_leader = leader_tg
            break

    if opponent_leader:
        opponent_team = coop_teams.get(opponent_leader)
        if opponent_team:
            coop_matchmaking_queue.pop(team["leader_tg"], None)
            coop_matchmaking_queue.pop(opponent_leader, None)
            started = await start_coop_battle(callback, team, opponent_team)
            if started:
                await callback.answer("Команда соперников найдена! Бой начался.")
                return

    try:
        await callback.message.edit_text(
            "🤝 <b>Кооператив PvP</b>\n\nКоманда в очереди поиска...",
            reply_markup=get_coop_waiting_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.bot.send_message(
            callback.from_user.id,
            "🤝 <b>Кооператив PvP</b>\n\nКоманда в очереди поиска...",
            reply_markup=get_coop_waiting_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "coop_cancel_queue")
async def coop_cancel_queue_callback(callback: CallbackQuery):
    team = _get_team_for_user(callback.from_user.id)
    if team:
        _remove_from_queue(team.get("leader_tg"))
    await _render_coop_menu(callback)

# -----------------------------
# Battle engine
# -----------------------------

def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _name_has_tokens(name: str, tokens: tuple[str, ...]) -> bool:
    normalized = _normalize_name(name)
    return any(token in normalized for token in tokens)


def _is_gojo_name(name: str) -> bool:
    normalized = _normalize_name(name)
    return normalized in GOJO_TOKENS


async def _get_user_technique_names(session, user_id: int) -> set[str]:
    result = await session.execute(
        select(Technique.name)
        .join(UserTechnique, UserTechnique.technique_id == Technique.id)
        .where(UserTechnique.user_id == user_id)
    )
    return {row[0] for row in result if row and row[0]}


def _get_character_profile(card_name: str) -> dict:
    return get_shared_character_profile(card_name)


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
    return battle["player_map"].get(tg_id)


def _get_turn_flags(battle: dict, player_num: int) -> dict:
    turn_flags = battle.setdefault("turn_flags", {})
    if player_num not in turn_flags:
        turn_flags[player_num] = {"attack_used": False, "rct_used": False, "mahoraga_used": False}
    return turn_flags[player_num]


def _reset_turn_flags(battle: dict, player_num: int):
    battle.setdefault("turn_flags", {})[player_num] = {"attack_used": False, "rct_used": False, "mahoraga_used": False}


def _pending_response_for(battle: dict, player_num: int):
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
        flags = _get_turn_flags(battle, player_num)
        can_domain = fighter_state.get("has_domain", False)
        can_simple = fighter_state.get("has_simple_domain", False) and fighter_state.get("simple_domain_turns", 0) == 0
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
        battle["log"].append(f"🌀 Махорага адаптируется к атаке «{label}»: -50% урона.")
    elif current < 1.0:
        heal = int(dealt_damage)
        main.hp = min(main.max_hp, main.hp + heal)
        adapt_map[attack_key] = 1.0
        battle["log"].append(f"🌀 Махорага полностью адаптировался к «{label}» (100%).")
    else:
        heal = int(dealt_damage)
        main.hp = min(main.max_hp, main.hp + heal)
        battle["log"].append(f"🌀 Махорага блокирует «{label}» (100%).")


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

    guaranteed_hit = _is_guaranteed_hit(battle, attacker_num, defender_num)
    infinity_chance = float(defender_state.get("infinity_chance", 0.0) or 0.0)
    if infinity_chance > 0 and not ignore_infinity and not guaranteed_hit:
        battle["log"].append("∞ Бесконечность блокирует атаку.")
        return 0, False, 0.0, False

    if can_dodge and not guaranteed_hit:
        chance = _dodge_chance(battle, attacker_state, defender_state, attacker_num, defender_num)
        if chance > 0 and random.random() < chance:
            return 0, True, chance, False

    attacker_bonus = _domain_attack_bonus(battle, attacker_num, defender_num)
    final_raw = max(1, int(raw_damage * attacker_bonus))
    defender = defender_state["main"]
    before_hp = int(defender.hp)
    if ignore_defense:
        dealt = defender.take_true_damage(final_raw)
    else:
        dealt = defender.take_damage(final_raw)
    if defender.hp <= 0 and defender_state.get("survive_lethal_available", False):
        defender.hp = 1
        defender_state["survive_lethal_available"] = False
        dealt = max(0, before_hp - 1)
        battle["log"].append(f"📜 Пакт выживания срабатывает: {defender.card_template.name} остаётся на 1 HP.")
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
    shikigami = state.get("shikigami")
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


def _format_fighter_line(state: dict, name: str) -> str:
    simple_left = state.get("simple_domain_turns", 0)
    simple_text = f" | 🛡 {simple_left}х" if simple_left > 0 else ""
    title = state.get("title")
    title_line = f"👑 {title.icon} {title.name}\n" if title else ""
    return (
        f"{name}\n"
        f"{title_line}"
        f"❤️ {state['main'].hp}/{state['main'].max_hp} | "
        f"💧 {state['ce']}/{state['max_ce']}{simple_text}"
    )


def _battle_view_text(battle: dict, viewer_tg: int) -> str:
    viewer_num = _player_num_by_tg(battle, viewer_tg)
    viewer_team = battle["player_team"][viewer_num]
    enemy_team = 2 if viewer_team == 1 else 1

    team_lines = []
    for pnum in battle["teams"][viewer_team]:
        info = battle["player_info"][pnum]
        state = battle["fighters"][pnum]
        team_lines.append(_format_fighter_line(state, f"🃏 {info['name']}"))

    enemy_lines = []
    for pnum in battle["teams"][enemy_team]:
        info = battle["player_info"][pnum]
        state = battle["fighters"][pnum]
        enemy_lines.append(_format_fighter_line(state, f"🃏 {info['name']}"))

    text = (
        f"🤝 <b>Кооп PvP — ход {battle['turn']}</b>\n\n"
        f"<b>Твоя команда:</b>\n" + "\n\n".join(team_lines) + "\n\n"
        f"<b>Команда противника:</b>\n" + "\n\n".join(enemy_lines)
    )

    domain = battle.get("domain_state")
    if domain:
        owner_info = battle["player_info"][domain["owner"]]
        target_info = battle["player_info"][domain["target"]]
        text += (
            f"\n\n🏯 <b>Активная территория:</b> {domain['name']}\n"
            f"Владелец: {owner_info['name']} | Цель: {target_info['name']} | Осталось: {domain['turns_left']}х"
        )

    pending = _pending_response_for(battle, viewer_num)
    if pending:
        text += "\n\n⚠️ <b>Ответ на домен:</b> выбери Расширение, Простую территорию или Махорагу."

    pending_battlerdan = _pending_battlerdan_for(battle, viewer_num)
    if pending_battlerdan:
        if pending_battlerdan.get("stage") == "choose":
            text += "\n\n🗣 <b>Дебаты:</b> выбери аргумент."
        elif pending_battlerdan.get("stage") == "guess":
            text += "\n\n❓ <b>Дебаты:</b> угадай аргумент."

    if battle["log"]:
        last_logs = battle["log"][-5:]
        text += "\n\n<b>Последние события:</b>\n" + "\n".join(f"• {line}" for line in last_logs)

    current_info = battle["player_info"].get(battle["current_player"], {})
    if battle["current_player"] == viewer_num:
        text += "\n\n⚡ <b>Твой ход!</b>"
    else:
        text += f"\n\n⏳ <b>Ход игрока:</b> {current_info.get('name', 'противника')}"

    return text


async def _edit_or_send_battle_message(callback: CallbackQuery, telegram_id: int, battle: dict):
    viewer_num = _player_num_by_tg(battle, telegram_id)
    is_your_turn = battle["current_player"] == viewer_num
    text = _battle_view_text(battle, telegram_id)
    action_state = _get_action_state(battle, viewer_num) if is_your_turn else None
    keyboard = get_coop_battle_keyboard(
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
    for info in battle["player_info"].values():
        await _edit_or_send_battle_message(callback, info["tg"], battle)


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

    if domain and domain.get("target") == player_num:
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
            base_raw = int(state["main"].max_hp * domain["dot_pct"]) + int(owner_state["main"].attack * 0.25)
            effect = domain.get("effect", "dot")
            if effect == "gojo_crit":
                raw = int(base_raw * 2.0)
                raw = int(raw * (1 + domain.get("damage_bonus", 0.0)))
                dealt = state["main"].take_damage(max(1, raw))
                battle["log"].append(f"🏯 {domain['name']} наносит критический урон: {dealt}.")
            elif effect == "soul_dot":
                raw = int(base_raw * (1 + domain.get("damage_bonus", 0.0)))
                dealt = state["main"].take_true_damage(max(1, raw))
                battle["log"].append(f"🏯 {domain['name']} бьёт по душе: {dealt} урона.")
            else:
                raw = int(base_raw * (1 + domain.get("damage_bonus", 0.0)))
                dealt = state["main"].take_damage(max(1, raw))
                battle["log"].append(f"🏯 {domain['name']} наносит {dealt} урона.")
            domain["turns_left"] -= 1
            if domain["turns_left"] <= 0:
                battle["log"].append("🌫 Эффект территории рассеялся.")
                battle["domain_state"] = None

    if simple_active:
        state["simple_domain_turns"] -= 1
        if state["simple_domain_turns"] == 0:
            battle["log"].append("🛡 Простая территория закончилась.")


def _team_alive(battle: dict, team_id: int) -> bool:
    return any(battle["fighters"][pnum]["main"].is_alive() for pnum in battle["teams"][team_id])


def _next_alive_player(battle: dict, start_index: int):
    order = battle["turn_order"]
    for offset in range(1, len(order) + 1):
        idx = (start_index + offset) % len(order)
        pnum = order[idx]
        if battle["fighters"][pnum]["main"].is_alive():
            return idx, pnum
    return None, None


def _select_target_player(battle: dict, attacker_num: int) -> int | None:
    attacker_team = battle["player_team"][attacker_num]
    enemy_team = 2 if attacker_team == 1 else 1
    candidates = [p for p in battle["teams"][enemy_team] if battle["fighters"][p]["main"].is_alive()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: battle["fighters"][p]["main"].hp)
    return candidates[0]


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


def _action_basic_attack(battle: dict, attacker_num: int, defender_num: int):
    attacker = battle["fighters"][attacker_num]
    defender = battle["fighters"][defender_num]

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
        can_dodge=can_dodge,
    )
    if blocked:
        battle["log"].append("🦆 Уточки блокируют удар.")
        return defender["main"].is_alive()
    if dodged:
        dodge_pct = int(dodge_chance * 100)
        target_name = battle["player_info"][defender_num]["name"]
        battle["log"].append(f"💨 {target_name} уклонился от атаки (шанс {dodge_pct}%).")
        return defender["main"].is_alive()

    if black_flash:
        restore_amount = min(4000, attacker["max_ce"] - attacker["ce"])
        attacker["ce"] += restore_amount
        battle["log"].append(f"⚫ Чёрная молния! Урон: {dealt}, восстановлено CE: {restore_amount}.")
    else:
        battle["log"].append(f"👊 Атака наносит {dealt} урона.")

    return defender["main"].is_alive()


def _action_special(battle: dict, attacker_num: int, defender_num: int, key: str):
    attacker = battle["fighters"][attacker_num]
    defender = battle["fighters"][defender_num]

    if attacker.get("simple_domain_turns", 0) > 0:
        return False, "Во время простой территории нельзя использовать спецтехники."

    special = next((sp for sp in attacker["specials"] if sp["key"] == key), None)
    if not special:
        return False, "Эта техника недоступна для твоей карты."

    if not _spend_ce(attacker, special["ce_cost"]):
        return False, "Недостаточно CE для этой техники."

    if special.get("effect") == "duck_guard":
        block_hits = max(1, int(special.get("block_hits", 1)))
        attacker["block_next_hits"] = max(attacker.get("block_next_hits", 0), block_hits)
        battle["log"].append("🦆 Уточки перекрывают следующий удар врага.")
        return defender["main"].is_alive(), None

    raw = int(_get_base_damage(attacker) * special["multiplier"] + special.get("flat", 0))
    raw, pact_mult = _apply_pact_attack_bonus(attacker, raw)

    weapon_effects = _collect_weapon_effects(
        attacker.get("weapon"), attacker.get("weapon2")
    )
    ignore_defense = bool(weapon_effects["ignore_defense"])
    ignore_infinity = bool(weapon_effects["ignore_infinity"])
    can_dodge = not bool(weapon_effects["ignore_dodge"])

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
    )
    if blocked:
        battle["log"].append("🦆 Уточки блокируют удар.")
        return defender["main"].is_alive(), None
    if dodged:
        dodge_pct = int(dodge_chance * 100)
        target_name = battle["player_info"][defender_num]["name"]
        battle["log"].append(
            f"💨 {target_name} уклонился от техники «{special['name']}» (шанс {dodge_pct}%)."
        )
        return defender["main"].is_alive(), None

    battle["log"].append(
        f"{special['icon']} {special['name']} наносит {dealt} урона (-{special['ce_cost']} CE)."
    )
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


def _action_domain(battle: dict, attacker_num: int, defender_num: int):
    attacker = battle["fighters"][attacker_num]
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
        if domain and domain.get("owner") != attacker_num:
            battle_defender_num = domain["owner"]
            defender = battle["fighters"][battle_defender_num]
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

    if domain and domain["owner"] != attacker_num:
        battle_defender_num = domain["owner"]
        defender = battle["fighters"][battle_defender_num]
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


def _action_higuruma_sword(battle: dict, attacker_num: int, defender_num: int):
    attacker = battle["fighters"][attacker_num]
    if not attacker.get("higuruma_sword_ready", False):
        return False, "Золотой меч сейчас недоступен."

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

    if effect.get("survive_lethal_once"):
        attacker["survive_lethal_available"] = True

    return True, effect.get("label", "Пакт активирован.")

async def _process_action(callback: CallbackQuery, action: str):
    user_id = callback.from_user.id
    battle = active_coop_battles.get(user_id)

    if not battle:
        await callback.answer("Бой не найден.", show_alert=True)
        return

    player_num = _player_num_by_tg(battle, user_id)
    if battle["current_player"] != player_num:
        await callback.answer("Сейчас не твой ход.", show_alert=True)
        return
    attacker_user_id = battle["player_info"][player_num]["user_id"]

    pending_battlerdan = _pending_battlerdan_for(battle, player_num)
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
            await _advance_turn(callback, battle, player_num)
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
            await _advance_turn(callback, battle, player_num)
            await callback.answer()
            return

        await callback.answer("Нужно сделать выбор в дебатах.", show_alert=True)
        return

    pending = _pending_response_for(battle, player_num)
    if pending:
        if action not in ("domain", "simple", "skip_response", "mahoraga"):
            await callback.answer("Нужно ответить на домен: расширение, простая территория или Махорага.", show_alert=True)
            return

        if action == "domain":
            target_num = _select_target_player(battle, player_num)
            if not target_num:
                await callback.answer("Нет доступных целей.", show_alert=True)
                return
            ok, error = _action_domain(battle, player_num, target_num)
            if error:
                await callback.answer(error, show_alert=True)
                return
            await check_achievements(attacker_user_id, "territories_used", value=1)
        elif action == "simple":
            ok, error = _action_simple_domain(battle, player_num)
            if error:
                await callback.answer(error, show_alert=True)
                return
        elif action == "mahoraga":
            flags = _get_turn_flags(battle, player_num)
            if flags.get("mahoraga_used"):
                await callback.answer("Адаптация уже активирована в этом ходу.", show_alert=True)
                return
            ok, error = _action_mahoraga(battle, player_num)
            if error:
                await callback.answer(error, show_alert=True)
                return
            flags["mahoraga_used"] = True
        else:
            battle["log"].append("⏭ Ответ на домен пропущен.")

        battle["pending_domain_response"] = None
        await _advance_turn(callback, battle, player_num)
        await callback.answer()
        return

    flags = _get_turn_flags(battle, player_num)

    if action == "basic":
        if flags.get("attack_used"):
            await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
            return
        target_num = _select_target_player(battle, player_num)
        if not target_num:
            await callback.answer("Нет доступных целей.", show_alert=True)
            return
        defender_alive = _action_basic_attack(battle, player_num, target_num)
        flags["attack_used"] = True
        if not defender_alive:
            await _check_end_or_continue(callback, battle)
            await callback.answer()
            return
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    if action == "higuruma_sword":
        if flags.get("attack_used"):
            await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
            return
        target_num = _select_target_player(battle, player_num)
        if not target_num:
            await callback.answer("Нет доступных целей.", show_alert=True)
            return
        defender_alive, error = _action_higuruma_sword(battle, player_num, target_num)
        if error:
            await callback.answer(error, show_alert=True)
            return
        flags["attack_used"] = True
        if not defender_alive:
            await _check_end_or_continue(callback, battle)
            await callback.answer()
            return
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    if action.startswith("special_"):
        if flags.get("attack_used"):
            await callback.answer("Ты уже использовал атаку в этом ходу.", show_alert=True)
            return
        target_num = _select_target_player(battle, player_num)
        if not target_num:
            await callback.answer("Нет доступных целей.", show_alert=True)
            return
        defender_alive, error = _action_special(battle, player_num, target_num, action.split("special_", 1)[1])
        if error:
            await callback.answer(error, show_alert=True)
            return
        flags["attack_used"] = True
        if not defender_alive:
            await _check_end_or_continue(callback, battle)
            await callback.answer()
            return
        await _update_battle_messages(callback, battle)
        await callback.answer()
        return

    if action == "rct":
        if flags.get("rct_used"):
            await callback.answer("ОПТ уже использована в этом ходу.", show_alert=True)
            return
        ok, error = _action_reverse_ct(battle, player_num)
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
        ok, error = _action_mahoraga(battle, player_num)
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
        ok, message = _action_pact(battle, player_num, pact_id)
        if not ok:
            await callback.answer(message, show_alert=True)
            return
        await _update_battle_messages(callback, battle)
        await callback.answer(message, show_alert=True)
        return

    if action == "domain":
        target_num = _select_target_player(battle, player_num)
        if not target_num:
            await callback.answer("Нет доступных целей.", show_alert=True)
            return
        prev_domain = battle.get("domain_state")
        prev_owner = prev_domain.get("owner") if prev_domain else None
        ok, error = _action_domain(battle, player_num, target_num)
        if error:
            await callback.answer(error, show_alert=True)
            return
        await check_achievements(attacker_user_id, "territories_used", value=1)
        if battle.get("battlerdan_pending"):
            await _update_battle_messages(callback, battle)
            await callback.answer()
            return
        domain_state = battle.get("domain_state")
        if prev_owner is None and domain_state and domain_state.get("owner") == player_num:
            battle["pending_domain_response"] = {"target": target_num, "owner": player_num}
        await _advance_turn(callback, battle, player_num)
        await callback.answer()
        return

    if action == "simple":
        ok, error = _action_simple_domain(battle, player_num)
        if error:
            await callback.answer(error, show_alert=True)
            return
        await _advance_turn(callback, battle, player_num)
        await callback.answer()
        return

    if action == "end_turn":
        await _advance_turn(callback, battle, player_num)
        await callback.answer()
        return

    await callback.answer("Неизвестное действие.", show_alert=True)


async def _check_end_or_continue(callback: CallbackQuery, battle: dict):
    team1_alive = _team_alive(battle, 1)
    team2_alive = _team_alive(battle, 2)
    if team1_alive and team2_alive:
        await _update_battle_messages(callback, battle)
        return
    winner_team = 1 if team1_alive else 2
    await end_coop_battle(callback, battle, winner_team)


async def _advance_turn(callback: CallbackQuery, battle: dict, acting_player_num: int):
    order = battle["turn_order"]
    current_idx = order.index(acting_player_num)
    next_idx, next_player = _next_alive_player(battle, current_idx)
    if next_player is None:
        return

    battle["current_player"] = next_player
    battle["turn"] += 1
    _reset_turn_flags(battle, next_player)

    domain = battle.get("domain_state")
    if domain and not battle["fighters"][domain["target"]]["main"].is_alive():
        battle["domain_state"] = None
        battle["pending_domain_response"] = None

    _apply_start_turn_effects(battle, next_player)

    domain = battle.get("domain_state")
    if domain and not battle["fighters"][domain["target"]]["main"].is_alive():
        battle["domain_state"] = None
        battle["pending_domain_response"] = None

    # Check if DOT killed someone
    if not battle["fighters"][next_player]["main"].is_alive():
        await _check_end_or_continue(callback, battle)
        return

    await _check_end_or_continue(callback, battle)


async def end_coop_battle(callback: CallbackQuery, battle: dict, winner_team: int):
    team1_ids = [battle["player_info"][p]["user_id"] for p in battle["teams"][1]]
    team2_ids = [battle["player_info"][p]["user_id"] for p in battle["teams"][2]]

    winner_ids = team1_ids if winner_team == 1 else team2_ids
    loser_ids = team2_ids if winner_team == 1 else team1_ids

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id.in_(winner_ids + loser_ids)))
        users = result.scalars().all()
        users_map = {u.id: u for u in users}

        now = datetime.utcnow()
        for uid in winner_ids:
            user = users_map.get(uid)
            if not user:
                continue
            user.pvp_wins += 1
            user.total_battles += 1
            user.last_battle_time = now
            await add_daily_quest_progress(session, user.id, "pvp_wins", amount=1)
            await add_daily_quest_progress(session, user.id, "pvp_battles", amount=1)

        for uid in loser_ids:
            user = users_map.get(uid)
            if not user:
                continue
            user.pvp_losses += 1
            user.total_battles += 1
            user.last_battle_time = now
            await add_daily_quest_progress(session, user.id, "pvp_battles", amount=1)

        winner_results = {}
        for uid in winner_ids:
            user = users_map.get(uid)
            if not user:
                continue
            leveled_up, actual_exp, unlocked_from_level = await apply_experience_with_pvp_rolls(session, user, 50)
            winner_results[uid] = (leveled_up, actual_exp, unlocked_from_level)

        # Save a compact battle record using team leaders
        leader1 = battle["team_leaders"][1]
        leader2 = battle["team_leaders"][2]
        winner_leader = leader1 if winner_team == 1 else leader2
        battle_record = Battle(
            battle_type="pvp_coop",
            player1_id=leader1,
            player2_id=leader2,
            winner_id=winner_leader,
            battle_log="\\n".join(battle["log"]),
            exp_gained=50,
            points_gained=0,
        )
        session.add(battle_record)
        await session.flush()

        for uid in winner_ids:
            user = users_map.get(uid)
            if not user:
                continue

            await check_achievements(uid, "pvp_wins", value=1, session=session)

            result = await session.execute(
                select(Battle)
                .where(
                    Battle.battle_type.in_(["pvp", "pvp_coop"]),
                    (Battle.player1_id == uid) | (Battle.player2_id == uid),
                )
                .order_by(Battle.created_at.desc())
                .limit(20)
            )
            streak = 0
            for record in result.scalars().all():
                if record.winner_id == uid:
                    streak += 1
                else:
                    break
            await check_achievements(uid, "pvp_streak", value=streak, absolute=True, session=session)

            await check_achievements(uid, "level", value=user.level, absolute=True, session=session)
            if user.hardcore_mode:
                await check_achievements(uid, "hardcore_level", value=user.level, absolute=True, session=session)

            result = await session.execute(
                select(func.count(UserTechnique.id)).where(UserTechnique.user_id == uid)
            )
            technique_count = int(result.scalar() or 0)
            await check_achievements(
                uid,
                "techniques_obtained",
                value=technique_count,
                absolute=True,
                session=session,
            )

            result = await session.execute(
                select(func.count(UserCard.id)).where(UserCard.user_id == uid)
            )
            card_count = int(result.scalar() or 0)
            await check_achievements(
                uid,
                "cards_collected",
                value=card_count,
                absolute=True,
                session=session,
            )

        await session.commit()

        # Send results
        for pnum, info in battle["player_info"].items():
            user = users_map.get(info["user_id"])
            if not user:
                continue
            is_winner = info["user_id"] in winner_ids
            if is_winner:
                leveled_up, actual_exp, unlocked = winner_results.get(info["user_id"], (False, 0, []))
                text = (
                    "🏆 <b>Победа в командном PvP!</b>\n\n"
                    f"⭐ Опыт: +{actual_exp}\n"
                )
                if leveled_up:
                    text += f"🎉 <b>Новый уровень! Теперь ты {user.level} уровень!</b>\n"
                if unlocked:
                    names = ", ".join(t.name for t in unlocked)
                    text += f"🆕 <b>Новые PvP-техники:</b> {names}\n"
            else:
                text = (
                    "💀 <b>Поражение в командном PvP</b>\n\n"
                    "Попробуй снова и станешь сильнее."
                )
            try:
                await callback.bot.send_message(info["tg"], text, parse_mode="HTML")
            except Exception:
                pass

    for tg in list(active_coop_battles.keys()):
        if active_coop_battles[tg]["battle_id"] == battle["battle_id"]:
            del active_coop_battles[tg]


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

    profile = _get_character_profile(main_name)
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
        "black_flash_chance": get_black_flash_chance(main_name),
        "domain_level": domain_level,
        "rct_level": rct_level,
        "next_attack_multiplier": 1.0,
        "next_attack_ready": False,
        "pact_used": set(),
        "has_mahoraga": has_mahoraga,
        "mahoraga_ready": False,
        "mahoraga_adapt": {},
        "mahoraga_domain_adapt": {},
        "mahoraga_cost": mahoraga_cost,
        "higuruma_sword_ready": False,
        "ce_lock_turns": 0,
        "attack_multiplier": attack_multiplier,
        "shikigami_damage_mult": shikigami_damage_mult,
        "survive_lethal_available": False,
        "pacts_disabled": is_toji,
        "ignore_domain_effects": is_toji,
        "is_battlerdan": is_battlerdan,
        "infinity_chance": 1.0 if is_gojo and TECH_INFINITY in technique_names else 0.0,
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

    return state


async def start_coop_battle(callback: CallbackQuery, team1: dict, team2: dict) -> bool:
    async with async_session() as session:
        team1_ids = team1.get("members", [])
        team2_ids = team2.get("members", [])
        all_tgs = team1_ids + team2_ids
        result = await session.execute(select(User).where(User.telegram_id.in_(all_tgs)))
        users = result.scalars().all()
        users_map = {u.telegram_id: u for u in users}

        # Validate all users
        for tg in all_tgs:
            user = users_map.get(tg)
            if not user or not user.slot_1_card_id:
                await callback.answer("У одного из игроков не экипирована главная карта.", show_alert=True)
                return False

        battle_id = f"coop_{team1['leader_tg']}_{team2['leader_tg']}_{datetime.utcnow().timestamp()}"
        fighters = {}
        player_info = {}
        player_team = {}
        turn_order = []

        next_player_num = 1
        for team_id, member_tgs in ((1, team1_ids), (2, team2_ids)):
            for tg in member_tgs:
                user = users_map[tg]
                main = await _load_card(session, user.slot_1_card_id)
                weapon = await _load_card(session, user.slot_2_card_id)
                shikigami = await _load_card(session, user.slot_3_card_id)
                pact1 = await _load_card(session, user.slot_4_card_id)
                pact2 = await _load_card(session, user.slot_5_card_id)

                if not main:
                    await callback.answer("У одного из игроков не экипирована главная карта.", show_alert=True)
                    return False

                main.heal()
                if weapon:
                    weapon.heal()
                if shikigami:
                    shikigami.heal()
                if pact1:
                    pact1.heal()
                if pact2:
                    pact2.heal()

                toolkit = await get_player_pvp_toolkit(session, user.id)
                clan_bonuses = await get_clan_bonuses(session, user.clan)
                technique_names = await _get_user_technique_names(session, user.id)
                fighters[next_player_num] = _build_fighter_state(
                    main,
                    weapon,
                    shikigami,
                    [pact1, pact2],
                    toolkit,
                    clan_bonuses=clan_bonuses,
                    technique_names=technique_names,
                )
                if user.equipped_title_id:
                    title = await session.scalar(select(Title).where(Title.id == user.equipped_title_id))
                    fighters[next_player_num]["title"] = title
                player_info[next_player_num] = {
                    "user_id": user.id,
                    "tg": user.telegram_id,
                    "name": _display_name(user),
                }
                player_team[next_player_num] = team_id
                turn_order.append(next_player_num)
                next_player_num += 1

        # Speed-based order
        turn_order.sort(key=lambda p: _get_fighter_speed(fighters[p]), reverse=True)

        battle = {
            "battle_id": battle_id,
            "teams": {
                1: [p for p in player_team if player_team[p] == 1],
                2: [p for p in player_team if player_team[p] == 2],
            },
            "team_leaders": {
                1: users_map[team1["leader_tg"]].id,
                2: users_map[team2["leader_tg"]].id,
            },
            "player_team": player_team,
            "player_info": player_info,
            "player_map": {info["tg"]: pnum for pnum, info in player_info.items()},
            "fighters": fighters,
            "turn_order": turn_order,
            "current_player": turn_order[0],
            "turn": 1,
            "domain_state": None,
            "pending_domain_response": None,
            "battlerdan_pending": None,
            "turn_flags": {p: {"attack_used": False, "rct_used": False, "mahoraga_used": False} for p in fighters},
            "log": ["⚡ Бой начинается! Первый ход за самым быстрым бойцом."],
            "messages": {},
        }

        for info in player_info.values():
            active_coop_battles[info["tg"]] = battle

        await _update_battle_messages(callback, battle)
        return True


@router.callback_query(F.data.startswith("coop_action_"))
async def coop_action_callback(callback: CallbackQuery):
    action = callback.data.split("coop_action_", 1)[1]
    await _process_action(callback, action)
