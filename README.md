# smart-scale

智能电子秤的 PC 主机仓库。运行时是 `python -m scale_host`，不是 Cursor。

当前进度：**TODO 1.6 日常测试**已验收。不插板子时日常测试全绿。真板测试要单独点名才会跑。

这台电脑默认禁止直接运行 `.ps1`。请用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\stm32\projects\smart-scale\scripts\test.ps1
```

报文以 `docs/protocol.md` 为准，状态切换以 `docs/state-machine.md` 为准。`docs/hardware-handoff.docx` 随每个已验收步骤追加进度和文件说明。

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
| `data/` | 商品表和测试图片，现在是空位 |
| `scripts/` | Windows 脚本：安装环境、启动主机、播放场景、跑测试 |

## 每个文件

| 文件 | 说明 |
|---|---|
| `.env.example` | 开关样例：设备用模拟器还是串口，视觉开不开，数据库文件放哪 |
| `.gitignore` | 不提交虚拟环境、`.env`、数据库和 Keil 编译产物 |
| `pyproject.toml` | 项目名称和依赖。日常 pytest 自动排除带 hardware 标记的测试 |
| `docs/protocol.md` | V1 通信协议。一行一个 JSON，串口 115200 8N1 |
| `docs/state-machine.md` | 八个称重状态，以及上电不要自动去皮 |
| `docs/hardware-handoff.docx` | 给硬件同学的进度。每验收一步追加一小段 |
| `docs/adr/.gitkeep` | 以后放架构决定记录。现在是空位 |
| `firmware/README.md` | 说明固件还没写，F103 和 F107 不能混用 |
| `firmware/Core/.gitkeep` | Cube 生成的核心代码以后放这里 |
| `firmware/Drivers/hx711/.gitkeep` | HX711 驱动以后放这里。许可证确认前不拷贝别人的源码 |
| `firmware/App/scale/.gitkeep` | 称重逻辑以后放这里 |
| `firmware/App/protocol/.gitkeep` | 固件侧的 JSON 编码以后放这里 |
| `firmware/App/state_machine/.gitkeep` | 固件侧状态机以后放这里 |
| `host/scale_host/__init__.py` | 包版本号 |
| `host/scale_host/__main__.py` | 让 `python -m scale_host` 能启动 |
| `host/scale_host/main.py` | 读环境变量并打印设备名和视觉开关 |
| `host/scale_host/protocol/messages.py` | 把一行 JSON 变成消息，坏行拒绝 |
| `host/scale_host/protocol/__init__.py` | 导出协议类型 |
| `host/scale_host/domain/models.py` | 程序内部的重量、状态、去皮命令，以及视觉和融合的空数据表 |
| `host/scale_host/domain/__init__.py` | 导出内部数据类型 |
| `host/scale_host/device/interface.py` | 秤的统一接口：连接、读事件、去皮、显示 |
| `host/scale_host/device/dynamics.py` | 按状态机把克数变成稳定、拿走、过载 |
| `host/scale_host/device/simulator.py` | 假秤。香蕉、噪声、拿走、过载、断开 |
| `host/scale_host/device/__init__.py` | 导出设备接口和假秤 |
| `host/scale_host/vision/.gitkeep` | 视觉实现以后放这里。现在关闭 |
| `host/scale_host/fusion/.gitkeep` | 重量和视觉的融合以后放这里 |
| `host/scale_host/storage/.gitkeep` | 数据库以后放这里 |
| `host/scale_host/agent/tools/.gitkeep` | 给助手调用的工具以后放这里。助手还没做 |
| `host/scale_host/ui/.gitkeep` | 界面以后放这里。现在只有控制台 |
| `scripts/setup.ps1` | 创建 `.venv` 并安装依赖 |
| `scripts/run_host.ps1` | 启动主机 |
| `scripts/run_simulator.ps1` | 播放场景，默认香蕉 |
| `scripts/test.ps1` | 运行不依赖真板的测试。直接双击会被系统拦住，要用 ExecutionPolicy Bypass 调用 |
| `simulator/__init__.py` | 场景命令的包 |
| `simulator/__main__.py` | `python -m simulator --scenario banana` 的入口 |
| `simulator/scenarios/.gitkeep` | 以后放场景数据文件。现在的场景写在代码里 |
| `data/products/.gitkeep` | 商品表空位 |
| `data/test_images/.gitkeep` | 测试图片空位 |
| `tests/unit/test_protocol_messages.py` | 协议合法行和坏行 |
| `tests/unit/test_domain_models.py` | 内部数据的形状 |
| `tests/unit/test_simulator.py` | 假秤场景 |
| `tests/unit/test_host_main.py` | 启动时打印的三行字 |
| `tests/unit/test_simulator_cli.py` | 香蕉场景命令打出的克数 |
| `tests/unit/test_dynamics.py` | 连续半秒几乎不动才算稳定；波动超过 0.5 克不算 |
| `tests/unit/.gitkeep` | 保留单元测试目录 |
| `tests/integration/.gitkeep` | 集成测试空位 |
| `tests/hardware/test_board_optional.py` | 真板测试占位。日常运行会跳过它 |
