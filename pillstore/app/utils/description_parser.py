import json
import re

from app.models.products import Product

IHERB_DISCLAIMER = (
    "Обратите внимание, что некоторые из описаний продуктов на нашем сайте выполнены с использованием "
    "машинного перевода. Это сделано исключительно для вашего удобства. iHerb не гарантирует, что переводы "
    "являются полными и безошибочными, и не несет ответственности за ошибки или неточности при переводе. "
    "Посетить веб-сайт производителя"
)
SECTION_HEADERS = (
    "Описание",
    "О продукте",
    "Другие ингредиенты",
    "Ингредиенты",
    "Рекомендации по применению",
    "Предупреждение об аллергенах",
    "Предупреждения",
    "Отказ от ответственности",
    "Производитель",
)
SKIP_SECTIONS = {"Отказ от ответственности", "Производитель"}


def _strip_disclaimer(text: str) -> str:
    if not (text or "").strip():
        return text or ""
    s = (text or "").replace(IHERB_DISCLAIMER, "").strip()
    return re.sub(r"\s+", " ", s) if s else ""


def split_text_by_section_headers(text: str) -> list[dict]:
    if not (text or "").strip():
        return []
    text = text.strip()
    pattern = "|".join(re.escape(h) for h in SECTION_HEADERS)
    positions = []
    for m in re.finditer(pattern, text):
        positions.append((m.start(), m.group(0).strip(), m.end()))
    positions.sort(key=lambda x: x[0])
    result = []
    for i, (start, header, end) in enumerate(positions):
        if header in SKIP_SECTIONS:
            continue
        end_next = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        content = text[end:end_next].strip()
        content = _strip_disclaimer(content)
        if not content:
            continue
        lines = [s.strip() for s in content.split("\n") if s.strip()]
        result.append({"title": header, "content": lines if lines else [content]})
    if not positions and text:
        intro = _strip_disclaimer(text)
        if intro:
            result.append({"title": "Описание", "content": [intro]})
    elif positions and positions[0][0] > 0:
        intro = _strip_disclaimer(text[: positions[0][0]].strip())
        if intro:
            result.insert(0, {"title": "Описание", "content": [intro]})
    return result


def split_right_column_text(text: str) -> list[dict]:
    if not (text or "").strip():
        return []
    text = (text or "").replace("‡", "").replace("**", "").replace("† †", "†").strip()
    parts = re.split(r"\s+(?=[А-ЯA-Z])", text)
    items = [s.strip() for s in parts if s.strip()]
    if not items:
        items = [text]
    return [{"title": "Пищевая ценность", "content": items}]


def sections_to_ordered_dict(left_sections: list, right_sections: list) -> dict:
    cleaned = {}
    for sec in left_sections:
        if not isinstance(sec, dict) or "title" not in sec or "content" not in sec:
            continue
        cleaned[sec["title"]] = [_strip_disclaimer(str(c)) for c in sec["content"]]
    for sec in right_sections:
        if not isinstance(sec, dict) or "title" not in sec or "content" not in sec:
            continue
        cleaned[sec["title"]] = [_strip_disclaimer(str(c)) for c in sec["content"]]
    return cleaned


async def formatted_description(product: Product) -> dict:
    left_raw = (product.description_left or "").strip()
    right_raw = (product.description_right or "").strip()
    left_sections = []
    right_sections = []

    if left_raw.startswith("["):
        try:
            left_sections = json.loads(left_raw)
        except (json.JSONDecodeError, TypeError):
            left_raw = ""
    if right_raw.startswith("["):
        try:
            right_sections = json.loads(right_raw)
        except (json.JSONDecodeError, TypeError):
            right_raw = ""

    if not left_sections and left_raw:
        left_sections = split_text_by_section_headers(left_raw)
    if not right_sections and right_raw:
        right_sections = split_right_column_text(right_raw)

    if not left_sections and not right_sections:
        return {}

    return sections_to_ordered_dict(left_sections or [], right_sections or [])
