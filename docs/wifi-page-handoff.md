# 手机网页交接：网页打不开

写给下一次对话。用户是贺琬婷。2026-11-03 20:41 她说「现在手机网页又打不开了」，接着要求把当前 bug 写成这份交接。不要再按这份文件更早的版本改固件：那里的 `AT+CIPCLOSE=5` 和反复 `AT+CIPSERVER` 已经证实会把网页服务踢掉。

## 用户现在要的

手机连热点 **SmartScale**，密码 **12345678**，打开 `http://192.168.4.1/`。页面打不开，是连不上，不是单纯慢。烧录后热点会掉，必须先断开再连上这个热点，再用 `http`，不要用 `https`。

上一轮她已经确认过的、不要推倒重来的行为：

- 手机页是和 TFT 一样的深色计价画面。下面有复位、去皮、保存、清空、记录、清单。
- 复位、去皮、保存、清空要播报：已复位、已去皮、已保存、已清空。板子上的去皮、保存、清空也播这三句。记录和清单不播。
- 板子上的清单键能显示真实清单。手机上点清单，手机里能看到清单；用手机点清单时，板子上曾经是空的。这个已经改成网页发完再向电脑要清单，**还没在这块新固件上复测**。
- 手机按键曾经很迟。已经改成先把网页发出去、关掉连接，再画屏幕，**还没复测手感**。她紧接着就说网页打不开了。

## 这次打不开的原因

电脑上的查询进程从 19:07 起占着秤的串口，日志在：

`C:\Users\wantinghe\.cursor\projects\c\terminals\166985.txt`

启动命令是 `scripts\run_board.ps1 -CameraPort COM5 -ScalePort COM3`。它把 `wifi:` 开头的调试行打出来。不要再开第二个进程，不要改 `.env`（`.env` 仍是模拟器）。COM3 是 `USB-SERIAL CH340`。打开这个口时 DTR、RTS 必须保持低，否则板子停在复位。

20:25 那版固件起来之后，日志里先有一次正常网页：

```text
wifi:up
wifi:get
wifi:AT+CIPSEND=0,1154
wifi:AT+CIPCLOSE=0
```

然后手机仍连着 `192.168.4.2`，固件不停回答域名查询（链路 4，UDP）。中间有 `wifi:connect`，但没有对应的 `wifi:get`，也没有再发 `AT+CIPCLOSE`。大约 4878 行以后只剩 `wifi:dnsq` / `wifi:dns` / `AT+CIPSEND=4,...`，新的网页连接不再出现。到交接时这份日志大约 5838 行，末尾仍是这种域名发送。

原因有两层，都在 `board\chengzhong\Core\Src\wifi.c`：

1. 每个 A 记录都答成 `192.168.4.1`（`wifi_dns_reply` 里的 16 字节答案）。手机于是对所有域名都来连这台秤，包括加密连接。加密连接没有 `GET`，旧代码看到不是网页就直接返回，不关连接。ESP 只有链路 0–3 能做网页，链路 4 是域名。四条被占满后，浏览器再开 `http://192.168.4.1/` 就进不来。
2. 一条域名发送刚结束，马上又发下一条。已经排上队的网页要等 `s_dns_ready == 0` 才发送，所以域名不停时网页永远排不上。`CONNECT` 到达后，请求正文经常还没读到，通道又被下一条域名占用。

`wifi:silent` 没有出现。服务曾经起来过，不是模块没启动，也不是页面超过 2048 字节。当时首页大约 1157 字节。

## 已经写进固件、烧过、但手机还没确认

2026-11-03 20:38 编译通过，32756 字节，RAM 14632。评估版上限 32768，只剩 12 字节。20:40:19 烧录日志是 `Erase Done.Programming Done.Verify OK.Application running`，文件是 `C:\stm32\_work\chengzhong-chengzhong-flash.log`。烧的是 `board\chengzhong\Objects\chengzhong.hex`，工程 `board\chengzhong\chengzhong.uvprojx`，Target `chengzhong`。

这次改动：

- 链路 0–3 一 `CONNECT`，`s_tcp_due` 向后推 500 ms。这段时间不回答域名，先把网页读出来。
- 有排队的网页（`s_next_ok`）或还没关掉的连接（`s_drop`）时，不开始下一条域名。排队的网页排在域名前面发。
- `+IPD` 正文不是 `GET` 也不是 `HTTP` 时，关掉这条连接。只有 `+IPD` 头、还没有正文时不关。已经认过的网页，后面的 `Host` 之类不要误关（`s_http`）。
- 去掉 `wifi:dnsq` 和 `wifi:dns` 两行调试，并缩短了 `WIFI_CSS`，否则链接器报 32876 字节。页面少了居中和两端对齐，深色和按钮还在。不要把 CSS 加回去，除非同时砍掉同样多的代码。

烧完之后，上面那份主机日志还没出现新的一轮 `wifi:AT` … `wifi:up`。不能据此说手机已经能打开。下一位先看日志末尾：有新的 `wifi:up`，再让用户重连热点后打开首页。成功时应看到 `wifi:connect` 后面跟上 `wifi:get` 或 `wifi:probe`，占着名额的连接要有 `AT+CIPCLOSE`。如果仍是连上就再无 `wifi:get`，这次修改没有解决问题，继续查，不要恢复 `CIPCLOSE=5`。

## 不要动的东西

- 不要改标定、HX711、SPI2、USART1、语音线。不要重写选项字节。
- Keil 源文件里的中文必须写成 UTF-8 的 `\x` 转义。Keil 按 GBK 读源文件。
- 语音口是 USART2，PA2/PA3，9600 8N1，GBK。已去皮 `D2 D1 C8 A5 C6 A4`，已保存 `D2 D1 B1 A3 B4 E6`，已清空 `D2 D1 C7 E5 BF D5`，已复位 `D2 D1 B8 B4 CE BB`。去皮只在 `Scale_Tare()` 成功时播。复位是页面发出去之后再 `NVIC_SystemReset()`。
- 网页必须留在大约 2048 字节以内，`s_page` 是 3072。超了 `wifi_ship` 会直接返回，`s_hold` 会一直为 1，后面的网页全部不再发送。
- 记录和清单的内容来自电脑。主机对查询回的是短文本 `wifi_page`（`名称|克数|价格`，清单以 `#合计` 结尾），不是 `receipt_result`。板子上的清单屏只认 `receipt_result`。手机点清单时，要等这一页发完再 `Proto_SendCommand("receipt")`。不要再调用 `TFT_ShowReceipt(NULL, 0, 0)`，那会把板子上的清单画空。
- 浏览器要等连接关闭才算这一页完成。先 `AT+CIPCLOSE`，再画 TFT。画屏幕时不要把 2048 字节的串口环形缓冲撑满。
- 栈是 `startup_stm32f107xc.s` 里的 `Stack_Size EQU 0x00001000`。大缓冲已经是 `static`。MCU 是 STM32F107VC，HAL。Keil 在 `C:\stm32\Keil_v5\UV4\UV4.exe`。ST-Link 是 `USB\VID_0483&PID_3748`。
- 编译和烧录（PowerShell 不要用 `&&`）：

```powershell
python C:\Users\wantinghe\.cursor\skills\keil\scripts\keil_build.py build --uv4 C:\stm32\Keil_v5\UV4\UV4.exe --project C:\stm32\projects\smart-scale\board\chengzhong\chengzhong.uvprojx --target chengzhong --log-dir C:\stm32\_work --json
python C:\Users\wantinghe\.cursor\skills\keil\scripts\keil_build.py flash --uv4 C:\stm32\Keil_v5\UV4\UV4.exe --project C:\stm32\projects\smart-scale\board\chengzhong\chengzhong.uvprojx --target chengzhong --log-dir C:\stm32\_work --json
```

烧录成功要看到 `Verify OK` 和 `Application running`。然后告诉用户重连 SmartScale，打开 `http://192.168.4.1/`。
