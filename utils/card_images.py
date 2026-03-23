from __future__ import annotations

from pathlib import Path


CARD_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
CARD_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "cards"


def _normalize_name(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _strip_all_suffixes(file_name: str) -> str:
    candidate = file_name or ""
    while True:
        next_candidate = Path(candidate).stem
        if next_candidate == candidate:
            return candidate
        candidate = next_candidate


def resolve_card_image_path(card_name: str | None, aliases: list[str] | tuple[str, ...] | None = None) -> Path | None:
    if not card_name or not CARD_ASSETS_DIR.exists():
        return None

    targets = {
        _normalize_name(card_name),
        _normalize_name((card_name or "").replace("ё", "е")),
    }
    for alias in aliases or []:
        targets.add(_normalize_name(alias))
        targets.add(_normalize_name((alias or "").replace("ё", "е")))

    targets.discard("")
    if not targets:
        return None

    for candidate in CARD_ASSETS_DIR.iterdir():
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in CARD_IMAGE_EXTENSIONS:
            continue

        candidate_keys = {
            _normalize_name(candidate.name),
            _normalize_name(candidate.stem),
            _normalize_name(_strip_all_suffixes(candidate.name)),
            _normalize_name(candidate.name.replace("ё", "е")),
            _normalize_name(candidate.stem.replace("ё", "е")),
            _normalize_name(_strip_all_suffixes(candidate.name).replace("ё", "е")),
        }
        if targets.intersection(candidate_keys):
            return candidate

    return None


def resolve_card_image_source(card_template=None, card_data: dict | None = None) -> str | Path | None:
    image_url = (
        getattr(card_template, "image_url", None)
        or (card_data or {}).get("image_url")
    )
    if image_url:
        return image_url

    aliases = (card_data or {}).get("image_aliases") or []
    card_name = getattr(card_template, "name", None) or (card_data or {}).get("name")
    return resolve_card_image_path(card_name, aliases=aliases)
