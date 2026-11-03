"""Answer a request for saved weighings or the current receipt.

The scale board does not store this list. The computer does.
"""

from __future__ import annotations

import json

from scale_host.catalog.lookup import spoken_name
from scale_host.receipt import ReceiptBook
from scale_host.storage import SqliteRepository

_RECORDS = {"records", "record", "记录", "称重", "称重记录"}
_RECEIPT = {"receipt", "清单", "小票"}


def records_payload(repository: SqliteRepository, limit: int = 20, *, compact: bool = False) -> dict:
    items = []
    for session in repository.list_sessions(limit):
        label = session.label or ""
        name = spoken_name(label) if label else ""
        if compact:
            items.append(
                {
                    "name": name,
                    "weight_g": session.weight_g,
                    "price": session.amount_yuan,
                }
            )
        else:
            items.append(
                {
                    "product": label,
                    "name": name,
                    "weight_g": session.weight_g,
                    "price": session.amount_yuan,
                    "price_per_kg": session.price_per_kg,
                    "portion_kcal": session.portion_kcal,
                    "portion_carb_g": session.portion_carb_g,
                    "portion_fiber_g": session.portion_fiber_g,
                    "timestamp": session.timestamp,
                }
            )
    return {"v": 1, "type": "records_result", "items": items}


def receipt_payload(repository: SqliteRepository) -> dict:
    book = ReceiptBook.from_rows(repository.list_receipt_lines())
    return book.result().model_dump()


def answer_query(repository: SqliteRepository, query: str, *, compact: bool = False) -> dict:
    text = query.strip()
    folded = text.casefold()
    if folded in _RECORDS or text in _RECORDS:
        return records_payload(repository, limit=5 if compact else 20, compact=compact)
    if folded in _RECEIPT or text in _RECEIPT:
        return receipt_payload(repository)
    return {"v": 1, "type": "query_result", "status": "error"}


def wifi_page(repository: SqliteRepository, query: str) -> dict:
    """One short line the scale can forward to a phone. The board drops lines over 512 bytes."""
    payload = answer_query(repository, query, compact=True)
    if payload["type"] == "records_result":
        parts = [
            f"{item['name']}|{item['weight_g']}|{item['price']:.2f}"
            for item in payload["items"]
            if item["price"] is not None
        ]
        text = "" if not parts else ";".join(parts)
    elif payload["type"] == "receipt_result":
        parts = [
            f"{item['n']} {spoken_name(item['product'])}|{item['weight_g']}|{item['price']:.2f}"
            for item in payload["items"]
        ]
        text = ("" if not parts else ";".join(parts)) + f"#{payload['total']:.2f}"
    else:
        text = "不能查询。"
    return {"v": 1, "type": "wifi_page", "text": text}


def reply_line(repository: SqliteRepository, line: str) -> str | None:
    """One incoming line, one JSON line back. Ignore blanks and AT noise."""
    text = line.strip()
    if text == "" or text.startswith("#"):
        return None
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return _dump({"v": 1, "type": "query_result", "status": "error"})
        if not isinstance(payload, dict) or payload.get("type") != "query":
            return None
        query = payload.get("query", "")
        if not isinstance(query, str):
            return _dump({"v": 1, "type": "query_result", "status": "error"})
        return _dump(answer_query(repository, query))
    folded = text.casefold()
    if folded not in _RECORDS and text not in _RECORDS and folded not in _RECEIPT and text not in _RECEIPT:
        return None
    return _dump(answer_query(repository, text))


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
