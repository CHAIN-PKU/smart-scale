# 通信协议 V1

STM32 和 PC 之间只传 **一行一个 JSON**。不要传裸重量，例如 `123.45`。

以后换 USB、以太网或另一块板，只要仍是这些 JSON 行，主机里的视觉和计价都不用改。改字段含义必须升版本，不能偷偷改 V1。

## 链路

| 项目 | V1 取值 |
|---|---|
| 编码 | UTF-8 |
| 帧 | 一个 JSON 对象，然后一个 `\n` |
| 行尾 | 接收方去掉末尾的 `\r`。所以 `\n` 和 `\r\n` 都可以 |
| 空行 | 忽略，不当成错误 |
| 一行长度 | 不含换行，最多 512 字节 |
| 串口 | 115200，8 数据位，无校验，1 停止位，无流控 |

一行里只能有一个 JSON。不要把 JSON 排成多行。

## 方向

| 方向 | `type` | 作用 |
|---|---|---|
| STM32 → PC | `weight` | 一次称重读数 |
| STM32 → PC | `status` | 秤的状态，取值见下方枚举 |
| STM32 → PC | `ack` | 对 PC 命令的回复 |
| PC → STM32 | `command` | 命令。V1 只有 `tare` |
| PC → STM32 | `display_result` | 要显示的商品和价格 |

STM32 发出的 `weight`、`status`、`ack` 共用一个 `seq`，每发一条加 1，到 4294967295 后回到 0。PC 发出的消息用 `request_id`，不用 `seq`。

`timestamp_ms` 是 MCU 从上电开始的毫秒数，不是日期时间。

## 兼容规则

- `v` 必须是数字 `1`。字符串 `"1"`、布尔 `true` 都算错。
- 规定的字段必须在，类型必须对。
- 不认识的额外字段要忽略，不要因为多了字段就丢弃整条消息。
- 不认识的 `type`，或 `v` 不是 1，整条拒绝。
- 数字不能是字符串。`326.4` 可以，`"326.4"` 不行。

## STM32 → PC：`weight`

净重已经减去去皮偏移。`tare_g` 是当前减掉的克数，不是一条命令。

| 字段 | 类型 | 含义 |
|---|---|---|
| `v` | 数字 `1` | 协议版本 |
| `type` | 字符串 `weight` | 消息类型 |
| `seq` | 整数，≥ 0 | 发送序号 |
| `timestamp_ms` | 整数，≥ 0 | 上电后的毫秒 |
| `weight_g` | 有限数字 | 净重，克 |
| `stable` | 布尔 | 这次读数是否已经稳定 |
| `tare_g` | 有限数字 | 当前去皮偏移，克 |
| `status` | `ok`、`overload`、`error` | `overload` 和 `error` 时，主机不得把 `weight_g` 当成有效商品重量 |

```json
{"v":1,"type":"weight","seq":182,"timestamp_ms":192839,"weight_g":326.4,"stable":true,"tare_g":12.7,"status":"ok"}
```

## STM32 → PC：`status`

| 字段 | 类型 | 含义 |
|---|---|---|
| `v` | 数字 `1` | 协议版本 |
| `type` | 字符串 `status` | 消息类型 |
| `seq` | 整数，≥ 0 | 发送序号 |
| `timestamp_ms` | 整数，≥ 0 | 上电后的毫秒 |
| `state` | 下列字符串之一 | 秤现在处于哪个状态 |
| `detail` | 字符串，可选，最多 64 字符 | 仅 `ERROR` 时使用。没有这个字段也可以 |

`state` 只能是：

`BOOT`、`READY`、`ZERO`、`WEIGHT_CHANGED`、`WEIGHT_STABLE`、`WEIGHT_REMOVED`、`OVERLOAD`、`ERROR`

何时进入这些状态，写在 `state-machine.md`。本文只规定线上的拼写。

```json
{"v":1,"type":"status","seq":2,"timestamp_ms":40,"state":"READY"}
```

## STM32 → PC：`ack`

| 字段 | 类型 | 含义 |
|---|---|---|
| `v` | 数字 `1` | 协议版本 |
| `type` | 字符串 `ack` | 消息类型 |
| `seq` | 整数，≥ 0 | 发送序号 |
| `timestamp_ms` | 整数，≥ 0 | 上电后的毫秒 |
| `command` | 字符串 | 去皮回复是 `tare`。保存成功或失败是 `save` |
| `status` | `ok` 或 `error` | 命令是否执行成功 |

```json
{"v":1,"type":"ack","seq":183,"timestamp_ms":193100,"command":"tare","status":"ok"}
```

## PC → STM32：`command`

| 字段 | 类型 | 含义 |
|---|---|---|
| `v` | 数字 `1` | 协议版本 |
| `type` | 字符串 `command` | 消息类型 |
| `command` | 字符串 `tare` | 电脑发给板子时，V1 只允许去皮。板子发给电脑的命令见下文 |

```json
{"v":1,"type":"command","command":"tare"}
```

收到合法的 `tare` 后，STM32 做去皮，再发一条 `ack`。去皮后的读数仍用 `weight` 上报，并带上新的 `tare_g`。`reboot` 仍然整条拒绝。

## PC → STM32：`display_result`

价格是人民币元。`weight_g` 是这次计价使用的净重。

| 字段 | 类型 | 含义 |
|---|---|---|
| `v` | 数字 `1` | 协议版本 |
| `type` | 字符串 `display_result` | 消息类型 |
| `request_id` | 非空字符串，最多 32 字符 | PC 自己的编号 |
| `product` | 非空字符串，最多 64 字符 | 商品名。短表发英文：banana、apple、orange、mandarin、pear、grape、watermelon、strawberry、peach、kiwi、pineapple、cantaloupe。板子显示中文 |
| `weight_g` | 有限数字 | 计价重量，克 |
| `price` | 有限数字，≥ 0 | 这一份的金额，元 |
| `price_per_kg` | 有限数字，≥ 0，可省略 | 单价，元每千克 |
| `portion_kcal` | 有限数字，≥ 0，可省略 | 这一份的热量，千卡 |
| `portion_carb_g` | 有限数字，≥ 0，可省略 | 这一份的碳水，克 |
| `portion_fiber_g` | 有限数字，≥ 0，可省略 | 这一份的膳食纤维，克 |

没有单价或营养时，不写出空字段。板子把商品名、单价、重量、金额和这一份营养画在同一屏，不再用营养键翻页。整屏字号小于原来的三行大字。商品名和金额更大，单价、重量、千卡、碳水和膳食纤维更小。语音仍只念商品名、克数、金额。

```json
{"v":1,"type":"display_result","request_id":"r_001","product":"banana","weight_g":326.4,"price":3.92,"price_per_kg":12,"portion_kcal":297,"portion_carb_g":71.8,"portion_fiber_g":3.9}
```

没有营养数时可以不带那三项：

```json
{"v":1,"type":"display_result","request_id":"r_001","product":"banana","weight_g":326.4,"price":3.92,"price_per_kg":12}
```

## STM32 → PC：`save`、`receipt`、`clear`

这三条和去皮用同一个 `type`，方向相反。电脑不会把这三条发给板子。板上只有四个键：去皮、保存、清单、清空。没有营养键。

| 键 | 丝印 | 引脚 | 发给电脑 |
|---|---|---|---|
| 去皮 | 原有按键 | PA1 | 板子自己去皮，不发 `save` |
| 保存 | SW2 | PE6 | `{"v":1,"type":"command","command":"save"}` |
| 清单 | SW3 | PE7 | `{"v":1,"type":"command","command":"receipt"}` |
| 清空 | SW4 | PC6 | `{"v":1,"type":"command","command":"clear"}` |

按下才发一条，松手不重复发。这三只脚不要改去皮 PA1、串口 PA9/PA10、语音 PA2/PA3、HX711 PB0/PB1 和屏幕 PB9–PB15。

| 字段 | 类型 | 含义 |
|---|---|---|
| `v` | 数字 `1` | 协议版本 |
| `type` | 字符串 `command` | 消息类型 |
| `command` | `save`、`receipt` 或 `clear` | 保存当前这一笔、调出清单、清空清单 |

```json
{"v":1,"type":"command","command":"save"}
```

当前称重仍自动发 `display_result`，但不自动进入清单。`save` 把当前这一笔加一行，同一笔可以按多次，每次加一行。没有当前计价时，电脑回 `ack`，`command` 为 `save`，`status` 为 `error`，清单不变。保存成功回 `status` 为 `ok`。

`receipt` 和 `clear` 都回 `receipt_result`。`clear` 先把清单删空。

## PC → STM32：`receipt_result`

清单不含营养。按保存顺序编号，从 1 开始。每一行有序号、名称、单价、重量、价格。合计是各行价格之和。

240×320 的清单页按下面排，一行一条，不要把一条拆成两行。字号小于计价屏里较小的那一档。数字右对齐，名称左对齐。合计单独占最底一行，和价格列对齐。没有记录时只留下标题和合计 0.00 元。

```text
清单
序号  名称     单价       重量      价格
1    banana   12元/kg   326.4克   3.92元
2    banana   12元/kg   221.4克   2.66元
合计                              6.58元
```

| 字段 | 类型 | 含义 |
|---|---|---|
| `v` | 数字 `1` | 协议版本 |
| `type` | 字符串 `receipt_result` | 消息类型 |
| `items` | 数组 | 按序号排列 |
| `items[].n` | 整数，≥ 1 | 序号，第一条是 1 |
| `items[].product` | 字符串 | 名称。发给板子的仍是 banana |
| `items[].price_per_kg` | 有限数字，≥ 0 | 单价，元每千克 |
| `items[].weight_g` | 有限数字 | 重量，克 |
| `items[].price` | 有限数字，≥ 0 | 这一行的价格，元 |
| `total` | 有限数字，≥ 0 | 价格合计，元 |

```json
{"v":1,"type":"receipt_result","items":[{"n":1,"product":"banana","price_per_kg":12,"weight_g":326.4,"price":3.92},{"n":2,"product":"banana","price_per_kg":12,"weight_g":221.4,"price":2.66}],"total":6.58}
```

清空后：

```json
{"v":1,"type":"receipt_result","items":[],"total":0}
```

以前的称重记录不自动放进这张清单。

## 必须拒绝的例子

解析器遇到下表时丢掉这一行，不把它变成称重数据。空行除外。

| 输入 | 原因 |
|---|---|
| `123.45` | 不是 JSON 对象 |
| `{` | JSON 不完整 |
| `[]` | 必须是对象，不能是数组 |
| `{"type":"weight"}` | 缺 `v`，也缺称重字段 |
| `{"v":"1","type":"weight","seq":1,"timestamp_ms":0,"weight_g":1,"stable":true,"tare_g":0,"status":"ok"}` | `v` 是字符串 |
| `{"v":2,"type":"weight","seq":1,"timestamp_ms":0,"weight_g":1,"stable":true,"tare_g":0,"status":"ok"}` | 版本不是 1 |
| `{"v":1,"type":"picture"}` | 未知 `type` |
| `{"v":1,"type":"weight","seq":1,"timestamp_ms":0,"weight_g":"326.4","stable":true,"tare_g":0,"status":"ok"}` | `weight_g` 是字符串 |
| `{"v":1,"type":"command","command":"reboot"}` | V1 没有这条命令 |
| `{"v":1,"type":"weight",...}{"v":1,"type":"weight",...}` | 一行里两个 JSON |

这一行合法。多出来的 `note` 要忽略，其余照常使用：

```json
{"v":1,"type":"weight","seq":1,"timestamp_ms":0,"weight_g":1,"stable":false,"tare_g":0,"status":"ok","note":"ignore-me"}
```

## V1 不包含

不传图片，不传商品数据库，不传模型名称。识别和计价在 PC 上完成。`display_result` 可以带这一份的千卡、碳水和膳食纤维。清单只由板子的 `save`、`receipt`、`clear` 控制。
