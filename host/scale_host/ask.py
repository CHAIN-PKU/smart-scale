"""Answer a short question from the local table and saved weighings. No network."""

from __future__ import annotations

import os
import re
import sys

from dotenv import load_dotenv

from scale_host.catalog import TableProductInfo
from scale_host.catalog.lookup import ProductInfo, food_from_text, spoken_name
from scale_host.fusion import portion_from_100g, yuan_amount
from scale_host.storage import SqliteRepository, WeighingSession

_GRAMS = re.compile(r"(\d+(?:\.\d+)?)\s*克")
_BANANA = ("banana", "香蕉")


def answer(question: str, sessions: list[WeighingSession] | None = None) -> str:
    text = question.strip()
    if _asks_screen(text):
        return _screen(sessions or [])
    if _asks_history(text):
        return _history(sessions or [])
    grams = _GRAMS.search(text)
    food = food_from_text(text)
    if grams and food is not None:
        return _portion(float(grams.group(1)), food)
    if food is not None:
        return _unit_price(food)
    if text:
        return "短表里没有这个名字，不出价。"
    return "可以问香蕉的单价，或者问最近一次称重。"


def main() -> None:
    load_dotenv(override=False)
    question = " ".join(sys.argv[1:]).strip()
    sessions = _saved_sessions()
    if not question:
        question = "香蕉多少钱"
    print(answer(question, sessions))
    print("sent_to_internet: no")


def _asks_screen(text: str) -> bool:
    return "屏幕" in text


def _asks_history(text: str) -> bool:
    return any(word in text for word in ("上次", "最近", "历史"))


def screen_line(
    label: str | None,
    weight_g: float,
    amount_yuan: float,
    *,
    price_per_kg: float | None = None,
    portion_kcal: float | None = None,
    portion_carb_g: float | None = None,
    portion_fiber_g: float | None = None,
) -> str:
    name = spoken_name(label) if label else "未知"
    parts = [name]
    if price_per_kg is not None:
        parts.append(f"每千克{price_per_kg:g}元")
    parts.append(f"{weight_g:g}克")
    parts.append(f"{amount_yuan:.2f}元")
    if portion_kcal is not None:
        parts.append(f"{portion_kcal:g}千卡")
    if portion_carb_g is not None:
        parts.append(f"碳水{portion_carb_g:g}克")
    if portion_fiber_g is not None:
        parts.append(f"膳食纤维{portion_fiber_g:g}克")
    return "、".join(parts)


def _screen(sessions: list[WeighingSession]) -> str:
    if not sessions:
        return "屏幕上还没有结果。"
    latest = sessions[0]
    if latest.amount_yuan is None:
        return "屏幕上还没有金额。"
    price_per_kg = latest.price_per_kg
    kcal = latest.portion_kcal
    carb = latest.portion_carb_g
    fiber = latest.portion_fiber_g
    if _is_banana(latest.label or "") and latest.weight_g > 0:
        info = TableProductInfo().lookup("banana")
        if price_per_kg is None:
            price_per_kg = info.price_per_kg
        if kcal is None:
            kcal = portion_from_100g(latest.weight_g, info.kcal_per_100g or 0)
        if carb is None:
            carb = portion_from_100g(latest.weight_g, info.carb_per_100g or 0)
        if fiber is None:
            fiber = portion_from_100g(latest.weight_g, info.fiber_per_100g or 0)
    return screen_line(
        latest.label,
        latest.weight_g,
        latest.amount_yuan,
        price_per_kg=price_per_kg,
        portion_kcal=kcal,
        portion_carb_g=carb,
        portion_fiber_g=fiber,
    )


def _is_banana(text: str) -> bool:
    folded = text.casefold()
    return any(name.casefold() in folded for name in _BANANA)


def _unit_price(info: ProductInfo) -> str:
    name = spoken_name(info.label)
    return (
        f"{name}：每千克 {info.price_per_kg:g} 元，"
        f"每 100 克 {info.kcal_per_100g:g} 千卡，碳水 {info.carb_per_100g:g} 克，"
        f"膳食纤维 {info.fiber_per_100g:g} 克。"
    )


def _portion(weight_g: float, info: ProductInfo) -> str:
    name = spoken_name(info.label)
    amount = yuan_amount(weight_g, info.price_per_kg or 0)
    kcal = portion_from_100g(weight_g, info.kcal_per_100g or 0)
    carb = portion_from_100g(weight_g, info.carb_per_100g or 0)
    fiber = portion_from_100g(weight_g, info.fiber_per_100g or 0)
    return (
        f"{weight_g:g} 克{name}：{amount:.2f} 元，{kcal:g} 千卡，"
        f"碳水 {carb:g} 克，膳食纤维 {fiber:g} 克。"
    )


def _history(sessions: list[WeighingSession]) -> str:
    if not sessions:
        return "还没有称重记录。"
    latest = sessions[0]
    amount = "" if latest.amount_yuan is None else f"，{latest.amount_yuan:.2f} 元"
    nutrition = _history_nutrition(latest)
    return f"最近一次：{latest.label}，{latest.weight_g:g} 克{amount}{nutrition}。"


def _history_nutrition(session: WeighingSession) -> str:
    kcal = session.portion_kcal
    carb = session.portion_carb_g
    fiber = session.portion_fiber_g
    label = session.label or ""
    if _is_banana(label) and session.weight_g > 0:
        info = TableProductInfo().lookup("banana")
        if kcal is None:
            kcal = portion_from_100g(session.weight_g, info.kcal_per_100g or 0)
        if carb is None:
            carb = portion_from_100g(session.weight_g, info.carb_per_100g or 0)
        if fiber is None:
            fiber = portion_from_100g(session.weight_g, info.fiber_per_100g or 0)
    if kcal is None or carb is None:
        return ""
    text = f"，{kcal:g} 千卡，碳水 {carb:g} 克"
    if fiber is not None:
        text += f"，膳食纤维 {fiber:g} 克"
    return text


def _saved_sessions() -> list[WeighingSession]:
    path = os.getenv("DATABASE_PATH", "data/scale.db")
    if not os.path.exists(path):
        return []
    return SqliteRepository(path).list_sessions(limit=1)


if __name__ == "__main__":
    main()
