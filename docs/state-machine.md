# 称重状态机 V1

这份文档只规定 STM32 上的称重状态。电脑上的识别、计价、数据库都不在这里。

状态名字必须和 `protocol.md` 里的 `state` 完全一致。进入一个新状态时发一条 `status`。状态没变就不要重复发。

每一次 HX711 给出新样本，就发一条 `weight`。常见模块是 10 Hz，大约 100 ms 一条。不要为了凑频率在没有新样本时补发。

状态机使用的重量是滤波之后的净重，单位克。滤波算法由固件自己定。

## 上电不要自动去皮

收到 PC 的 `{"v":1,"type":"command","command":"tare"}` 才做去皮。

上电时如果秤上已经有东西，要把它报成重量，不能把它清成 0。标定得到的比例系数和偏移，掉电后可以先不保存；保存放到以后做。没有保存之前，每次上电用固件里写死的比例系数，偏移保持上次运行留下的值；程序刚烧进去、还没有任何值时，偏移用 0。

## 可调参数

下面的数是初值。换传感器后可以改，但改完要告诉 PC 侧，模拟器要用同一组数。

| 名字 | 初值 | 含义 |
|---|---|---|
| `zero_band_g` | 2 | 净重绝对值不超过这个数，看成秤上没有东西 |
| `stable_delta_g` | 0.5 | 窗口里最大值减最小值不超过这个数，才叫稳定 |
| `stable_window_ms` | 500 | 要连续这么久都满足上面的条件 |
| `sample_count` | 5 | 10 Hz 时，500 ms 大约是 5 个新样本 |
| `overload_g` | 待硬件确认 | 超过传感器可用量程就进入 `OVERLOAD`。量程没定之前，先不要把某个大数写死成交货标准 |

`overload_g` 用传感器满量程的 90%。满量程以硬件同学确认的型号为准。

## 状态怎么走

```text
BOOT → READY → ZERO
ZERO → WEIGHT_CHANGED → WEIGHT_STABLE
WEIGHT_STABLE → WEIGHT_CHANGED        （重量又动了）
WEIGHT_CHANGED 或 WEIGHT_STABLE → WEIGHT_REMOVED → ZERO
任意称重状态 → OVERLOAD
任意状态 → ERROR
OVERLOAD 或 ERROR → READY             （故障消失）
去皮成功 → ZERO
```

| 状态 | 什么时候进入 | `weight.stable` | `weight.status` |
|---|---|---|---|
| `BOOT` | 刚上电，HX711 还不能读 | `false` | `ok` |
| `READY` | HX711 已经能读出样本 | `false` | `ok` |
| `ZERO` | 净重在 `zero_band_g` 以内，并且已经稳定 | `true` | `ok` |
| `WEIGHT_CHANGED` | 净重超出空秤范围，或者稳定读数又被打破 | `false` | `ok` |
| `WEIGHT_STABLE` | 超出空秤范围，并且连续 `stable_window_ms` 都稳定 | `true` | `ok` |
| `WEIGHT_REMOVED` | 之前在 `WEIGHT_CHANGED` 或 `WEIGHT_STABLE`，现在又回到空秤范围并稳定 | `true` | `ok` |
| `OVERLOAD` | 净重超过 `overload_g` | `false` | `overload` |
| `ERROR` | 连续 1 秒读不到 HX711，或数据线一直不就绪 | `false` | `error` |

`WEIGHT_REMOVED` 只表示“东西被拿走”这一下。这条 `status` 发出后，下一个状态就是 `ZERO`。空秤继续放着时留在 `ZERO`，不要反复发送 `WEIGHT_REMOVED`。

`READY` 同样很短。能读数之后立刻判断：空秤稳定就去 `ZERO`，上面有东西就去 `WEIGHT_CHANGED`。

## 去皮

只有在 `READY`、`ZERO`、`WEIGHT_CHANGED`、`WEIGHT_STABLE`、`WEIGHT_REMOVED` 里才接受去皮。

做法：连续取 10 个新样本求平均，把这个平均值当成新的零点偏移，`tare_g` 改成对应的克数，回复：

```json
{"v":1,"type":"ack","seq":183,"timestamp_ms":193100,"command":"tare","status":"ok"}
```

然后进入 `ZERO`。之后的 `weight_g` 是减去新偏移的净重。

在 `BOOT`、`OVERLOAD`、`ERROR` 里收到去皮命令：不要改偏移，回复 `"status":"error"`，状态保持不变。

## 一条放上再拿走的例子

秤是空的，已经在 `ZERO`。放上一件东西，再拿走。串口上至少应出现这些 `status`：

1. `WEIGHT_CHANGED`
2. `WEIGHT_STABLE`
3. `WEIGHT_REMOVED`
4. `ZERO`

中间每来一个 HX711 新样本，都还有一条 `weight`。稳定之前 `"stable":false`，进入 `WEIGHT_STABLE` 和 `ZERO` 之后 `"stable":true`。

## 固件做到这里就算对齐

HX711 读数、滤波、上面的状态、按 `protocol.md` 打成一行 JSON、从串口发出去、执行去皮、接收 `display_result`。

`display_result` 先能在串口调试助手里看到即可。屏幕以后再接，不挡住这条链路。

不需要实现视觉识别、数据库或电脑上的主机程序。
