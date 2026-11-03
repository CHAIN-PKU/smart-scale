# 手机网页交接：关掉后再进必须重连热点

2026-11-03 晚贺琬婷确认 Wi-Fi 已经解决。下面是解决前的现场记录，不要再按这份去改固件。当前进度以 `docs/todo.md` 和 `C:\stm32\memory.md` 第 9 节为准。

写给下一次对话。用户要的是：手机连上秤自己的热点后，反复打开网页都稳定，不要每次都去 Wi-Fi 设置里重连。

用户原话（2026-11-03）：「好像是需要我把 smartscale 重连一次，才能二次打开。」

## 现在的现象

已经稳定的部分：

- 手机连热点 **SmartScale**，密码 **12345678**。
- 第一次打开 `http://192.168.4.1/records` 或 `http://192.168.4.1/receipt` 能看到做好的手机页面。
- 页面里点「刷新这一页」可以。
- 电脑上的查询程序在跑，秤能向电脑要记录，再把 HTML 发回手机。
- 手机提示「无法访问互联网」是正常的。这个热点不上网。地址必须用 `http`，不要用 `https`，不要搜索这个 IP。

还没解决的部分：

- 把网页关掉，再打开，打不开。
- 此时手机仍然显示连着 SmartScale。
- 只有到 Wi-Fi 里把 SmartScale 断开再连上，才能再打开一次。
- 刷新能成、关掉再进不成。重连热点又能成一次。

## 现场证据

电脑日志在这次对话的终端里，主机从 2026-11-03 16:51 起一直占着 COM4，后来烧录后日志里能看到新一轮 `wifi:AT` … `wifi:up`。

第一次能看的纯文本固件之后，页面请求是成串出现的：

```text
wifi:get
wifi:AT+CIPSEND=0,1858
wifi:AT+CIPCLOSE=0
```

全部是链路 0，没有 1、2、3、4。说明浏览器后来的连接，固件并没有按真实链路号关掉。

当前烧进去的固件（约 17:29，29244 字节）会在空闲时不停打扫：

```text
wifi:AT
wifi:AT+CIPCLOSE=5
wifi:AT+CIPSERVER=1,80
```

大约每 5 秒一轮，中间夹着成功的 `wifi:get`。用户关掉页面后再进时，日志里往往不再出现新的 `wifi:get`。请求没到单片机。重连热点后才会再出现 `wifi:get`。

这说明：手机的 Wi-Fi 关联还在，但到 192.168.4.1:80 的新 TCP 已经进不来。重连热点会让站点重新关联，ESP 侧的客户端表被重建，所以又能打开一次。

## 最可疑的原因（还没改）

下一次对话不要先加功能。先拿掉现在这段「清场」。

`board/chengzhong/Core/Src/wifi.c` 里的 `wifi_broom_begin()` 会在空闲时发：

1. `AT`
2. `AT+CIPCLOSE=5`（CIPMUX=1 时，5 表示关掉全部 TCP）
3. `AT+CIPSERVER=1,80`（反复重新打开网页服务）

触发条件在 `Wifi_Poll()` 末尾：空闲、安静超过 600ms，并且（刚服务过页面，或距上次打扫超过 5 秒）。

这是为了修「5 个连接名额被占满」加上的，但日志证明它自己在反复踢网页服务。很多 ESP-01 AT 固件上，对已关联的手机反复 `CIPCLOSE=5` / 重开 `CIPSERVER`，会出现「Wi-Fi 还连着，但 80 端口不再接受这个站点，直到手机重新关联」。和用户描述一致。

建议的改法：

1. 删掉周期打扫，以及 `AT+CIPCLOSE=5`、反复 `AT+CIPSERVER=1,80`。不要每几秒重开服务。
2. 保留「一条 AT 命令必须等真正的 `OK` 或 `ERROR` 再发下一条」。不要把 `0,CLOSED` 当成命令结束，否则下一条 AT 会插进模块还没说完的回答里，模块会乱。
3. 页面发出去并看到 `SEND OK` 之后，只 `AT+CIPCLOSE=<这一条链路>`，然后等 `OK`。
4. 图标、探测这类不是 `/records`、`/receipt`、`/` 的 GET，立刻按它自己的链路号关掉，不要拿去向电脑要整页。
5. 启动时加一条 `AT+SLEEP=0`，关掉 ESP 的省电。软 AP 默认会睡，已关联的手机会出现「必须重连热点才能再打开网页」。这是第二条要验证的原因，放在删掉打扫之后。
6. 启动顺序里现在有 `AT+CIPSERVER=1,80` 得到 `no change`。模块没随单片机复位，服务是上次留下来的。若删掉打扫后仍然必须重连，再考虑只在开机时做一次 `AT+CIPSERVER=0` 然后 `AT+CIPSERVER=1,80`，平时不要重开。

验证方法：烧录后手机连上 SmartScale，打开 records，关掉，等两秒，不再动 Wi-Fi，直接再打开。要能重复几次。同时看电脑日志：空闲时不应再刷 `AT+CIPCLOSE=5`；第二次打开应出现新的 `wifi:get`，而不是只有打扫命令。

## 不要再走回头路

这些已经试过，不要原样加回去：

- 页面每 8 秒 `<meta http-equiv=refresh>`。每次刷新都是一条新 TCP，5 个名额很快满。用户要求过自动刷新，后来为了连接稳定拿掉了。刷新按钮还在。
- 任何 GET（包括 `/favicon.ico`）都当成称重记录去问电脑。favicon 会占住唯一一次应答，真正的页面被关掉。
- `+IPD` 和 `GET` 必须在同一行。ESP 经常先来一行 `+IPD,0,长度:`，GET 在下一行。只认同一行时，页面一次都打不开。当前用 `s_seen` 记住链路号。
- 没等到 `>` 和 `SEND OK` 就发下一条 AT，或在等 `>` 时把没有 GET 的 `+IPD` 直接 `CIPCLOSE`。
- 用电脑的 `http://127.0.0.1:8765` 给手机看。手机在 ESP 热点上，访问不到电脑网段。网页必须由单片机经 ESP 发出去。

## 数据路径

```text
手机浏览器
  -> ESP-01 软 AP（192.168.4.1:80）
  -> USART3（PD8 发 / PD9 收，115200）
  -> STM32 发现 GET /records 或 GET /receipt
  -> USART1（COM4，115200）发一行 JSON
  -> 电脑 SQLite
  -> 电脑回 {"v":1,"type":"wifi_page","text":"..."}
  -> STM32 把 text 填进 HTML，AT+CIPSEND 给手机
```

问电脑的那一行：

```json
{"v":1,"type":"query","query":"records"}
```

`query` 为 `records` 或 `receipt`。协议版本仍是 `docs/protocol.md` 的 V1，不要另起一套固件目录。

电脑回的 `text` 不能有双引号，必须是一行短文本。固件用 `"` 截取，缓冲区大约 480 字节。格式：

- 记录：`香蕉|221.4|2.66;橙子|247.6|1.98`，没有记录就是空字符串。
- 清单：同样的行，最后加 `#6.58`。空清单是 `#0.00`。
- 没有 `|` 的一句中文（例如电脑没回答）整句放进一张空状态卡片。

固件里的界面中文必须写成 UTF-8 的 `\xe6\x99\xba...` 这种转义。Keil 在这台电脑上会按 GBK 读源文件，直接写中文字符串会乱码。注释可以是中文。HTTP 头是 `Content-Type: text/html; charset=utf-8`。

页面样子：暖色纸底 `#f3efe6`，深绿顶栏 `#1e3d34`，金色当前按钮 `#e4c27a`，白卡片。顶栏 SMART SCALE / 智能电子秤。两个按钮链到 `/records` 和 `/receipt`。一行是名称、重量和「克」、价格和「元」。清单底部有合计。不要把自动刷新加回去，除非连接问题已经确认修好。

HTML 模板在固件 ROM 里。`s_page` 约 3072 字节，在 BSS，不占 32KB 限制。整页大约 1600–1900 字节。ESP 的 `AT+CIPSEND` 常见上限是 2048，不要把页面做大。记录最多 5 条，这是电脑 `wifi_page()` 的 `compact` 限制。

## 硬件和接线（不要改）

- 模块是 ESP-01（ESP8266，丝印 AI-Cloud inside），插在绿灯板 ESP8266 的 2×4 座。上面那个座是 BLUETOOTH，不是这个模块。
- 3.3V。CH_PD/EN 必须拉高。GPIO0 启动时不能接地。
- 板子排针没有 PC10/PC11。Wi-Fi 用 USART3 完全重映射：单片机 TX PD8 → 模块 RX，单片机 RX PD9 ← 模块 TX。`__HAL_AFIO_REMAP_USART3_ENABLE()`。中断函数名仍是 `USART3_IRQHandler`，里面调用 `Wifi_Uart4Isr`。变量仍叫 `huart4`，但 `Instance` 是 USART3。
- 用户已经接好：座子 RX→PD8，座子 TX→PD9，EN→3.3V。地用座子自己的地。这两根线只为 Wi-Fi。
- USART1 PA9/PA10 是电脑串口，115200，这台机器是 **COM4**（CH340，VID_1A86 PID_7523）。不要占用 PA9。
- USART2 PA2/PA3 是语音模块，9600。不要占用。
- 屏用 SPI2 的 PB9–PB15，所以 PB10/PB11 不能当 USART3 默认脚。
- HX711 在 PB0/PB1。按键：去皮 PA1，保存 PE6，清单 PE7，清除 PC6。
- 打开 COM4 时 DTR 和 RTS 必须先拉低再 open，再拉低一次。DTR 会把这块板按在复位里。
- 用户可以自己按板上的复位键。没有新固件时不要为了 Wi-Fi 去动 ST-Link。
- ST-Link 是 VID_0483 PID_3748。烧录会让热点掉线，手机必须重新连 SmartScale。
- 这块板的秤口是 COM4，不是脚本默认的 COM3。
- OpenMV 是另一根 USB 串口，经常是 COM5，不要从 F107 供电。这次 Wi-Fi 工作没有接 OpenMV，不要为了网页去启动它。

## 电脑侧

工程：`C:\stm32\projects\smart-scale`

查询文本在 `host/scale_host/remote_query.py` 的 `wifi_page()`。测试在 `tests/unit/test_remote_query.py`，断言是 `香蕉|221.4|2.66`、没有双引号、长度小于 400。改文本格式必须一起改测试。

当前查询进程是这次对话留下的，还占着 COM4。启动方式：

```powershell
cd C:\stm32\projects\smart-scale
$env:SCALE_DEVICE="serial"
$env:SERIAL_PORT="COM4"
$env:OPENMV_PORT=""
$env:VISION_PROVIDER="yolo"
$env:PRODUCT_INFO_PROVIDER="table"
$env:DESK="1"
.\.venv\Scripts\python.exe -m scale_host
```

`.env` 里写的是模拟器，不要靠它。`load_dotenv(override=False)`，所以必须在启动前设好环境变量。`OPENMV_PORT` 置空，否则没接相机时进程会退出。

看到 `serial_open: ok` 和 `desk: http://127.0.0.1:8765` 才算起来。桌面页只给电脑看。不要再开第二个进程，否则 COM4 会被占用。以 `wifi:` 开头的行是固件调试输出，主机打印它们。

改 Python 的 `wifi_page()` 之后必须关掉旧进程再开，否则秤拿到的还是旧句子。只改固件、不改文本格式时，不要关这个进程。烧录走 ST-Link，不占用 COM4，进程可以留着。

## 固件怎么编、怎么烧

Keil 评估版限制：只读 + 已初始化读写合计不超过 **32768** 字节。ZI（BSS）不算。当前大约 **29244** 字节 Flash，RAM/ZI 大约 **9920**。还有大约 3KB。中文字符串和 HTML 模板都算在 32KB 里。

MicroLIB 开着（`useUlib=1`），优化级别 4。不要用破解许可。不要为了省空间去恢复或再删 TIM；以前删过 `hal_tim.c`，并不是体积胜利。

编译和烧录要分开跑，PowerShell 不接受 `&&`：

```powershell
python C:\Users\wantinghe\.cursor\skills\keil\scripts\keil_build.py build --uv4 C:\stm32\Keil_v5\UV4\UV4.exe --project C:\stm32\projects\smart-scale\board\chengzhong\chengzhong.uvprojx --target chengzhong --log-dir C:\stm32\_work --json
python C:\Users\wantinghe\.cursor\skills\keil\scripts\keil_build.py flash --uv4 C:\stm32\Keil_v5\UV4\UV4.exe --project C:\stm32\projects\smart-scale\board\chengzhong\chengzhong.uvprojx --target chengzhong --log-dir C:\stm32\_work --json
```

成功标志在 `C:\stm32\_work\chengzhong-chengzhong-flash.log`：`Erase Done.Programming Done.Verify OK.Application running`。

烧完告诉用户：重新连接 SmartScale，再打开 `http://192.168.4.1/records`。

## 固件里和连接有关的状态

文件：`board/chengzhong/Core/Src/wifi.c`。`WIFI_ENABLE` 在 `config.h`。

阶段：0 `AT`，1 `AT+CWMODE=2`，2 `AT+CWSAP="SmartScale","12345678",5,3`，3 `AT+CIPMUX=1`，4 `AT+CIPSERVER=1,80`，5 运行，6 已发 `AT+CIPSEND` 在等 `>` 和 `SEND OK`，7 放弃。

运行后还会发 `AT+CIPSTO=2`。超时太短可能在电脑回答慢时把连接掐掉；电脑正常时回答很快。不要为了「释放名额」把服务整段重启。

`main.c` 的开机画面循环里必须同时调用 `Proto_Poll()` 和 `Wifi_Poll()`。漏掉 `Proto_Poll` 时，电脑的 JSON 要等到按下去皮才被读到，网页会一直等到兜底句。兜底句是「电脑还没有回答，请再刷新一次。」

`Wifi_OnPcLine()` 从电脑那一行里取出 `"text":"..."` 再组 HTML。组页面用追加，不要用 `sprintf` 吃用户文本，文本里的 `%` 会把格式弄坏。

## 其它约束

- 称重记录和清单在电脑 SQLite，不在单片机上。
- 不要新开第二套固件工程。
- 不要 git commit，不要 push，除非用户明确说。
- `docs/todo.md` 里那次 2026-10-27 的烧录记录已经过时，用户没要求改它。
- OpenMV 实时画面是老师的另一项，这次不要挡网页。
- 电脑自己的 Wi-Fi 是 5GHz，经常扫不到 ESP 的 2.4GHz 热点。不要为了扫描去断开电脑的网。
- 用户是贺琬婷。自定义 PCB 和硬件归曾燕。这项是用户自己的：无线查记录和清单，以及电脑上看 OpenMV。当前只做网页这一段。
