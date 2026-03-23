from __future__ import annotations

import shlex
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select

from config import ADMIN_IDS as CONFIG_ADMIN_IDS
from handlers.achievements import check_achievements
from models import (
    PromoCode,
    Technique,
    User,
    UserCard,
    UserPromoCode,
    UserTechnique,
    async_session,
)
from utils.card_rewards import get_card_data_by_name, grant_card_to_user
from utils.pvp_progression import apply_experience_with_pvp_rolls
from utils.technique_data import ALL_TECHNIQUES

router = Router()
PROMO_ADMIN_IDS = set(CONFIG_ADMIN_IDS + [1296861067])


def _normalize_name(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _parse_command_args(raw_text: str | None) -> list[str]:
    text = (raw_text or "").strip()
    if not text:
        return []

    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _find_technique_data(name: str | None) -> dict | None:
    normalized = _normalize_name(name)
    if not normalized:
        return None

    for technique in ALL_TECHNIQUES:
        if _normalize_name(technique.get("name")) == normalized:
            return technique
    return None


async def _resolve_message_user(session, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def _get_or_create_technique_template(session, tech_data: dict) -> Technique:
    technique = await session.scalar(
        select(Technique).where(Technique.name == tech_data["name"])
    )
    if technique:
        return technique

    technique = Technique(
        name=tech_data["name"],
        description=tech_data.get("description"),
        technique_type=tech_data["technique_type"],
        ce_cost=tech_data.get("ce_cost", 0),
        effect_type=tech_data.get("effect_type"),
        effect_value=tech_data.get("effect_value", 0),
        trigger_chance=tech_data.get("trigger_chance", 0.0),
        duration=tech_data.get("duration", 0),
        icon=tech_data.get("icon", "✨"),
        rarity=tech_data.get("rarity", "common"),
    )
    session.add(technique)
    await session.flush()
    return technique


def _parse_non_negative_int(raw_value: str, field_label: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Параметр {field_label} должен быть числом.") from exc

    if value < 0:
        raise ValueError(f"Параметр {field_label} не может быть отрицательным.")
    return value


@router.message(Command("promo"))
async def cmd_promo(message: Message):
    """Использовать промокод."""
    args = _parse_command_args(message.text)

    if len(args) < 2:
        await message.answer(
            "🎁 <b>Промокоды</b>\n\n"
            "Использование:\n"
            "<code>/promo КОД</code>\n\n"
            "Введи промокод, чтобы получить награду!",
            parse_mode="HTML",
        )
        return

    code = args[1].strip().upper()
    if not code:
        await message.answer("❌ Укажи код после команды, например: <code>/promo START</code>", parse_mode="HTML")
        return

    async with async_session() as session:
        user = await _resolve_message_user(session, message.from_user.id)
        if not user:
            await message.answer("Сначала используй /start")
            return

        promo = await session.scalar(
            select(PromoCode).where(
                PromoCode.code == code,
                PromoCode.is_active.is_(True),
            )
        )
        if not promo:
            await message.answer(
                "❌ <b>Промокод не найден или отключён!</b>\n\n"
                "Проверь правильность ввода.",
                parse_mode="HTML",
            )
            return

        if promo.expires_at and promo.expires_at < datetime.utcnow():
            promo.is_active = False
            await session.commit()
            await message.answer(
                "❌ <b>Промокод истёк!</b>\n\n"
                "Этот код больше не действует.",
                parse_mode="HTML",
            )
            return

        if promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
            await message.answer(
                "❌ <b>Промокод исчерпан!</b>\n\n"
                "Достигнут лимит использований.",
                parse_mode="HTML",
            )
            return

        already_used = await session.scalar(
            select(UserPromoCode).where(
                UserPromoCode.user_id == user.id,
                UserPromoCode.promo_code_id == promo.id,
            )
        )
        if already_used:
            await message.answer(
                "❌ <b>Ты уже использовал этот промокод!</b>\n\n"
                "Каждый код можно использовать только один раз.",
                parse_mode="HTML",
            )
            return

        reward_lines: list[str] = []
        unlocked_from_level = []

        if promo.exp_reward > 0:
            _, actual_exp, unlocked_from_level = await apply_experience_with_pvp_rolls(
                session, user, promo.exp_reward
            )
            reward_lines.append(f"⭐ Опыт: +{actual_exp}")

        if promo.points_reward > 0:
            user.points += promo.points_reward
            reward_lines.append(f"💎 Очки: +{promo.points_reward}")

        if promo.coins_reward > 0:
            user.coins += promo.coins_reward
            reward_lines.append(f"🪙 Монеты: +{promo.coins_reward}")

        if promo.card_reward:
            card_data = get_card_data_by_name(promo.card_reward)
            if card_data:
                await grant_card_to_user(session, user.id, card_data, level=1)
                reward_lines.append(f"🎴 Карта: <b>{card_data['name']}</b>")
            else:
                reward_lines.append(f"⚠️ Карта <b>{promo.card_reward}</b> не найдена и была пропущена.")

        if promo.technique_reward:
            tech_data = _find_technique_data(promo.technique_reward)
            if tech_data:
                tech_template = await _get_or_create_technique_template(session, tech_data)
                existing_user_technique = await session.scalar(
                    select(UserTechnique).where(
                        UserTechnique.user_id == user.id,
                        UserTechnique.technique_id == tech_template.id,
                    )
                )
                if existing_user_technique:
                    reward_lines.append(f"⚠️ Техника <b>{tech_data['name']}</b> уже есть у игрока.")
                else:
                    session.add(
                        UserTechnique(
                            user_id=user.id,
                            technique_id=tech_template.id,
                            level=1,
                            is_equipped=False,
                        )
                    )
                    reward_lines.append(f"✨ Техника: <b>{tech_data['name']}</b>")
            else:
                reward_lines.append(f"⚠️ Техника <b>{promo.technique_reward}</b> не найдена и была пропущена.")

        session.add(UserPromoCode(user_id=user.id, promo_code_id=promo.id))
        promo.current_uses += 1

        await check_achievements(user.id, "level", value=user.level, absolute=True, session=session)
        if user.hardcore_mode:
            await check_achievements(
                user.id,
                "hardcore_level",
                value=user.level,
                absolute=True,
                session=session,
            )

        technique_count = int(
            await session.scalar(select(func.count(UserTechnique.id)).where(UserTechnique.user_id == user.id))
            or 0
        )
        await check_achievements(
            user.id,
            "techniques_obtained",
            value=technique_count,
            absolute=True,
            session=session,
        )

        card_count = int(
            await session.scalar(select(func.count(UserCard.id)).where(UserCard.user_id == user.id))
            or 0
        )
        await check_achievements(
            user.id,
            "cards_collected",
            value=card_count,
            absolute=True,
            session=session,
        )
        await check_achievements(
            user.id,
            "coins_collected",
            value=user.coins,
            absolute=True,
            session=session,
        )

        await session.commit()

        if unlocked_from_level:
            reward_lines.append(
                f"✨ Новые PvP-техники: {', '.join(tech.name for tech in unlocked_from_level)}"
            )

        if not reward_lines:
            reward_lines.append("ℹ️ У этого промокода не было наград.")

        reward_text = (
            "🎉 <b>Промокод активирован!</b>\n\n"
            f"<i>{promo.description or 'Награды:'}</i>\n\n"
            + "\n".join(reward_lines)
            + "\n\n✅ <b>Награды начислены!</b>"
        )
        await message.answer(reward_text, parse_mode="HTML")


@router.message(Command("createpromo"))
async def cmd_create_promo(message: Message):
    """Создать промокод (только для админов)."""
    args = _parse_command_args(message.text)

    async with async_session() as session:
        user = await _resolve_message_user(session, message.from_user.id)
        if message.from_user.id not in PROMO_ADMIN_IDS and (not user or not user.is_admin):
            await message.answer("❌ У тебя нет прав для этой команды!")
            return

        if len(args) < 3:
            await message.answer(
                "🎁 <b>Создание промокода</b>\n\n"
                "Использование:\n"
                "<code>/createpromo КОД \"ОПИСАНИЕ\" [награды...]</code>\n\n"
                "Примеры:\n"
                "<code>/createpromo STARTER \"Стартовый бонус\" exp=100 coins=500 points=3</code>\n"
                "<code>/createpromo LEGENDARY \"Легендарная карта\" card=Годжо_Сатору uses=10</code>\n"
                "<code>/createpromo TECH \"Техника\" technique=Красный days=30</code>\n\n"
                "Параметры:\n"
                "- exp=N - опыт\n"
                "- points=N - очки\n"
                "- coins=N - монеты\n"
                "- card=НАЗВАНИЕ - карта\n"
                "- technique=НАЗВАНИЕ - техника\n"
                "- uses=N - количество использований (0 = без лимита)\n"
                "- days=N - срок действия в днях (0 = бессрочно)",
                parse_mode="HTML",
            )
            return

        code = args[1].strip().upper()
        payload_args = args[2:]
        option_start_index = len(payload_args)
        description_parts: list[str] = []
        for index, token in enumerate(payload_args):
            if "=" in token:
                option_start_index = index
                break
            description_parts.append(token)

        description = " ".join(description_parts).strip()
        if not code:
            await message.answer("❌ Код промокода не может быть пустым.")
            return
        if not description:
            await message.answer("❌ Описание промокода не может быть пустым.")
            return

        exp_reward = 0
        points_reward = 0
        coins_reward = 0
        card_reward = None
        technique_reward = None
        max_uses = 1
        days_valid = 7
        unknown_args: list[str] = []

        try:
            for raw_arg in payload_args[option_start_index:]:
                if "=" not in raw_arg:
                    unknown_args.append(raw_arg)
                    continue

                key, raw_value = raw_arg.split("=", 1)
                key = key.strip().lower()
                value = raw_value.strip()

                if key == "exp":
                    exp_reward = _parse_non_negative_int(value, "exp")
                elif key == "points":
                    points_reward = _parse_non_negative_int(value, "points")
                elif key == "coins":
                    coins_reward = _parse_non_negative_int(value, "coins")
                elif key == "card":
                    card_reward = value.replace("_", " ").strip()
                elif key == "technique":
                    technique_reward = value.replace("_", " ").strip()
                elif key == "uses":
                    max_uses = _parse_non_negative_int(value, "uses")
                elif key == "days":
                    days_valid = _parse_non_negative_int(value, "days")
                else:
                    unknown_args.append(raw_arg)
        except ValueError as exc:
            await message.answer(f"❌ {exc}")
            return

        if unknown_args:
            await message.answer(
                "❌ Не удалось распознать параметры:\n"
                + "\n".join(f"• <code>{arg}</code>" for arg in unknown_args),
                parse_mode="HTML",
            )
            return

        if not any([exp_reward, points_reward, coins_reward, card_reward, technique_reward]):
            await message.answer("❌ У промокода должна быть хотя бы одна награда.")
            return

        if card_reward and not get_card_data_by_name(card_reward):
            await message.answer(f"❌ Карта <b>{card_reward}</b> не найдена.", parse_mode="HTML")
            return

        if technique_reward and not _find_technique_data(technique_reward):
            await message.answer(f"❌ Техника <b>{technique_reward}</b> не найдена.", parse_mode="HTML")
            return

        existing = await session.scalar(select(PromoCode).where(PromoCode.code == code))
        if existing:
            await message.answer(f"❌ Промокод <code>{code}</code> уже существует!", parse_mode="HTML")
            return

        expires_at = datetime.utcnow() + timedelta(days=days_valid) if days_valid > 0 else None
        promo = PromoCode(
            code=code,
            description=description,
            exp_reward=exp_reward,
            points_reward=points_reward,
            coins_reward=coins_reward,
            card_reward=card_reward,
            technique_reward=technique_reward,
            max_uses=max_uses,
            current_uses=0,
            expires_at=expires_at,
            is_active=True,
        )
        session.add(promo)
        await session.commit()

        uses_label = "без лимита" if max_uses == 0 else str(max_uses)
        days_label = "бессрочно" if days_valid == 0 else f"{days_valid} дн."
        await message.answer(
            "✅ <b>Промокод создан!</b>\n\n"
            f"Код: <code>{code}</code>\n"
            f"Описание: {description}\n"
            f"Использований: {uses_label}\n"
            f"Срок: {days_label}\n\n"
            "Награды:\n"
            f"⭐ {exp_reward} опыта\n"
            f"💎 {points_reward} очков\n"
            f"🪙 {coins_reward} монет\n"
            f"🎴 Карта: {card_reward or 'Нет'}\n"
            f"✨ Техника: {technique_reward or 'Нет'}",
            parse_mode="HTML",
        )
