# smart-scale

智能电子秤的 PC 主机仓库。运行时是 `python -m scale_host`，不是 Cursor。

当前进度：**TODO 0.2 项目虚拟环境**。协议、模拟器、主机程序都还没写。

## 目录

| 路径 | 以后放什么 |
|---|---|
| `docs/` | 协议、状态机、校准。硬件同学只看这里 |
| `firmware/` | STM32 固件。阶段 4 再写，现在是空的 |
| `host/scale_host/` | PC 主机。设备、视觉、融合、数据库都从这里换实现 |
| `simulator/` | 没有板子时的称重场景 |
| `tests/` | 日常测试不依赖真 STM32。真板测试只放 `tests/hardware/` |
| `data/` | 商品表和测试图片 |
| `scripts/` | Windows 启动脚本 |

## 本地环境

依赖只装在项目虚拟环境里，不装进全局 Python。

```powershell
C:\stm32\projects\smart-scale\scripts\setup.ps1
```

解释器是 `C:\stm32\projects\smart-scale\.venv\Scripts\python.exe`。

主机入口还没写，所以这一步仍然不能 `python -m scale_host`。
