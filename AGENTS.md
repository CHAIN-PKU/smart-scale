# smart-scale 项目规则（C:\stm32\projects\smart-scale）

适用范围：`C:\stm32\projects\smart-scale` 及其子目录。这是独立 git 项目；进入本目录后，本文件优先于 `C:\stm32\AGENTS.md`。全局规则仍然有效。

## 一、项目边界与分工

1. 贺琬婷负责 PC 主机、识别、短表、金额/营养计算、小票与联调；曾燕负责传感器、标定、固件 `board/chengzhong`、OpenMV 当前画面、TFT 与语音。
2. 固件真源是 `board/chengzhong`。不要在 `firmware/` 另起一份固件树，不要把 Python 主机烧进 STM32，不要重刷曾燕的固件，除非用户明确要求。
3. 主机入口是 `python -m scale_host`。OpenMV 脚本在 `openmv/usb_stream.py`，模型在 `models/yolo11n.onnx`。
4. 协议 V1 与八个状态已冻结。不要新增不计价边角状态，不要改协议字段名；扩展前先读 `docs/protocol.md` 与 `docs/state-machine.md`。

## 二、协议与业务硬规则

5. 串口一行一个 JSON。`product` 发英文名；不加 `product_cn`。
6. `display_result` 包含英文 `product`、克数、金额，以及 `price_per_kg`、`portion_kcal`、`portion_carb_g`、`portion_fiber_g`；没有营养数据时不写后三项。
7. 短表只对表内商品出价；表外名字不出价。演示价不是真实售价。香蕉每千克 12 元、每 100 克 91 千卡、碳水 22 克、膳食纤维 1.2 克；橙子演示价每千克 8 元。其余商品按项目短表与《中国食物成分表》数据，不凭记忆补。
8. 同一份放上只算一次；漂过 0.5 克后再稳定不发第二笔；拿走再放才算下一笔。低于 5 克不计价。
9. 空秤先去皮；水果还在秤上时按去皮会把净重打成 0，屏幕不出价。这是已知交互，不是程序 bug。
10. 语音只念商品名、克数、金额；不念营养，不先报重量，不加 `product_cn`。只在新的计价出现时播报。
11. 照片只用于认名字；视觉返回的价格和营养丢弃，价格与营养由主机短表计算。旧照片不算“这一次”的画面。
12. 屏幕同一屏显示名称、单价、重量、金额与这一份营养；正式屏幕是曾燕的 TFT，主机对照页只用于联调。

## 三、硬件与接线（不得擅自改）

13. 秤 MCU 是 STM32F107VC，HAL；不要把 SPL 的 F103C8 示例拷进固件。
14. HX711：DT→PB0，SCK→PB1，5V、地。标定 RAW -411362、每克 438.71；满量程 5 kg，过载线 4500 克。未经批准不改标定与接线。
15. TFT 使用测试工程 SPI2：CS→PB11，RESET→PB12，DC→PB10，SDI→PB15，SCK→PB13，LED→PB9，SDO→PB14；触摸不接。
16. USART1 仍是 PA9 发送、PA10 接收。语音模块 PA2/PA3，CN-TTS，5V，UART 9600 8N1，GBK。去皮键 PA1；保存 SW2→PE6，清单 SW3→PE7，清空 SW4→PC6。
17. OpenMV Cam H7 Plus 插电脑 USB，不接 F107，不从 F107 供电。主机运行时不要在 OpenMV IDE 里连接相机，否则相机会被占住。
18. 串口以设备管理器或 `[System.IO.Ports.SerialPort]::GetPortNames()` 现查为准，不写死 COM 号。同一台机历史上出现过多个不同 COM 号；重插后会变。
19. 烧录/调试只按用户明确指令执行；不做 option bytes、全片擦除、RDP 解锁。未经要求不安装 J-Link/PL2303 等驱动。
20. 固件受 MicroLIB 与 32KB 限制；改固件前先确认当前镜像与剩余空间，不凭“编译过了”判断能上板。

## 四、运行与验证

模拟器（默认 `.env` 为 simulator + mock，不接硬件）：

```powershell
C:\stm32\projects\smart-scale\.venv\Scripts\python.exe -m scale_host
```

测试：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\stm32\projects\smart-scale\scripts\test.ps1
```

上板（先枚举 COM，再把占位符换成现场值；不要直接照抄历史端口）：

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
powershell -NoProfile -ExecutionPolicy Bypass -File C:\stm32\projects\smart-scale\scripts\run_board.ps1 -CameraPort <CAMERA_COM> -ScalePort <SCALE_COM>
```

看到 `openmv_frame: ok` 与 `serial_open: ok` 后再放水果。Wi-Fi 查询进程的启动方式见 `docs/todo.md` 的 2026-11-03 代码块；不要双开占用串口。

21. 汇报按层：静态检查 → 生成 → 编译链接 → 探针/烧录 → 板上 I/O → 仪器/闭环。编译成功不等于灯亮或屏幕出价。
22. 上板脚本只给那一个进程改环境变量；不要为了上板把 `.env` 长期改成 serial。`.env` 含密钥，永不提交、永不贴出明文。
23. 测试失败时给原始报错与失败层；不要用“应该可以”收尾。硬件不在位时明说“阻塞：等插板”，不空跑假装验收。

## 五、Git 与交付

24. 未经用户明确要求，不 `git commit`、不 `git push`、不改 `git config`。用户验收通过后，才提交刚验收的那一步。
25. 不提交：`.env`、`data/test_images/*.jpg`、`firmware/` 未跟踪树、`docs/firmware-handoff.docx`、与主机无关的 `.gitignore`/README 改动。
26. 远程状态以 `git status`、`git log`、`git rev-list --left-right --count origin/main...HEAD` 的实时输出为准，不引用旧 memory 里的 commit hash。
27. 提交信息用完整句子，说明“为什么”而不只是“改了什么”；不跳过 hooks，不用 force push/hard reset。

## 六、会话开头

进入本项目后按顺序读：`AGENTS.md`（本文件）→ `docs/todo.md` → `docs/protocol.md` → `docs/state-machine.md` → `C:\Users\wantinghe\.cursor\ee-rag\memory.md` 第 9 节。不要同时读迁移包里的 `02-MEMORIES.md` 副本。当前完整任务台账在 DSH 工作区的 `TASKS.md`，项目内进度仍以 `docs/todo.md` 为准。
