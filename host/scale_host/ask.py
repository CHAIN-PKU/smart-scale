"""Answer a short question from the local table and saved weighings. No network."""

from __future__ import annotations

import os
import re
import sys

from dotenv import load_dotenv

from scale_host.catalog import TableProductInfo
from scale_host.fusion import portion_from_100g, yuan_amount
from scale_host.storage import SqliteRepository, WeighingSession

_GRAMS = re.compile(r"(\d+(?:\.\d+)?)\s*克")
_BANANA = ("banana", "香蕉")


def answer(question: str, sessions: list[WeighingSession] | None = None) -> str:
    text = question.strip()
    if _asks_history(text):
        return _history(sessions or [])
    grams = _GRAMS.search(text)
    if grams and _is_banana(text):
        return _portion(float(grams.group(1)))
    if _is_banana(text):
        return _unit_price()
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


def _asks_history(text: str) -> bool:
    return any(word in text for word in ("上次", "最近", "历史"))


def _is_banana(text: str) -> bool:
    folded = text.casefold()
    return any(name.casefold() in folded for name in _BANANA)


def _unit_price() -> str:
    info = TableProductInfo().lookup("banana")
    return (
        f"香蕉：每千克 {info.price_per_kg:g} 元，"
        f"每 100 克 {info.kcal_per_100g:g} 千卡，碳水 {info.carb_per_100g:g} 克。"
    )


def _portion(weight_g: float) -> str:
    info = TableProductInfo().lookup("banana")
    amount = yuan_amount(weight_g, info.price_per_kg or 0)
    kcal = portion_from_100g(weight_g, info.kcal_per_100g or 0)
    carb = portion_from_100g(weight_g, info.carb_per_100g or 0)
    return f"{weight_g:g} 克香蕉：{amount:.2f} 元，{kcal:g} 千卡，碳水 {carb:g} 克。"


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
    if kcal is None or carb is None:
        label = session.label or ""
        if not _is_banana(label) or session.weight_g <= 0:
            return ""
        info = TableProductInfo().lookup("banana")
        kcal = portion_from_100g(session.weight_g, info.kcal_per_100g or 0)
        carb = portion_from_100g(session.weight_g, info.carb_per_100g or 0)
    return f"，{kcal:g} 千卡，碳水 {carb:g} 克"


def _saved_sessions() -> list[WeighingSession]:
    path = os.getenv("DATABASE_PATH", "data/scale.db")
    if not os.path.exists(path):
        return []
    return SqliteRepository(path).list_sessions(limit=1)


if __name__ == "__main__":
    main()
