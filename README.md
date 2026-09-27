# smart-scale

智能电子秤的 PC 主机仓库。运行时是 `python -m scale_host`，不是 Cursor。

当前进度：**TODO 5.5 显示行**已完成。3.92 元写成协议里的一行 `display_result`，给单片机显示。视觉应答里的 999 元不会出现在这一行里。不打开串口，也不访问外网。5.4 已提交为 `0341533`。

顺序写在 `docs/todo.md`。

这台电脑默认禁止直接运行 `.ps1`。请用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\stm32\projects\smart-scale\scripts\test.ps1
```

报文以 `docs/protocol.md` 为准，状态切换以 `docs/state-machine.md` 为准。`docs/hardware-handoff.docx` 随每个已验收步骤追加进度和文件说明。

识别分两步，都可以换实现，现在都不联网：

1. `VISION_PROVIDER` 选 `minimax` 或 `volcano`，只回答物品名称。
2. `PRODUCT_INFO_PROVIDER=text` 用更小的纯文本模型查单价和简介。
3. 没有 key 时明确失败。key 以后写在本机 `.env`，样例在 `.env.example`，仓库里不放真 key。
4. 默认 `VISION_PROVIDER=mock`。启动主机就会用假秤打出香蕉金额。设为 `disabled` 则只打印开关。SQLite 只存每次称重和纠错，不是商品总价表。

## 本地环境

依赖只装在项目虚拟环境里，不装进全局 Python。

```powershell
C:/stm32/projects/smart-scale/scripts/setup.ps1
C:/stm32/projects/smart-scale/.venv/Scripts/python.exe -m scale_host
```

默认打印：

```text
Smart Scale Host
device: simulator
vision: disabled
```

## 文件夹

| 路径 | 现在的作用 |
|---|---|
| `docs/` | 协议、状态机、给硬件同学的进度说明 |
| `firmware/` | STM32 固件。还是空位，阶段 4 再写 |
| `host/scale_host/` | PC 主机代码 |
| `simulator/` | 场景播放命令。称重规则仍在主机的模拟器里 |
| `tests/` | 日常测试不依赖真 STM32。真板测试只放 `tests/hardware/` |
| `data/` | 测试图片空位。不放全量商品单价 |
| `scripts/` | Windows 脚本：安装环境、启动主机、播放场景、跑测试 |

## 每个文件

| 文件 | 说明 |
|---|---|
| `.env.example` | 开关样例。默认识别和查价都用 mock。MiniMax、火山引擎和文本模型的 key 仍是空的 |
| `.gitignore` | 不提交虚拟环境、`.env`、数据库和 Keil 编译产物 |
| `pyproject.toml` | 项目名称和依赖。日常 pytest 自动排除带 hardware 标记的测试 |
| `docs/protocol.md` | V1 通信协议。一行一个 JSON，串口 115200 8N1 |
| `docs/state-machine.md` | 八个称重状态，以及上电不要自动去皮 |
| `docs/hardware-handoff.docx` | 给硬件同学的进度。每验收一步追加一小段 |
| `docs/todo.md` | 调整后的开发顺序。价格不进本地总表 |
| `docs/adr/.gitkeep` | 以后放架构决定记录。现在是空位 |
| `firmware/README.md` | 说明固件还没写，F103 和 F107 不能混用 |
| `firmware/Core/.gitkeep` | Cube 生成的核心代码以后放这里 |
| `firmware/Drivers/hx711/.gitkeep` | HX711 驱动以后放这里。许可证确认前不拷贝别人的源码 |
| `firmware/App/scale/.gitkeep` | 称重逻辑以后放这里 |
| `firmware/App/protocol/.gitkeep` | 固件侧的 JSON 编码以后放这里 |
| `firmware/App/state_machine/.gitkeep` | 固件侧状态机以后放这里 |
| `host/scale_host/__init__.py` | 包版本号 |
| `host/scale_host/__main__.py` | 让 `python -m scale_host` 能启动 |
| `host/scale_host/main.py` | 启动入口。模拟器打开时打印 3.92 元。串口会真正打开，失败就退出 |
| `host/scale_host/providers.py` | 没 key，或 key 还没接到网络时，抛出的两种错误 |
| `host/scale_host/protocol/messages.py` | 把一行 JSON 变成消息，坏行拒绝 |
| `host/scale_host/protocol/__init__.py` | 导出协议类型 |
| `host/scale_host/domain/models.py` | 程序内部的重量、状态、去皮命令，以及视觉和融合的空数据表 |
| `host/scale_host/domain/__init__.py` | 导出内部数据类型 |
| `host/scale_host/device/interface.py` | 秤的统一接口：连接、读事件、去皮、显示 |
| `host/scale_host/device/dynamics.py` | 按状态机把克数变成稳定、拿走、过载 |
| `host/scale_host/device/simulator.py` | 假秤。香蕉、噪声、拿走、过载、断开 |
| `host/scale_host/device/serial_device.py` | 按 V1 读写串口行。`open_system_port` 以 115200 8N1 打开 COM，打不开就报错 |
| `host/scale_host/device/__init__.py` | 导出设备接口、假秤和串口设备 |
| `host/scale_host/vision/interface.py` | 视觉接口。mock 固定认香蕉；MiniMax 和火山引擎只留空位，不发请求 |
| `host/scale_host/vision/__init__.py` | 导出视觉类型 |
| `host/scale_host/catalog/lookup.py` | 文本查价接口。mock 返回测试单价；真模型没 key 就失败，有占位 key 也不联网 |
| `host/scale_host/quote.py` | 先识别，再按名称查单价。模拟路径打印香蕉和每千克 12 元 |
| `host/scale_host/catalog/__init__.py` | 导出查价类型 |
| `host/scale_host/fusion/price.py` | 稳定重量乘单价，四舍五入到分。未稳定、过载或空秤会拒绝 |
| `host/scale_host/fusion/__init__.py` | 导出金额计算 |
| `host/scale_host/sale.py` | 假秤香蕉稳定后，接上模拟识别和模拟单价，打印 3.92 元 |
| `host/scale_host/serial_replay.py` | 不打开 COM，重放一行稳定重量，打印 3.92 元并写回显示 |
| `host/scale_host/serial_sequence.py` | 不打开 COM。先跳过还在变化的克数，稳定的 326.4 克才计价 |
| `host/scale_host/correct.py` | 把一次称重的商品名改掉，并读回当时的重量和图片路径 |
| `host/scale_host/cloud_request.py` | 写出认物品和查单价两个请求。不包含 key，也不发送 |
| `host/scale_host/loopback.py` | 把这两份请求交给进程内回环。不打开网络 |
| `host/scale_host/response_parse.py` | 把回环 JSON 变成识别结果和单价。视觉回复里的价格不采用 |
| `host/scale_host/reply_sale.py` | 用文本应答里的单价给稳定重量算金额。视觉应答里的价格不参与 |
| `host/scale_host/display_line.py` | 把这笔金额写成协议里的一行 `display_result`。不打开串口 |
| `host/scale_host/pipeline.py` | 把这次金额写入 SQLite，再读出来打印。串口上的稳定重量也走这里 |
| `host/scale_host/storage/records.py` | 一次称重、一条纠错、一条设备事件的数据形状。称重里可以带名称、单价和金额 |
| `host/scale_host/storage/repository.py` | 存储接口。以后可以换数据库，调用方不用改 |
| `host/scale_host/storage/sqlite.py` | 用 Python 自带的 SQLite 存称重、纠错，以及这次的名称、单价和金额。`products` 表只是以后可选的缓存，不是价格来源 |
| `host/scale_host/storage/__init__.py` | 导出存储类型 |
| `host/scale_host/agent/tools/.gitkeep` | 给助手调用的工具以后放这里。助手还没做 |
| `host/scale_host/ui/.gitkeep` | 界面以后放这里。现在只有控制台 |
| `scripts/setup.ps1` | 创建 `.venv` 并安装依赖 |
| `scripts/run_host.ps1` | 启动主机 |
| `scripts/run_simulator.ps1` | 播放场景，默认香蕉 |
| `scripts/run_quote.ps1` | 用模拟识别和模拟查价打出香蕉单价。不联网 |
| `scripts/run_sale.ps1` | 用假秤的稳定重量算出香蕉金额 3.92 元 |
| `scripts/run_record.ps1` | 把这次香蕉金额写入临时数据库，再打印读回的那一行 |
| `scripts/run_serial_replay.ps1` | 重放串口上的稳定重量行，打印 3.92 元。不打开 COM |
| `scripts/run_serial_sequence.ps1` | 重放从 0 克到 326.4 克的过程，只给稳定重量计价 |
| `scripts/run_correct.ps1` | 把这次香蕉改成苹果，并打印当时的重量和图片路径 |
| `scripts/run_request_preview.ps1` | 打印两个云请求的内容。不联网 |
| `scripts/run_loopback.ps1` | 把两份请求交给本机回环，并标明没有发到外网 |
| `scripts/run_parse_response.ps1` | 解析回环应答。视觉里的价格丢掉，文本里的单价保留 |
| `scripts/run_reply_sale.ps1` | 用解析后的文本单价给 326.4 克算出 3.92 元。不联网 |
| `scripts/run_display_line.ps1` | 打印单片机要显示的那一行 JSON。不打开 COM |
| `scripts/test.ps1` | 运行不依赖真板的测试。直接双击会被系统拦住，要用 ExecutionPolicy Bypass 调用 |
| `simulator/__init__.py` | 场景命令的包 |
| `simulator/__main__.py` | `python -m simulator --scenario banana` 的入口 |
| `simulator/scenarios/.gitkeep` | 以后放场景数据文件。现在的场景写在代码里 |
| `data/products/.gitkeep` | 不再作为全量单价表。目录先留着 |
| `data/test_images/.gitkeep` | 测试图片空位 |
| `tests/unit/test_protocol_messages.py` | 协议合法行和坏行 |
| `tests/unit/test_domain_models.py` | 内部数据的形状 |
| `tests/unit/test_simulator.py` | 假秤场景 |
| `tests/unit/test_host_main.py` | 关闭视觉时只打印开关；mock 时打印 3.92 元；串口打不开就退出 |
| `tests/unit/test_serial_device.py` | 假端口读出 326.4 克。打开参数是 115200 8N1。不存在的端口名会失败 |
| `tests/unit/test_serial_replay.py` | 重放的稳定重量打出 3.92 元，并写回显示行 |
| `tests/unit/test_serial_sequence.py` | 前 5 次重量被跳过，326.4 克才是 3.92 元 |
| `tests/unit/test_correct.py` | 纠错能读回预测名、正确名、326.4 克和图片路径 |
| `tests/unit/test_cloud_request.py` | 视觉请求不查价，文本请求不看图片，输出里没有 key |
| `tests/unit/test_loopback.py` | 回环收到两份请求。拦截网络调用后仍然成功 |
| `tests/unit/test_response_parse.py` | 视觉应答里的 999 不进入结果，文本应答的 12 元保留 |
| `tests/unit/test_reply_sale.py` | 视觉应答里的 999 不改变金额，326.4 克仍是 3.92 元 |
| `tests/unit/test_display_line.py` | 显示行是香蕉、326.4 克、3.92 元，正文里没有 999 |
| `tests/unit/test_providers.py` | 模拟识别和模拟查价不联网；云模型没 key 会失败 |
| `tests/unit/test_quote.py` | 识别出的名称会交给查价；模拟命令打出香蕉和 12 元 |
| `tests/unit/test_fusion.py` | 326.4 克乘 12 元/千克等于 3.92 元；不稳定时拒绝 |
| `tests/unit/test_simulator_cli.py` | 香蕉场景命令打出的克数 |
| `tests/unit/test_dynamics.py` | 连续半秒几乎不动才算稳定；波动超过 0.5 克不算 |
| `tests/unit/test_sqlite_repository.py` | 称重和纠错能写入数据库再读回 |
| `tests/unit/.gitkeep` | 保留单元测试目录 |
| `tests/integration/.gitkeep` | 保留集成测试目录 |
| `tests/integration/test_banana_pipeline.py` | 假秤到数据库的整条香蕉记录，读回 3.92 元 |
| `tests/hardware/test_board_optional.py` | 真板测试占位。日常运行会跳过它 |
