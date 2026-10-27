"""Opt-in receipt. A weighing is shown immediately and enters this list only on save."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from scale_host.fusion import Sale
from scale_host.protocol.messages import AckMessage, ReceiptItem, ReceiptResultMessage

_MODEL_CONFIG = ConfigDict(extra="forbid")
_FEN = Decimal("0.01")


class ReceiptLine(BaseModel):
    model_config = _MODEL_CONFIG
    product: str = Field(min_length=1)
    price_per_kg: float = Field(ge=0)
    weight_g: float = Field(gt=0)
    price: float = Field(ge=0)


class ReceiptBook:
    def __init__(self, lines: list[ReceiptLine] | None = None) -> None:
        self.lines = list(lines or [])
        self.current: Sale | None = None

    @classmethod
    def from_rows(cls, rows: list[tuple[str, float, float, float]]) -> ReceiptBook:
        return cls(
            [
                ReceiptLine(product=product, price_per_kg=price_per_kg, weight_g=weight_g, price=price)
                for product, weight_g, price, price_per_kg in rows
            ]
        )

    def forget(self) -> None:
        self.current = None

    def remember(self, sale: Sale) -> None:
        self.current = sale

    def rows(self) -> list[tuple[str, float, float, float]]:
        return [(line.product, line.weight_g, line.price, line.price_per_kg) for line in self.lines]

    def apply(self, command: str) -> AckMessage | ReceiptResultMessage:
        if command == "save":
            if self.current is None:
                return _save_ack("error")
            self.lines.append(
                ReceiptLine(
                    product=self.current.label,
                    price_per_kg=self.current.price_per_kg,
                    weight_g=self.current.weight_g,
                    price=self.current.amount_yuan,
                )
            )
            return _save_ack("ok")
        if command == "clear":
            self.lines.clear()
            return self.result()
        if command == "receipt":
            return self.result()
        raise ValueError(command)

    def result(self) -> ReceiptResultMessage:
        amount = sum((Decimal(str(line.price)) for line in self.lines), Decimal("0"))
        total = float(amount.quantize(_FEN, rounding=ROUND_HALF_UP))
        return ReceiptResultMessage(
            v=1,
            type="receipt_result",
            items=[
                ReceiptItem(
                    n=index,
                    product=line.product,
                    price_per_kg=line.price_per_kg,
                    weight_g=line.weight_g,
                    price=line.price,
                )
                for index, line in enumerate(self.lines, start=1)
            ],
            total=total,
        )


def _save_ack(status: Literal["ok", "error"]) -> AckMessage:
    return AckMessage(v=1, type="ack", seq=0, timestamp_ms=0, command="save", status=status)
