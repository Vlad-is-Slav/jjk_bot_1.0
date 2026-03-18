import random

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models import UserCard, UserQuote
from utils.quote_data import get_quotes_for_card


async def grant_quote_for_card(session, user_id: int, card_name: str):
    quotes = get_quotes_for_card(card_name)
    if not quotes:
        return None

    result = await session.execute(
        select(UserQuote.quote_text).where(
            UserQuote.user_id == user_id,
        )
    )
    owned_quote_texts = set(result.scalars().all())
    available_quotes = [quote for quote in quotes if quote not in owned_quote_texts]
    if not available_quotes:
        return None

    quote_text = random.choice(available_quotes)
    user_quote = UserQuote(
        user_id=user_id,
        card_name=card_name,
        quote_text=quote_text,
    )
    session.add(user_quote)
    return user_quote


async def ensure_quotes_for_owned_cards(session, user_id: int):
    """???????: ???? ? ????? ??? ?? ????? ?????? ? ??????, ????????? ????."""
    result = await session.execute(
        select(UserCard)
        .options(selectinload(UserCard.card_template))
        .where(UserCard.user_id == user_id)
    )
    user_cards = result.scalars().all()

    granted = []
    for user_card in user_cards:
        if not user_card.card_template:
            continue

        card_name = user_card.card_template.name
        existing = await session.execute(
            select(UserQuote.id).where(
                UserQuote.user_id == user_id,
                UserQuote.card_name == card_name,
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            continue

        granted_quote = await grant_quote_for_card(session, user_id, card_name)
        if granted_quote:
            granted.append(granted_quote)

    return granted