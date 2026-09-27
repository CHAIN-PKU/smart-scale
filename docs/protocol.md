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
| `command` | 字符串 | 回复的是哪条命令。V1 只有 `tare` |
| `status` | `ok` 或 `error` | 命令是否执行成功 |

```json
{"v":1,"type":"ack","seq":183,"timestamp_ms":193100,"command":"tare","status":"ok"}
```

## PC → STM32：`command`

| 字段 | 类型 | 含义 |
|---|---|---|
| `v` | 数字 `1` | 协议版本 |
| `type` | 字符串 `command` | 消息类型 |
| `command` | 字符串 `tare` | V1 只允许去皮。别的字符串整条拒绝 |

```json
{"v":1,"type":"command","command":"tare"}
```

收到合法的 `tare` 后，STM32 做去皮，再发一条 `ack`。去皮后的读数仍用 `weight` 上报，并带上新的 `tare_g`。

## PC → STM32：`display_result`

价格是人民币元。`weight_g` 是这次计价使用的净重。

| 字段 | 类型 | 含义 |
|---|---|---|
| `v` | 数字 `1` | 协议版本 |
| `type` | 字符串 `display_result` | 消息类型 |
| `request_id` | 非空字符串，最多 32 字符 | PC 自己的编号 |
| `product` | 非空字符串，最多 64 字符 | 商品名 |
| `weight_g` | 有限数字 | 计价重量，克 |
| `price` | 有限数字，≥ 0 | 金额，元 |

```json
{"v":1,"type":"display_result","request_id":"r_001","product":"banana","weight_g":326.4,"price":3.92}
```

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

不传图片，不传商品数据库，不传模型名称。识别和计价在 PC 上完成，只把 `display_result` 送回 STM32 显示。
