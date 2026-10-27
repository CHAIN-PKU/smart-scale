"""Print the defense card and write a local page. No network and no COM port."""

from __future__ import annotations

import asyncio
import sys
from html import escape
from pathlib import Path

from scale_host.catalog import TableProductInfo
from scale_host.device.simulator import SimulatedScaleDevice
from scale_host.domain import ScaleStatus
from scale_host.fusion import Sale, portion_from_100g
from scale_host.live_view import LIVE_FRAME, price_current_view
from scale_host.speech import announcement
from scale_host.vision.interface import MockVision

# The 2026-10-13 COM4 result. It is not the weight of the later banana photo.
REAL_WEIGHT_G = 220.3
REAL_AMOUNT_YUAN = 2.64
PAGE_PATH = Path("docs/defense-card.html")
TFT_MODEL = "3.2 TFT SPI 240×320 v1.0"
TFT_LIT = "2026-10-27"
_SCREEN_NAMES = {"banana": "香蕉", "香蕉": "香蕉"}


def real_portion() -> tuple[float, float]:
    info = TableProductInfo().lookup("banana")
    kcal = portion_from_100g(REAL_WEIGHT_G, info.kcal_per_100g or 0)
    carb = portion_from_100g(REAL_WEIGHT_G, info.carb_per_100g or 0)
    return kcal, carb


def screen_lines(sale: Sale) -> list[str]:
    name = _SCREEN_NAMES.get(sale.label, sale.label)
    return [name, f"{sale.weight_g:g} 克", f"{sale.amount_yuan:.2f} 元"]


async def live_sale() -> Sale:
    result = await price_current_view(SimulatedScaleDevice("banana"), MockVision())
    if (
        result.sale is None
        or result.recognized_at is None
        or result.recognized_at.state is not ScaleStatus.WEIGHT_STABLE
    ):
        raise RuntimeError("weight is not ready to price")
    return result.sale


async def card_lines() -> list[str]:
    sale = await live_sale()
    lines = screen_lines(sale)
    real_kcal, real_carb = real_portion()
    return [
        "screen:",
        f"product: {sale.label}",
        f"weight_g: {sale.weight_g}",
        f"price: {sale.amount_yuan:.2f}",
        f"frame: {LIVE_FRAME}",
        "recognized_when: WEIGHT_STABLE",
        f"tft: {TFT_MODEL}",
        f"tft_lit: {TFT_LIT}",
        "formal_screen:",
        *lines,
        "computer:",
        f"portion_kcal: {sale.portion_kcal}",
        f"portion_carb_g: {sale.portion_carb_g}",
        f"spoken_line: {announcement(sale)}",
        "real_weight_g: 220.3",
        "real_amount_yuan: 2.64",
        f"real_portion_kcal: {real_kcal}",
        f"real_portion_carb_g: {real_carb}",
        "sent_to_internet: no",
        "com_open: no",
    ]


def render_page(sale: Sale) -> str:
    name, weight, price = screen_lines(sale)
    real_kcal, real_carb = real_portion()
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>智能电子秤</title>
  <style>
    body {{ margin: 0; font-family: "Microsoft YaHei", sans-serif; background: #f4f7fb; color: #1c2833; }}
    main {{ max-width: 720px; margin: 32px auto; padding: 0 20px 40px; }}
    h1 {{ margin: 0 0 8px; color: #1f4e79; }}
    h2 {{ margin: 28px 0 8px; font-size: 18px; color: #1f4e79; }}
    p {{ line-height: 1.6; }}
    .panel {{ background: white; border: 1px solid #d0d7de; border-radius: 12px; padding: 16px 20px; }}
    .big {{ font-size: 28px; font-weight: 700; margin: 8px 0; }}
    .muted {{ color: #5b6770; }}
  </style>
</head>
<body>
  <main>
    <h1>智能电子秤</h1>
    <p class="muted">电脑上的对照页。正式屏幕是秤上的 {escape(TFT_MODEL)}，那里只显示下面这三行。</p>
    <h2>正式屏幕</h2>
    <section class="panel">
      <div class="big">{escape(name)}</div>
      <div class="big">{escape(weight)}</div>
      <div class="big">{escape(price)}</div>
      <p class="muted">{escape(TFT_LIT)} 这块屏已经点亮，能显示克重。上面三行是它要显示的商品名、克数和金额。这一屏来自放稳时的当前画面，不是事先上传的照片。热量和碳水留在下面的电脑区。发给板子的 product 仍是 {escape(sale.label)}。</p>
    </section>
    <h2>这次模拟的一屏</h2>
    <section class="panel">
      <div>商品名 {escape(sale.label)}</div>
      <div class="big">{sale.weight_g:g} 克</div>
      <div class="big">{sale.amount_yuan:.2f} 元</div>
      <p>电脑会念：{escape(announcement(sale))}。热量和碳水不念。</p>
      <p>热量 {sale.portion_kcal:g} 千卡，碳水 {sale.portion_carb_g:g} 克。这两项留在电脑上，不发给板子。</p>
    </section>
    <h2>真秤已经测过</h2>
    <section class="panel">
      <p>2026-10-13，COM4。放稳 {REAL_WEIGHT_G:g} 克，金额 {REAL_AMOUNT_YUAN:.2f} 元。当时名字用的是演示香蕉，不是后来这张照片。秤上就是现在这只托盘，标定保持那一次的零点和每克系数。</p>
      <p>按短表，这一份是 {real_kcal:g} 千卡，碳水 {real_carb:g} 克。这两项留在电脑上，不发给板子。</p>
    </section>
    <h2>照片</h2>
    <section class="panel">
      <p>香蕉照片已经认出，名字是 banana。贴纸那张没有食物，没有出价。</p>
    </section>
  </main>
</body>
</html>
"""


def write_page(sale: Sale, path: Path = PAGE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_page(sale), encoding="utf-8")
    return path


def main() -> None:
    try:
        sale = asyncio.run(live_sale())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    path = write_page(sale)
    print(f"product: {sale.label}")
    print(f"weight_g: {sale.weight_g}")
    print(f"price: {sale.amount_yuan:.2f}")
    print(f"portion_kcal: {sale.portion_kcal}")
    print(f"portion_carb_g: {sale.portion_carb_g}")
    print(f"spoken_line: {announcement(sale)}")
    print(f"page: {path.as_posix()}")
    print("sent_to_internet: no")


if __name__ == "__main__":
    main()
    sys.exit(0)
