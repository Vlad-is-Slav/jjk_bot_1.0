from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from keyboards import get_battle_menu
from utils.boss_data import BOSSES, get_boss_by_key

router = Router()


async def _sync_boss_templates(session) -> dict[str, object]:
    from models import BossBattle

    result = await session.execute(select(BossBattle))
    existing = {boss.name: boss for boss in result.scalars().all() if boss.name}
    synced = {}

    for boss in BOSSES:
        card = boss.get("card", {})
        rewards = boss.get("rewards", {})
        template = existing.get(boss["name"])
        if not template:
            template = BossBattle(name=boss["name"])
            session.add(template)
            await session.flush()

        template.description = boss.get("description")
        template.attack = int(card.get("attack", 100))
        template.defense = int(card.get("defense", 80))
        template.speed = int(card.get("speed", 70))
        template.hp = int(card.get("hp", 500))
        template.max_hp = int(card.get("hp", 500))
        template.exp_reward = int(boss.get("exp_reward", 500))
        template.points_reward = int(boss.get("points_reward", 0))
        template.coins_reward = int(rewards.get("coins", 0) or 0)
        template.special_reward = rewards.get("title", {}).get("name")
        template.required_level = int(boss.get("min_level", 1))
        template.cooldown_hours = 0
        synced[boss["key"]] = template

    await session.flush()
    return synced


async def _get_boss_progress(session, user_id: int, templates: dict[str, object]) -> dict[str, object]:
    from models import UserBossAttempt

    boss_ids = [template.id for template in templates.values() if getattr(template, "id", None)]
    if not boss_ids:
        return {}

    result = await session.execute(
        select(UserBossAttempt).where(
            UserBossAttempt.user_id == user_id,
            UserBossAttempt.boss_id.in_(boss_ids),
        )
    )
    attempts = {attempt.boss_id: attempt for attempt in result.scalars().all()}
    return {key: attempts.get(template.id) for key, template in templates.items()}


def _boss_menu_keyboard(user_level: int, completed_keys: set[str] | None = None) -> InlineKeyboardMarkup:
    completed_keys = completed_keys or set()
    rows = []
    for boss in BOSSES:
        key = boss["key"]
        if key in completed_keys:
            rows.append([InlineKeyboardButton(text=f"✅ {boss['name']} (пройден)", callback_data="noop")])
        elif user_level >= int(boss.get("min_level", 1)):
            rows.append([InlineKeyboardButton(text=f"🧿 {boss['name']}", callback_data=f"boss_start_{key}")])
        else:
            rows.append([
                InlineKeyboardButton(
                    text=f"🔒 {boss['name']} ({boss['min_level']} ур.)",
                    callback_data="noop",
                )
            ])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="battle_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("battle"))
async def cmd_battle(message: Message):
    await message.answer(
        "⚔️ <b>Меню боёв</b>\n\nВыбери тип боя:",
        reply_markup=get_battle_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "battle_menu")
async def battle_menu_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚔️ <b>Меню боёв</b>\n\n"
        "👹 <b>Арена проклятий</b> — обычные PvE-забеги.\n"
        "⚔️ <b>PvP</b> — бои с другими игроками.\n"
        "🧿 <b>Боссы</b> — особые одноразовые сражения с повышенными наградами.",
        reply_markup=get_battle_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "battle_history")
async def battle_history_callback(callback: CallbackQuery):
    from keyboards.main_menu import get_back_button
    from models import Battle, User, async_session

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        result = await session.execute(
            select(Battle)
            .options(selectinload(Battle.player1), selectinload(Battle.player2))
            .where((Battle.player1_id == user.id) | (Battle.player2_id == user.id))
            .order_by(Battle.created_at.desc())
            .limit(10)
        )
        battles = result.scalars().all()

        if not battles:
            await callback.message.edit_text(
                "📜 <b>История боёв</b>\n\nУ тебя пока нет завершённых боёв.",
                reply_markup=get_back_button("battle_menu"),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        lines = ["📜 <b>Последние бои</b>\n"]
        for index, battle in enumerate(battles, start=1):
            opponent_name = battle.get_opponent_name(user.id)
            is_winner = battle.winner_id == user.id
            result_emoji = "🏆" if is_winner else "💀"
            battle_type = "PvP" if battle.battle_type == "pvp" else "PvE"
            lines.append(f"{index}. {result_emoji} [{battle_type}] vs {opponent_name}")

        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=get_back_button("battle_menu"),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "boss_battles")
async def boss_battles_callback(callback: CallbackQuery):
    from models import User, async_session

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        templates = await _sync_boss_templates(session)
        progress = await _get_boss_progress(session, user.id, templates)
        completed_keys = {
            key for key, attempt in progress.items()
            if attempt and bool(getattr(attempt, "defeated", False))
        }

        lines = ["🧿 <b>Бои с боссами</b>\n"]
        for boss in BOSSES:
            attempt = progress.get(boss["key"])
            unlocked = user.level >= int(boss.get("min_level", 1))
            if attempt and bool(getattr(attempt, "defeated", False)):
                status = "✅ уже побеждён"
            elif unlocked:
                status = "доступен"
            else:
                status = f"от {boss['min_level']} уровня"
            reward_line = f"Награда: {boss.get('rewards', {}).get('coins', 0)} монет"
            if boss.get("rewards", {}).get("random_card"):
                reward_line += ", случайная карта"
            lines.append(
                f"<b>{boss['name']}</b>\n"
                f"{boss.get('description', '')}\n"
                f"Статус: {status}\n"
                f"{reward_line}"
            )

        await callback.message.edit_text(
            "\n\n".join(lines),
            reply_markup=_boss_menu_keyboard(user.level, completed_keys=completed_keys),
            parse_mode="HTML",
        )
        await callback.answer()


@router.callback_query(F.data.startswith("boss_start_"))
async def boss_start_callback(callback: CallbackQuery):
    from handlers.pve import (
        PVE_DEFAULT_STRATEGY,
        SimpleCard,
        _apply_strategy_to_state,
        _build_fighter_state,
        _ensure_curse,
        _find_active_pve_battle,
        _get_user_technique_names,
        _load_card,
        _player_baseline,
        _refresh_battle_rng,
        _send_active_run_prompt,
        active_pve_battles,
        last_pve_strategy,
    )
    from models import User, UserBossAttempt, async_session
    from utils.clan_progression import get_clan_bonuses
    from utils.pvp_progression import get_player_pvp_toolkit

    boss_key = callback.data.split("boss_start_", 1)[1]
    boss = get_boss_by_key(boss_key)
    if not boss:
        await callback.answer("Босс не найден.", show_alert=True)
        return

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if not user:
            await callback.answer("Сначала используй /start", show_alert=True)
            return

        templates = await _sync_boss_templates(session)
        boss_template = templates.get(boss_key)
        if not boss_template:
            await callback.answer("Не удалось подготовить босса.", show_alert=True)
            return

        if user.level < int(boss.get("min_level", 1)):
            await callback.answer(
                f"Этот босс открывается с {boss['min_level']} уровня.",
                show_alert=True,
            )
            return

        attempt = await session.scalar(
            select(UserBossAttempt).where(
                UserBossAttempt.user_id == user.id,
                UserBossAttempt.boss_id == boss_template.id,
            )
        )
        if attempt and bool(attempt.defeated):
            await callback.answer("Ты уже победил этого босса. Повторно пройти его нельзя.", show_alert=True)
            return

        if not attempt:
            attempt = UserBossAttempt(
                user_id=user.id,
                boss_id=boss_template.id,
                attempts=0,
                reward_claimed=False,
            )
            session.add(attempt)
            await session.flush()

        attempt.attempts = int(attempt.attempts or 0) + 1
        attempt.last_attempt = datetime.utcnow()

        main_card = await _load_card(session, user.slot_1_card_id)
        weapon_card = await _load_card(session, user.slot_2_card_id)
        shikigami_card = await _load_card(session, user.slot_3_card_id)
        pact_card_1 = await _load_card(session, user.slot_4_card_id)
        pact_card_2 = await _load_card(session, user.slot_5_card_id)
        if not main_card:
            await callback.answer("У тебя не экипирована главная карта.", show_alert=True)
            return

        main_card.heal()
        for extra in (weapon_card, shikigami_card, pact_card_1, pact_card_2):
            if extra:
                extra.heal()

        toolkit = await get_player_pvp_toolkit(session, user.id)
        clan_bonuses = await get_clan_bonuses(session, user.clan)
        player_techniques = await _get_user_technique_names(session, user.id)
        strategy_key = last_pve_strategy.get(user.telegram_id, PVE_DEFAULT_STRATEGY)

        player_state = _build_fighter_state(
            main_card,
            weapon_card,
            shikigami_card,
            [pact_card_1, pact_card_2],
            toolkit,
            clan_bonuses=clan_bonuses,
            technique_names=player_techniques,
        )
        _apply_strategy_to_state(player_state, strategy_key)

        boss_card_data = boss.get("card", {})
        boss_card = SimpleCard(
            name=boss["name"],
            description=boss.get("description", ""),
            attack=int(boss_card_data.get("attack", 80)),
            defense=int(boss_card_data.get("defense", 70)),
            speed=int(boss_card_data.get("speed", 60)),
            hp=int(boss_card_data.get("hp", 900)),
            max_ce=int(boss_card_data.get("max_ce", 180)),
            ce_regen=int(boss_card_data.get("ce_regen", 14)),
            domain_level=int(boss_card_data.get("domain_level", 0)),
            rct_level=int(boss_card_data.get("rct_level", 0)),
        )
        boss_state = _build_fighter_state(
            boss_card,
            None,
            None,
            [],
            {"has_domain": True, "has_simple_domain": False, "has_reverse_ct": False},
            profile_override=boss.get("profile"),
        )
        boss_card.heal()

        curse = await _ensure_curse(
            session,
            {
                "name": boss["name"],
                "description": boss.get("description", ""),
                "grade": 10,
                "curse_type": "boss",
                "exp_reward": int(boss.get("exp_reward", max(220, user.level * 22))),
                "points_reward": 0,
                "card_drop_chance": 0.0,
            },
            boss_card,
        )

        _, battle_tg = _find_active_pve_battle(callback.from_user.id)
        if battle_tg is not None and battle_tg in active_pve_battles:
            del active_pve_battles[battle_tg]

        battle = {
            "battle_id": f"boss_{user.id}_{boss['key']}_{datetime.utcnow().timestamp()}",
            "user_id": user.id,
            "player_tg": user.telegram_id,
            "fighters": {1: player_state, 2: boss_state},
            "turn": 1,
            "current_player": 1,
            "domain_state": None,
            "pending_domain_response": None,
            "battlerdan_pending": None,
            "pending_special_variant": {},
            "turn_flags": {
                1: {"attack_used": False, "rct_used": False, "mahoraga_used": False},
                2: {"attack_used": False, "rct_used": False, "mahoraga_used": False},
            },
            "log": [f"🧿 Перед тобой появляется босс {boss['name']}."],
            "difficulty": "hard",
            "baseline": _player_baseline(main_card, shikigami_card),
            "stage": 1,
            "awaiting_continue": False,
            "auto": False,
            "in_battle": False,
            "created_at": datetime.utcnow(),
            "restart_difficulty": "hard",
            "strategy": strategy_key,
            "curse": curse,
            "boss_data": boss,
            "boss_record_id": boss_template.id,
        }
        _refresh_battle_rng(battle)
        active_pve_battles[user.telegram_id] = battle
        await session.commit()

    await _send_active_run_prompt(callback, battle)
    await callback.answer("Босс готов к бою.")
